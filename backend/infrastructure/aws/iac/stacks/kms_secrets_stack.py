"""
KMS and Secrets Manager Stack

Creates KMS keys and Secrets Manager for secure configuration.
"""

from aws_cdk import (
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class KmsSecretsStack(BaseStack):
    """KMS and Secrets Manager stack for security."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        # Create KMS keys
        self.encryption_key = self._create_encryption_key()
        self.secrets_key = self._create_secrets_key()
        
        # Create secrets
        self._create_secrets()
        
        # Create outputs
        self._create_outputs()
    
    def _create_encryption_key(self) -> kms.Key:
        """Create KMS key for general encryption."""
        
        key = kms.Key(
            self,
            "EncryptionKey",
            description="KMS key for Infrastructure Recovery encryption",
            enable_key_rotation=True,
            alias=f"alias/{self.get_resource_name('encryption')}"
        )
        
        # Grant usage to Lambda service
        key.grant_encrypt_decrypt(
            iam.ServicePrincipal("lambda.amazonaws.com")
        )
        
        return key
    
    def _create_secrets_key(self) -> kms.Key:
        """Create KMS key for Secrets Manager."""
        
        key = kms.Key(
            self,
            "SecretsKey",
            description="KMS key for Secrets Manager encryption",
            enable_key_rotation=True,
            alias=f"alias/{self.get_resource_name('secrets')}"
        )
        
        # Grant usage to Secrets Manager
        key.grant_encrypt_decrypt(
            iam.ServicePrincipal("secretsmanager.amazonaws.com")
        )
        
        return key
    
    def _create_secrets(self) -> None:
        """Create secrets in Secrets Manager."""
        
        # OpenSearch master password
        self.opensearch_secret = secretsmanager.Secret(
            self,
            "OpenSearchSecret",
            secret_name=f"{self.get_resource_name('opensearch')}/master-password",
            description="OpenSearch master user password",
            encryption_key=self.secrets_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "admin"}',
                generate_string_key="password",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                password_length=32
            )
        )
        
        # A2A protocol encryption keys for each tenant
        self.tenant_secrets = {}
        for tenant_name in self.env_config.get_all_tenant_names():
            secret = secretsmanager.Secret(
                self,
                f"{tenant_name.title()}A2ASecret",
                secret_name=f"{self.get_resource_name('a2a')}/{tenant_name}",
                description=f"A2A protocol keys for {tenant_name}",
                encryption_key=self.secrets_key,
                generate_secret_string=secretsmanager.SecretStringGenerator(
                    secret_string_template='{"tenant": "' + tenant_name + '"}',
                    generate_string_key="private_key",
                    exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                    password_length=64
                )
            )
            
            self.add_tenant_tags(secret, tenant_name)
            self.tenant_secrets[tenant_name] = secret
        
        # Database connection secrets
        self.db_secret = secretsmanager.Secret(
            self,
            "DatabaseSecret",
            secret_name=f"{self.get_resource_name('database')}/connection",
            description="Database connection credentials",
            encryption_key=self.secrets_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "admin", "engine": "postgres", "host": "localhost", "port": 5432, "dbname": "infrarecovery"}',
                generate_string_key="password",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\@",
                password_length=32
            )
        )
        
        # API keys for external services
        self.api_keys_secret = secretsmanager.Secret(
            self,
            "ApiKeysSecret",
            secret_name=f"{self.get_resource_name('api-keys')}/external",
            description="API keys for external services",
            encryption_key=self.secrets_key,
            secret_object_value={
                "openai_api_key": secretsmanager.SecretValue.unsafe_plain_text("placeholder"),
                "anthropic_api_key": secretsmanager.SecretValue.unsafe_plain_text("placeholder"),
                "aws_bedrock_region": secretsmanager.SecretValue.unsafe_plain_text(self.env_config.aws_region)
            }
        )
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "EncryptionKeyId",
            value=self.encryption_key.key_id,
            description="KMS encryption key ID"
        )
        
        self.create_output(
            "EncryptionKeyArn",
            value=self.encryption_key.key_arn,
            description="KMS encryption key ARN"
        )
        
        self.create_output(
            "SecretsKeyId",
            value=self.secrets_key.key_id,
            description="KMS secrets key ID"
        )
        
        self.create_output(
            "OpenSearchSecretArn",
            value=self.opensearch_secret.secret_arn,
            description="OpenSearch master password secret ARN"
        )
        
        self.create_output(
            "DatabaseSecretArn",
            value=self.db_secret.secret_arn,
            description="Database connection secret ARN"
        )