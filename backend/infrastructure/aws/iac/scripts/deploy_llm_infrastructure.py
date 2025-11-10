"""
Deploy LLM Service Infrastructure to AWS

This script deploys all required AWS infrastructure for the LLM service:
- DynamoDB table for usage logs
- ElastiCache cluster for caching
- AWS Bedrock access configuration
- Secrets Manager for API keys
- IAM roles and policies
- CloudWatch monitoring

Usage:
    python deploy_llm_infrastructure.py --environment prod --region us-east-1
"""

import argparse
import boto3
import json
import sys
import time
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional


class LLMInfrastructureDeployer:
    """Deploy LLM service infrastructure to AWS."""
    
    def __init__(self, environment: str, region: str, dry_run: bool = False):
        """
        Initialize deployer.
        
        Args:
            environment: Environment name (dev, staging, prod)
            region: AWS region
            dry_run: If True, only show what would be deployed
        """
        self.environment = environment
        self.region = region
        self.dry_run = dry_run
        
        # AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.elasticache = boto3.client('elasticache', region_name=region)
        self.secretsmanager = boto3.client('secretsmanager', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.bedrock = boto3.client('bedrock', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get AWS account ID
        self.account_id = self.sts.get_caller_identity()['Account']
        
        # Resource names
        self.table_name = f"happyos-llm-usage-{environment}"
        self.cache_cluster_id = f"happyos-llm-cache-{environment}"
        self.iam_role_name = f"HappyOSLLMServiceRole-{environment}"
        self.iam_policy_name = f"HappyOSLLMServicePolicy-{environment}"
        
        print(f"🚀 LLM Infrastructure Deployer")
        print(f"   Environment: {environment}")
        print(f"   Region: {region}")
        print(f"   Account: {self.account_id}")
        print(f"   Dry Run: {dry_run}")
        print()
    
    def deploy_all(self) -> bool:
        """Deploy all infrastructure components."""
        try:
            print("=" * 60)
            print("DEPLOYING LLM SERVICE INFRASTRUCTURE")
            print("=" * 60)
            print()
            
            # Step 1: DynamoDB table
            if not self.deploy_dynamodb_table():
                return False
            
            # Step 2: ElastiCache cluster
            if not self.deploy_elasticache_cluster():
                return False
            
            # Step 3: IAM roles and policies
            if not self.deploy_iam_resources():
                return False
            
            # Step 4: Bedrock access
            if not self.configure_bedrock_access():
                return False
            
            # Step 5: Secrets Manager
            if not self.configure_secrets_manager():
                return False
            
            # Step 6: CloudWatch monitoring
            if not self.configure_cloudwatch_monitoring():
                return False
            
            print()
            print("=" * 60)
            print("✅ DEPLOYMENT COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print()
            
            self.print_deployment_summary()
            
            return True
            
        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            return False
    
    def deploy_dynamodb_table(self) -> bool:
        """Deploy DynamoDB table for LLM usage logs."""
        print("📊 Deploying DynamoDB Table...")
        print(f"   Table name: {self.table_name}")
        
        if self.dry_run:
            print("   [DRY RUN] Would create DynamoDB table")
            return True
        
        try:
            # Check if table already exists
            try:
                response = self.dynamodb.describe_table(TableName=self.table_name)
                print(f"   ✓ Table already exists (Status: {response['Table']['TableStatus']})")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise
            
            # Create table
            response = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {'AttributeName': 'log_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'log_id', 'AttributeType': 'S'},
                    {'AttributeName': 'tenant_id', 'AttributeType': 'S'},
                    {'AttributeName': 'agent_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'tenant_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'tenant_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'agent_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'agent_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
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
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'LLM'},
                    {'Key': 'Purpose', 'Value': 'Usage Tracking'}
                ]
            )
            
            print(f"   ✓ Table created (ARN: {response['TableDescription']['TableArn']})")
            print("   ⏳ Waiting for table to become active...")
            
            # Wait for table to be active
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
            
            print("   ✓ Table is now active")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to create DynamoDB table: {e}")
            return False
    
    def deploy_elasticache_cluster(self) -> bool:
        """Deploy ElastiCache Redis cluster for LLM caching."""
        print("\n🔴 Deploying ElastiCache Cluster...")
        print(f"   Cluster ID: {self.cache_cluster_id}")
        
        if self.dry_run:
            print("   [DRY RUN] Would create ElastiCache cluster")
            return True
        
        try:
            # Check if cluster already exists
            try:
                response = self.elasticache.describe_cache_clusters(
                    CacheClusterId=self.cache_cluster_id
                )
                cluster = response['CacheClusters'][0]
                print(f"   ✓ Cluster already exists (Status: {cluster['CacheClusterStatus']})")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'CacheClusterNotFound':
                    raise
            
            # Determine node type based on environment
            node_type = {
                'dev': 'cache.t3.micro',
                'staging': 'cache.t3.small',
                'prod': 'cache.r6g.large'
            }.get(self.environment, 'cache.t3.micro')
            
            # Create cluster
            response = self.elasticache.create_cache_cluster(
                CacheClusterId=self.cache_cluster_id,
                CacheNodeType=node_type,
                Engine='redis',
                EngineVersion='7.0',
                NumCacheNodes=1,
                Port=6379,
                PreferredMaintenanceWindow='sun:05:00-sun:06:00',
                SnapshotRetentionLimit=5 if self.environment == 'prod' else 1,
                SnapshotWindow='03:00-04:00',
                AutoMinorVersionUpgrade=True,
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'LLM'},
                    {'Key': 'Purpose', 'Value': 'Caching'}
                ]
            )
            
            print(f"   ✓ Cluster created (Node type: {node_type})")
            print("   ⏳ Waiting for cluster to become available (this may take 5-10 minutes)...")
            
            # Wait for cluster to be available
            waiter = self.elasticache.get_waiter('cache_cluster_available')
            waiter.wait(CacheClusterId=self.cache_cluster_id)
            
            # Get endpoint
            response = self.elasticache.describe_cache_clusters(
                CacheClusterId=self.cache_cluster_id,
                ShowCacheNodeInfo=True
            )
            endpoint = response['CacheClusters'][0]['CacheNodes'][0]['Endpoint']
            
            print(f"   ✓ Cluster is now available")
            print(f"   📍 Endpoint: {endpoint['Address']}:{endpoint['Port']}")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to create ElastiCache cluster: {e}")
            return False
    
    def deploy_iam_resources(self) -> bool:
        """Deploy IAM roles and policies for LLM service."""
        print("\n🔐 Deploying IAM Resources...")
        print(f"   Role: {self.iam_role_name}")
        print(f"   Policy: {self.iam_policy_name}")
        
        if self.dry_run:
            print("   [DRY RUN] Would create IAM role and policy")
            return True
        
        try:
            # Create IAM policy
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream"
                        ],
                        "Resource": f"arn:aws:bedrock:{self.region}::foundation-model/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "elasticache:DescribeCacheClusters",
                            "elasticache:DescribeCacheSubnetGroups"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:Query",
                            "dynamodb:Scan"
                        ],
                        "Resource": [
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{self.table_name}",
                            f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{self.table_name}/index/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "secretsmanager:GetSecretValue"
                        ],
                        "Resource": [
                            f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:happyos/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/happyos/*"
                    }
                ]
            }
            
            # Create policy
            try:
                policy_response = self.iam.create_policy(
                    PolicyName=self.iam_policy_name,
                    PolicyDocument=json.dumps(policy_document),
                    Description=f"Policy for HappyOS LLM Service ({self.environment})"
                )
                policy_arn = policy_response['Policy']['Arn']
                print(f"   ✓ Policy created: {policy_arn}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    policy_arn = f"arn:aws:iam::{self.account_id}:policy/{self.iam_policy_name}"
                    print(f"   ✓ Policy already exists: {policy_arn}")
                else:
                    raise
            
            # Create IAM role
            assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": ["ec2.amazonaws.com", "ecs-tasks.amazonaws.com"]},
                    "Action": "sts:AssumeRole"
                }]
            }
            
            try:
                role_response = self.iam.create_role(
                    RoleName=self.iam_role_name,
                    AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                    Description=f"Role for HappyOS LLM Service ({self.environment})"
                )
                print(f"   ✓ Role created: {role_response['Role']['Arn']}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    print(f"   ✓ Role already exists: {self.iam_role_name}")
                else:
                    raise
            
            # Attach policy to role
            self.iam.attach_role_policy(
                RoleName=self.iam_role_name,
                PolicyArn=policy_arn
            )
            print(f"   ✓ Policy attached to role")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to create IAM resources: {e}")
            return False
    
    def configure_bedrock_access(self) -> bool:
        """Configure AWS Bedrock access."""
        print("\n🤖 Configuring AWS Bedrock Access...")
        
        if self.dry_run:
            print("   [DRY RUN] Would configure Bedrock access")
            return True
        
        try:
            # List available foundation models
            response = self.bedrock.list_foundation_models()
            
            # Check for Claude models
            claude_models = [
                model for model in response['modelSummaries']
                if 'claude' in model['modelId'].lower()
            ]
            
            if claude_models:
                print(f"   ✓ Bedrock access configured")
                print(f"   📋 Available Claude models:")
                for model in claude_models[:3]:  # Show first 3
                    print(f"      - {model['modelId']}")
            else:
                print("   ⚠️  No Claude models available")
                print("   ℹ️  You may need to request model access in AWS Console:")
                print("      https://console.aws.amazon.com/bedrock/home#/modelaccess")
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  Could not verify Bedrock access: {e}")
            print("   ℹ️  Bedrock may not be available in this region")
            print("   ℹ️  LLM service will use OpenAI fallback")
            return True  # Don't fail deployment
    
    def configure_secrets_manager(self) -> bool:
        """Configure Secrets Manager for API keys."""
        print("\n🔑 Configuring Secrets Manager...")
        
        if self.dry_run:
            print("   [DRY RUN] Would configure secrets")
            return True
        
        try:
            secrets = [
                {
                    'name': f'happyos/openai-api-key-{self.environment}',
                    'description': 'OpenAI API key for LLM service',
                    'placeholder': 'sk-...'
                },
                {
                    'name': f'happyos/google-api-key-{self.environment}',
                    'description': 'Google GenAI API key for Banking Agent',
                    'placeholder': 'AIza...'
                }
            ]
            
            for secret in secrets:
                try:
                    # Check if secret exists
                    self.secretsmanager.describe_secret(SecretId=secret['name'])
                    print(f"   ✓ Secret exists: {secret['name']}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        # Create placeholder secret
                        self.secretsmanager.create_secret(
                            Name=secret['name'],
                            Description=secret['description'],
                            SecretString=secret['placeholder']
                        )
                        print(f"   ✓ Secret created: {secret['name']}")
                        print(f"      ⚠️  IMPORTANT: Update secret value with actual API key!")
                    else:
                        raise
            
            print("\n   ℹ️  To update secrets with actual API keys:")
            print(f"      aws secretsmanager put-secret-value \\")
            print(f"        --secret-id happyos/openai-api-key-{self.environment} \\")
            print(f"        --secret-string 'YOUR_ACTUAL_API_KEY'")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to configure secrets: {e}")
            return False
    
    def configure_cloudwatch_monitoring(self) -> bool:
        """Configure CloudWatch monitoring and alarms."""
        print("\n📈 Configuring CloudWatch Monitoring...")
        
        if self.dry_run:
            print("   [DRY RUN] Would configure CloudWatch monitoring")
            return True
        
        try:
            # Create log group
            log_group_name = f"/aws/happyos/llm-service-{self.environment}"
            
            try:
                self.cloudwatch.create_log_group(logGroupName=log_group_name)
                print(f"   ✓ Log group created: {log_group_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                    print(f"   ✓ Log group already exists: {log_group_name}")
                else:
                    raise
            
            # Set retention policy
            logs_client = boto3.client('logs', region_name=self.region)
            retention_days = 30 if self.environment == 'prod' else 7
            logs_client.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention_days
            )
            print(f"   ✓ Retention policy set: {retention_days} days")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to configure CloudWatch: {e}")
            return False
    
    def print_deployment_summary(self):
        """Print deployment summary with connection details."""
        print("\n📋 DEPLOYMENT SUMMARY")
        print("=" * 60)
        print(f"\nEnvironment: {self.environment}")
        print(f"Region: {self.region}")
        print(f"Account: {self.account_id}")
        
        print("\n📊 DynamoDB Table:")
        print(f"   Name: {self.table_name}")
        print(f"   ARN: arn:aws:dynamodb:{self.region}:{self.account_id}:table/{self.table_name}")
        
        print("\n🔴 ElastiCache Cluster:")
        print(f"   Cluster ID: {self.cache_cluster_id}")
        try:
            response = self.elasticache.describe_cache_clusters(
                CacheClusterId=self.cache_cluster_id,
                ShowCacheNodeInfo=True
            )
            endpoint = response['CacheClusters'][0]['CacheNodes'][0]['Endpoint']
            print(f"   Endpoint: {endpoint['Address']}:{endpoint['Port']}")
        except:
            print(f"   Endpoint: (check AWS Console)")
        
        print("\n🔐 IAM Resources:")
        print(f"   Role: {self.iam_role_name}")
        print(f"   Policy: {self.iam_policy_name}")
        
        print("\n🔑 Secrets Manager:")
        print(f"   OpenAI Key: happyos/openai-api-key-{self.environment}")
        print(f"   Google Key: happyos/google-api-key-{self.environment}")
        
        print("\n📈 CloudWatch:")
        print(f"   Log Group: /aws/happyos/llm-service-{self.environment}")
        
        print("\n⚙️  NEXT STEPS:")
        print("   1. Update Secrets Manager with actual API keys")
        print("   2. Configure environment variables in your application:")
        print(f"      - DYNAMODB_LLM_USAGE_TABLE={self.table_name}")
        print(f"      - ELASTICACHE_CLUSTER={self.cache_cluster_id}")
        print(f"      - AWS_REGION={self.region}")
        print("   3. Deploy application code")
        print("   4. Verify health checks")
        print("   5. Monitor CloudWatch metrics")
        print()
    
    def test_connectivity(self) -> bool:
        """Test connectivity to deployed resources."""
        print("\n🔍 Testing Connectivity...")
        
        all_tests_passed = True
        
        # Test DynamoDB
        try:
            self.dynamodb.describe_table(TableName=self.table_name)
            print("   ✓ DynamoDB table accessible")
        except Exception as e:
            print(f"   ❌ DynamoDB test failed: {e}")
            all_tests_passed = False
        
        # Test ElastiCache
        try:
            self.elasticache.describe_cache_clusters(CacheClusterId=self.cache_cluster_id)
            print("   ✓ ElastiCache cluster accessible")
        except Exception as e:
            print(f"   ❌ ElastiCache test failed: {e}")
            all_tests_passed = False
        
        # Test Secrets Manager
        try:
            self.secretsmanager.describe_secret(
                SecretId=f'happyos/openai-api-key-{self.environment}'
            )
            print("   ✓ Secrets Manager accessible")
        except Exception as e:
            print(f"   ❌ Secrets Manager test failed: {e}")
            all_tests_passed = False
        
        return all_tests_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy LLM Service Infrastructure to AWS'
    )
    parser.add_argument(
        '--environment',
        choices=['dev', 'staging', 'prod'],
        required=True,
        help='Deployment environment'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deployed without making changes'
    )
    parser.add_argument(
        '--test-only',
        action='store_true',
        help='Only test connectivity to existing resources'
    )
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = LLMInfrastructureDeployer(
        environment=args.environment,
        region=args.region,
        dry_run=args.dry_run
    )
    
    # Test only mode
    if args.test_only:
        success = deployer.test_connectivity()
        sys.exit(0 if success else 1)
    
    # Deploy infrastructure
    success = deployer.deploy_all()
    
    if success and not args.dry_run:
        # Test connectivity
        print()
        deployer.test_connectivity()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
