#!/usr/bin/env python3
"""
GCP to AWS Migration Utilities

Unified migration utilities for migrating infrastructure and data from GCP to AWS
while maintaining module isolation via HappyOS SDK.
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# ONLY HappyOS SDK imports allowed
from happyos_sdk import (
    A2AClient, create_a2a_client, create_service_facades,
    DatabaseFacade, StorageFacade, ComputeFacade, SearchFacade,
    CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker,
    HappyOSSDKError, ServiceUnavailableError, A2AError
)

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status enumeration."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK_REQUIRED = "rollback_required"
    ROLLED_BACK = "rolled_back"


class MigrationStep(Enum):
    """Migration step enumeration."""
    VALIDATE_SOURCE = "validate_source"
    PREPARE_TARGET = "prepare_target"
    MIGRATE_DATA = "migrate_data"
    MIGRATE_SERVICES = "migrate_services"
    MIGRATE_INFRASTRUCTURE = "migrate_infrastructure"
    VALIDATE_MIGRATION = "validate_migration"
    CLEANUP_SOURCE = "cleanup_source"


class ResourceType(Enum):
    """Resource type enumeration."""
    # GCP Resources
    BIGQUERY = "bigquery"
    CLOUD_RUN = "cloud_run"
    PUBSUB = "pubsub"
    CLOUD_STORAGE = "cloud_storage"
    CLOUD_FUNCTIONS = "cloud_functions"
    
    # AWS Resources  
    OPENSEARCH = "opensearch"
    DYNAMODB = "dynamodb"
    LAMBDA = "lambda"
    EVENTBRIDGE = "eventbridge"
    S3 = "s3"
    API_GATEWAY = "api_gateway"


@dataclass
class ResourceMapping:
    """Mapping between GCP and AWS resources."""
    gcp_type: ResourceType
    aws_type: ResourceType
    gcp_config: Dict[str, Any]
    aws_config: Dict[str, Any]
    migration_priority: int = 1
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class MigrationConfig:
    """Configuration for GCP to AWS migration."""
    migration_id: str
    source_project_id: str
    target_account_id: str
    source_region: str = "us-central1"
    target_region: str = "us-east-1"
    
    # Resource mappings
    resource_mappings: List[ResourceMapping] = None
    
    # Migration options
    preserve_data: bool = True
    validate_integrity: bool = True
    cleanup_source: bool = False
    rollback_on_failure: bool = True
    dry_run: bool = True
    
    def __post_init__(self):
        if self.resource_mappings is None:
            self.resource_mappings = []


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    step: MigrationStep
    status: MigrationStatus
    message: str
    migration_id: str
    data_migrated: int = 0
    services_migrated: int = 0
    resources_created: int = 0
    errors: List[str] = None
    warnings: List[str] = None
    timestamp: Optional[str] = None
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class GCPToAWSMigrator:
    """
    Unified GCP to AWS Migration Utilities.
    
    Provides comprehensive migration capabilities for:
    - BigQuery datasets to AWS OpenSearch and DynamoDB
    - Pub/Sub topics to EventBridge events
    - Cloud Run services to Lambda functions
    - Cloud Storage to S3 buckets
    - Infrastructure as Code conversion
    """
    
    def __init__(self, agent_id: str = "gcp_aws_migrator", 
                 tenant_id: Optional[str] = None):
        """
        Initialize GCP to AWS Migrator.
        
        Args:
            agent_id: Unique identifier for this migrator instance
            tenant_id: Tenant ID for multi-tenant deployments
        """
        self.agent_id = agent_id
        self.tenant_id = tenant_id or "default"
        
        # A2A client for communication
        self.a2a_client: Optional[A2AClient] = None
        
        # Service facades
        self.database: Optional[DatabaseFacade] = None
        self.storage: Optional[StorageFacade] = None
        self.compute: Optional[ComputeFacade] = None
        self.search: Optional[SearchFacade] = None
        
        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Migration state
        self.active_migrations: Dict[str, MigrationConfig] = {}
        self.migration_history: List[Dict[str, Any]] = []
        
        # Initialization status
        self.is_initialized = False
        
        logger.info(f"GCP to AWS Migrator created with agent_id: {agent_id}")
    
    async def initialize(self, transport_type: str = "inprocess",
                        endpoint: Optional[str] = None,
                        auth_token: Optional[str] = None) -> bool:
        """
        Initialize GCP to AWS Migrator.
        
        Args:
            transport_type: "network" or "inprocess"
            endpoint: Network endpoint for network transport
            auth_token: Authentication token for network transport
            
        Returns:
            Success status
        """
        try:
            # Create A2A client
            self.a2a_client = create_a2a_client(
                agent_id=self.agent_id,
                transport_type=transport_type,
                endpoint=endpoint,
                auth_token=auth_token,
                tenant_id=self.tenant_id
            )
            
            # Connect to A2A network
            await self.a2a_client.connect()
            
            # Create service facades
            facades = create_service_facades(self.a2a_client)
            self.database = facades["database"]
            self.storage = facades["storage"]
            self.compute = facades["compute"]
            self.search = facades["search"]
            
            # Initialize circuit breakers
            await self._initialize_circuit_breakers()
            
            # Register A2A message handlers
            await self._register_message_handlers()
            
            self.is_initialized = True
            logger.info("GCP to AWS Migrator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GCP to AWS Migrator: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown GCP to AWS Migrator."""
        try:
            if self.a2a_client:
                await self.a2a_client.disconnect()
            
            self.is_initialized = False
            logger.info("GCP to AWS Migrator shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during GCP to AWS Migrator shutdown: {e}")
    
    async def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for migration services."""
        try:
            # GCP services circuit breaker
            gcp_config = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=ServiceUnavailableError
            )
            self.circuit_breakers["gcp_services"] = get_circuit_breaker(
                "gcp_migration_services", gcp_config
            )
            
            # AWS services circuit breaker
            aws_config = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=ServiceUnavailableError
            )
            self.circuit_breakers["aws_services"] = get_circuit_breaker(
                "aws_migration_services", aws_config
            )
            
            # Data migration circuit breaker
            data_config = CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=120,
                expected_exception=Exception
            )
            self.circuit_breakers["data_migration"] = get_circuit_breaker(
                "data_migration", data_config
            )
            
            logger.info("Circuit breakers initialized for migration services")
            
        except Exception as e:
            logger.error(f"Failed to initialize circuit breakers: {e}")
            raise
    
    async def _register_message_handlers(self):
        """Register A2A message handlers for migration operations."""
        try:
            await self.a2a_client.register_handler("start_migration", self._handle_start_migration)
            await self.a2a_client.register_handler("get_migration_status", self._handle_get_migration_status)
            await self.a2a_client.register_handler("rollback_migration", self._handle_rollback_migration)
            await self.a2a_client.register_handler("validate_migration", self._handle_validate_migration)
            
            logger.info("GCP to AWS Migrator A2A handlers registered")
            
        except Exception as e:
            logger.error(f"Failed to register migration handlers: {e}")
            raise   
 # MIGRATION ORCHESTRATION METHODS
    
    async def migrate_bigquery_to_opensearch(self, 
                                           dataset_config: Dict[str, Any],
                                           migration_id: str) -> MigrationResult:
        """
        Migrate BigQuery dataset to AWS OpenSearch with schema mapping.
        
        Args:
            dataset_config: BigQuery dataset configuration
            migration_id: Migration identifier
            
        Returns:
            Migration result
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting BigQuery to OpenSearch migration: {dataset_config.get('dataset_id')}")
            
            # Use circuit breaker for data migration
            async def _migrate_data():
                # Extract data from BigQuery via A2A
                extract_response = await self.a2a_client.send_request(
                    recipient_id="gcp_data_service",
                    action="extract_bigquery_data",
                    data={
                        "project_id": dataset_config.get("project_id"),
                        "dataset_id": dataset_config.get("dataset_id"),
                        "tables": dataset_config.get("tables", []),
                        "migration_id": migration_id
                    }
                )
                
                if not extract_response.get("success"):
                    raise ServiceUnavailableError(f"BigQuery extraction failed: {extract_response.get('error')}")
                
                extracted_data = extract_response.get("data", [])
                
                # Transform data for OpenSearch
                transformed_data = await self._transform_bigquery_to_opensearch(extracted_data, dataset_config)
                
                # Create OpenSearch index via service facade
                index_name = f"{dataset_config.get('dataset_id', 'data')}-{migration_id}"
                
                # Create index mapping
                mapping_response = await self.search.create_index(
                    index_name=index_name,
                    mapping=self._generate_opensearch_mapping(transformed_data),
                    settings={
                        "number_of_shards": 1,
                        "number_of_replicas": 1
                    }
                )
                
                if not mapping_response.get("success"):
                    raise ServiceUnavailableError(f"OpenSearch index creation failed: {mapping_response.get('error')}")
                
                # Bulk load data to OpenSearch
                load_response = await self.search.bulk_index(
                    index_name=index_name,
                    documents=transformed_data
                )
                
                if not load_response.get("success"):
                    raise ServiceUnavailableError(f"OpenSearch data loading failed: {load_response.get('error')}")
                
                return {
                    "records_migrated": len(transformed_data),
                    "index_name": index_name,
                    "mapping_created": True
                }
            
            # Execute with circuit breaker
            result = await self.circuit_breakers["data_migration"].execute(_migrate_data)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return MigrationResult(
                success=True,
                step=MigrationStep.MIGRATE_DATA,
                status=MigrationStatus.COMPLETED,
                message=f"BigQuery to OpenSearch migration completed successfully",
                migration_id=migration_id,
                data_migrated=result.get("records_migrated", 0),
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"BigQuery to OpenSearch migration failed: {e}")
            
            return MigrationResult(
                success=False,
                step=MigrationStep.MIGRATE_DATA,
                status=MigrationStatus.FAILED,
                message=f"BigQuery to OpenSearch migration failed: {str(e)}",
                migration_id=migration_id,
                errors=[str(e)],
                duration_seconds=duration
            )
    
    async def migrate_pubsub_to_eventbridge(self, 
                                          topic_config: Dict[str, Any],
                                          migration_id: str) -> MigrationResult:
        """
        Migrate Pub/Sub topics to EventBridge with subscription mapping.
        
        Args:
            topic_config: Pub/Sub topic configuration
            migration_id: Migration identifier
            
        Returns:
            Migration result
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Pub/Sub to EventBridge migration: {topic_config.get('topic_name')}")
            
            # Use circuit breaker for infrastructure migration
            async def _migrate_events():
                # Create EventBridge event bus via A2A
                bus_response = await self.a2a_client.send_request(
                    recipient_id="aws_eventbridge_service",
                    action="create_event_bus",
                    data={
                        "bus_name": f"{topic_config.get('topic_name', 'events')}-{migration_id}",
                        "region": topic_config.get("target_region", "us-east-1"),
                        "migration_id": migration_id
                    }
                )
                
                if not bus_response.get("success"):
                    raise ServiceUnavailableError(f"EventBridge bus creation failed: {bus_response.get('error')}")
                
                bus_name = bus_response.get("bus_name")
                
                # Migrate subscriptions to EventBridge rules
                subscriptions = topic_config.get("subscriptions", [])
                rules_created = []
                
                for subscription in subscriptions:
                    rule_response = await self.a2a_client.send_request(
                        recipient_id="aws_eventbridge_service",
                        action="create_rule",
                        data={
                            "bus_name": bus_name,
                            "rule_name": f"{subscription}-rule",
                            "event_pattern": self._convert_pubsub_to_eventbridge_pattern(subscription),
                            "targets": self._convert_pubsub_targets(subscription),
                            "migration_id": migration_id
                        }
                    )
                    
                    if rule_response.get("success"):
                        rules_created.append(rule_response.get("rule_name"))
                    else:
                        logger.warning(f"Failed to create rule for subscription {subscription}: {rule_response.get('error')}")
                
                return {
                    "bus_name": bus_name,
                    "rules_created": rules_created,
                    "subscriptions_migrated": len(rules_created)
                }
            
            # Execute with circuit breaker
            result = await self.circuit_breakers["aws_services"].execute(_migrate_events)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return MigrationResult(
                success=True,
                step=MigrationStep.MIGRATE_INFRASTRUCTURE,
                status=MigrationStatus.COMPLETED,
                message=f"Pub/Sub to EventBridge migration completed successfully",
                migration_id=migration_id,
                services_migrated=result.get("subscriptions_migrated", 0),
                resources_created=1 + len(result.get("rules_created", [])),
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Pub/Sub to EventBridge migration failed: {e}")
            
            return MigrationResult(
                success=False,
                step=MigrationStep.MIGRATE_INFRASTRUCTURE,
                status=MigrationStatus.FAILED,
                message=f"Pub/Sub to EventBridge migration failed: {str(e)}",
                migration_id=migration_id,
                errors=[str(e)],
                duration_seconds=duration
            )
    
    async def migrate_cloud_run_to_lambda(self, 
                                        service_config: Dict[str, Any],
                                        migration_id: str) -> MigrationResult:
        """
        Migrate Cloud Run service to AWS Lambda with configuration mapping.
        
        Args:
            service_config: Cloud Run service configuration
            migration_id: Migration identifier
            
        Returns:
            Migration result
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Cloud Run to Lambda migration: {service_config.get('service_name')}")
            
            # Use circuit breaker for service migration
            async def _migrate_service():
                # Extract Cloud Run service configuration via A2A
                extract_response = await self.a2a_client.send_request(
                    recipient_id="gcp_compute_service",
                    action="extract_cloud_run_config",
                    data={
                        "project_id": service_config.get("project_id"),
                        "service_name": service_config.get("service_name"),
                        "region": service_config.get("region"),
                        "migration_id": migration_id
                    }
                )
                
                if not extract_response.get("success"):
                    raise ServiceUnavailableError(f"Cloud Run extraction failed: {extract_response.get('error')}")
                
                cloud_run_config = extract_response.get("config", {})
                
                # Transform configuration for Lambda
                lambda_config = await self._transform_cloud_run_to_lambda(cloud_run_config, service_config)
                
                # Create Lambda function via compute facade
                lambda_response = await self.compute.create_function(
                    function_name=lambda_config.get("function_name"),
                    runtime=lambda_config.get("runtime", "python3.9"),
                    handler=lambda_config.get("handler", "lambda_function.lambda_handler"),
                    code=lambda_config.get("code"),
                    environment=lambda_config.get("environment", {}),
                    memory_size=lambda_config.get("memory_size", 512),
                    timeout=lambda_config.get("timeout", 300)
                )
                
                if not lambda_response.get("success"):
                    raise ServiceUnavailableError(f"Lambda creation failed: {lambda_response.get('error')}")
                
                function_arn = lambda_response.get("function_arn")
                
                # Create API Gateway integration if needed
                api_gateway_response = None
                if service_config.get("create_api_gateway", True):
                    api_gateway_response = await self._create_api_gateway_integration(
                        function_arn, service_config, migration_id
                    )
                
                return {
                    "function_arn": function_arn,
                    "function_name": lambda_config.get("function_name"),
                    "api_gateway_created": api_gateway_response.get("success", False) if api_gateway_response else False
                }
            
            # Execute with circuit breaker
            result = await self.circuit_breakers["aws_services"].execute(_migrate_service)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return MigrationResult(
                success=True,
                step=MigrationStep.MIGRATE_SERVICES,
                status=MigrationStatus.COMPLETED,
                message=f"Cloud Run to Lambda migration completed successfully",
                migration_id=migration_id,
                services_migrated=1,
                resources_created=2 if result.get("api_gateway_created") else 1,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Cloud Run to Lambda migration failed: {e}")
            
            return MigrationResult(
                success=False,
                step=MigrationStep.MIGRATE_SERVICES,
                status=MigrationStatus.FAILED,
                message=f"Cloud Run to Lambda migration failed: {str(e)}",
                migration_id=migration_id,
                errors=[str(e)],
                duration_seconds=duration
            )
    
    # HELPER METHODS FOR DATA TRANSFORMATION
    
    async def _transform_bigquery_to_opensearch(self, 
                                              data: List[Dict[str, Any]], 
                                              config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform BigQuery data for OpenSearch indexing."""
        transformed_data = []
        
        for record in data:
            # Add OpenSearch-specific fields
            opensearch_record = {
                "_index": config.get("target_index", "migrated-data"),
                "_type": "_doc",
                "_id": record.get("id", f"record_{len(transformed_data)}"),
                **record
            }
            
            # Convert BigQuery timestamp format to ISO format
            if "timestamp" in record:
                try:
                    # Assume BigQuery timestamp is in microseconds
                    timestamp_ms = int(record["timestamp"]) / 1000
                    opensearch_record["@timestamp"] = datetime.fromtimestamp(timestamp_ms).isoformat()
                except (ValueError, TypeError):
                    opensearch_record["@timestamp"] = datetime.utcnow().isoformat()
            
            transformed_data.append(opensearch_record)
        
        return transformed_data
    
    def _generate_opensearch_mapping(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate OpenSearch index mapping from sample data."""
        if not data:
            return {"mappings": {"properties": {}}}
        
        # Analyze first few records to infer field types
        sample_record = data[0]
        properties = {}
        
        for field, value in sample_record.items():
            if field.startswith("_"):
                continue  # Skip OpenSearch internal fields
                
            if isinstance(value, str):
                if field in ["timestamp", "@timestamp"] or "time" in field.lower():
                    properties[field] = {"type": "date"}
                else:
                    properties[field] = {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
            elif isinstance(value, int):
                properties[field] = {"type": "long"}
            elif isinstance(value, float):
                properties[field] = {"type": "double"}
            elif isinstance(value, bool):
                properties[field] = {"type": "boolean"}
            else:
                properties[field] = {"type": "text"}
        
        return {
            "mappings": {
                "properties": properties
            }
        }
    
    def _convert_pubsub_to_eventbridge_pattern(self, subscription: str) -> Dict[str, Any]:
        """Convert Pub/Sub subscription to EventBridge event pattern."""
        # Basic conversion - in real implementation, would analyze subscription filters
        return {
            "source": ["custom.application"],
            "detail-type": [f"{subscription}-event"],
            "detail": {
                "subscription": [subscription]
            }
        }
    
    def _convert_pubsub_targets(self, subscription: str) -> List[Dict[str, Any]]:
        """Convert Pub/Sub subscription targets to EventBridge targets."""
        # Basic conversion - would map to actual Lambda functions or other targets
        return [
            {
                "Id": f"{subscription}-target",
                "Arn": f"arn:aws:lambda:us-east-1:123456789012:function:{subscription}-processor",
                "InputTransformer": {
                    "InputPathsMap": {
                        "detail": "$.detail"
                    },
                    "InputTemplate": '{"subscription": "<subscription>", "data": <detail>}'
                }
            }
        ]
    
    async def _transform_cloud_run_to_lambda(self, 
                                           cloud_run_config: Dict[str, Any], 
                                           service_config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Cloud Run configuration to Lambda configuration."""
        service_name = service_config.get("service_name", "unknown-service")
        
        # Extract memory and CPU settings
        memory_mb = 512  # Default
        if "resources" in cloud_run_config:
            memory_str = cloud_run_config["resources"].get("memory", "512Mi")
            if memory_str.endswith("Mi"):
                memory_mb = int(memory_str[:-2])
            elif memory_str.endswith("Gi"):
                memory_mb = int(memory_str[:-2]) * 1024
        
        # Convert timeout (Cloud Run uses seconds, Lambda uses seconds too)
        timeout = min(cloud_run_config.get("timeout", 300), 900)  # Lambda max is 15 minutes
        
        # Extract environment variables
        environment = {}
        if "env" in cloud_run_config:
            for env_var in cloud_run_config["env"]:
                environment[env_var.get("name", "")] = env_var.get("value", "")
        
        return {
            "function_name": f"migrated-{service_name}",
            "runtime": "python3.9",  # Default runtime
            "handler": "lambda_function.lambda_handler",
            "code": await self._extract_and_transform_code(cloud_run_config, service_config),
            "environment": environment,
            "memory_size": min(memory_mb, 10240),  # Lambda max is 10GB
            "timeout": timeout
        }
    
    async def _extract_and_transform_code(self, 
                                        cloud_run_config: Dict[str, Any], 
                                        service_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and transform Cloud Run code for Lambda deployment."""
        # In a real implementation, this would:
        # 1. Download the container image
        # 2. Extract the application code
        # 3. Transform the code for Lambda (add lambda_handler, etc.)
        # 4. Package as deployment package
        
        # For now, return a mock code package
        return {
            "ZipFile": b"# Migrated Lambda function\ndef lambda_handler(event, context):\n    return {'statusCode': 200, 'body': 'Hello from migrated service!'}"
        }
    
    async def _create_api_gateway_integration(self, 
                                            function_arn: str, 
                                            service_config: Dict[str, Any], 
                                            migration_id: str) -> Dict[str, Any]:
        """Create API Gateway integration for Lambda function."""
        try:
            # Create API Gateway via A2A
            api_response = await self.a2a_client.send_request(
                recipient_id="aws_api_gateway_service",
                action="create_rest_api",
                data={
                    "api_name": f"migrated-{service_config.get('service_name', 'service')}-api",
                    "description": f"Migrated API for {service_config.get('service_name')}",
                    "migration_id": migration_id
                }
            )
            
            if not api_response.get("success"):
                return {"success": False, "error": api_response.get("error")}
            
            api_id = api_response.get("api_id")
            
            # Create Lambda integration
            integration_response = await self.a2a_client.send_request(
                recipient_id="aws_api_gateway_service",
                action="create_lambda_integration",
                data={
                    "api_id": api_id,
                    "function_arn": function_arn,
                    "http_method": "ANY",
                    "resource_path": "/{proxy+}",
                    "migration_id": migration_id
                }
            )
            
            return {
                "success": integration_response.get("success", False),
                "api_id": api_id,
                "api_url": integration_response.get("api_url")
            }
            
        except Exception as e:
            logger.error(f"API Gateway integration failed: {e}")
            return {"success": False, "error": str(e)}
    
    # A2A MESSAGE HANDLERS
    
    async def _handle_start_migration(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start migration A2A message."""
        try:
            payload = message.get("payload", {})
            config_data = payload.get("config")
            
            if not config_data:
                return {"success": False, "error": "Missing migration config"}
            
            # Create migration config from data
            config = MigrationConfig(**config_data)
            
            # Start migration process
            result = await self.start_comprehensive_migration(config)
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"Error handling start migration: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_get_migration_status(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get migration status A2A message."""
        try:
            payload = message.get("payload", {})
            migration_id = payload.get("migration_id")
            
            return await self.get_migration_status(migration_id)
            
        except Exception as e:
            logger.error(f"Error handling get migration status: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_rollback_migration(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rollback migration A2A message."""
        try:
            payload = message.get("payload", {})
            migration_id = payload.get("migration_id")
            
            if not migration_id:
                return {"success": False, "error": "Missing migration_id"}
            
            result = await self.rollback_migration(migration_id)
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"Error handling rollback migration: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_validate_migration(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle validate migration A2A message."""
        try:
            payload = message.get("payload", {})
            migration_id = payload.get("migration_id")
            
            if not migration_id:
                return {"success": False, "error": "Missing migration_id"}
            
            result = await self.validate_migration(migration_id)
            return result
            
        except Exception as e:
            logger.error(f"Error handling validate migration: {e}")
            return {"success": False, "error": str(e)}
    
    # COMPREHENSIVE MIGRATION ORCHESTRATION
    
    async def start_comprehensive_migration(self, config: MigrationConfig) -> MigrationResult:
        """
        Start comprehensive GCP to AWS migration process.
        
        Args:
            config: Migration configuration
            
        Returns:
            Overall migration result
        """
        if not self.is_initialized:
            return MigrationResult(
                success=False,
                step=MigrationStep.VALIDATE_SOURCE,
                status=MigrationStatus.FAILED,
                message="GCP to AWS Migrator not initialized",
                migration_id=config.migration_id
            )
        
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting comprehensive GCP to AWS migration: {config.migration_id}")
            
            # Store migration configuration
            await self.database.store_data({
                "migration_id": config.migration_id,
                "config": asdict(config),
                "status": MigrationStatus.IN_PROGRESS.value,
                "started_at": datetime.utcnow().isoformat()
            }, "migration_config")
            
            # Add to active migrations
            self.active_migrations[config.migration_id] = config
            
            # Execute migration steps based on resource mappings
            step_results = []
            total_data_migrated = 0
            total_services_migrated = 0
            total_resources_created = 0
            
            # Sort resource mappings by priority
            sorted_mappings = sorted(config.resource_mappings, key=lambda x: x.migration_priority)
            
            for mapping in sorted_mappings:
                try:
                    if mapping.gcp_type == ResourceType.BIGQUERY and mapping.aws_type == ResourceType.OPENSEARCH:
                        result = await self.migrate_bigquery_to_opensearch(mapping.gcp_config, config.migration_id)
                    elif mapping.gcp_type == ResourceType.PUBSUB and mapping.aws_type == ResourceType.EVENTBRIDGE:
                        result = await self.migrate_pubsub_to_eventbridge(mapping.gcp_config, config.migration_id)
                    elif mapping.gcp_type == ResourceType.CLOUD_RUN and mapping.aws_type == ResourceType.LAMBDA:
                        result = await self.migrate_cloud_run_to_lambda(mapping.gcp_config, config.migration_id)
                    else:
                        logger.warning(f"Unsupported migration mapping: {mapping.gcp_type} -> {mapping.aws_type}")
                        continue
                    
                    step_results.append(result.to_dict())
                    
                    if result.success:
                        total_data_migrated += result.data_migrated
                        total_services_migrated += result.services_migrated
                        total_resources_created += result.resources_created
                    else:
                        if config.rollback_on_failure:
                            logger.warning(f"Migration step failed, initiating rollback: {result.message}")
                            await self.rollback_migration(config.migration_id)
                            break
                        
                except Exception as e:
                    logger.error(f"Migration step failed: {e}")
                    step_results.append({
                        "success": False,
                        "error": str(e),
                        "step": f"migrate_{mapping.gcp_type.value}_to_{mapping.aws_type.value}"
                    })
                    
                    if config.rollback_on_failure:
                        await self.rollback_migration(config.migration_id)
                        break
            
            # Determine overall success
            successful_steps = sum(1 for r in step_results if r.get("success", False))
            total_steps = len(step_results)
            overall_success = successful_steps == total_steps and total_steps > 0
            
            # Update migration status
            final_status = MigrationStatus.COMPLETED if overall_success else MigrationStatus.FAILED
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            migration_summary = {
                "migration_id": config.migration_id,
                "status": final_status.value,
                "step_results": step_results,
                "total_data_migrated": total_data_migrated,
                "total_services_migrated": total_services_migrated,
                "total_resources_created": total_resources_created,
                "successful_steps": successful_steps,
                "total_steps": total_steps,
                "duration_seconds": duration,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            await self.database.store_data(migration_summary, "migration_result")
            
            # Add to migration history
            self.migration_history.append(migration_summary)
            
            # Remove from active migrations
            if config.migration_id in self.active_migrations:
                del self.active_migrations[config.migration_id]
            
            return MigrationResult(
                success=overall_success,
                step=MigrationStep.VALIDATE_MIGRATION,
                status=final_status,
                message=f"Comprehensive migration {'completed successfully' if overall_success else 'failed'}",
                migration_id=config.migration_id,
                data_migrated=total_data_migrated,
                services_migrated=total_services_migrated,
                resources_created=total_resources_created,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Comprehensive migration orchestration error: {e}")
            
            # Remove from active migrations
            if config.migration_id in self.active_migrations:
                del self.active_migrations[config.migration_id]
            
            return MigrationResult(
                success=False,
                step=MigrationStep.VALIDATE_SOURCE,
                status=MigrationStatus.FAILED,
                message=f"Migration orchestration error: {str(e)}",
                migration_id=config.migration_id,
                errors=[str(e)],
                duration_seconds=duration
            )
    
    async def get_migration_status(self, migration_id: Optional[str] = None) -> Dict[str, Any]:
        """Get migration status."""
        try:
            if migration_id:
                # Get specific migration status
                migration_data = await self.database.query_data({
                    "migration_id": migration_id
                })
                
                if migration_data:
                    return {
                        "success": True,
                        "migration_id": migration_id,
                        "status": migration_data[0],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Migration not found: {migration_id}"
                    }
            else:
                # Get all migration statuses
                return {
                    "success": True,
                    "active_migrations": list(self.active_migrations.keys()),
                    "migration_history": self.migration_history[-10:],  # Last 10 migrations
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Get migration status error: {e}")
            return {"success": False, "error": str(e)}
    
    async def rollback_migration(self, migration_id: str) -> MigrationResult:
        """Rollback migration in case of failure."""
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Rolling back migration: {migration_id}")
            
            # Send rollback request via A2A
            response = await self.a2a_client.send_request(
                recipient_id="migration_rollback_service",
                action="rollback_migration",
                data={"migration_id": migration_id}
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if response.get("success"):
                return MigrationResult(
                    success=True,
                    step=MigrationStep.CLEANUP_SOURCE,
                    status=MigrationStatus.ROLLED_BACK,
                    message="Migration rollback completed successfully",
                    migration_id=migration_id,
                    duration_seconds=duration
                )
            else:
                return MigrationResult(
                    success=False,
                    step=MigrationStep.CLEANUP_SOURCE,
                    status=MigrationStatus.FAILED,
                    message=f"Migration rollback failed: {response.get('error', 'Unknown error')}",
                    migration_id=migration_id,
                    errors=[response.get('error', 'Unknown error')],
                    duration_seconds=duration
                )
                
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Migration rollback error: {e}")
            
            return MigrationResult(
                success=False,
                step=MigrationStep.CLEANUP_SOURCE,
                status=MigrationStatus.FAILED,
                message=f"Migration rollback error: {str(e)}",
                migration_id=migration_id,
                errors=[str(e)],
                duration_seconds=duration
            )
    
    async def validate_migration(self, migration_id: str) -> Dict[str, Any]:
        """Validate migration results and data integrity."""
        try:
            logger.info(f"Validating migration: {migration_id}")
            
            # Find migration in history
            migration_result = None
            for result in self.migration_history:
                if result.get("migration_id") == migration_id:
                    migration_result = result
                    break
            
            if not migration_result:
                return {"success": False, "error": "Migration not found"}
            
            # Send validation request via A2A
            response = await self.a2a_client.send_request(
                recipient_id="migration_validation_service",
                action="validate_migration_integrity",
                data={
                    "migration_id": migration_id,
                    "migration_result": migration_result
                }
            )
            
            if response.get("success"):
                validation_score = response.get("validation_score", 0.0)
                return {
                    "success": True,
                    "migration_id": migration_id,
                    "validation_score": validation_score,
                    "validation_passed": validation_score >= 0.8,
                    "validation_details": response.get("details", {}),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Migration validation failed: {response.get('error', 'Unknown error')}"
                }
                
        except Exception as e:
            logger.error(f"Migration validation error: {e}")
            return {"success": False, "error": str(e)}


# FACTORY FUNCTIONS AND UTILITIES

def create_gcp_to_aws_migrator(agent_id: str = "gcp_aws_migrator",
                              tenant_id: Optional[str] = None) -> GCPToAWSMigrator:
    """
    Factory function to create GCP to AWS Migrator.
    
    Args:
        agent_id: Migrator agent ID
        tenant_id: Tenant ID for multi-tenant deployments
        
    Returns:
        Configured GCPToAWSMigrator instance
    """
    return GCPToAWSMigrator(agent_id, tenant_id)


def create_felicia_finance_migration_config(
    migration_id: str,
    gcp_project_id: str,
    aws_account_id: str,
    gcp_region: str = "us-central1",
    aws_region: str = "us-east-1"
) -> MigrationConfig:
    """
    Create migration configuration for Felicia's Finance modules.
    
    Args:
        migration_id: Unique migration identifier
        gcp_project_id: GCP project ID
        aws_account_id: AWS account ID
        gcp_region: GCP region
        aws_region: AWS region
        
    Returns:
        MigrationConfig for Felicia's Finance
    """
    resource_mappings = [
        # Crypto BigQuery to OpenSearch
        ResourceMapping(
            gcp_type=ResourceType.BIGQUERY,
            aws_type=ResourceType.OPENSEARCH,
            gcp_config={
                "project_id": gcp_project_id,
                "dataset_id": "crypto_analytics_dataset",
                "tables": ["trading_data", "market_data", "portfolio_snapshots"],
                "region": gcp_region
            },
            aws_config={
                "domain_name": "crypto-analytics-search",
                "instance_type": "t3.small.search",
                "instance_count": 1,
                "region": aws_region
            },
            migration_priority=1
        ),
        
        # Bank BigQuery to OpenSearch
        ResourceMapping(
            gcp_type=ResourceType.BIGQUERY,
            aws_type=ResourceType.OPENSEARCH,
            gcp_config={
                "project_id": gcp_project_id,
                "dataset_id": "bank_of_anthos_dataset",
                "tables": ["transactions", "accounts", "users", "balances"],
                "region": gcp_region
            },
            aws_config={
                "domain_name": "bank-analytics-search",
                "instance_type": "t3.small.search",
                "instance_count": 1,
                "region": aws_region
            },
            migration_priority=1
        ),
        
        # Crypto Pub/Sub to EventBridge
        ResourceMapping(
            gcp_type=ResourceType.PUBSUB,
            aws_type=ResourceType.EVENTBRIDGE,
            gcp_config={
                "project_id": gcp_project_id,
                "topic_name": "crypto_events_topic",
                "subscriptions": ["trading-processor", "risk-monitor", "portfolio-updater"],
                "region": gcp_region
            },
            aws_config={
                "bus_name": "crypto-events-bus",
                "region": aws_region
            },
            migration_priority=2
        ),
        
        # Bank Pub/Sub to EventBridge
        ResourceMapping(
            gcp_type=ResourceType.PUBSUB,
            aws_type=ResourceType.EVENTBRIDGE,
            gcp_config={
                "project_id": gcp_project_id,
                "topic_name": "bank_events_topic",
                "subscriptions": ["transaction-processor", "balance-updater", "notification-sender"],
                "region": gcp_region
            },
            aws_config={
                "bus_name": "bank-events-bus",
                "region": aws_region
            },
            migration_priority=2
        ),
        
        # Crypto Cloud Run to Lambda
        ResourceMapping(
            gcp_type=ResourceType.CLOUD_RUN,
            aws_type=ResourceType.LAMBDA,
            gcp_config={
                "project_id": gcp_project_id,
                "service_name": "crypto_trading_service",
                "region": gcp_region
            },
            aws_config={
                "function_name": "crypto-trading-function",
                "runtime": "python3.9",
                "region": aws_region
            },
            migration_priority=3
        ),
        
        # Bank Cloud Run to Lambda
        ResourceMapping(
            gcp_type=ResourceType.CLOUD_RUN,
            aws_type=ResourceType.LAMBDA,
            gcp_config={
                "project_id": gcp_project_id,
                "service_name": "bank_transaction_service",
                "region": gcp_region
            },
            aws_config={
                "function_name": "bank-transaction-function",
                "runtime": "python3.9",
                "region": aws_region
            },
            migration_priority=3
        )
    ]
    
    return MigrationConfig(
        migration_id=migration_id,
        source_project_id=gcp_project_id,
        target_account_id=aws_account_id,
        source_region=gcp_region,
        target_region=aws_region,
        resource_mappings=resource_mappings,
        preserve_data=True,
        validate_integrity=True,
        cleanup_source=False,
        rollback_on_failure=True,
        dry_run=False
    )


# Global migrator instance
_global_migrator: Optional[GCPToAWSMigrator] = None


async def get_global_migrator(agent_id: str = "gcp_aws_migrator",
                             tenant_id: Optional[str] = None) -> GCPToAWSMigrator:
    """Get or create the global GCP to AWS migrator instance."""
    global _global_migrator
    
    if _global_migrator is None:
        _global_migrator = create_gcp_to_aws_migrator(agent_id, tenant_id)
        
        if not _global_migrator.is_initialized:
            await _global_migrator.initialize()
    
    return _global_migrator


async def shutdown_global_migrator():
    """Shutdown the global GCP to AWS migrator instance."""
    global _global_migrator
    
    if _global_migrator:
        await _global_migrator.shutdown()
        _global_migrator = None