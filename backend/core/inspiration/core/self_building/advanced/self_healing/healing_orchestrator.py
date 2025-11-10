"""
Self-Healing Orchestrator - Coordinates automatic healing of failed components.
Detects failures, analyzes patterns, and applies fixes automatically.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.core.config.settings import get_settings
from app.llm.router import get_llm_client
from app.core.error_handler import safe_execute

from ...registry.dynamic_registry import dynamic_registry, ComponentStatus
from ...intelligence.audit_logger import audit_logger, AuditEventType

logger = logging.getLogger(__name__)
settings = get_settings()


class FailureType(Enum):
    """Types of component failures."""
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT_ERROR = "timeout_error"
    DEPENDENCY_ERROR = "dependency_error"
    RESOURCE_ERROR = "resource_error"
    LOGIC_ERROR = "logic_error"


class HealingStrategy(Enum):
    """Strategies for healing components."""
    ROLLBACK = "rollback"
    PATCH = "patch"
    REGENERATE = "regenerate"
    DISABLE = "disable"
    DEPENDENCY_FIX = "dependency_fix"


@dataclass
class FailureRecord:
    """Record of a component failure."""
    component_name: str
    failure_type: FailureType
    error_message: str
    stack_trace: Optional[str]
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    user_request: Optional[str] = None
    healing_attempts: List[str] = field(default_factory=list)
    resolved: bool = False


@dataclass
class HealingAction:
    """Action taken to heal a component."""
    component_name: str
    strategy: HealingStrategy
    description: str
    timestamp: datetime
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailurePattern:
    """Pattern detected in component failures."""
    pattern_id: str
    failure_type: FailureType
    common_errors: List[str]
    affected_components: Set[str]
    frequency: int
    suggested_fix: str
    confidence: float
    first_seen: datetime
    last_seen: datetime


class SelfHealingOrchestrator:
    """
    Orchestrates automatic healing of failed components.
    Detects patterns, applies fixes, and learns from results.
    """
    
    def __init__(self):
        self.llm_client = None
        self.failure_records: List[FailureRecord] = []
        self.healing_actions: List[HealingAction] = []
        self.failure_patterns: Dict[str, FailurePattern] = {}
        
        # Healing configuration - load from settings
        self.config = {
            "max_healing_attempts": settings.max_healing_attempts,
            "healing_timeout": settings.healing_timeout,
            "pattern_detection_threshold": 3,
            "auto_healing_enabled": settings.auto_healing_enabled,
            "rollback_enabled": settings.healing_rollback_enabled,
            "regeneration_enabled": settings.healing_regeneration_enabled
        }
        
        # Component backups for rollback
        self.component_backups: Dict[str, List[Dict[str, Any]]] = {}
        
        # Statistics
        self.stats = {
            "total_failures": 0,
            "total_healing_attempts": 0,
            "successful_healings": 0,
            "patterns_detected": 0,
            "auto_fixes_applied": 0
        }
    
    async def initialize(self):
        """Initialize the self-healing system."""

        try:
            self.llm_client = get_llm_client()

            # Set up failure monitoring
            await self._setup_failure_monitoring()

            # Load existing patterns
            await self._load_failure_patterns()

            logger.info("Self-healing orchestrator initialized")

        except Exception as e:
            logger.error(f"Failed to initialize self-healing orchestrator: {e}")
            raise
    
    async def _setup_failure_monitoring(self):
        """Set up monitoring for component failures."""
        
        # Register with dynamic registry for failure notifications
        dynamic_registry.add_activation_hook("*", self._on_component_activation_failed)
        
        # Set up periodic health checks
        asyncio.create_task(self._periodic_health_check())
    
    async def _on_component_activation_failed(self, component_name: str, success: bool):
        """Handle component activation failures."""
        
        if not success:
            await self.handle_component_failure(
                component_name,
                FailureType.DEPENDENCY_ERROR,
                "Component activation failed",
                context={"trigger": "activation"}
            )
    
    async def handle_component_failure(
        self,
        component_name: str,
        failure_type: FailureType,
        error_message: str,
        stack_trace: Optional[str] = None,
        context: Dict[str, Any] = None,
        user_request: Optional[str] = None
    ) -> bool:
        """
        Handle a component failure and attempt healing.
        
        Args:
            component_name: Name of failed component
            failure_type: Type of failure
            error_message: Error message
            stack_trace: Optional stack trace
            context: Additional context
            user_request: Original user request if applicable
            
        Returns:
            True if healing was successful, False otherwise
        """
        
        if context is None:
            context = {}
        
        try:
            logger.warning(f"Component failure detected: {component_name} - {error_message}")
            
            # Record the failure
            failure_record = FailureRecord(
                component_name=component_name,
                failure_type=failure_type,
                error_message=error_message,
                stack_trace=stack_trace,
                timestamp=datetime.now(),
                context=context,
                user_request=user_request
            )
            
            self.failure_records.append(failure_record)
            self.stats["total_failures"] += 1
            
            # Log to audit system
            await audit_logger.log_error(
                f"Component failure: {error_message}",
                component_name=component_name,
                details={
                    "failure_type": failure_type.value,
                    "stack_trace": stack_trace,
                    "context": context
                }
            )
            
            # Check if auto-healing is enabled
            if not self.config["auto_healing_enabled"]:
                logger.info("Auto-healing disabled, skipping healing attempt")
                return False
            
            # Check healing attempt limit
            if len(failure_record.healing_attempts) >= self.config["max_healing_attempts"]:
                logger.warning(f"Max healing attempts reached for {component_name}")
                return False
            
            # Attempt healing
            healing_success = await self._attempt_healing(failure_record)
            
            if healing_success:
                failure_record.resolved = True
                self.stats["successful_healings"] += 1
                logger.info(f"Successfully healed component: {component_name}")
            else:
                logger.error(f"Failed to heal component: {component_name}")
            
            # Update failure patterns
            await self._update_failure_patterns(failure_record)
            
            return healing_success
            
        except Exception as e:
            logger.error(f"Error handling component failure: {e}")
            return False
    
    async def _attempt_healing(self, failure_record: FailureRecord) -> bool:
        """Attempt to heal a failed component."""
        
        component_name = failure_record.component_name
        failure_type = failure_record.failure_type
        
        try:
            # Determine healing strategy
            strategy = await self._determine_healing_strategy(failure_record)
            
            logger.info(f"Attempting healing with strategy: {strategy.value} for {component_name}")
            
            # Record healing attempt
            failure_record.healing_attempts.append(strategy.value)
            self.stats["total_healing_attempts"] += 1
            
            # Apply healing strategy
            success = False
            
            if strategy == HealingStrategy.ROLLBACK:
                success = await self._rollback_component(failure_record)
            elif strategy == HealingStrategy.PATCH:
                success = await self._patch_component(failure_record)
            elif strategy == HealingStrategy.REGENERATE:
                success = await self._regenerate_component(failure_record)
            elif strategy == HealingStrategy.DEPENDENCY_FIX:
                success = await self._fix_dependencies(failure_record)
            elif strategy == HealingStrategy.DISABLE:
                success = await self._disable_component(failure_record)
            
            # Record healing action
            healing_action = HealingAction(
                component_name=component_name,
                strategy=strategy,
                description=f"Healing attempt for {failure_type.value}",
                timestamp=datetime.now(),
                success=success
            )
            
            self.healing_actions.append(healing_action)
            
            if success:
                self.stats["auto_fixes_applied"] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Error during healing attempt: {e}")
            return False
    
    async def _determine_healing_strategy(self, failure_record: FailureRecord) -> HealingStrategy:
        """Determine the best healing strategy for a failure."""
        
        failure_type = failure_record.failure_type
        component_name = failure_record.component_name
        
        # Check if we have a backup for rollback
        has_backup = component_name in self.component_backups and self.component_backups[component_name]
        
        # Strategy selection logic
        if failure_type == FailureType.SYNTAX_ERROR:
            if has_backup and self.config["rollback_enabled"]:
                return HealingStrategy.ROLLBACK
            else:
                return HealingStrategy.PATCH
        
        elif failure_type == FailureType.IMPORT_ERROR:
            return HealingStrategy.DEPENDENCY_FIX
        
        elif failure_type == FailureType.RUNTIME_ERROR:
            # Check if this is a known pattern
            pattern = await self._find_matching_pattern(failure_record)
            if pattern and pattern.confidence > 0.8:
                return HealingStrategy.PATCH
            elif has_backup:
                return HealingStrategy.ROLLBACK
            else:
                return HealingStrategy.REGENERATE
        
        elif failure_type == FailureType.DEPENDENCY_ERROR:
            return HealingStrategy.DEPENDENCY_FIX
        
        elif failure_type == FailureType.TIMEOUT_ERROR:
            return HealingStrategy.PATCH  # Optimize performance
        
        else:
            # Default strategy
            if has_backup:
                return HealingStrategy.ROLLBACK
            else:
                return HealingStrategy.REGENERATE
    
    async def _rollback_component(self, failure_record: FailureRecord) -> bool:
        """Rollback component to previous working version."""
        
        component_name = failure_record.component_name
        
        try:
            if component_name not in self.component_backups:
                logger.warning(f"No backup found for component: {component_name}")
                return False
            
            backups = self.component_backups[component_name]
            if not backups:
                logger.warning(f"No backup versions available for: {component_name}")
                return False
            
            # Get the most recent backup
            latest_backup = backups[-1]
            
            # Restore the component
            component_path = latest_backup["path"]
            backup_content = latest_backup["content"]
            
            # Write backup content to file
            with open(component_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            
            # Reload the component
            from ...hot_reload.reload_manager import hot_reload_manager
            success = await hot_reload_manager.manual_reload(component_name)
            
            if success:
                logger.info(f"Successfully rolled back component: {component_name}")
                return True
            else:
                logger.error(f"Failed to reload rolled back component: {component_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return False
    
    async def _patch_component(self, failure_record: FailureRecord) -> bool:
        """Patch component code to fix the error."""
        
        component_name = failure_record.component_name
        
        try:
            # Get component info
            component = dynamic_registry.get_component(component_name)
            if not component:
                logger.error(f"Component not found: {component_name}")
                return False
            
            # Read current code
            with open(component.component.path, 'r', encoding='utf-8') as f:
                current_code = f.read()
            
            # Generate patch using LLM
            patch_prompt = self._create_patch_prompt(failure_record, current_code)
            
            patched_code = await safe_execute(
                self.llm_client.generate,
                patch_prompt,
                max_tokens=2000,
                temperature=0.1
            )
            
            if not patched_code:
                logger.error("Failed to generate patch")
                return False
            
            # Extract code from response
            patched_code = self._extract_code_from_response(patched_code)
            
            if not patched_code:
                logger.error("No valid code in patch response")
                return False
            
            # Validate patched code
            if not await self._validate_patched_code(patched_code, failure_record):
                logger.error("Patched code failed validation")
                return False
            
            # Backup current version before patching
            await self._backup_component(component_name, current_code, component.component.path)
            
            # Apply patch
            with open(component.component.path, 'w', encoding='utf-8') as f:
                f.write(patched_code)
            
            # Reload component
            from ...hot_reload.reload_manager import hot_reload_manager
            success = await hot_reload_manager.manual_reload(component_name)
            
            if success:
                logger.info(f"Successfully patched component: {component_name}")
                return True
            else:
                logger.error(f"Failed to reload patched component: {component_name}")
                # Rollback on failure
                await self._rollback_component(failure_record)
                return False
                
        except Exception as e:
            logger.error(f"Error during patching: {e}")
            return False
    
    def _create_patch_prompt(self, failure_record: FailureRecord, current_code: str) -> str:
        """Create a prompt for LLM to generate a patch."""
        
        return f"""
You are an expert Python developer fixing a bug in a HappyOS component.

COMPONENT: {failure_record.component_name}
FAILURE TYPE: {failure_record.failure_type.value}
ERROR MESSAGE: {failure_record.error_message}

CURRENT CODE:
```python
{current_code}
```

STACK TRACE:
{failure_record.stack_trace or 'Not available'}

CONTEXT:
{failure_record.context}

Please fix the bug in the code. Requirements:
1. Fix the specific error mentioned
2. Maintain all existing functionality
3. Keep the same function signatures
4. Add proper error handling
5. Include comments explaining the fix

Return ONLY the corrected Python code, no explanations.
"""
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        
        import re
        
        # Try to find code in triple backticks
        code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Try to find code in single backticks
        code_match = re.search(r'```\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # If no code blocks, assume entire response is code
        if 'def ' in response and 'import' in response:
            return response.strip()
        
        return None
    
    async def _validate_patched_code(self, patched_code: str, failure_record: FailureRecord) -> bool:
        """Validate that patched code is syntactically correct."""
        
        try:
            # Basic syntax check
            compile(patched_code, '<string>', 'exec')
            
            # Check that it still has required functions
            # This is a basic check - could be more sophisticated
            if failure_record.failure_type == FailureType.SYNTAX_ERROR:
                # For syntax errors, just check compilation
                return True
            
            # Additional validation could be added here
            return True
            
        except SyntaxError as e:
            logger.error(f"Patched code has syntax error: {e}")
            return False
        except Exception as e:
            logger.error(f"Patched code validation failed: {e}")
            return False
    
    async def _regenerate_component(self, failure_record: FailureRecord) -> bool:
        """Regenerate the component from scratch."""
        
        try:
            if not failure_record.user_request:
                logger.warning("Cannot regenerate without original user request")
                return False
            
            # Use the skill auto-generator to create a new version
            from ...generators.skill_auto_generator import auto_generate_skill
            
            new_component = await auto_generate_skill(
                failure_record.user_request,
                context=failure_record.context
            )
            
            if new_component:
                logger.info(f"Successfully regenerated component: {failure_record.component_name}")
                return True
            else:
                logger.error(f"Failed to regenerate component: {failure_record.component_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error during regeneration: {e}")
            return False
    
    async def _fix_dependencies(self, failure_record: FailureRecord) -> bool:
        """Fix dependency issues."""
        
        try:
            # This is a simplified implementation
            # In a real system, this would analyze import errors and try to fix them
            
            component_name = failure_record.component_name
            error_message = failure_record.error_message
            
            # Check if it's a missing import
            if "No module named" in error_message:
                # Extract module name
                import re
                match = re.search(r"No module named '([^']+)'", error_message)
                if match:
                    missing_module = match.group(1)
                    logger.info(f"Attempting to install missing module: {missing_module}")
                    
                    # Try to install the module (simplified)
                    # In production, this would be more sophisticated
                    return False  # For now, return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error fixing dependencies: {e}")
            return False
    
    async def _disable_component(self, failure_record: FailureRecord) -> bool:
        """Disable a problematic component."""
        
        try:
            component_name = failure_record.component_name
            
            # Deactivate the component
            success = await dynamic_registry.deactivate_component(component_name)
            
            if success:
                logger.info(f"Disabled problematic component: {component_name}")
                return True
            else:
                logger.error(f"Failed to disable component: {component_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error disabling component: {e}")
            return False
    
    async def _backup_component(self, component_name: str, content: str, path: str):
        """Backup a component before making changes."""
        
        try:
            if component_name not in self.component_backups:
                self.component_backups[component_name] = []
            
            backup = {
                "content": content,
                "path": path,
                "timestamp": datetime.now(),
                "version": len(self.component_backups[component_name]) + 1
            }
            
            self.component_backups[component_name].append(backup)
            
            # Keep only last 5 backups
            if len(self.component_backups[component_name]) > 5:
                self.component_backups[component_name] = self.component_backups[component_name][-5:]
            
            logger.debug(f"Backed up component: {component_name}")
            
        except Exception as e:
            logger.error(f"Error backing up component: {e}")
    
    async def _update_failure_patterns(self, failure_record: FailureRecord):
        """Update failure patterns based on new failure."""
        
        try:
            # Simple pattern detection based on error message similarity
            pattern_key = f"{failure_record.failure_type.value}_{hash(failure_record.error_message) % 1000}"
            
            if pattern_key in self.failure_patterns:
                # Update existing pattern
                pattern = self.failure_patterns[pattern_key]
                pattern.frequency += 1
                pattern.affected_components.add(failure_record.component_name)
                pattern.last_seen = failure_record.timestamp
                
                if failure_record.error_message not in pattern.common_errors:
                    pattern.common_errors.append(failure_record.error_message)
                
            else:
                # Create new pattern
                pattern = FailurePattern(
                    pattern_id=pattern_key,
                    failure_type=failure_record.failure_type,
                    common_errors=[failure_record.error_message],
                    affected_components={failure_record.component_name},
                    frequency=1,
                    suggested_fix="",  # Would be generated by LLM
                    confidence=0.5,
                    first_seen=failure_record.timestamp,
                    last_seen=failure_record.timestamp
                )
                
                self.failure_patterns[pattern_key] = pattern
                self.stats["patterns_detected"] += 1
            
            # Generate suggested fix if pattern is frequent enough
            pattern = self.failure_patterns[pattern_key]
            if (pattern.frequency >= self.config["pattern_detection_threshold"] and 
                not pattern.suggested_fix):
                
                pattern.suggested_fix = await self._generate_pattern_fix(pattern)
                pattern.confidence = min(pattern.frequency / 10.0, 1.0)
            
        except Exception as e:
            logger.error(f"Error updating failure patterns: {e}")
    
    async def _generate_pattern_fix(self, pattern: FailurePattern) -> str:
        """Generate a suggested fix for a failure pattern."""
        
        try:
            prompt = f"""
Analyze this failure pattern and suggest a fix:

FAILURE TYPE: {pattern.failure_type.value}
FREQUENCY: {pattern.frequency}
AFFECTED COMPONENTS: {list(pattern.affected_components)}
COMMON ERRORS: {pattern.common_errors}

Provide a concise fix suggestion that could prevent this type of failure.
"""
            
            suggestion = await safe_execute(
                self.llm_client.generate,
                prompt,
                max_tokens=200,
                temperature=0.3
            )
            
            return suggestion or "No suggestion available"
            
        except Exception as e:
            logger.error(f"Error generating pattern fix: {e}")
            return "Error generating suggestion"
    
    async def _find_matching_pattern(self, failure_record: FailureRecord) -> Optional[FailurePattern]:
        """Find a matching failure pattern for a failure record."""
        
        for pattern in self.failure_patterns.values():
            if (pattern.failure_type == failure_record.failure_type and
                any(error in failure_record.error_message for error in pattern.common_errors)):
                return pattern
        
        return None
    
    async def _periodic_health_check(self):
        """Perform periodic health checks on components."""
        
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Get all active components
                active_components = dynamic_registry.list_components(status=ComponentStatus.ACTIVE)
                
                for entry in active_components:
                    # Basic health check - could be more sophisticated
                    component_name = entry.component.name
                    
                    # Check if component has been failing frequently
                    recent_failures = [
                        f for f in self.failure_records
                        if (f.component_name == component_name and
                            f.timestamp > datetime.now() - timedelta(hours=1))
                    ]
                    
                    if len(recent_failures) > 3:
                        logger.warning(f"Component {component_name} has {len(recent_failures)} recent failures")
                        
                        # Consider disabling if too many failures
                        if len(recent_failures) > 5:
                            await self._disable_component(recent_failures[-1])
                
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
    
    async def _load_failure_patterns(self):
        """Load existing failure patterns from storage."""
        # This would load patterns from a persistent store
        # For now, we start with empty patterns
        pass
    
    def get_healing_stats(self) -> Dict[str, Any]:
        """Get healing statistics."""
        
        recent_failures = [
            f for f in self.failure_records
            if f.timestamp > datetime.now() - timedelta(hours=24)
        ]
        
        return {
            **self.stats,
            "recent_failures_24h": len(recent_failures),
            "healing_success_rate": (
                self.stats["successful_healings"] / max(self.stats["total_healing_attempts"], 1)
            ),
            "active_patterns": len(self.failure_patterns),
            "components_with_backups": len(self.component_backups),
            "recent_healing_actions": [
                {
                    "component": action.component_name,
                    "strategy": action.strategy.value,
                    "success": action.success,
                    "timestamp": action.timestamp.isoformat()
                }
                for action in self.healing_actions[-10:]
            ]
        }


# Global healing orchestrator instance
healing_orchestrator = SelfHealingOrchestrator()


# Convenience functions
async def handle_component_failure(
    component_name: str,
    failure_type: FailureType,
    error_message: str,
    **kwargs
) -> bool:
    """Handle a component failure."""
    return await healing_orchestrator.handle_component_failure(
        component_name, failure_type, error_message, **kwargs
    )


def get_healing_stats() -> Dict[str, Any]:
    """Get healing statistics."""
    return healing_orchestrator.get_healing_stats()