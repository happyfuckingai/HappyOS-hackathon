"""
🚀 ORCHESTRATOR AGENT SERVER
Exposes the OrchestratorAgent via a FastAPI server.
"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.orchestrator.orchestrator_agent import orchestrator_agent
from app.core.database.persistence_manager import initialize_persistence, cleanup_persistence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HappyOS Orchestrator Agent",
    description="The 'brain' that decides which tool to use.",
    version="1.0.0"
)

class OrchestratorRequest(BaseModel):
    user_id: str
    conversation_id: str
    user_input: str

@app.on_event("startup")
async def startup_event():
    logger.info("Orchestrator Agent server is starting up...")
    await initialize_persistence()
    logger.info("Persistence layer initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Orchestrator Agent server is shutting down...")
    await cleanup_persistence()
    logger.info("Persistence layer cleaned up.")

@app.post("/decide_and_execute")
async def decide_and_execute(request: OrchestratorRequest):
    """
    Main endpoint for deciding which tool to use and executing it.
    """
    try:
        response = await orchestrator_agent.decide_and_execute(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            user_input=request.user_input
        )
        return response
    except Exception as e:
        logger.error(f"Error in /decide_and_execute endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
