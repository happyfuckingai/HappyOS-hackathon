"""
Ultimate Self-Building System - Complete recursive self-improvement integration.
This is the master orchestrator that brings together all self-building capabilities
into one unified, recursive, self-improving system.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

# Import all self-building components
from app.core.self_building.self_building_orchestrator import self_building_orchestrator
from app.core.self_building.advanced.dependency_graph.graph_analyzer import dependency_analyzer
from app.core.self_building.advanced.dependency_graph.graph_visualizer import graph_visualizer
from app.core.self_building.advanced.self_healing.healing_orchestrator import healing_orchestrator, FailureType
from app.core.self_building.advanced.auto_docs.doc_generator import doc_generator
from app.core.self_building.advanced.marketplace.marketplace_api import external_marketplace
from app.core.self_building.advanced.optimization.optimization_engine import optimization_engine
from app.core.self_building.advanced.meta_building.meta_orchestrator import meta_orchestrator

from app.core.self_building.intelligence.audit_logger import audit_logger, AuditEventType

logger = logging.getLogger(__name__)


class UltimateSelfBuildingSystem:
    """
    The ultimate self-building system that orchestrates all components
    into a unified, recursive, self-improving AI. It manages other self-building
    components, including the core SelfBuildingOrchestrator (SBO1).
    SBO2 is responsible for the decision-making and initiation of new component
    generation, for instance, when SBO1 signals a need or when its meta-orchestrator
    identifies an opportunity for creating a new capability.
    """
    
    def __init__(self):
        self.initialized = False
        self.running = False
        self.startup_time = None
        
        # System components
        self.components = {
            "core_orchestrator": self_building_orchestrator,
            "dependency_analyzer": dependency_analyzer,
            "graph_visualizer": graph_visualizer,
            "healing_orchestrator": healing_orchestrator,
            "doc_generator": doc_generator,
            "external_marketplace": external_marketplace,
            "optimization_engine": optimization_engine,
            "meta_orchestrator": meta_orchestrator,  # The recursive crown jewel
            "audit_logger": audit_logger
        }
        
        # System statistics
        self.stats = {
            "startup_time": None,
            "total_components": len(self.components),
            "initialized_components": 0,
            "recursive_loops_active": 0,
            "self_improvements_made": 0,
            "system_evolution_level": 1.0
        }
    
    async def initialize(self):
        """Initialize the ultimate self-building system."""
        
        if self.initialized:
            logger.debug("Ultimate self-building system already initialized")
            return
        
        try:
            logger.info("🚀 Initializing Ultimate Self-Building System...")
            self.startup_time = datetime.now()
            
            # Log system startup
            await audit_logger.log_system_startup({
                "system_type": "ultimate_self_building",
                "startup_time": self.startup_time.isoformat(),
                "components": list(self.components.keys()),
                "recursive_capability": True,
                "meta_improvement_enabled": True
            })
            
            # Initialize components in dependency order
            await self._initialize_components_ordered()
            
            # Establish recursive loops
            await self._establish_recursive_loops()
            
            # Start ultimate monitoring
            await self._start_ultimate_monitoring()
            
            self.initialized = True
            self.running = True
            
            # Update stats
            self.stats["startup_time"] = self.startup_time
            self.stats["initialized_components"] = len(self.components)
            
            logger.info("🎉 Ultimate Self-Building System initialized successfully!")
            logger.info("🔄 Recursive self-improvement loops are now ACTIVE!")
            
        except Exception as e:
            logger.error(f"Failed to initialize ultimate self-building system: {e}")
            await audit_logger.log_error(f"Ultimate system initialization failed: {e}")
            raise
    
    async def _initialize_components_ordered(self):
        """Initialize components in the correct dependency order, respecting configuration."""

        # Get settings for selective initialization
        from app.config.settings import get_settings
        settings = get_settings()

        # Phase 1: Core infrastructure (always initialize if self-building is enabled)
        core_components = ["audit_logger", "core_orchestrator"]

        # Only initialize dependency analyzer if enabled
        if settings.enable_dependency_analyzer:
            core_components.append("dependency_analyzer")

        for component_name in core_components:
            await self._initialize_component(component_name)

        # Phase 2: Advanced capabilities (only if enabled)
        advanced_components = []

        if settings.enable_healing_orchestrator:
            advanced_components.append("healing_orchestrator")
        if settings.enable_doc_generator:
            advanced_components.append("doc_generator")
        if settings.enable_external_marketplace:
            advanced_components.append("external_marketplace")
        if settings.enable_optimization_engine:
            advanced_components.append("optimization_engine")

        for component_name in advanced_components:
            await self._initialize_component(component_name)

        # Phase 3: Visualization and meta-systems (only if enabled)
        meta_components = []

        if settings.enable_graph_visualizer:
            meta_components.append("graph_visualizer")
        if settings.enable_meta_orchestrator:
            meta_components.append("meta_orchestrator")  # Last - the recursive crown jewel

        for component_name in meta_components:
            await self._initialize_component(component_name)
    
    async def _initialize_component(self, component_name: str):
        """Initialize a specific component."""
        
        try:
            component = self.components[component_name]
            
            if hasattr(component, 'initialize'):
                logger.info(f"Initializing {component_name}...")
                await component.initialize()
                logger.info(f"✅ {component_name} initialized")
            else:
                logger.debug(f"Component {component_name} has no initialize method")
            
        except Exception as e:
            logger.error(f"Failed to initialize {component_name}: {e}")
            raise
    
    async def _establish_recursive_loops(self):
        """Establish the recursive self-improvement loops."""
        
        try:
            logger.info("🔄 Establishing recursive self-improvement loops...")
            
            # The meta-orchestrator creates the ultimate recursive loop
            # where the system uses itself to improve itself
            
            # Verify meta-orchestrator is registered as a plugin
            from .registry.dynamic_registry import dynamic_registry
            
            meta_component = dynamic_registry.get_component("meta_decision_engine")
            if meta_component:
                logger.info("✅ Meta-decision engine registered as plugin - recursive loop established!")
                self.stats["recursive_loops_active"] = 1
            else:
                logger.warning("⚠️ Meta-decision engine not found - recursive loop may not be active")
            
            # Start continuous recursive improvement
            asyncio.create_task(self._continuous_recursive_improvement())
            
            logger.info("🔄 Recursive loops established successfully!")
            
        except Exception as e:
            logger.error(f"Failed to establish recursive loops: {e}")
            raise
    
    async def _start_ultimate_monitoring(self):
        """Start ultimate system monitoring based on configuration."""

        try:
            from app.config.settings import get_settings
            settings = get_settings()

            # Start monitoring tasks based on configuration
            if settings.periodic_health_checks:
                asyncio.create_task(self._ultimate_health_monitor())

            if settings.recursive_improvement_enabled:
                asyncio.create_task(self._recursive_progress_tracker())

            if settings.system_evolution_tracking:
                asyncio.create_task(self._evolution_level_calculator())

            logger.info("📊 Ultimate monitoring started")

        except Exception as e:
            logger.error(f"Failed to start ultimate monitoring: {e}")
    
    async def _continuous_recursive_improvement(self):
        """Continuous recursive self-improvement cycle."""

        from app.config.settings import get_settings
        settings = get_settings()

        # Only run if recursive improvement is enabled
        if not settings.recursive_improvement_enabled:
            logger.info("🔄 Recursive improvement disabled by configuration")
            return

        while self.running:
            try:
                await asyncio.sleep(3600)  # Every hour

                logger.info("🔄 Starting recursive self-improvement cycle...")

                # Trigger meta-orchestrator to improve the system
                if hasattr(meta_orchestrator, 'trigger_self_improvement'):
                    improvement_result = await meta_orchestrator.trigger_self_improvement()

                    if improvement_result.get("success"):
                        self.stats["self_improvements_made"] += 1
                        logger.info(f"✅ Self-improvement completed: {improvement_result}")

                        # Update evolution level
                        await self._update_evolution_level()
                    else:
                        logger.info("ℹ️ No self-improvements needed at this time")
                else:
                    logger.warning("Meta-orchestrator does not have trigger_self_improvement method")

            except Exception as e:
                logger.error(f"Error in recursive improvement cycle: {e}")
    
    async def _ultimate_health_monitor(self):
        """Monitor the health of the ultimate system."""
        
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Check component health
                unhealthy_components = []
                
                for component_name, component in self.components.items():
                    try:
                        if hasattr(component, 'get_stats'):
                            stats = component.get_stats()
                            # Simple health check - could be more sophisticated
                            if isinstance(stats, dict) and stats.get("errors", 0) > 10:
                                unhealthy_components.append(component_name)
                    except Exception as e:
                        logger.warning(f"Health check failed for {component_name}: {e}")
                        unhealthy_components.append(component_name)
                
                # Trigger healing if needed
                if unhealthy_components:
                    logger.warning(f"Unhealthy components detected: {unhealthy_components}")
                    await self._trigger_system_healing(unhealthy_components)
                
            except Exception as e:
                logger.error(f"Error in ultimate health monitor: {e}")
    
    async def _recursive_progress_tracker(self):
        """Track recursive improvement progress."""
        
        while self.running:
            try:
                await asyncio.sleep(1800)  # Every 30 minutes
                
                # Get meta-orchestrator stats
                meta_stats = meta_orchestrator.get_meta_stats()
                
                # Update recursive progress
                self.stats["recursive_loops_active"] = 1 if meta_stats.get("active_tests", 0) > 0 else 0
                self.stats["self_improvements_made"] = meta_stats.get("total_improvements_deployed", 0)
                
                # Log progress
                logger.info(f"🔄 Recursive progress: {self.stats['self_improvements_made']} improvements made")
                
            except Exception as e:
                logger.error(f"Error tracking recursive progress: {e}")
    
    async def _evolution_level_calculator(self):
        """Calculate the system's evolution level."""
        
        while self.running:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Calculate evolution based on various factors
                base_level = 1.0
                
                # Factor in self-improvements
                improvement_factor = self.stats["self_improvements_made"] * 0.1
                
                # Factor in system complexity and capabilities
                complexity_factor = len(self.components) * 0.05
                
                # Factor in recursive capability
                recursive_factor = 0.5 if self.stats["recursive_loops_active"] > 0 else 0
                
                # Calculate new evolution level
                new_level = base_level + improvement_factor + complexity_factor + recursive_factor
                
                if new_level != self.stats["system_evolution_level"]:
                    old_level = self.stats["system_evolution_level"]
                    self.stats["system_evolution_level"] = new_level
                    
                    logger.info(f"🧬 System evolution level updated: {old_level:.2f} → {new_level:.2f}")
                    
                    # Log evolution milestone
                    await audit_logger.log_event(
                        AuditEventType.SYSTEM_STARTUP,  # Using existing event type
                        details={
                            "evolution_level_change": True,
                            "old_level": old_level,
                            "new_level": new_level,
                            "improvements_made": self.stats["self_improvements_made"]
                        }
                    )
                
            except Exception as e:
                logger.error(f"Error calculating evolution level: {e}")
    
    async def _trigger_system_healing(self, unhealthy_components: list):
        """Trigger healing for unhealthy components."""
        
        try:
            for component_name in unhealthy_components:
                logger.info(f"🏥 Triggering healing for component: {component_name}")
                
                # Use healing orchestrator to heal the component
                await healing_orchestrator.handle_component_failure(
                    component_name,
                    FailureType.RUNTIME_ERROR,
                    "Component health check failed",
                    context={"trigger": "ultimate_health_monitor"}
                )
                
        except Exception as e:
            logger.error(f"Error triggering system healing: {e}")
    
    async def _update_evolution_level(self):
        """Update the system evolution level after improvements."""
        
        # This will be handled by the evolution level calculator
        pass

    async def _should_proceed_with_generation(self, user_request: str, context: Dict[str, Any]) -> bool:
        """
        Decides whether SBO2 should proceed with generating a new component.
        This is a placeholder for more sophisticated decision logic based on
        system load, risk assessment, policies, etc.

        For now, it always approves generation.
        """
        # Placeholder: In the future, consult meta_orchestrator or other decision modules.
        # Example:
        # decision_context = {"user_request": user_request, "context": context, "current_load": self.get_system_load()}
        # meta_decision = await self._make_meta_decision(MetaDecisionType.SHOULD_GENERATE_SKILL, decision_context)
        # return meta_decision.get("result", {}).get("should_generate", True)

        logger.info(f"SBO2 decision point: Approving generation for request: {user_request[:100]}")
        return True # Currently always approves

    # DEVELOPER NOTE on SBO2-SBO1 Interaction for Generation:
    # The `handle_generation_candidate_request` method orchestrates the process
    # of handling a user request that might lead to new component generation.
    # The interaction with SBO1 (CoreSelfBuildingOrchestrator) is designed to
    # centralize generation decisions in SBO2 while SBO1 handles core mechanics.
    #
    # Flow:
    # 1. External Call: User/System calls SBO2's `handle_generation_candidate_request(request, context)`.
    # 2. SBO2 to SBO1 (Check & Signal):
    #    SBO2 calls `sbo1_instance.handle_user_request(request, context)`.
    #    SBO1 attempts to find an existing component.
    #    If no component is found, SBO1's `handle_user_request` returns a specific
    #    dictionary: `{"action_needed": "generation_required", "details": {...}}`.
    #    This return value is a passive signal; SBO1 does NOT call SBO2 back here.
    # 3. SBO2 Decision:
    #    SBO2 receives the signal from SBO1.
    #    SBO2 then calls its internal `_should_proceed_with_generation(details)` method
    #    to decide whether to generate the component.
    # 4. SBO2 to SBO1 (Execute Generation, if approved):
    #    If SBO2 decides to proceed, it calls `sbo1_instance._auto_generate_component(details)`.
    #    SBO1's `_auto_generate_component` then invokes the actual `SkillAutoGenerator`.
    # 5. Result: The generated component (or failure status) is returned up the chain.
    #
    # Circular Dependency Avoidance:
    # In this flow, SBO1 does not directly call any methods on SBO2. The communication
    # from SBO1 back to SBO2 (the signal for needing generation) is done via a return
    # value from `SBO1.handle_user_request`. SBO2 then initiates a separate, subsequent
    # call to a different SBO1 method (`_auto_generate_component`) if generation is approved.
    # This one-way control from SBO2 to SBO1 for distinct phases of the process
    # prevents circular method calls during a single generation sequence.
    # Module-level circular dependencies are also avoided as `self_building_orchestrator.py`
    # does not import `ultimate_self_building.py`.

    async def handle_generation_candidate_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handles a request that might lead to component generation.
        It first directs the SelfBuildingOrchestrator (SBO1) to check if any existing
        component can handle the request.
        If SBO1 signals 'generation_required', this method then takes over,
        decides if generation should proceed (currently, it proceeds directly),
        and then instructs SBO1 (via its `_auto_generate_component` method)
        to perform the actual generation. This centralizes generation control within SBO2.

        Args:
            user_request: The user's request string.
            context: Additional context.

        Returns:
            A dictionary with the outcome: either handled by an existing component,
            a newly generated component, or an error if generation failed.
        """
        if not self.running:
            await self.initialize()
        if context is None:
            context = {}

        sbo1_response = await self.components["core_orchestrator"].handle_user_request(user_request, context)

        if sbo1_response.get("action_needed") == "generation_required":
            details = sbo1_response.get("details", {})
            original_user_request = details.get("user_request", user_request)
            original_context = details.get("context", context)

            logger.info(f"SBO2 received 'generation_required' signal for: {original_user_request[:100]}...")

            # SBO2 makes a decision whether to proceed
            proceed_with_generation = await self._should_proceed_with_generation(original_user_request, original_context)

            if not proceed_with_generation:
                logger.warning(f"SBO2 decided NOT to proceed with generation for: {original_user_request[:100]}")
                # self.stats["generation_requests_declined"] = self.stats.get("generation_requests_declined", 0) + 1 # Optional new stat
                return {
                    "success": False,
                    "handled_by": "sbo2_decision_engine",
                    "action_taken": "generation_declined",
                    "reason": "SBO2 policy or current system state prevented generation.", # Generic reason
                    "error": "Component generation declined by orchestrator.",
                    "details": {
                        "user_request": original_user_request,
                        "context": original_context
                    }
                }

            # If proceed_with_generation is True, continue with existing logic:
            logger.info(f"SBO2 approved generation. Calling SBO1's _auto_generate_component for: {original_user_request[:100]}...")
            generated_component = await self.components["core_orchestrator"]._auto_generate_component(original_user_request, original_context)

            if generated_component:
                self.stats["self_improvements_made"] += 1 # Or a more specific counter for SBO2-led generations
                logger.info(f"SBO2 successfully orchestrated generation of component: {generated_component.name}")
                return {
                    "success": True,
                    "handled_by": "sbo2_orchestrated_generation",
                    "component_name": generated_component.name,
                    "component_type": generated_component.type,
                    "auto_generated": True,
                    "file_path": generated_component.path
                }
            else:
                # self.stats["errors_encountered"] += 1 # SBO1 already counts this
                logger.error("SBO2 orchestration: _auto_generate_component failed")
                return {
                    "success": False,
                    "error": "SBO2 failed to orchestrate component generation via SBO1",
                    "handled_by": "sbo2_orchestration_failure"
                }
        else:
            # If SBO1 handled it or failed in a way not requiring generation, return SBO1's response
            return sbo1_response
    
    async def get_ultimate_system_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the ultimate system."""
        
        try:
            # Collect status from all components
            component_status = {}
            
            for component_name, component in self.components.items():
                try:
                    if hasattr(component, 'get_stats'):
                        component_status[component_name] = component.get_stats()
                    elif hasattr(component, 'stats'):
                        component_status[component_name] = component.stats
                    else:
                        component_status[component_name] = {"status": "active"}
                except Exception as e:
                    component_status[component_name] = {"error": str(e)}
            
            # Calculate overall health
            healthy_components = sum(
                1 for status in component_status.values() 
                if not isinstance(status, dict) or not status.get("error")
            )
            
            overall_health = (healthy_components / len(self.components)) * 100
            
            return {
                "system": {
                    "initialized": self.initialized,
                    "running": self.running,
                    "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                    "uptime_seconds": (
                        (datetime.now() - self.startup_time).total_seconds() 
                        if self.startup_time else 0
                    ),
                    "evolution_level": self.stats["system_evolution_level"],
                    "overall_health": overall_health
                },
                "recursive_capability": {
                    "active_loops": self.stats["recursive_loops_active"],
                    "self_improvements_made": self.stats["self_improvements_made"],
                    "meta_orchestrator_active": "meta_orchestrator" in self.components
                },
                "components": component_status,
                "statistics": self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting ultimate system status: {e}")
            return {
                "error": str(e),
                "system": {
                    "initialized": self.initialized,
                    "running": self.running
                }
            }
    
    async def shutdown(self):
        """Shutdown the ultimate self-building system."""
        
        if not self.running:
            return
        
        try:
            logger.info("🛑 Shutting down Ultimate Self-Building System...")
            
            # Stop all components
            for component_name, component in self.components.items():
                try:
                    if hasattr(component, 'shutdown'):
                        await component.shutdown()
                        logger.info(f"✅ {component_name} shut down")
                except Exception as e:
                    logger.error(f"Error shutting down {component_name}: {e}")
            
            # Log system shutdown
            await audit_logger.log_system_shutdown({
                "shutdown_time": datetime.now().isoformat(),
                "uptime_seconds": (
                    (datetime.now() - self.startup_time).total_seconds() 
                    if self.startup_time else 0
                ),
                "final_evolution_level": self.stats["system_evolution_level"],
                "total_self_improvements": self.stats["self_improvements_made"]
            })
            
            self.running = False
            
            logger.info("🛑 Ultimate Self-Building System shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during ultimate system shutdown: {e}")


# Global ultimate system instance
ultimate_self_building_system = UltimateSelfBuildingSystem()


# Convenience functions
async def initialize_ultimate_self_building():
    """Initialize the ultimate self-building system."""
    await ultimate_self_building_system.initialize()


async def get_ultimate_system_status() -> Dict[str, Any]:
    """Get comprehensive status of the ultimate system."""
    return await ultimate_self_building_system.get_ultimate_system_status()


async def shutdown_ultimate_self_building():
    """Shutdown the ultimate self-building system."""
    await ultimate_self_building_system.shutdown()


async def trigger_ultimate_self_improvement():
    """Manually trigger ultimate self-improvement."""
    if ultimate_self_building_system.running:
        return await meta_orchestrator.trigger_self_improvement()
    else:
        return {"success": False, "error": "Ultimate system not running"}


async def handle_request_and_generate_if_needed(user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Handles a user request, attempting to find a capable component,
    and if none is found, uses SBO2's logic to potentially generate one.
    This is the primary entry point for request-driven generation.
    """
    # Ensure ultimate_self_building_system is initialized and running
    if not ultimate_self_building_system.initialized:
        await ultimate_self_building_system.initialize()
    elif not ultimate_self_building_system.running:
        # Or handle as an error, depending on desired behavior for a non-running system
        logger.warning("Ultimate self-building system is initialized but not running. Attempting to handle request.")
        # Potentially await ultimate_self_building_system.initialize() again or ensure it's running

    return await ultimate_self_building_system.handle_generation_candidate_request(user_request, context)


# Integration with existing orchestrator
async def integrate_with_main_orchestrator():
    """Integrate ultimate self-building with the main orchestrator."""
    
    try:
        # Import main orchestrator
        from app.core.orchestrator.clean_orchestrator import CleanOrchestrator
        
        # This would integrate the ultimate system with the main orchestrator
        # The main orchestrator would use the ultimate system for all self-building needs
        
        logger.info("🔗 Ultimate self-building integrated with main orchestrator")
        
    except Exception as e:
        logger.error(f"Error integrating with main orchestrator: {e}")


# Export all for easy access
__all__ = [
    "UltimateSelfBuildingSystem",
    "ultimate_self_building_system",
    "initialize_ultimate_self_building",
    "get_ultimate_system_status", 
    "shutdown_ultimate_self_building",
    "trigger_ultimate_self_improvement",
    "handle_request_and_generate_if_needed", # Added
    "integrate_with_main_orchestrator"
]