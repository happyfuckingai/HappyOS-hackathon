"""
MCP Client Interface

Provides a clean interface for MCP (Model Context Protocol) operations
with the local summarizer service.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .resilience import (
    create_default_circuit_breaker,
    create_default_retry_handler,
    create_default_degradation_handler,
    CircuitBreakerOpenError,
    ServiceUnavailableError
)

logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    """Configuration for MCP client"""
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3
    circuit_breaker_enabled: bool = True
    graceful_degradation: bool = True


class MCPClient:
    """
    MCP Client for communicating with local summarizer service
    
    Provides resilient communication with circuit breaker,
    retry logic, and graceful degradation.
    """
    
    def __init__(self, config: MCPClientConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.MCPClient")
        
        # Initialize resilience components
        self.retry_handler = create_default_retry_handler()
        self.circuit_breaker = create_default_circuit_breaker()
        self.degradation_handler = create_default_degradation_handler()
        
        # Service reference (will be injected)
        self._summarizer_service = None
    
    def set_summarizer_service(self, service):
        """Set the summarizer service instance"""
        self._summarizer_service = service
    
    async def summarize_meeting(
        self,
        meeting_id: str,
        content: str,
        style: str = "brief"
    ) -> Dict[str, Any]:
        """
        Summarize meeting content
        
        Args:
            meeting_id: Unique meeting identifier
            content: Meeting content to summarize
            style: Summary style (brief, detailed, bullet_points)
            
        Returns:
            Dictionary containing summary, topics, and action items
        """
        if not self.config.enabled:
            return self.degradation_handler.get_fallback_summary(meeting_id)
        
        try:
            if self.config.circuit_breaker_enabled:
                return await self.circuit_breaker.execute(
                    self._execute_summarize_meeting,
                    meeting_id,
                    content,
                    style
                )
            else:
                return await self._execute_summarize_meeting(
                    meeting_id,
                    content,
                    style
                )
                
        except (CircuitBreakerOpenError, ServiceUnavailableError) as e:
            self.logger.warning(f"Summarization failed: {e}")
            if self.config.graceful_degradation:
                return self.degradation_handler.get_fallback_summary(meeting_id)
            raise
    
    async def _execute_summarize_meeting(
        self,
        meeting_id: str,
        content: str,
        style: str
    ) -> Dict[str, Any]:
        """Execute meeting summarization with retry logic"""
        if not self._summarizer_service:
            raise ServiceUnavailableError("Summarizer service not available")
        
        return await self.retry_handler.execute_with_retry(
            self._summarizer_service.summarize_meeting,
            meeting_id,
            content,
            style
        )
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional search filters
            
        Returns:
            List of search results
        """
        if not self.config.enabled:
            return self.degradation_handler.get_fallback_search_results(query)
        
        try:
            if self.config.circuit_breaker_enabled:
                return await self.circuit_breaker.execute(
                    self._execute_semantic_search,
                    query,
                    limit,
                    filters
                )
            else:
                return await self._execute_semantic_search(query, limit, filters)
                
        except (CircuitBreakerOpenError, ServiceUnavailableError) as e:
            self.logger.warning(f"Semantic search failed: {e}")
            if self.config.graceful_degradation:
                return self.degradation_handler.get_fallback_search_results(query)
            raise
    
    async def _execute_semantic_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute semantic search with retry logic"""
        if not self._summarizer_service:
            raise ServiceUnavailableError("Summarizer service not available")
        
        return await self.retry_handler.execute_with_retry(
            self._summarizer_service.semantic_search,
            query,
            limit,
            filters or {}
        )
    
    async def process_voice_command(
        self,
        voice_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process voice command
        
        Args:
            voice_input: Voice command text
            context: Optional context information
            
        Returns:
            Response text
        """
        if not self.config.enabled:
            return "Voice command processing is currently unavailable"
        
        try:
            if self.config.circuit_breaker_enabled:
                return await self.circuit_breaker.execute(
                    self._execute_voice_command,
                    voice_input,
                    context
                )
            else:
                return await self._execute_voice_command(voice_input, context)
                
        except (CircuitBreakerOpenError, ServiceUnavailableError) as e:
            self.logger.warning(f"Voice command processing failed: {e}")
            if self.config.graceful_degradation:
                return f"Unable to process voice command: {voice_input}"
            raise
    
    async def _execute_voice_command(
        self,
        voice_input: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Execute voice command processing with retry logic"""
        if not self._summarizer_service:
            raise ServiceUnavailableError("Summarizer service not available")
        
        return await self.retry_handler.execute_with_retry(
            self._summarizer_service.process_voice_command,
            voice_input,
            context or {}
        )
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools
        
        Returns:
            List of available tool definitions
        """
        if not self.config.enabled or not self._summarizer_service:
            return []
        
        try:
            if hasattr(self._summarizer_service, 'get_available_tools'):
                return await self._summarizer_service.get_available_tools()
            else:
                # Return default tool list
                return [
                    {
                        "name": "summarize_meeting",
                        "description": "Summarize meeting content",
                        "parameters": {
                            "meeting_id": "string",
                            "content": "string",
                            "style": "string"
                        }
                    },
                    {
                        "name": "semantic_search",
                        "description": "Search meeting content semantically",
                        "parameters": {
                            "query": "string",
                            "limit": "integer"
                        }
                    },
                    {
                        "name": "process_voice_command",
                        "description": "Process voice commands",
                        "parameters": {
                            "voice_input": "string",
                            "context": "object"
                        }
                    }
                ]
        except Exception as e:
            self.logger.error(f"Failed to get available tools: {e}")
            return []
    
    async def get_conversation_context(
        self,
        meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current conversation context
        
        Args:
            meeting_id: Optional meeting ID for context
            
        Returns:
            Current conversation context
        """
        if not self.config.enabled or not self._summarizer_service:
            return {"context": "unavailable", "meeting_id": meeting_id}
        
        try:
            if hasattr(self._summarizer_service, 'get_conversation_context'):
                return await self._summarizer_service.get_conversation_context(
                    meeting_id
                )
            else:
                return {
                    "context": "basic",
                    "meeting_id": meeting_id,
                    "timestamp": asyncio.get_event_loop().time()
                }
        except Exception as e:
            self.logger.error(f"Failed to get conversation context: {e}")
            return {"context": "error", "error": str(e)}
    
    async def segment_topics(self, transcript: str) -> Dict[str, Any]:
        """
        Segment conversation into topics
        
        Args:
            transcript: Conversation transcript
            
        Returns:
            Topic segmentation results
        """
        if not self.config.enabled or not self._summarizer_service:
            return {"topics": [], "segments": []}
        
        try:
            if hasattr(self._summarizer_service, 'segment_topics'):
                return await self._summarizer_service.segment_topics(transcript)
            else:
                # Basic topic segmentation fallback
                return {
                    "topics": ["general_discussion"],
                    "segments": [
                        {
                            "start": 0,
                            "end": len(transcript),
                            "topic": "general_discussion",
                            "content": transcript[:200] + "..." if len(transcript) > 200 else transcript
                        }
                    ]
                }
        except Exception as e:
            self.logger.error(f"Failed to segment topics: {e}")
            return {"topics": [], "segments": [], "error": str(e)}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get client and service health status
        
        Returns:
            Health status information
        """
        status = {
            "client_enabled": self.config.enabled,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "service_available": self._summarizer_service is not None
        }
        
        if self._summarizer_service and hasattr(self._summarizer_service, 'get_service_health'):
            try:
                service_health = self._summarizer_service.get_service_health()
                status["service_health"] = service_health
            except Exception as e:
                status["service_health"] = {"error": str(e)}
        
        return status


# Factory function
def create_mcp_client(config: Optional[MCPClientConfig] = None) -> MCPClient:
    """Create MCP client with default or provided configuration"""
    if config is None:
        config = MCPClientConfig()
    
    return MCPClient(config)