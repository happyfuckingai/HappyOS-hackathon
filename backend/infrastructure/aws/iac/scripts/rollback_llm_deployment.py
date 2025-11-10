"""
Rollback LLM Service Deployment

This script provides rollback procedures for LLM service deployment issues:
- Disable LLM service (use fallback only)
- Switch to OpenAI-only mode
- Restore from backup
- Complete infrastructure teardown

Usage:
    python rollback_llm_deployment.py --environment prod --action disable-llm
"""

import argparse
import boto3
import json
import sys
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError


class LLMDeploymentRollback:
    """Rollback LLM service deployment."""
    
    def __init__(self, environment: str, region: str, dry_run: bool = False):
        """Initialize rollback handler."""
        self.environment = environment
        self.region = region
        self.dry_run = dry_run
        
        # AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.elasticache = boto3.client('elasticache', region_name=region)
        self.secretsmanager = boto3.client('secretsmanager', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get AWS account ID
        self.account_id = self.sts.get_caller_identity()['Account']
        
        # Resource names
        self.table_name = f"happyos-llm-usage-{environment}"
        self.cache_cluster_id = f"happyos-llm-cache-{environment}"
        self.iam_role_name = f"HappyOSLLMServiceRole-{environment}"
        self.iam_policy_name = f"HappyOSLLMServicePolicy-{environment}"
        
        print(f"🔄 LLM Deployment Rollback")
        print(f"   Environment: {environment}")
        print(f"   Region: {region}")
        print(f"   Dry Run: {dry_run}")
        print()
    
    def disable_llm_service(self) -> bool:
        """
        Disable LLM service, forcing all agents to use fallback logic.
        This is the safest rollback option.
        """
        print("🛑 Disabling LLM Service...")
        print("   All agents will use rule-based fallback logic")
        print()
        
        if self.dry_run:
            print("   [DRY RUN] Would disable LLM service")
            return True
        
        try:
            # Create a secret to signal LLM service should be disabled
            secret_name = f'happyos/llm-service-disabled-{self.environment}'
            
            try:
                self.secretsmanager.create_secret(
                    Name=secret_name,
                    Description='Flag to disable LLM service',
                    SecretString=json.dumps({
                        'disabled': True,
                        'disabled_at': datetime.utcnow().isoformat(),
                        'reason': 'Manual rollback'
                    })
                )
                print(f"   ✓ Created disable flag: {secret_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceExistsException':
                    # Update existing secret
                    self.secretsmanager.put_secret_value(
                        SecretId=secret_name,
                        SecretString=json.dumps({
                            'disabled': True,
                            'disabled_at': datetime.utcnow().isoformat(),
                            'reason': 'Manual rollback'
                        })
                    )
                    print(f"   ✓ Updated disable flag: {secret_name}")
                else:
                    raise
            
            print("\n   ✅ LLM service disabled successfully")
            print("\n   ℹ️  To re-enable:")
            print(f"      aws secretsmanager delete-secret --secret-id {secret_name}")
            print("      Then restart application services")
            
            return True
            
        except Exception as e:
            print(f"\n   ❌ Failed to disable LLM service: {e}")
            return False
    
    def switch_to_openai_only(self) -> bool:
        """
        Switch to OpenAI-only mode, disabling Bedrock.
        This is useful when Bedrock has issues.
        """
        print("🔄 Switching to OpenAI-Only Mode...")
        print("   Bedrock will be disabled, OpenAI will be primary")
        print()
        
        if self.dry_run:
            print("   [DRY RUN] Would switch to OpenAI-only mode")
            return True
        
        try:
            # Create a configuration secret
            secret_name = f'happyos/llm-config-{self.environment}'
            
            config = {
                'bedrock_enabled': False,
                'openai_enabled': True,
                'openai_only': True,
                'updated_at': datetime.utcnow().isoformat(),
                'reason': 'Rollback to OpenAI-only'
            }
            
            try:
                self.secretsmanager.create_secret(
                    Name=secret_name,
                    Description='LLM service configuration',
                    SecretString=json.dumps(config)
                )
                print(f"   ✓ Created config: {secret_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceExistsException':
                    self.secretsmanager.put_secret_value(
                        SecretId=secret_name,
                        SecretString=json.dumps(config)
                    )
                    print(f"   ✓ Updated config: {secret_name}")
                else:
                    raise
            
            print("\n   ✅ Switched to OpenAI-only mode")
            print("\n   ℹ️  Application services need to be restarted to pick up new config")
            print("\n   ℹ️  To re-enable Bedrock:")
            print(f"      Update secret {secret_name} with bedrock_enabled: true")
            
            return True
            
        except Exception as e:
            print(f"\n   ❌ Failed to switch to OpenAI-only: {e}")
            return False
    
    def restore_from_backup(self, backup_arn: str) -> bool:
        """
        Restore DynamoDB table from backup.
        
        Args:
            backup_arn: ARN of the backup to restore from
        """
        print(f"📦 Restoring from Backup...")
        print(f"   Backup ARN: {backup_arn}")
        print()
        
        if self.dry_run:
            print("   [DRY RUN] Would restore from backup")
            return True
        
        try:
            # Create new table name with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            restored_table_name = f"{self.table_name}-restored-{timestamp}"
            
            print(f"   Creating restored table: {restored_table_name}")
            
            response = self.dynamodb.restore_table_from_backup(
                TargetTableName=restored_table_name,
                BackupArn=backup_arn
            )
            
            print(f"   ✓ Restore initiated")
            print(f"   ⏳ Waiting for table to become active...")
            
            # Wait for table to be active
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=restored_table_name)
            
            print(f"   ✓ Table restored successfully")
            print(f"\n   ℹ️  Restored table: {restored_table_name}")
            print(f"   ℹ️  To use restored table, update application config:")
            print(f"      DYNAMODB_LLM_USAGE_TABLE={restored_table_name}")
            
            return True
            
        except Exception as e:
            print(f"\n   ❌ Failed to restore from backup: {e}")
            return False
    
    def list_backups(self) -> bool:
        """List available backups for the DynamoDB table."""
        print("📋 Available Backups...")
        print()
        
        try:
            response = self.dynamodb.list_backups(
                TableName=self.table_name
            )
            
            backups = response.get('BackupSummaries', [])
            
            if not backups:
                print("   ℹ️  No backups found")
                return True
            
            print(f"   Found {len(backups)} backup(s):\n")
            
            for i, backup in enumerate(backups, 1):
                print(f"   {i}. Backup ARN: {backup['BackupArn']}")
                print(f"      Created: {backup['BackupCreationDateTime']}")
                print(f"      Status: {backup['BackupStatus']}")
                print(f"      Size: {backup.get('BackupSizeBytes', 0) / 1024 / 1024:.2f} MB")
                print()
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to list backups: {e}")
            return False
    
    def teardown_infrastructure(self, confirm: bool = False) -> bool:
        """
        Complete teardown of LLM service infrastructure.
        WARNING: This is destructive and should only be used in emergencies.
        
        Args:
            confirm: Must be True to proceed with teardown
        """
        print("⚠️  INFRASTRUCTURE TEARDOWN")
        print("   This will DELETE all LLM service infrastructure!")
        print()
        
        if not confirm:
            print("   ❌ Teardown not confirmed")
            print("   ℹ️  Use --confirm flag to proceed")
            return False
        
        if self.dry_run:
            print("   [DRY RUN] Would teardown infrastructure")
            return True
        
        print("   ⚠️  Starting teardown in 5 seconds...")
        print("   Press Ctrl+C to cancel")
        
        try:
            import time
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n   ✓ Teardown cancelled")
            return False
        
        success = True
        
        # Delete ElastiCache cluster
        print("\n   🔴 Deleting ElastiCache cluster...")
        try:
            self.elasticache.delete_cache_cluster(
                CacheClusterId=self.cache_cluster_id
            )
            print(f"      ✓ Cluster deletion initiated: {self.cache_cluster_id}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'CacheClusterNotFound':
                print(f"      ❌ Failed to delete cluster: {e}")
                success = False
            else:
                print(f"      ℹ️  Cluster not found: {self.cache_cluster_id}")
        
        # Delete DynamoDB table
        print("\n   📊 Deleting DynamoDB table...")
        try:
            self.dynamodb.delete_table(TableName=self.table_name)
            print(f"      ✓ Table deletion initiated: {self.table_name}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                print(f"      ❌ Failed to delete table: {e}")
                success = False
            else:
                print(f"      ℹ️  Table not found: {self.table_name}")
        
        # Detach and delete IAM policy
        print("\n   🔐 Deleting IAM resources...")
        try:
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{self.iam_policy_name}"
            
            # Detach from role
            try:
                self.iam.detach_role_policy(
                    RoleName=self.iam_role_name,
                    PolicyArn=policy_arn
                )
                print(f"      ✓ Policy detached from role")
            except:
                pass
            
            # Delete role
            try:
                self.iam.delete_role(RoleName=self.iam_role_name)
                print(f"      ✓ Role deleted: {self.iam_role_name}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    print(f"      ❌ Failed to delete role: {e}")
            
            # Delete policy
            try:
                self.iam.delete_policy(PolicyArn=policy_arn)
                print(f"      ✓ Policy deleted: {self.iam_policy_name}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    print(f"      ❌ Failed to delete policy: {e}")
                    
        except Exception as e:
            print(f"      ❌ Error deleting IAM resources: {e}")
            success = False
        
        if success:
            print("\n   ✅ Infrastructure teardown completed")
        else:
            print("\n   ⚠️  Teardown completed with some errors")
        
        return success
    
    def create_incident_response_plan(self) -> bool:
        """Create incident response plan document."""
        print("📝 Creating Incident Response Plan...")
        print()
        
        plan = f"""
# LLM Service Incident Response Plan
Environment: {self.environment}
Region: {self.region}
Created: {datetime.utcnow().isoformat()}

## Quick Reference

### Emergency Contacts
- On-call Engineer: [FILL IN]
- Team Lead: [FILL IN]
- AWS Support: [FILL IN]

### Critical Resources
- DynamoDB Table: {self.table_name}
- ElastiCache Cluster: {self.cache_cluster_id}
- IAM Role: {self.iam_role_name}

## Incident Response Procedures

### 1. High Error Rate (>5%)

**Symptoms:**
- Error rate exceeds 5%
- Multiple failed LLM requests
- Circuit breaker opening frequently

**Actions:**
1. Check CloudWatch logs for error patterns
2. Verify API keys are valid
3. Check Bedrock service status
4. If Bedrock issues, switch to OpenAI-only:
   ```bash
   python rollback_llm_deployment.py --environment {self.environment} --action openai-only
   ```
5. If all providers failing, disable LLM service:
   ```bash
   python rollback_llm_deployment.py --environment {self.environment} --action disable-llm
   ```

### 2. High Latency (P95 >5s)

**Symptoms:**
- Slow response times
- Timeouts
- User complaints about performance

**Actions:**
1. Check ElastiCache connectivity
2. Verify cache hit rate (should be >20%)
3. Check Bedrock/OpenAI API status
4. Consider scaling ElastiCache cluster
5. Review recent code changes

### 3. High Cost (>$100/day)

**Symptoms:**
- Daily cost exceeds budget
- Unexpected spike in token usage
- Cost alerts triggered

**Actions:**
1. Identify high-usage agents:
   ```bash
   python monitor_llm_deployment.py --environment {self.environment} --duration 1
   ```
2. Review agent prompts for optimization
3. Increase cache TTL
4. Consider using cheaper models (gpt-3.5-turbo)
5. Implement rate limiting if needed

### 4. Circuit Breaker Open

**Symptoms:**
- Circuit breaker state is OPEN
- Automatic fallback to local services
- Degraded functionality

**Actions:**
1. Check underlying service health (Bedrock, OpenAI)
2. Review error logs for root cause
3. If transient issue, wait for auto-recovery
4. If persistent, switch to OpenAI-only or disable LLM
5. Monitor for recovery

### 5. Data Loss / Corruption

**Symptoms:**
- Missing usage logs
- Incorrect metrics
- Data inconsistencies

**Actions:**
1. List available backups:
   ```bash
   python rollback_llm_deployment.py --environment {self.environment} --action list-backups
   ```
2. Restore from most recent backup:
   ```bash
   python rollback_llm_deployment.py --environment {self.environment} --action restore --backup-arn <ARN>
   ```
3. Verify restored data
4. Update application configuration

## Rollback Procedures

### Option 1: Disable LLM Service (Safest)
```bash
python rollback_llm_deployment.py --environment {self.environment} --action disable-llm
```
- All agents use fallback logic
- No LLM calls made
- System remains functional

### Option 2: Switch to OpenAI-Only
```bash
python rollback_llm_deployment.py --environment {self.environment} --action openai-only
```
- Disables Bedrock
- Uses OpenAI as primary
- Maintains LLM functionality

### Option 3: Restore from Backup
```bash
python rollback_llm_deployment.py --environment {self.environment} --action restore --backup-arn <ARN>
```
- Restores DynamoDB table
- Recovers usage logs
- Requires application restart

### Option 4: Complete Teardown (Emergency Only)
```bash
python rollback_llm_deployment.py --environment {self.environment} --action teardown --confirm
```
- Deletes all infrastructure
- Use only in extreme cases
- Requires full redeployment

## Post-Incident

1. Document incident in incident log
2. Conduct post-mortem meeting
3. Update runbooks based on learnings
4. Implement preventive measures
5. Test rollback procedures

## Monitoring Commands

### Check Current Status
```bash
python validate_llm_deployment.py --environment {self.environment}
```

### Monitor in Real-Time
```bash
python monitor_llm_deployment.py --environment {self.environment} --duration 24
```

### View Logs
```bash
aws logs tail /aws/happyos/llm-service-{self.environment} --follow
```

### Check Metrics
```bash
aws cloudwatch get-metric-statistics \\
  --namespace HappyOS/LLM \\
  --metric-name llm_errors_total \\
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \\
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \\
  --period 300 \\
  --statistics Sum
```

## Escalation Path

1. **Level 1**: On-call engineer attempts resolution
2. **Level 2**: Team lead involved if not resolved in 30 minutes
3. **Level 3**: AWS Support contacted if infrastructure issue
4. **Level 4**: Executive team notified if customer impact

## Success Criteria

- Error rate < 1%
- P95 latency < 2 seconds
- Daily cost < $100
- Cache hit rate > 20%
- Circuit breaker CLOSED
- All agents functioning correctly
"""
        
        filename = f"llm_incident_response_plan_{self.environment}.md"
        
        try:
            with open(filename, 'w') as f:
                f.write(plan)
            
            print(f"   ✓ Incident response plan created: {filename}")
            print(f"\n   ℹ️  Review and customize the plan with your team")
            print(f"   ℹ️  Share with all team members")
            print(f"   ℹ️  Keep updated as procedures evolve")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to create plan: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Rollback LLM Service Deployment'
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
        '--action',
        choices=['disable-llm', 'openai-only', 'restore', 'list-backups', 'teardown', 'create-plan'],
        required=True,
        help='Rollback action to perform'
    )
    parser.add_argument(
        '--backup-arn',
        help='Backup ARN for restore action'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm destructive actions (required for teardown)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    # Create rollback handler
    rollback = LLMDeploymentRollback(
        environment=args.environment,
        region=args.region,
        dry_run=args.dry_run
    )
    
    # Execute action
    success = False
    
    if args.action == 'disable-llm':
        success = rollback.disable_llm_service()
    elif args.action == 'openai-only':
        success = rollback.switch_to_openai_only()
    elif args.action == 'restore':
        if not args.backup_arn:
            print("❌ --backup-arn required for restore action")
            sys.exit(1)
        success = rollback.restore_from_backup(args.backup_arn)
    elif args.action == 'list-backups':
        success = rollback.list_backups()
    elif args.action == 'teardown':
        success = rollback.teardown_infrastructure(confirm=args.confirm)
    elif args.action == 'create-plan':
        success = rollback.create_incident_response_plan()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
