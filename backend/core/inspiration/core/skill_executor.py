"""
Skill Executor Module

Provides centralized skill execution functionality for the HappyOS system.
This module serves as the main entry point for executing skills across the platform.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Union
from datetime import datetime
import hashlib

from .ai.intelligent_skill_system import get_intelligent_skill_system, SkillExecutionContext
from .error_handler import safe_execute

logger = logging.getLogger(__name__)

# Global skill system instance
_skill_system = None


async def _get_skill_system():
    """Get or initialize the skill system."""
    global _skill_system
    if _skill_system is None:
        _skill_system = get_intelligent_skill_system()
        # Give it time to initialize
        await asyncio.sleep(0.1)
    return _skill_system


async def execute_skill(
    skill_name: str,
    input_data: Union[str, Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a skill with the given input data and context.

    This is the main entry point for skill execution across the HappyOS platform.

    Args:
        skill_name (str): Name or ID of the skill to execute
        input_data (Union[str, Dict[str, Any]]): Input data for the skill
        context (Optional[Dict[str, Any]]): Additional context for execution

    Returns:
        Dict[str, Any]: Execution result with success status and output data
    """
    try:
        logger.info(f"Executing skill: {skill_name}")

        # Get the skill system
        skill_system = await _get_skill_system()

        # Create execution context
        execution_context = SkillExecutionContext(
            user_id=context.get('user_id', 'system') if context else 'system',
            conversation_id=context.get('conversation_id', 'default') if context else 'default',
            task_description=str(input_data)[:200],  # First 200 chars as description
            input_data=input_data,
            user_preferences=context if context else {}
        )

        # Execute the skill
        result = await skill_system.execute_skill(skill_name, execution_context)

        # Convert to the expected format
        response = {
            'success': result.success,
            'skill_id': result.skill_id,
            'execution_id': result.execution_id,
            'execution_time': result.execution_time,
            'output_data': result.output_data,
            'confidence': result.confidence,
            'error_message': result.error_message,
            'timestamp': result.timestamp.isoformat()
        }

        # Add user satisfaction if available
        if result.user_satisfaction is not None:
            response['user_satisfaction'] = result.user_satisfaction

        # Add improvement suggestions if available
        if result.improvement_suggestions:
            response['improvement_suggestions'] = result.improvement_suggestions

        logger.info(f"Skill {skill_name} executed successfully: {result.success}")
        return response

    except Exception as e:
        logger.error(f"Error executing skill {skill_name}: {e}")
        return {
            'success': False,
            'skill_id': skill_name,
            'execution_time': 0.0,
            'output_data': None,
            'error_message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


async def execute_skill_with_fallback(
    skill_name: str,
    input_data: Union[str, Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    fallback_skills: Optional[list] = None
) -> Dict[str, Any]:
    """
    Execute a skill with fallback options if the primary skill fails.

    Args:
        skill_name (str): Primary skill to execute
        input_data (Union[str, Dict[str, Any]]): Input data for the skill
        context (Optional[Dict[str, Any]]): Additional context for execution
        fallback_skills (Optional[list]): List of fallback skill names

    Returns:
        Dict[str, Any]: Execution result
    """
    # Try primary skill first
    result = await execute_skill(skill_name, input_data, context)

    if result['success'] or not fallback_skills:
        return result

    logger.info(f"Primary skill {skill_name} failed, trying fallbacks")

    # Try fallback skills
    for fallback_skill in fallback_skills:
        try:
            logger.info(f"Trying fallback skill: {fallback_skill}")
            fallback_result = await execute_skill(fallback_skill, input_data, context)

            if fallback_result['success']:
                logger.info(f"Fallback skill {fallback_skill} succeeded")
                return fallback_result

        except Exception as e:
            logger.warning(f"Fallback skill {fallback_skill} also failed: {e}")
            continue

    logger.error(f"All skills failed for input: {input_data}")
    return result  # Return original failure result


async def get_skill_info(skill_name: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific skill.

    Args:
        skill_name (str): Name or ID of the skill

    Returns:
        Optional[Dict[str, Any]]: Skill information or None if not found
    """
    try:
        skill_system = await _get_skill_system()

        if skill_name in skill_system.skills:
            skill = skill_system.skills[skill_name]
            return {
                'skill_id': skill.skill_id,
                'name': skill.name,
                'description': skill.description,
                'category': skill.category.value,
                'complexity': skill.complexity.value,
                'status': skill.status.value,
                'input_types': skill.input_types,
                'output_types': skill.output_types,
                'success_rate': skill.metrics.success_rate,
                'average_execution_time': skill.metrics.average_execution_time,
                'total_executions': skill.metrics.total_executions
            }

        return None

    except Exception as e:
        logger.error(f"Error getting skill info for {skill_name}: {e}")
        return None


async def list_available_skills(category: Optional[str] = None) -> list:
    """
    List all available skills, optionally filtered by category.

    Args:
        category (Optional[str]): Filter by skill category

    Returns:
        list: List of available skill information
    """
    try:
        skill_system = await _get_skill_system()

        skills = []
        for skill_id, skill in skill_system.skills.items():
            if skill.status.value == 'active':  # Only return active skills
                if category is None or skill.category.value == category:
                    skills.append({
                        'skill_id': skill.skill_id,
                        'name': skill.name,
                        'description': skill.description,
                        'category': skill.category.value,
                        'complexity': skill.complexity.value,
                        'success_rate': skill.metrics.success_rate,
                        'average_execution_time': skill.metrics.average_execution_time
                    })

        return skills

    except Exception as e:
        logger.error(f"Error listing available skills: {e}")
        return []


# Legacy compatibility functions
async def execute_component_skill(component_name: str, request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a skill for a specific component (legacy compatibility).

    Args:
        component_name (str): Name of the component
        request (str): Skill execution request
        context (Optional[Dict[str, Any]]): Additional context

    Returns:
        Dict[str, Any]: Execution result
    """
    # Map component name to skill name (simple mapping for now)
    skill_name = component_name.replace(' ', '_').lower()

    # Create context with component information
    enhanced_context = context or {}
    enhanced_context['component_name'] = component_name
    enhanced_context['request_type'] = 'component_skill'

    return await execute_skill(skill_name, request, enhanced_context)


# Initialize the skill system when module is imported
async def _initialize_skill_system():
    """Initialize the skill system in the background."""
    try:
        await _get_skill_system()
        logger.info("Skill executor system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize skill executor system: {e}")


# Start initialization
if asyncio.get_event_loop().is_running():
    # If event loop is already running, create a task
    asyncio.create_task(_initialize_skill_system())
else:
    # Otherwise, run it directly
    asyncio.run(_initialize_skill_system())