"""
Code Loader Module

This module provides functionality for loading and registering dynamically generated code.
"""

import os
import sys
import logging
import importlib
import importlib.util
import inspect
from typing import Dict, Any, Optional, List, Union, Callable, Type
from pathlib import Path
import json
import asyncio
import subprocess
import signal
import time
import threading
import re

from app.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

class CodeLoader:
    """
    Class for loading and registering dynamically generated code.
    """
    
    def __init__(self):
        """Initialize the code loader."""
        self.settings = get_settings()
        self.loaded_modules = {}
        self.loaded_components = {}
        self.restart_processes = {}
        self.module_watchers = {}
        
        # Create module registry
        self.module_registry = {}
        self.component_registry = {}
        self.function_registry = {}
        self.class_registry = {}
    
    async def load_python_module(
        self,
        file_path: Union[str, Path],
        module_name: Optional[str] = None,
        reload: bool = False,
        register: bool = True
    ) -> Dict[str, Any]:
        """
        Load a Python module from a file.
        
        Args:
            file_path: Path to the Python file
            module_name: Optional module name (defaults to filename without extension)
            reload: Whether to reload the module if already loaded
            register: Whether to register the module's classes and functions
            
        Returns:
            Dictionary containing the loaded module and its components
        """
        try:
            # Convert to Path object
            file_path = Path(file_path)
            
            # Ensure file exists
            if not file_path.exists():
                logger.error(f"Module file not found: {file_path}")
                return {"success": False, "error": f"Module file not found: {file_path}"}
            
            # Determine module name if not provided
            if not module_name:
                module_name = file_path.stem
            
            # Check if module is already loaded and reload is not requested
            if module_name in self.loaded_modules and not reload:
                logger.info(f"Module {module_name} already loaded")
                return {
                    "success": True,
                    "module": self.loaded_modules[module_name],
                    "components": self.module_registry.get(module_name, {})
                }
            
            # Load the module
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    logger.error(f"Failed to create module spec for {file_path}")
                    return {"success": False, "error": f"Failed to create module spec for {file_path}"}
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Store the loaded module
                self.loaded_modules[module_name] = module
                
                # Register module components if requested
                if register:
                    await self.register_module_components(module, module_name)
                
                logger.info(f"Successfully loaded module {module_name} from {file_path}")
                return {
                    "success": True,
                    "module": module,
                    "components": self.module_registry.get(module_name, {})
                }
            except Exception as e:
                logger.error(f"Error loading module {module_name} from {file_path}: {str(e)}")
                return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error loading Python module: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def register_module_components(self, module: Any, module_name: str) -> Dict[str, Any]:
        """
        Register classes and functions from a loaded module.
        
        Args:
            module: The loaded module
            module_name: The module name
            
        Returns:
            Dictionary containing the registered components
        """
        try:
            # Initialize registry for this module
            self.module_registry[module_name] = {
                "classes": {},
                "functions": {}
            }
            
            # Find all classes and functions in the module
            for name, obj in inspect.getmembers(module):
                # Skip private members
                if name.startswith("_"):
                    continue
                
                # Register classes
                if inspect.isclass(obj):
                    self.class_registry[name] = obj
                    self.module_registry[module_name]["classes"][name] = obj
                
                # Register functions
                elif inspect.isfunction(obj):
                    self.function_registry[name] = obj
                    self.module_registry[module_name]["functions"][name] = obj
            
            logger.info(f"Registered {len(self.module_registry[module_name]['classes'])} classes and "
                       f"{len(self.module_registry[module_name]['functions'])} functions from module {module_name}")
            
            return self.module_registry[module_name]
        except Exception as e:
            logger.error(f"Error registering components from module {module_name}: {str(e)}")
            return {"classes": {}, "functions": {}}
    
    async def load_javascript_component(
        self,
        file_path: Union[str, Path],
        component_name: Optional[str] = None,
        component_type: str = "react",
        hot_reload: bool = True
    ) -> Dict[str, Any]:
        """
        Load a JavaScript component.
        
        Args:
            file_path: Path to the JavaScript file
            component_name: Optional component name (defaults to filename without extension)
            component_type: Type of component (react, vue, etc.)
            hot_reload: Whether to enable hot reloading for this component
            
        Returns:
            Dictionary containing the component information
        """
        try:
            # Convert to Path object
            file_path = Path(file_path)
            
            # Ensure file exists
            if not file_path.exists():
                logger.error(f"Component file not found: {file_path}")
                return {"success": False, "error": f"Component file not found: {file_path}"}
            
            # Determine component name if not provided
            if not component_name:
                component_name = file_path.stem
            
            # Create component info
            component_info = {
                "name": component_name,
                "path": str(file_path),
                "type": component_type,
                "timestamp": time.time()
            }
            
            # Store component info
            self.component_registry[component_name] = component_info
            self.loaded_components[component_name] = component_info
            
            # Trigger hot reload if enabled
            if hot_reload:
                await self.trigger_hot_reload(component_name, file_path)
            
            logger.info(f"Successfully loaded component {component_name} from {file_path}")
            return {
                "success": True,
                "component": component_info
            }
        except Exception as e:
            logger.error(f"Error loading JavaScript component: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def trigger_hot_reload(self, component_name: str, file_path: Union[str, Path]) -> bool:
        """
        Trigger hot reload for a component.
        
        Args:
            component_name: The component name
            file_path: Path to the component file
            
        Returns:
            True if hot reload was triggered successfully, False otherwise
        """
        try:
            # Convert to Path object
            file_path = Path(file_path)
            
            # Check if hot reload server is running
            if not self.settings.code_generation.hot_reload_enabled:
                logger.warning("Hot reload is not enabled in settings")
                return False
            
            # Determine hot reload method
            hot_reload_method = self.settings.code_generation.hot_reload_method
            
            if hot_reload_method == "websocket":
                # Send hot reload signal via WebSocket
                await self._send_hot_reload_signal(component_name, file_path)
                return True
            elif hot_reload_method == "file_watcher":
                # Use file watcher for hot reload
                return self._setup_file_watcher(component_name, file_path)
            elif hot_reload_method == "restart":
                # Restart the development server
                return await self._restart_dev_server()
            else:
                logger.warning(f"Unknown hot reload method: {hot_reload_method}")
                return False
        except Exception as e:
            logger.error(f"Error triggering hot reload: {str(e)}")
            return False
    
    async def _send_hot_reload_signal(self, component_name: str, file_path: Path) -> bool:
        """
        Send hot reload signal via WebSocket.
        
        Args:
            component_name: The component name
            file_path: Path to the component file
            
        Returns:
            True if signal was sent successfully, False otherwise
        """
        try:
            # Import WebSocket client
            import websockets
            
            # Get WebSocket URL from settings
            ws_url = self.settings.code_generation.hot_reload_websocket_url
            
            # Prepare hot reload message
            message = json.dumps({
                "type": "hot-reload",
                "component": component_name,
                "path": str(file_path),
                "timestamp": time.time()
            })
            
            # Send message to WebSocket server
            async with websockets.connect(ws_url) as websocket:
                await websocket.send(message)
                logger.info(f"Sent hot reload signal for component {component_name}")
                return True
        except ImportError:
            logger.error("WebSocket client not available. Install with: pip install websockets")
            return False
        except Exception as e:
            logger.error(f"Error sending hot reload signal: {str(e)}")
            return False
    
    def _setup_file_watcher(self, component_name: str, file_path: Path) -> bool:
        """
        Set up a file watcher for hot reload.
        
        Args:
            component_name: The component name
            file_path: Path to the component file
            
        Returns:
            True if file watcher was set up successfully, False otherwise
        """
        try:
            # Check if watchdog is available
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
            except ImportError:
                logger.error("Watchdog not available. Install with: pip install watchdog")
                return False
            
            # Define event handler
            class ReloadHandler(FileSystemEventHandler):
                def __init__(self, callback):
                    self.callback = callback
                
                def on_modified(self, event):
                    if not event.is_directory and Path(event.src_path) == file_path:
                        self.callback(event.src_path)
            
            # Define callback
            def on_file_changed(path):
                logger.info(f"File changed: {path}")
                asyncio.run(self._send_hot_reload_signal(component_name, file_path))
            
            # Set up observer
            observer = Observer()
            handler = ReloadHandler(on_file_changed)
            observer.schedule(handler, str(file_path.parent), recursive=False)
            
            # Start observer in a separate thread
            observer.start()
            
            # Store observer for later cleanup
            self.module_watchers[component_name] = observer
            
            logger.info(f"Set up file watcher for component {component_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting up file watcher: {str(e)}")
            return False
    
    async def _restart_dev_server(self) -> bool:
        """
        Restart the development server.
        
        Returns:
            True if server was restarted successfully, False otherwise
        """
        try:
            # Get restart command from settings
            restart_cmd = self.settings.code_generation.dev_server_restart_command
            
            if not restart_cmd:
                logger.warning("No restart command configured in settings")
                return False
            
            # Execute restart command
            process = await asyncio.create_subprocess_shell(
                restart_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for process to complete
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Successfully restarted development server: {stdout.decode()}")
                return True
            else:
                logger.error(f"Error restarting development server: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error restarting development server: {str(e)}")
            return False
    
    async def get_registered_components(self, component_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all registered components.
        
        Args:
            component_type: Optional type to filter components
            
        Returns:
            Dictionary of registered components
        """
        if component_type:
            return {
                name: info for name, info in self.component_registry.items()
                if info.get("type") == component_type
            }
        else:
            return self.component_registry
    
    async def get_registered_modules(self) -> Dict[str, Any]:
        """
        Get all registered modules.
        
        Returns:
            Dictionary of registered modules
        """
        return self.module_registry
    
    async def get_registered_functions(self) -> Dict[str, Callable]:
        """
        Get all registered functions.
        
        Returns:
            Dictionary of registered functions
        """
        return self.function_registry
    
    async def get_registered_classes(self) -> Dict[str, Type]:
        """
        Get all registered classes.
        
        Returns:
            Dictionary of registered classes
        """
        return self.class_registry
    
    async def cleanup(self):
        """Clean up resources."""
        # Stop file watchers
        for component_name, observer in self.module_watchers.items():
            logger.info(f"Stopping file watcher for component {component_name}")
            observer.stop()
            observer.join()
        
        # Clear registries
        self.module_registry.clear()
        self.component_registry.clear()
        self.function_registry.clear()
        self.class_registry.clear()
        self.loaded_modules.clear()
        self.loaded_components.clear()
        self.module_watchers.clear()
        
        logger.info("Cleaned up code loader resources")

# Create singleton instance
code_loader = CodeLoader()