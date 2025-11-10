"""
Owl Network Module

This module handles network communication with the Owl service.
"""

import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional, Union
from ..error_handling.retry_manager import retry_with_backoff
from ...config.network_config import network_config

# Configure logging
logger = logging.getLogger(__name__)

class OwlNetworkClient:
    """Client for communicating with the Owl API"""
    
    def __init__(self, config=None):
        """
        Initialize the Owl network client
        
        Args:
            config: Optional custom configuration
        """
        self.config = config or network_config.owl
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
        Make a request to the Owl API
        
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
                    logger.error(f"Owl API error: {response.status} - {response_text}")
                    raise OwlNetworkError(
                        f"Owl API returned error {response.status}: {response_text}",
                        status_code=response.status,
                        response_text=response_text
                    )
                
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON response: {response_text}")
                    return {"raw_response": response_text}
                
        except aiohttp.ClientError as e:
            logger.error(f"Owl API request failed: {str(e)}")
            raise OwlNetworkError(f"Owl API request failed: {str(e)}")
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to the Owl API"""
        return await self.request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the Owl API"""
        return await self.request("POST", endpoint, data=data)
    
    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a PUT request to the Owl API"""
        return await self.request("PUT", endpoint, data=data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request to the Owl API"""
        return await self.request("DELETE", endpoint)
    
    async def check_connection(self) -> bool:
        """
        Check if the connection to Owl API is working
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to make a simple request to check connection
            await self.get("health")
            return True
        except Exception as e:
            logger.warning(f"Owl API connection check failed: {str(e)}")
            return False

class OwlNetworkError(Exception):
    """Exception raised for Owl network errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)

# Singleton instance
owl_network_client = OwlNetworkClient()