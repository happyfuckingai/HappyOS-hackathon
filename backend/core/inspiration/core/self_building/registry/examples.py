"""
Registry Examples

This module contains practical examples of how to use the Dynamic Registry
for component registration, lifecycle management, and dependency tracking.
"""

import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from app.core.self_building.registry.dynamic_registry import (
    DynamicRegistry,
    ComponentStatus,
    RegistryEntry,
    dynamic_registry
)
from app.core.self_building.discovery.component_scanner import ComponentInfo

logger = logging.getLogger(__name__)


async def basic_registry_example():
    """Basic component registration and management example."""

    print("=== Basic Registry Example ===")

    # Create registry instance
    registry = DynamicRegistry()
    
    # Create some sample components
    components = [
        ComponentInfo(
            name="calculator_skill",
            type="skill",
            path="app/skills/calculator_skill.py",
            module_name="calculator_skill",
            last_modified=datetime.now()
        ),
        ComponentInfo(
            name="weather_plugin",
            type="plugin",
            path="app/plugins/weather_plugin.py",
            module_name="weather_plugin",
            last_modified=datetime.now()
        ),
        ComponentInfo(
            name="file_server",
            type="mcp_server",
            path="app/mcp/servers/file_server.py",
            module_name="file_server",
            last_modified=datetime.now()
        )
    ]
    
    print("📋 Registering components...")
    
    # Register components
    for component in components:
        entry_id = await registry.register_component(component)
        print(f"   ✅ Registered {component.name} ({component.type}) -> {entry_id}")
    
    # List all registered components
    all_components = registry.list_components()
    print(f"\n📊 Registry status: {len(all_components)} components")
    
    for comp_id, entry in all_components.items():
        print(f"   - {comp_id}: {entry.component.name} ({entry.status.value})")
    
    print()


async def component_lifecycle_example():
    """Example of managing component lifecycle states."""

    print("=== Component Lifecycle Example ===")

    registry = DynamicRegistry()
    
    # Create a test component
    component = ComponentInfo(
        name="lifecycle_test",
        type="skill",
        path="app/skills/lifecycle_test.py",
        module_name="lifecycle_test",
        last_modified=datetime.now()
    )
    
    # Register component
    comp_id = await registry.register_component(component)
    print(f"📋 Registered component: {comp_id}")
    
    # Check initial status
    entry = registry.get_component(comp_id)
    print(f"   Initial status: {entry.status.value}")
    
    # Activate component
    print("🚀 Activating component...")
    success = await registry.activate_component(comp_id)
    if success:
        entry = registry.get_component(comp_id)
        print(f"   Status after activation: {entry.status.value}")
    
    # Deactivate component
    print("⏸️  Deactivating component...")
    await registry.deactivate_component(comp_id)
    entry = registry.get_component(comp_id)
    print(f"   Status after deactivation: {entry.status.value}")
    
    # Mark as error state
    print("❌ Marking component with error...")
    await registry.mark_component_error(comp_id, "Test error condition")
    entry = registry.get_component(comp_id)
    print(f"   Status after error: {entry.status.value}")
    print(f"   Error history: {entry.error_history}")
    
    # Unregister component
    print("🗑️  Unregistering component...")
    await registry.unregister_component(comp_id)
    
    # Verify removal
    entry = registry.get_component(comp_id)
    print(f"   Component exists after unregister: {entry is not None}")
    
    print()


async def dependency_management_example():
    """Example of managing component dependencies."""

    print("=== Dependency Management Example ===")

    registry = DynamicRegistry()
    
    # Create components with dependencies
    base_skill = ComponentInfo(
        name="base_skill",
        type="skill",
        path="app/skills/base_skill.py",
        module_name="base_skill",
        last_modified=datetime.now()
    )
    
    dependent_skill = ComponentInfo(
        name="dependent_skill",
        type="skill",
        path="app/skills/dependent_skill.py",
        module_name="dependent_skill",
        last_modified=datetime.now()
    )
    
    plugin_component = ComponentInfo(
        name="helper_plugin",
        type="plugin",
        path="app/plugins/helper_plugin.py",
        module_name="helper_plugin",
        last_modified=datetime.now()
    )
    
    # Register components
    base_id = await registry.register_component(base_skill)
    dependent_id = await registry.register_component(dependent_skill)
    plugin_id = await registry.register_component(plugin_component)
    
    print(f"📋 Registered components:")
    print(f"   Base: {base_id}")
    print(f"   Dependent: {dependent_id}")
    print(f"   Plugin: {plugin_id}")
    
    # Add dependencies
    print("🔗 Adding dependencies...")
    await registry.add_dependency(dependent_id, base_id)
    await registry.add_dependency(plugin_id, base_id)
    
    # Show dependency information
    base_entry = registry.get_component(base_id)
    dependent_entry = registry.get_component(dependent_id)
    plugin_entry = registry.get_component(plugin_id)
    
    print(f"\n📊 Dependency information:")
    print(f"   {base_id} dependents: {list(base_entry.dependents)}")
    print(f"   {dependent_id} dependencies: {list(dependent_entry.dependencies)}")
    print(f"   {plugin_id} dependencies: {list(plugin_entry.dependencies)}")
    
    # Get dependency chain
    dependents = registry.get_dependents(base_id)
    print(f"\n🕸️  Components that depend on {base_id}: {dependents}")
    
    dependencies = registry.get_dependencies(dependent_id)
    print(f"   {dependent_id} depends on: {dependencies}")
    
    print()


async def component_filtering_example():
    """Example of filtering and querying components."""

    print("=== Component Filtering Example ===")

    registry = DynamicRegistry()
    
    # Register various components
    components = [
        ("skill_a", "skill", ComponentStatus.ACTIVE),
        ("skill_b", "skill", ComponentStatus.INACTIVE),
        ("plugin_x", "plugin", ComponentStatus.ACTIVE),
        ("plugin_y", "plugin", ComponentStatus.ERROR),
        ("server_1", "mcp_server", ComponentStatus.ACTIVE),
        ("server_2", "mcp_server", ComponentStatus.REGISTERED)
    ]
    
    component_ids = {}
    for name, comp_type, status in components:
        component = ComponentInfo(
            name=name,
            type=comp_type,
            path=f"app/{comp_type}s/{name}.py",
            module_name=name,
            last_modified=datetime.now()
        )
        comp_id = await registry.register_component(component)
        component_ids[name] = comp_id
        
        # Set desired status
        if status == ComponentStatus.ACTIVE:
            await registry.activate_component(comp_id)
        elif status == ComponentStatus.ERROR:
            await registry.mark_component_error(comp_id, "Test error")
    
    print("📋 Registered test components")
    
    # Filter by type
    skills = registry.get_components_by_type("skill")
    plugins = registry.get_components_by_type("plugin")
    servers = registry.get_components_by_type("mcp_server")
    
    print(f"\n🎯 Components by type:")
    print(f"   Skills: {len(skills)} - {list(skills.keys())}")
    print(f"   Plugins: {len(plugins)} - {list(plugins.keys())}")
    print(f"   MCP Servers: {len(servers)} - {list(servers.keys())}")
    
    # Filter by status
    active_components = registry.get_components_by_status(ComponentStatus.ACTIVE)
    error_components = registry.get_components_by_status(ComponentStatus.ERROR)
    
    print(f"\n📊 Components by status:")
    print(f"   Active: {len(active_components)} components")
    print(f"   Error: {len(error_components)} components")
    
    # Get healthy components
    healthy_components = registry.get_healthy_components()
    print(f"   Healthy: {len(healthy_components)} components")
    
    print()


async def component_access_tracking_example():
    """Example of tracking component access and usage."""

    print("=== Component Access Tracking Example ===")

    registry = DynamicRegistry()
    
    # Register a test component
    component = ComponentInfo(
        name="tracked_skill",
        type="skill",
        path="app/skills/tracked_skill.py",
        module_name="tracked_skill",
        last_modified=datetime.now()
    )
    
    comp_id = await registry.register_component(component)
    await registry.activate_component(comp_id)
    
    print(f"📋 Registered tracked component: {comp_id}")
    
    # Simulate component access
    print("📊 Simulating component access...")
    for i in range(5):
        instance = await registry.get_component_instance(comp_id)
        print(f"   Access {i+1}: Got instance {instance is not None}")
        await asyncio.sleep(0.1)  # Small delay between accesses
    
    # Get access statistics
    entry = registry.get_component(comp_id)
    print(f"\n📈 Access statistics:")
    print(f"   Access count: {entry.access_count}")
    print(f"   Last accessed: {entry.last_accessed}")
    print(f"   Registration time: {entry.registered_at}")
    
    # Get usage stats
    usage_stats = registry.get_usage_stats()
    print(f"\n📊 Overall usage statistics:")
    print(f"   Total components: {usage_stats['total_components']}")
    print(f"   Active components: {usage_stats['active_components']}")
    print(f"   Total accesses: {usage_stats['total_accesses']}")
    print(f"   Most accessed: {usage_stats.get('most_accessed', 'N/A')}")
    
    print()


async def global_registry_example():
    """Example using the global registry instance."""

    print("=== Global Registry Example ===")

    # Use the global dynamic_registry instance
    print("🌐 Using global dynamic registry...")
    
    # Register component using global instance
    component = ComponentInfo(
        name="global_test",
        type="skill",
        path="app/skills/global_test.py",
        module_name="global_test",
        last_modified=datetime.now()
    )
    
    comp_id = await dynamic_registry.register_component(component)
    print(f"✅ Registered with global registry: {comp_id}")
    
    # Activate component
    await dynamic_registry.activate_component(comp_id)
    print(f"🚀 Activated component")
    
    # Get component status
    entry = dynamic_registry.get_component(comp_id)
    print(f"📊 Component status: {entry.status.value}")
    
    # List all components in global registry
    all_components = dynamic_registry.list_components()
    print(f"📋 Global registry has {len(all_components)} components")
    
    print()


async def error_handling_example():
    """Example of error handling in registry operations."""

    print("=== Error Handling Example ===")

    registry = DynamicRegistry()
    
    # Test various error scenarios
    print("🚨 Testing error scenarios...")
    
    # Try to get non-existent component
    print("   Testing non-existent component access...")
    entry = registry.get_component("non_existent_id")
    print(f"   Non-existent component result: {entry}")
    
    # Try to activate non-existent component
    print("   Testing non-existent component activation...")
    try:
        success = await registry.activate_component("non_existent_id")
        print(f"   Activation result: {success}")
    except Exception as e:
        print(f"   Activation error: {type(e).__name__}: {e}")
    
    # Register component with error
    print("   Testing component with initialization error...")
    error_component = ComponentInfo(
        name="error_component",
        type="skill",
        path="app/skills/error_component.py",
        module_name="error_component",
        last_modified=datetime.now(),
        error="Simulated initialization error"
    )
    
    comp_id = await registry.register_component(error_component)
    print(f"   Error component registered: {comp_id}")
    
    # Try to activate error component
    success = await registry.activate_component(comp_id)
    print(f"   Error component activation: {success}")
    
    entry = registry.get_component(comp_id)
    print(f"   Error component status: {entry.status.value}")
    
    print()


async def performance_monitoring_example():
    """Example of monitoring registry performance."""

    print("=== Performance Monitoring Example ===")

    registry = DynamicRegistry()
    
    # Register multiple components to test performance
    print("⚡ Performance testing with multiple components...")
    
    import time
    
    # Measure registration performance
    start_time = time.time()
    component_ids = []
    
    for i in range(100):
        component = ComponentInfo(
            name=f"perf_test_{i}",
            type="skill",
            path=f"app/skills/perf_test_{i}.py",
            module_name=f"perf_test_{i}",
            last_modified=datetime.now()
        )
        comp_id = await registry.register_component(component)
        component_ids.append(comp_id)
    
    registration_time = time.time() - start_time
    print(f"   Registration: 100 components in {registration_time:.3f}s")
    print(f"   Rate: {100/registration_time:.1f} components/second")
    
    # Measure activation performance
    start_time = time.time()
    activation_count = 0
    
    for comp_id in component_ids[:50]:  # Activate first 50
        success = await registry.activate_component(comp_id)
        if success:
            activation_count += 1
    
    activation_time = time.time() - start_time
    print(f"   Activation: {activation_count} components in {activation_time:.3f}s")
    print(f"   Rate: {activation_count/activation_time:.1f} activations/second")
    
    # Measure query performance
    start_time = time.time()
    
    for _ in range(1000):  # 1000 queries
        all_components = registry.list_components()
        active_components = registry.get_components_by_status(ComponentStatus.ACTIVE)
        skills = registry.get_components_by_type("skill")
    
    query_time = time.time() - start_time
    print(f"   Queries: 3000 queries in {query_time:.3f}s")
    print(f"   Rate: {3000/query_time:.1f} queries/second")
    
    print()


async def advanced_dependency_example():
    """Example of advanced dependency management scenarios."""

    print("=== Advanced Dependency Example ===")

    registry = DynamicRegistry()
    
    # Create a more complex dependency graph
    components = {}
    
    # Base components (no dependencies)
    for name in ["base_util", "config_manager", "logger"]:
        component = ComponentInfo(
            name=name,
            type="skill",
            path=f"app/skills/{name}.py",
            module_name=name,
            last_modified=datetime.now()
        )
        comp_id = await registry.register_component(component)
        components[name] = comp_id
    
    # Mid-level components (depend on base)
    for name in ["data_processor", "api_client"]:
        component = ComponentInfo(
            name=name,
            type="skill",
            path=f"app/skills/{name}.py",
            module_name=name,
            last_modified=datetime.now()
        )
        comp_id = await registry.register_component(component)
        components[name] = comp_id
        
        # Add dependencies to base components
        await registry.add_dependency(comp_id, components["base_util"])
        await registry.add_dependency(comp_id, components["logger"])
    
    # High-level components (depend on mid-level)
    high_level_component = ComponentInfo(
        name="complex_skill",
        type="skill",
        path="app/skills/complex_skill.py",
        module_name="complex_skill",
        last_modified=datetime.now()
    )
    complex_id = await registry.register_component(high_level_component)
    components["complex_skill"] = complex_id
    
    # Add dependencies to mid-level components
    await registry.add_dependency(complex_id, components["data_processor"])
    await registry.add_dependency(complex_id, components["api_client"])
    await registry.add_dependency(complex_id, components["config_manager"])
    
    print("🕸️  Created complex dependency graph")
    
    # Analyze dependency graph
    print("\\n📊 Dependency analysis:")
    for name, comp_id in components.items():
        entry = registry.get_component(comp_id)
        deps = list(entry.dependencies)
        dependents = list(entry.dependents)
        
        print(f"   {name}:")
        print(f"     Dependencies: {len(deps)} - {deps}")
        print(f"     Dependents: {len(dependents)} - {dependents}")
    
    # Test circular dependency detection
    print("\\n🔄 Testing circular dependency detection...")
    try:
        # Try to create circular dependency
        await registry.add_dependency(components["base_util"], components["complex_skill"])
        print("   ❌ Circular dependency was allowed (this should not happen)")
    except Exception as e:
        print(f"   ✅ Circular dependency prevented: {type(e).__name__}")
    
    print()


async def run_all_examples():
    """Run all registry examples."""
    
    print("🚀 Starting Dynamic Registry Examples")
    print("=" * 55)
    
    try:
        await basic_registry_example()
        await component_lifecycle_example()
        await dependency_management_example()
        await component_filtering_example()
        await component_access_tracking_example()
        await global_registry_example()
        await error_handling_example()
        await performance_monitoring_example()
        await advanced_dependency_example()
        
        print("✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for common registry operations
async def quick_registry_demo():
    """Quick demonstration of registry capabilities."""
    
    print("🎯 Quick Registry Demo")
    print("-" * 25)
    
    # Register a component using global registry
    component = ComponentInfo(
        name="demo_skill",
        type="skill",
        path="app/skills/demo_skill.py",
        module_name="demo_skill",
        last_modified=datetime.now()
    )
    
    comp_id = await dynamic_registry.register_component(component)
    print(f"📋 Registered: {comp_id}")
    
    # Activate component
    await dynamic_registry.activate_component(comp_id)
    print(f"🚀 Activated: {comp_id}")
    
    # Show status
    entry = dynamic_registry.get_component(comp_id)
    print(f"📊 Status: {entry.status.value}")
    
    # Get registry stats
    all_components = dynamic_registry.list_components()
    print(f"📈 Total components in registry: {len(all_components)}")
    
    print("✅ Quick demo completed!")


async def register_and_activate_component(component_info: ComponentInfo) -> str:
    """Register and activate a component in one operation."""
    
    # Register component
    comp_id = await dynamic_registry.register_component(component_info)
    print(f"📋 Registered: {component_info.name} -> {comp_id}")
    
    # Activate component
    success = await dynamic_registry.activate_component(comp_id)
    if success:
        print(f"🚀 Activated: {component_info.name}")
    else:
        print(f"❌ Failed to activate: {component_info.name}")
    
    return comp_id


async def get_registry_health_report():
    """Get a comprehensive health report of the registry."""
    
    all_components = dynamic_registry.list_components()
    
    # Count by status
    status_counts = {}
    for entry in all_components.values():
        status = entry.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Count by type
    type_counts = {}
    for entry in all_components.values():
        comp_type = entry.component.type
        type_counts[comp_type] = type_counts.get(comp_type, 0) + 1
    
    # Get usage stats
    usage_stats = dynamic_registry.get_usage_stats()
    
    print("🏥 Registry Health Report")
    print("-" * 30)
    print(f"Total components: {len(all_components)}")
    print(f"By status: {status_counts}")
    print(f"By type: {type_counts}")
    print(f"Total accesses: {usage_stats.get('total_accesses', 0)}")
    print(f"Active components: {usage_stats.get('active_components', 0)}")
    
    return {
        "total_components": len(all_components),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "usage_stats": usage_stats
    }


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())