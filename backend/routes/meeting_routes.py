from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import json
import uuid
import os
try:
    from backend.modules.database import get_db, Meeting, User
    from backend.modules.auth import get_current_user
    from backend.modules.models import (
        Meeting as MeetingModel,
        MeetingCreateRequest,
        User as UserModel,
        AgentSessionRequest,
        AgentSessionResponse,
    )
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from backend.modules.database import get_db, Meeting, User
    from backend.modules.auth import get_current_user
    from backend.modules.models import (
        Meeting as MeetingModel,
        MeetingCreateRequest,
        User as UserModel,
        AgentSessionRequest,
        AgentSessionResponse,
    )
try:
    from backend.utils.livekit_utils import generate_livekit_token, ensure_agent_dispatch
except ImportError:
    from utils.livekit_utils import generate_livekit_token, ensure_agent_dispatch

router = APIRouter()

@router.get("/meetings", response_model=List[MeetingModel])
async def get_meetings(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    meetings = db.query(Meeting).all()
    return [MeetingModel(id=m.id, name=m.name, status=m.status, created_at=m.created_at, participants=[p.id for p in m.participants], owner_id=m.owner_id) for m in meetings]

@router.post("/meetings", response_model=MeetingModel)
async def create_meeting(request: MeetingCreateRequest, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(id=meeting_id, name=request.name, owner_id=current_user.id)

    # Lägg till mem0-metadata för möte
    meeting.mem0_context = {
        "created_by": current_user.id,
        "created_at": datetime.now().isoformat(),
        "memory_mode": request.memory_mode or "auto",  # auto, manual, hybrid
        "memory_retention_days": request.memory_retention_days or 90,
        "allow_participant_memories": request.allow_participant_memories if request.allow_participant_memories is not None else True
    }

    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return MeetingModel(id=meeting.id, name=meeting.name, status=meeting.status, created_at=meeting.created_at, participants=[], owner_id=meeting.owner_id, mem0_context=meeting.mem0_context)

@router.get("/meetings/{meeting_id}", response_model=MeetingModel)
async def get_meeting(meeting_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return MeetingModel(id=meeting.id, name=meeting.name, status=meeting.status, created_at=meeting.created_at, participants=[p.id for p in meeting.participants], owner_id=meeting.owner_id)

@router.post("/meetings/{meeting_id}/join")
async def join_meeting(meeting_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if user not in meeting.participants:
        meeting.participants.append(user)
        db.commit()
    
    # Generate LiveKit token for the participant
    try:
        livekit_token = generate_livekit_token(
            room_name=meeting_id,
            participant_name=user.username or user.email,
            participant_identity=str(user.id)
        )
        livekit_url = os.getenv('LIVEKIT_URL', 'wss://happpy-svhoibpt.livekit.cloud')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate LiveKit token: {str(e)}"
        )
    
    return {
        "message": "Joined meeting",
        "meeting_id": meeting_id,
        "participant_id": user.id,
        "livekitToken": livekit_token,
        "livekitUrl": livekit_url
    }

@router.post("/meetings/{meeting_id}/agent-session", response_model=AgentSessionResponse)
async def ensure_agent_session(
    meeting_id: str,
    request: AgentSessionRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    participant_id = request.participant_id or str(current_user.id)
    try:
        dispatch = await ensure_agent_dispatch(meeting_id, participant_id)
        try:
            metadata = json.loads(dispatch.metadata or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return AgentSessionResponse(
            session_id=metadata.get("session_id") or dispatch.id,
            agent_name=dispatch.agent_name,
            room=dispatch.room,
            metadata=metadata if metadata else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ensure agent session: {str(exc)}",
        ) from exc

@router.delete("/meetings/{meeting_id}")
async def end_meeting(meeting_id: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    meeting.status = "completed"
    db.commit()
    return {"message": "Meeting ended"}
