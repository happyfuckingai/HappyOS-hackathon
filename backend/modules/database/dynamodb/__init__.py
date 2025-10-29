"""
DynamoDB module for multi-tenant UI resources
"""

from .client import DynamoDBClient, dynamodb_client
from .config import DynamoDBConfig
from .operations import DynamoDBOperations

__all__ = [
    'DynamoDBClient',
    'dynamodb_client', 
    'DynamoDBConfig',
    'DynamoDBOperations'
]