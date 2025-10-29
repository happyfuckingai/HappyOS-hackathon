"""
A2A Router - Internal Agent-to-Agent Communication

Routes messages between agents within the same system (domain).
Uses the global registry to find and invoke target agents.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..registry.agents import build, is_registered, get_agents_by_domain
from .protocol import A2AMessage, A2AResponse, A2AMessageType

logger = logging.getLogger(__name__)


class A2ARouter:
    """
    Router for internal agent-to-agent communication within a domain.
    
    Handles message routing between the 5 standard agent roles:
    - coordinator
    - architect  
    - implementation
    - product_manager
    - quality_assurance
    """
    
    def __init__(self, domain: str):
        self.domain = domain
        self.message_history = []
        self.active_conversations = {}
        
    async def route_message(self, message: A2AMessage) -> A2AResponse:
        """
        Route a message to the target agent within this domain.
        
        Args:
            message: A2A message to route
            
        Returns:
            Response from target agent
        """
        try:
            # Build full agent name with domain prefix
            target_agent_name = f"{self.domain}.{message.to_agent}"
            
            # Check if target agent is registered
            if not is_registered(target_agent_name):
                available_agents = get_agents_by_domain(self.domain)
                return A2AResponse(
                    success=False,
                    error=f"Agent '{target_agent_name}' not found. Available: {available_agents}",
                    message_id=message.message_id
                )
            
            # Build target agent instance
            target_agent = build(target_agent_name)
            
            # Log the routing
            logger.info(f"Routing A2A message from {message.from_agent} to {target_agent_name}")
            self._log_message(message)
            
            # Call the target agent
            if hasattr(target_agent, 'handle_a2a_message'):
                response_data = await target_agent.handle_a2a_message(message)
            elif hasattr(target_agent, 'call'):
                response_data = await target_agent.call(message.tool, message.payload)
            else:
                return A2AResponse(
                    success=False,
                    error=f"Agent '{target_agent_name}' does not support A2A messaging",
                    message_id=message.message_id
                )
            
            # Create successful response
            response = A2AResponse(
                success=True,
                data=response_data,
                message_id=message.message_id,
                from_agent=target_agent_name,
                to_agent=message.from_agent
            )
            
            self._log_response(response)
            return response
            
        except Exception as e:
            logger.error(f"A2A routing failed: {e}")
            return A2AResponse(
                success=False,
                error=str(e),
                message_id=message.message_id
            )
    
    async def broadcast_message(self, message: A2AMessage, exclude_agents: list = None) -> Dict[str, A2AResponse]:
        """
        Broadcast message to all agents in the domain.
        
        Args:
            message: Message to broadcast
            exclude_agents: List of agent names to exclude
            
        Returns:
            Dict mapping agent names to their responses
        """
        exclude_agents = exclude_agents or []
        domain_agents = get_agents_by_domain(self.domain)
        
        responses = {}
        
        for agent_name in domain_agents:
            # Extract role name (remove domain prefix)
            role_name = agent_name.split('.', 1)[1] if '.' in agent_name else agent_name
            
            if role_name not in exclude_agents:
                # Create message copy for this agent
                agent_message = A2AMessage(
                    message_id=f"{message.message_id}_{role_name}",
                    from_agent=message.from_agent,
                    to_agent=role_name,
                    message_type=message.message_type,
                    tool=message.tool,
                    payload=message.payload,
                    correlation_id=message.correlation_id
                )
                
                response = await self.route_message(agent_message)
                responses[role_name] = response
        
        return responses
    
    def get_conversation_history(self, conversation_id: str) -> list:
        """Get message history for a conversation."""
        return [
            msg for msg in self.message_history 
            if msg.get('correlation_id') == conversation_id
        ]
    
    def get_domain_stats(self) -> Dict[str, Any]:
        """Get routing statistics for this domain."""
        domain_agents = get_agents_by_domain(self.domain)
        
        return {
            "domain": self.domain,
            "registered_agents": len(domain_agents),
            "agent_names": domain_agents,
            "total_messages": len(self.message_history),
            "active_conversations": len(self.active_conversations)
        }
    
    def _log_message(self, message: A2AMessage):
        """Log outgoing message."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "message",
            "message_id": message.message_id,
            "from_agent": message.from_agent,
            "to_agent": f"{self.domain}.{message.to_agent}",
            "tool": message.tool,
            "correlation_id": message.correlation_id
        }
        self.message_history.append(log_entry)
    
    def _log_response(self, response: A2AResponse):
        """Log incoming response."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "response", 
            "message_id": response.message_id,
            "from_agent": response.from_agent,
            "to_agent": response.to_agent,
            "success": response.success
        }
        self.message_history.append(log_entry)


# Global routers per domain
_domain_routers: Dict[str, A2ARouter] = {}

def get_router(domain: str) -> A2ARouter:
    """Get or create A2A router for a domain."""
    if domain not in _domain_routers:
        _domain_routers[domain] = A2ARouter(domain)
    return _domain_routers[domain]

async def route_message(domain: str, message: A2AMessage) -> A2AResponse:
    """
    Route a message within a domain.
    
    Convenience function for routing without managing router instances.
    """
    router = get_router(domain)
    return await router.route_message(message)