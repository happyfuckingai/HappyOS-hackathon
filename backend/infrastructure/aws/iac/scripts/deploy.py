#!/usr/bin/env python3
"""
Deployment Automation Script

Handles CDK deployment with environment-specific configurations and rollback capabilities.
"""

import os
import sys
import json
import subprocess
import argparse
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

from ..config.environment_config import EnvironmentConfig
from ..config.parameters import ParameterManager


class DeploymentManager:
    """Manages CDK deployments with automation and rollback capabilities."""
    
    def __init__(self, environment: str, region: str, profile: Optional[str] = None):
        self.environment = environment
        self.region = region
        self.profile = profile
        
        # Initialize AWS session
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.cloudformation = session.client('cloudformation', region_name=region)
        self.s3 = session.client('s3', region_name=region)
        
        # Load configuration
        self.env_config = EnvironmentConfig(environment)
        self.param_manager = ParameterManager(environment)
        
        # Set CDK environment variables
        self._set_cdk_environment()
    
    def _set_cdk_environment(self) -> None:
        """Set CDK environment variables."""
        os.environ['CDK_DEFAULT_REGION'] = self.region
        os.environ['CDK_ENVIRONMENT'] = self.environment
        
        if self.profile:
            os.environ['AWS_PROFILE'] = self.profile
    
    def bootstrap_cdk(self) -> bool:
        """Bootstrap CDK in the target environment."""
        print(f"Bootstrapping CDK for environment: {self.environment}")
        
        try:
            cmd = [
                'cdk', 'bootstrap',
                f'aws://{self.env_config.aws_account_id}/{self.region}',
                '--context', f'environment={self.environment}'
            ]
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"CDK bootstrap failed: {result.stderr}")
                return False
            
            print("CDK bootstrap completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during CDK bootstrap: {e}")
            return False
    
    def synthesize_stacks(self) -> bool:
        """Synthesize CDK stacks to CloudFormation templates."""
        print("Synthesizing CDK stacks...")
        
        try:
            cmd = [
                'cdk', 'synth',
                '--context', f'environment={self.environment}'
            ]
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"CDK synthesis failed: {result.stderr}")
                return False
            
            print("CDK synthesis completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during CDK synthesis: {e}")
            return False
    
    def deploy_stacks(self, stack_names: Optional[List[str]] = None, require_approval: bool = False) -> bool:
        """Deploy CDK stacks with optional stack filtering."""
        print(f"Deploying stacks for environment: {self.environment}")
        
        try:
            # Create backup before deployment
            if not self._create_deployment_backup():
                print("Warning: Failed to create deployment backup")
            
            cmd = [
                'cdk', 'deploy',
                '--context', f'environment={self.environment}',
                '--require-approval', 'never' if not require_approval else 'any-change',
                '--outputs-file', f'outputs-{self.environment}.json'
            ]
            
            if stack_names:
                cmd.extend(stack_names)
            else:
                cmd.append('--all')
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"CDK deployment failed: {result.stderr}")
                return False
            
            print("CDK deployment completed successfully")
            
            # Save deployment metadata
            self._save_deployment_metadata()
            
            return True
            
        except Exception as e:
            print(f"Error during CDK deployment: {e}")
            return False
    
    def destroy_stacks(self, stack_names: Optional[List[str]] = None, force: bool = False) -> bool:
        """Destroy CDK stacks with safety checks."""
        if not force and self.environment == 'prod':
            print("ERROR: Cannot destroy production stacks without --force flag")
            return False
        
        print(f"Destroying stacks for environment: {self.environment}")
        
        try:
            cmd = [
                'cdk', 'destroy',
                '--context', f'environment={self.environment}',
                '--force'
            ]
            
            if stack_names:
                cmd.extend(stack_names)
            else:
                cmd.append('--all')
            
            if self.profile:
                cmd.extend(['--profile', self.profile])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self._get_cdk_dir())
            
            if result.returncode != 0:
                print(f"CDK destroy failed: {result.stderr}")
                return False
            
            print("CDK destroy completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during CDK destroy: {e}")
            return False
    
    def rollback_deployment(self, backup_id: str) -> bool:
        """Rollback to a previous deployment state."""
        print(f"Rolling back to backup: {backup_id}")
        
        try:
            # Get list of stacks from backup
            stacks = self._get_backup_stacks(backup_id)
            
            if not stacks:
                print(f"No stacks found in backup: {backup_id}")
                return False
            
            # Rollback each stack
            for stack_name in stacks:
                if not self._rollback_stack(stack_name, backup_id):
                    print(f"Failed to rollback stack: {stack_name}")
                    return False
            
            print("Rollback completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during rollback: {e}")
            return False
    
    def validate_deployment(self) -> bool:
        """Validate the current deployment state."""
        print("Validating deployment...")
        
        try:
            # Check stack status
            stacks = self._get_environment_stacks()
            
            for stack_name in stacks:
                stack_info = self.cloudformation.describe_stacks(StackName=stack_name)
                stack_status = stack_info['Stacks'][0]['StackStatus']
                
                if stack_status not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                    print(f"Stack {stack_name} is in invalid state: {stack_status}")
                    return False
            
            # Run health checks
            if not self._run_health_checks():
                print("Health checks failed")
                return False
            
            print("Deployment validation passed")
            return True
            
        except Exception as e:
            print(f"Error during validation: {e}")
            return False
    
    def _get_cdk_dir(self) -> str:
        """Get CDK application directory."""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def _create_deployment_backup(self) -> bool:
        """Create backup of current deployment state."""
        try:
            backup_id = f"{self.environment}-{int(os.time())}"
            
            # Get current stack templates
            stacks = self._get_environment_stacks()
            
            for stack_name in stacks:
                template = self.cloudformation.get_template(StackName=stack_name)
                
                # Save template to S3 backup bucket
                backup_key = f"backups/{backup_id}/{stack_name}.json"
                self.s3.put_object(
                    Bucket=f"infra-recovery-{self.environment}-backups",
                    Key=backup_key,
                    Body=json.dumps(template['TemplateBody'], indent=2)
                )
            
            print(f"Backup created with ID: {backup_id}")
            return True
            
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return False
    
    def _save_deployment_metadata(self) -> None:
        """Save deployment metadata for tracking."""
        metadata = {
            'environment': self.environment,
            'region': self.region,
            'timestamp': int(os.time()),
            'stacks': self._get_environment_stacks(),
            'parameters': self.param_manager.get_parameter_context()
        }
        
        with open(f'deployment-{self.environment}.json', 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _get_environment_stacks(self) -> List[str]:
        """Get list of stacks for the current environment."""
        try:
            paginator = self.cloudformation.get_paginator('list_stacks')
            
            stacks = []
            for page in paginator.paginate():
                for stack in page['StackSummaries']:
                    if (stack['StackStatus'] != 'DELETE_COMPLETE' and 
                        f"InfrastructureRecovery-{self.environment}" in stack['StackName']):
                        stacks.append(stack['StackName'])
            
            return stacks
            
        except Exception as e:
            print(f"Error getting environment stacks: {e}")
            return []
    
    def _get_backup_stacks(self, backup_id: str) -> List[str]:
        """Get list of stacks from backup."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=f"infra-recovery-{self.environment}-backups",
                Prefix=f"backups/{backup_id}/"
            )
            
            stacks = []
            for obj in response.get('Contents', []):
                stack_name = os.path.basename(obj['Key']).replace('.json', '')
                stacks.append(stack_name)
            
            return stacks
            
        except Exception as e:
            print(f"Error getting backup stacks: {e}")
            return []
    
    def _rollback_stack(self, stack_name: str, backup_id: str) -> bool:
        """Rollback a single stack to backup state."""
        try:
            # Get backup template
            backup_key = f"backups/{backup_id}/{stack_name}.json"
            response = self.s3.get_object(
                Bucket=f"infra-recovery-{self.environment}-backups",
                Key=backup_key
            )
            
            template = json.loads(response['Body'].read())
            
            # Update stack with backup template
            self.cloudformation.update_stack(
                StackName=stack_name,
                TemplateBody=json.dumps(template)
            )
            
            # Wait for update to complete
            waiter = self.cloudformation.get_waiter('stack_update_complete')
            waiter.wait(StackName=stack_name)
            
            return True
            
        except Exception as e:
            print(f"Error rolling back stack {stack_name}: {e}")
            return False
    
    def _run_health_checks(self) -> bool:
        """Run health checks on deployed infrastructure."""
        try:
            # Check API Gateway health
            # Check Lambda function health
            # Check OpenSearch cluster health
            # Check ElastiCache cluster health
            
            # Placeholder for actual health checks
            print("Health checks passed (placeholder)")
            return True
            
        except Exception as e:
            print(f"Health check failed: {e}")
            return False


def main():
    """Main entry point for deployment script."""
    parser = argparse.ArgumentParser(description='CDK Deployment Automation')
    parser.add_argument('action', choices=['bootstrap', 'synth', 'deploy', 'destroy', 'rollback', 'validate'])
    parser.add_argument('--environment', '-e', required=True, choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', '-r', default='us-east-1')
    parser.add_argument('--profile', '-p', help='AWS profile to use')
    parser.add_argument('--stacks', '-s', nargs='+', help='Specific stacks to deploy/destroy')
    parser.add_argument('--backup-id', '-b', help='Backup ID for rollback')
    parser.add_argument('--require-approval', action='store_true', help='Require approval for changes')
    parser.add_argument('--force', action='store_true', help='Force action (for destroy)')
    
    args = parser.parse_args()
    
    # Initialize deployment manager
    deployment_manager = DeploymentManager(
        environment=args.environment,
        region=args.region,
        profile=args.profile
    )
    
    # Execute requested action
    success = False
    
    if args.action == 'bootstrap':
        success = deployment_manager.bootstrap_cdk()
    elif args.action == 'synth':
        success = deployment_manager.synthesize_stacks()
    elif args.action == 'deploy':
        success = deployment_manager.deploy_stacks(
            stack_names=args.stacks,
            require_approval=args.require_approval
        )
    elif args.action == 'destroy':
        success = deployment_manager.destroy_stacks(
            stack_names=args.stacks,
            force=args.force
        )
    elif args.action == 'rollback':
        if not args.backup_id:
            print("ERROR: --backup-id is required for rollback")
            sys.exit(1)
        success = deployment_manager.rollback_deployment(args.backup_id)
    elif args.action == 'validate':
        success = deployment_manager.validate_deployment()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()