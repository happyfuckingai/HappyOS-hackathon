"""Database connection and session management."""
from .connection import *

# Import modular components
from .dynamodb import dynamodb_client, DynamoDBClient, DynamoDBConfig
from .s3 import s3_client, S3Client, S3Config
from .repository import ui_resource_repository, UIResourceRepository

__all__ = [
    # Legacy SQLAlchemy components
    'get_db', 'init_db', 'get_db_health', 'close_db_connections',
    
    # DynamoDB components
    'dynamodb_client', 'DynamoDBClient', 'DynamoDBConfig',
    
    # S3 components  
    's3_client', 'S3Client', 'S3Config',
    
    # Repository layer
    'ui_resource_repository', 'UIResourceRepository'
]
