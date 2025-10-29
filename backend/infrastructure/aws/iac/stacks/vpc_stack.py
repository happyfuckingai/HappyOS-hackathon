"""
VPC Stack

Creates VPC with network isolation and security groups for multi-tenant architecture.
"""

from aws_cdk import (
    aws_ec2 as ec2,
    CfnOutput
)
from constructs import Construct
from typing import List

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class VpcStack(BaseStack):
    """VPC stack with network isolation and security groups."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        # Create VPC
        self.vpc = self._create_vpc()
        
        # Create security groups
        self.opensearch_security_group = self._create_opensearch_security_group()
        self.elasticache_security_group = self._create_elasticache_security_group()
        self.lambda_security_group = self._create_lambda_security_group()
        self.api_gateway_security_group = self._create_api_gateway_security_group()
        
        # Create VPC endpoints if enabled
        if self.env_config.network.enable_vpc_endpoints:
            self._create_vpc_endpoints()
        
        # Create outputs
        self._create_outputs()
    
    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public and private subnets."""
        
        # Define subnet configuration
        subnet_config = []
        
        # Public subnets
        for i, (az, cidr) in enumerate(zip(
            self.env_config.network.availability_zones,
            self.env_config.network.public_subnet_cidrs
        )):
            subnet_config.append(
                ec2.SubnetConfiguration(
                    name=f"PublicSubnet{i+1}",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            )
        
        # Private subnets
        for i, (az, cidr) in enumerate(zip(
            self.env_config.network.availability_zones,
            self.env_config.network.private_subnet_cidrs
        )):
            subnet_config.append(
                ec2.SubnetConfiguration(
                    name=f"PrivateSubnet{i+1}",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS if self.env_config.network.enable_nat_gateway else ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            )
        
        vpc = ec2.Vpc(
            self,
            "InfraRecoveryVpc",
            vpc_name=self.get_resource_name("vpc"),
            ip_addresses=ec2.IpAddresses.cidr(self.env_config.network.vpc_cidr),
            max_azs=len(self.env_config.network.availability_zones),
            subnet_configuration=subnet_config,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateways=len(self.env_config.network.availability_zones) if self.env_config.network.enable_nat_gateway else 0
        )
        
        return vpc
    
    def _create_opensearch_security_group(self) -> ec2.SecurityGroup:
        """Create security group for OpenSearch cluster."""
        sg = ec2.SecurityGroup(
            self,
            "OpenSearchSecurityGroup",
            vpc=self.vpc,
            description="Security group for OpenSearch cluster",
            security_group_name=self.get_resource_name("opensearch-sg")
        )
        
        # Allow HTTPS access from Lambda functions
        sg.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.lambda_security_group.security_group_id),
            connection=ec2.Port.tcp(443),
            description="HTTPS access from Lambda functions"
        )
        
        # Allow HTTP access from Lambda functions (for development)
        if self.env_config.environment == "dev":
            sg.add_ingress_rule(
                peer=ec2.Peer.security_group_id(self.lambda_security_group.security_group_id),
                connection=ec2.Port.tcp(80),
                description="HTTP access from Lambda functions (dev only)"
            )
        
        return sg
    
    def _create_elasticache_security_group(self) -> ec2.SecurityGroup:
        """Create security group for ElastiCache cluster."""
        sg = ec2.SecurityGroup(
            self,
            "ElastiCacheSecurityGroup",
            vpc=self.vpc,
            description="Security group for ElastiCache cluster",
            security_group_name=self.get_resource_name("elasticache-sg")
        )
        
        # Allow Redis access from Lambda functions
        sg.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.lambda_security_group.security_group_id),
            connection=ec2.Port.tcp(6379),
            description="Redis access from Lambda functions"
        )
        
        return sg
    
    def _create_lambda_security_group(self) -> ec2.SecurityGroup:
        """Create security group for Lambda functions."""
        sg = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Lambda functions",
            security_group_name=self.get_resource_name("lambda-sg")
        )
        
        # Allow outbound HTTPS traffic
        sg.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS outbound traffic"
        )
        
        # Allow outbound HTTP traffic (for development)
        if self.env_config.environment == "dev":
            sg.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(80),
                description="HTTP outbound traffic (dev only)"
            )
        
        return sg
    
    def _create_api_gateway_security_group(self) -> ec2.SecurityGroup:
        """Create security group for API Gateway VPC Link."""
        sg = ec2.SecurityGroup(
            self,
            "ApiGatewaySecurityGroup",
            vpc=self.vpc,
            description="Security group for API Gateway VPC Link",
            security_group_name=self.get_resource_name("apigateway-sg")
        )
        
        # Allow inbound HTTPS traffic
        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS inbound traffic"
        )
        
        return sg
    
    def _create_vpc_endpoints(self) -> None:
        """Create VPC endpoints for AWS services."""
        
        # S3 Gateway endpoint
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )
        
        # Interface endpoints for other services
        services = [
            ec2.InterfaceVpcEndpointAwsService.LAMBDA,
            ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            ec2.InterfaceVpcEndpointAwsService.KMS,
            ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH
        ]
        
        for i, service in enumerate(services):
            self.vpc.add_interface_endpoint(
                f"InterfaceEndpoint{i+1}",
                service=service,
                subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                security_groups=[self.lambda_security_group]
            )
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "VpcId",
            value=self.vpc.vpc_id,
            description="VPC ID"
        )
        
        self.create_output(
            "VpcCidr",
            value=self.vpc.vpc_cidr_block,
            description="VPC CIDR block"
        )
        
        # Private subnet IDs
        private_subnet_ids = [subnet.subnet_id for subnet in self.vpc.private_subnets]
        self.create_output(
            "PrivateSubnetIds",
            value=",".join(private_subnet_ids),
            description="Private subnet IDs"
        )
        
        # Public subnet IDs
        public_subnet_ids = [subnet.subnet_id for subnet in self.vpc.public_subnets]
        self.create_output(
            "PublicSubnetIds",
            value=",".join(public_subnet_ids),
            description="Public subnet IDs"
        )
        
        # Security group IDs
        self.create_output(
            "OpenSearchSecurityGroupId",
            value=self.opensearch_security_group.security_group_id,
            description="OpenSearch security group ID"
        )
        
        self.create_output(
            "ElastiCacheSecurityGroupId",
            value=self.elasticache_security_group.security_group_id,
            description="ElastiCache security group ID"
        )
        
        self.create_output(
            "LambdaSecurityGroupId",
            value=self.lambda_security_group.security_group_id,
            description="Lambda security group ID"
        )