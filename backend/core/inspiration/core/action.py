import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

# Forward declaration for type hinting action_handler_context if needed by handlers
# class ActionHandlerContext: (Define if specific context structure is needed for actions)
#     user_id: str
#     # ... other fields

# Type for an action handler function
ActionHandler = Callable[[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]], Dict[str, Any]] # user_id, data, context

# --- Action Handler Implementations ---
async def handle_get_system_status(user_id: str, data: Optional[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info(f"Executing action 'get_system_status' for user {user_id} with data: {data}")
    # In a real scenario, this would fetch actual system status
    # For now, using placeholder data
    from app.core.skills.skill_registry import skill_registry # Example: Get status from skill_registry
    from app.agents.multi_agent import agent_orchestrator # Example: Get status from agent_orchestrator

    status_info = {
        "timestamp": datetime.utcnow().isoformat(),
        "message": "System status placeholder",
        "details": {
            "skill_registry_status": skill_registry.get_registry_status() if skill_registry else 'Not available',
            "agent_orchestrator_status": agent_orchestrator.get_system_status() if agent_orchestrator else 'Not available',
        }
    }
    return {"success": True, "data": status_info}

async def handle_example_action(user_id: str, data: Optional[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info(f"Executing action 'example_action' for user {user_id} with data: {data}")
    return {
        "success": True,
        "message": f"Example action executed for user {user_id}.",
        "received_data": data
    }

# --- Action Registry ---
# Maps action_id to its handler function
# Note: Action handlers should be async if they perform I/O
_action_registry: Dict[str, ActionHandler] = {
    "get_system_status": handle_get_system_status,
    "example_action": handle_example_action,
    # Add more actions here
}

async def execute_action(
    action_id: str,
    user_id: str,
    data: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes a predefined action based on action_id.

    Args:
        action_id: The unique identifier for the action.
        user_id: The ID of the user requesting the action.
        data: Optional dictionary of data for the action.
        context: Optional dictionary for execution context (e.g., conversation details).

    Returns:
        A dictionary containing the result of the action.
    """
    if context is None:
        context = {}
    if data is None:
        data = {}

    logger.info(f"Attempting to execute action '{action_id}' for user '{user_id}' with data: {data}")

    handler = _action_registry.get(action_id)

    if not handler:
        logger.warning(f"Action_id '{action_id}' not found in registry.")
        return {
            "success": False,
            "error": "Action not found",
            "action_id": action_id,
            "message": f"Action '{action_id}' is not a recognized action."
        }

    try:
        # Call the action handler
        # Pass user_id, data, and context to the handler
        result = await handler(user_id=user_id, data=data, context=context)
        logger.info(f"Action '{action_id}' executed successfully for user '{user_id}'.")
        return result
    except Exception as e:
        logger.error(f"Error executing action '{action_id}' for user '{user_id}': {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "action_id": action_id,
            "message": f"An error occurred while executing action '{action_id}'."
        }

# Example of how to add a new action dynamically (if needed)
# def register_action(action_id: str, handler: ActionHandler):
#     if action_id in _action_registry:
#         logger.warning(f"Action_id '{action_id}' is already registered. Overwriting.")
#     _action_registry[action_id] = handler
#     logger.info(f"Registered action: {action_id}")

# Need to ensure datetime is imported for handle_get_system_status
from datetime import datetime
