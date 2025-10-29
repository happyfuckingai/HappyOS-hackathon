#!/usr/bin/env python3
"""
Infrastructure Recovery CDK Application

This CDK application provisions the complete AWS infrastructure for the
multi-tenant agent platform with fallback capabilities.
"""

import os
from aws_cdk import App, Environment, Tags
from constructs import Construct

from .stacks.vpc_stack import VpcStack
from .stacks.opensearch_stack import OpenSearchStack
from .stacks.lambda_stack import LambdaStack
from .stacks.api_gateway_stack import ApiGatewayStack
from .stacks.elasticache_stack import ElastiCacheStack
from .stacks.cloudwatch_stack import CloudWatchStack
from .stacks.kms_secrets_stack import KmsSecretsStack
from .stacks.iam_stack import IamStack
from .config.environment_config import EnvironmentConfig


class InfrastructureRecoveryApp(Construct):
    """Main CDK application for infrastructure recovery."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Load environment configuration
        self.env_config = EnvironmentConfig()
        
        # Create foundational stacks
        self.vpc_stack = VpcStack(
            self, "VpcStack",
            env_config=self.env_config,
            description="VPC with network isolation and security groups"
        )
        
        self.iam_stack = IamStack(
            self, "IamStack",
            env_config=self.env_config,
            description="IAM roles and policies for multi-tenant access"
        )
        
        self.kms_secrets_stack = KmsSecretsStack(
            self, "KmsSecretsStack",
            env_config=self.env_config,
            description="KMS keys and Secrets Manager for secure configuration"
        )
        
        # Create service stacks
        self.opensearch_stack = OpenSearchStack(
            self, "OpenSearchStack",
            vpc=self.vpc_stack.vpc,
            security_group=self.vpc_stack.opensearch_security_group,
            env_config=self.env_config,
            description="OpenSearch cluster with tenant indices"
        )
        
        self.elasticache_stack = ElastiCacheStack(
            self, "ElastiCacheStack",
            vpc=self.vpc_stack.vpc,
            security_group=self.vpc_stack.elasticache_security_group,
            env_config=self.env_config,
            description="ElastiCache Redis cluster for caching"
        )
        
        self.lambda_stack = LambdaStack(
            self, "LambdaStack",
            vpc=self.vpc_stack.vpc,
            security_group=self.vpc_stack.lambda_security_group,
            env_config=self.env_config,
            description="Lambda functions for agent runtime"
        )
        
        self.api_gateway_stack = ApiGatewayStack(
            self, "ApiGatewayStack",
            lambda_functions=self.lambda_stack.functions,
            env_config=self.env_config,
            description="API Gateway with request routing and throttling"
        )
        
        self.cloudwatch_stack = CloudWatchStack(
            self, "CloudWatchStack",
            env_config=self.env_config,
            description="CloudWatch metrics, logs, and alarms"
        )
        
        # Add stack dependencies
        self._setup_dependencies()
        
        # Apply common tags
        self._apply_tags()
    
    def _setup_dependencies(self) -> None:
        """Set up dependencies between stacks."""
        # Service stacks depend on foundational stacks
        self.opensearch_stack.add_dependency(self.vpc_stack)
        self.opensearch_stack.add_dependency(self.iam_stack)
        
        self.elasticache_stack.add_dependency(self.vpc_stack)
        self.elasticache_stack.add_dependency(self.iam_stack)
        
        self.lambda_stack.add_dependency(self.vpc_stack)
        self.lambda_stack.add_dependency(self.iam_stack)
        self.lambda_stack.add_dependency(self.kms_secrets_stack)
        
        self.api_gateway_stack.add_dependency(self.lambda_stack)
        self.api_gateway_stack.add_dependency(self.iam_stack)
        
        self.cloudwatch_stack.add_dependency(self.lambda_stack)
        self.cloudwatch_stack.add_dependency(self.opensearch_stack)
    
    def _apply_tags(self) -> None:
        """Apply common tags to all resources."""
        Tags.of(self).add("Project", "InfrastructureRecovery")
        Tags.of(self).add("Environment", self.env_config.environment)
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("CostCenter", self.env_config.cost_center)


def main():
    """Main entry point for CDK application."""
    app = App()
    
    # Get environment configuration
    env_config = EnvironmentConfig()
    
    # Create the main application stack
    InfrastructureRecoveryApp(
        app, 
        f"InfrastructureRecovery-{env_config.environment}",
        env=Environment(
            account=env_config.aws_account_id,
            region=env_config.aws_region
        )
    )
    
    app.synth()


if __name__ == "__main__":
    main()