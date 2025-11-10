"""
Owl Helpers Module

This module provides utility functions for working with Owl integration,
including decision logic for when to use Owl and input sanitization.
"""

import re
import logging
import html
from typing import Dict, Any, List, Optional, Union
import json

from .owl_config import get_owl_config

logger = logging.getLogger(__name__)

# Keywords that suggest complex tasks that would benefit from Owl
COMPLEX_TASK_KEYWORDS = [
    "create", "build", "develop", "generate", "implement", "design",
    "system", "application", "dashboard", "report", "analysis",
    "multi", "complex", "advanced", "sophisticated", "intelligent",
    "code", "program", "script", "automate", "workflow",
    "frontend", "backend", "fullstack", "database", "api",
    "component", "module", "service", "integration", "interface"
]

# Keywords that suggest simple tasks that don't need Owl
SIMPLE_TASK_KEYWORDS = [
    "what", "who", "when", "where", "why", "how", "is", "are", "can", "could",
    "tell", "explain", "describe", "define", "summarize", "list",
    "simple", "basic", "quick", "help", "show", "find", "search"
]

def should_use_owl_for_skill(
    user_request: str, 
    context: Optional[Dict[str, Any]] = None,
    force_owl: bool = False
) -> bool:
    """
    Determine if a user request should be handled by Owl.
    
    Uses a combination of heuristics to decide if the request is complex
    enough to benefit from Owl's multi-agent capabilities.
    
    Args:
        user_request: The user's request text
        context: Optional context about the request and user
        force_owl: If True, always use Owl regardless of other factors
        
    Returns:
        Boolean indicating whether to use Owl
    """
    if force_owl:
        logger.info("Forcing use of Owl due to explicit request")
        return True
    
    # Get configuration
    config = get_owl_config()
    
    # If Owl is disabled, don't use it
    if not config.get("use_local_owl", True):
        logger.debug("Owl usage is disabled in configuration")
        return False
    
    # Check for explicit Owl request in context
    if context and context.get("use_owl", False):
        logger.info("Using Owl due to context flag")
        return True
    
    # Normalize request text
    request_text = user_request.lower().strip()
    
    # Check request length - very short requests are unlikely to need Owl
    if len(request_text.split()) < config["length_threshold"]:
        # Short request - check if it contains specific complex keywords
        has_complex_keywords = any(keyword in request_text for keyword in COMPLEX_TASK_KEYWORDS)
        if not has_complex_keywords:
            logger.debug(f"Request too short for Owl: {len(request_text.split())} words")
            return False
    
    # Calculate complexity score based on keywords
    complexity_score = 0.0
    
    # Check for complex task keywords
    complex_matches = sum(1 for keyword in COMPLEX_TASK_KEYWORDS if keyword in request_text)
    complexity_score += (complex_matches / len(COMPLEX_TASK_KEYWORDS)) * 0.6
    
    # Check for simple task keywords (negative indicator)
    simple_matches = sum(1 for keyword in SIMPLE_TASK_KEYWORDS if keyword in request_text)
    complexity_score -= (simple_matches / len(SIMPLE_TASK_KEYWORDS)) * 0.4
    
    # Adjust score based on request length (longer requests tend to be more complex)
    word_count = len(request_text.split())
    length_factor = min(1.0, word_count / 200)  # Cap at 1.0 for requests with 200+ words
    complexity_score += length_factor * 0.2
    
    # Check for code-related patterns
    code_patterns = [
        r"```[a-z]*\n",  # Code blocks
        r"function\s+\w+\s*\(",  # Function definitions
        r"class\s+\w+",  # Class definitions
        r"import\s+\w+",  # Import statements
        r"<[a-z]+>.*</[a-z]+>",  # HTML tags
        r"\{\s*[\"\']?\w+[\"\']?\s*:",  # JSON-like structures
    ]
    
    code_matches = sum(1 for pattern in code_patterns if re.search(pattern, user_request))
    if code_matches > 0:
        complexity_score += 0.3
    
    # Check for specific task types that benefit from multi-agent collaboration
    multi_agent_indicators = [
        "collaborate", "team", "multiple", "agents", "specialists",
        "different perspectives", "diverse", "varied", "cross-functional"
    ]
    
    multi_agent_matches = sum(1 for indicator in multi_agent_indicators if indicator in request_text)
    if multi_agent_matches > 0:
        complexity_score += 0.2
    
    # Log the decision factors
    logger.debug(f"Owl decision factors - Complexity score: {complexity_score:.2f}, " +
                f"Complex keywords: {complex_matches}, Simple keywords: {simple_matches}, " +
                f"Word count: {word_count}, Code patterns: {code_matches}")
    
    # Make the final decision based on the complexity threshold
    use_owl = complexity_score >= config["complexity_threshold"]
    
    if use_owl:
        logger.info(f"Using Owl for request with complexity score {complexity_score:.2f}")
    else:
        logger.info(f"Not using Owl for request with complexity score {complexity_score:.2f}")
    
    return use_owl


def sanitize_input(input_text: str) -> str:
    """
    Sanitize input text to prevent security issues.
    
    Args:
        input_text: The text to sanitize
        
    Returns:
        Sanitized text
    """
    if not input_text:
        return ""
    
    # HTML escape to prevent XSS
    sanitized = html.escape(input_text)
    
    # Remove potential command injection patterns
    dangerous_patterns = [
        r"^\s*rm\s+-rf", r"^\s*sudo", r"^\s*chmod", r"^\s*chown",
        r"^\s*wget\s+.*\s*\|\s*bash", r"^\s*curl\s+.*\s*\|\s*bash",
        r"^\s*eval\s*\(", r"^\s*exec\s*\("
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, input_text, re.IGNORECASE):
            logger.warning(f"Potentially dangerous pattern detected in input: {pattern}")
            sanitized = re.sub(pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE)
    
    return sanitized


def extract_code_from_response(response_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract code files from an Owl response.
    
    Args:
        response_data: The response data from Owl
        
    Returns:
        Dictionary mapping file paths to code content
    """
    code_files = {}
    
    # Check for generated_code field
    if "generated_code" in response_data:
        if isinstance(response_data["generated_code"], dict):
            code_files = response_data["generated_code"]
        elif isinstance(response_data["generated_code"], list):
            for item in response_data["generated_code"]:
                if isinstance(item, dict) and "path" in item and "content" in item:
                    code_files[item["path"]] = item["content"]
    
    # Check for files field
    elif "files" in response_data:
        if isinstance(response_data["files"], dict):
            code_files = response_data["files"]
        elif isinstance(response_data["files"], list):
            for item in response_data["files"]:
                if isinstance(item, dict) and "path" in item and "content" in item:
                    code_files[item["path"]] = item["content"]
    
    return code_files