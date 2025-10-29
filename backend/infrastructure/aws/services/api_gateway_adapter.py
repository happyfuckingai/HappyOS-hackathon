"""
AWS API Gateway service adapter for request routing and throttling.
This adapter provides API management capabilities using AWS API Gateway.
"""

import json
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError


class AWSAPIGatewayAdapter:
    """AWS API Gateway implementation for request routing and management."""
    
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize AWS API Gateway adapter."""
        self.region_name = region_name
        self.apigateway_client = boto3.client('apigateway', region_name=region_name)
        self.apigatewayv2_client = boto3.client('apigatewayv2', region_name=region_name)
        
        # Tenant-specific API configurations
        self.tenant_apis = {
            'meetmind': {'api_id': None, 'stage': 'prod'},
            'agent_svea': {'api_id': None, 'stage': 'prod'},
            'felicias_finance': {'api_id': None, 'stage': 'prod'}
        }
    
    def _get_tenant_api_id(self, tenant_id: str) -> Optional[str]:
        """Get API Gateway ID for a tenant."""
        return self.tenant_apis.get(tenant_id, {}).get('api_id')
    
    async def create_api(self, tenant_id: str, api_name: str, description: str = None) -> Optional[str]:
        """Create a new API Gateway for a tenant."""
        try:
            response = self.apigatewayv2_client.create_api(
                Name=f"{tenant_id}-{api_name}",
                Description=description or f"API for {tenant_id}",
                ProtocolType='HTTP',
                CorsConfiguration={
                    'AllowCredentials': True,
                    'AllowHeaders': ['*'],
                    'AllowMethods': ['*'],
                    'AllowOrigins': ['*'],
                    'MaxAge': 86400
                }
            )
            
            api_id = response['ApiId']
            
            # Store API ID for tenant
            if tenant_id in self.tenant_apis:
                self.tenant_apis[tenant_id]['api_id'] = api_id
            
            return api_id
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error creating API Gateway: {e}")
            return None
    
    async def create_route(self, tenant_id: str, route_key: str, target: str, 
                          authorization_type: str = "NONE") -> bool:
        """Create a route in the tenant's API Gateway."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                print(f"No API Gateway found for tenant: {tenant_id}")
                return False
            
            # Create integration first
            integration_response = self.apigatewayv2_client.create_integration(
                ApiId=api_id,
                IntegrationType='HTTP_PROXY',
                IntegrationUri=target,
                PayloadFormatVersion='2.0'
            )
            
            integration_id = integration_response['IntegrationId']
            
            # Create route
            self.apigatewayv2_client.create_route(
                ApiId=api_id,
                RouteKey=route_key,
                Target=f"integrations/{integration_id}",
                AuthorizationType=authorization_type
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error creating route: {e}")
            return False
    
    async def deploy_api(self, tenant_id: str, stage_name: str = "prod") -> bool:
        """Deploy API Gateway to a stage."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                return False
            
            # Create or update stage
            try:
                self.apigatewayv2_client.create_stage(
                    ApiId=api_id,
                    StageName=stage_name,
                    AutoDeploy=True
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConflictException':
                    # Stage already exists, update it
                    self.apigatewayv2_client.update_stage(
                        ApiId=api_id,
                        StageName=stage_name,
                        AutoDeploy=True
                    )
                else:
                    raise
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error deploying API: {e}")
            return False
    
    async def get_api_url(self, tenant_id: str, stage_name: str = "prod") -> Optional[str]:
        """Get the API Gateway URL for a tenant."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                return None
            
            return f"https://{api_id}.execute-api.{self.region_name}.amazonaws.com/{stage_name}"
            
        except Exception as e:
            print(f"Error getting API URL: {e}")
            return None
    
    async def set_throttling(self, tenant_id: str, rate_limit: int, burst_limit: int) -> bool:
        """Set throttling limits for a tenant's API."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                return False
            
            stage_name = self.tenant_apis[tenant_id]['stage']
            
            # Update stage throttling
            self.apigatewayv2_client.update_stage(
                ApiId=api_id,
                StageName=stage_name,
                ThrottleSettings={
                    'RateLimit': rate_limit,
                    'BurstLimit': burst_limit
                }
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error setting throttling: {e}")
            return False
    
    async def get_api_metrics(self, tenant_id: str, start_time: str, end_time: str) -> Optional[Dict[str, Any]]:
        """Get API Gateway metrics for a tenant."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                return None
            
            # Use CloudWatch to get metrics
            cloudwatch = boto3.client('cloudwatch', region_name=self.region_name)
            
            metrics = {}
            
            # Get request count
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Count',
                Dimensions=[
                    {'Name': 'ApiId', 'Value': api_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour
                Statistics=['Sum']
            )
            
            metrics['request_count'] = sum(point['Sum'] for point in response['Datapoints'])
            
            # Get latency
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Latency',
                Dimensions=[
                    {'Name': 'ApiId', 'Value': api_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                metrics['average_latency'] = sum(point['Average'] for point in response['Datapoints']) / len(response['Datapoints'])
            else:
                metrics['average_latency'] = 0
            
            # Get error count
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='4XXError',
                Dimensions=[
                    {'Name': 'ApiId', 'Value': api_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            metrics['4xx_errors'] = sum(point['Sum'] for point in response['Datapoints'])
            
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='5XXError',
                Dimensions=[
                    {'Name': 'ApiId', 'Value': api_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            metrics['5xx_errors'] = sum(point['Sum'] for point in response['Datapoints'])
            
            return metrics
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting API metrics: {e}")
            return None
    
    async def list_apis(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """List API Gateways, optionally filtered by tenant."""
        try:
            response = self.apigatewayv2_client.get_apis()
            
            apis = []
            for api in response['Items']:
                api_info = {
                    'api_id': api['ApiId'],
                    'name': api['Name'],
                    'protocol': api['ProtocolType'],
                    'created_date': api['CreatedDate'].isoformat(),
                    'api_endpoint': api.get('ApiEndpoint', ''),
                    'description': api.get('Description', '')
                }
                
                # Filter by tenant if specified
                if tenant_id:
                    if api['Name'].startswith(f"{tenant_id}-"):
                        apis.append(api_info)
                else:
                    apis.append(api_info)
            
            return apis
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error listing APIs: {e}")
            return []
    
    async def delete_api(self, tenant_id: str) -> bool:
        """Delete API Gateway for a tenant."""
        try:
            api_id = self._get_tenant_api_id(tenant_id)
            if not api_id:
                return False
            
            self.apigatewayv2_client.delete_api(ApiId=api_id)
            
            # Clear from tenant APIs
            if tenant_id in self.tenant_apis:
                self.tenant_apis[tenant_id]['api_id'] = None
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error deleting API: {e}")
            return False