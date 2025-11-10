# Registry Module

## Overview

The Registry Module provides centralized component management for HappyOS's self-building system. It handles registration, lifecycle management, dependency tracking, and component orchestration, serving as the central authority for all components in the system.

## Features

- **Centralized Component Management**: Single source of truth for all system components
- **Lifecycle Management**: Complete component lifecycle from registration to deactivation
- **Dependency Tracking**: Sophisticated dependency graph management with circular detection
- **Status Monitoring**: Real-time component status tracking and health monitoring
- **Access Control**: Component access management and usage statistics
- **Performance Optimization**: Efficient component lookups and batch operations
- **Error Recovery**: Robust error handling and component recovery mechanisms
- **Usage Analytics**: Comprehensive usage statistics and performance metrics

## Architecture

### Core Components

#### DynamicRegistry
The main registry orchestrator that manages all component operations and maintains the component database.

```python
class DynamicRegistry:
    def __init__(self):
        self.entries: Dict[str, RegistryEntry] = {}
        self.type_index: Dict[str, Set[str]] = {}
        self.status_index: Dict[ComponentStatus, Set[str]] = {}
        self.dependency_graph = DependencyGraph()
```

#### ComponentStatus
Enumeration defining the possible states of a component:

```python
class ComponentStatus(Enum):
    DISCOVERED = "discovered"      # Found but not yet registered
    REGISTERED = "registered"      # Registered but not active
    ACTIVE = "active"             # Currently active and available
    INACTIVE = "inactive"         # Temporarily deactivated
    ERROR = "error"               # In error state
```

#### RegistryEntry
Data structure containing complete component information:

```python
@dataclass
class RegistryEntry:
    component: ComponentInfo
    status: ComponentStatus
    registered_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    instance: Optional[Any] = None
    error_history: List[str] = field(default_factory=list)
```

### Registry Operations

1. **Registration**: Add new components to the registry
2. **Activation**: Initialize and activate registered components
3. **Deactivation**: Safely deactivate components while preserving state
4. **Dependency Management**: Track and enforce component dependencies
5. **Status Management**: Monitor and update component status
6. **Access Tracking**: Track component usage and performance
7. **Error Handling**: Manage component errors and recovery

## Usage

### Basic Component Registration

```python
from app.core.self_building.registry.dynamic_registry import DynamicRegistry
from app.core.self_building.discovery.component_scanner import ComponentInfo

# Create registry instance
registry = DynamicRegistry()

# Create component info
component = ComponentInfo(
    name="calculator_skill",
    type="skill",
    path="app/skills/calculator_skill.py",
    module_name="calculator_skill",
    last_modified=datetime.now()
)

# Register component
component_id = await registry.register_component(component)
print(f"Registered component: {component_id}")
```

### Component Lifecycle Management

```python
# Activate component
success = await registry.activate_component(component_id)
if success:
    print("Component activated successfully")

# Check component status
entry = registry.get_component(component_id)
print(f"Component status: {entry.status.value}")

# Deactivate component
await registry.deactivate_component(component_id)

# Unregister component
await registry.unregister_component(component_id)
```

### Global Registry Instance

```python
from app.core.self_building.registry.dynamic_registry import dynamic_registry

# Use global registry instance
component_id = await dynamic_registry.register_component(component)
await dynamic_registry.activate_component(component_id)

# Get component instance
instance = await dynamic_registry.get_component_instance(component_id)
```

### Component Querying and Filtering

```python
# Get all components
all_components = registry.list_components()

# Filter by type
skills = registry.get_components_by_type("skill")
plugins = registry.get_components_by_type("plugin")

# Filter by status
active_components = registry.get_components_by_status(ComponentStatus.ACTIVE)
error_components = registry.get_components_by_status(ComponentStatus.ERROR)

# Get healthy components
healthy_components = registry.get_healthy_components()
```

## Dependency Management

### Adding Dependencies

```python
# Add dependency relationship
await registry.add_dependency(dependent_id, dependency_id)

# Add multiple dependencies
dependencies = ["base_util", "logger", "config_manager"]
for dep_id in dependencies:
    await registry.add_dependency(component_id, dep_id)
```

### Dependency Queries

```python
# Get component dependencies
dependencies = registry.get_dependencies(component_id)

# Get components that depend on this one
dependents = registry.get_dependents(component_id)

# Check for circular dependencies
has_circular = registry.has_circular_dependency(component_id, potential_dependency)
```

### Dependency Resolution

```python
# Get activation order based on dependencies
activation_order = registry.get_activation_order([comp1, comp2, comp3])

# Activate components in dependency order
for component_id in activation_order:
    await registry.activate_component(component_id)
```

## Status Management

### Component Status Tracking

```python
# Get current status
entry = registry.get_component(component_id)
current_status = entry.status

# Update status
await registry.set_component_status(component_id, ComponentStatus.ACTIVE)

# Mark component with error
await registry.mark_component_error(component_id, "Error message")

# Clear error status
await registry.clear_component_error(component_id)
```

### Status Monitoring

```python
# Monitor status changes
async def status_change_callback(component_id: str, old_status: ComponentStatus, 
                                new_status: ComponentStatus):
    print(f"Component {component_id} status changed: {old_status} -> {new_status}")

registry.register_status_callback(status_change_callback)
```

### Health Monitoring

```python
# Get registry health statistics
health_stats = registry.get_health_stats()
print(f"Healthy components: {health_stats['healthy_count']}")
print(f"Error components: {health_stats['error_count']}")
print(f"Health percentage: {health_stats['health_percentage']:.1%}")
```

## Performance Features

### Component Caching

```python
# Enable component instance caching
registry.enable_instance_caching(max_size=100, ttl=3600)

# Get cached instance (faster subsequent access)
instance = await registry.get_component_instance(component_id)
```

### Batch Operations

```python
# Register multiple components
components = [comp1, comp2, comp3]
component_ids = await registry.register_components_batch(components)

# Activate multiple components
success_count = await registry.activate_components_batch(component_ids)

# Bulk status updates
await registry.update_component_status_batch({
    comp1: ComponentStatus.ACTIVE,
    comp2: ComponentStatus.INACTIVE,
    comp3: ComponentStatus.ERROR
})
```

### Indexing and Fast Lookups

```python
# Registry automatically maintains indices for fast lookups
# Type index
skills = registry.type_index["skill"]

# Status index  
active_components = registry.status_index[ComponentStatus.ACTIVE]

# Custom indices can be added for specific use cases
registry.create_custom_index("author", lambda entry: entry.component.metadata.get("author"))
```

## Integration

### Discovery Integration

```python
from app.core.self_building.discovery.component_scanner import component_scanner

async def scan_and_register():
    # Scan for new components
    components = await component_scanner.scan_all_components()
    
    # Register discovered components
    for component in components:
        if not component.error:
            comp_id = await dynamic_registry.register_component(component)
            await dynamic_registry.activate_component(comp_id)
```

### Hot Reload Integration

```python
from app.core.self_building.hot_reload.reload_manager import hot_reload_manager

async def registry_reload_callback(file_path: str, change_type: str):
    # Find component by file path
    component_id = registry.find_component_by_path(file_path)
    
    if component_id:
        # Deactivate for reload
        await registry.deactivate_component(component_id)
        
        try:
            # Reload component
            await reload_component_module(file_path)
            
            # Reactivate component
            await registry.activate_component(component_id)
            
        except Exception as e:
            # Mark as error
            await registry.mark_component_error(component_id, str(e))

hot_reload_manager.register_reload_callback("all", registry_reload_callback)
```

### Audit Logger Integration

```python
from app.core.self_building.intelligence.audit_logger import audit_logger

async def audited_register_component(component: ComponentInfo):
    try:
        # Register component
        component_id = await registry.register_component(component)
        
        # Log successful registration
        await audit_logger.log_component_registered(
            component.name,
            component.type,
            success=True
        )
        
        return component_id
        
    except Exception as e:
        # Log failed registration
        await audit_logger.log_component_registered(
            component.name,
            component.type,
            success=False,
            error_message=str(e)
        )
        raise
```

## Error Handling

### Error Types

```python
class RegistryError(Exception):
    """Base exception for registry errors."""
    pass

class ComponentNotFoundError(RegistryError):
    """Component not found in registry."""
    pass

class DependencyError(RegistryError):
    """Dependency-related error."""
    pass

class CircularDependencyError(DependencyError):
    """Circular dependency detected."""
    pass

class ComponentActivationError(RegistryError):
    """Component activation failed."""
    pass
```

### Error Recovery

```python
async def robust_component_activation(component_id: str):
    """Activate component with error recovery."""
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            success = await registry.activate_component(component_id)
            if success:
                return True
                
        except ComponentActivationError as e:
            retry_count += 1
            logger.warning(f"Activation attempt {retry_count} failed: {e}")
            
            if retry_count < max_retries:
                # Wait before retry
                await asyncio.sleep(2 ** retry_count)
            else:
                # Mark as error after all retries
                await registry.mark_component_error(component_id, str(e))
                return False
        
        except Exception as e:
            # Immediate failure for unexpected errors
            await registry.mark_component_error(component_id, str(e))
            return False
    
    return False
```

### Dependency Validation

```python
async def validate_dependencies(component_id: str):
    """Validate all component dependencies."""
    
    dependencies = registry.get_dependencies(component_id)
    invalid_deps = []
    
    for dep_id in dependencies:
        dep_entry = registry.get_component(dep_id)
        
        if not dep_entry:
            invalid_deps.append(f"Missing dependency: {dep_id}")
        elif dep_entry.status == ComponentStatus.ERROR:
            invalid_deps.append(f"Dependency in error: {dep_id}")
        elif dep_entry.status != ComponentStatus.ACTIVE:
            invalid_deps.append(f"Dependency not active: {dep_id}")
    
    if invalid_deps:
        error_msg = "; ".join(invalid_deps)
        await registry.mark_component_error(component_id, error_msg)
        return False
    
    return True
```

## Usage Analytics

### Access Tracking

```python
# Access tracking is automatic
instance = await registry.get_component_instance(component_id)

# Get access statistics
entry = registry.get_component(component_id)
print(f"Access count: {entry.access_count}")
print(f"Last accessed: {entry.last_accessed}")
```

### Usage Statistics

```python
# Get comprehensive usage statistics
usage_stats = registry.get_usage_stats()

print(f"Total components: {usage_stats['total_components']}")
print(f"Active components: {usage_stats['active_components']}")
print(f"Total accesses: {usage_stats['total_accesses']}")
print(f"Average accesses per component: {usage_stats['avg_accesses']}")
print(f"Most accessed component: {usage_stats['most_accessed']}")
```

### Performance Metrics

```python
# Get performance metrics
performance_metrics = registry.get_performance_metrics()

print(f"Average activation time: {performance_metrics['avg_activation_time']:.3f}s")
print(f"Average lookup time: {performance_metrics['avg_lookup_time']:.3f}s")
print(f"Cache hit rate: {performance_metrics['cache_hit_rate']:.1%}")
```

## Advanced Features

### Custom Component Factories

```python
# Register custom component factory
async def custom_skill_factory(component_info: ComponentInfo):
    """Custom factory for skill components."""
    
    # Custom initialization logic
    instance = await create_skill_instance(component_info)
    
    # Custom configuration
    await configure_skill(instance, component_info.metadata)
    
    return instance

registry.register_component_factory("skill", custom_skill_factory)
```

### Component Lifecycle Hooks

```python
# Register lifecycle hooks
async def pre_activation_hook(component_id: str, entry: RegistryEntry):
    """Called before component activation."""
    print(f"Pre-activation: {component_id}")

async def post_activation_hook(component_id: str, entry: RegistryEntry):
    """Called after component activation."""
    print(f"Post-activation: {component_id}")

registry.register_lifecycle_hook("pre_activation", pre_activation_hook)
registry.register_lifecycle_hook("post_activation", post_activation_hook)
```

### Custom Indexing

```python
# Create custom indices for fast lookups
registry.create_index("author", lambda entry: entry.component.metadata.get("author"))
registry.create_index("version", lambda entry: entry.component.version)

# Use custom indices
author_components = registry.get_components_by_index("author", "HappyOS")
v1_components = registry.get_components_by_index("version", "1.0.0")
```

## Best Practices

### Registry Best Practices

1. **Use Global Instance**: Use the global registry for consistency
2. **Proper Lifecycle**: Follow proper registration -> activation -> deactivation flow
3. **Dependency Management**: Carefully manage component dependencies
4. **Error Handling**: Implement robust error handling and recovery
5. **Performance Monitoring**: Monitor registry performance and optimize

### Component Design

1. **Clear Dependencies**: Explicitly declare component dependencies
2. **Proper Cleanup**: Implement proper cleanup in component deactivation
3. **Error Resilience**: Design components to handle errors gracefully
4. **Resource Management**: Manage resources efficiently
5. **Status Reporting**: Provide clear status and health information

### Performance Optimization

1. **Efficient Lookups**: Use indexed lookups where possible
2. **Batch Operations**: Use batch operations for multiple components
3. **Caching**: Enable caching for frequently accessed components
4. **Lazy Loading**: Implement lazy loading for expensive components
5. **Resource Pooling**: Pool expensive resources when appropriate

## Monitoring and Debugging

### Registry Health

```python
# Continuous health monitoring
async def monitor_registry_health():
    while True:
        health_stats = registry.get_health_stats()
        
        if health_stats['health_percentage'] < 0.8:  # 80% threshold
            logger.warning(f"Registry health below threshold: {health_stats['health_percentage']:.1%}")
            
            # Get error components
            error_components = registry.get_components_by_status(ComponentStatus.ERROR)
            for comp_id in error_components:
                entry = registry.get_component(comp_id)
                logger.error(f"Component {comp_id} in error: {entry.error_history[-1]}")
        
        await asyncio.sleep(60)  # Check every minute
```

### Dependency Visualization

```python
# Generate dependency graph visualization
def generate_dependency_graph():
    """Generate a visualization of the component dependency graph."""
    
    graph_data = {
        "nodes": [],
        "edges": []
    }
    
    # Add nodes
    for comp_id, entry in registry.list_components().items():
        graph_data["nodes"].append({
            "id": comp_id,
            "label": entry.component.name,
            "type": entry.component.type,
            "status": entry.status.value
        })
    
    # Add edges
    for comp_id, entry in registry.list_components().items():
        for dep_id in entry.dependencies:
            graph_data["edges"].append({
                "from": dep_id,
                "to": comp_id,
                "label": "depends_on"
            })
    
    return graph_data
```

## Troubleshooting

### Common Issues

#### Component Not Found
```python
# Safe component access
def safe_get_component(component_id: str):
    try:
        return registry.get_component(component_id)
    except ComponentNotFoundError:
        logger.warning(f"Component not found: {component_id}")
        return None
```

#### Circular Dependencies
```python
# Detect and resolve circular dependencies
def detect_circular_dependencies():
    circular_deps = registry.find_circular_dependencies()
    
    if circular_deps:
        logger.error(f"Circular dependencies detected: {circular_deps}")
        # Implement resolution strategy
        for cycle in circular_deps:
            await resolve_circular_dependency(cycle)
```

#### Memory Leaks
```python
# Prevent memory leaks
async def cleanup_inactive_components():
    """Cleanup inactive components to prevent memory leaks."""
    
    inactive_components = registry.get_components_by_status(ComponentStatus.INACTIVE)
    cutoff_time = datetime.now() - timedelta(hours=1)
    
    for comp_id in inactive_components:
        entry = registry.get_component(comp_id)
        
        if (entry.last_accessed and 
            entry.last_accessed < cutoff_time):
            # Cleanup component instance
            await registry.cleanup_component_instance(comp_id)
```

## Examples

See `examples.py` for comprehensive usage examples including:
- Basic component registration
- Lifecycle management
- Dependency management
- Component filtering
- Access tracking
- Error handling
- Performance monitoring
- Advanced dependency scenarios

## API Reference

### DynamicRegistry Class

#### Core Methods
- `register_component()`: Register a new component
- `unregister_component()`: Remove component from registry
- `activate_component()`: Activate a registered component
- `deactivate_component()`: Deactivate an active component
- `get_component()`: Get component entry by ID
- `get_component_instance()`: Get component instance

#### Query Methods
- `list_components()`: Get all registered components
- `get_components_by_type()`: Filter components by type
- `get_components_by_status()`: Filter components by status
- `get_healthy_components()`: Get all healthy components

#### Dependency Methods
- `add_dependency()`: Add dependency relationship
- `remove_dependency()`: Remove dependency relationship
- `get_dependencies()`: Get component dependencies
- `get_dependents()`: Get components that depend on this one

#### Statistics Methods
- `get_usage_stats()`: Get usage statistics
- `get_health_stats()`: Get health statistics
- `get_performance_metrics()`: Get performance metrics

### Global Instance
- `dynamic_registry`: Global registry instance

## Future Enhancements

### Planned Features
1. **Distributed Registry**: Support for distributed component registry
2. **Version Management**: Component versioning and rollback support
3. **Service Discovery**: Integration with service discovery systems
4. **Load Balancing**: Automatic load balancing for component instances
5. **Resource Quotas**: Resource usage quotas and limits
6. **Advanced Analytics**: Machine learning-based component optimization

### Extensibility
The module is designed for easy extension with new component types, custom factories, lifecycle hooks, and indexing strategies. Custom registry implementations can be created by extending the base classes and implementing specific management logic.