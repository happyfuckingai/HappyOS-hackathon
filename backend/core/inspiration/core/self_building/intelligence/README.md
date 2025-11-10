# Intelligence Module

## Overview

The Intelligence Module provides comprehensive audit logging, monitoring, and analytics capabilities for HappyOS's self-building system. It tracks all operations, changes, and events to ensure complete visibility into system behavior, enabling debugging, optimization, and compliance monitoring.

## Features

- **Comprehensive Audit Logging**: Complete event tracking for all system operations
- **Real-time Monitoring**: Live system event tracking and analysis
- **Event Classification**: Structured event types for different system operations
- **Performance Analytics**: Duration tracking and performance metrics
- **Error Tracking**: Detailed error logging with context and metadata
- **Export Capabilities**: JSON and CSV export functionality
- **Automated Cleanup**: Intelligent log rotation and cleanup
- **Query Interface**: Flexible event filtering and search capabilities

## Architecture

### Core Components

#### AuditLogger
The main audit logging orchestrator that manages all audit events and provides a centralized logging interface.

#### Event Types
- **COMPONENT_DISCOVERED**: When new components are found by the scanner
- **COMPONENT_REGISTERED**: When components are registered in the system
- **COMPONENT_ACTIVATED**: When components are loaded and activated
- **COMPONENT_DEACTIVATED**: When components are stopped or unloaded
- **COMPONENT_RELOADED**: When components are hot-reloaded
- **SKILL_AUTO_GENERATED**: When new skills are automatically generated
- **PLUGIN_AUTO_GENERATED**: When new plugins are automatically generated
- **MCP_SERVER_AUTO_GENERATED**: When new MCP servers are automatically generated
- **FILE_CREATED**: When new files are created by the system
- **FILE_MODIFIED**: When files are modified by the system
- **ERROR_OCCURRED**: When errors occur during operations
- **SYSTEM_STARTUP**: When the system starts up
- **SYSTEM_SHUTDOWN**: When the system shuts down

### Data Structures

#### AuditEvent
Contains comprehensive information about individual audit events:
```python
@dataclass
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    component_name: Optional[str] = None
    component_type: Optional[str] = None
    user_request: Optional[str] = None
    details: Dict[str, Any] = None
    success: bool = True
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = None
```

#### Event Metadata
Each event can contain rich metadata including:
- **Component Information**: Name, type, version, capabilities
- **Performance Data**: Execution time, resource usage, optimization metrics
- **Context Data**: User requests, system state, configuration
- **Error Details**: Stack traces, error codes, recovery actions
- **System Metrics**: Memory usage, CPU utilization, disk space

## Usage

### Basic Audit Logging

```python
from app.core.self_building.intelligence.audit_logger import audit_logger, AuditEventType

# Log system startup
await audit_logger.log_system_startup({
    "version": "1.0.0",
    "components_loaded": ["skills", "plugins", "mcp_servers"]
})

# Log component discovery
await audit_logger.log_component_discovered(
    component_name="weather_skill",
    component_type="skill",
    file_path="/app/skills/weather_skill.py"
)

# Log skill generation
await audit_logger.log_skill_auto_generated(
    skill_name="calculator",
    user_request="Create a calculator skill",
    skill_type="computational",
    file_path="/app/skills/generated/calculator.py",
    success=True,
    duration_seconds=2.5,
    llm_model="gpt-4"
)
```

### Event Querying

```python
# Get recent events
recent_events = audit_logger.get_events(limit=10)

# Get error events
error_events = audit_logger.get_events(
    event_type=AuditEventType.ERROR_OCCURRED,
    limit=5
)

# Get events for specific component
skill_events = audit_logger.get_events(
    component_type="skill",
    component_name="weather_skill"
)

# Get events since yesterday
from datetime import datetime, timedelta
yesterday = datetime.now() - timedelta(days=1)
recent_events = audit_logger.get_events(since=yesterday)
```

### Statistics and Analytics

```python
# Get comprehensive statistics
stats = audit_logger.get_audit_stats()
print(f"Total events: {stats['total_events']}")
print(f"Error rate: {stats['error_rate']:.2%}")
print(f"Events last 24h: {stats['events_last_24h']}")

# View events by type
for event_type, count in stats['events_by_type'].items():
    print(f"{event_type}: {count}")
```

### Export and Backup

```python
# Export recent logs as JSON
json_file = await audit_logger.export_audit_log(
    start_date=datetime.now() - timedelta(days=7),
    format="json"
)

# Export all logs as CSV
csv_file = await audit_logger.export_audit_log(format="csv")

# Cleanup old logs
cleaned_files = await audit_logger.cleanup_old_logs(days_to_keep=30)
```

## Configuration

### Log Directory Structure
```
logs/
├── audit/
│   ├── audit_20241008.jsonl
│   ├── audit_20241007.jsonl
│   └── audit_export_20241008_143025.json
```

### File Formats

#### JSONL Format (Default)
Each line contains a complete JSON event:
```json
{"event_id": "20241008_143025_0001", "event_type": "component_discovered", "timestamp": "2024-10-08T14:30:25.123456", "component_name": "weather_skill", "component_type": "skill", "details": {"file_path": "/app/skills/weather_skill.py"}, "success": true}
```

#### JSON Export Format
Complete array of events:
```json
[
  {
    "event_id": "20241008_143025_0001",
    "event_type": "component_discovered",
    "timestamp": "2024-10-08T14:30:25.123456",
    "component_name": "weather_skill",
    "component_type": "skill",
    "details": {
      "file_path": "/app/skills/weather_skill.py"
    },
    "success": true
  }
]
```

## Integration

### Self-Building System Integration

The Intelligence Module is deeply integrated with all self-building components:

```python
# Component Scanner Integration
from app.core.self_building.discovery.component_scanner import component_scanner
from app.core.self_building.intelligence.audit_logger import audit_logger

async def scan_with_audit():
    components = await component_scanner.scan_all_components()
    for component in components:
        await audit_logger.log_component_discovered(
            component.name,
            component.type,
            component.path
        )
```

### Skill Auto-Generator Integration

```python
# Generator Integration
from app.core.self_building.generators.skill_auto_generator import SkillAutoGenerator

async def generate_with_audit():
    generator = SkillAutoGenerator()
    
    start_time = time.time()
    try:
        skill = await generator.generate_skill(user_request)
        duration = time.time() - start_time
        
        await audit_logger.log_skill_auto_generated(
            skill_name=skill.name,
            user_request=user_request,
            skill_type=skill.type,
            file_path=skill.file_path,
            success=True,
            duration_seconds=duration
        )
    except Exception as e:
        duration = time.time() - start_time
        await audit_logger.log_skill_auto_generated(
            skill_name="unknown",
            user_request=user_request,
            skill_type="unknown",
            file_path="",
            success=False,
            error_message=str(e),
            duration_seconds=duration
        )
```

### Hot Reload Integration

```python
# Hot Reload Integration
from app.core.self_building.hot_reload.watcher import FileWatcher

async def reload_with_audit():
    async def on_file_change(file_path, change_type):
        component_name = Path(file_path).stem
        
        start_time = time.time()
        try:
            await reload_component(file_path)
            duration = time.time() - start_time
            
            await audit_logger.log_component_reloaded(
                component_name=component_name,
                component_type="skill",
                change_type=change_type,
                success=True,
                duration_seconds=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            await audit_logger.log_component_reloaded(
                component_name=component_name,
                component_type="skill",
                change_type=change_type,
                success=False,
                error_message=str(e),
                duration_seconds=duration
            )
    
    watcher = FileWatcher(on_change=on_file_change)
    await watcher.start()
```

## Performance Considerations

### Memory Management
- Events are stored in memory with configurable limits
- Automatic log rotation prevents excessive memory usage
- Cleanup utilities remove old files automatically

### File I/O Optimization
- Asynchronous file writing prevents blocking
- JSONL format enables streaming and append operations
- Batch operations for bulk exports

### Query Performance
- In-memory filtering for recent events
- Index-based lookups for common queries
- Pagination support for large result sets

## Monitoring and Alerting

### Error Rate Monitoring
```python
# Monitor error rates
stats = audit_logger.get_audit_stats()
error_rate = stats['error_rate']

if error_rate > 0.05:  # 5% error threshold
    await send_alert(f"High error rate detected: {error_rate:.2%}")
```

### Performance Monitoring
```python
# Monitor component performance
slow_components = []
events = audit_logger.get_events(limit=100)

for event in events:
    if event.duration_seconds and event.duration_seconds > 5.0:
        slow_components.append({
            'component': event.component_name,
            'duration': event.duration_seconds,
            'timestamp': event.timestamp
        })

if slow_components:
    await send_performance_alert(slow_components)
```

## Best Practices

### Event Logging
1. **Always log both success and failure cases**
2. **Include relevant context in details and metadata**
3. **Use appropriate event types for better categorization**
4. **Include timing information for performance analysis**
5. **Add user context when available**

### Error Handling
1. **Log errors with complete context**
2. **Include stack traces in details**
3. **Add recovery actions in metadata**
4. **Use structured error messages**

### Performance
1. **Use async methods for all audit operations**
2. **Batch operations when possible**
3. **Clean up old logs regularly**
4. **Monitor memory usage and file sizes**

### Security
1. **Sanitize sensitive data before logging**
2. **Use secure file permissions for log files**
3. **Consider encryption for sensitive audit data**
4. **Implement log integrity checks**

## Troubleshooting

### Common Issues

#### Permission Errors
```python
# Fallback to current directory if default path fails
try:
    self.log_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    fallback_dir = Path.cwd() / "logs_audit"
    self.log_dir = fallback_dir
    self.log_dir.mkdir(parents=True, exist_ok=True)
```

#### File Lock Issues
```python
# Use file locks for concurrent access
import fcntl

with open(log_file, 'a') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    f.write(log_entry)
```

#### Memory Issues
```python
# Limit in-memory events
MAX_MEMORY_EVENTS = 10000

if len(self.events) > MAX_MEMORY_EVENTS:
    # Keep only recent events
    self.events = self.events[-MAX_MEMORY_EVENTS//2:]
```

## Examples

See `examples.py` for comprehensive usage examples including:
- Basic audit logging
- Skill auto-generation logging
- Component reload logging
- Error logging
- Event querying
- Statistics and analytics
- Export and cleanup operations
- Custom event creation
- Monitoring integration

## API Reference

### AuditLogger Class

#### Methods
- `log_event()`: Log a generic audit event
- `log_component_discovered()`: Log component discovery
- `log_component_registered()`: Log component registration
- `log_component_activated()`: Log component activation
- `log_component_reloaded()`: Log component hot reload
- `log_skill_auto_generated()`: Log automatic skill generation
- `log_error()`: Log error events
- `log_system_startup()`: Log system startup
- `log_system_shutdown()`: Log system shutdown
- `get_events()`: Query audit events with filtering
- `get_audit_stats()`: Get comprehensive statistics
- `export_audit_log()`: Export events to file
- `cleanup_old_logs()`: Clean up old log files

#### Convenience Functions
- `log_component_discovered()`: Global function for component discovery
- `log_skill_auto_generated()`: Global function for skill generation
- `log_error()`: Global function for error logging

## Future Enhancements

### Planned Features
1. **Real-time Dashboard**: Web interface for live audit monitoring
2. **Advanced Analytics**: Machine learning-based pattern detection
3. **Alert System**: Configurable alerts for specific events
4. **External Integration**: Support for external monitoring systems
5. **Compliance Features**: Audit trail verification and signing
6. **Performance Profiling**: Detailed performance analysis tools

### Extensibility
The module is designed for easy extension with new event types, export formats, and integration points. Custom event types can be added to the `AuditEventType` enum, and new export formats can be implemented in the `export_audit_log` method.