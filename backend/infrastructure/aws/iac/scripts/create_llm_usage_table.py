"""
Script to create DynamoDB table for LLM usage logging.

This table stores all LLM requests for monitoring, cost tracking, and analytics.
"""

import boto3
from botocore.exceptions import ClientError


def create_llm_usage_table(
    table_name: str = "llm_usage_logs",
    region_name: str = "us-east-1"
):
    """
    Create DynamoDB table for LLM usage logs.
    
    Table schema:
    - Partition key: log_id (tenant_id#agent_id#timestamp)
    - GSI 1: tenant_id (for tenant-specific queries)
    - GSI 2: agent_id (for agent-specific queries)
    
    Args:
        table_name: Name of the DynamoDB table
        region_name: AWS region
    """
    dynamodb = boto3.client('dynamodb', region_name=region_name)
    
    try:
        # Create table
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'log_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'log_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'tenant_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'agent_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'tenant_id-timestamp-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'tenant_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'agent_id-timestamp-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'agent_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            },
            Tags=[
                {
                    'Key': 'Purpose',
                    'Value': 'LLM Usage Tracking'
                },
                {
                    'Key': 'Service',
                    'Value': 'HappyOS'
                }
            ]
        )
        
        print(f"Table {table_name} created successfully!")
        print(f"Table ARN: {response['TableDescription']['TableArn']}")
        print(f"Table status: {response['TableDescription']['TableStatus']}")
        print("\nWaiting for table to become active...")
        
        # Wait for table to be active
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        
        print(f"Table {table_name} is now active and ready to use!")
        
        return response
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {table_name} already exists.")
        else:
            print(f"Error creating table: {e}")
            raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


def delete_llm_usage_table(
    table_name: str = "llm_usage_logs",
    region_name: str = "us-east-1"
):
    """
    Delete DynamoDB table for LLM usage logs.
    
    Args:
        table_name: Name of the DynamoDB table
        region_name: AWS region
    """
    dynamodb = boto3.client('dynamodb', region_name=region_name)
    
    try:
        response = dynamodb.delete_table(TableName=table_name)
        print(f"Table {table_name} deleted successfully!")
        return response
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Table {table_name} does not exist.")
        else:
            print(f"Error deleting table: {e}")
            raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


def describe_llm_usage_table(
    table_name: str = "llm_usage_logs",
    region_name: str = "us-east-1"
):
    """
    Describe DynamoDB table for LLM usage logs.
    
    Args:
        table_name: Name of the DynamoDB table
        region_name: AWS region
    """
    dynamodb = boto3.client('dynamodb', region_name=region_name)
    
    try:
        response = dynamodb.describe_table(TableName=table_name)
        table = response['Table']
        
        print(f"\nTable: {table['TableName']}")
        print(f"Status: {table['TableStatus']}")
        print(f"Item count: {table['ItemCount']}")
        print(f"Size: {table['TableSizeBytes']} bytes")
        print(f"Created: {table['CreationDateTime']}")
        
        print("\nKey Schema:")
        for key in table['KeySchema']:
            print(f"  - {key['AttributeName']} ({key['KeyType']})")
        
        print("\nGlobal Secondary Indexes:")
        for gsi in table.get('GlobalSecondaryIndexes', []):
            print(f"  - {gsi['IndexName']}")
            print(f"    Status: {gsi['IndexStatus']}")
            print(f"    Keys: {[k['AttributeName'] for k in gsi['KeySchema']]}")
        
        return response
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Table {table_name} does not exist.")
        else:
            print(f"Error describing table: {e}")
            raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python create_llm_usage_table.py [create|delete|describe] [table_name] [region]")
        sys.exit(1)
    
    action = sys.argv[1]
    table_name = sys.argv[2] if len(sys.argv) > 2 else "llm_usage_logs"
    region = sys.argv[3] if len(sys.argv) > 3 else "us-east-1"
    
    if action == "create":
        create_llm_usage_table(table_name, region)
    elif action == "delete":
        delete_llm_usage_table(table_name, region)
    elif action == "describe":
        describe_llm_usage_table(table_name, region)
    else:
        print(f"Unknown action: {action}")
        print("Valid actions: create, delete, describe")
        sys.exit(1)
