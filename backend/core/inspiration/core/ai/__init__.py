"""
🤖 AI MODULE - ADVANCED ARTIFICIAL INTELLIGENCE

Enhanced AI capabilities for HappyOS:
- Advanced personality modeling
- Intelligent skill systems
- Predictive analytics
- Machine learning integration
"""

from .enhanced_personality_engine import (
    EnhancedMrHappyAgent,
    PersonalityProfile,
    EmotionState,
    ConversationMemory,
    SentimentAnalyzer,
    PersonalityLearner,
    get_enhanced_mr_happy_agent,
    process_with_enhanced_personality
)

from .intelligent_skill_system import (
    IntelligentSkillSystem,
    SkillDefinition,
    SkillExecutionContext,
    SkillExecutionResult,
    CapabilityDiscoveryEngine,
    SkillLearningEngine,
    get_intelligent_skill_system,
    process_with_intelligent_skills
)

__all__ = [
    # Personality Engine
    'EnhancedMrHappyAgent',
    'PersonalityProfile',
    'EmotionState',
    'ConversationMemory',
    'SentimentAnalyzer',
    'PersonalityLearner',
    'get_enhanced_mr_happy_agent',
    'process_with_enhanced_personality',
    
    # Intelligent Skill System
    'IntelligentSkillSystem',
    'SkillDefinition',
    'SkillExecutionContext',
    'SkillExecutionResult',
    'CapabilityDiscoveryEngine',
    'SkillLearningEngine',
    'get_intelligent_skill_system',
    'process_with_intelligent_skills'
]

