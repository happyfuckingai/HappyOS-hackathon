import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from adk.adk_integration import ADKIntegration

adk_integration = ADKIntegration()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await adk_integration.initialize()
    yield
    # Shutdown (if needed in the future)
    pass

app = FastAPI(
    title="ADK Orchestrator MCP Server",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "ADK Orchestrator is running"}

@app.get("/status")
async def get_status():
    return await adk_integration.get_system_status()

@app.post("/handle_request")
async def handle_request(request: dict):
    request_type = request.get("type")
    payload = request.get("payload")

    if not request_type or not payload:
        raise HTTPException(status_code=400, detail="Invalid request format")

    if request_type == "banking":
        return await adk_integration.handle_banking_request(payload)
    elif request_type == "crypto":
        return await adk_integration.handle_crypto_request(payload)
    elif request_type == "financial_analysis":
        return await adk_integration.analyze_financial_query(payload.get("query"))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown request type: {request_type}")
