"""
DynamoDB client for async operations
"""

import logging
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError

from ...config.settings import settings
from .config import DynamoDBConfig
from .table_manager import TableManager

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """
    Async DynamoDB client for UI resource operations
    """
    
    def __init__(self):
        self.session: Optional[aioboto3.Session] = None
        self.dynamodb = None
        self.table = None
        self._initialized = False
        self.table_manager = TableManager()
    
    async def initialize(self):
        """Initialize DynamoDB client and ensure table exists"""
        if self._initialized:
            return
        
        try:
            # Create aioboto3 session
            self.session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            # Create DynamoDB resource
            self.dynamodb = self.session.resource('dynamodb')
            
            # Ensure table exists
            await self.table_manager.ensure_table_exists(self.dynamodb)
            
            # Get table reference
            self.table = await self.dynamodb.Table(DynamoDBConfig.TABLE_NAME)
            
            self._initialized = True
            logger.info(f"DynamoDB client initialized for table: {DynamoDBConfig.TABLE_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB client: {e}")
            raise
    
    def _build_partition_key(self, tenant_id: str, session_id: str) -> str:
        """Build partition key from tenant and session IDs"""
        return f"{tenant_id}#{session_id}"
    
    def _build_gsi1_sort_key(self, agent_id: str, created_at: str) -> str:
        """Build GSI1 sort key from agent ID and creation timestamp"""
        return f"{agent_id}#{created_at}"
    
    async def close(self):
        """Close DynamoDB client connections"""
        if self.session:
            await self.session.close()
        self._initialized = False
        logger.info("DynamoDB client closed")


# Global DynamoDB client instance
dynamodb_client = DynamoDBClient()