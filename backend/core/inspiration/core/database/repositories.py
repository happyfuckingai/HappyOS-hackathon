"""
🏪 DATABASE REPOSITORIES - DATA ACCESS LAYER

Repository pattern implementation for:
- Conversation management
- User profile management
- Skill usage analytics
- Performance metrics
- System configuration
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from .connection import DatabaseConnection
from .models import (
    Conversation, ConversationMessage, UserProfile, SkillUsage,
    PerformanceMetric, SystemConfig, ConversationState, MessageType,
    SkillExecutionStatus
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common functionality."""
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
    
    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())


class ConversationRepository(BaseRepository):
    """Repository for conversation management."""
    
    async def create_conversation(self, user_id: str, initial_context: Dict[str, Any] = None) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            conversation_id=self._generate_id(),
            user_id=user_id,
            state=ConversationState.ACTIVE,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            context_data=initial_context or {}
        )
        
        data = conversation.to_dict()
        await self.db.execute_query(
            """INSERT INTO conversations 
               (conversation_id, user_id, state, created_at, last_activity, 
                context_data, user_preferences, personality_context, total_messages, 
                total_skills_used, total_skills_generated, average_response_time, 
                user_satisfaction_score) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['conversation_id'], data['user_id'], data['state'], 
             data['created_at'], data['last_activity'], data['context_data'],
             data['user_preferences'], data['personality_context'], 
             data['total_messages'], data['total_skills_used'], 
             data['total_skills_generated'], data['average_response_time'],
             data['user_satisfaction_score'])
        )
        
        logger.info(f"Created conversation {conversation.conversation_id} for user {user_id}")
        return conversation
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await self.db.execute_query(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,)
        )
        
        if result:
            row = result[0]
            return Conversation.from_dict({
                'conversation_id': row[0],
                'user_id': row[1],
                'state': row[2],
                'created_at': row[3],
                'last_activity': row[4],
                'context_data': row[5],
                'user_preferences': row[6],
                'personality_context': row[7],
                'total_messages': row[8],
                'total_skills_used': row[9],
                'total_skills_generated': row[10],
                'average_response_time': row[11],
                'user_satisfaction_score': row[12]
            })
        
        return None
    
    async def update_conversation(self, conversation: Conversation) -> bool:
        """Update conversation."""
        data = conversation.to_dict()
        
        result = await self.db.execute_query(
            """UPDATE conversations SET 
               state = ?, last_activity = ?, context_data = ?, 
               user_preferences = ?, personality_context = ?, 
               total_messages = ?, total_skills_used = ?, 
               total_skills_generated = ?, average_response_time = ?, 
               user_satisfaction_score = ?
               WHERE conversation_id = ?""",
            (data['state'], data['last_activity'], data['context_data'],
             data['user_preferences'], data['personality_context'],
             data['total_messages'], data['total_skills_used'],
             data['total_skills_generated'], data['average_response_time'],
             data['user_satisfaction_score'], data['conversation_id'])
        )
        
        return result > 0
    
    async def get_user_conversations(self, user_id: str, limit: int = 50, 
                                   state: Optional[ConversationState] = None) -> List[Conversation]:
        """Get conversations for a user."""
        if state:
            result = await self.db.execute_query(
                """SELECT * FROM conversations 
                   WHERE user_id = ? AND state = ? 
                   ORDER BY last_activity DESC LIMIT ?""",
                (user_id, state.value, limit)
            )
        else:
            result = await self.db.execute_query(
                """SELECT * FROM conversations 
                   WHERE user_id = ? 
                   ORDER BY last_activity DESC LIMIT ?""",
                (user_id, limit)
            )
        
        conversations = []
        for row in result:
            conversations.append(Conversation.from_dict({
                'conversation_id': row[0],
                'user_id': row[1],
                'state': row[2],
                'created_at': row[3],
                'last_activity': row[4],
                'context_data': row[5],
                'user_preferences': row[6],
                'personality_context': row[7],
                'total_messages': row[8],
                'total_skills_used': row[9],
                'total_skills_generated': row[10],
                'average_response_time': row[11],
                'user_satisfaction_score': row[12]
            }))
        
        return conversations
    
    async def add_message(self, message: ConversationMessage) -> bool:
        """Add message to conversation."""
        data = message.to_dict()
        
        result = await self.db.execute_query(
            """INSERT INTO conversation_messages 
               (message_id, conversation_id, message_type, content, timestamp, 
                metadata, task_id, skill_used, response_time, confidence_score) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['message_id'], data['conversation_id'], data['message_type'],
             data['content'], data['timestamp'], data['metadata'],
             data['task_id'], data['skill_used'], data['response_time'],
             data['confidence_score'])
        )
        
        # Update conversation message count
        await self.db.execute_query(
            """UPDATE conversations SET 
               total_messages = total_messages + 1,
               last_activity = ?
               WHERE conversation_id = ?""",
            (message.timestamp.isoformat(), message.conversation_id)
        )
        
        return result > 0
    
    async def get_conversation_messages(self, conversation_id: str, 
                                      limit: int = 100, offset: int = 0) -> List[ConversationMessage]:
        """Get messages for a conversation."""
        result = await self.db.execute_query(
            """SELECT * FROM conversation_messages 
               WHERE conversation_id = ? 
               ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            (conversation_id, limit, offset)
        )
        
        messages = []
        for row in result:
            messages.append(ConversationMessage.from_dict({
                'message_id': row[0],
                'conversation_id': row[1],
                'message_type': row[2],
                'content': row[3],
                'timestamp': row[4],
                'metadata': row[5],
                'task_id': row[6],
                'skill_used': row[7],
                'response_time': row[8],
                'confidence_score': row[9]
            }))
        
        return messages
    
    async def archive_old_conversations(self, days_old: int = 30) -> int:
        """Archive conversations older than specified days."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        
        result = await self.db.execute_query(
            """UPDATE conversations SET state = ? 
               WHERE last_activity < ? AND state != ?""",
            (ConversationState.ARCHIVED.value, cutoff_date, ConversationState.ARCHIVED.value)
        )
        
        logger.info(f"Archived {result} conversations older than {days_old} days")
        return result
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation and all its messages."""
        queries = [
            ("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,)),
            ("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
        ]
        
        success = await self.db.execute_transaction(queries)
        if success:
            logger.info(f"Deleted conversation {conversation_id}")
        
        return success


class UserRepository(BaseRepository):
    """Repository for user profile management."""
    
    async def create_user(self, user_id: str, username: str = None, 
                         email: str = None) -> UserProfile:
        """Create a new user profile."""
        user = UserProfile(
            user_id=user_id,
            username=username,
            email=email,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow()
        )
        
        data = user.to_dict()
        await self.db.execute_query(
            """INSERT INTO user_profiles 
               (user_id, username, email, created_at, last_active, preferences, 
                personality_traits, interaction_patterns, skill_preferences, 
                total_conversations, total_messages, total_skills_used, 
                average_session_duration, preferred_communication_style, 
                timezone, language) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['user_id'], data['username'], data['email'], 
             data['created_at'], data['last_active'], data['preferences'],
             data['personality_traits'], data['interaction_patterns'],
             data['skill_preferences'], data['total_conversations'],
             data['total_messages'], data['total_skills_used'],
             data['average_session_duration'], data['preferred_communication_style'],
             data['timezone'], data['language'])
        )
        
        logger.info(f"Created user profile for {user_id}")
        return user
    
    async def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by ID."""
        result = await self.db.execute_query(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        
        if result:
            row = result[0]
            return UserProfile.from_dict({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'created_at': row[3],
                'last_active': row[4],
                'preferences': row[5],
                'personality_traits': row[6],
                'interaction_patterns': row[7],
                'skill_preferences': row[8],
                'total_conversations': row[9],
                'total_messages': row[10],
                'total_skills_used': row[11],
                'average_session_duration': row[12],
                'preferred_communication_style': row[13],
                'timezone': row[14],
                'language': row[15]
            })
        
        return None
    
    async def update_user(self, user: UserProfile) -> bool:
        """Update user profile."""
        data = user.to_dict()
        
        result = await self.db.execute_query(
            """UPDATE user_profiles SET 
               username = ?, email = ?, last_active = ?, preferences = ?, 
               personality_traits = ?, interaction_patterns = ?, 
               skill_preferences = ?, total_conversations = ?, 
               total_messages = ?, total_skills_used = ?, 
               average_session_duration = ?, preferred_communication_style = ?, 
               timezone = ?, language = ?
               WHERE user_id = ?""",
            (data['username'], data['email'], data['last_active'],
             data['preferences'], data['personality_traits'],
             data['interaction_patterns'], data['skill_preferences'],
             data['total_conversations'], data['total_messages'],
             data['total_skills_used'], data['average_session_duration'],
             data['preferred_communication_style'], data['timezone'],
             data['language'], data['user_id'])
        )
        
        return result > 0
    
    async def get_or_create_user(self, user_id: str, username: str = None, 
                                email: str = None) -> UserProfile:
        """Get existing user or create new one."""
        user = await self.get_user(user_id)
        if user is None:
            user = await self.create_user(user_id, username, email)
        return user
    
    async def update_user_activity(self, user_id: str) -> bool:
        """Update user's last activity timestamp."""
        result = await self.db.execute_query(
            "UPDATE user_profiles SET last_active = ? WHERE user_id = ?",
            (datetime.utcnow().isoformat(), user_id)
        )
        return result > 0


class SkillAnalyticsRepository(BaseRepository):
    """Repository for skill usage analytics."""
    
    async def record_skill_usage(self, usage: SkillUsage) -> bool:
        """Record skill usage."""
        data = usage.to_dict()
        
        result = await self.db.execute_query(
            """INSERT INTO skill_usage 
               (usage_id, skill_id, skill_name, user_id, conversation_id, 
                execution_status, execution_time, timestamp, input_data, 
                output_data, error_details, confidence_score, user_feedback, 
                skill_generated, generation_time) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['usage_id'], data['skill_id'], data['skill_name'],
             data['user_id'], data['conversation_id'], data['execution_status'],
             data['execution_time'], data['timestamp'], data['input_data'],
             data['output_data'], data['error_details'], data['confidence_score'],
             data['user_feedback'], data['skill_generated'], data['generation_time'])
        )
        
        return result > 0
    
    async def get_skill_performance(self, skill_id: str, 
                                  days: int = 30) -> Dict[str, Any]:
        """Get skill performance metrics."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Get basic stats
        result = await self.db.execute_query(
            """SELECT 
                COUNT(*) as total_uses,
                AVG(execution_time) as avg_execution_time,
                SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) as success_count,
                AVG(confidence_score) as avg_confidence
               FROM skill_usage 
               WHERE skill_id = ? AND timestamp > ?""",
            (skill_id, cutoff_date)
        )
        
        if result:
            row = result[0]
            total_uses = row[0]
            success_rate = (row[2] / total_uses * 100) if total_uses > 0 else 0
            
            return {
                "skill_id": skill_id,
                "period_days": days,
                "total_uses": total_uses,
                "success_rate": success_rate,
                "average_execution_time": row[1] or 0,
                "average_confidence": row[3] or 0
            }
        
        return {"skill_id": skill_id, "total_uses": 0}
    
    async def get_popular_skills(self, limit: int = 10, 
                               days: int = 30) -> List[Dict[str, Any]]:
        """Get most popular skills."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        result = await self.db.execute_query(
            """SELECT skill_id, skill_name, COUNT(*) as usage_count,
                      AVG(execution_time) as avg_time,
                      SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
               FROM skill_usage 
               WHERE timestamp > ?
               GROUP BY skill_id, skill_name
               ORDER BY usage_count DESC
               LIMIT ?""",
            (cutoff_date, limit)
        )
        
        return [
            {
                "skill_id": row[0],
                "skill_name": row[1],
                "usage_count": row[2],
                "average_execution_time": row[3],
                "success_rate": row[4]
            }
            for row in result
        ]
    
    async def get_user_skill_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user's skill usage preferences."""
        result = await self.db.execute_query(
            """SELECT skill_id, skill_name, COUNT(*) as usage_count,
                      AVG(execution_time) as avg_time,
                      AVG(confidence_score) as avg_confidence
               FROM skill_usage 
               WHERE user_id = ?
               GROUP BY skill_id, skill_name
               ORDER BY usage_count DESC
               LIMIT 20""",
            (user_id,)
        )
        
        return {
            "user_id": user_id,
            "preferred_skills": [
                {
                    "skill_id": row[0],
                    "skill_name": row[1],
                    "usage_count": row[2],
                    "average_execution_time": row[3],
                    "average_confidence": row[4]
                }
                for row in result
            ]
        }


class PerformanceRepository(BaseRepository):
    """Repository for performance metrics."""
    
    async def record_metric(self, metric: PerformanceMetric) -> bool:
        """Record a performance metric."""
        data = metric.to_dict()
        
        result = await self.db.execute_query(
            """INSERT INTO performance_metrics 
               (metric_id, component, metric_name, metric_value, timestamp, 
                context, user_id, conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data['metric_id'], data['component'], data['metric_name'],
             data['metric_value'], data['timestamp'], data['context'],
             data['user_id'], data['conversation_id'])
        )
        
        return result > 0
    
    async def get_component_metrics(self, component: str, 
                                  metric_name: str = None,
                                  hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics for a component."""
        cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        if metric_name:
            result = await self.db.execute_query(
                """SELECT metric_name, metric_value, timestamp, context 
                   FROM performance_metrics 
                   WHERE component = ? AND metric_name = ? AND timestamp > ?
                   ORDER BY timestamp DESC""",
                (component, metric_name, cutoff_time)
            )
        else:
            result = await self.db.execute_query(
                """SELECT metric_name, metric_value, timestamp, context 
                   FROM performance_metrics 
                   WHERE component = ? AND timestamp > ?
                   ORDER BY timestamp DESC""",
                (component, cutoff_time)
            )
        
        return [
            {
                "metric_name": row[0],
                "metric_value": row[1],
                "timestamp": row[2],
                "context": row[3]
            }
            for row in result
        ]
    
    async def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary across all components."""
        cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        result = await self.db.execute_query(
            """SELECT component, metric_name, 
                      COUNT(*) as count,
                      AVG(metric_value) as avg_value,
                      MIN(metric_value) as min_value,
                      MAX(metric_value) as max_value
               FROM performance_metrics 
               WHERE timestamp > ?
               GROUP BY component, metric_name
               ORDER BY component, metric_name""",
            (cutoff_time,)
        )
        
        summary = {}
        for row in result:
            component = row[0]
            if component not in summary:
                summary[component] = {}
            
            summary[component][row[1]] = {
                "count": row[2],
                "average": row[3],
                "minimum": row[4],
                "maximum": row[5]
            }
        
        return summary


class ConfigRepository(BaseRepository):
    """Repository for system configuration."""
    
    async def get_config(self, config_key: str) -> Optional[SystemConfig]:
        """Get configuration value."""
        result = await self.db.execute_query(
            "SELECT * FROM system_config WHERE config_key = ?",
            (config_key,)
        )
        
        if result:
            row = result[0]
            return SystemConfig.from_dict({
                'config_key': row[0],
                'config_value': row[1],
                'config_type': row[2],
                'description': row[3],
                'created_at': row[4],
                'updated_at': row[5],
                'created_by': row[6],
                'updated_by': row[7]
            })
        
        return None
    
    async def set_config(self, config_key: str, config_value: str, 
                        config_type: str, description: str = None,
                        updated_by: str = None) -> bool:
        """Set configuration value."""
        now = datetime.utcnow().isoformat()
        
        # Try to update existing config
        result = await self.db.execute_query(
            """UPDATE system_config SET 
               config_value = ?, config_type = ?, description = ?, 
               updated_at = ?, updated_by = ?
               WHERE config_key = ?""",
            (config_value, config_type, description, now, updated_by, config_key)
        )
        
        if result == 0:
            # Insert new config
            result = await self.db.execute_query(
                """INSERT INTO system_config 
                   (config_key, config_value, config_type, description, 
                    created_at, updated_at, created_by, updated_by) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (config_key, config_value, config_type, description,
                 now, now, updated_by, updated_by)
            )
        
        return result > 0
    
    async def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values."""
        result = await self.db.execute_query(
            "SELECT config_key, config_value, config_type FROM system_config"
        )
        
        config = {}
        for row in result:
            config_obj = SystemConfig(
                config_key=row[0],
                config_value=row[1],
                config_type=row[2]
            )
            config[row[0]] = config_obj.get_typed_value()
        
        return config
    
    async def delete_config(self, config_key: str) -> bool:
        """Delete configuration value."""
        result = await self.db.execute_query(
            "DELETE FROM system_config WHERE config_key = ?",
            (config_key,)
        )
        
        return result > 0

