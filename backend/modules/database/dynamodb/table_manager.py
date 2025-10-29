"""
DynamoDB table management operations
"""

import logging
from botocore.exceptions import ClientError

from .config import DynamoDBConfig

logger = logging.getLogger(__name__)


class TableManager:
    """Manages DynamoDB table creation and configuration"""
    
    async def ensure_table_exists(self, dynamodb):
        """Create DynamoDB table if it doesn't exist"""
        try:
            # Check if table exists
            existing_tables = await dynamodb.meta.client.list_tables()
            
            if DynamoDBConfig.TABLE_NAME in existing_tables['TableNames']:
                logger.info(f"DynamoDB table {DynamoDBConfig.TABLE_NAME} already exists")
                return
            
            # Create table
            await self._create_table(dynamodb)
            
            # Wait for table to be active
            waiter = dynamodb.meta.client.get_waiter('table_exists')
            await waiter.wait(TableName=DynamoDBConfig.TABLE_NAME)
            
            # Enable TTL
            await self._enable_ttl(dynamodb)
            
            logger.info(f"Created DynamoDB table: {DynamoDBConfig.TABLE_NAME}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Table {DynamoDBConfig.TABLE_NAME} already exists")
            else:
                logger.error(f"Failed to create DynamoDB table: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error creating DynamoDB table: {e}")
            raise
    
    async def _create_table(self, dynamodb):
        """Create the DynamoDB table with proper schema"""
        table_definition = {
            'TableName': DynamoDBConfig.TABLE_NAME,
            'KeySchema': [
                {
                    'AttributeName': DynamoDBConfig.PARTITION_KEY,
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': DynamoDBConfig.SORT_KEY,
                    'KeyType': 'RANGE'
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': DynamoDBConfig.PARTITION_KEY,
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': DynamoDBConfig.SORT_KEY,
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': DynamoDBConfig.GSI1_PK,
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': DynamoDBConfig.GSI1_SK,
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': DynamoDBConfig.GSI1_NAME,
                    'KeySchema': [
                        {
                            'AttributeName': DynamoDBConfig.GSI1_PK,
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': DynamoDBConfig.GSI1_SK,
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            'BillingMode': DynamoDBConfig.BILLING_MODE
        }
        
        await dynamodb.meta.client.create_table(**table_definition)
    
    async def _enable_ttl(self, dynamodb):
        """Enable TTL on the table"""
        try:
            await dynamodb.meta.client.update_time_to_live(
                TableName=DynamoDBConfig.TABLE_NAME,
                TimeToLiveSpecification={
                    'AttributeName': DynamoDBConfig.TTL_ATTRIBUTE,
                    'Enabled': True
                }
            )
            logger.info(f"Enabled TTL on table {DynamoDBConfig.TABLE_NAME}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                logger.info("TTL already enabled on table")
            else:
                logger.error(f"Failed to enable TTL: {e}")
                raise