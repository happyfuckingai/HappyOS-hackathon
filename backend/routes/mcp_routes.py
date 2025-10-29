from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
import time
from ..modules.auth import get_current_user
from ..modules.models import SummarizeRequest, SummarizeResponse, ToolInfo, User as UserModel
from ..services.integration.mcp_integration import (
    get_mcp_service,
    initialize_mcp_service,
    shutdown_mcp_service,
    summarize_meeting,
    get_available_tools,
    process_file_for_summary,
    get_conversation_context,
    segment_topics_in_conversation,
    process_voice_command,
    get_mcp_health
)
from ..services.summarizer_client import SummarizerClient

logger = logging.getLogger(__name__)
router = APIRouter()
_summarizer_client = SummarizerClient()

PERSONA_ALIASES = {
    "po": "PO",
    "product_owner": "PO",
    "eng": "Eng",
    "engineer": "Eng",
    "engineering": "Eng",
    "cs": "CS",
    "customer_success": "CS",
    "exec": "Exec",
    "executive": "Exec",
}
VALID_PERSONAS = {"PO", "Eng", "CS", "Exec"}


def _normalize_persona(persona: str) -> Optional[str]:
    if not persona:
        return None
    if persona in VALID_PERSONAS:
        return persona
    lowered = persona.strip().lower()
    return PERSONA_ALIASES.get(lowered)

# Lifecycle events for MCP service
@router.on_event("startup")
async def startup_event():
    """Initialize MCP service on startup"""
    try:
        await initialize_mcp_service()
        logger.info("MCP service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MCP service: {e}")
        # Don't raise here, let the application continue but log the error

@router.on_event("shutdown")
async def shutdown_event():
    """Shutdown MCP service on application shutdown"""
    try:
        await shutdown_mcp_service()
        logger.info("MCP service shutdown successfully")
    except Exception as e:
        logger.error(f"Error during MCP service shutdown: {e}")

@router.post("/mcp/summarize", response_model=SummarizeResponse)
async def summarize(
    request: SummarizeRequest,
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Summarize meeting content using MCP server

    This endpoint calls the MCP summarizer server to generate
    AI-driven summaries of meeting transcripts.
    """
    try:
        logger.info(f"Generating summary for meeting: {request.meeting_id}")

        # Run summarization in background to avoid blocking
        result = await summarize_meeting(request.meeting_id, request.content)

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )

        return SummarizeResponse(
            summary=result.get("summary", ""),
            topics=result.get("topics", []),
            action_items=result.get("action_items", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.get("/mcp/meetings/{meeting_id}/personas/{persona}/context")
async def get_persona_context(
    meeting_id: str,
    persona: str,
    current_user: UserModel = Depends(get_current_user),
):
    """
    Fetch the latest conversation context for a given meeting and persona.
    """
    normalized_persona = _normalize_persona(persona)
    if not normalized_persona:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid persona '{persona}'. Expected one of: {', '.join(sorted(VALID_PERSONAS))}",
        )

    try:
        context = await _summarizer_client.get_conversation_context_async(
            meeting_id=meeting_id,
            persona=normalized_persona,
        )
        return {
            "meeting_id": meeting_id,
            "persona": normalized_persona,
            "context": context,
        }
    except Exception as exc:
        logger.error("Failed to fetch context for %s/%s: %s", meeting_id, normalized_persona, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation context: {exc}",
        )


@router.get("/mcp/meetings/{meeting_id}/visuals")
async def get_meeting_visuals(
    meeting_id: str,
    current_user: UserModel = Depends(get_current_user),
):
    """
    Fetch the latest visuals (phase bars, topics, action widgets, artifacts) for a meeting.
    """
    try:
        visuals = await _summarizer_client.get_visuals_async(meeting_id=meeting_id)
        return {
            "meeting_id": meeting_id,
            "visuals": visuals,
        }
    except Exception as exc:
        logger.error("Failed to fetch visuals for %s: %s", meeting_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch meeting visuals: {exc}",
        )

@router.get("/mcp/tools", response_model=List[ToolInfo])
async def get_tools(current_user: UserModel = Depends(get_current_user)):
    """
    Get list of available MCP tools

    Returns information about all tools available in the MCP server.
    """
    try:
        logger.info("Fetching available MCP tools")
        tools = await get_available_tools()

        return [
            ToolInfo(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"]
            )
            for tool in tools
        ]

    except Exception as e:
        logger.error(f"Error fetching tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available tools: {str(e)}"
        )

@router.post("/mcp/process-file")
async def process_file(
    file_path: str,
    action: str = "summarize",
    current_user: UserModel = Depends(get_current_user)
):
    """
    Process a file for summarization or analysis

    Supports various file types including PDF, images, and videos.
    """
    try:
        logger.info(f"Processing file: {file_path} with action: {action}")

        result = await process_file_for_summary(file_path, action)

        return {
            "success": True,
            "result": result,
            "file_path": file_path,
            "action": action
        }

    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.get("/mcp/context")
async def get_context(current_user: UserModel = Depends(get_current_user)):
    """
    Get current conversation context

    Returns information about the current conversation state,
    active topics, and context.
    """
    try:
        logger.info("Fetching conversation context")
        context = await get_conversation_context()

        return {
            "success": True,
            "context": context
        }

    except Exception as e:
        logger.error(f"Error fetching context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch context: {str(e)}"
        )

@router.post("/mcp/segment-topics")
async def segment_topics(
    transcript: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Segment conversation into topics

    Analyzes conversation transcript and identifies different topics
    for better organization and navigation.
    """
    try:
        logger.info("Segmenting conversation into topics")
        result = await segment_topics_in_conversation(transcript)

        return {
            "success": True,
            "result": result
        }

    except Exception as e:
        logger.error(f"Error segmenting topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to segment topics: {str(e)}"
        )

@router.post("/mcp/voice-command")
async def process_voice(
    voice_input: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Process voice command for topic management

    Supports natural language voice commands for interacting
    with the topic management system.
    """
    try:
        logger.info(f"Processing voice command: {voice_input}")
        result = await process_voice_command(voice_input)

        return {
            "success": True,
            "result": result,
            "voice_input": voice_input
        }

    except Exception as e:
        logger.error(f"Error processing voice command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process voice command: {str(e)}"
        )

@router.get("/mcp/health")
async def health_check(current_user: UserModel = Depends(get_current_user)):
    """
    Get MCP service health status

    Returns detailed health information about the MCP server connection,
    available tools, and service status.
    """
    try:
        logger.info("Checking MCP service health")
        health = await get_mcp_health()

        return {
            "success": True,
            "health": health,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error checking health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check health: {str(e)}"
        )

@router.post("/mcp/call-tool")
async def call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """
    Call a specific MCP tool directly

    Allows direct access to any MCP tool with custom parameters.
    Useful for advanced use cases and debugging.
    """
    try:
        logger.info(f"Calling MCP tool: {tool_name} with arguments: {arguments}")

        service = get_mcp_service()
        result = await service.call_tool(tool_name, arguments)

        content = await service.get_tool_result_content(result)

        return {
            "success": True,
            "tool_name": tool_name,
            "result": content,
            "arguments": arguments
        }

    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call tool: {str(e)}"
        )
