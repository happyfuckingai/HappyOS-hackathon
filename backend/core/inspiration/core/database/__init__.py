"""
🗄️ DATABASE MODULE - PERSISTENT STORAGE FOR HAPPYOS

This module provides persistent storage capabilities for:
- Conversation history and state
- User preferences and personality data
- Skill usage analytics
- Performance metrics
- System configuration
"""

from .connection import DatabaseConnection, get_db_connection
from .models import (
    Conversation, ConversationMessage, UserProfile, SkillUsage, 
    PerformanceMetric, SystemConfig
)
from .repositories import (
    ConversationRepository, UserRepository, SkillAnalyticsRepository,
    PerformanceRepository, ConfigRepository
)
from .migrations import DatabaseMigrator

__all__ = [
    'DatabaseConnection',
    'get_db_connection',
    'Conversation',
    'ConversationMessage', 
    'UserProfile',
    'SkillUsage',
    'PerformanceMetric',
    'SystemConfig',
    'ConversationRepository',
    'UserRepository',
    'SkillAnalyticsRepository',
    'PerformanceRepository',
    'ConfigRepository',
    'DatabaseMigrator'
]

