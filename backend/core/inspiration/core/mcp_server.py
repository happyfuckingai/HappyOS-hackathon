"""
🚀 HappyOS Core MCP Server
FastAPI-based MCP server that exposes all available skills as HTTP endpoints.
"""
import logging
import json
import os
import sys
import importlib
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="HappyOS MCP Server",
    description="Provides access to all HappyOS skills and core functionalities via HTTP endpoints.",
    version="1.0.0"
)

# Store for dynamically registered tools
mcp_tools = {}

def discover_and_register_skills():
    """
    Dynamically discovers and registers all skill modules found in the 'skills' directory.
    A skill is recognized if it's a directory containing a '_module.py' file.
    """
    logger.info("🔧 Discovering and registering HappyOS skills as FastAPI endpoints...")
    skills_dir = Path(__file__).resolve().parent.parent / "skills"

    if not skills_dir.is_dir():
        logger.warning(f"Skills directory not found at {skills_dir}. No skills will be loaded.")
        return

    for skill_path in skills_dir.iterdir():
        if skill_path.is_dir():
            module_file = skill_path / "_module.py"
            if module_file.is_file():
                skill_name = skill_path.name
                module_name = f"app.skills.{skill_name}._module"
                try:
                    # Dynamically import the module
                    skill_module = importlib.import_module(module_name)

                    # The module should have a 'register_endpoints' function
                    if hasattr(skill_module, 'register_endpoints'):
                        skill_module.register_endpoints(app)
                        logger.info(f"✅ Successfully registered skill: {skill_name}")
                    else:
                        logger.warning(f"⚠️ Skill '{skill_name}' has a _module.py but no 'register_endpoints' function.")
                except Exception as e:
                    logger.error(f"❌ Failed to register skill '{skill_name}': {e}", exc_info=True)

# Pydantic models for API requests
class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

class ProcessRequest(BaseModel):
    request_text: str

# --- Core FastAPI Endpoints ---

@app.get("/health")
async def health_check():
    """Performs a health check on the HappyOS Core MCP server."""
    return {
        "success": True,
        "status": "healthy",
        "service": "happyos-core-mcp",
        "available_endpoints": [
            "/health",
            "/skills",
            "/process_request",
            "/execute_tool"
        ]
    }

@app.get("/skills")
async def list_skills():
    """Lists all dynamically loaded skills and their endpoints."""
    skills_info = {}

    # Get all routes from the FastAPI app
    for route in app.routes:
        if hasattr(route, 'path') and route.path.startswith('/skills/'):
            # Extract skill name from path
            path_parts = route.path.strip('/').split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'skills':
                skill_name = path_parts[1]
                if skill_name not in skills_info:
                    skills_info[skill_name] = []
                skills_info[skill_name].append({
                    "path": route.path,
                    "methods": getattr(route, 'methods', [])
                })

    return {
        "success": True,
        "skills": skills_info
    }

@app.post("/process_request")
async def process_request(request: ProcessRequest):
    """Process a user request using the ultimate system."""
    try:
        from app.core.ultimate_system import ultimate_system
        response = await ultimate_system.handle_user_request(request.request_text)
        return {
            "success": True,
            "response": response
        }
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/execute_tool")
async def execute_tool(request: ToolRequest):
    """Execute a specific tool by name."""
    try:
        if request.tool_name not in mcp_tools:
            raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")

        tool_func = mcp_tools[request.tool_name]
        result = await tool_func(**request.parameters)
        return {
            "success": True,
            "tool": request.tool_name,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error executing tool {request.tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing tool: {str(e)}")

# --- Server Lifespan ---
@app.on_event("startup")
async def startup_event():
    """Server startup logic."""
    logger.info("🚀 HappyOS Core MCP Server is starting up...")
    discover_and_register_skills()
    logger.info("✅ HappyOS Core MCP Server startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Server shutdown logic."""
    logger.info("👋 HappyOS Core MCP Server is shutting down...")

# This FastAPI app can be run directly or imported by a main server runner.
if __name__ == '__main__':
    import uvicorn
    logger.info("Running HappyOS Core MCP Server in standalone mode for testing.")

    # Add happyos root to path for imports to work
    happyos_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(happyos_root))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8055,
        log_level="info"
    )
