"""
Discovery Examples

This module contains practical examples of how to use the Component Discovery
system for automatic component scanning, registration, and hot-reload monitoring.
"""

import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from app.core.self_building.discovery.component_scanner import (
    ComponentScanner,
    ComponentInfo,
    component_scanner
)

logger = logging.getLogger(__name__)


async def basic_component_scanning_example():
    """Basic component scanning example."""

    print("=== Basic Component Scanning Example ===")

    # Create a scanner instance
    scanner = ComponentScanner(base_path=".")
    
    # Scan for all components
    print("🔍 Scanning for components...")
    components = await scanner.scan_all_components()
    
    print(f"✅ Found {len(components)} components:")
    
    # Group by type
    by_type = {}
    for component in components:
        if component.type not in by_type:
            by_type[component.type] = []
        by_type[component.type].append(component)
    
    for comp_type, comps in by_type.items():
        print(f"  📦 {comp_type}: {len(comps)} components")
        for comp in comps[:3]:  # Show first 3
            print(f"    - {comp.name} ({comp.path})")
        if len(comps) > 3:
            print(f"    ... and {len(comps) - 3} more")

    print()


async def skill_discovery_example():
    """Example of discovering skills specifically."""

    print("=== Skill Discovery Example ===")

    scanner = ComponentScanner()
    
    # Scan only for skills
    print("🎯 Scanning for skills...")
    skills = await scanner.scan_skills()
    
    print(f"🔧 Found {len(skills)} skills:")
    for skill in skills:
        print(f"  - {skill.name}")
        print(f"    Path: {skill.path}")
        print(f"    Module: {skill.module_name}")
        print(f"    Registered: {skill.registered}")
        print(f"    Last Modified: {skill.last_modified}")
        if skill.error:
            print(f"    ❌ Error: {skill.error}")
        if skill.metadata:
            print(f"    📋 Metadata: {skill.metadata}")
        print()

    print()


async def plugin_discovery_example():
    """Example of discovering plugins specifically."""

    print("=== Plugin Discovery Example ===")

    scanner = ComponentScanner()
    
    # Scan only for plugins
    print("🔌 Scanning for plugins...")
    plugins = await scanner.scan_plugins()
    
    print(f"🔧 Found {len(plugins)} plugins:")
    for plugin in plugins:
        print(f"  - {plugin.name}")
        print(f"    Path: {plugin.path}")
        print(f"    Module: {plugin.module_name}")
        print(f"    Registered: {plugin.registered}")
        if plugin.error:
            print(f"    ❌ Error: {plugin.error}")
        print()

    print()


async def mcp_server_discovery_example():
    """Example of discovering MCP servers specifically."""

    print("=== MCP Server Discovery Example ===")

    scanner = ComponentScanner()
    
    # Scan only for MCP servers
    print("🌐 Scanning for MCP servers...")
    mcp_servers = await scanner.scan_mcp_servers()
    
    print(f"🔧 Found {len(mcp_servers)} MCP servers:")
    for server in mcp_servers:
        print(f"  - {server.name}")
        print(f"    Path: {server.path}")
        print(f"    Module: {server.module_name}")
        print(f"    Registered: {server.registered}")
        if server.error:
            print(f"    ❌ Error: {server.error}")
        print()

    print()


async def component_registration_example():
    """Example of registering discovered components."""

    print("=== Component Registration Example ===")

    scanner = ComponentScanner()
    
    # Scan components
    components = await scanner.scan_all_components()
    
    # Register components that aren't already registered
    registered_count = 0
    for component in components:
        if not component.registered and not component.error:
            try:
                success = await scanner.register_component(component)
                if success:
                    registered_count += 1
                    print(f"✅ Registered {component.name} ({component.type})")
                else:
                    print(f"❌ Failed to register {component.name}")
            except Exception as e:
                print(f"❌ Error registering {component.name}: {e}")
    
    print(f"\n📊 Registered {registered_count} new components")
    print()


async def component_metadata_example():
    """Example of extracting component metadata."""

    print("=== Component Metadata Example ===")

    scanner = ComponentScanner()
    
    # Scan components with metadata extraction
    components = await scanner.scan_all_components()
    
    print("📋 Component Metadata:")
    for component in components[:5]:  # Show first 5
        print(f"\n🔧 {component.name} ({component.type})")
        print(f"   Path: {component.path}")
        print(f"   Module: {component.module_name}")
        
        if component.metadata:
            print("   Metadata:")
            for key, value in component.metadata.items():
                print(f"     {key}: {value}")
        else:
            print("   No metadata available")
    
    print()


async def component_status_monitoring_example():
    """Example of monitoring component status."""

    print("=== Component Status Monitoring Example ===")

    scanner = ComponentScanner()
    
    # Get component status
    components = await scanner.scan_all_components()
    
    # Categorize components
    healthy = [c for c in components if not c.error and c.registered]
    errored = [c for c in components if c.error]
    unregistered = [c for c in components if not c.error and not c.registered]
    
    print("📊 Component Status Summary:")
    print(f"  ✅ Healthy: {len(healthy)} components")
    print(f"  ❌ Errored: {len(errored)} components")
    print(f"  ⏳ Unregistered: {len(unregistered)} components")
    
    if errored:
        print("\n❌ Components with errors:")
        for component in errored:
            print(f"  - {component.name}: {component.error}")
    
    if unregistered:
        print("\n⏳ Unregistered components:")
        for component in unregistered[:5]:  # Show first 5
            print(f"  - {component.name} ({component.type})")
    
    print()


async def file_system_monitoring_example():
    """Example of monitoring file system changes."""

    print("=== File System Monitoring Example ===")

    scanner = ComponentScanner()
    
    # Check for recently modified components
    components = await scanner.scan_all_components()
    
    # Find recently modified components (last 24 hours)
    from datetime import timedelta
    recent_threshold = datetime.now() - timedelta(hours=24)
    
    recent_changes = [
        c for c in components 
        if c.last_modified > recent_threshold
    ]
    
    print(f"📅 Components modified in last 24 hours: {len(recent_changes)}")
    for component in recent_changes:
        print(f"  - {component.name} ({component.type})")
        print(f"    Modified: {component.last_modified}")
        print(f"    Path: {component.path}")
    
    print()


async def custom_scan_paths_example():
    """Example of using custom scan paths."""

    print("=== Custom Scan Paths Example ===")

    # Create scanner with custom paths
    custom_scanner = ComponentScanner(base_path="/home/mr/happyos")
    
    # Override default scan paths
    custom_scanner.scan_paths = {
        "skills": [
            Path("/home/mr/happyos/app/skills"),
            Path("/home/mr/happyos/app/skills/generated"),
            Path("/home/mr/happyos/custom_skills")  # Custom path
        ],
        "plugins": [
            Path("/home/mr/happyos/app/plugins"),
            Path("/home/mr/happyos/external_plugins")  # Custom path
        ],
        "mcp_servers": [
            Path("/home/mr/happyos/app/mcp/servers")
        ]
    }
    
    print("🔍 Scanning with custom paths...")
    try:
        components = await custom_scanner.scan_all_components()
        print(f"✅ Found {len(components)} components in custom paths")
        
        # Show scan paths used
        print("\n📁 Scan paths used:")
        for comp_type, paths in custom_scanner.scan_paths.items():
            print(f"  {comp_type}:")
            for path in paths:
                exists = path.exists()
                print(f"    - {path} {'✅' if exists else '❌'}")
    
    except Exception as e:
        print(f"❌ Custom scan failed: {e}")
    
    print()


async def component_filtering_example():
    """Example of filtering discovered components."""

    print("=== Component Filtering Example ===")

    scanner = ComponentScanner()
    components = await scanner.scan_all_components()
    
    # Filter by type
    skills = [c for c in components if c.type == "skill"]
    plugins = [c for c in components if c.type == "plugin"]
    
    print(f"🎯 Filtered results:")
    print(f"  Skills: {len(skills)}")
    print(f"  Plugins: {len(plugins)}")
    
    # Filter by registration status
    registered = [c for c in components if c.registered]
    unregistered = [c for c in components if not c.registered]
    
    print(f"\n📋 Registration status:")
    print(f"  Registered: {len(registered)}")
    print(f"  Unregistered: {len(unregistered)}")
    
    # Filter by health status
    healthy = [c for c in components if not c.error]
    errored = [c for c in components if c.error]
    
    print(f"\n🏥 Health status:")
    print(f"  Healthy: {len(healthy)}")
    print(f"  With errors: {len(errored)}")
    
    # Filter by name pattern
    test_components = [c for c in components if "test" in c.name.lower()]
    print(f"\n🧪 Test components: {len(test_components)}")
    
    print()


async def global_scanner_example():
    """Example using the global component scanner instance."""

    print("=== Global Scanner Example ===")

    # Use the global component_scanner instance
    print("🌐 Using global component scanner...")
    
    # Scan all components
    components = await component_scanner.scan_all_components()
    print(f"✅ Found {len(components)} components via global scanner")
    
    # Get specific component types
    skills = await component_scanner.scan_skills()
    plugins = await component_scanner.scan_plugins()
    mcp_servers = await component_scanner.scan_mcp_servers()
    
    print(f"📊 Component breakdown:")
    print(f"  Skills: {len(skills)}")
    print(f"  Plugins: {len(plugins)}")
    print(f"  MCP Servers: {len(mcp_servers)}")
    
    print()


async def component_dependency_example():
    """Example of analyzing component dependencies."""

    print("=== Component Dependency Analysis Example ===")

    scanner = ComponentScanner()
    components = await scanner.scan_all_components()
    
    print("🔗 Analyzing component dependencies...")
    
    # Simple dependency analysis based on imports
    dependencies = {}
    
    for component in components:
        if component.metadata and "imports" in component.metadata:
            deps = component.metadata["imports"]
            dependencies[component.name] = deps
    
    print(f"📊 Dependency analysis for {len(dependencies)} components:")
    for comp_name, deps in dependencies.items():
        if deps:
            print(f"  {comp_name}:")
            for dep in deps[:3]:  # Show first 3 dependencies
                print(f"    - {dep}")
            if len(deps) > 3:
                print(f"    ... and {len(deps) - 3} more")
    
    print()


async def performance_monitoring_example():
    """Example of monitoring component discovery performance."""

    print("=== Performance Monitoring Example ===")

    import time
    
    scanner = ComponentScanner()
    
    # Measure scan performance
    start_time = time.time()
    components = await scanner.scan_all_components()
    scan_duration = time.time() - start_time
    
    print(f"⏱️  Scan Performance:")
    print(f"  Total components: {len(components)}")
    print(f"  Scan duration: {scan_duration:.2f} seconds")
    print(f"  Components per second: {len(components) / scan_duration:.1f}")
    
    # Measure individual type scans
    type_performance = {}
    
    for scan_type in ["skills", "plugins", "mcp_servers"]:
        start_time = time.time()
        if scan_type == "skills":
            comps = await scanner.scan_skills()
        elif scan_type == "plugins":
            comps = await scanner.scan_plugins()
        else:
            comps = await scanner.scan_mcp_servers()
        duration = time.time() - start_time
        
        type_performance[scan_type] = {
            "count": len(comps),
            "duration": duration
        }
    
    print(f"\n📊 Performance by type:")
    for scan_type, perf in type_performance.items():
        print(f"  {scan_type}: {perf['count']} components in {perf['duration']:.2f}s")
    
    print()


async def run_all_examples():
    """Run all component discovery examples."""
    
    print("🚀 Starting Component Discovery Examples")
    print("=" * 60)
    
    try:
        await basic_component_scanning_example()
        await skill_discovery_example()
        await plugin_discovery_example()
        await mcp_server_discovery_example()
        await component_registration_example()
        await component_metadata_example()
        await component_status_monitoring_example()
        await file_system_monitoring_example()
        await custom_scan_paths_example()
        await component_filtering_example()
        await global_scanner_example()
        await component_dependency_example()
        await performance_monitoring_example()
        
        print("✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for quick component discovery
async def quick_scan_demo():
    """Quick demonstration of component discovery capabilities."""
    
    print("🎯 Quick Component Discovery Demo")
    print("-" * 40)
    
    # Quick scan using global scanner
    components = await component_scanner.scan_all_components()
    
    # Show summary
    by_type = {}
    for comp in components:
        by_type[comp.type] = by_type.get(comp.type, 0) + 1
    
    print(f"📊 Discovered components:")
    for comp_type, count in by_type.items():
        print(f"  {comp_type}: {count}")
    
    # Show health status
    healthy = len([c for c in components if not c.error])
    errored = len([c for c in components if c.error])
    
    print(f"🏥 Health status:")
    print(f"  Healthy: {healthy}")
    print(f"  With errors: {errored}")
    
    print("✅ Quick demo completed!")


async def discover_and_register_all():
    """Discover and register all components in one operation."""
    
    print("🔄 Discover and Register All Components")
    print("-" * 45)
    
    # Scan all components
    components = await component_scanner.scan_all_components()
    print(f"🔍 Discovered {len(components)} components")
    
    # Register unregistered components
    registered = 0
    failed = 0
    
    for component in components:
        if not component.registered and not component.error:
            try:
                success = await component_scanner.register_component(component)
                if success:
                    registered += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to register {component.name}: {e}")
                failed += 1
    
    print(f"📊 Registration results:")
    print(f"  Successfully registered: {registered}")
    print(f"  Failed to register: {failed}")
    print(f"  Already registered: {len([c for c in components if c.registered])}")
    
    print("✅ Discovery and registration completed!")


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())