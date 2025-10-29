#!/usr/bin/env python3
"""
Infrastructure Conversion Utilities

Convert Terraform GCP configurations to AWS CDK/CloudFormation
and migrate infrastructure components while maintaining A2A accessibility.
"""

import asyncio
import logging
import json
import yaml
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import re

# ONLY HappyOS SDK imports allowed
from happyos_sdk import (
    A2AClient, create_a2a_client, create_service_facades,
    DatabaseFacade, StorageFacade, ComputeFacade,
    CircuitBreaker, get_circuit_breaker, CircuitBreakerConfig,
    HappyOSSDKError, ServiceUnavailableError
)

logger = logging.getLogger(__name__)


@dataclass
class TerraformResource:
    """Terraform resource configuration."""
    resource_type: str
    resource_name: str
    configuration: Dict[str, Any]
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class AWSResource:
    """AWS CDK/CloudFormation resource configuration."""
    resource_type: str
    resource_name: str
    properties: Dict[str, Any]
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class ConversionResult:
    """Result of infrastructure conversion."""
    success: bool
    conversion_id: str
    source_resources: int
    converted_resources: int
    aws_resources: List[AWSResource]
    cdk_code: str
    cloudformation_template: Dict[str, Any]
    errors: List[str] = None
    warnings: List[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class InfrastructureConverter:
    """
    Infrastructure Conversion from Terraform GCP to AWS CDK.
    
    Converts:
    - Terraform GCP configurations to AWS CDK
    - GCP Cloud Run services to AWS Lambda functions accessible via A2A
    - GCP Load Balancer to AWS API Gateway
    - Monitoring and alerting to AWS CloudWatch
    """
    
    def __init__(self, agent_id: str = "infrastructure_converter",
                 tenant_id: Optional[str] = None):
        """
        Initialize Infrastructure Converter.
        
        Args:
            agent_id: Converter agent ID
            tenant_id: Tenant ID for isolation
        """
        self.agent_id = agent_id
        self.tenant_id = tenant_id or "default"
        
        # HappyOS SDK components
        self.a2a_client: Optional[A2AClient] = None
        self.database: Optional[DatabaseFacade] = None
        self.storage: Optional[StorageFacade] = None
        self.compute: Optional[ComputeFacade] = None
        
        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Conversion mappings
        self.resource_mappings = self._initialize_resource_mappings()
        
        # Conversion history
        self.conversion_history: List[Dict[str, Any]] = []
        
        self.is_initialized = False
        logger.info(f"Infrastructure Converter created: {agent_id}")
    
    async def initialize(self) -> bool:
        """Initialize the infrastructure converter."""
        try:
            # Create A2A client
            self.a2a_client = create_a2a_client(
                agent_id=self.agent_id,
                transport_type="inprocess",
                tenant_id=self.tenant_id
            )
            
            await self.a2a_client.connect()
            
            # Create service facades
            facades = create_service_facades(self.a2a_client)
            self.database = facades["database"]
            self.storage = facades["storage"]
            self.compute = facades["compute"]
            
            # Initialize circuit breakers
            await self._initialize_circuit_breakers()
            
            self.is_initialized = True
            logger.info("Infrastructure Converter initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Infrastructure Converter: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the infrastructure converter."""
        try:
            if self.a2a_client:
                await self.a2a_client.disconnect()
            
            self.is_initialized = False
            logger.info("Infrastructure Converter shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for infrastructure operations."""
        # Terraform parsing circuit breaker
        parsing_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        self.circuit_breakers["terraform_parsing"] = get_circuit_breaker(
            "terraform_parsing", parsing_config
        )
        
        # AWS resource creation circuit breaker
        aws_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=120,
            expected_exception=ServiceUnavailableError
        )
        self.circuit_breakers["aws_resources"] = get_circuit_breaker(
            "aws_resource_creation", aws_config
        )
    
    def _initialize_resource_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize GCP to AWS resource mappings."""
        return {
            "google_cloud_run_service": {
                "aws_type": "AWS::Lambda::Function",
                "converter": self._convert_cloud_run_to_lambda
            },
            "google_compute_global_forwarding_rule": {
                "aws_type": "AWS::ApiGateway::RestApi",
                "converter": self._convert_load_balancer_to_api_gateway
            },
            "google_bigquery_dataset": {
                "aws_type": "AWS::OpenSearch::Domain",
                "converter": self._convert_bigquery_to_opensearch
            },
            "google_pubsub_topic": {
                "aws_type": "AWS::Events::EventBus",
                "converter": self._convert_pubsub_to_eventbridge
            },
            "google_storage_bucket": {
                "aws_type": "AWS::S3::Bucket",
                "converter": self._convert_storage_to_s3
            },
            "google_monitoring_alert_policy": {
                "aws_type": "AWS::CloudWatch::Alarm",
                "converter": self._convert_monitoring_to_cloudwatch
            }
        }    
# TERRAFORM PARSING AND CONVERSION
    
    async def convert_terraform_to_cdk(self, 
                                     terraform_config: Union[str, Dict[str, Any]],
                                     conversion_id: str) -> ConversionResult:
        """
        Convert Terraform GCP configurations to AWS CDK.
        
        Args:
            terraform_config: Terraform configuration (file path or dict)
            conversion_id: Unique conversion identifier
            
        Returns:
            Conversion result with CDK code and CloudFormation template
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Terraform to CDK conversion: {conversion_id}")
            
            # Parse Terraform configuration
            async def _parse_terraform():
                if isinstance(terraform_config, str):
                    # Load from file
                    config_path = Path(terraform_config)
                    if not config_path.exists():
                        raise FileNotFoundError(f"Terraform config file not found: {terraform_config}")
                    
                    with open(config_path, 'r') as f:
                        if config_path.suffix == '.json':
                            return json.load(f)
                        else:
                            # Parse HCL (simplified - in real implementation would use proper HCL parser)
                            return self._parse_hcl_file(f.read())
                else:
                    return terraform_config
            
            tf_config = await self.circuit_breakers["terraform_parsing"].execute(_parse_terraform)
            
            # Extract Terraform resources
            terraform_resources = self._extract_terraform_resources(tf_config)
            
            # Convert resources to AWS equivalents
            aws_resources = []
            conversion_errors = []
            conversion_warnings = []
            
            for tf_resource in terraform_resources:
                try:
                    aws_resource = await self._convert_terraform_resource(tf_resource)
                    if aws_resource:
                        aws_resources.append(aws_resource)
                    else:
                        conversion_warnings.append(f"No conversion mapping for resource type: {tf_resource.resource_type}")
                        
                except Exception as e:
                    conversion_errors.append(f"Failed to convert resource {tf_resource.resource_name}: {str(e)}")
            
            # Generate CDK code
            cdk_code = self._generate_cdk_code(aws_resources, conversion_id)
            
            # Generate CloudFormation template
            cloudformation_template = self._generate_cloudformation_template(aws_resources, conversion_id)
            
            # Store conversion result
            await self._store_conversion_result(conversion_id, {
                "terraform_resources": len(terraform_resources),
                "aws_resources": len(aws_resources),
                "errors": conversion_errors,
                "warnings": conversion_warnings
            })
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            result = ConversionResult(
                success=len(conversion_errors) == 0,
                conversion_id=conversion_id,
                source_resources=len(terraform_resources),
                converted_resources=len(aws_resources),
                aws_resources=aws_resources,
                cdk_code=cdk_code,
                cloudformation_template=cloudformation_template,
                errors=conversion_errors,
                warnings=conversion_warnings
            )
            
            self.conversion_history.append(asdict(result))
            
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Terraform to CDK conversion failed: {e}")
            
            return ConversionResult(
                success=False,
                conversion_id=conversion_id,
                source_resources=0,
                converted_resources=0,
                aws_resources=[],
                cdk_code="",
                cloudformation_template={},
                errors=[str(e)]
            )
    
    def _parse_hcl_file(self, hcl_content: str) -> Dict[str, Any]:
        """Parse HCL file content (simplified parser)."""
        # This is a simplified HCL parser for demonstration
        # In a real implementation, would use python-hcl2 or similar
        
        config = {"resource": {}}
        
        # Extract resource blocks using regex
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{([^}]+)\}'
        
        for match in re.finditer(resource_pattern, hcl_content, re.DOTALL):
            resource_type = match.group(1)
            resource_name = match.group(2)
            resource_body = match.group(3)
            
            if resource_type not in config["resource"]:
                config["resource"][resource_type] = {}
            
            # Parse resource properties (simplified)
            properties = {}
            prop_pattern = r'(\w+)\s*=\s*"([^"]+)"'
            
            for prop_match in re.finditer(prop_pattern, resource_body):
                prop_name = prop_match.group(1)
                prop_value = prop_match.group(2)
                properties[prop_name] = prop_value
            
            config["resource"][resource_type][resource_name] = properties
        
        return config
    
    def _extract_terraform_resources(self, tf_config: Dict[str, Any]) -> List[TerraformResource]:
        """Extract Terraform resources from configuration."""
        resources = []
        
        if "resource" not in tf_config:
            return resources
        
        for resource_type, resource_instances in tf_config["resource"].items():
            for resource_name, resource_config in resource_instances.items():
                # Extract dependencies (simplified)
                dependencies = []
                if isinstance(resource_config, dict):
                    for key, value in resource_config.items():
                        if isinstance(value, str) and "${" in value:
                            # Extract resource references
                            ref_pattern = r'\$\{([^}]+)\}'
                            for ref_match in re.finditer(ref_pattern, value):
                                dependencies.append(ref_match.group(1))
                
                resources.append(TerraformResource(
                    resource_type=resource_type,
                    resource_name=resource_name,
                    configuration=resource_config,
                    dependencies=dependencies
                ))
        
        return resources
    
    async def _convert_terraform_resource(self, tf_resource: TerraformResource) -> Optional[AWSResource]:
        """Convert a single Terraform resource to AWS equivalent."""
        if tf_resource.resource_type not in self.resource_mappings:
            return None
        
        mapping = self.resource_mappings[tf_resource.resource_type]
        converter_func = mapping["converter"]
        
        try:
            aws_resource = await converter_func(tf_resource)
            return aws_resource
            
        except Exception as e:
            logger.error(f"Resource conversion failed for {tf_resource.resource_name}: {e}")
            raise
    
    # RESOURCE-SPECIFIC CONVERTERS
    
    async def _convert_cloud_run_to_lambda(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP Cloud Run service to AWS Lambda function accessible via A2A."""
        config = tf_resource.configuration
        
        # Extract Cloud Run configuration
        service_name = tf_resource.resource_name
        image = config.get("template", {}).get("spec", {}).get("containers", [{}])[0].get("image", "")
        memory = config.get("template", {}).get("spec", {}).get("containers", [{}])[0].get("resources", {}).get("limits", {}).get("memory", "512Mi")
        
        # Convert memory format
        memory_mb = 512
        if memory.endswith("Mi"):
            memory_mb = int(memory[:-2])
        elif memory.endswith("Gi"):
            memory_mb = int(memory[:-2]) * 1024
        
        # Generate Lambda properties
        lambda_properties = {
            "FunctionName": f"migrated-{service_name}",
            "Runtime": "python3.9",
            "Handler": "lambda_function.lambda_handler",
            "MemorySize": min(memory_mb, 10240),  # Lambda max is 10GB
            "Timeout": 900,  # 15 minutes max
            "Environment": {
                "Variables": {
                    "MIGRATED_FROM": "cloud_run",
                    "ORIGINAL_SERVICE": service_name,
                    "A2A_ENABLED": "true",
                    "TENANT_ID": self.tenant_id
                }
            },
            "Code": {
                "ZipFile": self._generate_lambda_wrapper_code(service_name, image)
            },
            "Role": {"Fn::GetAtt": [f"{service_name}LambdaRole", "Arn"]},
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-CloudRun"},
                {"Key": "OriginalService", "Value": service_name},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::Lambda::Function",
            resource_name=f"{service_name}Lambda",
            properties=lambda_properties,
            dependencies=[f"{service_name}LambdaRole"]
        )
    
    async def _convert_load_balancer_to_api_gateway(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP Load Balancer to AWS API Gateway."""
        config = tf_resource.configuration
        
        # Extract load balancer configuration
        lb_name = tf_resource.resource_name
        target = config.get("target", "")
        
        # Generate API Gateway properties
        api_properties = {
            "Name": f"migrated-{lb_name}-api",
            "Description": f"Migrated API Gateway from GCP Load Balancer {lb_name}",
            "EndpointConfiguration": {
                "Types": ["REGIONAL"]
            },
            "Policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "execute-api:Invoke",
                        "Resource": "arn:aws:execute-api:*:*:*"
                    }
                ]
            },
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-LoadBalancer"},
                {"Key": "OriginalTarget", "Value": target},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::ApiGateway::RestApi",
            resource_name=f"{lb_name}ApiGateway",
            properties=api_properties
        )
    
    async def _convert_bigquery_to_opensearch(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP BigQuery dataset to AWS OpenSearch domain."""
        config = tf_resource.configuration
        
        # Extract BigQuery configuration
        dataset_name = tf_resource.resource_name
        location = config.get("location", "US")
        
        # Generate OpenSearch properties
        opensearch_properties = {
            "DomainName": f"migrated-{dataset_name.lower().replace('_', '-')}",
            "EngineVersion": "OpenSearch_1.3",
            "ClusterConfig": {
                "InstanceType": "t3.small.search",
                "InstanceCount": 1,
                "DedicatedMasterEnabled": False
            },
            "EBSOptions": {
                "EBSEnabled": True,
                "VolumeType": "gp3",
                "VolumeSize": 20
            },
            "AccessPolicies": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{self.tenant_id}:root"},
                        "Action": "es:*",
                        "Resource": f"arn:aws:es:*:{self.tenant_id}:domain/migrated-{dataset_name.lower().replace('_', '-')}/*"
                    }
                ]
            },
            "EncryptionAtRestOptions": {
                "Enabled": True
            },
            "NodeToNodeEncryptionOptions": {
                "Enabled": True
            },
            "DomainEndpointOptions": {
                "EnforceHTTPS": True
            },
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-BigQuery"},
                {"Key": "OriginalDataset", "Value": dataset_name},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::OpenSearch::Domain",
            resource_name=f"{dataset_name}OpenSearch",
            properties=opensearch_properties
        )
    
    async def _convert_pubsub_to_eventbridge(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP Pub/Sub topic to AWS EventBridge."""
        config = tf_resource.configuration
        
        # Extract Pub/Sub configuration
        topic_name = tf_resource.resource_name
        
        # Generate EventBridge properties
        eventbridge_properties = {
            "Name": f"migrated-{topic_name}-bus",
            "Description": f"Migrated EventBridge bus from GCP Pub/Sub topic {topic_name}",
            "EventSourceName": f"custom.{topic_name}",
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-PubSub"},
                {"Key": "OriginalTopic", "Value": topic_name},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::Events::EventBus",
            resource_name=f"{topic_name}EventBus",
            properties=eventbridge_properties
        )
    
    async def _convert_storage_to_s3(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP Cloud Storage bucket to AWS S3 bucket."""
        config = tf_resource.configuration
        
        # Extract storage configuration
        bucket_name = tf_resource.resource_name
        location = config.get("location", "US")
        storage_class = config.get("storage_class", "STANDARD")
        
        # Map GCP storage class to S3
        s3_storage_class = {
            "STANDARD": "STANDARD",
            "NEARLINE": "STANDARD_IA",
            "COLDLINE": "GLACIER",
            "ARCHIVE": "DEEP_ARCHIVE"
        }.get(storage_class, "STANDARD")
        
        # Generate S3 properties
        s3_properties = {
            "BucketName": f"migrated-{bucket_name}-{self.tenant_id}",
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            },
            "LifecycleConfiguration": {
                "Rules": [
                    {
                        "Id": "MigratedStorageClassRule",
                        "Status": "Enabled",
                        "Transitions": [
                            {
                                "Days": 30,
                                "StorageClass": s3_storage_class
                            }
                        ]
                    }
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True
            },
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-CloudStorage"},
                {"Key": "OriginalBucket", "Value": bucket_name},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::S3::Bucket",
            resource_name=f"{bucket_name}S3Bucket",
            properties=s3_properties
        )
    
    async def _convert_monitoring_to_cloudwatch(self, tf_resource: TerraformResource) -> AWSResource:
        """Convert GCP Monitoring alert policy to AWS CloudWatch alarm."""
        config = tf_resource.configuration
        
        # Extract monitoring configuration
        policy_name = tf_resource.resource_name
        display_name = config.get("display_name", policy_name)
        
        # Generate CloudWatch alarm properties
        cloudwatch_properties = {
            "AlarmName": f"migrated-{policy_name}",
            "AlarmDescription": f"Migrated CloudWatch alarm from GCP monitoring policy {display_name}",
            "MetricName": "CPUUtilization",  # Default metric
            "Namespace": "AWS/Lambda",
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 2,
            "Threshold": 80,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [
                {"Ref": f"{policy_name}SNSTopic"}
            ],
            "Tags": [
                {"Key": "MigratedFrom", "Value": "GCP-Monitoring"},
                {"Key": "OriginalPolicy", "Value": policy_name},
                {"Key": "TenantId", "Value": self.tenant_id}
            ]
        }
        
        return AWSResource(
            resource_type="AWS::CloudWatch::Alarm",
            resource_name=f"{policy_name}CloudWatchAlarm",
            properties=cloudwatch_properties
        )    
# CODE GENERATION
    
    def _generate_lambda_wrapper_code(self, service_name: str, original_image: str) -> str:
        """Generate Lambda wrapper code for migrated Cloud Run service."""
        return f'''
import json
import logging
import os
from typing import Dict, Any

# HappyOS SDK imports for A2A communication
try:
    from happyos_sdk import create_a2a_client, A2AClient
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global A2A client
a2a_client: A2AClient = None

async def initialize_a2a():
    """Initialize A2A client for backend communication."""
    global a2a_client
    
    if A2A_AVAILABLE and not a2a_client:
        try:
            a2a_client = create_a2a_client(
                agent_id="migrated-{service_name}",
                transport_type="network",
                tenant_id=os.environ.get("TENANT_ID", "default")
            )
            await a2a_client.connect()
            logger.info("A2A client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize A2A client: {{e}}")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for migrated Cloud Run service: {service_name}
    Original image: {original_image}
    """
    try:
        logger.info(f"Processing request for migrated service: {service_name}")
        
        # Extract request information
        http_method = event.get("httpMethod", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {{}})
        body = event.get("body", "")
        
        # Initialize A2A client if available
        if A2A_AVAILABLE:
            import asyncio
            asyncio.run(initialize_a2a())
        
        # Process request based on original Cloud Run service logic
        # This is a placeholder - actual implementation would contain
        # the migrated business logic from the original service
        
        response_body = {{
            "message": "Hello from migrated {service_name}",
            "original_image": "{original_image}",
            "method": http_method,
            "path": path,
            "migrated_at": "{{datetime.utcnow().isoformat()}}",
            "a2a_enabled": A2A_AVAILABLE
        }}
        
        return {{
            "statusCode": 200,
            "headers": {{
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "X-Migrated-From": "GCP-CloudRun",
                "X-Original-Service": "{service_name}"
            }},
            "body": json.dumps(response_body)
        }}
        
    except Exception as e:
        logger.error(f"Error processing request: {{e}}")
        
        return {{
            "statusCode": 500,
            "headers": {{
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }},
            "body": json.dumps({{
                "error": "Internal server error",
                "service": "{service_name}",
                "migrated_from": "GCP-CloudRun"
            }})
        }}
'''
    
    def _generate_cdk_code(self, aws_resources: List[AWSResource], conversion_id: str) -> str:
        """Generate AWS CDK code from converted resources."""
        cdk_imports = [
            "from aws_cdk import (",
            "    Stack,",
            "    aws_lambda as _lambda,",
            "    aws_apigateway as apigateway,",
            "    aws_opensearch as opensearch,",
            "    aws_events as events,",
            "    aws_s3 as s3,",
            "    aws_cloudwatch as cloudwatch,",
            "    aws_iam as iam,",
            "    Duration,",
            "    RemovalPolicy",
            ")",
            "from constructs import Construct",
            "",
            ""
        ]
        
        class_definition = [
            f"class MigratedInfrastructureStack(Stack):",
            f'    """',
            f'    Migrated infrastructure stack from GCP to AWS',
            f'    Conversion ID: {conversion_id}',
            f'    Generated at: {datetime.utcnow().isoformat()}',
            f'    """',
            f"",
            f"    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:",
            f"        super().__init__(scope, construct_id, **kwargs)",
            f"",
            f"        # Migrated resources",
        ]
        
        resource_definitions = []
        
        for resource in aws_resources:
            if resource.resource_type == "AWS::Lambda::Function":
                resource_definitions.extend(self._generate_lambda_cdk_code(resource))
            elif resource.resource_type == "AWS::ApiGateway::RestApi":
                resource_definitions.extend(self._generate_api_gateway_cdk_code(resource))
            elif resource.resource_type == "AWS::OpenSearch::Domain":
                resource_definitions.extend(self._generate_opensearch_cdk_code(resource))
            elif resource.resource_type == "AWS::Events::EventBus":
                resource_definitions.extend(self._generate_eventbridge_cdk_code(resource))
            elif resource.resource_type == "AWS::S3::Bucket":
                resource_definitions.extend(self._generate_s3_cdk_code(resource))
            elif resource.resource_type == "AWS::CloudWatch::Alarm":
                resource_definitions.extend(self._generate_cloudwatch_cdk_code(resource))
        
        # Combine all parts
        cdk_code_lines = cdk_imports + class_definition + resource_definitions
        
        return "\n".join(cdk_code_lines)
    
    def _generate_lambda_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for Lambda function."""
        props = resource.properties
        
        return [
            f"",
            f"        # Lambda function: {resource.resource_name}",
            f"        {resource.resource_name.lower()}_role = iam.Role(",
            f"            self, '{resource.resource_name}Role',",
            f"            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),",
            f"            managed_policies=[",
            f"                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')",
            f"            ]",
            f"        )",
            f"",
            f"        {resource.resource_name.lower()} = _lambda.Function(",
            f"            self, '{resource.resource_name}',",
            f"            function_name='{props['FunctionName']}',",
            f"            runtime=_lambda.Runtime.PYTHON_3_9,",
            f"            handler='{props['Handler']}',",
            f"            code=_lambda.Code.from_inline('''",
            f"{props['Code']['ZipFile']}",
            f"            '''),",
            f"            memory_size={props['MemorySize']},",
            f"            timeout=Duration.seconds({props['Timeout']}),",
            f"            role={resource.resource_name.lower()}_role,",
            f"            environment={props.get('Environment', {}).get('Variables', {})},",
            f"        )",
            f""
        ]
    
    def _generate_api_gateway_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for API Gateway."""
        props = resource.properties
        
        return [
            f"",
            f"        # API Gateway: {resource.resource_name}",
            f"        {resource.resource_name.lower()} = apigateway.RestApi(",
            f"            self, '{resource.resource_name}',",
            f"            rest_api_name='{props['Name']}',",
            f"            description='{props['Description']}',",
            f"            endpoint_configuration=apigateway.EndpointConfiguration(",
            f"                types=[apigateway.EndpointType.REGIONAL]",
            f"            ),",
            f"        )",
            f""
        ]
    
    def _generate_opensearch_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for OpenSearch domain."""
        props = resource.properties
        
        return [
            f"",
            f"        # OpenSearch domain: {resource.resource_name}",
            f"        {resource.resource_name.lower()} = opensearch.Domain(",
            f"            self, '{resource.resource_name}',",
            f"            domain_name='{props['DomainName']}',",
            f"            version=opensearch.EngineVersion.OPENSEARCH_1_3,",
            f"            capacity=opensearch.CapacityConfig(",
            f"                data_node_instance_type='{props['ClusterConfig']['InstanceType']}',",
            f"                data_nodes={props['ClusterConfig']['InstanceCount']}",
            f"            ),",
            f"            ebs=opensearch.EbsOptions(",
            f"                volume_size={props['EBSOptions']['VolumeSize']},",
            f"                volume_type=opensearch.EbsDeviceVolumeType.GP3",
            f"            ),",
            f"            encryption_at_rest=opensearch.EncryptionAtRestOptions(",
            f"                enabled={str(props['EncryptionAtRestOptions']['Enabled']).lower()}",
            f"            ),",
            f"            node_to_node_encryption={str(props['NodeToNodeEncryptionOptions']['Enabled']).lower()},",
            f"            enforce_https={str(props['DomainEndpointOptions']['EnforceHTTPS']).lower()},",
            f"        )",
            f""
        ]
    
    def _generate_eventbridge_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for EventBridge."""
        props = resource.properties
        
        return [
            f"",
            f"        # EventBridge bus: {resource.resource_name}",
            f"        {resource.resource_name.lower()} = events.EventBus(",
            f"            self, '{resource.resource_name}',",
            f"            event_bus_name='{props['Name']}',",
            f"            description='{props['Description']}',",
            f"        )",
            f""
        ]
    
    def _generate_s3_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for S3 bucket."""
        props = resource.properties
        
        return [
            f"",
            f"        # S3 bucket: {resource.resource_name}",
            f"        {resource.resource_name.lower()} = s3.Bucket(",
            f"            self, '{resource.resource_name}',",
            f"            bucket_name='{props['BucketName']}',",
            f"            encryption=s3.BucketEncryption.S3_MANAGED,",
            f"            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,",
            f"            removal_policy=RemovalPolicy.RETAIN,",
            f"        )",
            f""
        ]
    
    def _generate_cloudwatch_cdk_code(self, resource: AWSResource) -> List[str]:
        """Generate CDK code for CloudWatch alarm."""
        props = resource.properties
        
        return [
            f"",
            f"        # CloudWatch alarm: {resource.resource_name}",
            f"        {resource.resource_name.lower()} = cloudwatch.Alarm(",
            f"            self, '{resource.resource_name}',",
            f"            alarm_name='{props['AlarmName']}',",
            f"            alarm_description='{props['AlarmDescription']}',",
            f"            metric=cloudwatch.Metric(",
            f"                namespace='{props['Namespace']}',",
            f"                metric_name='{props['MetricName']}',",
            f"                statistic='{props['Statistic']}',",
            f"            ),",
            f"            threshold={props['Threshold']},",
            f"            evaluation_periods={props['EvaluationPeriods']},",
            f"        )",
            f""
        ]
    
    def _generate_cloudformation_template(self, aws_resources: List[AWSResource], conversion_id: str) -> Dict[str, Any]:
        """Generate CloudFormation template from converted resources."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"Migrated infrastructure from GCP to AWS (Conversion ID: {conversion_id})",
            "Parameters": {
                "TenantId": {
                    "Type": "String",
                    "Default": self.tenant_id,
                    "Description": "Tenant ID for resource isolation"
                }
            },
            "Resources": {},
            "Outputs": {}
        }
        
        for resource in aws_resources:
            # Add resource to template
            template["Resources"][resource.resource_name] = {
                "Type": resource.resource_type,
                "Properties": resource.properties
            }
            
            # Add dependencies if any
            if resource.dependencies:
                template["Resources"][resource.resource_name]["DependsOn"] = resource.dependencies
            
            # Add output for important resources
            if resource.resource_type in ["AWS::Lambda::Function", "AWS::ApiGateway::RestApi", "AWS::OpenSearch::Domain"]:
                template["Outputs"][f"{resource.resource_name}Arn"] = {
                    "Description": f"ARN of {resource.resource_name}",
                    "Value": {"Fn::GetAtt": [resource.resource_name, "Arn"]},
                    "Export": {
                        "Name": {"Fn::Sub": f"${{AWS::StackName}}-{resource.resource_name}-Arn"}
                    }
                }
        
        return template
    
    async def _store_conversion_result(self, conversion_id: str, result_data: Dict[str, Any]):
        """Store conversion result for tracking."""
        try:
            conversion_record = {
                "conversion_id": conversion_id,
                "tenant_id": self.tenant_id,
                "result_data": result_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.database.store_data(conversion_record, "infrastructure_conversion")
            
        except Exception as e:
            logger.error(f"Failed to store conversion result: {e}")


# Factory function
def create_infrastructure_converter(agent_id: str = "infrastructure_converter",
                                  tenant_id: Optional[str] = None) -> InfrastructureConverter:
    """Create Infrastructure Converter instance."""
    return InfrastructureConverter(agent_id, tenant_id)


# Utility functions for Felicia's Finance migration
def create_felicia_finance_terraform_config() -> Dict[str, Any]:
    """Create sample Terraform configuration for Felicia's Finance migration."""
    return {
        "resource": {
            "google_cloud_run_service": {
                "crypto_trading_service": {
                    "name": "crypto-trading-service",
                    "location": "us-central1",
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "image": "gcr.io/project/crypto-trading:latest",
                                    "resources": {
                                        "limits": {
                                            "memory": "2Gi",
                                            "cpu": "1000m"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                },
                "bank_transaction_service": {
                    "name": "bank-transaction-service",
                    "location": "us-central1",
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "image": "gcr.io/project/bank-transactions:latest",
                                    "resources": {
                                        "limits": {
                                            "memory": "1Gi",
                                            "cpu": "500m"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "google_bigquery_dataset": {
                "crypto_analytics": {
                    "dataset_id": "crypto_analytics_dataset",
                    "location": "US"
                },
                "bank_analytics": {
                    "dataset_id": "bank_of_anthos_dataset",
                    "location": "US"
                }
            },
            "google_pubsub_topic": {
                "crypto_events": {
                    "name": "crypto-events-topic"
                },
                "bank_events": {
                    "name": "bank-events-topic"
                }
            },
            "google_storage_bucket": {
                "crypto_data": {
                    "name": "crypto-data-bucket",
                    "location": "US",
                    "storage_class": "STANDARD"
                },
                "bank_data": {
                    "name": "bank-data-bucket",
                    "location": "US",
                    "storage_class": "STANDARD"
                }
            }
        }
    }