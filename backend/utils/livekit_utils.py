"""
LiveKit utilities for generating access tokens and dispatching agents
"""
import json
import os
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from livekit import api

def generate_livekit_token(room_name: str, participant_name: str, participant_identity: str) -> str:
    """
    Generate a LiveKit access token for a participant to join a room
    
    Args:
        room_name: Name of the LiveKit room (usually meeting_id)
        participant_name: Display name of the participant
        participant_identity: Unique identifier for the participant (usually user_id)
    
    Returns:
        JWT token string for LiveKit access
    """
    # Get LiveKit credentials from environment
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    
    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in environment")
    
    # Create access token
    token = api.AccessToken(api_key, api_secret)
    
    # Set token identity and name
    token.with_identity(participant_identity)
    token.with_name(participant_name)
    
    # Grant permissions for the room
    token.with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    ))
    
    # Set token expiration (24 hours)
    token.with_ttl(timedelta(hours=24))
    
    return token.to_jwt()


async def ensure_agent_dispatch(
    room_name: str,
    participant_id: str,
    *,
    agent_name: Optional[str] = None,
) -> api.AgentDispatch:
    """
    Ensure there is an explicit agent dispatch for the participant in the given room.

    If a dispatch already exists for the participant it is returned, otherwise a new
    dispatch is created with metadata describing the participant/session.
    """
    agent_name = agent_name or os.getenv("LIVEKIT_AGENT_NAME", "meetmind-agent")

    async with api.LiveKitAPI() as lkapi:
        existing_dispatches = await lkapi.agent_dispatch.list_dispatch(room_name)
        for dispatch in existing_dispatches:
            if dispatch.agent_name != agent_name:
                continue
            try:
                metadata = json.loads(dispatch.metadata or "{}")
            except json.JSONDecodeError:
                metadata = {}
            if metadata.get("participant_id") == participant_id:
                return dispatch

        session_id = str(uuid4())
        metadata_payload = {
            "participant_id": participant_id,
            "session_id": session_id,
        }
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_name,
                metadata=json.dumps(metadata_payload),
            )
        )
        return dispatch
