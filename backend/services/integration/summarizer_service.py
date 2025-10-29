"""
Backend Summarizer Service

This service integrates the summarizer components directly into the FastAPI backend,
eliminating the need for a separate MCP server process. It provides a clean interface
for the FastAPI routes to access summarizer functionality.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

# Lazy imports to avoid triggering A2A protocol initialization at import time
# These will be imported only when summarizer is actually used

logger = logging.getLogger(__name__)


class SummarizerService:
    """
    Main service for integrating summarizer components into FastAPI backend.
    """

    def __init__(self):
        """Initialize the summarizer service."""
        self.logger = logging.getLogger(__name__)

        # Core components
        self.database_manager: Optional[DatabaseManager] = None
        self.vector_search_manager: Optional[VectorSearchManager] = None
        self.ai_client_manager: Optional[AIClientManager] = None
        self.ai_summarization_manager: Optional[AISummarizationManager] = None
        self.topic_manager: Optional[TopicManager] = None
        self.ui_state_manager: Optional[UIStateManager] = None
        self.voice_commands_manager: Optional[VoiceCommandsManager] = None
        self.mcp_tools_handler: Optional[MCPToolsHandler] = None
        self.search_handlers: Optional[SearchHandlers] = None

        # Service state
        self.initialized = False

    async def initialize(self) -> bool:
        """
        Initialize all summarizer components.

        Returns:
            True if initialization successful
        """
        if self.initialized:
            return True

        try:
            self.logger.info("Initializing Summarizer Service...")

            # Initialize components in dependency order
            await self._initialize_components()

            self.initialized = True
            self.logger.info("Summarizer Service initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Summarizer Service: {e}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Clean up all components."""
        if not self.initialized:
            return

        try:
            self.logger.info("Shutting down Summarizer Service...")

            # Cleanup components in reverse order
            components = [
                self.search_handlers,
                self.mcp_tools_handler,
                self.voice_commands_manager,
                self.ui_state_manager,
                self.topic_manager,
                self.ai_summarization_manager,
                self.ai_client_manager,
                self.vector_search_manager,
                self.database_manager,
            ]

            for component in components:
                if component and hasattr(component, 'shutdown'):
                    try:
                        await component.shutdown()
                    except Exception as e:
                        self.logger.error(f"Error shutting down component: {e}")

            self.initialized = False
            self.logger.info("Summarizer Service shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during Summarizer Service cleanup: {e}")

    async def _initialize_components(self):
        """Initialize all components with proper dependency order."""
        # Lazy import summarizer components to avoid triggering A2A at module load time
        from ...summarizer.database.database import DatabaseManager
        from ...summarizer.managers.vector_search_manager import VectorSearchManager
        from ...summarizer.ai_clients import AIClientManager
        from ...summarizer.core.ai_summarization import AISummarizationManager
        from ...summarizer.managers.topic_manager import TopicManager
        from ...summarizer.managers.ui_state_manager import UIStateManager
        from ...summarizer.utils.voice_commands import VoiceCommandsManager
        from ...summarizer.utils.mcp_tools import MCPToolsHandler
        from ...summarizer.utils.search_handlers import SearchHandlers
        
        # 1. Database manager (no dependencies)
        self.database_manager = DatabaseManager()
        await self.database_manager.initialize()

        # 2. Vector search manager (no dependencies)
        self.vector_search_manager = VectorSearchManager()
        await self.vector_search_manager.initialize()

        # 3. AI client manager (no dependencies)
        self.ai_client_manager = AIClientManager()
        await self.ai_client_manager.initialize()

        # 4. AI summarization manager (depends on AI client manager)
        self.ai_summarization_manager = AISummarizationManager(self.ai_client_manager)
        await self.ai_summarization_manager.initialize()

        # 5. Topic manager (depends on database and AI summarization)
        self.topic_manager = TopicManager(self.database_manager, self.ai_summarization_manager)
        await self.topic_manager.initialize()

        # 6. UI state manager (no dependencies)
        self.ui_state_manager = UIStateManager()
        await self.ui_state_manager.initialize()

        # 7. Voice commands manager (depends on UI state and topic managers)
        self.voice_commands_manager = VoiceCommandsManager(
            self.ui_state_manager, self.topic_manager, self.ai_summarization_manager
        )
        await self.voice_commands_manager.initialize()

        # 8. MCP tools handler (depends on database, topic, and AI summarization)
        self.mcp_tools_handler = MCPToolsHandler(
            self.database_manager, self.topic_manager, self.ai_summarization_manager
        )
        await self.mcp_tools_handler.initialize()

        # 9. Search handlers (depends on vector search, database, and AI client)
        self.search_handlers = SearchHandlers(
            self.vector_search_manager, self.database_manager, self.ai_client_manager
        )
        await self.search_handlers.initialize()

    # Convenience methods for common operations

    async def summarize_meeting(self, meeting_id: str, content: str, style: str = "brief") -> Dict[str, Any]:
        """
        Summarize a meeting.

        Args:
            meeting_id: Unique meeting identifier
            content: Meeting content/transcript
            style: Summary style ("brief", "detailed", "executive")

        Returns:
            Summary result with topics and action items
        """
        try:
            # Generate summary
            summary = await self.ai_summarization_manager.generate_summary(meeting_id, style)

            # Detect topics
            topics = await self.topic_manager.detect_topics(content)

            # Extract action items
            action_items = await self.ai_summarization_manager.extract_action_items(content)

            # Generate insights
            participants = []  # Extract from content if needed
            insights = await self.ai_summarization_manager.generate_insights(topics, action_items, participants)

            return {
                "summary": summary,
                "topics": topics,
                "action_items": action_items,
                "insights": insights,
                "meeting_id": meeting_id
            }

        except Exception as e:
            self.logger.error(f"Error summarizing meeting {meeting_id}: {e}")
            return {
                "error": str(e),
                "summary": f"Error generating summary: {str(e)}",
                "topics": [],
                "action_items": []
            }

    async def process_voice_command(self, voice_input: str, context: Dict[str, Any] = None) -> str:
        """
        Process a voice command.

        Args:
            voice_input: Voice command string
            context: Additional context

        Returns:
            Command execution result
        """
        try:
            if not self.voice_commands_manager:
                return "Voice commands not available"

            result = await self.voice_commands_manager.process_command(voice_input, context or {})
            return result

        except Exception as e:
            self.logger.error(f"Error processing voice command '{voice_input}': {e}")
            return f"Error processing voice command: {str(e)}"

    async def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Perform semantic search.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Search results
        """
        try:
            if not self.search_handlers:
                return []

            results = await self.search_handlers.semantic_search(query, None)
            return results[:limit]

        except Exception as e:
            self.logger.error(f"Error performing semantic search for '{query}': {e}")
            return []

    async def get_meeting_context(self, meeting_id: str) -> Dict[str, Any]:
        """
        Get current meeting context.

        Args:
            meeting_id: Meeting ID

        Returns:
            Meeting context information
        """
        try:
            context = {
                "meeting_id": meeting_id,
                "conversation_context": self.ai_summarization_manager.get_conversation_context() if self.ai_summarization_manager else {},
                "topic_status": self.topic_manager.get_topic_manager_status() if self.topic_manager else {},
                "ui_status": self.ui_state_manager.get_ui_status() if self.ui_state_manager else {},
                "vector_index_stats": await self.vector_search_manager.get_index_stats() if self.vector_search_manager else {}
            }

            return context

        except Exception as e:
            self.logger.error(f"Error getting meeting context for {meeting_id}: {e}")
            return {"error": str(e)}

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get service health status.

        Returns:
            Health status information
        """
        return {
            "initialized": self.initialized,
            "database_available": self.database_manager is not None,
            "vector_search_available": self.vector_search_manager is not None,
            "ai_clients_available": self.ai_client_manager is not None,
            "ai_summarization_available": self.ai_summarization_manager is not None,
            "topic_manager_available": self.topic_manager is not None,
            "ui_state_manager_available": self.ui_state_manager is not None,
            "voice_commands_available": self.voice_commands_manager is not None,
            "mcp_tools_available": self.mcp_tools_handler is not None,
            "search_handlers_available": self.search_handlers is not None
        }


# Global service instance
_summarizer_service: Optional[SummarizerService] = None


def get_summarizer_service() -> SummarizerService:
    """Get or create global summarizer service instance."""
    global _summarizer_service

    if _summarizer_service is None:
        _summarizer_service = SummarizerService()

    return _summarizer_service


async def initialize_summarizer_service() -> SummarizerService:
    """Initialize summarizer service."""
    service = get_summarizer_service()

    if not service.initialized:
        success = await service.initialize()
        if not success:
            raise RuntimeError("Failed to initialize summarizer service")

    return service


async def shutdown_summarizer_service():
    """Shutdown summarizer service."""
    global _summarizer_service

    if _summarizer_service:
        await _summarizer_service.cleanup()
        _summarizer_service = None


@asynccontextmanager
async def summarizer_lifespan():
    """Async context manager for summarizer service lifecycle."""
    service = get_summarizer_service()
    await service.initialize()
    try:
        yield service
    finally:
        await service.cleanup()