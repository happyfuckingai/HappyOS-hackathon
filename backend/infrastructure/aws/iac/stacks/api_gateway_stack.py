"""
API Gateway Stack

Creates API Gateway with request routing and throttling.
"""

from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    CfnOutput
)
from constructs import Construct
from typing import Dict

from .base_stack import BaseStack
from ..config.environment_config import EnvironmentConfig


class ApiGatewayStack(BaseStack):
    """API Gateway stack with request routing and throttling."""
    
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        lambda_functions: Dict[str, lambda_.Function],
        env_config: EnvironmentConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env_config, **kwargs)
        
        self.lambda_functions = lambda_functions
        
        # Create API Gateway
        self.api = self._create_api_gateway()
        
        # Create resources and methods
        self._create_api_resources()
        
        # Create outputs
        self._create_outputs()
    
    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create REST API Gateway."""
        
        api = apigateway.RestApi(
            self,
            "InfraRecoveryApi",
            rest_api_name=self.get_resource_name("api"),
            description="Infrastructure Recovery API Gateway",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            ),
            deploy_options=apigateway.StageOptions(
                stage_name=self.env_config.environment,
                throttling_rate_limit=self.env_config.services.api_gateway_throttle_rate,
                throttling_burst_limit=self.env_config.services.api_gateway_throttle_burst,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            )
        )
        
        return api
    
    def _create_api_resources(self) -> None:
        """Create API resources and methods."""
        
        # Health check endpoint
        health_resource = self.api.root.add_resource("health")
        health_integration = apigateway.LambdaIntegration(
            self.lambda_functions["health_check"]
        )
        health_resource.add_method("GET", health_integration)
        
        # Tenant-specific endpoints
        for tenant_name in self.env_config.get_all_tenant_names():
            tenant_config = self.env_config.get_tenant_config(tenant_name)
            
            # Create tenant resource
            tenant_resource = self.api.root.add_resource(tenant_name)
            
            # Create agent endpoints for each tenant
            for agent_name in tenant_config.agents:
                agent_resource = tenant_resource.add_resource(agent_name)
                
                function_key = f"{tenant_name}_{agent_name}"
                if function_key in self.lambda_functions:
                    integration = apigateway.LambdaIntegration(
                        self.lambda_functions[function_key]
                    )
                    
                    # Add methods
                    agent_resource.add_method("POST", integration)
                    agent_resource.add_method("GET", integration)
        
        # Circuit breaker endpoint
        circuit_breaker_resource = self.api.root.add_resource("circuit-breaker")
        circuit_breaker_integration = apigateway.LambdaIntegration(
            self.lambda_functions["circuit_breaker"]
        )
        circuit_breaker_resource.add_method("GET", circuit_breaker_integration)
        circuit_breaker_resource.add_method("POST", circuit_breaker_integration)
    
    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        
        self.create_output(
            "ApiGatewayUrl",
            value=self.api.url,
            description="API Gateway URL"
        )
        
        self.create_output(
            "ApiGatewayId",
            value=self.api.rest_api_id,
            description="API Gateway ID"
        )