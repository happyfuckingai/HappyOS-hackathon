from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

try:
    from backend.modules.database import get_db, Agent, AgentProcess as DBAgentProcess
    from backend.modules.auth import get_current_user
    from backend.modules.models import (
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from backend.modules.database import get_db, Agent, AgentProcess as DBAgentProcess
    from backend.modules.auth import get_current_user
    from backend.modules.models import (
    Agent as AgentModel, AgentStartRequest, User as UserModel,
    AgentConfig, AgentStatus, AgentProcess, ResourceMetrics
)

router = APIRouter()

@router.get("/agents", response_model=List[AgentModel])
async def get_agents(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Get all agents"""
    agents = db.query(Agent).all()
    return [AgentModel(id=a.id, name=a.name, status=a.status, created_at=a.created_at, participant_id=a.participant_id) for a in agents]

@router.post("/agents/start", response_model=AgentProcess)
async def start_agent(
    config: AgentConfig, 
    db: Session = Depends(get_db), 
    current_user: UserModel = Depends(get_current_user)
):
    """Start a new agent with real process management"""
    try:
        # Create agent record first
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id, 
            name=config.name, 
            status="starting", 
            participant_id=getattr(config, 'participant_id', None)
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Start the actual process
        agent_process = await agent_process_manager.start_agent(agent_id, config)
        
        # Update agent status
        agent.status = "running"
        db.commit()
        
        return agent_process
        
    except Exception as e:
        # Update agent status to failed if it was created
        if 'agent' in locals():
            agent.status = "failed"
            db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}"
        )

@router.delete("/agents/{agent_id}")
async def stop_agent(
    agent_id: str, 
    force: bool = False,
    db: Session = Depends(get_db), 
    current_user: UserModel = Depends(get_current_user)
):
    """Stop an agent and its processes"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    
    # Find and stop all processes for this agent
    processes = db.query(DBAgentProcess).filter(
        DBAgentProcess.agent_id == agent_id,
        DBAgentProcess.status.in_(["starting", "running"])
    ).all()
    
    stopped_processes = []
    for process in processes:
        success = await agent_process_manager.stop_agent(process.id, force=force)
        if success:
            stopped_processes.append(process.id)
    
    # Update agent status
    agent.status = "stopped"
    db.commit()
    
    return {
        "message": f"Agent stopped",
        "agent_id": agent_id,
        "stopped_processes": stopped_processes,
        "force": force
    }

@router.get("/agents/{agent_id}/status", response_model=AgentModel)
async def get_agent_status(
    agent_id: str, 
    db: Session = Depends(get_db), 
    current_user: UserModel = Depends(get_current_user)
):
    """Get agent status"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentModel(id=agent.id, name=agent.name, status=agent.status, created_at=agent.created_at, participant_id=agent.participant_id)

@router.get("/agents/{agent_id}/processes", response_model=List[AgentStatus])
async def get_agent_processes(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all processes for an agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    
    processes = db.query(DBAgentProcess).filter(
        DBAgentProcess.agent_id == agent_id
    ).all()
    
    process_statuses = []
    for process in processes:
        status = await agent_process_manager.get_agent_status(process.id)
        if status:
            process_statuses.append(status)
    
    return process_statuses

@router.get("/agents/active", response_model=List[AgentStatus])
async def get_active_agents(
    current_user: UserModel = Depends(get_current_user)
):
    """Get all active agent processes"""
    return await agent_process_manager.list_active_agents()

@router.post("/agents/restart-failed")
async def restart_failed_agents(
    current_user: UserModel = Depends(get_current_user)
):
    """Restart failed agents that have restart policy enabled"""
    restarted = await agent_process_manager.restart_failed_agents()
    return {
        "message": f"Restarted {len(restarted)} failed agents",
        "restarted_agents": restarted
    }

@router.post("/agents/{process_id}/heartbeat")
async def report_heartbeat(
    process_id: str,
    heartbeat_data: Dict[str, Any] = Body(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Report heartbeat from an agent process"""
    try:
        heartbeat = HeartbeatData(
            process_id=process_id,
            timestamp=datetime.utcnow(),
            status=heartbeat_data.get("status", "healthy"),
            resource_usage=heartbeat_data.get("resource_usage"),
            custom_metrics=heartbeat_data.get("custom_metrics"),
            error_message=heartbeat_data.get("error_message")
        )
        
        success = await agent_heartbeat_service.report_heartbeat(heartbeat)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Process not found"
            )
        
        return {"message": "Heartbeat recorded", "timestamp": heartbeat.timestamp}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record heartbeat: {str(e)}"
        )

@router.get("/agents/{process_id}/health")
async def get_agent_health(
    process_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get health information for a specific agent process"""
    health_info = await agent_heartbeat_service.get_agent_health(process_id)
    
    if not health_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found"
        )
    
    return health_info

@router.get("/agents/health/all")
async def get_all_agent_health(
    current_user: UserModel = Depends(get_current_user)
):
    """Get health information for all agents"""
    health_reports = await agent_heartbeat_service.get_all_agent_health()
    return {
        "health_reports": health_reports,
        "total_agents": len(health_reports),
        "timestamp": datetime.utcnow()
    }

# New orchestration endpoints

@router.post("/agents/orchestration/mission")
async def execute_mission(
    mission: Dict[str, Any] = Body(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Execute a mission using the A2A orchestration system"""
    try:
        orchestration_service = await get_orchestration_service()
        result = await orchestration_service.execute_mission(mission)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission execution failed: {str(e)}"
        )

@router.get("/agents/orchestration/status")
async def get_orchestration_status(
    current_user: UserModel = Depends(get_current_user)
):
    """Get comprehensive orchestration system status"""
    try:
        orchestration_service = await get_orchestration_service()
        return await orchestration_service.get_system_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orchestration status: {str(e)}"
        )

@router.get("/agents/orchestration/workflows")
async def list_active_workflows(
    current_user: UserModel = Depends(get_current_user)
):
    """List all active workflows"""
    try:
        orchestration_service = await get_orchestration_service()
        workflows = await orchestration_service.list_active_workflows()
        return {
            "workflows": workflows,
            "total_active": len(workflows),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflows: {str(e)}"
        )

@router.get("/agents/orchestration/workflows/{workflow_id}")
async def get_workflow_status(
    workflow_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get status of a specific workflow"""
    try:
        orchestration_service = await get_orchestration_service()
        workflow_status = await orchestration_service.get_workflow_status(workflow_id)
        
        if not workflow_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        return workflow_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}"
        )

@router.delete("/agents/orchestration/workflows/{workflow_id}")
async def stop_workflow(
    workflow_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Stop a specific workflow"""
    try:
        orchestration_service = await get_orchestration_service()
        success = await orchestration_service.stop_workflow(workflow_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found or could not be stopped"
            )
        
        return {
            "message": f"Workflow {workflow_id} stopped successfully",
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop workflow: {str(e)}"
        )

@router.post("/agents/orchestration/jobs")
async def enqueue_agent_job(
    job_data: Dict[str, Any] = Body(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Enqueue a job for agent processing"""
    try:
        job_type = job_data.get("job_type")
        agent_type = job_data.get("agent_type")
        payload = job_data.get("payload", {})
        priority = job_data.get("priority", 5)
        
        if not job_type or not agent_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="job_type and agent_type are required"
            )
        
        orchestration_service = await get_orchestration_service()
        job_id = await orchestration_service.enqueue_agent_job(job_type, agent_type, payload, priority)
        
        if not job_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue job"
            )
        
        return {
            "job_id": job_id,
            "job_type": job_type,
            "agent_type": agent_type,
            "priority": priority,
            "timestamp": datetime.utcnow()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue job: {str(e)}"
        )

@router.get("/agents/orchestration/agents")
async def list_orchestration_agents(
    current_user: UserModel = Depends(get_current_user)
):
    """List all agents managed by the orchestration system"""
    try:
        orchestration_service = await get_orchestration_service()
        agents = await orchestration_service.list_agents()
        return {
            "agents": agents,
            "total_agents": len(agents),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list orchestration agents: {str(e)}"
        )

@router.get("/agents/orchestration/agents/{agent_id}")
async def get_orchestration_agent_status(
    agent_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get detailed status of a specific orchestration agent"""
    try:
        orchestration_service = await get_orchestration_service()
        agent_status = await orchestration_service.get_agent_status(agent_id)
        
        if not agent_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return agent_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}"
        )