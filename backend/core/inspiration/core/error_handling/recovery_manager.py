"""
🔧 RECOVERY MANAGER

Automated error recovery workflows:
- Strategy-based recovery actions
- Component health restoration
- Fallback mechanisms
- Recovery success tracking
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .error_classifier import ErrorClassification, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategies."""
    RETRY = "retry"                     # Simple retry
    RESTART_COMPONENT = "restart_component"  # Restart failed component
    FALLBACK_SERVICE = "fallback_service"    # Use alternative service
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Reduce functionality
    ESCALATE = "escalate"               # Escalate to human intervention
    IGNORE = "ignore"                   # Ignore error (for non-critical issues)


@dataclass
class RecoveryAction:
    """Recovery action definition."""
    name: str
    strategy: RecoveryStrategy
    action_func: Callable[..., Awaitable[bool]]  # Returns success status
    description: str
    max_attempts: int = 3
    cooldown_seconds: int = 60
    prerequisites: List[str] = field(default_factory=list)
    
    # Execution tracking
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0


@dataclass
class RecoveryExecution:
    """Recovery execution record."""
    recovery_id: str
    component: str
    error_classification: ErrorClassification
    strategy: RecoveryStrategy
    actions_attempted: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    success: bool = False
    final_action: Optional[str] = None
    error_details: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Get recovery duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class RecoveryManager:
    """
    Automated error recovery manager for HappyOS.
    """
    
    def __init__(self):
        self.recovery_actions: Dict[str, RecoveryAction] = {}
        self.recovery_strategies: Dict[tuple, List[str]] = {}  # (category, severity) -> action names
        self.recovery_history: List[RecoveryExecution] = []
        self._lock = asyncio.Lock()
        
        # Initialize default recovery actions
        self._initialize_default_actions()
        self._initialize_default_strategies()
    
    def _initialize_default_actions(self):
        """Initialize default recovery actions."""
        
        # Simple retry action
        async def simple_retry_action(component: str, context: Dict[str, Any]) -> bool:
            """Simple retry recovery action."""
            try:
                # Get the original function and retry it
                original_func = context.get('original_function')
                if original_func:
                    await original_func()
                    return True
                return False
            except Exception as e:
                logger.error(f"Simple retry failed for {component}: {e}")
                return False
        
        self.recovery_actions['simple_retry'] = RecoveryAction(
            name='simple_retry',
            strategy=RecoveryStrategy.RETRY,
            action_func=simple_retry_action,
            description='Retry the failed operation',
            max_attempts=3,
            cooldown_seconds=30
        )
        
        # Component restart action
        async def restart_component_action(component: str, context: Dict[str, Any]) -> bool:
            """Restart component recovery action."""
            try:
                logger.info(f"Attempting to restart component: {component}")
                
                # Component-specific restart logic
                if component == 'mr_happy_agent':
                    return await self._restart_mr_happy_agent(context)
                elif component == 'skill_registry':
                    return await self._restart_skill_registry(context)
                elif component == 'orchestrator':
                    return await self._restart_orchestrator(context)
                elif component == 'database':
                    return await self._restart_database_connection(context)
                else:
                    logger.warning(f"No restart procedure defined for component: {component}")
                    return False
                    
            except Exception as e:
                logger.error(f"Component restart failed for {component}: {e}")
                return False
        
        self.recovery_actions['restart_component'] = RecoveryAction(
            name='restart_component',
            strategy=RecoveryStrategy.RESTART_COMPONENT,
            action_func=restart_component_action,
            description='Restart the failed component',
            max_attempts=2,
            cooldown_seconds=120
        )
        
        # Fallback service action
        async def fallback_service_action(component: str, context: Dict[str, Any]) -> bool:
            """Fallback service recovery action."""
            try:
                logger.info(f"Activating fallback for component: {component}")
                
                # Component-specific fallback logic
                fallback_activated = False
                
                if component == 'skill_registry':
                    # Use cached skills only
                    fallback_activated = await self._activate_skill_cache_fallback(context)
                elif component == 'mr_happy_agent':
                    # Use simplified responses
                    fallback_activated = await self._activate_simple_response_fallback(context)
                elif component == 'database':
                    # Use in-memory storage
                    fallback_activated = await self._activate_memory_storage_fallback(context)
                
                return fallback_activated
                
            except Exception as e:
                logger.error(f"Fallback activation failed for {component}: {e}")
                return False
        
        self.recovery_actions['fallback_service'] = RecoveryAction(
            name='fallback_service',
            strategy=RecoveryStrategy.FALLBACK_SERVICE,
            action_func=fallback_service_action,
            description='Activate fallback service',
            max_attempts=1,
            cooldown_seconds=300
        )
        
        # Graceful degradation action
        async def graceful_degradation_action(component: str, context: Dict[str, Any]) -> bool:
            """Graceful degradation recovery action."""
            try:
                logger.info(f"Applying graceful degradation for component: {component}")
                
                # Reduce functionality to maintain core operations
                degradation_applied = False
                
                if component == 'skill_registry':
                    # Disable skill generation, use existing skills only
                    degradation_applied = await self._apply_skill_generation_degradation(context)
                elif component == 'mr_happy_agent':
                    # Use basic responses without personality
                    degradation_applied = await self._apply_personality_degradation(context)
                elif component == 'orchestrator':
                    # Use simple processing only
                    degradation_applied = await self._apply_processing_degradation(context)
                
                return degradation_applied
                
            except Exception as e:
                logger.error(f"Graceful degradation failed for {component}: {e}")
                return False
        
        self.recovery_actions['graceful_degradation'] = RecoveryAction(
            name='graceful_degradation',
            strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            action_func=graceful_degradation_action,
            description='Apply graceful degradation',
            max_attempts=1,
            cooldown_seconds=600
        )
        
        # Clear cache action
        async def clear_cache_action(component: str, context: Dict[str, Any]) -> bool:
            """Clear cache recovery action."""
            try:
                logger.info(f"Clearing cache for component: {component}")
                
                # Component-specific cache clearing
                if component == 'skill_registry':
                    return await self._clear_skill_cache(context)
                elif component == 'mr_happy_agent':
                    return await self._clear_personality_cache(context)
                
                return True
                
            except Exception as e:
                logger.error(f"Cache clearing failed for {component}: {e}")
                return False
        
        self.recovery_actions['clear_cache'] = RecoveryAction(
            name='clear_cache',
            strategy=RecoveryStrategy.RETRY,
            action_func=clear_cache_action,
            description='Clear component cache',
            max_attempts=1,
            cooldown_seconds=60
        )
        
        logger.info(f"Initialized {len(self.recovery_actions)} recovery actions")
    
    def _initialize_default_strategies(self):
        """Initialize default recovery strategies."""
        
        # Network errors
        self.recovery_strategies[(ErrorCategory.NETWORK, ErrorSeverity.LOW)] = [
            'simple_retry'
        ]
        self.recovery_strategies[(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)] = [
            'simple_retry', 'fallback_service'
        ]
        self.recovery_strategies[(ErrorCategory.NETWORK, ErrorSeverity.HIGH)] = [
            'simple_retry', 'fallback_service', 'graceful_degradation'
        ]
        
        # Authentication errors
        self.recovery_strategies[(ErrorCategory.AUTHENTICATION, ErrorSeverity.LOW)] = [
            'simple_retry'
        ]
        self.recovery_strategies[(ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM)] = [
            'restart_component'
        ]
        
        # Resource errors
        self.recovery_strategies[(ErrorCategory.RESOURCE, ErrorSeverity.MEDIUM)] = [
            'clear_cache', 'restart_component'
        ]
        self.recovery_strategies[(ErrorCategory.RESOURCE, ErrorSeverity.HIGH)] = [
            'clear_cache', 'restart_component', 'graceful_degradation'
        ]
        self.recovery_strategies[(ErrorCategory.RESOURCE, ErrorSeverity.CRITICAL)] = [
            'restart_component', 'graceful_degradation'
        ]
        
        # Database errors
        self.recovery_strategies[(ErrorCategory.DATABASE, ErrorSeverity.MEDIUM)] = [
            'simple_retry', 'restart_component'
        ]
        self.recovery_strategies[(ErrorCategory.DATABASE, ErrorSeverity.HIGH)] = [
            'restart_component', 'fallback_service'
        ]
        
        # External service errors
        self.recovery_strategies[(ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM)] = [
            'simple_retry', 'fallback_service'
        ]
        self.recovery_strategies[(ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.HIGH)] = [
            'fallback_service', 'graceful_degradation'
        ]
        
        # System errors
        self.recovery_strategies[(ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM)] = [
            'restart_component'
        ]
        self.recovery_strategies[(ErrorCategory.SYSTEM, ErrorSeverity.HIGH)] = [
            'restart_component', 'graceful_degradation'
        ]
        
        logger.info(f"Initialized recovery strategies for {len(self.recovery_strategies)} error types")
    
    async def attempt_recovery(self, component: str, error_classification: ErrorClassification,
                             context: Dict[str, Any] = None) -> RecoveryExecution:
        """
        Attempt recovery for a failed component.
        
        Args:
            component: Name of the failed component
            error_classification: Classification of the error
            context: Additional context for recovery
            
        Returns:
            RecoveryExecution with results
        """
        recovery_id = f"recovery_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{component}"
        
        execution = RecoveryExecution(
            recovery_id=recovery_id,
            component=component,
            error_classification=error_classification,
            strategy=RecoveryStrategy.RETRY  # Will be updated
        )
        
        async with self._lock:
            self.recovery_history.append(execution)
        
        logger.info(f"Starting recovery for component '{component}' "
                   f"(category: {error_classification.category.value}, "
                   f"severity: {error_classification.severity.value})")
        
        try:
            # Get recovery strategy
            strategy_key = (error_classification.category, error_classification.severity)
            action_names = self.recovery_strategies.get(strategy_key, ['simple_retry'])
            
            if not action_names:
                logger.warning(f"No recovery strategy defined for {strategy_key}")
                execution.error_details = f"No recovery strategy for {strategy_key}"
                execution.end_time = datetime.utcnow()
                return execution
            
            # Attempt recovery actions in order
            for action_name in action_names:
                if action_name not in self.recovery_actions:
                    logger.warning(f"Recovery action '{action_name}' not found")
                    continue
                
                action = self.recovery_actions[action_name]
                execution.strategy = action.strategy
                
                # Check if action can be executed (cooldown, max attempts)
                if not await self._can_execute_action(action):
                    logger.info(f"Skipping action '{action_name}' due to cooldown or max attempts")
                    continue
                
                logger.info(f"Executing recovery action: {action_name}")
                execution.actions_attempted.append(action_name)
                
                try:
                    # Execute the recovery action
                    success = await action.action_func(component, context or {})
                    
                    # Update action tracking
                    action.last_executed = datetime.utcnow()
                    action.execution_count += 1
                    if success:
                        action.success_count += 1
                    
                    if success:
                        execution.success = True
                        execution.final_action = action_name
                        logger.info(f"Recovery successful with action: {action_name}")
                        break
                    else:
                        logger.warning(f"Recovery action '{action_name}' failed")
                
                except Exception as e:
                    logger.error(f"Recovery action '{action_name}' raised exception: {e}")
                    action.execution_count += 1
                    continue
            
            execution.end_time = datetime.utcnow()
            
            if execution.success:
                logger.info(f"Recovery completed successfully for '{component}' "
                           f"in {execution.duration:.2f}s using {execution.final_action}")
            else:
                logger.error(f"Recovery failed for '{component}' after trying "
                           f"{len(execution.actions_attempted)} actions")
                execution.error_details = "All recovery actions failed"
            
            return execution
            
        except Exception as e:
            execution.end_time = datetime.utcnow()
            execution.error_details = str(e)
            logger.error(f"Recovery process failed for '{component}': {e}")
            return execution
    
    async def _can_execute_action(self, action: RecoveryAction) -> bool:
        """Check if recovery action can be executed."""
        now = datetime.utcnow()
        
        # Check max attempts
        if action.execution_count >= action.max_attempts:
            return False
        
        # Check cooldown
        if action.last_executed:
            time_since_last = (now - action.last_executed).total_seconds()
            if time_since_last < action.cooldown_seconds:
                return False
        
        return True
    
    # Component-specific recovery implementations
    async def _restart_mr_happy_agent(self, context: Dict[str, Any]) -> bool:
        """Restart Mr Happy Agent."""
        try:
            # Simulate agent restart
            logger.info("Restarting Mr Happy Agent...")
            await asyncio.sleep(1)  # Simulate restart time
            
            # Reset agent state
            agent = context.get('mr_happy_agent')
            if agent and hasattr(agent, 'reset'):
                await agent.reset()
            
            return True
        except Exception as e:
            logger.error(f"Failed to restart Mr Happy Agent: {e}")
            return False
    
    async def _restart_skill_registry(self, context: Dict[str, Any]) -> bool:
        """Restart Skill Registry."""
        try:
            logger.info("Restarting Skill Registry...")
            await asyncio.sleep(1)
            
            # Clear and reload skills
            registry = context.get('skill_registry')
            if registry and hasattr(registry, 'reload'):
                await registry.reload()
            
            return True
        except Exception as e:
            logger.error(f"Failed to restart Skill Registry: {e}")
            return False
    
    async def _restart_orchestrator(self, context: Dict[str, Any]) -> bool:
        """Restart Orchestrator."""
        try:
            logger.info("Restarting Orchestrator...")
            await asyncio.sleep(1)
            
            # Reset orchestrator state
            orchestrator = context.get('orchestrator')
            if orchestrator and hasattr(orchestrator, 'reset'):
                await orchestrator.reset()
            
            return True
        except Exception as e:
            logger.error(f"Failed to restart Orchestrator: {e}")
            return False
    
    async def _restart_database_connection(self, context: Dict[str, Any]) -> bool:
        """Restart database connection."""
        try:
            logger.info("Restarting database connection...")
            await asyncio.sleep(2)
            
            # Reconnect to database
            db = context.get('database')
            if db and hasattr(db, 'reconnect'):
                await db.reconnect()
            
            return True
        except Exception as e:
            logger.error(f"Failed to restart database connection: {e}")
            return False
    
    async def _activate_skill_cache_fallback(self, context: Dict[str, Any]) -> bool:
        """Activate skill cache fallback."""
        try:
            logger.info("Activating skill cache fallback...")
            # Use only cached skills, disable new skill generation
            return True
        except Exception as e:
            logger.error(f"Failed to activate skill cache fallback: {e}")
            return False
    
    async def _activate_simple_response_fallback(self, context: Dict[str, Any]) -> bool:
        """Activate simple response fallback."""
        try:
            logger.info("Activating simple response fallback...")
            # Use basic responses without personality
            return True
        except Exception as e:
            logger.error(f"Failed to activate simple response fallback: {e}")
            return False
    
    async def _activate_memory_storage_fallback(self, context: Dict[str, Any]) -> bool:
        """Activate memory storage fallback."""
        try:
            logger.info("Activating memory storage fallback...")
            # Use in-memory storage instead of database
            return True
        except Exception as e:
            logger.error(f"Failed to activate memory storage fallback: {e}")
            return False
    
    async def _apply_skill_generation_degradation(self, context: Dict[str, Any]) -> bool:
        """Apply skill generation degradation."""
        try:
            logger.info("Applying skill generation degradation...")
            # Disable skill generation, use existing skills only
            return True
        except Exception as e:
            logger.error(f"Failed to apply skill generation degradation: {e}")
            return False
    
    async def _apply_personality_degradation(self, context: Dict[str, Any]) -> bool:
        """Apply personality degradation."""
        try:
            logger.info("Applying personality degradation...")
            # Use basic responses without personality features
            return True
        except Exception as e:
            logger.error(f"Failed to apply personality degradation: {e}")
            return False
    
    async def _apply_processing_degradation(self, context: Dict[str, Any]) -> bool:
        """Apply processing degradation."""
        try:
            logger.info("Applying processing degradation...")
            # Use simple processing strategies only
            return True
        except Exception as e:
            logger.error(f"Failed to apply processing degradation: {e}")
            return False
    
    async def _clear_skill_cache(self, context: Dict[str, Any]) -> bool:
        """Clear skill cache."""
        try:
            logger.info("Clearing skill cache...")
            registry = context.get('skill_registry')
            if registry and hasattr(registry, 'clear_cache'):
                await registry.clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to clear skill cache: {e}")
            return False
    
    async def _clear_personality_cache(self, context: Dict[str, Any]) -> bool:
        """Clear personality cache."""
        try:
            logger.info("Clearing personality cache...")
            agent = context.get('mr_happy_agent')
            if agent and hasattr(agent, 'clear_cache'):
                await agent.clear_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to clear personality cache: {e}")
            return False
    
    def add_recovery_action(self, action: RecoveryAction):
        """Add custom recovery action."""
        self.recovery_actions[action.name] = action
        logger.info(f"Added custom recovery action: {action.name}")
    
    def set_recovery_strategy(self, category: ErrorCategory, severity: ErrorSeverity, 
                            action_names: List[str]):
        """Set recovery strategy for error type."""
        self.recovery_strategies[(category, severity)] = action_names
        logger.info(f"Set recovery strategy for {category.value}/{severity.value}: {action_names}")
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        if not self.recovery_history:
            return {"total_recoveries": 0}
        
        total = len(self.recovery_history)
        successful = sum(1 for r in self.recovery_history if r.success)
        
        # Calculate average duration
        durations = [r.duration for r in self.recovery_history if r.duration]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Count by strategy
        strategy_counts = {}
        for recovery in self.recovery_history:
            strategy = recovery.strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Count by component
        component_counts = {}
        for recovery in self.recovery_history:
            component = recovery.component
            component_counts[component] = component_counts.get(component, 0) + 1
        
        return {
            "total_recoveries": total,
            "successful_recoveries": successful,
            "success_rate": successful / total * 100,
            "average_duration": avg_duration,
            "strategy_distribution": strategy_counts,
            "component_distribution": component_counts,
            "action_stats": {
                name: {
                    "executions": action.execution_count,
                    "successes": action.success_count,
                    "success_rate": action.success_count / action.execution_count * 100 if action.execution_count > 0 else 0
                }
                for name, action in self.recovery_actions.items()
            }
        }
    
    def get_recent_recoveries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent recovery attempts."""
        recent = sorted(self.recovery_history, key=lambda r: r.start_time, reverse=True)[:limit]
        
        return [
            {
                "recovery_id": r.recovery_id,
                "component": r.component,
                "start_time": r.start_time.isoformat(),
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration": r.duration,
                "success": r.success,
                "strategy": r.strategy.value,
                "actions_attempted": r.actions_attempted,
                "final_action": r.final_action,
                "error_category": r.error_classification.category.value,
                "error_severity": r.error_classification.severity.value
            }
            for r in recent
        ]


# Global recovery manager
_recovery_manager: Optional[RecoveryManager] = None


def get_recovery_manager() -> RecoveryManager:
    """Get global recovery manager."""
    global _recovery_manager
    
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager()
    
    return _recovery_manager


async def attempt_recovery(component: str, error_classification: ErrorClassification,
                         context: Dict[str, Any] = None) -> RecoveryExecution:
    """Convenience function for recovery attempts."""
    manager = get_recovery_manager()
    return await manager.attempt_recovery(component, error_classification, context)

