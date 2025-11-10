"""
Validate LLM Service Deployment

This script validates that all LLM service infrastructure is properly deployed
and configured. It performs comprehensive health checks and connectivity tests.

Usage:
    python validate_llm_deployment.py --environment prod --region us-east-1
"""

import argparse
import boto3
import json
import sys
import time
from typing import Dict, List, Tuple
from botocore.exceptions import ClientError


class LLMDeploymentValidator:
    """Validate LLM service deployment."""
    
    def __init__(self, environment: str, region: str):
        """Initialize validator."""
        self.environment = environment
        self.region = region
        
        # AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.elasticache = boto3.client('elasticache', region_name=region)
        self.secretsmanager = boto3.client('secretsmanager', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.bedrock = boto3.client('bedrock', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get AWS account ID
        self.account_id = self.sts.get_caller_identity()['Account']
        
        # Resource names
        self.table_name = f"happyos-llm-usage-{environment}"
        self.cache_cluster_id = f"happyos-llm-cache-{environment}"
        self.iam_role_name = f"HappyOSLLMServiceRole-{environment}"
        self.log_group_name = f"/aws/happyos/llm-service-{environment}"
        
        # Validation results
        self.results: List[Tuple[str, bool, str]] = []
        
        print(f"🔍 LLM Deployment Validator")
        print(f"   Environment: {environment}")
        print(f"   Region: {region}")
        print(f"   Account: {self.account_id}")
        print()
    
    def validate_all(self) -> bool:
        """Run all validation checks."""
        print("=" * 60)
        print("VALIDATING LLM SERVICE DEPLOYMENT")
        print("=" * 60)
        print()
        
        # Run all checks
        self.validate_dynamodb()
        self.validate_elasticache()
        self.validate_iam()
        self.validate_bedrock()
        self.validate_secrets()
        self.validate_cloudwatch()
        
        # Print summary
        self.print_summary()
        
        # Return overall status
        return all(result[1] for result in self.results)
    
    def validate_dynamodb(self):
        """Validate DynamoDB table."""
        print("📊 Validating DynamoDB Table...")
        
        try:
            response = self.dynamodb.describe_table(TableName=self.table_name)
            table = response['Table']
            
            # Check table status
            if table['TableStatus'] != 'ACTIVE':
                self.results.append((
                    "DynamoDB Table Status",
                    False,
                    f"Table status is {table['TableStatus']}, expected ACTIVE"
                ))
                print(f"   ❌ Table status: {table['TableStatus']}")
                return
            
            print(f"   ✓ Table exists and is ACTIVE")
            
            # Check GSIs
            gsis = table.get('GlobalSecondaryIndexes', [])
            expected_gsis = ['tenant_id-timestamp-index', 'agent_id-timestamp-index']
            
            for expected_gsi in expected_gsis:
                gsi_found = any(gsi['IndexName'] == expected_gsi for gsi in gsis)
                if gsi_found:
                    print(f"   ✓ GSI exists: {expected_gsi}")
                else:
                    self.results.append((
                        f"DynamoDB GSI: {expected_gsi}",
                        False,
                        "GSI not found"
                    ))
                    print(f"   ❌ GSI missing: {expected_gsi}")
                    return
            
            # Check provisioned throughput
            read_capacity = table['ProvisionedThroughput']['ReadCapacityUnits']
            write_capacity = table['ProvisionedThroughput']['WriteCapacityUnits']
            print(f"   ✓ Provisioned throughput: {read_capacity} RCU, {write_capacity} WCU")
            
            self.results.append(("DynamoDB Table", True, "All checks passed"))
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self.results.append((
                    "DynamoDB Table",
                    False,
                    f"Table {self.table_name} not found"
                ))
                print(f"   ❌ Table not found: {self.table_name}")
            else:
                self.results.append((
                    "DynamoDB Table",
                    False,
                    str(e)
                ))
                print(f"   ❌ Error: {e}")
        except Exception as e:
            self.results.append(("DynamoDB Table", False, str(e)))
            print(f"   ❌ Unexpected error: {e}")
    
    def validate_elasticache(self):
        """Validate ElastiCache cluster."""
        print("\n🔴 Validating ElastiCache Cluster...")
        
        try:
            response = self.elasticache.describe_cache_clusters(
                CacheClusterId=self.cache_cluster_id,
                ShowCacheNodeInfo=True
            )
            cluster = response['CacheClusters'][0]
            
            # Check cluster status
            if cluster['CacheClusterStatus'] != 'available':
                self.results.append((
                    "ElastiCache Cluster Status",
                    False,
                    f"Cluster status is {cluster['CacheClusterStatus']}, expected available"
                ))
                print(f"   ❌ Cluster status: {cluster['CacheClusterStatus']}")
                return
            
            print(f"   ✓ Cluster exists and is available")
            
            # Check engine
            if cluster['Engine'] != 'redis':
                self.results.append((
                    "ElastiCache Engine",
                    False,
                    f"Engine is {cluster['Engine']}, expected redis"
                ))
                print(f"   ❌ Wrong engine: {cluster['Engine']}")
                return
            
            print(f"   ✓ Engine: Redis {cluster['EngineVersion']}")
            
            # Get endpoint
            if cluster['CacheNodes']:
                endpoint = cluster['CacheNodes'][0]['Endpoint']
                print(f"   ✓ Endpoint: {endpoint['Address']}:{endpoint['Port']}")
            
            # Check node type
            print(f"   ✓ Node type: {cluster['CacheNodeType']}")
            
            self.results.append(("ElastiCache Cluster", True, "All checks passed"))
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'CacheClusterNotFound':
                self.results.append((
                    "ElastiCache Cluster",
                    False,
                    f"Cluster {self.cache_cluster_id} not found"
                ))
                print(f"   ❌ Cluster not found: {self.cache_cluster_id}")
            else:
                self.results.append((
                    "ElastiCache Cluster",
                    False,
                    str(e)
                ))
                print(f"   ❌ Error: {e}")
        except Exception as e:
            self.results.append(("ElastiCache Cluster", False, str(e)))
            print(f"   ❌ Unexpected error: {e}")
    
    def validate_iam(self):
        """Validate IAM role and policies."""
        print("\n🔐 Validating IAM Resources...")
        
        try:
            # Check role exists
            try:
                role = self.iam.get_role(RoleName=self.iam_role_name)
                print(f"   ✓ IAM role exists: {self.iam_role_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    self.results.append((
                        "IAM Role",
                        False,
                        f"Role {self.iam_role_name} not found"
                    ))
                    print(f"   ❌ Role not found: {self.iam_role_name}")
                    return
                raise
            
            # Check attached policies
            response = self.iam.list_attached_role_policies(RoleName=self.iam_role_name)
            policies = response['AttachedPolicies']
            
            if not policies:
                self.results.append((
                    "IAM Policies",
                    False,
                    "No policies attached to role"
                ))
                print(f"   ❌ No policies attached to role")
                return
            
            print(f"   ✓ Attached policies:")
            for policy in policies:
                print(f"      - {policy['PolicyName']}")
            
            self.results.append(("IAM Resources", True, "All checks passed"))
            
        except Exception as e:
            self.results.append(("IAM Resources", False, str(e)))
            print(f"   ❌ Error: {e}")
    
    def validate_bedrock(self):
        """Validate Bedrock access."""
        print("\n🤖 Validating AWS Bedrock Access...")
        
        try:
            # List foundation models
            response = self.bedrock.list_foundation_models()
            
            # Check for Claude models
            claude_models = [
                model for model in response['modelSummaries']
                if 'claude' in model['modelId'].lower()
            ]
            
            if claude_models:
                print(f"   ✓ Bedrock access configured")
                print(f"   ✓ Available Claude models: {len(claude_models)}")
                for model in claude_models[:3]:
                    print(f"      - {model['modelId']}")
                self.results.append(("Bedrock Access", True, "Claude models available"))
            else:
                self.results.append((
                    "Bedrock Access",
                    False,
                    "No Claude models available - may need to request access"
                ))
                print(f"   ⚠️  No Claude models available")
                print(f"   ℹ️  Request access at: https://console.aws.amazon.com/bedrock/home#/modelaccess")
            
        except Exception as e:
            self.results.append((
                "Bedrock Access",
                False,
                f"Bedrock not available: {str(e)}"
            ))
            print(f"   ⚠️  Bedrock not available: {e}")
            print(f"   ℹ️  LLM service will use OpenAI fallback")
    
    def validate_secrets(self):
        """Validate Secrets Manager configuration."""
        print("\n🔑 Validating Secrets Manager...")
        
        secrets_to_check = [
            f'happyos/openai-api-key-{self.environment}',
            f'happyos/google-api-key-{self.environment}'
        ]
        
        all_secrets_valid = True
        
        for secret_name in secrets_to_check:
            try:
                response = self.secretsmanager.describe_secret(SecretId=secret_name)
                print(f"   ✓ Secret exists: {secret_name}")
                
                # Try to get secret value to verify it's accessible
                try:
                    secret_value = self.secretsmanager.get_secret_value(SecretId=secret_name)
                    secret_string = secret_value['SecretString']
                    
                    # Check if it's still a placeholder
                    if secret_string.startswith('sk-...') or secret_string.startswith('AIza...'):
                        print(f"      ⚠️  Secret appears to be placeholder value")
                        print(f"      ℹ️  Update with actual API key")
                        all_secrets_valid = False
                    else:
                        print(f"      ✓ Secret value configured")
                        
                except Exception as e:
                    print(f"      ❌ Cannot access secret value: {e}")
                    all_secrets_valid = False
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print(f"   ❌ Secret not found: {secret_name}")
                    all_secrets_valid = False
                else:
                    print(f"   ❌ Error checking secret: {e}")
                    all_secrets_valid = False
        
        if all_secrets_valid:
            self.results.append(("Secrets Manager", True, "All secrets configured"))
        else:
            self.results.append((
                "Secrets Manager",
                False,
                "Some secrets missing or not configured"
            ))
    
    def validate_cloudwatch(self):
        """Validate CloudWatch configuration."""
        print("\n📈 Validating CloudWatch...")
        
        try:
            # Check log group exists
            try:
                response = self.logs.describe_log_groups(
                    logGroupNamePrefix=self.log_group_name
                )
                
                if response['logGroups']:
                    log_group = response['logGroups'][0]
                    print(f"   ✓ Log group exists: {self.log_group_name}")
                    
                    if 'retentionInDays' in log_group:
                        print(f"   ✓ Retention: {log_group['retentionInDays']} days")
                    
                    self.results.append(("CloudWatch Logs", True, "Log group configured"))
                else:
                    self.results.append((
                        "CloudWatch Logs",
                        False,
                        f"Log group {self.log_group_name} not found"
                    ))
                    print(f"   ❌ Log group not found: {self.log_group_name}")
                    
            except Exception as e:
                self.results.append(("CloudWatch Logs", False, str(e)))
                print(f"   ❌ Error: {e}")
                
        except Exception as e:
            self.results.append(("CloudWatch", False, str(e)))
            print(f"   ❌ Unexpected error: {e}")
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, success, _ in self.results if success)
        failed = len(self.results) - passed
        
        print(f"\nTotal Checks: {len(self.results)}")
        print(f"✓ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\n❌ FAILED CHECKS:")
            for check, success, message in self.results:
                if not success:
                    print(f"   - {check}: {message}")
        
        print()
        if failed == 0:
            print("✅ ALL VALIDATION CHECKS PASSED")
            print("   LLM service infrastructure is properly deployed")
        else:
            print("⚠️  SOME VALIDATION CHECKS FAILED")
            print("   Please review and fix the issues above")
        
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate LLM Service Deployment'
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
    
    args = parser.parse_args()
    
    # Create validator
    validator = LLMDeploymentValidator(
        environment=args.environment,
        region=args.region
    )
    
    # Run validation
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
