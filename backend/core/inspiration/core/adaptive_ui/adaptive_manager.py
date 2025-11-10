"""
Adaptive UI Behavior Manager for HappyOS.

This system manages dynamic interface adjustments based on:
- User preferences and behavior patterns
- Device and context information
- Real-time interaction feedback
- Environmental factors
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


class AdaptiveRule:
    """Represents an adaptive UI rule."""

    def __init__(self, rule_id: str, condition: Dict[str, Any], action: Dict[str, Any],
                 priority: int = 1, enabled: bool = True):
        self.rule_id = rule_id
        self.condition = condition
        self.action = action
        self.priority = priority
        self.enabled = enabled
        self.activation_count = 0
        self.last_activated = None
        self.success_rate = 0.0

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if the rule condition is met."""
        try:
            return self._evaluate_condition(self.condition, context)
        except Exception as e:
            logger.error(f"Error evaluating rule {self.rule_id}: {e}")
            return False

    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Recursively evaluate condition."""
        condition_type = condition.get("type")

        if condition_type == "and":
            return all(self._evaluate_condition(sub_cond, context) for sub_cond in condition.get("conditions", []))
        elif condition_type == "or":
            return any(self._evaluate_condition(sub_cond, context) for sub_cond in condition.get("conditions", []))
        elif condition_type == "equals":
            return context.get(condition.get("field")) == condition.get("value")
        elif condition_type == "contains":
            value = context.get(condition.get("field"), "")
            return condition.get("value", "") in str(value)
        elif condition_type == "greater_than":
            return float(context.get(condition.get("field"), 0)) > float(condition.get("value", 0))
        elif condition_type == "less_than":
            return float(context.get(condition.get("field"), 0)) < float(condition.get("value", 0))
        elif condition_type == "time_range":
            current_hour = datetime.now().hour
            start_hour = condition.get("start_hour", 0)
            end_hour = condition.get("end_hour", 23)
            return start_hour <= current_hour <= end_hour

        return False

    def apply(self, ui_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the rule action to the UI state."""
        try:
            self.activation_count += 1
            self.last_activated = datetime.now()

            return self._apply_action(self.action, ui_state)
        except Exception as e:
            logger.error(f"Error applying rule {self.rule_id}: {e}")
            return ui_state

    def _apply_action(self, action: Dict[str, Any], ui_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply action to UI state."""
        action_type = action.get("type")
        new_state = ui_state.copy()

        if action_type == "set_property":
            path = action.get("path", "").split(".")
            value = action.get("value")

            # Navigate to the property path
            current = new_state
            for key in path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            current[path[-1]] = value

        elif action_type == "modify_layout":
            layout_changes = action.get("changes", {})
            if "layout" not in new_state:
                new_state["layout"] = {}

            new_state["layout"].update(layout_changes)

        elif action_type == "adjust_component":
            component_id = action.get("component_id")
            adjustments = action.get("adjustments", {})

            if "components" not in new_state:
                new_state["components"] = {}

            if component_id not in new_state["components"]:
                new_state["components"][component_id] = {}

            new_state["components"][component_id].update(adjustments)

        elif action_type == "trigger_behavior":
            behavior = action.get("behavior")
            if "behaviors" not in new_state:
                new_state["behaviors"] = []
            new_state["behaviors"].append(behavior)

        return new_state


class AdaptiveUIManager:
    """
    Adaptive UI Manager.

    Manages adaptive behavior rules and applies them to create
    personalized, context-aware user interfaces.
    """

    def __init__(self):
        self.rules: Dict[str, AdaptiveRule] = {}
        self.active_contexts: Dict[str, Dict[str, Any]] = {}
        self.learning_data: Dict[str, Any] = {
            "rule_performance": defaultdict(list),
            "user_patterns": defaultdict(list),
            "context_transitions": []
        }
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Initialize default adaptive rules."""

        # Time-based rules
        self.add_rule(AdaptiveRule(
            "morning_mode",
            {
                "type": "time_range",
                "start_hour": 6,
                "end_hour": 11
            },
            {
                "type": "modify_layout",
                "changes": {
                    "theme": "light",
                    "energy": "high",
                    "focus": "productivity"
                }
            },
            priority=2
        ))

        self.add_rule(AdaptiveRule(
            "evening_mode",
            {
                "type": "time_range",
                "start_hour": 18,
                "end_hour": 22
            },
            {
                "type": "modify_layout",
                "changes": {
                    "theme": "dark",
                    "energy": "low",
                    "focus": "relaxation"
                }
            },
            priority=2
        ))

        # User preference rules
        self.add_rule(AdaptiveRule(
            "dark_mode_preference",
            {
                "type": "equals",
                "field": "user.theme",
                "value": "dark"
            },
            {
                "type": "set_property",
                "path": "theme",
                "value": "dark"
            },
            priority=3
        ))

        self.add_rule(AdaptiveRule(
            "high_complexity_preference",
            {
                "type": "equals",
                "field": "user.complexity_preference",
                "value": "high"
            },
            {
                "type": "modify_layout",
                "changes": {
                    "show_advanced_options": True,
                    "component_density": "high"
                }
            },
            priority=2
        ))

        # Device context rules
        self.add_rule(AdaptiveRule(
            "mobile_context",
            {
                "type": "equals",
                "field": "device.type",
                "value": "mobile"
            },
            {
                "type": "modify_layout",
                "changes": {
                    "layout": "single_column",
                    "touch_targets": "large",
                    "font_size": "large"
                }
            },
            priority=4
        ))

        # Engagement-based rules
        self.add_rule(AdaptiveRule(
            "high_engagement",
            {
                "type": "greater_than",
                "field": "user.engagement_level",
                "value": 0.7
            },
            {
                "type": "modify_layout",
                "changes": {
                    "show_suggestions": True,
                    "enable_shortcuts": True,
                    "auto_advance": True
                }
            },
            priority=2
        ))

        # Component creation patterns
        self.add_rule(AdaptiveRule(
            "frequent_dashboard_user",
            {
                "type": "contains",
                "field": "user.frequent_components",
                "value": "dashboard"
            },
            {
                "type": "trigger_behavior",
                "behavior": "suggest_dashboard_templates"
            },
            priority=1
        ))

    def add_rule(self, rule: AdaptiveRule):
        """Add an adaptive rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added adaptive rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str):
        """Remove an adaptive rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed adaptive rule: {rule_id}")

    def enable_rule(self, rule_id: str):
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str):
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False

    async def adapt_ui(self, user_id: str, current_ui_state: Dict[str, Any],
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt the UI based on user context and rules.

        Args:
            user_id: Unique user identifier
            current_ui_state: Current UI state
            context: User and environmental context

        Returns:
            Adapted UI state
        """
        try:
            # Update active context
            self.active_contexts[user_id] = context

            # Get applicable rules
            applicable_rules = self._get_applicable_rules(context)

            if not applicable_rules:
                return current_ui_state

            # Apply rules in priority order
            adapted_state = current_ui_state.copy()
            applied_rules = []

            for rule in applicable_rules:
                if rule.evaluate(context):
                    old_state = adapted_state.copy()
                    adapted_state = rule.apply(adapted_state)
                    applied_rules.append({
                        "rule_id": rule.rule_id,
                        "priority": rule.priority,
                        "changes": self._diff_states(old_state, adapted_state)
                    })

                    # Track rule performance
                    self.learning_data["rule_performance"][rule.rule_id].append({
                        "timestamp": datetime.now().isoformat(),
                        "user_id": user_id,
                        "context": context.copy()
                    })

            # Log adaptation
            if applied_rules:
                logger.info(f"Applied {len(applied_rules)} adaptive rules for user {user_id}")

                # Track context transitions
                self.learning_data["context_transitions"].append({
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id,
                    "from_context": self.active_contexts.get(user_id, {}),
                    "to_context": context,
                    "applied_rules": applied_rules
                })

            return adapted_state

        except Exception as e:
            logger.error(f"Error adapting UI for user {user_id}: {e}")
            return current_ui_state

    def _get_applicable_rules(self, context: Dict[str, Any]) -> List[AdaptiveRule]:
        """Get rules applicable to the current context."""
        applicable = []

        for rule in self.rules.values():
            if rule.enabled and rule.evaluate(context):
                applicable.append(rule)

        # Sort by priority (higher priority first)
        applicable.sort(key=lambda r: r.priority, reverse=True)

        return applicable

    def _diff_states(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the difference between two states."""
        def deep_diff(old, new, path=""):
            diff = {}

            # Find new or changed keys
            for key in new:
                if key not in old:
                    diff[f"{path}.{key}" if path else key] = new[key]
                elif isinstance(new[key], dict) and isinstance(old[key], dict):
                    sub_diff = deep_diff(old[key], new[key], f"{path}.{key}" if path else key)
                    diff.update(sub_diff)
                elif new[key] != old[key]:
                    diff[f"{path}.{key}" if path else key] = new[key]

            return diff

        return deep_diff(old_state, new_state)

    async def learn_from_interaction(self, user_id: str, interaction: Dict[str, Any],
                                   feedback: Optional[Dict[str, Any]] = None):
        """
        Learn from user interactions to improve adaptive behavior.

        Args:
            user_id: User identifier
            interaction: Interaction data
            feedback: Optional user feedback
        """
        try:
            # Store interaction pattern
            self.learning_data["user_patterns"][user_id].append({
                "timestamp": datetime.now().isoformat(),
                "interaction": interaction,
                "feedback": feedback
            })

            # Limit stored patterns to last 1000 per user
            if len(self.learning_data["user_patterns"][user_id]) > 1000:
                self.learning_data["user_patterns"][user_id] = self.learning_data["user_patterns"][user_id][-1000:]

            # Generate new rules based on patterns (simple implementation)
            await self._generate_dynamic_rules(user_id)

        except Exception as e:
            logger.error(f"Error learning from interaction for user {user_id}: {e}")

    async def _generate_dynamic_rules(self, user_id: str):
        """Generate dynamic rules based on user patterns."""
        patterns = self.learning_data["user_patterns"][user_id]

        if len(patterns) < 10:  # Need minimum data
            return

        # Analyze patterns for common behaviors
        recent_patterns = patterns[-20:]  # Last 20 interactions

        # Example: Create rule for frequent component type usage
        component_types = [p.get("interaction", {}).get("component_type") for p in recent_patterns if p.get("interaction", {}).get("component_type")]

        if len(component_types) >= 5:
            most_common = max(set(component_types), key=component_types.count)
            frequency = component_types.count(most_common) / len(component_types)

            if frequency > 0.6:  # 60% usage
                rule_id = f"frequent_{most_common}_user_{user_id}"

                if rule_id not in self.rules:
                    rule = AdaptiveRule(
                        rule_id,
                        {
                            "type": "equals",
                            "field": "user_id",
                            "value": user_id
                        },
                        {
                            "type": "trigger_behavior",
                            "behavior": f"suggest_{most_common}_components"
                        },
                        priority=1
                    )

                    self.add_rule(rule)
                    logger.info(f"Generated dynamic rule for frequent {most_common} usage: {rule_id}")

    async def get_personalized_recommendations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get personalized recommendations based on learned patterns."""
        try:
            patterns = self.learning_data["user_patterns"][user_id]

            if len(patterns) < 5:
                return []

            # Analyze recent patterns
            recent = patterns[-10:]

            recommendations = []

            # Time-based recommendations
            current_hour = datetime.now().hour
            if 6 <= current_hour <= 11:
                morning_interactions = [p for p in recent if 6 <= datetime.fromisoformat(p["timestamp"]).hour <= 11]
                if morning_interactions:
                    recommendations.append({
                        "type": "time_based",
                        "title": "Morning Productivity Mode",
                        "description": "Based on your morning activity, consider creating a dashboard",
                        "confidence": 0.8
                    })

            # Component-based recommendations
            component_types = [p.get("interaction", {}).get("component_type") for p in recent if p.get("interaction", {}).get("component_type")]
            if component_types:
                most_common = max(set(component_types), key=component_types.count)
                recommendations.append({
                    "type": "component_based",
                    "title": f"Try Advanced {most_common.title()}",
                    "description": f"You frequently use {most_common} components. Try the advanced version!",
                    "confidence": 0.7
                })

            return recommendations[:5]  # Max 5 recommendations

        except Exception as e:
            logger.error(f"Error getting recommendations for user {user_id}: {e}")
            return []

    async def get_adaptation_stats(self) -> Dict[str, Any]:
        """Get statistics about adaptive behavior."""
        try:
            total_rules = len(self.rules)
            enabled_rules = len([r for r in self.rules.values() if r.enabled])
            total_users = len(self.active_contexts)

            rule_stats = {}
            for rule_id, rule in self.rules.items():
                rule_stats[rule_id] = {
                    "enabled": rule.enabled,
                    "priority": rule.priority,
                    "activation_count": rule.activation_count,
                    "last_activated": rule.last_activated.isoformat() if rule.last_activated else None,
                    "success_rate": rule.success_rate
                }

            return {
                "total_rules": total_rules,
                "enabled_rules": enabled_rules,
                "disabled_rules": total_rules - enabled_rules,
                "active_users": total_users,
                "rule_statistics": rule_stats,
                "learning_data_size": len(json.dumps(self.learning_data))
            }

        except Exception as e:
            logger.error(f"Error getting adaptation stats: {e}")
            return {"error": str(e)}

    async def export_user_rules(self, user_id: str) -> Dict[str, Any]:
        """Export adaptive rules and patterns for a specific user."""
        try:
            user_patterns = self.learning_data["user_patterns"].get(user_id, [])
            user_context = self.active_contexts.get(user_id, {})

            # Get user-specific rules
            user_rules = {}
            for rule_id, rule in self.rules.items():
                if user_id in rule_id:
                    user_rules[rule_id] = {
                        "rule_id": rule.rule_id,
                        "condition": rule.condition,
                        "action": rule.action,
                        "priority": rule.priority,
                        "enabled": rule.enabled,
                        "activation_count": rule.activation_count
                    }

            return {
                "user_id": user_id,
                "exported_at": datetime.now().isoformat(),
                "user_context": user_context,
                "user_rules": user_rules,
                "pattern_count": len(user_patterns),
                "recent_patterns": user_patterns[-10:]  # Last 10 patterns
            }

        except Exception as e:
            logger.error(f"Error exporting user rules for {user_id}: {e}")
            return {"error": str(e)}


# Global adaptive UI manager instance
adaptive_manager = AdaptiveUIManager()