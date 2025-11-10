"""
Hot Reload Manager - Handles real-time reloading of components.
Watches for file changes and automatically reloads components without restart.
"""

import logging
import asyncio
import sys
import importlib
from typing import Dict, Any, Set, Optional, Callable
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler # Removed FileModifiedEvent, FileCreatedEvent

from ..discovery.component_scanner import component_scanner, ComponentInfo
from ..registry.dynamic_registry import dynamic_registry

logger = logging.getLogger(__name__)


class ComponentFileHandler(FileSystemEventHandler):
    """Handles file system events for component files."""
    
    def __init__(self, reload_manager):
        self.reload_manager = reload_manager
        super().__init__()
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith('.py'):
            asyncio.create_task(self.reload_manager.handle_file_change(event.src_path, 'modified'))
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith('.py'):
            asyncio.create_task(self.reload_manager.handle_file_change(event.src_path, 'created'))


class HotReloadManager:
    """
    Manages hot reloading of components.
    Watches for file changes and automatically reloads affected components.
    """
    
    def __init__(self):
        self.observer = Observer()
        self.watched_paths: Set[str] = set()
        self.reload_callbacks: Dict[str, List[Callable]] = {}
        self.reload_history = []
        self.is_watching = False
        
        # Reload statistics
        self.stats = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload": None
        }
    
    async def start_watching(self):
        """Start watching for file changes."""
        
        if self.is_watching:
            logger.debug("Hot reload manager already watching")
            return
        
        try:
            # Watch component directories
            watch_dirs = [
                "/home/mr/Dokument/filee.tar/happyos/app/skills",
                "/home/mr/Dokument/filee.tar/happyos/app/plugins",
                "/home/mr/Dokument/filee.tar/happyos/app/mcp/servers",
                "/home/mr/Dokument/filee.tar/happyos/app/core"
            ]
            
            event_handler = ComponentFileHandler(self)
            
            for watch_dir in watch_dirs:
                if Path(watch_dir).exists():
                    self.observer.schedule(event_handler, watch_dir, recursive=True)
                    self.watched_paths.add(watch_dir)
                    logger.debug(f"Watching directory: {watch_dir}")
            
            self.observer.start()
            self.is_watching = True
            
            logger.info("Hot reload manager started watching for changes")
            
        except Exception as e:
            logger.error(f"Failed to start hot reload manager: {e}")
            raise
    
    async def stop_watching(self):
        """Stop watching for file changes."""
        
        if not self.is_watching:
            return
        
        try:
            self.observer.stop()
            self.observer.join()
            self.is_watching = False
            
            logger.info("Hot reload manager stopped watching")
            
        except Exception as e:
            logger.error(f"Error stopping hot reload manager: {e}")
    
    async def handle_file_change(self, file_path: str, change_type: str):
        """
        Handle a file change event.
        
        Args:
            file_path: Path to the changed file
            change_type: Type of change ('modified', 'created', 'deleted')
        """
        try:
            logger.debug(f"File {change_type}: {file_path}")
            
            # Skip temporary files and non-Python files
            if (file_path.endswith('.tmp') or 
                file_path.endswith('.swp') or
                not file_path.endswith('.py')):
                return
            
            # Find affected component
            component = await self._find_component_by_path(file_path)
            
            if component:
                await self._reload_component(component, change_type)
            elif change_type == 'created':
                # New file created, scan for new component
                await self._scan_new_component(file_path)
            
        except Exception as e:
            logger.error(f"Error handling file change {file_path}: {e}")
    
    async def _find_component_by_path(self, file_path: str) -> Optional[ComponentInfo]:
        """Find a component by its file path."""
        
        for component in component_scanner.discovered_components.values():
            if component.path == file_path:
                return component
        
        return None
    
    async def _reload_component(self, component: ComponentInfo, change_type: str):
        """
        Reload a specific component.
        
        Args:
            component: ComponentInfo to reload
            change_type: Type of change that triggered reload
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Reloading component: {component.name} ({change_type})")
            
            # Deactivate component first
            await dynamic_registry.deactivate_component(component.name)
            
            # Remove from loaded modules to force reload
            module_name = component.module_name
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Reload the component
            success = await component_scanner.reload_component(component.name)
            
            if success:
                # Re-register and activate
                await dynamic_registry.register_component(component)
                await dynamic_registry.activate_component(component.name)
                
                # Run reload callbacks
                await self._run_reload_callbacks(component.name, True)
                
                self.stats["successful_reloads"] += 1
                logger.info(f"Successfully reloaded component: {component.name}")
                
            else:
                self.stats["failed_reloads"] += 1
                logger.error(f"Failed to reload component: {component.name}")
                
                # Run reload callbacks with failure
                await self._run_reload_callbacks(component.name, False)
            
            # Track reload
            self._track_reload(component.name, change_type, success, start_time)
            
        except Exception as e:
            self.stats["failed_reloads"] += 1
            logger.error(f"Error reloading component {component.name}: {e}")
            
            # Track failed reload
            self._track_reload(component.name, change_type, False, start_time, str(e))
    
    async def _scan_new_component(self, file_path: str):
        """Scan and register a newly created component."""
        
        try:
            logger.info(f"Scanning new file: {file_path}")
            
            # Determine component type from path
            path_obj = Path(file_path)
            
            if "/skills/" in str(path_obj):
                component_type = "skills"
            elif "/plugins/" in str(path_obj):
                component_type = "plugins"
            elif "/mcp/" in str(path_obj):
                component_type = "mcp_servers"
            else:
                logger.debug(f"File not in component directory: {file_path}")
                return
            
            # Analyze the new file
            component = await component_scanner._analyze_file(path_obj, component_type)
            
            if component:
                # Load and register the new component
                success = await component_scanner.load_component(component)
                
                if success:
                    await dynamic_registry.register_component(component)
                    await dynamic_registry.activate_component(component.name)
                    
                    logger.info(f"Discovered and registered new component: {component.name}")
                    
                    # Track as new component
                    self._track_reload(component.name, "created", True, datetime.now())
            
        except Exception as e:
            logger.error(f"Error scanning new component {file_path}: {e}")
    
    async def _run_reload_callbacks(self, component_name: str, success: bool):
        """Run reload callbacks for a component."""
        
        callbacks = self.reload_callbacks.get(component_name, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(component_name, success)
                else:
                    callback(component_name, success)
            except Exception as e:
                logger.error(f"Reload callback failed for {component_name}: {e}")
    
    def _track_reload(
        self, 
        component_name: str, 
        change_type: str, 
        success: bool, 
        start_time: datetime,
        error: Optional[str] = None
    ):
        """Track a reload operation for analytics."""
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        reload_record = {
            "timestamp": end_time,
            "component_name": component_name,
            "change_type": change_type,
            "success": success,
            "duration_seconds": duration,
            "error": error
        }
        
        self.reload_history.append(reload_record)
        
        # Keep only recent history
        if len(self.reload_history) > 1000:
            self.reload_history = self.reload_history[-500:]
        
        # Update stats
        self.stats["total_reloads"] += 1
        self.stats["last_reload"] = end_time
    
    def add_reload_callback(self, component_name: str, callback: Callable):
        """
        Add a callback to be called when a component is reloaded.
        
        Args:
            component_name: Name of component to watch
            callback: Function to call on reload (component_name, success) -> None
        """
        if component_name not in self.reload_callbacks:
            self.reload_callbacks[component_name] = []
        
        self.reload_callbacks[component_name].append(callback)
        logger.debug(f"Added reload callback for component: {component_name}")
    
    def remove_reload_callback(self, component_name: str, callback: Callable):
        """Remove a reload callback for a component."""
        
        if component_name in self.reload_callbacks:
            try:
                self.reload_callbacks[component_name].remove(callback)
                logger.debug(f"Removed reload callback for component: {component_name}")
            except ValueError:
                pass
    
    async def manual_reload(self, component_name: str) -> bool:
        """
        Manually reload a specific component.
        
        Args:
            component_name: Name of component to reload
            
        Returns:
            True if successfully reloaded, False otherwise
        """
        component = component_scanner.get_component(component_name)
        
        if not component:
            logger.error(f"Component not found for manual reload: {component_name}")
            return False
        
        await self._reload_component(component, "manual")
        return True
    
    async def reload_all_components(self) -> Dict[str, Any]:
        """
        Reload all discovered components.
        
        Returns:
            Dictionary with reload results
        """
        logger.info("Starting reload of all components")
        
        results = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "components": []
        }
        
        for component in component_scanner.discovered_components.values():
            results["total"] += 1
            
            try:
                await self._reload_component(component, "bulk_reload")
                results["successful"] += 1
                results["components"].append({
                    "name": component.name,
                    "success": True
                })
            except Exception as e:
                results["failed"] += 1
                results["components"].append({
                    "name": component.name,
                    "success": False,
                    "error": str(e)
                })
        
        logger.info(f"Bulk reload completed: {results['successful']}/{results['total']} successful")
        return results
    
    def get_reload_stats(self) -> Dict[str, Any]:
        """Get hot reload statistics."""
        
        recent_reloads = self.reload_history[-10:] if self.reload_history else []
        
        return {
            **self.stats,
            "is_watching": self.is_watching,
            "watched_paths": list(self.watched_paths),
            "recent_reloads": recent_reloads,
            "average_reload_time": (
                sum(r["duration_seconds"] for r in self.reload_history) / len(self.reload_history)
                if self.reload_history else 0
            )
        }


# Global hot reload manager instance
hot_reload_manager = HotReloadManager()


# Convenience functions
async def start_hot_reload():
    """Start the hot reload manager."""
    await hot_reload_manager.start_watching()


async def stop_hot_reload():
    """Stop the hot reload manager."""
    await hot_reload_manager.stop_watching()


async def reload_component(component_name: str) -> bool:
    """Manually reload a specific component."""
    return await hot_reload_manager.manual_reload(component_name)