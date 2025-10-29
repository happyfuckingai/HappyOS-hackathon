"""
Parameter Management for CDK Application

Handles parameter validation, transformation, and context management.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json


@dataclass
class ParameterDefinition:
    """Definition of a CDK parameter."""
    name: str
    description: str
    parameter_type: str
    default_value: Optional[Any] = None
    allowed_values: Optional[List[str]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    constraint_description: Optional[str] = None


class ParameterManager:
    """Manages CDK parameters and validation."""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.parameters: Dict[str, ParameterDefinition] = {}
        self._define_parameters()
    
    def _define_parameters(self) -> None:
        """Define all CDK parameters."""
        
        # Environment parameters
        self.parameters["Environment"] = ParameterDefinition(
            name="Environment",
            description="Deployment environment (dev, staging, prod)",
            parameter_type="String",
            default_value=self.environment,
            allowed_values=["dev", "staging", "prod"],
            constraint_description="Must be dev, staging, or prod"
        )
        
        # Network parameters
        self.parameters["VpcCidr"] = ParameterDefinition(
            name="VpcCidr",
            description="CIDR block for the VPC",
            parameter_type="String",
            default_value="10.0.0.0/16",
            constraint_description="Must be a valid CIDR block"
        )
        
        self.parameters["AvailabilityZones"] = ParameterDefinition(
            name="AvailabilityZones",
            description="Comma-separated list of availability zones",
            parameter_type="CommaDelimitedList",
            default_value="us-east-1a,us-east-1b",
            constraint_description="Must be valid availability zones"
        )
        
        # Service parameters
        self.parameters["OpenSearchInstanceType"] = ParameterDefinition(
            name="OpenSearchInstanceType",
            description="Instance type for OpenSearch cluster",
            parameter_type="String",
            default_value="t3.small.search",
            allowed_values=[
                "t3.small.search", "t3.medium.search", "t3.large.search",
                "m6g.large.search", "m6g.xlarge.search", "m6g.2xlarge.search"
            ],
            constraint_description="Must be a valid OpenSearch instance type"
        )
        
        self.parameters["ElastiCacheNodeType"] = ParameterDefinition(
            name="ElastiCacheNodeType",
            description="Node type for ElastiCache cluster",
            parameter_type="String",
            default_value="cache.t3.micro",
            allowed_values=[
                "cache.t3.micro", "cache.t3.small", "cache.t3.medium",
                "cache.r6g.large", "cache.r6g.xlarge", "cache.r6g.2xlarge"
            ],
            constraint_description="Must be a valid ElastiCache node type"
        )
        
        self.parameters["LambdaMemorySize"] = ParameterDefinition(
            name="LambdaMemorySize",
            description="Memory size for Lambda functions (MB)",
            parameter_type="Number",
            default_value=512,
            constraint_description="Must be between 128 and 10240 MB"
        )
        
        # Security parameters
        self.parameters["KmsKeyRotation"] = ParameterDefinition(
            name="KmsKeyRotation",
            description="Enable automatic KMS key rotation",
            parameter_type="String",
            default_value="true",
            allowed_values=["true", "false"],
            constraint_description="Must be true or false"
        )
        
        # Monitoring parameters
        self.parameters["EnableDetailedMonitoring"] = ParameterDefinition(
            name="EnableDetailedMonitoring",
            description="Enable detailed CloudWatch monitoring",
            parameter_type="String",
            default_value="false",
            allowed_values=["true", "false"],
            constraint_description="Must be true or false"
        )
        
        # Cost optimization parameters
        self.parameters["EnableCostOptimization"] = ParameterDefinition(
            name="EnableCostOptimization",
            description="Enable cost optimization features",
            parameter_type="String",
            default_value="true",
            allowed_values=["true", "false"],
            constraint_description="Must be true or false"
        )
    
    def get_parameter_definition(self, name: str) -> ParameterDefinition:
        """Get parameter definition by name."""
        if name not in self.parameters:
            raise ValueError(f"Parameter '{name}' not found")
        return self.parameters[name]
    
    def get_all_parameters(self) -> Dict[str, ParameterDefinition]:
        """Get all parameter definitions."""
        return self.parameters.copy()
    
    def validate_parameter_value(self, name: str, value: Any) -> bool:
        """Validate a parameter value against its definition."""
        param_def = self.get_parameter_definition(name)
        
        # Check allowed values
        if param_def.allowed_values and value not in param_def.allowed_values:
            return False
        
        # Check string length constraints
        if param_def.parameter_type == "String" and isinstance(value, str):
            if param_def.min_length and len(value) < param_def.min_length:
                return False
            if param_def.max_length and len(value) > param_def.max_length:
                return False
        
        return True
    
    def get_parameter_context(self) -> Dict[str, Any]:
        """Get parameter context for CDK deployment."""
        context = {}
        
        for name, param_def in self.parameters.items():
            # Try to get value from environment variable
            env_var_name = f"CDK_PARAM_{name.upper()}"
            value = os.getenv(env_var_name, param_def.default_value)
            
            # Validate the value
            if not self.validate_parameter_value(name, value):
                raise ValueError(
                    f"Invalid value '{value}' for parameter '{name}'. "
                    f"{param_def.constraint_description}"
                )
            
            context[name] = value
        
        return context
    
    def generate_cdk_json_context(self) -> Dict[str, Any]:
        """Generate context section for cdk.json file."""
        return {
            "@aws-cdk/aws-lambda:recognizeLayerVersion": True,
            "@aws-cdk/core:checkSecretUsage": True,
            "@aws-cdk/core:target-partitions": ["aws", "aws-cn"],
            "@aws-cdk/aws-opensearch:enableOpensearchMultiAzWithStandby": True,
            "parameters": self.get_parameter_context()
        }