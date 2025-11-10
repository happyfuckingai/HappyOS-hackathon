"""
CAMEL Network Module

This module handles network communication with the CAMEL service.
"""

import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional, Union, List
from ..error_handling.retry_manager import retry_with_backoff
from ...config.network_config import network_config

# Configure logging
logger = logging.getLogger(__name__)

class CamelNetworkClient:
    """Client for communicating with the CAMEL API"""
    
    def __init__(self, config=None):
        """
        Initialize the CAMEL network client
        
        Args:
            config: Optional custom configuration
        """
        self.config = config or network_config.camel
        self.base_url = self.config.base_url
        self.api_key = os.getenv(self.config.api_key_env_var, "")
        self.session = None
    
    async def initialize(self):
        """Initialize the HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self._get_default_headers(),
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
    
    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @retry_with_backoff(max_retries=3, backoff_factor=0.5)
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the CAMEL API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Request data (for POST, PUT, etc.)
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response data as dictionary
        """
        await self.initialize()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                proxy=self.config.proxy,
                ssl=self.config.verify_ssl
            ) as response:
                response_text = await response.text()
                
                if response.status >= 400:
                    logger.error(f"CAMEL API error: {response.status} - {response_text}")
                    raise CamelNetworkError(
                        f"CAMEL API returned error {response.status}: {response_text}",
                        status_code=response.status,
                        response_text=response_text
                    )
                
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON response: {response_text}")
                    return {"raw_response": response_text}
                
        except aiohttp.ClientError as e:
            logger.error(f"CAMEL API request failed: {str(e)}")
            raise CamelNetworkError(f"CAMEL API request failed: {str(e)}")
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to the CAMEL API"""
        return await self.request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the CAMEL API"""
        return await self.request("POST", endpoint, data=data)
    
    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a PUT request to the CAMEL API"""
        return await self.request("PUT", endpoint, data=data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request to the CAMEL API"""
        return await self.request("DELETE", endpoint)
    
    async def check_connection(self) -> bool:
        """
        Check if the connection to CAMEL API is working
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to make a simple request to check connection
            await self.get("health")
            return True
        except Exception as e:
            logger.warning(f"CAMEL API connection check failed: {str(e)}")
            return False
    
    async def create_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new CAMEL agent
        
        Args:
            agent_config: Agent configuration
            
        Returns:
            Created agent data
        """
        return await self.post("agents", data=agent_config)
    
    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent details
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent data
        """
        return await self.get(f"agents/{agent_id}")
    
    async def list_agents(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        List available agents
        
        Args:
            filters: Optional filters
            
        Returns:
            List of agents
        """
        response = await self.get("agents", params=filters)
        return response.get("agents", [])
    
    async def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Delete an agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Deletion status
        """
        return await self.delete(f"agents/{agent_id}")
    
    async def start_conversation(self, conversation_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new conversation between agents
        
        Args:
            conversation_config: Conversation configuration
            
        Returns:
            Conversation data
        """
        return await self.post("conversations", data=conversation_config)
    
    async def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get conversation details
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation data
        """
        return await self.get(f"conversations/{conversation_id}")
    
    async def send_message(self, conversation_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to a conversation
        
        Args:
            conversation_id: Conversation ID
            message: Message data
            
        Returns:
            Message status
        """
        return await self.post(f"conversations/{conversation_id}/messages", data=message)

class CamelNetworkError(Exception):
    """Exception raised for CAMEL network errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)

# Singleton instance
camel_network_client = CamelNetworkClient()