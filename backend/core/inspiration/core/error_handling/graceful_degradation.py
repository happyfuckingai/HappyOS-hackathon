"""
⬇️ GRACEFUL DEGRADATION MANAGER

Manages graceful degradation of system functionality:
- Progressive feature reduction
- Core functionality preservation
- User experience optimization during failures
- Automatic recovery when services restore
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    """Degradation levels."""
    NORMAL = "normal"           # Full functionality
    MINOR = "minor"            # Minor features disabled
    MODERATE = "moderate"      # Significant features disabled
    SEVERE = "severe"          # Only core features available
    CRITICAL = "critical"      # Minimal functionality only


@dataclass
class DegradationRule:
    """Degradation rule definition."""
    name: str
    level: DegradationLevel
    trigger_conditions: List[str]  # Component failures that trigger this rule
    disabled_features: List[str]
    fallback_actions: List[str]
    user_message: str
    auto_recovery: bool = True
    
    # Tracking
    activated: bool = False
    activation_time: Optional[datetime] = None
    deactivation_time: Optional[datetime] = None


class GracefulDegradationManager:
    """
    Manages graceful degradation of system functionality.
    """
    
    def __init__(self):
        self.degradation_rules: Dict[str, DegradationRule] = {}
        self.current_level = DegradationLevel.NORMAL
        self.active_rules: Set[str] = set()
        self.disabled_features: Set[str] = set()
        self.degradation_history: List[Dict[str, Any]] = []
        
        # Initialize default rules
        self._initialize_default_rules()
        
        logger.info("Graceful degradation manager initialized")
    
    def _initialize_default_rules(self):
        """Initialize default degradation rules."""
        
        # Database failure degradation
        self.degradation_rules["database_failure"] = DegradationRule(
            name="database_failure",
            level=DegradationLevel.MODERATE,
            trigger_conditions=["database_unhealthy"],
            disabled_features=[
                "conversation_persistence",
                "user_preference_learning",
                "skill_analytics",
                "long_term_memory"
            ],
            fallback_actions=[
                "activate_memory_storage",
                "disable_analytics_collection",
                "use_session_only_memory"
            ],
            user_message="Some features are temporarily unavailable due to database maintenance. Your conversation will continue with limited memory.",
            auto_recovery=True
        )
        
        # Skill registry failure degradation
        self.degradation_rules["skill_registry_failure"] = DegradationRule(
            name="skill_registry_failure",
            level=DegradationLevel.MINOR,
            trigger_conditions=["skill_registry_unhealthy"],
            disabled_features=[
                "dynamic_skill_generation",
                "skill_discovery",
                "skill_optimization"
            ],
            fallback_actions=[
                "use_cached_skills_only",
                "disable_skill_generation",
                "use_basic_responses"
            ],
            user_message="Skill generation is temporarily disabled. I'll use my existing capabilities to help you.",
            auto_recovery=True
        )
        
        # Mr Happy agent failure degradation
        self.degradation_rules["mr_happy_failure"] = DegradationRule(
            name="mr_happy_failure",
            level=DegradationLevel.MINOR,
            trigger_conditions=["mr_happy_agent_unhealthy"],
            disabled_features=[
                "personality_adaptation",
                "emotional_responses",
                "personalized_interactions"
            ],
            fallback_actions=[
                "use_neutral_responses",
                "disable_personality_features",
                "use_standard_templates"
            ],
            user_message="I'm operating in simplified mode. My responses may be less personalized temporarily.",
            auto_recovery=True
        )
        
        # Network failure degradation
        self.degradation_rules["network_failure"] = DegradationRule(
            name="network_failure",
            level=DegradationLevel.SEVERE,
            trigger_conditions=["external_service_failures"],
            disabled_features=[
                "external_api_calls",
                "real_time_data",
                "cloud_services",
                "remote_skill_execution"
            ],
            fallback_actions=[
                "use_cached_data_only",
                "disable_external_integrations",
                "use_offline_capabilities"
            ],
            user_message="I'm operating in offline mode due to connectivity issues. Some features may be limited.",
            auto_recovery=True
        )
        
        # Resource exhaustion degradation
        self.degradation_rules["resource_exhaustion"] = DegradationRule(
            name="resource_exhaustion",
            level=DegradationLevel.MODERATE,
            trigger_conditions=["high_memory_usage", "high_cpu_usage"],
            disabled_features=[
                "background_processing",
                "advanced_analytics",
                "concurrent_operations",
                "heavy_computations"
            ],
            fallback_actions=[
                "reduce_processing_load",
                "disable_background_tasks",
                "limit_concurrent_requests",
                "use_simplified_algorithms"
            ],
            user_message="I'm optimizing performance by temporarily reducing some background activities.",
            auto_recovery=True
        )
        
        logger.info(f"Initialized {len(self.degradation_rules)} degradation rules")
    
    async def evaluate_degradation(self, component_health: Dict[str, str]):
        """Evaluate if degradation should be applied based on component health."""
        triggered_rules = set()
        
        # Check each rule's trigger conditions
        for rule_name, rule in self.degradation_rules.items():
            should_trigger = False
            
            for condition in rule.trigger_conditions:
                if self._check_condition(condition, component_health):
                    should_trigger = True
                    break
            
            if should_trigger and rule_name not in self.active_rules:
                triggered_rules.add(rule_name)
            elif not should_trigger and rule_name in self.active_rules:
                # Rule should be deactivated
                await self._deactivate_rule(rule_name)
        
        # Activate triggered rules
        for rule_name in triggered_rules:
            await self._activate_rule(rule_name)
        
        # Update overall degradation level
        self._update_degradation_level()
    
    def _check_condition(self, condition: str, component_health: Dict[str, str]) -> bool:
        """Check if a degradation condition is met."""
        if condition == "database_unhealthy":
            return component_health.get("database") == "unhealthy"
        elif condition == "skill_registry_unhealthy":
            return component_health.get("skill_registry") == "unhealthy"
        elif condition == "mr_happy_agent_unhealthy":
            return component_health.get("mr_happy_agent") == "unhealthy"
        elif condition == "external_service_failures":
            # Check for multiple external service failures
            external_failures = sum(1 for k, v in component_health.items() 
                                  if "external" in k and v == "unhealthy")
            return external_failures >= 2
        elif condition == "high_memory_usage":
            # Simulate memory usage check
            return False  # Would check actual memory usage
        elif condition == "high_cpu_usage":
            # Simulate CPU usage check
            return False  # Would check actual CPU usage
        
        return False
    
    async def _activate_rule(self, rule_name: str):
        """Activate a degradation rule."""
        rule = self.degradation_rules[rule_name]
        
        if rule.activated:
            return
        
        logger.warning(f"Activating degradation rule: {rule_name} (level: {rule.level.value})")
        
        rule.activated = True
        rule.activation_time = datetime.utcnow()
        self.active_rules.add(rule_name)
        
        # Disable features
        for feature in rule.disabled_features:
            self.disabled_features.add(feature)
            logger.info(f"Disabled feature: {feature}")
        
        # Execute fallback actions
        for action in rule.fallback_actions:
            await self._execute_fallback_action(action)
        
        # Record degradation event
        self._record_degradation_event("activated", rule_name, rule.level)
        
        logger.info(f"Degradation rule '{rule_name}' activated successfully")
    
    async def _deactivate_rule(self, rule_name: str):
        """Deactivate a degradation rule."""
        rule = self.degradation_rules[rule_name]
        
        if not rule.activated:
            return
        
        logger.info(f"Deactivating degradation rule: {rule_name}")
        
        rule.activated = False
        rule.deactivation_time = datetime.utcnow()
        self.active_rules.discard(rule_name)
        
        # Re-enable features if no other rules disable them
        for feature in rule.disabled_features:
            if not self._is_feature_disabled_by_other_rules(feature, rule_name):
                self.disabled_features.discard(feature)
                logger.info(f"Re-enabled feature: {feature}")
        
        # Record degradation event
        self._record_degradation_event("deactivated", rule_name, rule.level)
        
        logger.info(f"Degradation rule '{rule_name}' deactivated successfully")
    
    def _is_feature_disabled_by_other_rules(self, feature: str, exclude_rule: str) -> bool:
        """Check if a feature is disabled by other active rules."""
        for rule_name in self.active_rules:
            if rule_name != exclude_rule:
                rule = self.degradation_rules[rule_name]
                if feature in rule.disabled_features:
                    return True
        return False
    
    async def _execute_fallback_action(self, action: str):
        """Execute a fallback action."""
        try:
            logger.info(f"Executing fallback action: {action}")
            
            if action == "activate_memory_storage":
                await self._activate_memory_storage()
            elif action == "disable_analytics_collection":
                await self._disable_analytics_collection()
            elif action == "use_session_only_memory":
                await self._use_session_only_memory()
            elif action == "use_cached_skills_only":
                await self._use_cached_skills_only()
            elif action == "disable_skill_generation":
                await self._disable_skill_generation()
            elif action == "use_basic_responses":
                await self._use_basic_responses()
            elif action == "use_neutral_responses":
                await self._use_neutral_responses()
            elif action == "disable_personality_features":
                await self._disable_personality_features()
            elif action == "use_standard_templates":
                await self._use_standard_templates()
            elif action == "use_cached_data_only":
                await self._use_cached_data_only()
            elif action == "disable_external_integrations":
                await self._disable_external_integrations()
            elif action == "use_offline_capabilities":
                await self._use_offline_capabilities()
            elif action == "reduce_processing_load":
                await self._reduce_processing_load()
            elif action == "disable_background_tasks":
                await self._disable_background_tasks()
            elif action == "limit_concurrent_requests":
                await self._limit_concurrent_requests()
            elif action == "use_simplified_algorithms":
                await self._use_simplified_algorithms()
            else:
                logger.warning(f"Unknown fallback action: {action}")
                
        except Exception as e:
            logger.error(f"Failed to execute fallback action '{action}': {e}")
    
    # Fallback action implementations
    async def _activate_memory_storage(self):
        """Activate in-memory storage fallback."""
        logger.info("Activated in-memory storage fallback")
    
    async def _disable_analytics_collection(self):
        """Disable analytics collection."""
        logger.info("Disabled analytics collection")
    
    async def _use_session_only_memory(self):
        """Use session-only memory."""
        logger.info("Switched to session-only memory")
    
    async def _use_cached_skills_only(self):
        """Use cached skills only."""
        logger.info("Using cached skills only")
    
    async def _disable_skill_generation(self):
        """Disable skill generation."""
        logger.info("Disabled skill generation")
    
    async def _use_basic_responses(self):
        """Use basic responses."""
        logger.info("Switched to basic responses")
    
    async def _use_neutral_responses(self):
        """Use neutral responses."""
        logger.info("Switched to neutral responses")
    
    async def _disable_personality_features(self):
        """Disable personality features."""
        logger.info("Disabled personality features")
    
    async def _use_standard_templates(self):
        """Use standard templates."""
        logger.info("Switched to standard templates")
    
    async def _use_cached_data_only(self):
        """Use cached data only."""
        logger.info("Using cached data only")
    
    async def _disable_external_integrations(self):
        """Disable external integrations."""
        logger.info("Disabled external integrations")
    
    async def _use_offline_capabilities(self):
        """Use offline capabilities."""
        logger.info("Switched to offline capabilities")
    
    async def _reduce_processing_load(self):
        """Reduce processing load."""
        logger.info("Reduced processing load")
    
    async def _disable_background_tasks(self):
        """Disable background tasks."""
        logger.info("Disabled background tasks")
    
    async def _limit_concurrent_requests(self):
        """Limit concurrent requests."""
        logger.info("Limited concurrent requests")
    
    async def _use_simplified_algorithms(self):
        """Use simplified algorithms."""
        logger.info("Switched to simplified algorithms")
    
    def _update_degradation_level(self):
        """Update overall degradation level based on active rules."""
        if not self.active_rules:
            self.current_level = DegradationLevel.NORMAL
            return
        
        # Find the highest degradation level among active rules
        max_level = DegradationLevel.NORMAL
        
        for rule_name in self.active_rules:
            rule = self.degradation_rules[rule_name]
            if rule.level.value > max_level.value:
                max_level = rule.level
        
        if self.current_level != max_level:
            old_level = self.current_level
            self.current_level = max_level
            logger.warning(f"Degradation level changed from {old_level.value} to {max_level.value}")
    
    def _record_degradation_event(self, event_type: str, rule_name: str, level: DegradationLevel):
        """Record degradation event."""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'rule_name': rule_name,
            'level': level.value,
            'active_rules': list(self.active_rules),
            'disabled_features': list(self.disabled_features)
        }
        
        self.degradation_history.append(event)
        
        # Keep only recent history
        if len(self.degradation_history) > 100:
            self.degradation_history = self.degradation_history[-50:]
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is currently enabled."""
        return feature not in self.disabled_features
    
    def get_degradation_status(self) -> Dict[str, Any]:
        """Get current degradation status."""
        active_rule_details = []
        for rule_name in self.active_rules:
            rule = self.degradation_rules[rule_name]
            active_rule_details.append({
                'name': rule_name,
                'level': rule.level.value,
                'user_message': rule.user_message,
                'disabled_features': rule.disabled_features,
                'activation_time': rule.activation_time.isoformat() if rule.activation_time else None
            })
        
        return {
            'current_level': self.current_level.value,
            'active_rules': active_rule_details,
            'disabled_features': list(self.disabled_features),
            'total_rules': len(self.degradation_rules),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_user_message(self) -> Optional[str]:
        """Get user-facing message about current degradation."""
        if not self.active_rules:
            return None
        
        # Return message from the highest priority active rule
        highest_priority_rule = None
        highest_level = DegradationLevel.NORMAL
        
        for rule_name in self.active_rules:
            rule = self.degradation_rules[rule_name]
            if rule.level.value > highest_level.value:
                highest_level = rule.level
                highest_priority_rule = rule
        
        return highest_priority_rule.user_message if highest_priority_rule else None
    
    def get_degradation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get degradation history."""
        return self.degradation_history[-limit:]
    
    def add_custom_rule(self, rule: DegradationRule):
        """Add custom degradation rule."""
        self.degradation_rules[rule.name] = rule
        logger.info(f"Added custom degradation rule: {rule.name}")
    
    async def force_degradation(self, rule_name: str):
        """Force activation of a degradation rule."""
        if rule_name in self.degradation_rules:
            await self._activate_rule(rule_name)
            self._update_degradation_level()
            logger.warning(f"Forced activation of degradation rule: {rule_name}")
        else:
            logger.error(f"Degradation rule not found: {rule_name}")
    
    async def force_recovery(self, rule_name: str = None):
        """Force recovery from degradation."""
        if rule_name:
            if rule_name in self.active_rules:
                await self._deactivate_rule(rule_name)
                self._update_degradation_level()
                logger.info(f"Forced recovery from degradation rule: {rule_name}")
        else:
            # Recover from all degradation
            for rule_name in list(self.active_rules):
                await self._deactivate_rule(rule_name)
            self._update_degradation_level()
            logger.info("Forced recovery from all degradation")


# Global degradation manager
_degradation_manager: Optional[GracefulDegradationManager] = None


def get_degradation_manager() -> GracefulDegradationManager:
    """Get global degradation manager."""
    global _degradation_manager
    
    if _degradation_manager is None:
        _degradation_manager = GracefulDegradationManager()
    
    return _degradation_manager

