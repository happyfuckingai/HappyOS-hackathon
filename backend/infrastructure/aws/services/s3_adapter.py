"""
AWS S3 service adapter for object storage operations.
This adapter provides storage capabilities using AWS S3.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import StorageService


class AWSS3Adapter(StorageService):
    """AWS S3 implementation for object storage operations."""
    
    def __init__(self, bucket_name: str, region_name: str = "us-east-1"):
        """Initialize AWS S3 adapter."""
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.s3_resource = boto3.resource('s3', region_name=region_name)
        
        # Tenant prefixes for isolation
        self.tenant_prefixes = {
            'meetmind': 'meetmind/',
            'agent_svea': 'agentsvea/',
            'felicias_finance': 'feliciasfi/'
        }
    
    def _get_tenant_key(self, key: str, tenant_id: str) -> str:
        """Generate tenant-isolated object key."""
        prefix = self.tenant_prefixes.get(tenant_id, f"{tenant_id}/")
        if not key.startswith(prefix):
            return f"{prefix}{key}"
        return key
    
    def _ensure_bucket_exists(self) -> bool:
        """Ensure the S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    if self.region_name == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region_name}
                        )
                    return True
                except ClientError as create_error:
                    print(f"Error creating bucket: {create_error}")
                    return False
            else:
                print(f"Error checking bucket: {e}")
                return False
    
    async def put_object(self, key: str, data: bytes, tenant_id: str, 
                        metadata: Dict[str, str] = None) -> bool:
        """Store an object."""
        try:
            if not self._ensure_bucket_exists():
                return False
            
            object_key = self._get_tenant_key(key, tenant_id)
            
            # Prepare metadata
            object_metadata = {
                'tenant_id': tenant_id,
                'uploaded_at': datetime.utcnow().isoformat()
            }
            if metadata:
                object_metadata.update(metadata)
            
            # Upload object
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=data,
                Metadata=object_metadata,
                ServerSideEncryption='AES256'  # Enable server-side encryption
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error storing object: {e}")
            return False
    
    async def get_object(self, key: str, tenant_id: str) -> Optional[bytes]:
        """Retrieve an object."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            # Verify tenant isolation
            metadata = response.get('Metadata', {})
            if metadata.get('tenant_id') != tenant_id:
                print(f"Tenant mismatch for object {key}")
                return None
            
            return response['Body'].read()
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            print(f"Error retrieving object: {e}")
            return None
        except Exception as e:
            print(f"Error retrieving object: {e}")
            return None
    
    async def delete_object(self, key: str, tenant_id: str) -> bool:
        """Delete an object."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            # Verify object belongs to tenant before deletion
            try:
                response = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=object_key
                )
                metadata = response.get('Metadata', {})
                if metadata.get('tenant_id') != tenant_id:
                    print(f"Cannot delete object {key}: tenant mismatch")
                    return False
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    return True  # Object doesn't exist, consider it deleted
                raise
            
            # Delete the object
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error deleting object: {e}")
            return False
    
    async def list_objects(self, prefix: str, tenant_id: str) -> List[str]:
        """List objects with prefix."""
        try:
            tenant_prefix = self._get_tenant_key(prefix, tenant_id)
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=tenant_prefix
            )
            
            objects = []
            tenant_prefix_len = len(self.tenant_prefixes.get(tenant_id, f"{tenant_id}/"))
            
            for obj in response.get('Contents', []):
                # Remove tenant prefix from key
                clean_key = obj['Key'][tenant_prefix_len:]
                objects.append(clean_key)
            
            return objects
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error listing objects: {e}")
            return []
    
    async def get_object_metadata(self, key: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            # Verify tenant isolation
            metadata = response.get('Metadata', {})
            if metadata.get('tenant_id') != tenant_id:
                return None
            
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'etag': response['ETag'].strip('"'),
                'content_type': response.get('ContentType'),
                'metadata': metadata,
                'storage_class': response.get('StorageClass', 'STANDARD'),
                'server_side_encryption': response.get('ServerSideEncryption')
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            print(f"Error getting object metadata: {e}")
            return None
    
    async def copy_object(self, source_key: str, dest_key: str, tenant_id: str) -> bool:
        """Copy an object within the same tenant."""
        try:
            source_object_key = self._get_tenant_key(source_key, tenant_id)
            dest_object_key = self._get_tenant_key(dest_key, tenant_id)
            
            # Verify source object belongs to tenant
            try:
                response = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=source_object_key
                )
                metadata = response.get('Metadata', {})
                if metadata.get('tenant_id') != tenant_id:
                    print(f"Cannot copy object {source_key}: tenant mismatch")
                    return False
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    print(f"Source object {source_key} not found")
                    return False
                raise
            
            # Copy the object
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_object_key
            }
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_object_key,
                MetadataDirective='COPY'
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error copying object: {e}")
            return False
    
    async def generate_presigned_url(self, key: str, tenant_id: str, 
                                   expiration: int = 3600, method: str = 'get_object') -> Optional[str]:
        """Generate a presigned URL for object access."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            # Verify object exists and belongs to tenant
            if method == 'get_object':
                try:
                    response = self.s3_client.head_object(
                        Bucket=self.bucket_name,
                        Key=object_key
                    )
                    metadata = response.get('Metadata', {})
                    if metadata.get('tenant_id') != tenant_id:
                        return None
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        return None
                    raise
            
            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            
            return url
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error generating presigned URL: {e}")
            return None
    
    async def get_bucket_metrics(self) -> Dict[str, Any]:
        """Get bucket metrics and statistics."""
        try:
            # Get bucket size and object count using CloudWatch
            cloudwatch = boto3.client('cloudwatch', region_name=self.region_name)
            
            metrics = {}
            
            # Get bucket size
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': self.bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                EndTime=datetime.utcnow(),
                Period=86400,  # 1 day
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                metrics['bucket_size_bytes'] = response['Datapoints'][-1]['Average']
            else:
                metrics['bucket_size_bytes'] = 0
            
            # Get object count
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': self.bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                EndTime=datetime.utcnow(),
                Period=86400,
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                metrics['object_count'] = int(response['Datapoints'][-1]['Average'])
            else:
                metrics['object_count'] = 0
            
            return metrics
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting bucket metrics: {e}")
            return {}
    
    async def create_multipart_upload(self, key: str, tenant_id: str, 
                                    metadata: Dict[str, str] = None) -> Optional[str]:
        """Create a multipart upload for large objects."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            # Prepare metadata
            object_metadata = {
                'tenant_id': tenant_id,
                'uploaded_at': datetime.utcnow().isoformat()
            }
            if metadata:
                object_metadata.update(metadata)
            
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                Metadata=object_metadata,
                ServerSideEncryption='AES256'
            )
            
            return response['UploadId']
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error creating multipart upload: {e}")
            return None
    
    async def upload_part(self, key: str, tenant_id: str, upload_id: str, 
                         part_number: int, data: bytes) -> Optional[str]:
        """Upload a part for multipart upload."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            response = self.s3_client.upload_part(
                Bucket=self.bucket_name,
                Key=object_key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=data
            )
            
            return response['ETag']
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error uploading part: {e}")
            return None
    
    async def complete_multipart_upload(self, key: str, tenant_id: str, 
                                      upload_id: str, parts: List[Dict[str, Any]]) -> bool:
        """Complete a multipart upload."""
        try:
            object_key = self._get_tenant_key(key, tenant_id)
            
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error completing multipart upload: {e}")
            return False