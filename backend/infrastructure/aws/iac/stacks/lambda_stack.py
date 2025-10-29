"""
Lambda Stack

Creates Lambda functions for agent runtime with tenant isolation.
"""

from aws_cdk import (
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as iam,
    Duration,
    CfnOutput
)
from constructs import Construct
from typing import Dict

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class LambdaStack(BaseStack):
    """Lambda stack for agent runtime."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        vpc: ec2.Vpc,
        security_group: ec2.SecurityGroup,
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        self.vpc = vpc
        self.security_group = security_group
        self.functions: Dict[str, lambda_.Function] = {}
        
        # Create Lambda functions for each tenant
        self._create_tenant_functions()
        
        # Create shared functions
        self._create_shared_functions()
        
        # Create outputs
        self._create_outputs()
    
    def _create_tenant_functions(self) -> None:
        """Create Lambda functions for each tenant."""
        
        for tenant_name in self.env_config.get_all_tenant_names():
            tenant_config = self.env_config.get_tenant_config(tenant_name)
            
            # Create function for each agent in the tenant
            for agent_name in tenant_config.agents:
                function_name = f"{tenant_config.lambda_prefix}{agent_name}"
                
                function = lambda_.Function(
                    self,
                    f"{tenant_name.title()}{agent_name.title()}Function",
                    function_name=self.get_resource_name(function_name),
                    runtime=lambda_.Runtime.PYTHON_3_11,
                    handler="main.handler",
                    code=lambda_.Code.from_asset("../agents"),  # Placeholder path
                    memory_size=self.env_config.services.lambda_memory_size,
                    timeout=Duration.seconds(self.env_config.services.lambda_timeout),
                    vpc=self.vpc,
                    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                    security_groups=[self.security_group],
                    environment={
                        "TENANT_ID": tenant_name,
                        "AGENT_TYPE": agent_name,
                        "ENVIRONMENT": self.env_config.environment
                    }
                )
                
                # Add tenant-specific tags
                self.add_tenant_tags(function, tenant_name)
                
                self.functions[f"{tenant_name}_{agent_name}"] = function
    
    def _create_shared_functions(self) -> None:
        """Create shared Lambda functions."""
        
        # Health check function
        health_function = lambda_.Function(
            self,
            "HealthCheckFunction",
            function_name=self.get_resource_name("health-check"),
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="health.handler",
            code=lambda_.Code.from_asset("../shared"),  # Placeholder path
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={
                "ENVIRONMENT": self.env_config.environment
            }
        )
        
        self.functions["health_check"] = health_function
        
        # Circuit breaker function
        circuit_breaker_function = lambda_.Function(
            self,
            "CircuitBreakerFunction",
            function_name=self.get_resource_name("circuit-breaker"),
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="circuit_breaker.handler",
            code=lambda_.Code.from_asset("../shared"),  # Placeholder path
            memory_size=512,
            timeout=Duration.seconds(60),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[self.security_group],
            environment={
                "ENVIRONMENT": self.env_config.environment
            }
        )
        
        self.functions["circuit_breaker"] = circuit_breaker_function
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        # Output function ARNs
        for function_key, function in self.functions.items():
            self.create_output(
                f"{function_key.title().replace('_', '')}FunctionArn",
                value=function.function_arn,
                description=f"ARN for {function_key} Lambda function"
            )