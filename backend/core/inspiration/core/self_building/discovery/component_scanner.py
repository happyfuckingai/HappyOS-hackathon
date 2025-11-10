"""
Component discovery and scanning.
Automatically finds and loads all plugins, skills, and MCP servers.
"""

import os
import importlib
import importlib.util
import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """Information about a discovered component."""
    name: str
    type: str  # 'skill', 'plugin', 'mcp_server'
    path: str
    module_name: str
    last_modified: datetime
    registered: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComponentScanner:
    """Scans and discovers all components in the system."""
    
    def __init__(self, base_path: str = "."): # Changed default base_path to relative "."
        self.base_path = Path(base_path)
        self.scan_paths = {
            "skills": [
                self.base_path / "app" / "skills",
                self.base_path / "app" / "skills" / "generated"
            ],
            "plugins": [
                self.base_path / "app" / "plugins",
                self.base_path / "app" / "plugins" / "generated"
            ],
            "mcp_servers": [
                self.base_path / "app" / "mcp" / "servers",
                self.base_path / "app" / "mcp" / "servers" / "generated"
            ]
        }
        self.discovered_components: Dict[str, ComponentInfo] = {}
        self.loaded_modules: Set[str] = set()
        
        # Statistics
        self.stats = {
            "total_discovered": 0,
            "total_loaded": 0,
            "scan_count": 0,
            "last_scan": None,
            "errors": 0
        }
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all scan directories exist."""
        for component_type, paths in self.scan_paths.items():
            for path in paths:
                path.mkdir(parents=True, exist_ok=True)
                
                # Create __init__.py if it doesn't exist
                init_file = path / "__init__.py"
                if not init_file.exists():
                    init_file.write_text("# Auto-generated __init__.py\n")
    
    async def scan_all_components(self) -> Dict[str, List[ComponentInfo]]:
        """Scan all component types and return discovered components."""
        
        results = {}
        
        for component_type, paths in self.scan_paths.items():
            components = []
            
            for scan_path in paths:
                found = await self._scan_directory(scan_path, component_type)
                components.extend(found)
            
            results[component_type] = components
            logger.info(f"Discovered {len(components)} {component_type}")
        
        return results
    
    async def _scan_directory(self, directory: Path, component_type: str) -> List[ComponentInfo]:
        """Scan a specific directory for components."""
        
        components = []
        
        if not directory.exists():
            return components
        
        try:
            for file_path in directory.rglob("*.py"):
                # Skip __init__.py and __pycache__
                if file_path.name.startswith("__"):
                    continue
                
                component = await self._analyze_file(file_path, component_type)
                if component:
                    components.append(component)
                    self.discovered_components[component.name] = component
        
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return components
    
    async def _analyze_file(self, file_path: Path, component_type: str) -> Optional[ComponentInfo]:
        """Analyze a Python file to determine if it's a valid component."""
        
        try:
            # Get file stats
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Generate module name
            relative_path = file_path.relative_to(self.base_path)
            module_name = str(relative_path.with_suffix("")).replace("/", ".")
            
            # Read file content to check for required patterns
            content = file_path.read_text(encoding='utf-8')
            
            # Check if it's a valid component
            if not self._is_valid_component(content, component_type):
                return None
            
            component_name = file_path.stem
            
            return ComponentInfo(
                name=component_name,
                type=component_type,
                path=str(file_path),
                module_name=module_name,
                last_modified=last_modified,
                metadata={
                    "file_size": stat.st_size,
                    "has_register_function": "def register(" in content,
                    "has_execute_function": "def execute" in content or "async def execute" in content
                }
            )
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return None
    
    def _is_valid_component(self, content: str, component_type: str) -> bool:
        """Check if file content represents a valid component."""
        
        # Common requirements
        if not content.strip():
            return False
        
        # Type-specific validation
        if component_type == "skills":
            return (
                "def execute" in content or "async def execute" in content
            ) and "skill" in content.lower()
        
        elif component_type == "plugins":
            return (
                "def register" in content or "class" in content
            ) and "plugin" in content.lower()
        
        elif component_type == "mcp_servers":
            return (
                "mcp" in content.lower() or "server" in content.lower()
            ) and ("def" in content or "class" in content)
        
        return True
    
    async def load_component(self, component: ComponentInfo) -> bool:
        """Load and register a specific component."""
        
        try:
            # Skip if already loaded
            if component.module_name in self.loaded_modules:
                return True
            
            # Import the module
            spec = importlib.util.spec_from_file_location(
                component.module_name, 
                component.path
            )
            
            if not spec or not spec.loader:
                component.error = "Could not create module spec"
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Register the component if it has a register function
            if hasattr(module, "register"):
                await self._safe_register(module, component)
            
            # Mark as loaded
            self.loaded_modules.add(component.module_name)
            component.registered = True
            
            logger.info(f"Successfully loaded component: {component.name}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to load component {component.name}: {e}"
            logger.error(error_msg)
            component.error = error_msg
            return False
    
    async def _safe_register(self, module, component: ComponentInfo):
        """Safely call the register function of a module."""
        
        try:
            register_func = getattr(module, "register")
            
            # Call register function (handle both sync and async)
            if asyncio.iscoroutinefunction(register_func):
                await register_func()
            else:
                register_func()
            
            logger.info(f"Registered component: {component.name}")
            
        except Exception as e:
            logger.error(f"Error registering component {component.name}: {e}")
            component.error = f"Registration failed: {e}"
    
    async def reload_component(self, component_name: str) -> bool:
        """Reload a specific component."""
        
        component = self.discovered_components.get(component_name)
        if not component:
            return False
        
        try:
            # Remove from loaded modules to force reload
            if component.module_name in self.loaded_modules:
                self.loaded_modules.remove(component.module_name)
            
            # Reload the component
            return await self.load_component(component)
            
        except Exception as e:
            logger.error(f"Error reloading component {component_name}: {e}")
            return False
    
    def get_component_stats(self) -> Dict[str, Any]:
        """Get statistics about discovered components."""
        
        stats = {
            "total_discovered": len(self.discovered_components),
            "total_loaded": len(self.loaded_modules),
            "by_type": {},
            "errors": []
        }
        
        # Count by type
        for component in self.discovered_components.values():
            comp_type = component.type
            if comp_type not in stats["by_type"]:
                stats["by_type"][comp_type] = {
                    "discovered": 0,
                    "registered": 0,
                    "errors": 0
                }
            
            stats["by_type"][comp_type]["discovered"] += 1
            
            if component.registered:
                stats["by_type"][comp_type]["registered"] += 1
            
            if component.error:
                stats["by_type"][comp_type]["errors"] += 1
                stats["errors"].append({
                    "component": component.name,
                    "type": component.type,
                    "error": component.error
                })
        
        return stats
    
    def list_components(self, component_type: Optional[str] = None) -> List[ComponentInfo]:
        """List all discovered components, optionally filtered by type."""
        
        components = list(self.discovered_components.values())
        
        if component_type:
            components = [c for c in components if c.type == component_type]
        
        return sorted(components, key=lambda x: x.name)


# Global scanner instance
component_scanner = ComponentScanner()


# Convenience functions
async def scan_components() -> Dict[str, List[ComponentInfo]]:
    """Scan all components."""
    return await component_scanner.scan_all_components()


async def load_all_components() -> Dict[str, Any]:
    """Load all discovered components."""
    results = {"total_loaded": 0, "errors": 0, "components": []}
    
    for component in component_scanner.discovered_components.values():
        success = await component_scanner.load_component(component)
        if success:
            results["total_loaded"] += 1
            results["components"].append(component.name)
        else:
            results["errors"] += 1
    
    return results


def get_component_stats() -> Dict[str, Any]:
    """Get component statistics."""
    return component_scanner.get_component_stats()