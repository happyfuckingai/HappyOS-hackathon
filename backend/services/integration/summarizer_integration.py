"""
Summarizer Integration Service

Provides high-level integration with the summarizer service,
combining MCP client functionality with business logic.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .mcp_client import MCPClient, MCPClientConfig, create_mcp_client

logger = logging.getLogger(__name__)


@dataclass
class SummarizerServiceConfig:
    """Configuration for local summarizer service"""
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3
    circuit_breaker_enabled: bool = True
    graceful_degradation: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutes


@dataclass
class SummarizerServiceHealth:
    """Health status of local summarizer service"""
    is_initialized: bool = False
    component_count: int = 0
    last_check: Optional[float] = None
    error_message: Optional[str] = None


class SummarizerIntegrationService:
    """
    High-level integration service for summarizer functionality
    
    Provides business logic layer on top of MCP client,
    including caching, validation, and enhanced error handling.
    """
    
    def __init__(self, config: SummarizerServiceConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SummarizerIntegrationService")
        
        # Create MCP client
        mcp_config = MCPClientConfig(
            enabled=config.enabled,
            timeout=config.timeout,
            max_retries=config.max_retries,
            circuit_breaker_enabled=config.circuit_breaker_enabled,
            graceful_degradation=config.graceful_degradation
        )
        self.mcp_client = create_mcp_client(mcp_config)
        
        # Cache for responses
        self._response_cache = {}
        self._health_status = SummarizerServiceHealth()
    
    def set_summarizer_service(self, service):
        """Set the underlying summarizer service"""
        self.mcp_client.set_summarizer_service(service)
        self._health_status.is_initialized = True
    
    async def summarize_meeting(
        self,
        meeting_id: str,
        content: str,
        style: str = "brief",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Summarize meeting with enhanced business logic
        
        Args:
            meeting_id: Unique meeting identifier
            content: Meeting content to summarize
            style: Summary style (brief, detailed, bullet_points)
            use_cache: Whether to use cached results
            
        Returns:
            Enhanced summary with metadata
        """
        # Input validation
        if not meeting_id or not content:
            raise ValueError("meeting_id and content are required")
        
        if style not in ["brief", "detailed", "bullet_points"]:
            style = "brief"
        
        # Check cache first
        cache_key = f"summary:{meeting_id}:{style}:{hash(content)}"
        if use_cache and self.config.cache_enabled:
            cached_result = self._get_cached_response(cache_key)
            if cached_result:
                self.logger.debug(f"Returning cached summary for {meeting_id}")
                return cached_result
        
        try:
            # Get summary from MCP client
            result = await self.mcp_client.summarize_meeting(
                meeting_id,
                content,
                style
            )
            
            # Enhance result with metadata
            enhanced_result = {
                **result,
                "metadata": {
                    "meeting_id": meeting_id,
                    "style": style,
                    "content_length": len(content),
                    "processing_timestamp": asyncio.get_event_loop().time(),
                    "cached": False
                }
            }
            
            # Cache the result
            if self.config.cache_enabled:
                self._cache_response(cache_key, enhanced_result)
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"Failed to summarize meeting {meeting_id}: {e}")
            raise
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search with enhanced business logic
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional search filters
            use_cache: Whether to use cached results
            
        Returns:
            Enhanced search results with metadata
        """
        # Input validation
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if limit <= 0 or limit > 100:
            limit = 10
        
        # Check cache first
        cache_key = f"search:{hash(query)}:{limit}:{hash(str(filters))}"
        if use_cache and self.config.cache_enabled:
            cached_result = self._get_cached_response(cache_key)
            if cached_result:
                self.logger.debug(f"Returning cached search results for: {query}")
                return cached_result
        
        try:
            # Get search results from MCP client
            results = await self.mcp_client.semantic_search(
                query,
                limit,
                filters
            )
            
            # Enhance results with metadata
            enhanced_results = []
            for i, result in enumerate(results):
                enhanced_result = {
                    **result,
                    "rank": i + 1,
                    "query": query,
                    "search_timestamp": asyncio.get_event_loop().time(),
                    "cached": False
                }
                enhanced_results.append(enhanced_result)
            
            # Cache the results
            if self.config.cache_enabled:
                self._cache_response(cache_key, enhanced_results)
            
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"Failed to perform semantic search for '{query}': {e}")
            raise
    
    async def process_voice_command(
        self,
        voice_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice command with enhanced business logic
        
        Args:
            voice_input: Voice command text
            context: Optional context information
            
        Returns:
            Enhanced response with metadata
        """
        # Input validation
        if not voice_input or not voice_input.strip():
            raise ValueError("Voice input cannot be empty")
        
        try:
            # Process voice command through MCP client
            response = await self.mcp_client.process_voice_command(
                voice_input,
                context
            )
            
            # Return enhanced response
            return {
                "response": response,
                "metadata": {
                    "voice_input": voice_input,
                    "context_provided": context is not None,
                    "processing_timestamp": asyncio.get_event_loop().time()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process voice command '{voice_input}': {e}")
            raise
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with enhanced metadata"""
        try:
            tools = await self.mcp_client.get_available_tools()
            
            # Enhance tools with additional metadata
            enhanced_tools = []
            for tool in tools:
                enhanced_tool = {
                    **tool,
                    "service": "summarizer",
                    "available": self.config.enabled,
                    "last_updated": asyncio.get_event_loop().time()
                }
                enhanced_tools.append(enhanced_tool)
            
            return enhanced_tools
            
        except Exception as e:
            self.logger.error(f"Failed to get available tools: {e}")
            return []
    
    async def get_conversation_context(
        self,
        meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get conversation context with enhanced metadata"""
        try:
            context = await self.mcp_client.get_conversation_context(meeting_id)
            
            # Enhance context with service metadata
            enhanced_context = {
                **context,
                "service_metadata": {
                    "service_enabled": self.config.enabled,
                    "health_status": self._health_status.is_initialized,
                    "last_check": asyncio.get_event_loop().time()
                }
            }
            
            return enhanced_context
            
        except Exception as e:
            self.logger.error(f"Failed to get conversation context: {e}")
            return {"error": str(e)}
    
    async def segment_topics_in_conversation(
        self,
        transcript: str
    ) -> Dict[str, Any]:
        """Segment conversation topics with enhanced metadata"""
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")
        
        try:
            result = await self.mcp_client.segment_topics(transcript)
            
            # Enhance result with metadata
            enhanced_result = {
                **result,
                "metadata": {
                    "transcript_length": len(transcript),
                    "processing_timestamp": asyncio.get_event_loop().time(),
                    "topic_count": len(result.get("topics", [])),
                    "segment_count": len(result.get("segments", []))
                }
            }
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"Failed to segment topics: {e}")
            raise
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        try:
            # Get MCP client health
            client_health = await self.mcp_client.get_health_status()
            
            # Combine with service health
            health_status = {
                "service_config": {
                    "enabled": self.config.enabled,
                    "cache_enabled": self.config.cache_enabled,
                    "timeout": self.config.timeout,
                    "max_retries": self.config.max_retries
                },
                "client_health": client_health,
                "service_health": {
                    "is_initialized": self._health_status.is_initialized,
                    "component_count": self._health_status.component_count,
                    "last_check": self._health_status.last_check,
                    "error_message": self._health_status.error_message
                },
                "cache_stats": {
                    "enabled": self.config.cache_enabled,
                    "entries": len(self._response_cache)
                }
            }
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Failed to get health status: {e}")
            return {"error": str(e)}
    
    def _cache_response(self, key: str, response: Any):
        """Cache response with TTL"""
        if not self.config.cache_enabled:
            return
        
        expiry = asyncio.get_event_loop().time() + self.config.cache_ttl
        self._response_cache[key] = {
            "data": response,
            "expiry": expiry
        }
    
    def _get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response if available and not expired"""
        if not self.config.cache_enabled or key not in self._response_cache:
            return None
        
        cached = self._response_cache[key]
        current_time = asyncio.get_event_loop().time()
        
        if current_time > cached["expiry"]:
            del self._response_cache[key]
            return None
        
        # Mark as cached in metadata if it's a dict
        result = cached["data"]
        if isinstance(result, dict) and "metadata" in result:
            result["metadata"]["cached"] = True
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            for item in result:
                if "cached" in item:
                    item["cached"] = True
        
        return result
    
    def clear_cache(self):
        """Clear response cache"""
        self._response_cache.clear()
        self.logger.info("Response cache cleared")


# Global service instance
_integration_service: Optional[SummarizerIntegrationService] = None


def get_integration_service() -> SummarizerIntegrationService:
    """Get or create global integration service instance"""
    global _integration_service
    
    if _integration_service is None:
        config = SummarizerServiceConfig()
        _integration_service = SummarizerIntegrationService(config)
    
    return _integration_service


async def initialize_integration_service(
    config: Optional[SummarizerServiceConfig] = None
) -> SummarizerIntegrationService:
    """Initialize integration service with configuration"""
    global _integration_service
    
    if config is None:
        config = SummarizerServiceConfig()
    
    _integration_service = SummarizerIntegrationService(config)
    
    # Try to initialize with summarizer service
    try:
        from .summarizer_service import get_summarizer_service
        summarizer_service = get_summarizer_service()
        _integration_service.set_summarizer_service(summarizer_service)
    except ImportError:
        logger.warning("Summarizer service not available")
    
    return _integration_service


async def shutdown_integration_service():
    """Shutdown integration service"""
    global _integration_service
    
    if _integration_service:
        _integration_service.clear_cache()
        _integration_service = None