"""
Self-Building Orchestrator - Main coordinator for the self-building system.
Orchestrates component discovery, auto-generation, registration, and hot reload.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.self_building.discovery.component_scanner import component_scanner, scan_components, load_all_components
from app.core.self_building.registry.dynamic_registry import dynamic_registry, ComponentStatus
from app.core.self_building.generators.skill_auto_generator import skill_auto_generator, auto_generate_skill
from app.core.self_building.hot_reload.reload_manager import hot_reload_manager, start_hot_reload
from app.core.self_building.intelligence.audit_logger import audit_logger, AuditEventType

logger = logging.getLogger(__name__)


class SelfBuildingOrchestrator:
    """
    Core orchestrator for self-building tasks like component discovery, registration,
    loading, and hot-reloading. It identifies when new components (e.g., skills)
    are needed to fulfill a request and signals this to a higher-level orchestrator
    (e.g., UltimateSelfBuildingSystem) which then manages the actual generation process.
    This orchestrator itself does not directly generate new components upon user request anymore.
    """
    
    def __init__(self):
        self.initialized = False
        self.running = False
        self.startup_time = None
        
        # System statistics
        self.stats = {
            "startup_time": None,
            "components_discovered": 0,
            "components_registered": 0,
            "skills_auto_generated": 0,
            "hot_reloads_performed": 0,
            "errors_encountered": 0
        }
    
    async def initialize(self):
        """Initialize the self-building system."""
        
        if self.initialized:
            logger.debug("Self-building orchestrator already initialized")
            return
        
        try:
            logger.info("Initializing self-building orchestrator...")
            self.startup_time = datetime.now()
            
            # Log system startup
            await audit_logger.log_system_startup({
                "startup_time": self.startup_time.isoformat(),
                "components": ["scanner", "registry", "generators", "hot_reload", "audit"]
            })
            
            # Initialize components
            await self._initialize_components()
            
            # Perform initial system scan
            await self._initial_system_scan()
            
            # Start hot reload monitoring
            await start_hot_reload()
            
            self.initialized = True
            self.running = True
            
            logger.info("Self-building orchestrator initialized successfully")
            
            # Update stats
            self.stats["startup_time"] = self.startup_time
            
        except Exception as e:
            logger.error(f"Failed to initialize self-building orchestrator: {e}")
            await audit_logger.log_error(f"Orchestrator initialization failed: {e}")
            raise
    
    async def _initialize_components(self):
        """Initialize all self-building components."""
        
        # Initialize skill auto-generator
        await skill_auto_generator.initialize()
        logger.debug("Skill auto-generator initialized")
        
        # Additional component initializations can be added here
        logger.debug("All self-building components initialized")
    
    async def _initial_system_scan(self):
        """Perform initial scan of the system."""
        
        logger.info("Performing initial system scan...")
        
        try:
            # Scan all components
            discovered_components = await scan_components()
            
            total_discovered = sum(len(comps) for comps in discovered_components.values())
            self.stats["components_discovered"] = total_discovered
            
            logger.info(f"Discovered {total_discovered} components")
            
            # Load all discovered components
            load_results = await load_all_components()
            
            self.stats["components_registered"] = load_results["total_loaded"]
            
            logger.info(f"Loaded {load_results['total_loaded']} components")
            
            # Log discovery results
            for component_type, components in discovered_components.items():
                for component in components:
                    await audit_logger.log_component_discovered(
                        component.name,
                        component.type,
                        component.path
                    )
            
        except Exception as e:
            logger.error(f"Initial system scan failed: {e}")
            await audit_logger.log_error(f"Initial system scan failed: {e}")
            raise
    
    async def handle_user_request(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handles a user request by attempting to find a capable existing component.
        If a suitable component is found, it returns information about it.
        If no capable component is found, it returns a dictionary with
        `action_needed: "generation_required"` along with request details,
        signaling that a higher-level system should consider generating a new component.
        It no longer directly triggers auto-generation.
        
        Args:
            user_request: The user's request string.
            context: Additional context for handling the request.
            
        Returns:
            A dictionary containing either information about the capable component found
            or a signal that component generation is required.
        """
        
        if not self.running:
            await self.initialize()
        
        if context is None:
            context = {}
        
        try:
            logger.info(f"Handling user request: {user_request[:100]}...")
            
            # Step 1: Check if existing components can handle the request
            capable_components = await self._find_capable_components(user_request)
            
            if capable_components:
                logger.info(f"Found {len(capable_components)} capable components")
                
                # Use existing component
                component = capable_components[0]  # Use first capable component
                
                # Activate component if needed
                await dynamic_registry.activate_component(component.name)
                
                return {
                    "success": True,
                    "handled_by": "existing_component",
                    "component_name": component.name,
                    "component_type": component.type,
                    "auto_generated": False
                }
            
            # Step 2: No existing component can handle it - auto-generate
            logger.info("No capable components found, auto-generation recommended.")
            
            return {
                "success": False,
                "error": "No capable component found. Auto-generation recommended.",
                "action_needed": "generation_required",
                "details": {
                    "user_request": user_request,
                    "context": context or {}
                }
            }
                
        except Exception as e:
            logger.error(f"Error handling user request: {e}")
            await audit_logger.log_error(f"Request handling failed: {e}")
            
            self.stats["errors_encountered"] += 1
            
            return {
                "success": False,
                "error": str(e),
                "handled_by": "none"
            }
    
    async def _find_capable_components(
        self, 
        user_request: str
    ) -> List[Any]:
        """Find existing components that can handle the user request."""
        
        # This is a simplified implementation
        # In a real system, this would use more sophisticated matching
        
        capable_components = []
        
        # Get all active components
        active_components = dynamic_registry.list_components(status=ComponentStatus.ACTIVE)
        
        # Simple keyword matching for now
        request_lower = user_request.lower()
        
        for entry in active_components:
            component = entry.component
            
            # Check component metadata for capabilities
            if component.metadata:
                # Check if component type matches request intent
                if component.type == "skills":
                    # Simple heuristic matching
                    if any(keyword in request_lower for keyword in ["scrape", "web"] if "web" in component.name.lower()):
                        capable_components.append(component)
                    elif any(keyword in request_lower for keyword in ["api", "http"] if "api" in component.name.lower()):
                        capable_components.append(component)
                    elif any(keyword in request_lower for keyword in ["file", "data"] if "file" in component.name.lower()):
                        capable_components.append(component)
        
        return capable_components

    async def _auto_generate_component(self, user_request: str, context: Dict[str, Any] = None):
        """
        Triggers the auto-generation of a new skill based on the user request.
        This method is intended to be called by a higher-level orchestrator
        after it has decided to proceed with generation.
        """
        logger.info(f"Auto-generating component for request: {user_request[:100]}...")
        try:
            # Use the imported skill_auto_generator instance
            new_skill_component = await skill_auto_generator.generate_skill_for_need(user_request, context or {})
            
            if new_skill_component:
                self.stats["skills_auto_generated"] += 1
                logger.info(f"Successfully auto-generated skill: {new_skill_component.name}")
                # The generator already handles registration, so we just return the info.
                return {
                    "name": new_skill_component.name,
                    "type": "skill",
                    "path": new_skill_component.path,
                    "component": new_skill_component 
                }
            else:
                logger.error("Failed to auto-generate skill.")
                self.stats["errors_encountered"] += 1
                return None
        except Exception as e:
            logger.critical(f"A critical error occurred during auto-generation: {e}", exc_info=True)
            self.stats["errors_encountered"] += 1
            return None
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        
        try:
            # Get component scanner stats
            scanner_stats = component_scanner.get_component_stats()
            
            # Get registry stats
            registry_stats = dynamic_registry.get_registry_stats()
            
            # Get hot reload stats
            reload_stats = hot_reload_manager.get_reload_stats()
            
            # Get audit stats
            audit_stats = audit_logger.get_audit_stats()
            
            # Get skill generator stats
            generator_stats = skill_auto_generator.get_generation_stats()
            
            return {
                "system": {
                    "initialized": self.initialized,
                    "running": self.running,
                    "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                    "uptime_seconds": (
                        (datetime.now() - self.startup_time).total_seconds() 
                        if self.startup_time else 0
                    )
                },
                "components": {
                    "scanner": scanner_stats,
                    "registry": registry_stats,
                    "hot_reload": reload_stats,
                    "audit": audit_stats,
                    "generator": generator_stats
                },
                "statistics": self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "error": str(e),
                "system": {"initialized": self.initialized, "running": self.running}
            }
    
    async def shutdown(self):
        """Shutdown the self-building system."""
        
        if not self.running:
            return
        
        try:
            logger.info("Shutting down self-building orchestrator...")
            
            # Stop hot reload monitoring
            await hot_reload_manager.stop_watching()
            
            # Log system shutdown
            await audit_logger.log_system_shutdown({
                "shutdown_time": datetime.now().isoformat(),
                "uptime_seconds": (
                    (datetime.now() - self.startup_time).total_seconds() 
                    if self.startup_time else 0
                ),
                "final_stats": self.stats
            })
            
            self.running = False
            
            logger.info("Self-building orchestrator shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def force_rescan(self) -> Dict[str, Any]:
        """Force a complete rescan of the system."""
        
        logger.info("Forcing complete system rescan...")
        
        try:
            # Clear existing discoveries
            component_scanner.discovered_components.clear()
            component_scanner.loaded_modules.clear()
            
            # Perform fresh scan
            await self._initial_system_scan()
            
            # Update stats
            scanner_stats = component_scanner.get_component_stats()
            self.stats["components_discovered"] = scanner_stats["total_discovered"]
            
            logger.info("Force rescan completed successfully")
            
            return {
                "success": True,
                "components_discovered": scanner_stats["total_discovered"],
                "components_registered": scanner_stats["total_loaded"]
            }
            
        except Exception as e:
            logger.error(f"Force rescan failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global orchestrator instance
self_building_orchestrator = SelfBuildingOrchestrator()


# Convenience functions
async def initialize_self_building():
    """Initialize the self-building system."""
    await self_building_orchestrator.initialize()


async def handle_user_request(user_request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle a user request with auto-generation if needed."""
    return await self_building_orchestrator.handle_user_request(user_request, context)


async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status."""
    return await self_building_orchestrator.get_system_status()


async def shutdown_self_building():
    """Shutdown the self-building system."""
    await self_building_orchestrator.shutdown()
