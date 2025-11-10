"""
CAMEL Client Module

This module provides a client for interacting with the CAMEL framework API,
enabling communication with CAMEL agents and workflows.
"""

import json
import logging
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass

from app.core.camel.camel_config import camel_config, AgentRole
from app.core.error_handling.retry_manager import retry_with_backoff
from app.core.security.security import get_secure_api_key

logger = logging.getLogger(__name__)

@dataclass
class CamelResponse:
    """Response from CAMEL API."""
    success: bool
    message: str
    data: Dict[str, Any]
    status_code: int
    conversation_id: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any], status_code: int) -> 'CamelResponse':
        """
        Create a CamelResponse from an API response.
        
        Args:
            response_data: The response data from the API
            status_code: The HTTP status code
            
        Returns:
            CamelResponse object
        """
        return cls(
            success=response_data.get('success', False),
            message=response_data.get('message', ''),
            data=response_data.get('data', {}),
            status_code=status_code,
            conversation_id=response_data.get('conversation_id')
        )
    
    @classmethod
    def error(cls, message: str, status_code: int = 500) -> 'CamelResponse':
        """
        Create an error response.
        
        Args:
            message: Error message
            status_code: HTTP status code
            
        Returns:
            CamelResponse object
        """
        return cls(
            success=False,
            message=message,
            data={},
            status_code=status_code
        )

class CamelClient:
    """
    Client for interacting with the CAMEL framework API.
    
    This client provides methods for creating agents, starting conversations,
    sending messages, and managing workflows.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the CAMEL client.
        
        Args:
            base_url: Base URL for the CAMEL API
            api_key: API key for authentication
        """
        self.base_url = base_url or camel_config.base_url
        self._api_key = api_key
        self._session = None
        self.active_conversations: Dict[str, Dict[str, Any]] = {}
    
    async def _get_api_key(self) -> str:
        """
        Get the API key for authentication.
        
        Returns:
            API key as string
        """
        if self._api_key:
            return self._api_key
        
        try:
            # Try to get from secure storage
            api_key = await get_secure_api_key('camel')
            self._api_key = api_key
            return api_key
        except ValueError:
            # Fall back to configuration
            if camel_config.api_key:
                self._api_key = camel_config.api_key
                return camel_config.api_key
            
            raise ValueError("No API key available for CAMEL API")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session.
        
        Returns:
            aiohttp.ClientSession
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=10.0)
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Make a request to the CAMEL API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            
        Returns:
            CamelResponse object
        """
        session = await self._get_session()
        api_key = await self._get_api_key()
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            ) as response:
                response_data = await response.json()
                return CamelResponse.from_api_response(response_data, response.status)
        except aiohttp.ClientError as e:
            logger.error(f"Error making request to CAMEL API: {str(e)}")
            return CamelResponse.error(f"Error making request: {str(e)}")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON response from CAMEL API")
            return CamelResponse.error("Error decoding JSON response")
    
    async def create_agent(
        self, 
        role: Union[AgentRole, str],
        name: Optional[str] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        custom_parameters: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Create a new CAMEL agent.
        
        Args:
            role: Agent role
            name: Agent name
            system_message: System message for the agent
            model: LLM model to use
            temperature: Temperature for generation
            max_tokens: Maximum tokens for generation
            custom_parameters: Additional parameters
            
        Returns:
            CamelResponse with agent information
        """
        if isinstance(role, AgentRole):
            role_str = role.value
        else:
            role_str = role
        
        data = {
            "role": role_str,
            "name": name or f"{role_str}_agent",
            "system_message": system_message,
            "model": model or camel_config.default_model,
            "temperature": temperature or camel_config.default_temperature,
            "max_tokens": max_tokens or camel_config.default_max_tokens
        }
        
        if custom_parameters:
            data.update(custom_parameters)
        
        return await self._make_request("POST", "/agents", data=data)
    
    async def get_agent(self, agent_id: str) -> CamelResponse:
        """
        Get information about an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            CamelResponse with agent information
        """
        return await self._make_request("GET", f"/agents/{agent_id}")
    
    async def start_conversation(
        self,
        agents: List[str],
        initial_message: str,
        max_turns: Optional[int] = None,
        template: Optional[str] = None,
        custom_parameters: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Start a new conversation between agents.
        
        Args:
            agents: List of agent IDs
            initial_message: Initial message to start the conversation
            max_turns: Maximum number of turns
            template: Conversation template name
            custom_parameters: Additional parameters
            
        Returns:
            CamelResponse with conversation information
        """
        data = {
            "agents": agents,
            "initial_message": initial_message,
            "max_turns": max_turns or camel_config.conversation_templates.get(template, {}).get("max_turns", 10),
            "template": template
        }
        
        if custom_parameters:
            data.update(custom_parameters)
        
        response = await self._make_request("POST", "/conversations", data=data)
        
        if response.success and response.conversation_id:
            # Store conversation information
            self.active_conversations[response.conversation_id] = {
                "agents": agents,
                "initial_message": initial_message,
                "max_turns": data["max_turns"],
                "template": template,
                "status": "active",
                "turns": 0
            }
        
        return response
    
    async def get_conversation(self, conversation_id: str) -> CamelResponse:
        """
        Get information about a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            CamelResponse with conversation information
        """
        response = await self._make_request("GET", f"/conversations/{conversation_id}")
        
        if response.success and conversation_id in self.active_conversations:
            # Update conversation information
            self.active_conversations[conversation_id].update({
                "status": response.data.get("status", "unknown"),
                "turns": response.data.get("turns", 0)
            })
        
        return response
    
    async def send_message(
        self,
        conversation_id: str,
        message: str,
        sender_id: str,
        recipient_id: Optional[str] = None
    ) -> CamelResponse:
        """
        Send a message in a conversation.
        
        Args:
            conversation_id: Conversation ID
            message: Message content
            sender_id: ID of the agent sending the message
            recipient_id: ID of the agent receiving the message
            
        Returns:
            CamelResponse with message information
        """
        data = {
            "message": message,
            "sender_id": sender_id
        }
        
        if recipient_id:
            data["recipient_id"] = recipient_id
        
        return await self._make_request(
            "POST", 
            f"/conversations/{conversation_id}/messages", 
            data=data
        )
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before: Optional[str] = None,
        after: Optional[str] = None
    ) -> CamelResponse:
        """
        Get messages from a conversation.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return
            before: Return messages before this message ID
            after: Return messages after this message ID
            
        Returns:
            CamelResponse with messages
        """
        params = {}
        if limit:
            params["limit"] = limit
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        
        return await self._make_request(
            "GET", 
            f"/conversations/{conversation_id}/messages", 
            params=params
        )
    
    async def end_conversation(self, conversation_id: str) -> CamelResponse:
        """
        End a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            CamelResponse with result
        """
        response = await self._make_request("POST", f"/conversations/{conversation_id}/end")
        
        if response.success and conversation_id in self.active_conversations:
            self.active_conversations[conversation_id]["status"] = "ended"
        
        return response
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        agents: List[str],
        steps: List[Dict[str, Any]],
        custom_parameters: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Create a new workflow.
        
        Args:
            name: Workflow name
            description: Workflow description
            agents: List of agent IDs
            steps: List of workflow steps
            custom_parameters: Additional parameters
            
        Returns:
            CamelResponse with workflow information
        """
        data = {
            "name": name,
            "description": description,
            "agents": agents,
            "steps": steps
        }
        
        if custom_parameters:
            data.update(custom_parameters)
        
        return await self._make_request("POST", "/workflows", data=data)
    
    async def start_workflow(
        self,
        workflow_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Start a workflow.
        
        Args:
            workflow_id: Workflow ID
            input_data: Input data for the workflow
            
        Returns:
            CamelResponse with workflow execution information
        """
        data = {}
        if input_data:
            data["input"] = input_data
        
        return await self._make_request("POST", f"/workflows/{workflow_id}/start", data=data)
    
    async def get_workflow_status(self, execution_id: str) -> CamelResponse:
        """
        Get the status of a workflow execution.
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            CamelResponse with workflow execution status
        """
        return await self._make_request("GET", f"/workflow-executions/{execution_id}")
    
    async def cancel_workflow(self, execution_id: str) -> CamelResponse:
        """
        Cancel a workflow execution.
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            CamelResponse with result
        """
        return await self._make_request("POST", f"/workflow-executions/{execution_id}/cancel")
    
    async def get_workflow_result(self, execution_id: str) -> CamelResponse:
        """
        Get the result of a workflow execution.
        
        Args:
            execution_id: Workflow execution ID
            
        Returns:
            CamelResponse with workflow execution result
        """
        return await self._make_request("GET", f"/workflow-executions/{execution_id}/result")
    
    async def run_agent_task(
        self,
        agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> CamelResponse:
        """
        Run a task with a single agent.
        
        Args:
            agent_id: Agent ID
            task: Task description
            context: Additional context for the task
            
        Returns:
            CamelResponse with task result
        """
        data = {
            "task": task
        }
        
        if context:
            data["context"] = context
        
        return await self._make_request("POST", f"/agents/{agent_id}/tasks", data=data)
    
    async def run_multi_agent_task(
        self,
        task: str,
        roles: List[Union[AgentRole, str]],
        context: Optional[Dict[str, Any]] = None,
        max_turns: Optional[int] = None,
        template: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Run a task with multiple agents.
        
        This is a higher-level method that creates agents, starts a conversation,
        and returns the result.
        
        Args:
            task: Task description
            roles: List of agent roles
            context: Additional context for the task
            max_turns: Maximum number of turns
            template: Conversation template name
            
        Returns:
            Tuple of (success, result_data, conversation_id)
        """
        # Create agents
        agent_ids = []
        for role in roles:
            if isinstance(role, AgentRole):
                role_str = role.value
            else:
                role_str = role
            
            # Get agent configuration if available
            agent_config = camel_config.agent_configs.get(
                AgentRole(role_str) if role_str in [e.value for e in AgentRole] else AgentRole.CUSTOM,
                None
            )
            
            agent_response = await self.create_agent(
                role=role_str,
                name=agent_config.name if agent_config else f"{role_str}_agent",
                system_message=agent_config.system_message if agent_config else None,
                model=agent_config.model if agent_config else None,
                temperature=agent_config.temperature if agent_config else None,
                max_tokens=agent_config.max_tokens if agent_config else None
            )
            
            if not agent_response.success:
                logger.error(f"Failed to create agent with role {role_str}: {agent_response.message}")
                return False, {"error": f"Failed to create agent: {agent_response.message}"}, None
            
            agent_ids.append(agent_response.data["agent_id"])
        
        # Start conversation
        conversation_response = await self.start_conversation(
            agents=agent_ids,
            initial_message=task,
            max_turns=max_turns,
            template=template,
            custom_parameters={"context": context} if context else None
        )
        
        if not conversation_response.success:
            logger.error(f"Failed to start conversation: {conversation_response.message}")
            return False, {"error": f"Failed to start conversation: {conversation_response.message}"}, None
        
        conversation_id = conversation_response.conversation_id
        
        # Wait for conversation to complete
        status = "active"
        result_data = {}
        
        while status == "active":
            await asyncio.sleep(2)  # Poll every 2 seconds
            
            status_response = await self.get_conversation(conversation_id)
            if not status_response.success:
                logger.error(f"Failed to get conversation status: {status_response.message}")
                return False, {"error": f"Failed to get conversation status: {status_response.message}"}, conversation_id
            
            status = status_response.data.get("status", "unknown")
            
            if status == "completed":
                # Get messages
                messages_response = await self.get_messages(conversation_id)
                if messages_response.success:
                    result_data = {
                        "conversation": status_response.data,
                        "messages": messages_response.data.get("messages", []),
                        "summary": status_response.data.get("summary", ""),
                        "outcome": status_response.data.get("outcome", {})
                    }
                    return True, result_data, conversation_id
                else:
                    logger.error(f"Failed to get conversation messages: {messages_response.message}")
                    return False, {"error": f"Failed to get conversation messages: {messages_response.message}"}, conversation_id
            
            elif status == "failed":
                logger.error(f"Conversation failed: {status_response.data.get('error', 'Unknown error')}")
                return False, {"error": f"Conversation failed: {status_response.data.get('error', 'Unknown error')}"}, conversation_id
        
        return False, {"error": "Conversation ended with unknown status"}, conversation_id

# Global client instance
camel_client = CamelClient()