"""
Dynamic Registry - Central registry for all components in the system.
Handles registration, deregistration, and component lifecycle management.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..discovery.component_scanner import ComponentInfo

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """Status of a component in the registry."""
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class RegistryEntry:
    """Entry in the dynamic registry."""
    component: ComponentInfo
    status: ComponentStatus
    registered_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    instance: Optional[Any] = None
    error_history: List[str] = field(default_factory=list)


class DynamicRegistry:
    """
    Central registry for all components in the system.
    Manages component lifecycle, dependencies, and activation.
    """
    
    def __init__(self):
        self.entries: Dict[str, RegistryEntry] = {}
        self.type_index: Dict[str, Set[str]] = {
            "skills": set(),
            "plugins": set(),
            "mcp_servers": set()
        }
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.activation_hooks: Dict[str, List[Callable]] = {}
        self.deactivation_hooks: Dict[str, List[Callable]] = {}
        
        # Registry statistics
        self.stats = {
            "total_registered": 0,
            "total_active": 0,
            "total_errors": 0,
            "registrations_today": 0,
            "last_cleanup": datetime.now()
        }
    
    async def register_component(
        self, 
        component: ComponentInfo, 
        instance: Optional[Any] = None
    ) -> bool:
        """
        Register a component in the registry.
        
        Args:
            component: ComponentInfo to register
            instance: Optional instance of the component
            
        Returns:
            True if successfully registered, False otherwise
        """
        try:
            # Check if already registered
            if component.name in self.entries:
                logger.debug(f"Component already registered: {component.name}")
                return True
            
            # Create registry entry
            entry = RegistryEntry(
                component=component,
                status=ComponentStatus.REGISTERED,
                registered_at=datetime.now(),
                instance=instance
            )
            
            # Add to registry
            self.entries[component.name] = entry
            self.type_index[component.type].add(component.name)
            
            # Update statistics
            self.stats["total_registered"] += 1
            self.stats["registrations_today"] += 1
            
            # Run activation hooks
            await self._run_activation_hooks(component.name)
            
            logger.info(f"Registered component: {component.name} ({component.type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register component {component.name}: {e}")
            return False
    
    async def deregister_component(self, component_name: str) -> bool:
        """
        Deregister a component from the registry.
        
        Args:
            component_name: Name of component to deregister
            
        Returns:
            True if successfully deregistered, False otherwise
        """
        try:
            entry = self.entries.get(component_name)
            if not entry:
                logger.warning(f"Component not found for deregistration: {component_name}")
                return False
            
            # Run deactivation hooks
            await self._run_deactivation_hooks(component_name)
            
            # Remove from type index
            self.type_index[entry.component.type].discard(component_name)
            
            # Remove dependencies
            self._remove_dependencies(component_name)
            
            # Remove from registry
            del self.entries[component_name]
            
            # Update statistics
            self.stats["total_registered"] -= 1
            
            logger.info(f"Deregistered component: {component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deregister component {component_name}: {e}")
            return False
    
    async def activate_component(self, component_name: str) -> bool:
        """
        Activate a registered component.
        
        Args:
            component_name: Name of component to activate
            
        Returns:
            True if successfully activated, False otherwise
        """
        try:
            entry = self.entries.get(component_name)
            if not entry:
                logger.error(f"Component not found: {component_name}")
                return False
            
            if entry.status == ComponentStatus.ACTIVE:
                logger.debug(f"Component already active: {component_name}")
                return True
            
            # Check dependencies
            if not await self._check_dependencies(component_name):
                logger.error(f"Dependencies not satisfied for: {component_name}")
                return False
            
            # Activate the component
            if entry.instance and hasattr(entry.instance, 'activate'):
                await self._safe_call(entry.instance.activate)
            
            # Update status
            entry.status = ComponentStatus.ACTIVE
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            
            # Update statistics
            self.stats["total_active"] += 1
            
            logger.info(f"Activated component: {component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to activate component {component_name}: {e}")
            await self._mark_component_error(component_name, str(e))
            return False
    
    async def deactivate_component(self, component_name: str) -> bool:
        """
        Deactivate an active component.
        
        Args:
            component_name: Name of component to deactivate
            
        Returns:
            True if successfully deactivated, False otherwise
        """
        try:
            entry = self.entries.get(component_name)
            if not entry:
                logger.error(f"Component not found: {component_name}")
                return False
            
            if entry.status != ComponentStatus.ACTIVE:
                logger.debug(f"Component not active: {component_name}")
                return True
            
            # Check if other components depend on this one
            if entry.dependents:
                logger.warning(f"Component has dependents, deactivating them first: {component_name}")
                for dependent in list(entry.dependents):
                    await self.deactivate_component(dependent)
            
            # Deactivate the component
            if entry.instance and hasattr(entry.instance, 'deactivate'):
                await self._safe_call(entry.instance.deactivate)
            
            # Update status
            entry.status = ComponentStatus.INACTIVE
            
            # Update statistics
            self.stats["total_active"] -= 1
            
            logger.info(f"Deactivated component: {component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate component {component_name}: {e}")
            return False
    
    def add_dependency(self, component_name: str, dependency_name: str):
        """Add a dependency relationship between components."""
        
        if component_name not in self.entries or dependency_name not in self.entries:
            logger.error(f"Cannot add dependency: component not found")
            return
        
        # Add to dependency graph
        if component_name not in self.dependency_graph:
            self.dependency_graph[component_name] = set()
        self.dependency_graph[component_name].add(dependency_name)
        
        # Update registry entries
        self.entries[component_name].dependencies.add(dependency_name)
        self.entries[dependency_name].dependents.add(component_name)
        
        logger.debug(f"Added dependency: {component_name} -> {dependency_name}")
    
    def remove_dependency(self, component_name: str, dependency_name: str):
        """Remove a dependency relationship between components."""
        
        if component_name in self.dependency_graph:
            self.dependency_graph[component_name].discard(dependency_name)
        
        if component_name in self.entries:
            self.entries[component_name].dependencies.discard(dependency_name)
        
        if dependency_name in self.entries:
            self.entries[dependency_name].dependents.discard(component_name)
        
        logger.debug(f"Removed dependency: {component_name} -> {dependency_name}")
    
    def _remove_dependencies(self, component_name: str):
        """Remove all dependencies for a component."""
        
        entry = self.entries.get(component_name)
        if not entry:
            return
        
        # Remove as dependency from others
        for dependent in list(entry.dependents):
            self.remove_dependency(dependent, component_name)
        
        # Remove dependencies on others
        for dependency in list(entry.dependencies):
            self.remove_dependency(component_name, dependency)
        
        # Remove from dependency graph
        self.dependency_graph.pop(component_name, None)
    
    async def _check_dependencies(self, component_name: str) -> bool:
        """Check if all dependencies for a component are satisfied."""
        
        entry = self.entries.get(component_name)
        if not entry:
            return False
        
        for dependency in entry.dependencies:
            dep_entry = self.entries.get(dependency)
            if not dep_entry or dep_entry.status != ComponentStatus.ACTIVE:
                # Try to activate dependency
                if not await self.activate_component(dependency):
                    return False
        
        return True
    
    async def _run_activation_hooks(self, component_name: str):
        """Run activation hooks for a component."""
        
        hooks = self.activation_hooks.get(component_name, [])
        for hook in hooks:
            try:
                await self._safe_call(hook, component_name)
            except Exception as e:
                logger.error(f"Activation hook failed for {component_name}: {e}")
    
    async def _run_deactivation_hooks(self, component_name: str):
        """Run deactivation hooks for a component."""
        
        hooks = self.deactivation_hooks.get(component_name, [])
        for hook in hooks:
            try:
                await self._safe_call(hook, component_name)
            except Exception as e:
                logger.error(f"Deactivation hook failed for {component_name}: {e}")
    
    async def _safe_call(self, func, *args, **kwargs):
        """Safely call a function, handling both sync and async."""
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Safe call failed: {e}")
            raise
    
    async def _mark_component_error(self, component_name: str, error: str):
        """Mark a component as having an error."""
        
        entry = self.entries.get(component_name)
        if entry:
            entry.status = ComponentStatus.ERROR
            entry.error_history.append(f"{datetime.now()}: {error}")
            self.stats["total_errors"] += 1
    
    def get_component(self, component_name: str) -> Optional[RegistryEntry]:
        """Get a component entry from the registry."""
        return self.entries.get(component_name)
    
    def list_components(
        self, 
        component_type: Optional[str] = None,
        status: Optional[ComponentStatus] = None
    ) -> List[RegistryEntry]:
        """
        List components in the registry.
        
        Args:
            component_type: Optional filter by component type
            status: Optional filter by status
            
        Returns:
            List of RegistryEntry objects
        """
        entries = list(self.entries.values())
        
        if component_type:
            entries = [e for e in entries if e.component.type == component_type]
        
        if status:
            entries = [e for e in entries if e.status == status]
        
        return sorted(entries, key=lambda x: x.component.name)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        
        # Update current stats
        active_count = sum(1 for e in self.entries.values() if e.status == ComponentStatus.ACTIVE)
        error_count = sum(1 for e in self.entries.values() if e.status == ComponentStatus.ERROR)
        
        self.stats.update({
            "total_active": active_count,
            "total_errors": error_count,
            "by_type": {
                comp_type: len(names) 
                for comp_type, names in self.type_index.items()
            },
            "by_status": {
                status.value: sum(1 for e in self.entries.values() if e.status == status)
                for status in ComponentStatus
            }
        })
        
        return self.stats.copy()
    
    def add_activation_hook(self, component_name: str, hook: Callable):
        """Add an activation hook for a component."""
        
        if component_name not in self.activation_hooks:
            self.activation_hooks[component_name] = []
        self.activation_hooks[component_name].append(hook)
    
    def add_deactivation_hook(self, component_name: str, hook: Callable):
        """Add a deactivation hook for a component."""
        
        if component_name not in self.deactivation_hooks:
            self.deactivation_hooks[component_name] = []
        self.deactivation_hooks[component_name].append(hook)
    
    async def cleanup_inactive_components(self, max_age_hours: int = 24):
        """Clean up inactive components that haven't been accessed recently."""
        
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for name, entry in self.entries.items():
            if (entry.status == ComponentStatus.INACTIVE and
                entry.last_accessed and
                entry.last_accessed.timestamp() < cutoff_time):
                to_remove.append(name)
        
        for name in to_remove:
            await self.deregister_component(name)
            logger.info(f"Cleaned up inactive component: {name}")
        
        self.stats["last_cleanup"] = datetime.now()
        return len(to_remove)


# Global registry instance
dynamic_registry = DynamicRegistry()


# Convenience functions
async def register_component(component: ComponentInfo, instance: Optional[Any] = None) -> bool:
    """Register a component in the global registry."""
    return await dynamic_registry.register_component(component, instance)


async def activate_component(component_name: str) -> bool:
    """Activate a component in the global registry."""
    return await dynamic_registry.activate_component(component_name)


def get_component(component_name: str) -> Optional[RegistryEntry]:
    """Get a component from the global registry."""
    return dynamic_registry.get_component(component_name)