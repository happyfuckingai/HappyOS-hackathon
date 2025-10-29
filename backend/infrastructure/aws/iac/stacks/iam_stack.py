"""
IAM Stack

Creates IAM roles and policies for multi-tenant access control.
"""

from aws_cdk import (
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct
from typing import Dict

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class IamStack(BaseStack):
    """IAM stack for role-based access control."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        # Create service roles
        self.lambda_execution_role = self._create_lambda_execution_role()
        self.api_gateway_role = self._create_api_gateway_role()
        self.opensearch_role = self._create_opensearch_role()
        
        # Create tenant-specific roles
        self.tenant_roles = self._create_tenant_roles()
        
        # Create cross-service policies
        self._create_cross_service_policies()
        
        # Create outputs
        self._create_outputs()
    
    def _create_lambda_execution_role(self) -> iam.Role:
        """Create Lambda execution role with necessary permissions."""
        
        role = iam.Role(
            self,
            "LambdaExecutionRole",
            role_name=self.get_resource_name("lambda-execution"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Add custom policies
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[f"arn:aws:secretsmanager:{self.env_config.aws_region}:{self.env_config.aws_account_id}:secret:{self.get_resource_name('*')}"]
            )
        )
        
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey"
                ],
                resources=[f"arn:aws:kms:{self.env_config.aws_region}:{self.env_config.aws_account_id}:key/*"]
            )
        )
        
        return role
    
    def _create_api_gateway_role(self) -> iam.Role:
        """Create API Gateway execution role."""
        
        role = iam.Role(
            self,
            "ApiGatewayRole",
            role_name=self.get_resource_name("api-gateway"),
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonAPIGatewayPushToCloudWatchLogs")
            ]
        )
        
        # Add Lambda invoke permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{self.env_config.aws_region}:{self.env_config.aws_account_id}:function:{self.get_resource_name('*')}"]
            )
        )
        
        return role
    
    def _create_opensearch_role(self) -> iam.Role:
        """Create OpenSearch service role."""
        
        role = iam.Role(
            self,
            "OpenSearchRole",
            role_name=self.get_resource_name("opensearch"),
            assumed_by=iam.ServicePrincipal("opensearch.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonOpenSearchServiceRolePolicy")
            ]
        )
        
        return role
    
    def _create_tenant_roles(self) -> Dict[str, iam.Role]:
        """Create tenant-specific IAM roles."""
        
        tenant_roles = {}
        
        for tenant_name in self.env_config.get_all_tenant_names():
            tenant_config = self.env_config.get_tenant_config(tenant_name)
            
            role = iam.Role(
                self,
                f"{tenant_name.title()}Role",
                role_name=self.get_resource_name(f"{tenant_name}-tenant"),
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
                ]
            )
            
            # Add tenant-specific permissions
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "es:ESHttpGet",
                        "es:ESHttpPost",
                        "es:ESHttpPut",
                        "es:ESHttpDelete"
                    ],
                    resources=[
                        f"arn:aws:es:{self.env_config.aws_region}:{self.env_config.aws_account_id}:domain/{self.get_resource_name('opensearch')}/{tenant_config.opensearch_index_prefix}*"
                    ]
                )
            )
            
            # Add ElastiCache permissions with namespace isolation
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "elasticache:DescribeCacheClusters",
                        "elasticache:DescribeReplicationGroups"
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "elasticache:cache-cluster-id": f"{self.get_resource_name('redis-cluster')}"
                        }
                    }
                )
            )
            
            # Add tenant-specific tags
            self.add_tenant_tags(role, tenant_name)
            
            tenant_roles[tenant_name] = role
        
        return tenant_roles
    
    def _create_cross_service_policies(self) -> None:
        """Create policies for cross-service communication."""
        
        # Circuit breaker policy
        circuit_breaker_policy = iam.ManagedPolicy(
            self,
            "CircuitBreakerPolicy",
            managed_policy_name=self.get_resource_name("circuit-breaker-policy"),
            description="Policy for circuit breaker functionality",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:ListMetrics",
                        "cloudwatch:PutMetricData"
                    ],
                    resources=["*"]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:InvokeFunction"
                    ],
                    resources=[f"arn:aws:lambda:{self.env_config.aws_region}:{self.env_config.aws_account_id}:function:{self.get_resource_name('health-check')}"]
                )
            ]
        )
        
        # Attach to Lambda execution role
        self.lambda_execution_role.add_managed_policy(circuit_breaker_policy)
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "LambdaExecutionRoleArn",
            value=self.lambda_execution_role.role_arn,
            description="Lambda execution role ARN"
        )
        
        self.create_output(
            "ApiGatewayRoleArn",
            value=self.api_gateway_role.role_arn,
            description="API Gateway role ARN"
        )
        
        self.create_output(
            "OpenSearchRoleArn",
            value=self.opensearch_role.role_arn,
            description="OpenSearch service role ARN"
        )
        
        # Output tenant role ARNs
        for tenant_name, role in self.tenant_roles.items():
            self.create_output(
                f"{tenant_name.title()}RoleArn",
                value=role.role_arn,
                description=f"IAM role ARN for {tenant_name} tenant"
            )