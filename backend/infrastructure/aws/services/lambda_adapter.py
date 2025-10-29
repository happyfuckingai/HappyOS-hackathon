"""
AWS Lambda service adapter for function invocation and compute operations.
This adapter provides compute capabilities using AWS Lambda functions.
"""

import json
import uuid
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import ComputeService


class AWSLambdaAdapter(ComputeService):
    """AWS Lambda implementation for compute operations."""
    
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize AWS Lambda adapter."""
        self.region_name = region_name
        self.lambda_client = boto3.client('lambda', region_name=region_name)
        self.stepfunctions_client = boto3.client('stepfunctions', region_name=region_name)
        
        # Function name prefixes for different tenants
        self.tenant_function_prefixes = {
            'meetmind': 'meetmind-',
            'agent_svea': 'agentsvea-',
            'felicias_finance': 'feliciasfi-'
        }
    
    def _get_function_name(self, function_name: str, tenant_id: str) -> str:
        """Generate tenant-specific function name."""
        prefix = self.tenant_function_prefixes.get(tenant_id, f"{tenant_id}-")
        if not function_name.startswith(prefix):
            return f"{prefix}{function_name}"
        return function_name
    
    def _prepare_payload(self, payload: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """Prepare payload with tenant context."""
        return {
            'tenant_id': tenant_id,
            'request_id': str(uuid.uuid4()),
            'payload': payload
        }
    
    async def invoke_function(self, function_name: str, payload: Dict[str, Any], 
                             tenant_id: str, async_mode: bool = False) -> Dict[str, Any]:
        """Invoke a compute function."""
        try:
            full_function_name = self._get_function_name(function_name, tenant_id)
            prepared_payload = self._prepare_payload(payload, tenant_id)
            
            # Determine invocation type
            invocation_type = 'Event' if async_mode else 'RequestResponse'
            
            response = self.lambda_client.invoke(
                FunctionName=full_function_name,
                InvocationType=invocation_type,
                Payload=json.dumps(prepared_payload)
            )
            
            if async_mode:
                # For async invocation, return request ID
                return {
                    'request_id': prepared_payload['request_id'],
                    'status': 'submitted',
                    'async': True
                }
            else:
                # For sync invocation, parse and return response
                response_payload = response['Payload'].read()
                
                if response['StatusCode'] == 200:
                    try:
                        result = json.loads(response_payload.decode('utf-8'))
                        return {
                            'request_id': prepared_payload['request_id'],
                            'status': 'completed',
                            'result': result,
                            'async': False
                        }
                    except json.JSONDecodeError:
                        return {
                            'request_id': prepared_payload['request_id'],
                            'status': 'completed',
                            'result': response_payload.decode('utf-8'),
                            'async': False
                        }
                else:
                    return {
                        'request_id': prepared_payload['request_id'],
                        'status': 'error',
                        'error': f"Function returned status code: {response['StatusCode']}",
                        'async': False
                    }
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error invoking Lambda function: {e}")
            return {
                'request_id': str(uuid.uuid4()),
                'status': 'error',
                'error': str(e),
                'async': async_mode
            }
    
    async def schedule_job(self, job_config: Dict[str, Any], tenant_id: str) -> str:
        """Schedule a job for execution using Step Functions."""
        try:
            # Extract job configuration
            function_name = job_config.get('function_name')
            schedule = job_config.get('schedule')  # cron expression
            payload = job_config.get('payload', {})
            
            if not function_name:
                raise ValueError("function_name is required in job_config")
            
            # Create execution input
            execution_input = {
                'tenant_id': tenant_id,
                'function_name': self._get_function_name(function_name, tenant_id),
                'payload': payload,
                'job_id': str(uuid.uuid4()),
                'schedule': schedule
            }
            
            # For now, we'll use direct execution since Step Functions state machine
            # would need to be pre-configured. In a full implementation, this would
            # create a scheduled execution.
            job_id = execution_input['job_id']
            
            # If it's a one-time job (no schedule), execute immediately
            if not schedule:
                result = await self.invoke_function(
                    function_name, payload, tenant_id, async_mode=True
                )
                return result.get('request_id', job_id)
            
            # For scheduled jobs, we would integrate with EventBridge
            # For now, return the job ID
            return job_id
            
        except Exception as e:
            print(f"Error scheduling job: {e}")
            raise
    
    async def get_job_status(self, job_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get job execution status."""
        try:
            # In a full implementation, this would query Step Functions or CloudWatch
            # For now, we'll return a basic status structure
            
            # Try to get CloudWatch logs for the job
            logs_client = boto3.client('logs', region_name=self.region_name)
            
            # This is a simplified implementation
            # In practice, you'd need to track job executions in a database
            # or use Step Functions execution ARNs
            
            return {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'status': 'unknown',  # Would be: pending, running, completed, failed
                'created_at': None,
                'started_at': None,
                'completed_at': None,
                'result': None,
                'error': None
            }
            
        except Exception as e:
            print(f"Error getting job status: {e}")
            return {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def list_functions(self, tenant_id: str) -> List[str]:
        """List available functions for a tenant."""
        try:
            prefix = self.tenant_function_prefixes.get(tenant_id, f"{tenant_id}-")
            
            response = self.lambda_client.list_functions()
            
            tenant_functions = []
            for function in response.get('Functions', []):
                function_name = function['FunctionName']
                if function_name.startswith(prefix):
                    # Remove tenant prefix for cleaner names
                    clean_name = function_name[len(prefix):]
                    tenant_functions.append(clean_name)
            
            return tenant_functions
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error listing functions: {e}")
            return []
    
    async def get_function_info(self, function_name: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific function."""
        try:
            full_function_name = self._get_function_name(function_name, tenant_id)
            
            response = self.lambda_client.get_function(
                FunctionName=full_function_name
            )
            
            config = response['Configuration']
            return {
                'function_name': function_name,
                'full_name': full_function_name,
                'runtime': config.get('Runtime'),
                'timeout': config.get('Timeout'),
                'memory_size': config.get('MemorySize'),
                'last_modified': config.get('LastModified'),
                'description': config.get('Description', ''),
                'environment': config.get('Environment', {}).get('Variables', {})
            }
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting function info: {e}")
            return None