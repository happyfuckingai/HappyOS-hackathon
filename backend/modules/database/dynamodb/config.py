"""
DynamoDB configuration constants
"""

from ...config.settings import settings


class DynamoDBConfig:
    """DynamoDB configuration constants"""
    
    # Table configuration
    TABLE_NAME = settings.AWS_DYNAMODB_TABLE_NAME
    
    # Key schema
    PARTITION_KEY = "PK"  # tenantId#sessionId
    SORT_KEY = "SK"       # resourceId
    
    # Global Secondary Index
    GSI1_NAME = "GSI1"
    GSI1_PK = "GSI1PK"    # tenantId
    GSI1_SK = "GSI1SK"    # agentId#createdAt
    
    # TTL attribute
    TTL_ATTRIBUTE = "TTL"
    
    # Billing mode and capacity
    BILLING_MODE = "PAY_PER_REQUEST"  # On-demand billing
    
    # Batch operation limits
    BATCH_WRITE_MAX_ITEMS = 25
    BATCH_GET_MAX_ITEMS = 100