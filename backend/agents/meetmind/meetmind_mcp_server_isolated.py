"""
MeetMind MCP Server - Isolated Implementation

MCP server for meeting intelligence tools that uses ONLY HappyOS SDK
for communication with the core platform. No direct backend imports allowed.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# MCP imports
from mcp.server import FastMCP
from mcp.types import Tool, TextContent

# HappyOS SDK imports - ONLY allowed imports
from happyos_sdk import (
    A2AClient, create_a2a_client, create_service_facades,
    DatabaseFacade, StorageFacade, ComputeFacade, SearchFacade,
    SecretsFacade, CacheFacade, HappyOSSDKError, A2AError
)

# Local MeetMind imports
from backend.agents.meetmind.meetmind_agent import MeetMindAgent, create_meetmind_agent
from backend.agents.meetmind.a2a_messages import MeetMindA2AMessageFactory, MeetMindMessageType

logger = logging.getLogger(__name__)


@dataclass
class MCPToolResult:
    """Result from MCP tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    
    def to_text_content(self) -> List[TextContent]:
        """Convert to MCP TextContent."""
        if self.success:
            content = json.dumps({
                "success": True,
                "data": self.data,
                "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat()
            }, indent=2)
        else:
            content = json.dumps({
                "success": False,
                "error": self.error,
                "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat()
            }, indent=2)
        
        return [TextContent(type="text", text=content)]


class MeetMindMCPServer:
    """
    MeetMind MCP Server - Isolated implementation.
    
    Provides MCP tools for meeting intelligence:
    - Meeting management (start, end, status)
    - Transcript processing
    - Summary generation
    - Action item extraction
    - Topic detection
    - Participant analysis
    
    Uses ONLY HappyOS SDK for communication with core platform.
    """
    
    def __init__(self, 
                 server_name: str = "meetmind-mcp-server",
                 host: str = "0.0.0.0",
                 port: int = 8150):
        """
        Initialize MeetMind MCP server.
        
        Args:
            server_name: Name of the MCP server
            host: Host to bind to
            port: Port to bind to
        """
        self.server_name = server_name
        self.host = host
        self.port = port
        
        # Create MCP server
        self.mcp = FastMCP(
            name=server_name,
            host=host,
            port=port,
            mount_path="/mcp"
        )
        
        # MeetMind agent
        self.meetmind_agent: Optional[MeetMindAgent] = None
        
        # A2A client and services
        self.a2a_client: Optional[A2AClient] = None
        self.services: Dict[str, Any] = {}
        
        # Server state
        self.is_initialized = False
        
        logger.info(f"MeetMind MCP Server created: {server_name}")
    
    async def initialize(self):
        """Initialize the MCP server and MeetMind agent."""
        if self.is_initialized:
            return
        
        try:
            # Create MeetMind agent
            self.meetmind_agent = create_meetmind_agent(
                agent_id=f"meetmind_mcp_{uuid.uuid4().hex[:8]}",
                transport_type="inprocess"
            )
            
            # Initialize the agent
            await self.meetmind_agent.initialize()
            
            # Get A2A client and services from agent
            self.a2a_client = self.meetmind_agent.a2a_client
            self.services = self.meetmind_agent.services
            
            # Register MCP tools
            await self._register_mcp_tools()
            
            self.is_initialized = True
            logger.info("MeetMind MCP Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MeetMind MCP Server: {e}")
            raise HappyOSSDKError(f"MCP Server initialization failed: {e}")
    
    async def shutdown(self):
        """Shutdown the MCP server."""
        if not self.is_initialized:
            return
        
        try:
            # Shutdown MeetMind agent
            if self.meetmind_agent:
                await self.meetmind_agent.shutdown()
            
            self.is_initialized = False
            logger.info("MeetMind MCP Server shutdown successfully")
            
        except Exception as e:
            logger.error(f"Error during MCP server shutdown: {e}")
    
    async def _register_mcp_tools(self):
        """Register MCP tools."""
        
        @self.mcp.tool()
        async def start_meeting(
            meeting_id: str,
            participants: List[str],
            agenda: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> str:
            """Start a new meeting session."""
            try:
                result = await self.meetmind_agent.start_meeting(
                    meeting_id=meeting_id,
                    participants=participants,
                    agenda=agenda,
                    metadata=metadata
                )
                
                tool_result = MCPToolResult(
                    success=True,
                    data=result,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": tool_result.timestamp
                })
                
            except Exception as e:
                logger.error(f"start_meeting tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def add_transcript_chunk(
            meeting_id: str,
            content: str,
            speaker: Optional[str] = None,
            timestamp: Optional[str] = None,
            is_final: bool = False
        ) -> str:
            """Add a transcript chunk to an active meeting."""
            try:
                result = await self.meetmind_agent.add_transcript_chunk(
                    meeting_id=meeting_id,
                    content=content,
                    speaker=speaker,
                    timestamp=timestamp,
                    is_final=is_final
                )
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"add_transcript_chunk tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def generate_meeting_summary(
            meeting_id: str,
            summary_style: str = "executive"
        ) -> str:
            """Generate a meeting summary."""
            try:
                result = await self.meetmind_agent.generate_meeting_summary(
                    meeting_id=meeting_id,
                    summary_style=summary_style
                )
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"generate_meeting_summary tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def extract_action_items(meeting_id: str) -> str:
            """Extract action items from a meeting."""
            try:
                result = await self.meetmind_agent.extract_action_items(meeting_id)
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"extract_action_items tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def detect_topics(meeting_id: str) -> str:
            """Detect topics in a meeting."""
            try:
                result = await self.meetmind_agent.detect_topics(meeting_id)
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"detect_topics tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def end_meeting(meeting_id: str) -> str:
            """End a meeting session."""
            try:
                result = await self.meetmind_agent.end_meeting(meeting_id)
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"end_meeting tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def get_meeting_status(meeting_id: str) -> str:
            """Get the current status of a meeting."""
            try:
                result = await self.meetmind_agent.get_meeting_status(meeting_id)
                
                return json.dumps({
                    "success": True,
                    "data": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"get_meeting_status tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def analyze_meeting_participants(
            meeting_id: str,
            analysis_type: str = "engagement"
        ) -> str:
            """Analyze meeting participants."""
            try:
                # Request participant analysis via A2A protocol
                analysis_request = {
                    "meeting_id": meeting_id,
                    "analysis_type": analysis_type
                }
                
                response = await self.a2a_client.send_request(
                    recipient_id="ai_analysis_service",
                    action="analyze_participants",
                    data=analysis_request
                )
                
                return json.dumps({
                    "success": response.get("success", True),
                    "data": response,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"analyze_meeting_participants tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def search_meeting_content(
            meeting_id: str,
            query: str,
            search_type: str = "semantic"
        ) -> str:
            """Search meeting content."""
            try:
                # Use search service facade
                search_request = {
                    "query": query,
                    "filters": {
                        "meeting_id": meeting_id,
                        "data_type": "meeting_session"
                    },
                    "search_type": search_type
                }
                
                if search_type == "semantic":
                    # Use hybrid search for semantic queries
                    results = await self.services["search"].search(
                        query=query,
                        filters=search_request["filters"]
                    )
                else:
                    # Use regular search
                    results = await self.services["search"].search(
                        query=query,
                        filters=search_request["filters"]
                    )
                
                return json.dumps({
                    "success": True,
                    "data": {
                        "query": query,
                        "results": results,
                        "search_type": search_type
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"search_meeting_content tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def financial_compliance_check(
            meeting_id: str,
            financial_topics: List[str],
            compliance_requirements: List[str]
        ) -> str:
            """Perform financial compliance check for cross-module workflow."""
            try:
                # Create financial compliance check message
                message = MeetMindA2AMessageFactory.create_financial_compliance_check_message(
                    meeting_id=meeting_id,
                    financial_topics=financial_topics,
                    compliance_requirements=compliance_requirements
                )
                
                # Send to Agent Svea ERPNext module for compliance validation
                response = await self.a2a_client.send_request(
                    recipient_id="agent_svea_erp",
                    action="validate_financial_compliance",
                    data=message["data"]
                )
                
                return json.dumps({
                    "success": response.get("success", True),
                    "data": response,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"financial_compliance_check tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def meeting_financial_analysis(
            meeting_id: str,
            financial_decisions: List[Dict[str, Any]]
        ) -> str:
            """Perform meeting-driven financial analysis workflow."""
            try:
                # Create meeting financial analysis message
                message = MeetMindA2AMessageFactory.create_meeting_financial_analysis_message(
                    meeting_id=meeting_id,
                    financial_decisions=financial_decisions
                )
                
                # Send to Felicia's Finance modules for analysis
                crypto_response = await self.a2a_client.send_request(
                    recipient_id="felicias_finance_crypto",
                    action="analyze_financial_decisions",
                    data=message["data"]
                )
                
                bank_response = await self.a2a_client.send_request(
                    recipient_id="felicias_finance_bank",
                    action="analyze_financial_decisions",
                    data=message["data"]
                )
                
                # Combine responses
                combined_analysis = {
                    "crypto_analysis": crypto_response,
                    "banking_analysis": bank_response,
                    "meeting_id": meeting_id
                }
                
                return json.dumps({
                    "success": True,
                    "data": combined_analysis,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"meeting_financial_analysis tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        @self.mcp.tool()
        async def get_server_health() -> str:
            """Get standardized MCP server health status."""
            try:
                # Import HappyOS SDK health monitoring
                from happyos_sdk.health_monitoring import get_health_monitor
                from happyos_sdk.metrics_collection import get_metrics_collector
                
                # Get or create health monitor
                health_monitor = get_health_monitor(
                    agent_type="meetmind",
                    agent_id=self.meetmind_agent.agent_id if self.meetmind_agent else "meetmind_server",
                    version="1.0.0"
                )
                
                # Register dependency checks if not already registered
                if not hasattr(health_monitor, '_meetmind_checks_registered'):
                    # MeetMind agent check
                    health_monitor.register_dependency_check(
                        "meetmind_agent",
                        lambda: {
                            "status": "available" if (self.meetmind_agent and self.meetmind_agent.is_initialized) else "unavailable"
                        }
                    )
                    
                    # A2A client check
                    health_monitor.register_dependency_check(
                        "a2a_client",
                        lambda: {
                            "status": "available" if (self.a2a_client and self.a2a_client.is_connected) else "unavailable"
                        }
                    )
                    
                    # Services availability check
                    health_monitor.register_dependency_check(
                        "services",
                        lambda: {
                            "status": "available" if self.services else "unavailable"
                        }
                    )
                    
                    health_monitor._meetmind_checks_registered = True
                
                # Get standardized health response
                health_response = await health_monitor.get_health_status()
                
                # Add MeetMind specific metrics
                if self.meetmind_agent:
                    health_response.agent_metrics.active_connections = len(self.meetmind_agent.active_meetings)
                
                # Record health metrics
                metrics_collector = get_metrics_collector("meetmind", health_response.agent_id)
                await metrics_collector.record_health_status(
                    health_response.status.value,
                    health_response.response_time_ms
                )
                
                # Return standardized health response as JSON string
                return json.dumps({
                    "success": True,
                    "data": health_response.to_dict(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as e:
                logger.error(f"get_server_health tool error: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    def get_mcp_app(self):
        """Get the FastAPI app for the MCP server."""
        return self.mcp.sse_app()
    
    async def run(self):
        """Run the MCP server."""
        if not self.is_initialized:
            await self.initialize()
        
        # The MCP server will be run by the FastAPI app
        logger.info(f"MeetMind MCP Server ready at {self.host}:{self.port}")


# Factory function for creating MCP server
def create_meetmind_mcp_server(server_name: str = "meetmind-mcp-server",
                              host: str = "0.0.0.0",
                              port: int = 8150) -> MeetMindMCPServer:
    """
    Factory function to create MeetMind MCP server.
    
    Args:
        server_name: Name of the MCP server
        host: Host to bind to
        port: Port to bind to
        
    Returns:
        Configured MeetMind MCP server
    """
    return MeetMindMCPServer(server_name, host, port)


# Global server instance
meetmind_mcp_server = None


async def get_meetmind_mcp_server() -> MeetMindMCPServer:
    """Get or create the global MeetMind MCP server instance."""
    global meetmind_mcp_server
    
    if meetmind_mcp_server is None:
        meetmind_mcp_server = create_meetmind_mcp_server()
        await meetmind_mcp_server.initialize()
    
    return meetmind_mcp_server


if __name__ == "__main__":
    # Run the MCP server standalone
    import uvicorn
    
    async def main():
        server = create_meetmind_mcp_server()
        await server.initialize()
        
        # Create FastAPI app
        app = server.get_mcp_app()
        
        # Run with uvicorn
        config = uvicorn.Config(
            app=app,
            host=server.host,
            port=server.port,
            log_level="info"
        )
        
        server_instance = uvicorn.Server(config)
        await server_instance.serve()
    
    asyncio.run(main())