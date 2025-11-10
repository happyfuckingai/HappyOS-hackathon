"""
CAMEL Helpers Module

This module provides utility functions for working with CAMEL agents and conversations.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import asyncio
from datetime import datetime

from app.core.camel.camel_config import AgentRole
from app.core.camel.camel_client import camel_client

logger = logging.getLogger(__name__)

async def extract_code_from_messages(messages: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Extract code blocks from conversation messages.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        Dictionary of file paths to code content
    """
    code_blocks = {}
    
    # Regular expression to match code blocks with file paths
    # Format: ```language:path/to/file.ext
    # code content
    # ```
    code_block_pattern = r"```(?:(\w+):)?([^\n]+)?\n(.*?)```"
    
    for message in messages:
        content = message.get("content", "")
        
        # Find all code blocks in the message
        matches = re.finditer(code_block_pattern, content, re.DOTALL)
        
        for match in matches:
            language = match.group(1) or ""
            file_path = match.group(2)
            code = match.group(3)
            
            if file_path:
                # Clean up file path
                file_path = file_path.strip()
                
                # Add to code blocks
                code_blocks[file_path] = code
    
    return code_blocks

async def extract_json_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract JSON objects from conversation messages.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        List of extracted JSON objects
    """
    json_objects = []
    
    # Regular expression to match JSON blocks
    # Format: ```json
    # { "key": "value" }
    # ```
    json_block_pattern = r"```json\n(.*?)```"
    
    for message in messages:
        content = message.get("content", "")
        
        # Find all JSON blocks in the message
        matches = re.finditer(json_block_pattern, content, re.DOTALL)
        
        for match in matches:
            json_str = match.group(1)
            
            try:
                json_obj = json.loads(json_str)
                json_objects.append(json_obj)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON: {json_str}")
    
    return json_objects

async def extract_task_list_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract task lists from conversation messages.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        List of tasks with status
    """
    tasks = []
    
    # Regular expression to match task list items
    # Format: - [ ] Task description
    # or: - [x] Completed task
    task_pattern = r"- \[([ xX])\] (.*)"
    
    for message in messages:
        content = message.get("content", "")
        
        # Find all task list items in the message
        matches = re.finditer(task_pattern, content)
        
        for match in matches:
            status = match.group(1)
            description = match.group(2).strip()
            
            tasks.append({
                "description": description,
                "completed": status.lower() == "x",
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp")
            })
    
    return tasks

async def run_conversation_with_roles(
    task: str,
    roles: List[Union[AgentRole, str]],
    context: Optional[Dict[str, Any]] = None,
    max_turns: Optional[int] = None,
    template: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Run a conversation between agents with specified roles.
    
    Args:
        task: Task description
        roles: List of agent roles
        context: Additional context for the task
        max_turns: Maximum number of turns
        template: Conversation template name
        
    Returns:
        Tuple of (success, result_data, conversation_id)
    """
    return await camel_client.run_multi_agent_task(
        task=task,
        roles=roles,
        context=context,
        max_turns=max_turns,
        template=template
    )

async def run_pair_conversation(
    task: str,
    role1: Union[AgentRole, str] = AgentRole.USER,
    role2: Union[AgentRole, str] = AgentRole.ASSISTANT,
    context: Optional[Dict[str, Any]] = None,
    max_turns: Optional[int] = None
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Run a conversation between two agents.
    
    Args:
        task: Task description
        role1: Role of the first agent
        role2: Role of the second agent
        context: Additional context for the task
        max_turns: Maximum number of turns
        
    Returns:
        Tuple of (success, result_data, conversation_id)
    """
    return await run_conversation_with_roles(
        task=task,
        roles=[role1, role2],
        context=context,
        max_turns=max_turns,
        template="pair_conversation"
    )

async def run_team_conversation(
    task: str,
    roles: List[Union[AgentRole, str]],
    context: Optional[Dict[str, Any]] = None,
    max_turns: Optional[int] = None
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Run a conversation between a team of agents.
    
    Args:
        task: Task description
        roles: List of agent roles
        context: Additional context for the task
        max_turns: Maximum number of turns
        
    Returns:
        Tuple of (success, result_data, conversation_id)
    """
    return await run_conversation_with_roles(
        task=task,
        roles=roles,
        context=context,
        max_turns=max_turns,
        template="team_conversation"
    )

async def run_code_generation_task(
    task: str,
    language: str = "python",
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, str]]:
    """
    Run a code generation task with a programmer agent.
    
    Args:
        task: Task description
        language: Programming language
        context: Additional context for the task
        
    Returns:
        Tuple of (success, code_files)
    """
    enhanced_context = context.copy() if context else {}
    enhanced_context["language"] = language
    
    success, result_data, conversation_id = await run_pair_conversation(
        task=f"Generate {language} code for: {task}",
        role1=AgentRole.USER,
        role2=AgentRole.PROGRAMMER,
        context=enhanced_context
    )
    
    if not success:
        logger.error(f"Code generation task failed: {result_data.get('error')}")
        return False, {}
    
    # Extract code from messages
    messages = result_data.get("messages", [])
    code_files = await extract_code_from_messages(messages)
    
    return True, code_files

async def run_design_task(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run a design task with a designer agent.
    
    Args:
        task: Task description
        context: Additional context for the task
        
    Returns:
        Tuple of (success, design_data)
    """
    success, result_data, conversation_id = await run_pair_conversation(
        task=f"Create a design for: {task}",
        role1=AgentRole.USER,
        role2=AgentRole.DESIGNER,
        context=context
    )
    
    if not success:
        logger.error(f"Design task failed: {result_data.get('error')}")
        return False, {}
    
    # Extract JSON from messages
    messages = result_data.get("messages", [])
    json_objects = await extract_json_from_messages(messages)
    
    # Combine all JSON objects into one design data object
    design_data = {}
    for json_obj in json_objects:
        design_data.update(json_obj)
    
    return True, design_data

async def run_architecture_task(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run an architecture task with an architect agent.
    
    Args:
        task: Task description
        context: Additional context for the task
        
    Returns:
        Tuple of (success, architecture_data)
    """
    success, result_data, conversation_id = await run_pair_conversation(
        task=f"Design an architecture for: {task}",
        role1=AgentRole.USER,
        role2=AgentRole.ARCHITECT,
        context=context
    )
    
    if not success:
        logger.error(f"Architecture task failed: {result_data.get('error')}")
        return False, {}
    
    # Extract JSON from messages
    messages = result_data.get("messages", [])
    json_objects = await extract_json_from_messages(messages)
    
    # Extract code (diagrams, etc.) from messages
    code_files = await extract_code_from_messages(messages)
    
    # Combine all data into one architecture data object
    architecture_data = {
        "components": [],
        "diagrams": code_files
    }
    
    for json_obj in json_objects:
        if "components" in json_obj:
            architecture_data["components"].extend(json_obj["components"])
        else:
            # Add other properties
            for key, value in json_obj.items():
                if key != "components":
                    architecture_data[key] = value
    
    return True, architecture_data

async def run_development_team_task(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run a task with a development team (architect, programmer, tester).
    
    Args:
        task: Task description
        context: Additional context for the task
        
    Returns:
        Tuple of (success, result_data)
    """
    roles = [
        AgentRole.ARCHITECT,
        AgentRole.PROGRAMMER,
        AgentRole.TESTER
    ]
    
    success, result_data, conversation_id = await run_team_conversation(
        task=task,
        roles=roles,
        context=context
    )
    
    if not success:
        logger.error(f"Development team task failed: {result_data.get('error')}")
        return False, {}
    
    # Extract code from messages
    messages = result_data.get("messages", [])
    code_files = await extract_code_from_messages(messages)
    
    # Extract task list from messages
    tasks = await extract_task_list_from_messages(messages)
    
    # Add code files and tasks to result data
    result_data["code_files"] = code_files
    result_data["tasks"] = tasks
    
    return True, result_data

async def should_use_camel_for_task(task: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Determine if a task should be handled by CAMEL.
    
    Args:
        task: Task description
        context: Additional context for the task
        
    Returns:
        Boolean indicating whether to use CAMEL
    """
    # Check if context explicitly specifies to use CAMEL
    if context and context.get("use_camel") is not None:
        return context.get("use_camel")
    
    # Check for keywords that suggest CAMEL would be useful
    camel_keywords = [
        "collaborate", "team", "design", "architecture", "develop",
        "create a system", "build an application", "implement a feature",
        "multi-agent", "multiple perspectives", "brainstorm", "plan",
        "complex project", "software development", "engineering task"
    ]
    
    for keyword in camel_keywords:
        if keyword.lower() in task.lower():
            return True
    
    # Check task complexity (length as a simple heuristic)
    if len(task) > 200:  # Long tasks might benefit from multi-agent collaboration
        return True
    
    # Default to not using CAMEL for simple tasks
    return False