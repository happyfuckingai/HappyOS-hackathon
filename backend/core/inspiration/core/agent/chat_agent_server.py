"""
🚀 CHAT AGENT SERVER
Exposes the ChatAgent via a FastAPI server.
"""
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.agent.chat_agent import chat_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HappyOS Chat Agent",
    description="Handles chat messages and provides responses.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    conversation_id: str
    user_id: str
    organization_id: str
    user_input: str

class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    user_id: str
    organization_id: str
    timestamp: float

@app.on_event("startup")
async def startup_event():
    logger.info("Chat Agent server is starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Chat Agent server is shutting down...")

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handle a chat message and return a response.
    """
    try:
        logger.info(f"Processing chat request for conversation {request.conversation_id}")

        response = await chat_agent.handle_message(
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            organization_id=request.organization_id,
            user_input=request.user_input
        )

        return ChatResponse(**response)
    except Exception as e:
        logger.error(f"Error in /chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "chat-agent",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

