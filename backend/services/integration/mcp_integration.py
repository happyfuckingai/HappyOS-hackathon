"""
MCP Integration Service for Backend (Refactored)

This module provides the main integration interface, delegating to
specialized modules for resilience, client communication, and business logic.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .summarizer_integration import (
    get_integration_service,
    initialize_integration_service,
    shutdown_integration_service,
    SummarizerServiceConfig
)

logger = logging.getLogger(__name__)

# Global service instance for backward compatibility
_mcp_service = None


class MCPIntegrationService:
    """
    Simplified MCP Integration Service
    
    Delegates to the new modular architecture while maintaining
    backward compatibility with existing code.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.MCPIntegrationService")
        self._integration_service = get_integration_service()
    
    async def summarize_meeting(
        self,
        meeting_id: str,
        content: str,
        style: str = "brief"
    ) -> Dict[str, Any]:
        """Summarize meeting content"""
        return await self._integration_service.summarize_meeting(
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
        """Perform semantic search"""
        return await self._integration_service.semantic_search(
            query,
            limit,
            filters
        )
    
    async def process_voice_command(
        self,
        voice_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process voice command"""
        result = await self._integration_service.process_voice_command(
            voice_input,
            context
        )
        return result.get("response", "No response")
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get available tools"""
        return await self._integration_service.get_available_tools()
    
    async def get_conversation_context(
        self,
        meeting_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get conversation context"""
        return await self._integration_service.get_conversation_context(meeting_id)
    
    async def segment_topics_in_conversation(
        self,
        transcript: str
    ) -> Dict[str, Any]:
        """Segment conversation topics"""
        return await self._integration_service.segment_topics_in_conversation(
            transcript
        )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status"""
        return await self._integration_service.get_health_status()
    
    def set_summarizer_service(self, service):
        """Set summarizer service"""
        self._integration_service.set_summarizer_service(service)


def get_mcp_service() -> MCPIntegrationService:
    """Get or create global MCP service instance"""
    global _mcp_service
    
    if _mcp_service is None:
        _mcp_service = MCPIntegrationService()
    
    return _mcp_service


async def initialize_mcp_service() -> MCPIntegrationService:
    """Initialize MCP service"""
    global _mcp_service
    
    # Initialize the integration service
    await initialize_integration_service()
    
    # Create MCP service wrapper
    _mcp_service = MCPIntegrationService()
    
    return _mcp_service


async def shutdown_mcp_service():
    """Shutdown MCP service"""
    global _mcp_service
    
    if _mcp_service:
        await shutdown_integration_service()
        _mcp_service = None


# Convenience functions for backward compatibility
async def summarize_meeting(meeting_id: str, content: str) -> Dict[str, Any]:
    """Summarize a meeting using the local summarizer service"""
    service = get_mcp_service()
    return await service.summarize_meeting(meeting_id, content)


async def get_available_tools() -> List[Dict[str, Any]]:
    """Get list of available summarizer tools"""
    service = get_mcp_service()
    return await service.get_available_tools()


async def process_file_for_summary(file_path: str, action: str = "summarize") -> str:
    """Process a file for summarization (placeholder)"""
    logger.warning("File processing not implemented")
    return f"File processing not available for {file_path}"


async def get_conversation_context() -> Dict[str, Any]:
    """Get current conversation context"""
    service = get_mcp_service()
    return await service.get_conversation_context()


async def segment_topics_in_conversation(transcript: str) -> Dict[str, Any]:
    """Segment conversation into topics"""
    service = get_mcp_service()
    return await service.segment_topics_in_conversation(transcript)


async def get_mcp_health() -> Dict[str, Any]:
    """Get MCP service health status"""
    service = get_mcp_service()
    return await service.get_health_status()


async def process_voice_command(voice_input: str) -> str:
    """Process voice command for topic management"""
    service = get_mcp_service()
    return await service.process_voice_command(voice_input)