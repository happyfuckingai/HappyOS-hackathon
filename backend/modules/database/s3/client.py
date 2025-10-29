"""
S3 client for async operations
"""

import logging
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError

from ...config.settings import settings
from .config import S3Config
from .bucket_manager import BucketManager

logger = logging.getLogger(__name__)


class S3StorageError(Exception):
    """Base exception for S3 storage operations"""
    pass


class S3Client:
    """
    Async S3 client for UI resource snapshots and audit logs
    """
    
    def __init__(self):
        self.session: Optional[aioboto3.Session] = None
        self.s3 = None
        self._initialized = False
        self.bucket_manager = BucketManager()
    
    async def initialize(self):
        """Initialize S3 client and ensure bucket exists"""
        if self._initialized:
            return
        
        try:
            # Create aioboto3 session
            self.session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=S3Config.REGION
            )
            
            # Create S3 client
            self.s3 = self.session.client('s3')
            
            # Ensure bucket exists
            await self.bucket_manager.ensure_bucket_exists(self.s3)
            
            self._initialized = True
            logger.info(f"S3 client initialized for bucket: {S3Config.BUCKET_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise S3StorageError(f"S3 initialization failed: {str(e)}")
    
    async def close(self):
        """Close S3 client connections"""
        if self.session:
            await self.session.close()
        self._initialized = False
        logger.info("S3 client closed")


# Global S3 client instance
s3_client = S3Client()