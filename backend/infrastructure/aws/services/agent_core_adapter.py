"""
AWS Agent Core service adapter for memory and runtime management.
This adapter interfaces with AWS services to provide agent memory and session management.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import AgentCoreService, AgentSession
from backend.infrastructure.aws.retry_policies import aws_resilient, execute_aws_operation


class AWSAgentCoreAdapter(AgentCoreService):
    """AWS implementation of Agent Core service using DynamoDB and Lambda."""
    
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize AWS Agent Core adapter."""
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.lambda_client = boto3.client('lambda', region_name=region_name)
        
        # Table names - these should be configurable
        self.memory_table_name = "agent-memory"
        self.sessions_table_name = "agent-sessions"
        
        # Initialize tables
        self._memory_table = None
        self._sessions_table = None
    
    @property
    def memory_table(self):
        """Lazy load memory table."""
        if self._memory_table is None:
            self._memory_table = self.dynamodb.Table(self.memory_table_name)
        return self._memory_table
    
    @property
    def sessions_table(self):
        """Lazy load sessions table."""
        if self._sessions_table is None:
            self._sessions_table = self.dynamodb.Table(self.sessions_table_name)
        return self._sessions_table
    
    def _get_memory_key(self, user_id: str, key: str, tenant_id: str) -> str:
        """Generate tenant-isolated memory key."""
        return f"{tenant_id}#{user_id}#{key}"
    
    def _get_session_key(self, session_id: str, tenant_id: str) -> str:
        """Generate tenant-isolated session key."""
        return f"{tenant_id}#{session_id}"
    
    async def put_memory(self, user_id: str, key: str, value: Any, tenant_id: str) -> bool:
        """Store memory data for a user within a tenant context."""
        async def _put_operation():
            memory_key = self._get_memory_key(user_id, key, tenant_id)
            
            item = {
                'memory_key': memory_key,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'key': key,
                'value': json.dumps(value) if not isinstance(value, str) else value,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.memory_table.put_item(Item=item)
            return True
        
        try:
            return await execute_aws_operation('dynamodb', _put_operation)
        except Exception as e:
            print(f"Error storing memory: {e}")
            return False
    
    async def get_memory(self, user_id: str, key: str, tenant_id: str) -> Any:
        """Retrieve memory data for a user within a tenant context."""
        try:
            memory_key = self._get_memory_key(user_id, key, tenant_id)
            
            response = self.memory_table.get_item(
                Key={'memory_key': memory_key}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            value = item['value']
            
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except (ClientError, BotoCoreError) as e:
            print(f"Error retrieving memory: {e}")
            return None
    
    async def create_session(self, tenant_id: str, agent_id: str, user_id: str, config: Dict[str, Any]) -> str:
        """Create a new agent session."""
        try:
            session_id = str(uuid.uuid4())
            session_key = self._get_session_key(session_id, tenant_id)
            
            session_data = {
                'session_key': session_key,
                'session_id': session_id,
                'tenant_id': tenant_id,
                'agent_id': agent_id,
                'user_id': user_id,
                'status': 'active',
                'memory_context': {},
                'configuration': config,
                'created_at': datetime.utcnow().isoformat(),
                'last_activity': datetime.utcnow().isoformat()
            }
            
            self.sessions_table.put_item(Item=session_data)
            return session_id
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error creating session: {e}")
            raise
    
    async def get_session(self, session_id: str, tenant_id: str) -> Optional[AgentSession]:
        """Retrieve an agent session."""
        try:
            session_key = self._get_session_key(session_id, tenant_id)
            
            response = self.sessions_table.get_item(
                Key={'session_key': session_key}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            
            return AgentSession(
                session_id=item['session_id'],
                tenant_id=item['tenant_id'],
                agent_id=item['agent_id'],
                user_id=item['user_id'],
                created_at=datetime.fromisoformat(item['created_at']),
                last_activity=datetime.fromisoformat(item['last_activity']),
                status=item['status'],
                memory_context=item.get('memory_context', {}),
                configuration=item.get('configuration', {})
            )
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error retrieving session: {e}")
            return None
    
    async def update_session(self, session_id: str, tenant_id: str, updates: Dict[str, Any]) -> bool:
        """Update an agent session."""
        try:
            session_key = self._get_session_key(session_id, tenant_id)
            
            # Build update expression
            update_expression = "SET last_activity = :last_activity"
            expression_values = {
                ':last_activity': datetime.utcnow().isoformat()
            }
            
            for key, value in updates.items():
                if key in ['status', 'memory_context', 'configuration']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value
            
            self.sessions_table.update_item(
                Key={'session_key': session_key},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error updating session: {e}")
            return False
    
    async def delete_session(self, session_id: str, tenant_id: str) -> bool:
        """Delete an agent session."""
        try:
            session_key = self._get_session_key(session_id, tenant_id)
            
            self.sessions_table.delete_item(
                Key={'session_key': session_key}
            )
            
            return True
            
        except (ClientError, BotoCoreError) as e:
            print(f"Error deleting session: {e}")
            return False