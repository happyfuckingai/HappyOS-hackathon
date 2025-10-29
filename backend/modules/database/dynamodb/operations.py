"""
DynamoDB CRUD operations for UI resources
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from botocore.exceptions import ClientError

from ...models.ui_resource import UIResource, UIResourceQuery
from .client import DynamoDBClient
from .config import DynamoDBConfig

logger = logging.getLogger(__name__)


class DynamoDBOperations:
    """
    DynamoDB operations for UI resources
    """
    
    def __init__(self, client: DynamoDBClient):
        self.client = client
    
    def _calculate_ttl(self, ttl_seconds: Optional[int]) -> Optional[int]:
        """Calculate TTL timestamp from seconds"""
        if not ttl_seconds:
            return None
        
        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        return int(expiry_time.timestamp())
    
    def _resource_to_item(self, resource: UIResource) -> Dict[str, Any]:
        """Convert UIResource to DynamoDB item"""
        # Build keys
        pk = self.client._build_partition_key(resource.tenantId, resource.sessionId)
        sk = resource.id
        gsi1_pk = resource.tenantId
        gsi1_sk = self.client._build_gsi1_sort_key(resource.agentId, resource.createdAt)
        
        # Build item
        item = {
            DynamoDBConfig.PARTITION_KEY: pk,
            DynamoDBConfig.SORT_KEY: sk,
            DynamoDBConfig.GSI1_PK: gsi1_pk,
            DynamoDBConfig.GSI1_SK: gsi1_sk,
            'tenantId': resource.tenantId,
            'sessionId': resource.sessionId,
            'agentId': resource.agentId,
            'type': resource.type,
            'version': resource.version,
            'revision': resource.revision,
            'payload': json.loads(resource.payload.model_dump_json()),
            'tags': resource.tags,
            'createdAt': resource.createdAt,
            'updatedAt': resource.updatedAt
        }
        
        # Add optional fields
        if resource.ttlSeconds:
            item[DynamoDBConfig.TTL_ATTRIBUTE] = self._calculate_ttl(resource.ttlSeconds)
            item['ttlSeconds'] = resource.ttlSeconds
        
        if resource.idempotencyKey:
            item['idempotencyKey'] = resource.idempotencyKey
        
        if resource.expiresAt:
            item['expiresAt'] = resource.expiresAt
        
        return item
    
    def _item_to_resource(self, item: Dict[str, Any]) -> UIResource:
        """Convert DynamoDB item to UIResource"""
        # Convert Decimal to int/float for JSON serialization
        def decimal_to_number(obj):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            elif isinstance(obj, dict):
                return {k: decimal_to_number(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decimal_to_number(v) for v in obj]
            return obj
        
        # Clean up item
        clean_item = decimal_to_number(item)
        
        # Build UIResource
        resource_data = {
            'id': clean_item[DynamoDBConfig.SORT_KEY],
            'tenantId': clean_item['tenantId'],
            'sessionId': clean_item['sessionId'],
            'agentId': clean_item['agentId'],
            'type': clean_item['type'],
            'version': clean_item['version'],
            'revision': clean_item['revision'],
            'payload': clean_item['payload'],
            'tags': clean_item.get('tags', []),
            'createdAt': clean_item['createdAt'],
            'updatedAt': clean_item['updatedAt']
        }
        
        # Add optional fields
        if 'ttlSeconds' in clean_item:
            resource_data['ttlSeconds'] = clean_item['ttlSeconds']
        
        if 'idempotencyKey' in clean_item:
            resource_data['idempotencyKey'] = clean_item['idempotencyKey']
        
        if 'expiresAt' in clean_item:
            resource_data['expiresAt'] = clean_item['expiresAt']
        
        return UIResource(**resource_data)
    
    async def put_resource(self, resource: UIResource) -> UIResource:
        """Store UI resource in DynamoDB"""
        try:
            item = self._resource_to_item(resource)
            await self.client.table.put_item(Item=item)
            logger.debug(f"Stored resource: {resource.id}")
            return resource
        except ClientError as e:
            logger.error(f"Failed to store resource {resource.id}: {e}")
            raise
    
    async def get_resource(self, tenant_id: str, session_id: str, resource_id: str) -> Optional[UIResource]:
        """Get UI resource by ID with tenant isolation"""
        try:
            pk = self.client._build_partition_key(tenant_id, session_id)
            
            response = await self.client.table.get_item(
                Key={
                    DynamoDBConfig.PARTITION_KEY: pk,
                    DynamoDBConfig.SORT_KEY: resource_id
                }
            )
            
            if 'Item' not in response:
                return None
            
            return self._item_to_resource(response['Item'])
        except ClientError as e:
            logger.error(f"Failed to get resource {resource_id}: {e}")
            raise
    
    async def delete_resource(self, tenant_id: str, session_id: str, resource_id: str) -> bool:
        """Delete UI resource with tenant isolation"""
        try:
            pk = self.client._build_partition_key(tenant_id, session_id)
            
            response = await self.client.table.delete_item(
                Key={
                    DynamoDBConfig.PARTITION_KEY: pk,
                    DynamoDBConfig.SORT_KEY: resource_id
                },
                ReturnValues='ALL_OLD'
            )
            
            return 'Attributes' in response
        except ClientError as e:
            logger.error(f"Failed to delete resource {resource_id}: {e}")
            raise
    
    async def query_resources(self, query: UIResourceQuery) -> List[UIResource]:
        """Query UI resources with filtering and tenant isolation"""
        try:
            resources = []
            
            if query.tenantId and query.sessionId:
                # Query by partition key (tenant + session)
                resources = await self._query_by_session(query)
            elif query.tenantId:
                # Query by GSI1 (tenant only)
                resources = await self._query_by_tenant(query)
            else:
                raise ValueError("tenantId is required for queries")
            
            # Apply additional filters
            if query.agentId:
                resources = [r for r in resources if r.agentId == query.agentId]
            
            if query.type:
                resources = [r for r in resources if r.type == query.type]
            
            if query.tags:
                resources = [r for r in resources if any(tag in r.tags for tag in query.tags)]
            
            if not query.includeExpired:
                resources = [r for r in resources if not r.is_expired()]
            
            # Apply pagination
            if query.offset:
                resources = resources[query.offset:]
            
            if query.limit:
                resources = resources[:query.limit]
            
            return resources
        except Exception as e:
            logger.error(f"Failed to query resources: {e}")
            raise
    
    async def _query_by_session(self, query: UIResourceQuery) -> List[UIResource]:
        """Query resources by tenant and session (partition key)"""
        pk = self.client._build_partition_key(query.tenantId, query.sessionId)
        
        response = await self.client.table.query(
            KeyConditionExpression=f"{DynamoDBConfig.PARTITION_KEY} = :pk",
            ExpressionAttributeValues={':pk': pk}
        )
        
        return [self._item_to_resource(item) for item in response.get('Items', [])]
    
    async def _query_by_tenant(self, query: UIResourceQuery) -> List[UIResource]:
        """Query resources by tenant using GSI1"""
        expression_values = {':tenant_id': query.tenantId}
        key_condition = f"{DynamoDBConfig.GSI1_PK} = :tenant_id"
        
        # Add agent filter to key condition if specified
        if query.agentId:
            key_condition += f" AND begins_with({DynamoDBConfig.GSI1_SK}, :agent_prefix)"
            expression_values[':agent_prefix'] = f"{query.agentId}#"
        
        response = await self.client.table.query(
            IndexName=DynamoDBConfig.GSI1_NAME,
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values
        )
        
        return [self._item_to_resource(item) for item in response.get('Items', [])]