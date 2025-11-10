"""
Hot Reload Examples

This module contains practical examples of how to use the Hot Reload system
for real-time component reloading without system restart.
"""

import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from app.core.self_building.hot_reload.reload_manager import (
    HotReloadManager,
    hot_reload_manager
)

logger = logging.getLogger(__name__)


async def basic_hot_reload_example():
    """Basic hot reload setup and monitoring example."""

    print("=== Basic Hot Reload Example ===")

    # Create reload manager
    reload_manager = HotReloadManager()
    
    # Start watching for changes
    print("🔄 Starting hot reload monitoring...")
    await reload_manager.start()
    
    # Add watch paths
    watch_paths = [
        "app/skills",
        "app/plugins",
        "app/mcp/servers"
    ]
    
    for path in watch_paths:
        if Path(path).exists():
            reload_manager.add_watch_path(path)
            print(f"   👀 Watching: {path}")
    
    print("✅ Hot reload monitoring active")
    print("   ℹ️  Try modifying a file in the watched directories")
    print("   ℹ️  Press Ctrl+C to stop monitoring")
    
    try:
        # Keep monitoring (in real usage, this would run continuously)
        await asyncio.sleep(30)  # Monitor for 30 seconds for demo
    except KeyboardInterrupt:
        print("\n🛑 Stopping hot reload monitoring...")
    finally:
        await reload_manager.stop()
        print("✅ Hot reload stopped")
    
    print()


async def component_specific_reload_example():
    """Example of setting up reload callbacks for specific components."""

    print("=== Component-Specific Reload Example ===")

    reload_manager = HotReloadManager()
    
    # Define reload callbacks for different component types
    async def skill_reload_callback(file_path: str, change_type: str):
        print(f"🔧 Skill reload triggered: {file_path} ({change_type})")
        # Custom skill reload logic
        component_name = Path(file_path).stem
        print(f"   Reloading skill: {component_name}")
        # Add actual reload logic here
    
    async def plugin_reload_callback(file_path: str, change_type: str):
        print(f"🔌 Plugin reload triggered: {file_path} ({change_type})")
        # Custom plugin reload logic
        component_name = Path(file_path).stem
        print(f"   Reloading plugin: {component_name}")
    
    async def mcp_server_reload_callback(file_path: str, change_type: str):
        print(f"🌐 MCP Server reload triggered: {file_path} ({change_type})")
        # Custom MCP server reload logic
        component_name = Path(file_path).stem
        print(f"   Reloading MCP server: {component_name}")
    
    # Register callbacks
    reload_manager.register_reload_callback("skills", skill_reload_callback)
    reload_manager.register_reload_callback("plugins", plugin_reload_callback)
    reload_manager.register_reload_callback("mcp_servers", mcp_server_reload_callback)
    
    print("📋 Registered component-specific reload callbacks")
    
    # Start monitoring
    await reload_manager.start()
    reload_manager.add_watch_path("app/skills")
    reload_manager.add_watch_path("app/plugins")
    reload_manager.add_watch_path("app/mcp/servers")
    
    print("🔄 Monitoring with custom callbacks...")
    print("   ℹ️  Modify files to see component-specific reload handling")
    
    try:
        await asyncio.sleep(20)  # Monitor for 20 seconds for demo
    except KeyboardInterrupt:
        pass
    finally:
        await reload_manager.stop()
    
    print()


async def reload_history_example():
    """Example of tracking and viewing reload history."""

    print("=== Reload History Example ===")

    reload_manager = HotReloadManager()
    await reload_manager.start()
    
    # Add some watch paths
    reload_manager.add_watch_path("app/skills")
    
    # Simulate some reload events (in real usage, these would be triggered by file changes)
    print("📝 Simulating reload events...")
    
    # Add some fake reload history for demonstration
    reload_manager.reload_history.extend([
        {
            "timestamp": datetime.now(),
            "file_path": "app/skills/example_skill.py",
            "change_type": "modified",
            "component_name": "example_skill",
            "success": True,
            "duration": 0.125
        },
        {
            "timestamp": datetime.now(),
            "file_path": "app/plugins/example_plugin.py",
            "change_type": "created",
            "component_name": "example_plugin",
            "success": True,
            "duration": 0.087
        },
        {
            "timestamp": datetime.now(),
            "file_path": "app/skills/broken_skill.py",
            "change_type": "modified",
            "component_name": "broken_skill",
            "success": False,
            "error": "Import error: missing dependency"
        }
    ])
    
    # Get reload history
    history = reload_manager.get_reload_history()
    
    print(f"📊 Reload History ({len(history)} events):")
    for event in history:
        status = "✅" if event.get("success", False) else "❌"
        duration = f" ({event.get('duration', 0):.3f}s)" if event.get("duration") else ""
        error = f" - Error: {event.get('error')}" if event.get("error") else ""
        
        print(f"   {status} {event['timestamp'].strftime('%H:%M:%S')} - "
              f"{event['component_name']} ({event['change_type']}){duration}{error}")
    
    # Get reload statistics
    stats = reload_manager.get_reload_stats()
    print(f"\n📈 Reload Statistics:")
    print(f"   Total reloads: {stats['total_reloads']}")
    print(f"   Successful: {stats['successful_reloads']}")
    print(f"   Failed: {stats['failed_reloads']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")
    print(f"   Average duration: {stats['average_duration']:.3f}s")
    
    await reload_manager.stop()
    print()


async def error_handling_example():
    """Example of error handling during hot reload."""

    print("=== Error Handling Example ===")

    reload_manager = HotReloadManager()
    
    # Define an error-handling callback
    async def error_aware_callback(file_path: str, change_type: str):
        try:
            print(f"🔄 Attempting reload: {file_path}")
            
            # Simulate reload logic that might fail
            component_name = Path(file_path).stem
            
            # Simulate different error scenarios
            if "broken" in component_name:
                raise ImportError("Missing dependency: numpy")
            elif "syntax" in component_name:
                raise SyntaxError("Invalid syntax in line 42")
            elif "permission" in component_name:
                raise PermissionError("Cannot access file")
            else:
                print(f"   ✅ Successfully reloaded {component_name}")
        
        except ImportError as e:
            print(f"   ❌ Import error: {e}")
            # Handle import errors (maybe install dependencies)
        
        except SyntaxError as e:
            print(f"   ❌ Syntax error: {e}")
            # Handle syntax errors (maybe revert to backup)
        
        except PermissionError as e:
            print(f"   ❌ Permission error: {e}")
            # Handle permission errors
        
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            # Handle other errors
    
    # Register error-aware callback
    reload_manager.register_reload_callback("skills", error_aware_callback)
    
    print("🛡️  Error handling example setup")
    print("   ℹ️  Try creating files with 'broken', 'syntax', or 'permission' in the name")
    
    await reload_manager.start()
    reload_manager.add_watch_path("app/skills")
    
    try:
        await asyncio.sleep(15)  # Monitor for 15 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await reload_manager.stop()
    
    print()


async def performance_monitoring_example():
    """Example of monitoring hot reload performance."""

    print("=== Performance Monitoring Example ===")

    reload_manager = HotReloadManager()
    
    # Performance tracking callback
    reload_times = []
    
    async def performance_callback(file_path: str, change_type: str):
        import time
        start_time = time.time()
        
        try:
            # Simulate reload work
            component_name = Path(file_path).stem
            await asyncio.sleep(0.1)  # Simulate reload time
            
            duration = time.time() - start_time
            reload_times.append(duration)
            
            print(f"⚡ Reloaded {component_name} in {duration:.3f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ Failed to reload {component_name} in {duration:.3f}s: {e}")
    
    reload_manager.register_reload_callback("skills", performance_callback)
    
    await reload_manager.start()
    reload_manager.add_watch_path("app/skills")
    
    print("📊 Performance monitoring active...")
    print("   ℹ️  Modify some files to see reload performance")
    
    try:
        await asyncio.sleep(10)  # Monitor for 10 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await reload_manager.stop()
    
    # Show performance statistics
    if reload_times:
        avg_time = sum(reload_times) / len(reload_times)
        min_time = min(reload_times)
        max_time = max(reload_times)
        
        print(f"\n📈 Performance Statistics:")
        print(f"   Reloads: {len(reload_times)}")
        print(f"   Average time: {avg_time:.3f}s")
        print(f"   Fastest: {min_time:.3f}s")
        print(f"   Slowest: {max_time:.3f}s")
    else:
        print("   No reloads occurred during monitoring")
    
    print()


async def global_reload_manager_example():
    """Example using the global hot reload manager instance."""

    print("=== Global Reload Manager Example ===")

    # Use the global hot_reload_manager instance
    print("🌐 Using global hot reload manager...")
    
    # Simple callback
    async def global_callback(file_path: str, change_type: str):
        component_name = Path(file_path).stem
        print(f"🔄 Global reload: {component_name} ({change_type})")
    
    # Register with global manager
    hot_reload_manager.register_reload_callback("all", global_callback)
    
    # Start global monitoring
    await hot_reload_manager.start()
    hot_reload_manager.add_watch_path("app/skills")
    
    print("✅ Global hot reload monitoring active")
    
    try:
        await asyncio.sleep(10)  # Monitor for 10 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await hot_reload_manager.stop()
    
    print()


async def selective_reload_example():
    """Example of selective reloading based on file patterns."""

    print("=== Selective Reload Example ===")

    reload_manager = HotReloadManager()
    
    # Selective reload callback that filters by file patterns
    async def selective_callback(file_path: str, change_type: str):
        file_path_obj = Path(file_path)
        
        # Only reload certain files
        if file_path_obj.name.startswith("test_"):
            print(f"⏭️  Skipping test file: {file_path_obj.name}")
            return
        
        if file_path_obj.suffix != ".py":
            print(f"⏭️  Skipping non-Python file: {file_path_obj.name}")
            return
        
        if "generated" in str(file_path_obj):
            print(f"🤖 Auto-generated file reload: {file_path_obj.name}")
        else:
            print(f"👤 Manual file reload: {file_path_obj.name}")
        
        # Perform actual reload
        component_name = file_path_obj.stem
        print(f"   ✅ Reloaded {component_name}")
    
    reload_manager.register_reload_callback("skills", selective_callback)
    
    await reload_manager.start()
    reload_manager.add_watch_path("app/skills")
    
    print("🎯 Selective reload monitoring (excludes test files)")
    
    try:
        await asyncio.sleep(15)  # Monitor for 15 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await reload_manager.stop()
    
    print()


async def dependency_aware_reload_example():
    """Example of dependency-aware reloading."""

    print("=== Dependency-Aware Reload Example ===")

    reload_manager = HotReloadManager()
    
    # Track component dependencies
    dependencies = {
        "skill_a": ["skill_b", "skill_c"],
        "skill_b": ["util_module"],
        "plugin_x": ["skill_a", "config_module"]
    }
    
    async def dependency_callback(file_path: str, change_type: str):
        component_name = Path(file_path).stem
        
        print(f"🔄 Reloading {component_name}...")
        
        # Check what depends on this component
        dependents = [
            comp for comp, deps in dependencies.items()
            if component_name in deps
        ]
        
        if dependents:
            print(f"   📋 Components that depend on {component_name}: {dependents}")
            
            # Reload dependents in order
            for dependent in dependents:
                print(f"   🔄 Cascading reload: {dependent}")
                # Perform actual dependent reload here
        else:
            print(f"   ℹ️  No dependencies to reload")
    
    reload_manager.register_reload_callback("skills", dependency_callback)
    reload_manager.register_reload_callback("plugins", dependency_callback)
    
    await reload_manager.start()
    reload_manager.add_watch_path("app/skills")
    reload_manager.add_watch_path("app/plugins")
    
    print("🕸️  Dependency-aware reload monitoring")
    print("   ℹ️  Modifying files will trigger dependent component reloads")
    
    try:
        await asyncio.sleep(20)  # Monitor for 20 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await reload_manager.stop()
    
    print()


async def run_all_examples():
    """Run all hot reload examples."""
    
    print("🚀 Starting Hot Reload Examples")
    print("=" * 50)
    
    try:
        await basic_hot_reload_example()
        await component_specific_reload_example()
        await reload_history_example()
        await error_handling_example()
        await performance_monitoring_example()
        await global_reload_manager_example()
        await selective_reload_example()
        await dependency_aware_reload_example()
        
        print("✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for common hot reload tasks
async def quick_reload_demo():
    """Quick demonstration of hot reload capabilities."""
    
    print("🎯 Quick Hot Reload Demo")
    print("-" * 30)
    
    # Simple callback
    async def demo_callback(file_path: str, change_type: str):
        print(f"🔄 File changed: {Path(file_path).name} ({change_type})")
    
    # Start monitoring
    await hot_reload_manager.start()
    hot_reload_manager.register_reload_callback("all", demo_callback)
    hot_reload_manager.add_watch_path("app/skills")
    
    print("👀 Watching app/skills for changes...")
    print("   ℹ️  Try modifying a file in that directory")
    
    try:
        await asyncio.sleep(10)  # Monitor for 10 seconds
    except KeyboardInterrupt:
        pass
    finally:
        await hot_reload_manager.stop()
    
    print("✅ Quick demo completed!")


async def setup_development_reload():
    """Set up hot reload for development environment."""
    
    print("🛠️  Setting up development hot reload...")
    
    async def dev_callback(file_path: str, change_type: str):
        print(f"🔧 Dev reload: {Path(file_path).name}")
        # Add development-specific reload logic
    
    await hot_reload_manager.start()
    hot_reload_manager.register_reload_callback("all", dev_callback)
    
    # Watch all component directories
    watch_paths = [
        "app/skills",
        "app/plugins",
        "app/mcp/servers",
        "app/core"
    ]
    
    for path in watch_paths:
        if Path(path).exists():
            hot_reload_manager.add_watch_path(path)
            print(f"   👀 Watching: {path}")
    
    print("✅ Development hot reload active!")
    return hot_reload_manager


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())