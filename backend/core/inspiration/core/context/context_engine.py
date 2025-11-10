"""
Context Awareness Engine for HappyOS.

This engine maintains conversation context, user preferences, and learns from
interactions to provide personalized AI-driven experiences.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import os
from pathlib import Path
from app.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class UserPreferences:
    """Manages user preferences and learned behaviors."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.preferences = {
            "component_types": defaultdict(int),  # Frequency of component types used
            "color_schemes": defaultdict(int),    # Preferred color schemes
            "sizes": defaultdict(int),           # Preferred sizes
            "complexity_level": "medium",        # Preferred complexity
            "interaction_style": "conversational", # Interaction preferences
            "language": "sv",                    # Preferred language
            "theme": "dark",                     # UI theme preference
            "animations": True,                  # Animation preferences
            "notifications": True,               # Notification preferences
            "auto_save": True,                   # Auto-save preferences
        }
        self.interaction_history = []
        self.learning_data = {
            "successful_generations": [],
            "failed_generations": [],
            "user_feedback": [],
            "usage_patterns": []
        }

    def update_preference(self, category: str, value: str, weight: float = 1.0):
        """Update a user preference with weighted learning."""
        if category in self.preferences:
            if isinstance(self.preferences[category], dict):
                self.preferences[category][value] += weight
            else:
                self.preferences[category] = value

    def get_preference(self, category: str) -> Any:
        """Get user preference, with fallback to defaults."""
        if category in self.preferences:
            pref = self.preferences[category]
            if isinstance(pref, dict):
                # Return most frequent choice
                return max(pref.items(), key=lambda x: x[1])[0] if pref else None
            return pref
        return None

    def get_top_preferences(self, category: str, top_n: int = 3) -> List[Tuple[str, int]]:
        """Get top N preferences for a category."""
        if category in self.preferences and isinstance(self.preferences[category], dict):
            sorted_prefs = sorted(
                self.preferences[category].items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_prefs[:top_n]
        return []


class ConversationMemory:
    """Manages conversation context and memory."""

    def __init__(self, user_id: str, max_context_length: int = 50):
        self.user_id = user_id
        self.max_context_length = max_context_length
        self.conversations = []
        self.current_conversation = {
            "id": f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "start_time": datetime.now().isoformat(),
            "messages": [],
            "context": {},
            "generated_components": [],
            "user_actions": []
        }
        self.long_term_memory = {
            "important_facts": [],
            "preferred_workflows": [],
            "recurring_requests": defaultdict(int),
            "learned_patterns": []
        }

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to the current conversation."""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }

        self.current_conversation["messages"].append(message)

        # Maintain max context length
        if len(self.current_conversation["messages"]) > self.max_context_length:
            self.current_conversation["messages"] = self.current_conversation["messages"][-self.max_context_length:]

    def add_component_generation(self, component_data: Dict[str, Any]):
        """Track component generation in conversation."""
        self.current_conversation["generated_components"].append({
            "timestamp": datetime.now().isoformat(),
            "component": component_data
        })

    def add_user_action(self, action: str, details: Dict[str, Any]):
        """Track user actions for learning."""
        user_action = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        self.current_conversation["user_actions"].append(user_action)

    def get_recent_context(self, message_count: int = 10) -> List[Dict]:
        """Get recent conversation context."""
        return self.current_conversation["messages"][-message_count:]

    def get_context_summary(self) -> str:
        """Generate a summary of the current conversation context."""
        messages = self.get_recent_context()
        if not messages:
            return "New conversation started"

        # Extract key information
        user_requests = [m for m in messages if m["role"] == "user"]
        ai_responses = [m for m in messages if m["role"] == "assistant"]
        components_created = len(self.current_conversation["generated_components"])

        summary = f"Conversation with {len(user_requests)} user requests, {len(ai_responses)} AI responses"
        if components_created > 0:
            summary += f", {components_created} components created"

        return summary

    def extract_patterns(self) -> List[str]:
        """Extract recurring patterns from conversation."""
        patterns = []

        # Analyze component generation patterns
        component_types = [comp["component"]["type"] for comp in self.current_conversation["generated_components"]]
        if component_types:
            most_common = max(set(component_types), key=component_types.count)
            patterns.append(f"Prefers {most_common} components")

        # Analyze message patterns
        messages = self.current_conversation["messages"]
        if len(messages) >= 3:
            # Look for question patterns
            question_count = sum(1 for m in messages if "?" in m["content"])
            if question_count > len(messages) * 0.3:
                patterns.append("Asks many questions - needs more guidance")

        return patterns


class ContextEngine:
    """
    Context Awareness Engine.

    Maintains comprehensive context for users including preferences,
    conversation history, and learned behaviors.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or "data/context")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.user_contexts = {}  # user_id -> context_data
        self.active_conversations = {}  # user_id -> ConversationMemory
        self.user_preferences = {}  # user_id -> UserPreferences

        self.llm_client = OpenRouterClient()

        # Context retention settings
        self.context_retention_days = 30
        self.max_conversations_per_user = 100

    async def initialize_user_context(self, user_id: str) -> Dict[str, Any]:
        """Initialize or load user context."""
        if user_id not in self.user_contexts:
            # Try to load from storage
            context_data = await self._load_user_context(user_id)
            if context_data:
                self.user_contexts[user_id] = context_data
            else:
                # Create new context
                self.user_contexts[user_id] = {
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    "last_active": datetime.now().isoformat(),
                    "total_conversations": 0,
                    "total_components_created": 0,
                    "session_count": 0
                }

        # Initialize conversation memory and preferences if not exists
        if user_id not in self.active_conversations:
            self.active_conversations[user_id] = ConversationMemory(user_id)

        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id)

        return self.user_contexts[user_id]

    async def process_user_interaction(self, user_id: str, user_input: str,
                                     analysis_result: Dict[str, Any],
                                     system_response: Optional[str] = None) -> Dict[str, Any]:
        """Process a user interaction and update context."""
        # Initialize user context if needed
        await self.initialize_user_context(user_id)

        # Get conversation memory
        conversation = self.active_conversations[user_id]
        preferences = self.user_preferences[user_id]

        # Add messages to conversation
        conversation.add_message("user", user_input, {
            "analysis": analysis_result,
            "timestamp": datetime.now().isoformat()
        })

        if system_response:
            conversation.add_message("assistant", system_response, {
                "timestamp": datetime.now().isoformat()
            })

        # Update preferences based on analysis
        self._update_preferences_from_analysis(preferences, analysis_result)

        # Update user context stats
        user_context = self.user_contexts[user_id]
        user_context["last_active"] = datetime.now().isoformat()

        # Extract and store patterns
        patterns = conversation.extract_patterns()
        if patterns:
            conversation.long_term_memory["learned_patterns"].extend(patterns)

        return {
            "conversation_id": conversation.current_conversation["id"],
            "context_summary": conversation.get_context_summary(),
            "learned_patterns": patterns,
            "updated_preferences": self._get_preference_summary(preferences)
        }

    def _update_preferences_from_analysis(self, preferences: UserPreferences,
                                        analysis_result: Dict[str, Any]):
        """Update user preferences based on analysis result."""
        entities = analysis_result.get("entities", [])

        # Update component type preferences
        component_type = analysis_result.get("component_type")
        if component_type:
            preferences.update_preference("component_types", component_type)

        # Update other entity-based preferences
        for entity in entities:
            entity_type = entity.get("type")
            entity_value = entity.get("value")

            if entity_type == "color":
                preferences.update_preference("color_schemes", entity_value)
            elif entity_type == "size":
                preferences.update_preference("sizes", entity_value)

        # Update complexity preference based on action plan
        action_plan = analysis_result.get("action_plan", {})
        complexity = action_plan.get("estimated_complexity")
        if complexity:
            preferences.update_preference("complexity_level", complexity, weight=0.5)

    def _get_preference_summary(self, preferences: UserPreferences) -> Dict[str, Any]:
        """Get a summary of user preferences."""
        return {
            "preferred_component_types": preferences.get_top_preferences("component_types", 3),
            "preferred_colors": preferences.get_top_preferences("color_schemes", 3),
            "preferred_sizes": preferences.get_top_preferences("sizes", 2),
            "complexity_level": preferences.get_preference("complexity_level"),
            "theme": preferences.get_preference("theme")
        }

    async def get_context_for_generation(self, user_id: str, user_request: str) -> Dict[str, Any]:
        """Get comprehensive context for component generation."""
        await self.initialize_user_context(user_id)

        conversation = self.active_conversations[user_id]
        preferences = self.user_preferences[user_id]

        # Get recent conversation context
        recent_messages = conversation.get_recent_context(5)

        # Get user preferences summary
        pref_summary = self._get_preference_summary(preferences)

        # Get conversation patterns
        patterns = conversation.extract_patterns()

        # Get previously generated components for reference
        recent_components = conversation.current_conversation["generated_components"][-3:]

        return {
            "user_id": user_id,
            "conversation_context": recent_messages,
            "user_preferences": pref_summary,
            "learned_patterns": patterns,
            "recent_components": recent_components,
            "conversation_summary": conversation.get_context_summary(),
            "long_term_memory": conversation.long_term_memory,
            "current_request": user_request
        }

    async def learn_from_feedback(self, user_id: str, component_data: Dict[str, Any],
                                feedback: Dict[str, Any]):
        """Learn from user feedback on generated components."""
        await self.initialize_user_context(user_id)

        preferences = self.user_preferences[user_id]

        # Store feedback
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component_data,
            "feedback": feedback,
            "rating": feedback.get("rating", 0),
            "comments": feedback.get("comments", "")
        }

        preferences.learning_data["user_feedback"].append(feedback_entry)

        # Learn from positive feedback
        if feedback.get("rating", 0) >= 4:  # Good rating
            component_type = component_data.get("type")
            if component_type:
                preferences.update_preference("component_types", component_type, weight=2.0)

        # Learn from negative feedback
        elif feedback.get("rating", 0) <= 2:  # Poor rating
            component_type = component_data.get("type")
            if component_type:
                # Reduce preference for this type
                preferences.preferences["component_types"][component_type] = max(
                    0, preferences.preferences["component_types"].get(component_type, 0) - 1
                )

    async def get_personalized_suggestions(self, user_id: str) -> List[str]:
        """Get personalized suggestions based on user behavior."""
        await self.initialize_user_context(user_id)

        preferences = self.user_preferences[user_id]
        conversation = self.active_conversations[user_id]

        suggestions = []

        # Suggest preferred component types
        top_components = preferences.get_top_preferences("component_types", 2)
        if top_components:
            comp_type = top_components[0][0]
            suggestions.append(f"Skapa en {comp_type} - det verkar som du gillar dessa!")

        # Suggest based on recent activity
        recent_components = conversation.current_conversation["generated_components"]
        if len(recent_components) >= 2:
            last_type = recent_components[-1]["component"]["type"]
            second_last_type = recent_components[-2]["component"]["type"]
            if last_type == second_last_type:
                suggestions.append(f"Du har skapat flera {last_type} komponenter. Vill du skapa en till?")

        # Suggest based on time of day
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 12:
            suggestions.append("God morgon! Skapa en dashboard för att starta dagen produktivt?")
        elif 18 <= current_hour <= 22:
            suggestions.append("God kväll! Vill du skapa något för att avsluta dagen?")

        return suggestions[:3]  # Max 3 suggestions

    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user behavior and preferences."""
        await self.initialize_user_context(user_id)

        preferences = self.user_preferences[user_id]
        conversation = self.active_conversations[user_id]

        total_conversations = self.user_contexts[user_id]["total_conversations"]
        total_components = self.user_contexts[user_id]["total_components_created"]

        # Analyze component preferences
        component_prefs = preferences.get_top_preferences("component_types", 5)
        color_prefs = preferences.get_top_preferences("color_schemes", 3)

        # Analyze usage patterns
        patterns = conversation.extract_patterns()

        # Calculate engagement metrics
        avg_components_per_conversation = total_components / max(total_conversations, 1)

        return {
            "user_id": user_id,
            "total_conversations": total_conversations,
            "total_components_created": total_components,
            "average_components_per_conversation": round(avg_components_per_conversation, 2),
            "preferred_component_types": component_prefs,
            "preferred_colors": color_prefs,
            "learned_patterns": patterns,
            "complexity_preference": preferences.get_preference("complexity_level"),
            "engagement_level": "high" if avg_components_per_conversation > 1 else "medium" if avg_components_per_conversation > 0.5 else "low"
        }

    async def _load_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load user context from storage."""
        context_file = self.storage_path / f"{user_id}_context.json"

        if context_file.exists():
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if context is still valid (not too old)
                created_at = datetime.fromisoformat(data["created_at"])
                if datetime.now() - created_at < timedelta(days=self.context_retention_days):
                    return data

            except Exception as e:
                logger.error(f"Error loading user context for {user_id}: {e}")

        return None

    async def _save_user_context(self, user_id: str):
        """Save user context to storage."""
        if user_id in self.user_contexts:
            context_file = self.storage_path / f"{user_id}_context.json"

            try:
                with open(context_file, 'w', encoding='utf-8') as f:
                    json.dump(self.user_contexts[user_id], f, indent=2, ensure_ascii=False)

            except Exception as e:
                logger.error(f"Error saving user context for {user_id}: {e}")

    async def cleanup_old_contexts(self):
        """Clean up old user contexts."""
        cutoff_date = datetime.now() - timedelta(days=self.context_retention_days)

        for context_file in self.storage_path.glob("*_context.json"):
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                created_at = datetime.fromisoformat(data["created_at"])
                if created_at < cutoff_date:
                    context_file.unlink()
                    logger.info(f"Cleaned up old context: {context_file.name}")

            except Exception as e:
                logger.error(f"Error cleaning up context {context_file.name}: {e}")

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data for backup or migration."""
        await self.initialize_user_context(user_id)

        return {
            "user_context": self.user_contexts[user_id],
            "conversation_memory": self.active_conversations[user_id].current_conversation,
            "preferences": {
                "preferences": dict(self.user_preferences[user_id].preferences),
                "learning_data": self.user_preferences[user_id].learning_data
            },
            "long_term_memory": self.active_conversations[user_id].long_term_memory,
            "exported_at": datetime.now().isoformat()
        }


# Global context engine instance
context_engine = ContextEngine()


async def get_user_context(user_id: str) -> Dict[str, Any]:
    """Convenience function to get user context."""
    return await context_engine.initialize_user_context(user_id)


async def process_interaction(user_id: str, user_input: str,
                            analysis_result: Dict[str, Any],
                            system_response: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to process user interactions."""
    return await context_engine.process_user_interaction(
        user_id, user_input, analysis_result, system_response
    )