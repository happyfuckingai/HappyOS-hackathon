"""
AWS Secrets Manager service adapter for secure configuration management.
This adapter provides secrets management capabilities using AWS Secrets Manager.
"""

import json
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import SecretsService


class AWSSecretsManagerAdapter(SecretsService):
    """AWS Secrets Manager implementation for secrets management."""
    
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize AWS Secrets Manager adapter."""
        self.region_name = region_name
        self.secrets_client = boto3.client('secretsmanager', region_name=region_name)
        
        # Tenant-specific secret prefixes for isolation
        self.tenant_prefixes = {
            'meetmind': 'meetmind/',
            'agent_svea': 'agentsvea/',
            'felicias_finance': 'feliciasfi/'
        }
    
    def _get_secret_name(self, secret_name: str, tenant_id: str = None) -> str:
        """Generate tenant-isolated secret name."""
        if tenant_id:
            prefix = self.tenant_prefixes.get(tenant_id, f"{tenant_id}/")
            if not secret_name.startswith(prefix):
                return f"{prefix}{secret_name}"
        return secret_name
    
    async def get_secret(self, secret_name: str, tenant_id: str = None) -> Optional[str]:
        """Retrieve a secret value."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            response = self.secrets_client.get_secret_value(
                SecretId=full_secret_name
            )
            
            # Return the secret string
            return response.get('SecretString')
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                return None
            elif error_code == 'DecryptionFailureException':
                print(f"Failed to decrypt secret {secret_name}")
                return None
            elif error_code == 'InternalServiceErrorException':
                print(f"Internal service error retrieving secret {secret_name}")
                return None
            else:
                print(f"Error retrieving secret {secret_name}: {e}")
                return None
        except Exception as e:
            print(f"Unexpected error retrieving secret {secret_name}: {e}")
            return None
    
    async def put_secret(self, secret_name: str, secret_value: str, tenant_id: str = None) -> bool:
        """Store a secret value."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            # Try to update existing secret first
            try:
                self.secrets_client.update_secret(
                    SecretId=full_secret_name,
                    SecretString=secret_value
                )
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Secret doesn't exist, create it
                    description = f"Secret for {tenant_id}" if tenant_id else "Application secret"
                    
                    # Add tenant tag if applicable
                    tags = []
                    if tenant_id:
                        tags.append({
                            'Key': 'TenantId',
                            'Value': tenant_id
                        })
                        tags.append({
                            'Key': 'Environment',
                            'Value': 'production'  # Could be configurable
                        })
                    
                    self.secrets_client.create_secret(
                        Name=full_secret_name,
                        Description=description,
                        SecretString=secret_value,
                        Tags=tags
                    )
                    return True
                else:
                    raise
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error storing secret {secret_name}: {e}")
            return False
    
    async def delete_secret(self, secret_name: str, tenant_id: str = None) -> bool:
        """Delete a secret."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            # Schedule secret for deletion (can be recovered within recovery window)
            self.secrets_client.delete_secret(
                SecretId=full_secret_name,
                RecoveryWindowInDays=7  # Minimum recovery window
            )
            
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return True  # Secret doesn't exist, consider it deleted
            print(f"Error deleting secret {secret_name}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error deleting secret {secret_name}: {e}")
            return False
    
    async def get_secret_json(self, secret_name: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve a secret value as JSON."""
        try:
            secret_string = await self.get_secret(secret_name, tenant_id)
            if secret_string:
                return json.loads(secret_string)
            return None
            
        except json.JSONDecodeError as e:
            print(f"Secret {secret_name} is not valid JSON: {e}")
            return None
    
    async def put_secret_json(self, secret_name: str, secret_data: Dict[str, Any], tenant_id: str = None) -> bool:
        """Store a secret value as JSON."""
        try:
            secret_string = json.dumps(secret_data)
            return await self.put_secret(secret_name, secret_string, tenant_id)
            
        except (TypeError, ValueError) as e:
            print(f"Failed to serialize secret data to JSON: {e}")
            return False
    
    async def list_secrets(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """List secrets, optionally filtered by tenant."""
        try:
            secrets = []
            paginator = self.secrets_client.get_paginator('list_secrets')
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    secret_name = secret['Name']
                    
                    # Filter by tenant if specified
                    if tenant_id:
                        prefix = self.tenant_prefixes.get(tenant_id, f"{tenant_id}/")
                        if not secret_name.startswith(prefix):
                            continue
                        # Remove tenant prefix for cleaner display
                        display_name = secret_name[len(prefix):]
                    else:
                        display_name = secret_name
                    
                    secret_info = {
                        'name': display_name,
                        'full_name': secret_name,
                        'description': secret.get('Description', ''),
                        'created_date': secret.get('CreatedDate').isoformat() if secret.get('CreatedDate') else None,
                        'last_changed_date': secret.get('LastChangedDate').isoformat() if secret.get('LastChangedDate') else None,
                        'last_accessed_date': secret.get('LastAccessedDate').isoformat() if secret.get('LastAccessedDate') else None,
                        'tags': secret.get('Tags', [])
                    }
                    
                    secrets.append(secret_info)
            
            return secrets
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error listing secrets: {e}")
            return []
    
    async def rotate_secret(self, secret_name: str, tenant_id: str = None, 
                           rotation_lambda_arn: str = None) -> bool:
        """Rotate a secret using AWS Lambda function."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            if rotation_lambda_arn:
                # Configure automatic rotation
                self.secrets_client.rotate_secret(
                    SecretId=full_secret_name,
                    RotationLambdaArn=rotation_lambda_arn,
                    RotationRules={
                        'AutomaticallyAfterDays': 30  # Rotate every 30 days
                    }
                )
            else:
                # Manual rotation - just trigger rotation
                self.secrets_client.rotate_secret(
                    SecretId=full_secret_name
                )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error rotating secret {secret_name}: {e}")
            return False
    
    async def get_secret_versions(self, secret_name: str, tenant_id: str = None) -> List[Dict[str, Any]]:
        """Get all versions of a secret."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            response = self.secrets_client.describe_secret(
                SecretId=full_secret_name
            )
            
            versions = []
            version_ids = response.get('VersionIdsToStages', {})
            
            for version_id, stages in version_ids.items():
                version_info = {
                    'version_id': version_id,
                    'stages': stages,
                    'created_date': response.get('CreatedDate').isoformat() if response.get('CreatedDate') else None,
                    'is_current': 'AWSCURRENT' in stages,
                    'is_pending': 'AWSPENDING' in stages
                }
                versions.append(version_info)
            
            return versions
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting secret versions for {secret_name}: {e}")
            return []
    
    async def restore_secret(self, secret_name: str, tenant_id: str = None) -> bool:
        """Restore a deleted secret (within recovery window)."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            self.secrets_client.restore_secret(
                SecretId=full_secret_name
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error restoring secret {secret_name}: {e}")
            return False
    
    async def update_secret_description(self, secret_name: str, description: str, tenant_id: str = None) -> bool:
        """Update secret description."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            self.secrets_client.update_secret(
                SecretId=full_secret_name,
                Description=description
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error updating secret description for {secret_name}: {e}")
            return False
    
    async def tag_secret(self, secret_name: str, tags: Dict[str, str], tenant_id: str = None) -> bool:
        """Add tags to a secret."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            # Convert dict to AWS tags format
            aws_tags = [{'Key': key, 'Value': value} for key, value in tags.items()]
            
            self.secrets_client.tag_resource(
                SecretId=full_secret_name,
                Tags=aws_tags
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error tagging secret {secret_name}: {e}")
            return False
    
    async def untag_secret(self, secret_name: str, tag_keys: List[str], tenant_id: str = None) -> bool:
        """Remove tags from a secret."""
        try:
            full_secret_name = self._get_secret_name(secret_name, tenant_id)
            
            self.secrets_client.untag_resource(
                SecretId=full_secret_name,
                TagKeys=tag_keys
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error untagging secret {secret_name}: {e}")
            return False
    
    async def get_random_password(self, length: int = 32, exclude_characters: str = None, 
                                 include_space: bool = False, require_each_included_type: bool = True) -> Optional[str]:
        """Generate a random password using AWS Secrets Manager."""
        try:
            params = {
                'PasswordLength': length,
                'IncludeSpace': include_space,
                'RequireEachIncludedType': require_each_included_type
            }
            
            if exclude_characters:
                params['ExcludeCharacters'] = exclude_characters
            
            response = self.secrets_client.get_random_password(**params)
            
            return response.get('RandomPassword')
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error generating random password: {e}")
            return None