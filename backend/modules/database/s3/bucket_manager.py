"""
S3 bucket management operations
"""

import logging
from botocore.exceptions import ClientError

from .config import S3Config

logger = logging.getLogger(__name__)


class BucketManager:
    """Manages S3 bucket creation and lifecycle configuration"""
    
    async def ensure_bucket_exists(self, s3_client):
        """Create S3 bucket if it doesn't exist"""
        try:
            # Check if bucket exists
            await s3_client.head_bucket(Bucket=S3Config.BUCKET_NAME)
            logger.info(f"S3 bucket {S3Config.BUCKET_NAME} already exists")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == '404':
                # Bucket doesn't exist, create it
                await self._create_bucket(s3_client)
                await self._setup_bucket_lifecycle(s3_client)
                logger.info(f"Created S3 bucket: {S3Config.BUCKET_NAME}")
            else:
                logger.error(f"Failed to check bucket existence: {e}")
                raise
    
    async def _create_bucket(self, s3_client):
        """Create the S3 bucket"""
        try:
            if S3Config.REGION == 'us-east-1':
                # us-east-1 doesn't need LocationConstraint
                await s3_client.create_bucket(Bucket=S3Config.BUCKET_NAME)
            else:
                await s3_client.create_bucket(
                    Bucket=S3Config.BUCKET_NAME,
                    CreateBucketConfiguration={'LocationConstraint': S3Config.REGION}
                )
        except ClientError as create_error:
            if create_error.response['Error']['Code'] == 'BucketAlreadyExists':
                logger.info(f"Bucket {S3Config.BUCKET_NAME} already exists")
            else:
                raise
    
    async def _setup_bucket_lifecycle(self, s3_client):
        """Set up bucket lifecycle rules for automatic cleanup"""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'SnapshotRetention',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': f"{S3Config.SNAPSHOTS_PREFIX}/"},
                        'Expiration': {'Days': S3Config.SNAPSHOT_RETENTION_DAYS}
                    },
                    {
                        'ID': 'AuditLogRetention',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': f"{S3Config.AUDIT_LOGS_PREFIX}/"},
                        'Expiration': {'Days': S3Config.AUDIT_LOG_RETENTION_DAYS}
                    },
                    {
                        'ID': 'ArchiveRetention',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': f"{S3Config.ARCHIVES_PREFIX}/"},
                        'Expiration': {'Days': S3Config.ARCHIVE_RETENTION_DAYS}
                    }
                ]
            }
            
            await s3_client.put_bucket_lifecycle_configuration(
                Bucket=S3Config.BUCKET_NAME,
                LifecycleConfiguration=lifecycle_config
            )
            
            logger.info("Set up S3 bucket lifecycle rules")
            
        except Exception as e:
            logger.warning(f"Failed to set up bucket lifecycle: {e}")