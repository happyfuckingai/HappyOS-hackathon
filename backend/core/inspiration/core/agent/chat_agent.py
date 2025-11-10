"""
HappyOS Chat Agent - Simple implementation for demonstration
"""
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ChatAgent:
    """Simple chat agent implementation."""
    
    async def handle_message(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        user_input: str
    ) -> Dict[str, Any]:
        """
        Handle a chat message and return a response.
        
        Args:
            conversation_id: ID of the conversation
            user_id: ID of the user
            organization_id: ID of the organization
            user_input: User's input message
            
        Returns:
            Dictionary containing the response
        """
        logger.info(f"Handling message for conversation {conversation_id}: {user_input}")
        
        # Simple echo response for demonstration
        response_text = f"I received your message: '{user_input}'. This is a response from HappyOS Chat Agent."
        
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        return {
            "message": response_text,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "timestamp": asyncio.get_event_loop().time()
        }

# Create a global instance
chat_agent = ChatAgent()
