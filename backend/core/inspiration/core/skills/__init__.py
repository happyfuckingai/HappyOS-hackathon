"""
Skills package for HappyOS.
Clean modular architecture with separated responsibilities.
"""

from .skill_registry import skill_registry, SkillCapability
from .skill_generator import skill_generator, generate_skill_for_request
from .clean_skill_generator import clean_skill_generator, generate_skill_for_request as clean_generate_skill_for_request

# Import separated modules
from .prompts.skill_prompts import skill_prompts
from .templates.skill_templates import skill_templates
from .validation.skill_validator import skill_validator, ValidationResult

__all__ = [
    "skill_registry",
    "SkillCapability", 
    "skill_generator",
    "generate_skill_for_request",
    "clean_skill_generator",
    "clean_generate_skill_for_request",
    "skill_prompts",
    "skill_templates", 
    "skill_validator",
    "ValidationResult"
]