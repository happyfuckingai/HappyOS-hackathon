"""
AWS ElastiCache service adapter for caching operations.
This adapter provides caching capabilities using AWS ElastiCache (Redis).
"""

import json
import pickle
from typing import Any, Dict, List, Optional
import boto3
import redis
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import CacheService


class AWSElastiCacheAdapter(CacheService):
    """AWS ElastiCache implementation for caching operations."""
    
    def __init__(self, cluster_endpoint: str, port: int = 6379, region_name: str = "us-east-1"):
        """Initialize AWS ElastiCache adapter."""
        self.cluster_endpoint = cluster_endpoint
        self.port = port
        self.region_name = region_name
        
        # ElastiCache management client
        self.elasticache_client = boto3.client('elasticache', region_name=region_name)
        
        # Redis connection pool
        self.redis_pool = redis.ConnectionPool(
            host=cluster_endpoint,
            port=port,
            decode_responses=False,  # We'll handle encoding ourselves
            max_connections=20,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        self._redis_client = None
    
    @property
    def redis_client(self):
        """Lazy load Redis client."""
        if self._redis_client is None:
            self._redis_client = redis.Redis(connection_pool=self.redis_pool)
        return self._redis_client
    
    def _get_tenant_key(self, key: str, tenant_id: str) -> str:
        """Generate tenant-isolated cache key."""
        return f"{tenant_id}:{key}"
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage in Redis."""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        else:
            # Use pickle for complex objects
            return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from Redis storage."""
        try:
            # Try JSON first (for simple types)
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle for complex objects
            return pickle.loads(data)
    
    async def get(self, key: str, tenant_id: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            data = self.redis_client.get(cache_key)
            
            if data is None:
                return None
            
            return self._deserialize_value(data)
            
        except Exception as e:
            print(f"Error getting cache value: {e}")
            return None
    
    async def set(self, key: str, value: Any, tenant_id: str, ttl: int = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            serialized_value = self._serialize_value(value)
            
            if ttl:
                result = self.redis_client.setex(cache_key, ttl, serialized_value)
            else:
                result = self.redis_client.set(cache_key, serialized_value)
            
            return bool(result)
            
        except Exception as e:
            print(f"Error setting cache value: {e}")
            return False
    
    async def delete(self, key: str, tenant_id: str) -> bool:
        """Delete value from cache."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            result = self.redis_client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            print(f"Error deleting cache value: {e}")
            return False
    
    async def exists(self, key: str, tenant_id: str) -> bool:
        """Check if key exists in cache."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            return bool(self.redis_client.exists(cache_key))
            
        except Exception as e:
            print(f"Error checking cache key existence: {e}")
            return False
    
    async def increment(self, key: str, tenant_id: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value in cache."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            return self.redis_client.incrby(cache_key, amount)
            
        except Exception as e:
            print(f"Error incrementing cache value: {e}")
            return None
    
    async def decrement(self, key: str, tenant_id: str, amount: int = 1) -> Optional[int]:
        """Decrement a numeric value in cache."""
        try:
            cache_key = self._get_tenant_key(key, tenant_id)
            return self.redis_client.decrby(cache_key, amount)
            
        except Exception as e:
            print(f"Error decrementing cache value: {e}")
            return None
    
    async def get_multiple(self, keys: List[str], tenant_id: str) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            cache_keys = [self._get_tenant_key(key, tenant_id) for key in keys]
            values = self.redis_client.mget(cache_keys)
            
            result = {}
            for i, key in enumerate(keys):
                if values[i] is not None:
                    result[key] = self._deserialize_value(values[i])
                else:
                    result[key] = None
            
            return result
            
        except Exception as e:
            print(f"Error getting multiple cache values: {e}")
            return {}
    
    async def set_multiple(self, key_value_pairs: Dict[str, Any], tenant_id: str, ttl: int = None) -> bool:
        """Set multiple values in cache."""
        try:
            pipe = self.redis_client.pipeline()
            
            for key, value in key_value_pairs.items():
                cache_key = self._get_tenant_key(key, tenant_id)
                serialized_value = self._serialize_value(value)
                
                if ttl:
                    pipe.setex(cache_key, ttl, serialized_value)
                else:
                    pipe.set(cache_key, serialized_value)
            
            results = pipe.execute()
            return all(results)
            
        except Exception as e:
            print(f"Error setting multiple cache values: {e}")
            return False
    
    async def get_keys_by_pattern(self, pattern: str, tenant_id: str) -> List[str]:
        """Get keys matching a pattern for a tenant."""
        try:
            tenant_pattern = self._get_tenant_key(pattern, tenant_id)
            cache_keys = self.redis_client.keys(tenant_pattern)
            
            # Remove tenant prefix from keys
            tenant_prefix = f"{tenant_id}:"
            return [key.decode('utf-8')[len(tenant_prefix):] for key in cache_keys]
            
        except Exception as e:
            print(f"Error getting keys by pattern: {e}")
            return []
    
    async def flush_tenant_cache(self, tenant_id: str) -> bool:
        """Flush all cache entries for a tenant."""
        try:
            pattern = f"{tenant_id}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                self.redis_client.delete(*keys)
            
            return True
            
        except Exception as e:
            print(f"Error flushing tenant cache: {e}")
            return False
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache cluster information."""
        try:
            info = self.redis_client.info()
            
            return {
                'redis_version': info.get('redis_version'),
                'used_memory': info.get('used_memory'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'uptime_in_seconds': info.get('uptime_in_seconds')
            }
            
        except Exception as e:
            print(f"Error getting cache info: {e}")
            return {}
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get ElastiCache cluster status from AWS."""
        try:
            # Extract cluster ID from endpoint
            cluster_id = self.cluster_endpoint.split('.')[0]
            
            response = self.elasticache_client.describe_cache_clusters(
                CacheClusterId=cluster_id,
                ShowCacheNodeInfo=True
            )
            
            if not response['CacheClusters']:
                return {'status': 'not_found'}
            
            cluster = response['CacheClusters'][0]
            
            return {
                'cluster_id': cluster['CacheClusterId'],
                'status': cluster['CacheClusterStatus'],
                'engine': cluster['Engine'],
                'engine_version': cluster['EngineVersion'],
                'num_cache_nodes': cluster['NumCacheNodes'],
                'cache_node_type': cluster['CacheNodeType'],
                'availability_zone': cluster.get('PreferredAvailabilityZone'),
                'security_groups': [sg['SecurityGroupId'] for sg in cluster.get('SecurityGroups', [])],
                'parameter_group': cluster.get('CacheParameterGroup', {}).get('CacheParameterGroupName'),
                'subnet_group': cluster.get('CacheSubnetGroupName')
            }
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting cluster status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def create_backup(self, backup_name: str) -> bool:
        """Create a backup of the cache cluster."""
        try:
            # Extract cluster ID from endpoint
            cluster_id = self.cluster_endpoint.split('.')[0]
            
            self.elasticache_client.create_snapshot(
                SnapshotName=backup_name,
                CacheClusterId=cluster_id
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error creating backup: {e}")
            return False
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        try:
            response = self.elasticache_client.describe_snapshots()
            
            backups = []
            for snapshot in response['Snapshots']:
                backups.append({
                    'snapshot_name': snapshot['SnapshotName'],
                    'cache_cluster_id': snapshot.get('CacheClusterId'),
                    'snapshot_status': snapshot['SnapshotStatus'],
                    'snapshot_source': snapshot['SnapshotSource'],
                    'node_type': snapshot.get('CacheNodeType'),
                    'engine': snapshot.get('Engine'),
                    'engine_version': snapshot.get('EngineVersion'),
                    'num_cache_nodes': snapshot.get('NumCacheNodes'),
                    'port': snapshot.get('Port'),
                    'snapshot_retention_limit': snapshot.get('SnapshotRetentionLimit'),
                    'snapshot_window': snapshot.get('SnapshotWindow')
                })
            
            return backups
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error listing backups: {e}")
            return []
    
    def close_connections(self):
        """Close Redis connections."""
        try:
            if self._redis_client:
                self._redis_client.close()
            if self.redis_pool:
                self.redis_pool.disconnect()
        except Exception as e:
            print(f"Error closing connections: {e}")