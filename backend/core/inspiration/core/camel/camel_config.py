"""
CAMEL Configuration Module

This module provides configuration settings for the CAMEL framework integration,
including agent roles, conversation templates, and system parameters.
"""

import os
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path

class AgentRole(Enum):
    """Predefined roles for CAMEL agents."""
    USER = "user"
    ASSISTANT = "assistant"
    PROGRAMMER = "programmer"
    DESIGNER = "designer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    ARCHITECT = "architect"
    PRODUCT_MANAGER = "product_manager"
    DATABASE_EXPERT = "database_expert"
    SECURITY_EXPERT = "security_expert"
    FRONTEND_DEVELOPER = "frontend_developer"
    BACKEND_DEVELOPER = "backend_developer"
    DEVOPS_ENGINEER = "devops_engineer"
    SYSTEM_ADMINISTRATOR = "system_administrator"
    QUALITY_ASSURANCE = "quality_assurance"
    TECHNICAL_WRITER = "technical_writer"
    DATA_SCIENTIST = "data_scientist"
    MACHINE_LEARNING_ENGINEER = "machine_learning_engineer"
    UI_UX_DESIGNER = "ui_ux_designer"
    BUSINESS_ANALYST = "business_analyst"
    DOMAIN_EXPERT = "domain_expert"
    CUSTOM = "custom"  # For custom roles defined at runtime

@dataclass
class AgentConfig:
    """Configuration for a CAMEL agent."""
    role: AgentRole
    name: str
    description: str
    system_message: str
    capabilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    knowledge_base: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConversationTemplate:
    """Template for agent conversations."""
    name: str
    description: str
    roles: List[AgentRole]
    initial_prompt: str
    turn_structure: List[Dict[str, Any]]
    max_turns: int = 10
    termination_conditions: List[str] = field(default_factory=list)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CamelConfig:
    """Main configuration for CAMEL integration."""
    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    default_model: str = "gpt-4"
    default_temperature: float = 0.7
    default_max_tokens: int = 1024
    agent_configs: Dict[AgentRole, AgentConfig] = field(default_factory=dict)
    conversation_templates: Dict[str, ConversationTemplate] = field(default_factory=dict)
    log_conversations: bool = True
    log_directory: str = "/home/mr/Dokument/filee.tar/logs/camel"
    enable_memory: bool = True
    memory_window_size: int = 10
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> 'CamelConfig':
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            CamelConfig object
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            config_data = json.load(f)
        
        # Process agent configs
        agent_configs = {}
        for role_str, config in config_data.get('agent_configs', {}).items():
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.CUSTOM
            
            agent_configs[role] = AgentConfig(
                role=role,
                name=config.get('name', role_str),
                description=config.get('description', ''),
                system_message=config.get('system_message', ''),
                capabilities=config.get('capabilities', []),
                constraints=config.get('constraints', []),
                knowledge_base=config.get('knowledge_base'),
                model=config.get('model'),
                temperature=config.get('temperature', 0.7),
                max_tokens=config.get('max_tokens', 1024),
                custom_parameters=config.get('custom_parameters', {})
            )
        
        # Process conversation templates
        conversation_templates = {}
        for name, template in config_data.get('conversation_templates', {}).items():
            roles = [AgentRole(r) if r in [e.value for e in AgentRole] else AgentRole.CUSTOM 
                    for r in template.get('roles', [])]
            
            conversation_templates[name] = ConversationTemplate(
                name=name,
                description=template.get('description', ''),
                roles=roles,
                initial_prompt=template.get('initial_prompt', ''),
                turn_structure=template.get('turn_structure', []),
                max_turns=template.get('max_turns', 10),
                termination_conditions=template.get('termination_conditions', []),
                custom_parameters=template.get('custom_parameters', {})
            )
        
        return cls(
            base_url=config_data.get('base_url', "http://localhost:8000"),
            api_key=config_data.get('api_key'),
            default_model=config_data.get('default_model', "gpt-4"),
            default_temperature=config_data.get('default_temperature', 0.7),
            default_max_tokens=config_data.get('default_max_tokens', 1024),
            agent_configs=agent_configs,
            conversation_templates=conversation_templates,
            log_conversations=config_data.get('log_conversations', True),
            log_directory=config_data.get('log_directory', "/home/mr/Dokument/filee.tar/logs/camel"),
            enable_memory=config_data.get('enable_memory', True),
            memory_window_size=config_data.get('memory_window_size', 10),
            custom_parameters=config_data.get('custom_parameters', {})
        )
    
    def to_file(self, file_path: Union[str, Path]) -> None:
        """
        Save configuration to a JSON file.
        
        Args:
            file_path: Path to save the configuration file
        """
        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)
        
        # Convert agent configs to dict
        agent_configs = {}
        for role, config in self.agent_configs.items():
            agent_configs[role.value] = {
                'name': config.name,
                'description': config.description,
                'system_message': config.system_message,
                'capabilities': config.capabilities,
                'constraints': config.constraints,
                'knowledge_base': config.knowledge_base,
                'model': config.model,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens,
                'custom_parameters': config.custom_parameters
            }
        
        # Convert conversation templates to dict
        conversation_templates = {}
        for name, template in self.conversation_templates.items():
            conversation_templates[name] = {
                'description': template.description,
                'roles': [r.value for r in template.roles],
                'initial_prompt': template.initial_prompt,
                'turn_structure': template.turn_structure,
                'max_turns': template.max_turns,
                'termination_conditions': template.termination_conditions,
                'custom_parameters': template.custom_parameters
            }
        
        config_data = {
            'base_url': self.base_url,
            'api_key': self.api_key,
            'default_model': self.default_model,
            'default_temperature': self.default_temperature,
            'default_max_tokens': self.default_max_tokens,
            'agent_configs': agent_configs,
            'conversation_templates': conversation_templates,
            'log_conversations': self.log_conversations,
            'log_directory': self.log_directory,
            'enable_memory': self.enable_memory,
            'memory_window_size': self.memory_window_size,
            'custom_parameters': self.custom_parameters
        }
        
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=2)

# Default configuration
default_config = CamelConfig()

# Load configuration from environment variables
def load_config_from_env() -> CamelConfig:
    """
    Load configuration from environment variables.
    
    Returns:
        CamelConfig object
    """
    config = CamelConfig()
    
    # Load basic settings from environment variables
    if os.getenv('CAMEL_BASE_URL'):
        config.base_url = os.getenv('CAMEL_BASE_URL')
    
    if os.getenv('CAMEL_API_KEY'):
        config.api_key = os.getenv('CAMEL_API_KEY')
    
    if os.getenv('CAMEL_DEFAULT_MODEL'):
        config.default_model = os.getenv('CAMEL_DEFAULT_MODEL')
    
    if os.getenv('CAMEL_DEFAULT_TEMPERATURE'):
        config.default_temperature = float(os.getenv('CAMEL_DEFAULT_TEMPERATURE'))
    
    if os.getenv('CAMEL_DEFAULT_MAX_TOKENS'):
        config.default_max_tokens = int(os.getenv('CAMEL_DEFAULT_MAX_TOKENS'))
    
    if os.getenv('CAMEL_LOG_CONVERSATIONS'):
        config.log_conversations = os.getenv('CAMEL_LOG_CONVERSATIONS').lower() == 'true'
    
    if os.getenv('CAMEL_LOG_DIRECTORY'):
        config.log_directory = os.getenv('CAMEL_LOG_DIRECTORY')
    
    if os.getenv('CAMEL_ENABLE_MEMORY'):
        config.enable_memory = os.getenv('CAMEL_ENABLE_MEMORY').lower() == 'true'
    
    if os.getenv('CAMEL_MEMORY_WINDOW_SIZE'):
        config.memory_window_size = int(os.getenv('CAMEL_MEMORY_WINDOW_SIZE'))
    
    return config

# Get configuration
def get_camel_config() -> CamelConfig:
    """
    Get the CAMEL configuration.
    
    First tries to load from a configuration file, then from environment variables,
    and falls back to default configuration if neither is available.
    
    Returns:
        CamelConfig object
    """
    config_file = os.getenv('CAMEL_CONFIG_FILE', '/home/mr/Dokument/filee.tar/config/camel_config.json')
    
    try:
        return CamelConfig.from_file(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            return load_config_from_env()
        except Exception:
            return default_config

# Global configuration instance
camel_config = get_camel_config()