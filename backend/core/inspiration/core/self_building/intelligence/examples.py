"""
Intelligence Examples

This module contains practical examples of how to use the Intelligence components
for audit logging, system monitoring, and self-building operations tracking.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.core.self_building.intelligence.audit_logger import (
    audit_logger,
    AuditEventType,
    AuditEvent,
    log_component_discovered,
    log_skill_auto_generated,
    log_error
)

logger = logging.getLogger(__name__)


async def basic_audit_logging_example():
    """Basic audit logging example for system events."""

    print("=== Basic Audit Logging Example ===")

    # Log system startup
    await audit_logger.log_system_startup({
        "version": "1.0.0",
        "startup_time": datetime.now().isoformat(),
        "components_loaded": ["skills", "plugins", "mcp_servers"],
        "config_path": "./config/dynamic_config.json"
    })
    print("✅ System startup logged")

    # Log component discovery
    await audit_logger.log_component_discovered(
        component_name="example_skill",
        component_type="skill",
        file_path="/app/skills/example_skill.py"
    )
    print("✅ Component discovery logged")

    # Log component registration
    await audit_logger.log_component_registered(
        component_name="example_skill",
        component_type="skill",
        success=True
    )
    print("✅ Component registration logged")

    # Log component activation with timing
    await audit_logger.log_component_activated(
        component_name="example_skill",
        component_type="skill",
        duration_seconds=0.125
    )
    print("✅ Component activation logged")

    print()


async def skill_auto_generation_logging_example():
    """Example of logging automatic skill generation."""

    print("=== Skill Auto-Generation Logging Example ===")

    # Log successful skill generation
    await audit_logger.log_skill_auto_generated(
        skill_name="weather_checker",
        user_request="Create a skill to check the weather",
        skill_type="api_integration",
        file_path="/app/skills/generated/weather_checker.py",
        success=True,
        duration_seconds=2.35,
        llm_model="gpt-4"
    )
    print("✅ Successful skill generation logged")

    # Log failed skill generation
    await audit_logger.log_skill_auto_generated(
        skill_name="complex_calculator",
        user_request="Create a quantum physics calculator",
        skill_type="computational",
        file_path="/app/skills/generated/complex_calculator.py",
        success=False,
        error_message="Unable to generate quantum physics calculations due to complexity",
        duration_seconds=5.2,
        llm_model="gpt-4"
    )
    print("✅ Failed skill generation logged")

    print()


async def component_reload_logging_example():
    """Example of logging component hot reload events."""

    print("=== Component Reload Logging Example ===")

    # Log successful hot reload
    await audit_logger.log_component_reloaded(
        component_name="data_processor",
        component_type="skill",
        change_type="code_update",
        success=True,
        duration_seconds=0.08
    )
    print("✅ Successful hot reload logged")

    # Log failed hot reload
    await audit_logger.log_component_reloaded(
        component_name="broken_component",
        component_type="plugin",
        change_type="dependency_update",
        success=False,
        error_message="Import error: missing dependency 'numpy'",
        duration_seconds=0.15
    )
    print("✅ Failed hot reload logged")

    print()


async def error_logging_example():
    """Example of logging system errors."""

    print("=== Error Logging Example ===")

    # Log general system error
    await audit_logger.log_error(
        error_message="Database connection timeout",
        component_name="database_manager",
        component_type="system",
        details={
            "connection_string": "postgresql://localhost:5432/happyos",
            "timeout_seconds": 30,
            "retry_attempts": 3
        }
    )
    print("✅ System error logged")

    # Log skill execution error
    await audit_logger.log_error(
        error_message="Skill execution failed: invalid input format",
        component_name="json_parser",
        component_type="skill",
        details={
            "input_data": "malformed_json_string",
            "expected_format": "valid JSON object",
            "user_request": "Parse this JSON data"
        }
    )
    print("✅ Skill execution error logged")

    print()


async def audit_event_querying_example():
    """Example of querying audit events."""

    print("=== Audit Event Querying Example ===")

    # Get recent events
    recent_events = audit_logger.get_events(limit=10)
    print(f"📊 Found {len(recent_events)} recent events")

    # Get events by type
    error_events = audit_logger.get_events(
        event_type=AuditEventType.ERROR_OCCURRED,
        limit=5
    )
    print(f"❌ Found {len(error_events)} error events")

    # Get events for specific component
    skill_events = audit_logger.get_events(
        component_type="skill",
        limit=10
    )
    print(f"🔧 Found {len(skill_events)} skill-related events")

    # Get events since yesterday
    yesterday = datetime.now() - timedelta(days=1)
    recent_events = audit_logger.get_events(
        since=yesterday,
        limit=50
    )
    print(f"📅 Found {len(recent_events)} events since yesterday")

    # Show event details
    if recent_events:
        latest_event = recent_events[0]
        print(f"\n🔍 Latest event details:")
        print(f"   ID: {latest_event.event_id}")
        print(f"   Type: {latest_event.event_type.value}")
        print(f"   Component: {latest_event.component_name}")
        print(f"   Success: {latest_event.success}")
        print(f"   Timestamp: {latest_event.timestamp}")
        if latest_event.details:
            print(f"   Details: {latest_event.details}")

    print()


async def audit_statistics_example():
    """Example of getting audit statistics."""

    print("=== Audit Statistics Example ===")

    # Get comprehensive statistics
    stats = audit_logger.get_audit_stats()
    
    print(f"📈 Audit Statistics:")
    print(f"   Total events: {stats['total_events']}")
    print(f"   Events last 24h: {stats['events_last_24h']}")
    print(f"   Error count: {stats['errors_count']}")
    print(f"   Error rate: {stats['error_rate']:.2%}")
    
    if stats['last_event']:
        print(f"   Last event: {stats['last_event']}")
    
    print(f"\n📊 Events by type:")
    for event_type, count in stats['events_by_type'].items():
        print(f"   {event_type}: {count}")
    
    if stats['recent_errors']:
        print(f"\n❌ Recent errors:")
        for error in stats['recent_errors']:
            print(f"   {error['timestamp']}: {error['error']} ({error['component']})")

    print()


async def audit_export_example():
    """Example of exporting audit logs."""

    print("=== Audit Export Example ===")

    try:
        # Export last 24 hours as JSON
        start_date = datetime.now() - timedelta(days=1)
        json_file = await audit_logger.export_audit_log(
            start_date=start_date,
            format="json"
        )
        print(f"📄 Exported audit log to JSON: {json_file}")

        # Export all events as CSV
        csv_file = await audit_logger.export_audit_log(
            format="csv"
        )
        print(f"📊 Exported audit log to CSV: {csv_file}")

    except Exception as e:
        print(f"❌ Export failed: {e}")

    print()


async def audit_cleanup_example():
    """Example of cleaning up old audit logs."""

    print("=== Audit Cleanup Example ===")

    try:
        # Clean up logs older than 30 days
        cleaned_count = await audit_logger.cleanup_old_logs(days_to_keep=30)
        print(f"🧹 Cleaned up {cleaned_count} old audit log files")

        # Clean up logs older than 7 days (more aggressive)
        cleaned_count = await audit_logger.cleanup_old_logs(days_to_keep=7)
        print(f"🧹 Cleaned up {cleaned_count} additional old audit log files")

    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

    print()


async def custom_audit_event_example():
    """Example of creating custom audit events."""

    print("=== Custom Audit Event Example ===")

    # Log custom system optimization event
    event_id = await audit_logger.log_event(
        event_type=AuditEventType.SYSTEM_STARTUP,  # Reusing existing type
        component_name="optimization_engine",
        component_type="system",
        details={
            "optimization_type": "memory_cleanup",
            "memory_freed_mb": 128,
            "cpu_usage_before": 75.5,
            "cpu_usage_after": 45.2,
            "optimization_strategy": "garbage_collection"
        },
        success=True,
        duration_seconds=1.23,
        metadata={
            "trigger": "automatic",
            "threshold_reached": True,
            "performance_improvement": "30%"
        }
    )
    print(f"✅ Custom optimization event logged: {event_id}")

    # Log custom user interaction event
    event_id = await audit_logger.log_event(
        event_type=AuditEventType.COMPONENT_ACTIVATED,  # Reusing existing type
        component_name="chat_interface",
        component_type="frontend",
        user_request="Help me create a to-do list application",
        details={
            "interface_type": "chat",
            "user_id": "user_123",
            "session_id": "sess_456",
            "request_complexity": "medium"
        },
        success=True,
        metadata={
            "user_experience_level": "beginner",
            "preferred_language": "python",
            "project_type": "web_app"
        }
    )
    print(f"✅ Custom user interaction event logged: {event_id}")

    print()


async def monitoring_integration_example():
    """Example of integrating audit logging with monitoring systems."""

    print("=== Monitoring Integration Example ===")

    # Simulate a monitoring check
    def check_system_health():
        """Simulate system health check."""
        return {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "active_connections": 42,
            "healthy": True
        }

    # Perform health check and log results
    health_data = check_system_health()
    
    event_id = await audit_logger.log_event(
        event_type=AuditEventType.SYSTEM_STARTUP,  # Reusing for monitoring
        component_name="health_monitor",
        component_type="monitoring",
        details=health_data,
        success=health_data.get("healthy", False),
        metadata={
            "check_type": "system_health",
            "automated": True,
            "alert_level": "info" if health_data.get("healthy") else "warning"
        }
    )
    
    print(f"🏥 System health check logged: {event_id}")
    print(f"   Status: {'Healthy' if health_data.get('healthy') else 'Issues detected'}")
    print(f"   CPU: {health_data.get('cpu_usage')}%")
    print(f"   Memory: {health_data.get('memory_usage')}%")
    print(f"   Disk: {health_data.get('disk_usage')}%")

    print()


async def run_all_examples():
    """Run all audit logging examples."""
    
    print("🚀 Starting Intelligence Audit Logging Examples")
    print("=" * 60)
    
    try:
        await basic_audit_logging_example()
        await skill_auto_generation_logging_example()
        await component_reload_logging_example()
        await error_logging_example()
        await audit_event_querying_example()
        await audit_statistics_example()
        await audit_export_example()
        await audit_cleanup_example()
        await custom_audit_event_example()
        await monitoring_integration_example()
        
        print("✅ All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for common use cases
async def quick_audit_demo():
    """Quick demonstration of audit logging capabilities."""
    
    print("🎯 Quick Audit Demo")
    print("-" * 30)
    
    # Log a simple event
    await log_component_discovered("demo_component", "skill", "/app/skills/demo.py")
    
    # Log an error
    await log_error("Demo error for testing", "demo_component")
    
    # Show recent events
    events = audit_logger.get_events(limit=5)
    print(f"📊 Recent events: {len(events)}")
    
    # Show statistics
    stats = audit_logger.get_audit_stats()
    print(f"📈 Total events: {stats['total_events']}")
    
    print("✅ Quick demo completed!")


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())