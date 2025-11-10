"""
Owl Client Module

This module provides a client for interacting with the Owl multi-agent runtime framework.
It handles API communication, authentication, and response processing.
"""

import json
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime

from .owl_config import get_owl_config
from .owl_helpers import sanitize_input
from app.core.error_handling.retry_manager import retry_with_backoff
from app.core.security.security import get_secure_api_key

logger = logging.getLogger(__name__)

@dataclass
class OwlResponse:
    """Data class for structured Owl API responses."""
    success: bool
    data: Dict[str, Any]
    message: str
    timestamp: datetime
    raw_response: Dict[str, Any]
    
    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> 'OwlResponse':
        """Create an OwlResponse from the raw API response."""
        return cls(
            success=response.get('success', False),
            data=response.get('data', {}),
            message=response.get('message', ''),
            timestamp=datetime.now(),
            raw_response=response
        )
    
    def get_generated_code(self) -> Dict[str, str]:
        """Extract generated code from the response if available."""
        if not self.success:
            return {}
        
        code_data = {}
        if 'generated_code' in self.data:
            code_data = self.data['generated_code']
        elif 'files' in self.data:
            code_data = self.data['files']
        
        return code_data
    
    def get_agent_logs(self) -> List[Dict[str, Any]]:
        """Extract agent logs from the response if available."""
        if not self.success:
            return []
        
        return self.data.get('agent_logs', [])


class OwlClient:
    """Client for interacting with the Owl multi-agent runtime framework."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Owl client.
        
        Args:
            config: Optional configuration dictionary. If not provided,
                   configuration will be loaded from environment variables.
        """
        self.config = config or get_owl_config()
        self.base_url = self.config['api_url']
        self.timeout = aiohttp.ClientTimeout(total=self.config['timeout_seconds'])
        self.session = None
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize the aiohttp session with appropriate headers."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
            )
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        api_key = await get_secure_api_key('owl')
        return {
            'Authorization': f"Bearer {api_key}"
        }
    
    @retry_with_backoff(max_retries=3, base_delay=1, max_delay=10)
    async def send_task_to_owl(
        self, 
        task: str, 
        context: Optional[Dict[str, Any]] = None,
        agent_type: str = "camel_chat",
        workflow_id: Optional[str] = None
    ) -> OwlResponse:
        """
        Send a task to Owl for processing by CAMEL agents.
        
        Args:
            task: The task description or user request
            context: Additional context for the task (user info, history, etc.)
            agent_type: The type of agent to handle the task
            workflow_id: Optional workflow ID for continuing an existing workflow
            
        Returns:
            OwlResponse object containing the processed result
        """
        self._initialize_session()
        
        # Sanitize inputs
        sanitized_task = sanitize_input(task)
        sanitized_context = {k: sanitize_input(v) if isinstance(v, str) else v 
                            for k, v in (context or {}).items()}
        
        # Prepare payload
        payload = {
            "task": sanitized_task,
            "context": sanitized_context,
            "agent": agent_type
        }
        
        if workflow_id:
            payload["workflow_id"] = workflow_id
            
        # Log request (excluding sensitive data)
        logger.info(f"Sending task to Owl: agent={agent_type}, workflow_id={workflow_id}")
        logger.debug(f"Task: {sanitized_task[:100]}...")
        
        try:
            # Get authentication headers
            auth_headers = await self._get_auth_headers()
            
            # Send request to Owl API
            endpoint = f"{self.base_url}/api/agent-chat"
            async with self.session.post(
                endpoint, 
                json=payload,
                headers=auth_headers
            ) as response:
                # Check for HTTP errors
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"Owl API error: {response.status} - {error_text}")
                    return OwlResponse(
                        success=False,
                        data={},
                        message=f"API error: {response.status}",
                        timestamp=datetime.now(),
                        raw_response={"error": error_text}
                    )
                
                # Parse response
                response_data = await response.json()
                owl_response = OwlResponse.from_api_response(response_data)
                
                # Log success/failure
                if owl_response.success:
                    logger.info(f"Successfully processed task with Owl: {owl_response.message}")
                else:
                    logger.warning(f"Owl task processing failed: {owl_response.message}")
                
                return owl_response
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error when connecting to Owl API: {str(e)}")
            return OwlResponse(
                success=False,
                data={},
                message=f"Network error: {str(e)}",
                timestamp=datetime.now(),
                raw_response={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Unexpected error in Owl API communication: {str(e)}")
            return OwlResponse(
                success=False,
                data={},
                message=f"Unexpected error: {str(e)}",
                timestamp=datetime.now(),
                raw_response={"error": str(e)}
            )
    
    async def get_workflow_status(self, workflow_id: str) -> OwlResponse:
        """
        Get the status of an existing workflow.
        
        Args:
            workflow_id: The ID of the workflow to check
            
        Returns:
            OwlResponse object containing the workflow status
        """
        self._initialize_session()
        
        try:
            # Get authentication headers
            auth_headers = await self._get_auth_headers()
            
            # Send request to Owl API
            endpoint = f"{self.base_url}/api/workflow/{workflow_id}/status"
            async with self.session.get(
                endpoint,
                headers=auth_headers
            ) as response:
                # Check for HTTP errors
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"Owl API error: {response.status} - {error_text}")
                    return OwlResponse(
                        success=False,
                        data={},
                        message=f"API error: {response.status}",
                        timestamp=datetime.now(),
                        raw_response={"error": error_text}
                    )
                
                # Parse response
                response_data = await response.json()
                return OwlResponse.from_api_response(response_data)
                
        except Exception as e:
            logger.error(f"Error getting workflow status: {str(e)}")
            return OwlResponse(
                success=False,
                data={},
                message=f"Error: {str(e)}",
                timestamp=datetime.now(),
                raw_response={"error": str(e)}
            )
    
    async def cancel_workflow(self, workflow_id: str) -> OwlResponse:
        """
        Cancel an existing workflow.
        
        Args:
            workflow_id: The ID of the workflow to cancel
            
        Returns:
            OwlResponse object containing the cancellation result
        """
        self._initialize_session()
        
        try:
            # Get authentication headers
            auth_headers = await self._get_auth_headers()
            
            # Send request to Owl API
            endpoint = f"{self.base_url}/api/workflow/{workflow_id}/cancel"
            async with self.session.post(
                endpoint,
                headers=auth_headers
            ) as response:
                # Check for HTTP errors
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"Owl API error: {response.status} - {error_text}")
                    return OwlResponse(
                        success=False,
                        data={},
                        message=f"API error: {response.status}",
                        timestamp=datetime.now(),
                        raw_response={"error": error_text}
                    )
                
                # Parse response
                response_data = await response.json()
                return OwlResponse.from_api_response(response_data)
                
        except Exception as e:
            logger.error(f"Error cancelling workflow: {str(e)}")
            return OwlResponse(
                success=False,
                data={},
                message=f"Error: {str(e)}",
                timestamp=datetime.now(),
                raw_response={"error": str(e)}
            )