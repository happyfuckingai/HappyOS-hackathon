"""
🤖 ORCHESTRATOR AGENT
The "brain" that decides which tool to use.
"""
import logging
from typing import Dict, Any, List
from dataclasses import asdict

from app.core.ai.intelligent_skill_system import get_intelligent_skill_system, SkillExecutionContext
from app.core.database.persistence_manager import get_persistence_manager

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    An AI-powered orchestrator that uses the IntelligentSkillSystem to route tasks.
    """
    def __init__(self):
        self.skill_system = get_intelligent_skill_system()
        self.persistence_manager = get_persistence_manager()

    async def decide_and_execute(self, user_id: str, conversation_id: str, user_input: str) -> Dict[str, Any]:
        """
        Recommends and executes the best skill for the user's input.
        If no skill is suitable, it handles the request as a general conversation.
        """
        try:
            # Get conversation history for context
            history = await self.persistence_manager.get_conversation_history(conversation_id)
            
            # Create execution context
            exec_context = SkillExecutionContext(
                user_id=user_id,
                conversation_id=conversation_id,
                task_description=user_input,
                input_data=user_input,
                conversation_history=history
            )

            # Get skill recommendations
            recommended_skills = await self.skill_system.recommend_skills(user_input, asdict(exec_context))

            if recommended_skills:
                top_skill = recommended_skills[0]
                logger.info(f"Orchestrator selected skill: {top_skill['name']}")
                
                # Execute the skill
                execution_result = await self.skill_system.execute_skill(top_skill['skill_id'], exec_context)
                
                # Record skill usage
                await self.persistence_manager.record_skill_usage(
                    skill_id=top_skill['skill_id'],
                    skill_name=top_skill['name'],
                    user_id=user_id,
                    conversation_id=conversation_id,
                    execution_status="success" if execution_result.success else "failure",
                    execution_time=execution_result.execution_time,
                    error_details={"error": execution_result.error_message} if not execution_result.success else None
                )
                
                return execution_result.to_dict()
            else:
                logger.info("No suitable skill found. Handling as general conversation.")
                # The IntelligentSkillSystem can also handle general conversation
                # by executing a default "communication" skill.
                # For now, we'll just return a simple response.
                return {"success": True, "output_data": "I'm not sure how to help with that. Can you try rephrasing?"}

        except Exception as e:
            logger.error(f"An unexpected error occurred during orchestration: {e}", exc_info=True)
            return {"success": False, "error": "An internal error occurred."}

# Global instance for the server
orchestrator_agent = OrchestratorAgent()
