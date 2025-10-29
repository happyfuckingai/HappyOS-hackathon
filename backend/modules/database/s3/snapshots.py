"""
S3 snapshot management operations
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from botocore.exceptions import ClientError

from ...models.ui_resource import UIResource
from .config import S3Config
from .utils import compress_data, decompress_data

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages UI resource snapshots in S3"""
    
    def __init__(self, s3_client):
        self.s3_client = s3_client
    
    def _build_snapshot_key(self, tenant_id: str, session_id: str, timestamp: str) -> str:
        """Build S3 key for snapshot"""
        date_prefix = timestamp[:10]  # YYYY-MM-DD
        return f"{S3Config.SNAPSHOTS_PREFIX}/{tenant_id}/{date_prefix}/{session_id}_{timestamp}.{S3Config.SNAPSHOT_FORMAT}"
    
    async def create_snapshot(
        self,
        tenant_id: str,
        session_id: str,
        resources: List[UIResource],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a snapshot of UI resources for a session
        
        Args:
            tenant_id: Tenant ID for isolation
            session_id: Session ID
            resources: List of resources to snapshot
            metadata: Optional metadata to include
            
        Returns:
            str: S3 key of the created snapshot
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build snapshot data
        snapshot_data = {
            'metadata': {
                'tenant_id': tenant_id,
                'session_id': session_id,
                'timestamp': timestamp,
                'resource_count': len(resources),
                'snapshot_id': str(uuid.uuid4()),
                **(metadata or {})
            },
            'resources': [resource.model_dump() for resource in resources]
        }
        
        # Serialize and compress
        json_data = json.dumps(snapshot_data, indent=2)
        compressed_data = compress_data(json_data)
        
        # Build S3 key
        s3_key = self._build_snapshot_key(tenant_id, session_id, timestamp)
        
        # Upload to S3
        await self.s3_client.put_object(
            Bucket=S3Config.BUCKET_NAME,
            Key=s3_key,
            Body=compressed_data,
            ContentType='application/json',
            ContentEncoding='gzip',
            Metadata={
                'tenant-id': tenant_id,
                'session-id': session_id,
                'resource-count': str(len(resources)),
                'snapshot-timestamp': timestamp
            }
        )
        
        logger.info(f"Created snapshot: {s3_key} ({len(resources)} resources)")
        return s3_key
    
    async def get_snapshot(self, s3_key: str, tenant_id: str) -> Dict[str, Any]:
        """
        Retrieve a snapshot from S3
        
        Args:
            s3_key: S3 key of the snapshot
            tenant_id: Tenant ID for validation
            
        Returns:
            Dict[str, Any]: Snapshot data
        """
        # Validate tenant access
        if not s3_key.startswith(f"{S3Config.SNAPSHOTS_PREFIX}/{tenant_id}/"):
            raise ValueError(f"Access denied: snapshot doesn't belong to tenant {tenant_id}")
        
        try:
            # Get object from S3
            response = await self.s3_client.get_object(
                Bucket=S3Config.BUCKET_NAME,
                Key=s3_key
            )
            
            # Read and decompress data
            compressed_data = await response['Body'].read()
            json_data = decompress_data(compressed_data)
            snapshot_data = json.loads(json_data)
            
            logger.debug(f"Retrieved snapshot: {s3_key}")
            return snapshot_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise ValueError(f"Snapshot not found: {s3_key}")
            else:
                logger.error(f"Failed to get snapshot {s3_key}: {e}")
                raise
    
    async def list_snapshots(
        self,
        tenant_id: str,
        session_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List snapshots for a tenant
        
        Args:
            tenant_id: Tenant ID
            session_id: Optional session ID filter
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            limit: Maximum number of snapshots to return
            
        Returns:
            List[Dict[str, Any]]: List of snapshot metadata
        """
        prefix = f"{S3Config.SNAPSHOTS_PREFIX}/{tenant_id}/"
        
        # Add date filter to prefix if provided
        if start_date:
            prefix += f"{start_date}/"
        
        # List objects
        paginator = self.s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=S3Config.BUCKET_NAME,
            Prefix=prefix
        )
        
        snapshots = []
        count = 0
        
        async for page in page_iterator:
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                # Apply filters
                key = obj['Key']
                
                # Session filter
                if session_id and f"/{session_id}_" not in key:
                    continue
                
                # Date range filter
                if end_date:
                    # Extract date from key
                    key_parts = key.split('/')
                    if len(key_parts) >= 3:
                        key_date = key_parts[2]  # Date part
                        if key_date > end_date:
                            continue
                
                # Get object metadata
                try:
                    head_response = await self.s3_client.head_object(
                        Bucket=S3Config.BUCKET_NAME,
                        Key=key
                    )
                    
                    snapshot_info = {
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'metadata': head_response.get('Metadata', {}),
                        'tenant_id': tenant_id
                    }
                    
                    snapshots.append(snapshot_info)
                    count += 1
                    
                    if limit and count >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to get metadata for {key}: {e}")
                    continue
            
            if limit and count >= limit:
                break
        
        # Sort by last modified (newest first)
        snapshots.sort(key=lambda x: x['last_modified'], reverse=True)
        
        logger.debug(f"Listed {len(snapshots)} snapshots for tenant {tenant_id}")
        return snapshots