"""
Base Stack Class

Provides common functionality and patterns for all CDK stacks.
"""

from aws_cdk import Stack, Tags, CfnOutput
from constructs import Construct
from typing import Dict, Any, Optional

from ..config.environment_config import EnvironmentConfig


class BaseStack(Stack):
    """Base class for all CDK stacks with common functionality."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        env_config: EnvironmentConfig,
        description: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, description=description, **kwargs)
        
        self.env_config = env_config
        self.stack_name = env_config.get_stack_name(construct_id.replace("Stack", ""))
        
        # Apply common tags
        self._apply_common_tags()
    
    def _apply_common_tags(self) -> None:
        """Apply common tags to all resources in this stack."""
        Tags.of(self).add("Project", "InfrastructureRecovery")
        Tags.of(self).add("Environment", self.env_config.environment)
        Tags.of(self).add("Stack", self.stack_name)
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("CostCenter", self.env_config.cost_center)
    
    def create_output(
        self, 
        output_id: str, 
        value: str, 
        description: Optional[str] = None,
        export_name: Optional[str] = None
    ) -> CfnOutput:
        """Create a CloudFormation output with standardized naming."""
        if not export_name:
            export_name = f"{self.stack_name}-{output_id}"
        
        return CfnOutput(
            self,
            output_id,
            value=value,
            description=description,
            export_name=export_name
        )
    
    def get_resource_name(self, resource_type: str, tenant: Optional[str] = None) -> str:
        """Get standardized resource name."""
        return self.env_config.get_resource_name(resource_type, tenant)
    
    def add_tenant_tags(self, construct: Construct, tenant_name: str) -> None:
        """Add tenant-specific tags to a construct."""
        Tags.of(construct).add("Tenant", tenant_name)
        Tags.of(construct).add("TenantDomain", self.env_config.get_tenant_config(tenant_name).domain)