"""
OpenSearch Stack

Creates OpenSearch cluster with tenant indices and security configuration.
"""

from aws_cdk import (
    aws_opensearch as opensearch,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class OpenSearchStack(BaseStack):
    """OpenSearch stack with tenant isolation."""
    
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
        
        # Create OpenSearch domain
        self.domain = self._create_opensearch_domain()
        
        # Create outputs
        self._create_outputs()
    
    def _create_opensearch_domain(self) -> opensearch.Domain:
        """Create OpenSearch domain with tenant isolation."""
        
        # Create IAM role for OpenSearch
        opensearch_role = iam.Role(
            self,
            "OpenSearchRole",
            assumed_by=iam.ServicePrincipal("opensearch.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonOpenSearchServiceRolePolicy")
            ]
        )
        
        # Create domain
        domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            version=opensearch.EngineVersion.OPENSEARCH_2_5,
            domain_name=self.get_resource_name("opensearch"),
            capacity=opensearch.CapacityConfig(
                data_node_instance_type=self.env_config.services.opensearch_instance_type,
                data_nodes=self.env_config.services.opensearch_instance_count
            ),
            ebs=opensearch.EbsOptions(
                volume_size=self.env_config.services.opensearch_volume_size,
                volume_type=ec2.EbsDeviceVolumeType.GP3
            ),
            vpc=self.vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
            security_groups=[self.security_group],
            zone_awareness=opensearch.ZoneAwarenessConfig(
                enabled=self.env_config.services.opensearch_instance_count > 1,
                availability_zone_count=min(2, self.env_config.services.opensearch_instance_count)
            ),
            logging=opensearch.LoggingOptions(
                slow_search_log_enabled=True,
                app_log_enabled=True,
                slow_index_log_enabled=True
            ),
            node_to_node_encryption=True,
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            enforce_https=True,
            fine_grained_access_control=opensearch.AdvancedSecurityOptions(
                master_user_name="admin",
                master_user_password_secret_key_id="opensearch-master-password"
            )
        )
        
        return domain
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "OpenSearchDomainEndpoint",
            value=self.domain.domain_endpoint,
            description="OpenSearch domain endpoint"
        )
        
        self.create_output(
            "OpenSearchDomainArn",
            value=self.domain.domain_arn,
            description="OpenSearch domain ARN"
        )