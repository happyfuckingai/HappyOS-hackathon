"""
Performance optimizations for DynamoDB operations to achieve sub-second latency
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import time

from botocore.exceptions import ClientError

from ...models.ui_resource import UIResource, UIResourceQuery
from .client import DynamoDBClient
from .config import DynamoDBConfig
from .operations import DynamoDBOperations

logger = logging.getLogger(__name__)


class PerformanceOptimizedOperations(DynamoDBOperations):
    """
    Performance-optimized DynamoDB operations for sub-second latency
    
    Optimizations:
    - Batch operations for bulk reads/writes
    - Connection pooling and reuse
    - Parallel query execution
    - Query result caching
    - Optimized key patterns
    """
    
    def __init__(self, client: DynamoDBClient):
        super().__init__(client)
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.query_cache: Dict[str, Tuple[List[UIResource], float]] = {}
        self.cache_ttl = 5.0  # 5 second cache TTL for hot queries
        
        # Performance metrics
        self.operation_times: Dict[str, List[float]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _record_operation_time(self, operation: str, duration: float):
        """Record operation timing for performance monitoring"""
        if operation not in self.operation_times:
            self.operation_times[operation] = []
        self.operation_times[operation].append(duration)
        
        # Keep only last 100 measurements
        if len(self.operation_times[operation]) > 100:
            self.operation_times[operation] = self.operation_times[operation][-100:]
    
    def _get_cache_key(self, query: UIResourceQuery) -> str:
        """Generate cache key for query"""
        return f"{query.tenantId}:{query.sessionId}:{query.agentId}:{query.type}:{','.join(query.tags or [])}"
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - timestamp < self.cache_ttl
    
    async def batch_put_resources(self, resources: List[UIResource]) -> List[UIResource]:
        """
        Batch write multiple resources for optimal performance
        
        Args:
            resources: List of resources to store
            
        Returns:
            List of stored resources
        """
        start_time = time.time()
        
        try:
            # Split into batches of 25 (DynamoDB limit)
            batch_size = DynamoDBConfig.BATCH_WRITE_MAX_ITEMS
            batches = [resources[i:i + batch_size] for i in range(0, len(resources), batch_size)]
            
            # Process batches in parallel
            tasks = [self._write_batch(batch) for batch in batches]
            await asyncio.gather(*tasks)
            
            duration = time.time() - start_time
            self._record_operation_time('batch_put', duration)
            
            logger.debug(f"Batch wrote {len(resources)} resources in {duration:.3f}s")
            return resources
            
        except Exception as e:
            logger.error(f"Batch put failed: {e}")
            raise
    
    async def _write_batch(self, resources: List[UIResource]) -> None:
        """Write a single batch of resources"""
        if not resources:
            return
        
        # Convert resources to items
        items = [self._resource_to_item(resource) for resource in resources]
        
        # Build batch write request
        request_items = {
            DynamoDBConfig.TABLE_NAME: [
                {'PutRequest': {'Item': item}} for item in items
            ]
        }
        
        # Execute batch write with retries
        unprocessed_items = request_items
        retry_count = 0
        max_retries = 3
        
        while unprocessed_items and retry_count < max_retries:
            try:
                response = await self.client.dynamodb.batch_write_item(
                    RequestItems=unprocessed_items
                )
                
                unprocessed_items = response.get('UnprocessedItems', {})
                
                if unprocessed_items:
                    retry_count += 1
                    # Exponential backoff
                    await asyncio.sleep(0.1 * (2 ** retry_count))
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                    retry_count += 1
                    await asyncio.sleep(0.1 * (2 ** retry_count))
                else:
                    raise
        
        if unprocessed_items:
            logger.warning(f"Failed to write {len(unprocessed_items)} items after {max_retries} retries")
    
    async def batch_get_resources(self, keys: List[Tuple[str, str, str]]) -> List[UIResource]:
        """
        Batch get multiple resources by keys
        
        Args:
            keys: List of (tenant_id, session_id, resource_id) tuples
            
        Returns:
            List of found resources
        """
        start_time = time.time()
        
        try:
            if not keys:
                return []
            
            # Split into batches of 100 (DynamoDB limit)
            batch_size = DynamoDBConfig.BATCH_GET_MAX_ITEMS
            batches = [keys[i:i + batch_size] for i in range(0, len(keys), batch_size)]
            
            # Process batches in parallel
            tasks = [self._get_batch(batch) for batch in batches]
            batch_results = await asyncio.gather(*tasks)
            
            # Flatten results
            resources = []
            for batch_result in batch_results:
                resources.extend(batch_result)
            
            duration = time.time() - start_time
            self._record_operation_time('batch_get', duration)
            
            logger.debug(f"Batch got {len(resources)} resources in {duration:.3f}s")
            return resources
            
        except Exception as e:
            logger.error(f"Batch get failed: {e}")
            raise
    
    async def _get_batch(self, keys: List[Tuple[str, str, str]]) -> List[UIResource]:
        """Get a single batch of resources"""
        if not keys:
            return []
        
        # Build batch get request
        request_keys = []
        for tenant_id, session_id, resource_id in keys:
            pk = self.client._build_partition_key(tenant_id, session_id)
            request_keys.append({
                DynamoDBConfig.PARTITION_KEY: pk,
                DynamoDBConfig.SORT_KEY: resource_id
            })
        
        request_items = {
            DynamoDBConfig.TABLE_NAME: {
                'Keys': request_keys
            }
        }
        
        # Execute batch get with retries
        unprocessed_keys = request_items
        retry_count = 0
        max_retries = 3
        all_items = []
        
        while unprocessed_keys and retry_count < max_retries:
            try:
                response = await self.client.dynamodb.batch_get_item(
                    RequestItems=unprocessed_keys
                )
                
                # Collect items
                items = response.get('Responses', {}).get(DynamoDBConfig.TABLE_NAME, [])
                all_items.extend(items)
                
                unprocessed_keys = response.get('UnprocessedKeys', {})
                
                if unprocessed_keys:
                    retry_count += 1
                    await asyncio.sleep(0.1 * (2 ** retry_count))
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                    retry_count += 1
                    await asyncio.sleep(0.1 * (2 ** retry_count))
                else:
                    raise
        
        # Convert items to resources
        resources = [self._item_to_resource(item) for item in all_items]
        return resources
    
    async def query_resources_optimized(self, query: UIResourceQuery) -> List[UIResource]:
        """
        Optimized query with caching and parallel execution
        
        Args:
            query: Query parameters
            
        Returns:
            List of matching resources
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = self._get_cache_key(query)
            if cache_key in self.query_cache:
                cached_resources, cache_time = self.query_cache[cache_key]
                if self._is_cache_valid(cache_time):
                    self.cache_hits += 1
                    duration = time.time() - start_time
                    self._record_operation_time('query_cached', duration)
                    logger.debug(f"Cache hit for query {cache_key} in {duration:.3f}s")
                    return cached_resources
            
            self.cache_misses += 1
            
            # Execute optimized query
            if query.tenantId and query.sessionId:
                # Use partition key query (fastest)
                resources = await self._query_by_session_optimized(query)
            elif query.tenantId:
                # Use GSI query
                resources = await self._query_by_tenant_optimized(query)
            else:
                raise ValueError("tenantId is required for queries")
            
            # Apply filters in parallel
            resources = await self._apply_filters_parallel(resources, query)
            
            # Cache result
            self.query_cache[cache_key] = (resources, time.time())
            
            # Limit cache size
            if len(self.query_cache) > 1000:
                # Remove oldest entries
                oldest_keys = sorted(self.query_cache.keys(), 
                                   key=lambda k: self.query_cache[k][1])[:100]
                for key in oldest_keys:
                    del self.query_cache[key]
            
            duration = time.time() - start_time
            self._record_operation_time('query_optimized', duration)
            
            logger.debug(f"Optimized query returned {len(resources)} resources in {duration:.3f}s")
            return resources
            
        except Exception as e:
            logger.error(f"Optimized query failed: {e}")
            raise
    
    async def _query_by_session_optimized(self, query: UIResourceQuery) -> List[UIResource]:
        """Optimized session query with parallel processing"""
        pk = self.client._build_partition_key(query.tenantId, query.sessionId)
        
        # Build optimized query parameters
        query_params = {
            'KeyConditionExpression': f"{DynamoDBConfig.PARTITION_KEY} = :pk",
            'ExpressionAttributeValues': {':pk': pk}
        }
        
        # Add sort key filter if we have specific resource patterns
        if query.agentId:
            # Use begins_with for agent-specific resources
            query_params['FilterExpression'] = 'agentId = :agent_id'
            query_params['ExpressionAttributeValues'][':agent_id'] = query.agentId
        
        # Execute query
        response = await self.client.table.query(**query_params)
        
        return [self._item_to_resource(item) for item in response.get('Items', [])]
    
    async def _query_by_tenant_optimized(self, query: UIResourceQuery) -> List[UIResource]:
        """Optimized tenant query using GSI with parallel processing"""
        expression_values = {':tenant_id': query.tenantId}
        key_condition = f"{DynamoDBConfig.GSI1_PK} = :tenant_id"
        
        # Optimize for agent queries
        if query.agentId:
            key_condition += f" AND begins_with({DynamoDBConfig.GSI1_SK}, :agent_prefix)"
            expression_values[':agent_prefix'] = f"{query.agentId}#"
        
        query_params = {
            'IndexName': DynamoDBConfig.GSI1_NAME,
            'KeyConditionExpression': key_condition,
            'ExpressionAttributeValues': expression_values
        }
        
        # Execute query
        response = await self.client.table.query(**query_params)
        
        return [self._item_to_resource(item) for item in response.get('Items', [])]
    
    async def _apply_filters_parallel(self, resources: List[UIResource], query: UIResourceQuery) -> List[UIResource]:
        """Apply filters in parallel for better performance"""
        if not resources:
            return resources
        
        # Create filter tasks
        filter_tasks = []
        
        if query.type:
            filter_tasks.append(self._filter_by_type(resources, query.type))
        
        if query.tags:
            filter_tasks.append(self._filter_by_tags(resources, query.tags))
        
        if not query.includeExpired:
            filter_tasks.append(self._filter_expired(resources))
        
        # Execute filters in parallel
        if filter_tasks:
            filter_results = await asyncio.gather(*filter_tasks)
            
            # Intersect all filter results
            filtered_resources = resources
            for filter_result in filter_results:
                filtered_resources = [r for r in filtered_resources if r in filter_result]
            
            return filtered_resources
        
        return resources
    
    async def _filter_by_type(self, resources: List[UIResource], resource_type: str) -> List[UIResource]:
        """Filter resources by type"""
        return [r for r in resources if r.type == resource_type]
    
    async def _filter_by_tags(self, resources: List[UIResource], tags: List[str]) -> List[UIResource]:
        """Filter resources by tags"""
        return [r for r in resources if any(tag in r.tags for tag in tags)]
    
    async def _filter_expired(self, resources: List[UIResource]) -> List[UIResource]:
        """Filter out expired resources"""
        return [r for r in resources if not r.is_expired()]
    
    def invalidate_cache(self, tenant_id: str, session_id: Optional[str] = None):
        """Invalidate cache entries for tenant/session"""
        keys_to_remove = []
        
        for cache_key in self.query_cache:
            if cache_key.startswith(f"{tenant_id}:"):
                if session_id is None or cache_key.startswith(f"{tenant_id}:{session_id}:"):
                    keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.query_cache[key]
        
        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for {tenant_id}:{session_id}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_ratio': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'cache_size': len(self.query_cache),
            'operation_times': {}
        }
        
        # Calculate average operation times
        for operation, times in self.operation_times.items():
            if times:
                stats['operation_times'][operation] = {
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'count': len(times)
                }
        
        return stats
    
    def reset_performance_stats(self):
        """Reset performance statistics"""
        self.operation_times.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.query_cache.clear()
        logger.info("Performance statistics reset")