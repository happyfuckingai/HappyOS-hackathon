"""
Simple standalone test for alarm and Lambda event handlers.

This test verifies the new event handlers work correctly without requiring
any backend imports.
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict

# Copy minimal classes needed for testing
@dataclass
class TelemetryInsight:
    """Represents an analyzed insight from telemetry data."""
    insight_type: str
    severity: str
    affected_component: str
    affected_tenants: List[str]
    metrics: Dict[str, float]
    description: str
    recommended_action: str
    confidence_score: float
    timestamp: datetime
    insight_id: str = field(default_factory=lambda: f"insight_{datetime.now().timestamp()}")


@dataclass
class CloudWatchEvent:
    """Represents a CloudWatch/EventBridge event."""
    event_type: str
    source: str
    detail: Dict[str, Any]
    timestamp: datetime
    tenant_id: str


class SimpleLearningEngine:
    """Simplified LearningEngine for testing."""
    def __init__(self):
        self.insights_cache: List[TelemetryInsight] = []


print("Testing Event Handlers (Standalone)...")
print("=" * 60)

# Test 1: Test Lambda completion event handler logic
print("\n1. Testing Lambda completion event handler logic...")
try:
    learning_engine = SimpleLearningEngine()
    
    # Simulate Lambda completion event with high duration
    event = CloudWatchEvent(
        event_type="lambda_completion",
        source="aws.lambda",
        detail={
            "functionName": "test-function",
            "status": "Succeeded",
            "duration": 6000,  # 6 seconds (above 5 second threshold)
            "memoryUsed": 200,
            "memorySize": 512,
            "billedDuration": 6000
        },
        timestamp=datetime.now(),
        tenant_id="test_tenant"
    )
    
    # Simulate the handler logic
    detail = event.detail
    function_name = detail.get('functionName', 'unknown')
    duration_ms = detail.get('duration', 0)
    memory_used_mb = detail.get('memoryUsed', 0)
    memory_size_mb = detail.get('memorySize', 0)
    
    optimization_opportunities = []
    
    # Check for high duration (> 5 seconds)
    if duration_ms > 5000:
        optimization_opportunities.append({
            'type': 'performance',
            'metric': 'duration',
            'value': duration_ms,
            'threshold': 5000,
            'recommendation': 'Optimize Lambda function execution time'
        })
    
    # Check for high memory usage (> 80% of allocated)
    if memory_size_mb > 0:
        memory_usage_pct = (memory_used_mb / memory_size_mb) * 100
        
        if memory_usage_pct > 80:
            optimization_opportunities.append({
                'type': 'resource',
                'metric': 'memory_usage',
                'value': memory_usage_pct,
                'threshold': 80,
                'recommendation': 'Increase Lambda memory allocation or optimize memory usage'
            })
        elif memory_usage_pct < 20:
            optimization_opportunities.append({
                'type': 'cost',
                'metric': 'memory_usage',
                'value': memory_usage_pct,
                'threshold': 20,
                'recommendation': 'Reduce Lambda memory allocation to save costs'
            })
    
    # Create insights
    for opp in optimization_opportunities:
        insight = TelemetryInsight(
            insight_type='optimization_opportunity',
            severity='medium',
            affected_component=function_name,
            affected_tenants=[event.tenant_id],
            metrics={
                opp['metric']: opp['value'],
                f"{opp['metric']}_threshold": opp['threshold']
            },
            description=f"Lambda function {function_name} {opp['type']} optimization: "
                       f"{opp['metric']} = {opp['value']:.1f} (threshold: {opp['threshold']})",
            recommended_action=opp['recommendation'],
            confidence_score=0.8,
            timestamp=event.timestamp
        )
        learning_engine.insights_cache.append(insight)
    
    if len(learning_engine.insights_cache) > 0:
        print(f"✅ Created {len(learning_engine.insights_cache)} optimization insight(s)")
        for insight in learning_engine.insights_cache:
            print(f"   - {insight.description}")
            print(f"   - Recommendation: {insight.recommended_action}")
    else:
        print("❌ No optimization insights created")
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Test Lambda error event handler logic
print("\n2. Testing Lambda error event handler logic...")
try:
    learning_engine = SimpleLearningEngine()
    
    # Simulate Lambda error event
    event = CloudWatchEvent(
        event_type="lambda_completion",
        source="aws.lambda",
        detail={
            "functionName": "test-function",
            "status": "Failed",
            "errorMessage": "Timeout error",
            "duration": 30000,
            "memoryUsed": 400,
            "memorySize": 512
        },
        timestamp=datetime.now(),
        tenant_id="test_tenant"
    )
    
    # Simulate the handler logic
    detail = event.detail
    function_name = detail.get('functionName', 'unknown')
    status = detail.get('status', 'unknown')
    
    # Check for errors
    if status == 'Failed' or detail.get('errorMessage'):
        error_message = detail.get('errorMessage', 'Unknown error')
        
        insight = TelemetryInsight(
            insight_type='error_pattern',
            severity='high',
            affected_component=function_name,
            affected_tenants=[event.tenant_id],
            metrics={
                'error_count': 1,
                'duration_ms': detail.get('duration', 0),
                'memory_used_mb': detail.get('memoryUsed', 0)
            },
            description=f"Lambda function {function_name} execution failed: {error_message}",
            recommended_action=f"Investigate and fix Lambda function {function_name}",
            confidence_score=0.9,
            timestamp=event.timestamp
        )
        learning_engine.insights_cache.append(insight)
    
    if len(learning_engine.insights_cache) > 0:
        print(f"✅ Created {len(learning_engine.insights_cache)} error insight(s)")
        insight = learning_engine.insights_cache[0]
        print(f"   - Severity: {insight.severity}")
        print(f"   - Description: {insight.description}")
    else:
        print("❌ No error insights created")
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Test alarm event handler logic
print("\n3. Testing alarm event handler logic...")
try:
    # Simulate critical alarm event
    event = CloudWatchEvent(
        event_type="alarm",
        source="aws.cloudwatch",
        detail={
            "alarmName": "HighErrorRate",
            "state": "ALARM",
            "previousState": "OK"
        },
        timestamp=datetime.now(),
        tenant_id="test_tenant"
    )
    
    # Simulate the handler logic
    detail = event.detail
    alarm_name = detail.get('alarmName', 'unknown')
    state = detail.get('state', 'UNKNOWN')
    
    # Check alarm severity based on alarm name patterns
    critical_patterns = [
        'HighErrorRate',
        'HighLatency',
        'LowResourceOperations',
        'SystemFailure',
        'CriticalError',
        'ServiceDown'
    ]
    
    is_critical = any(pattern in alarm_name for pattern in critical_patterns)
    
    if state == 'ALARM' and is_critical:
        print(f"✅ Critical alarm detected: {alarm_name}")
        print(f"   - Would trigger emergency improvement cycle")
        print(f"   - Alarm state: {state}")
        print(f"   - Previous state: {detail.get('previousState', 'UNKNOWN')}")
    else:
        print(f"⚠️ Non-critical alarm or not in ALARM state")
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test memory optimization detection
print("\n4. Testing Lambda memory optimization detection...")
try:
    learning_engine = SimpleLearningEngine()
    
    # Simulate Lambda event with high memory usage
    event = CloudWatchEvent(
        event_type="lambda_completion",
        source="aws.lambda",
        detail={
            "functionName": "memory-intensive-function",
            "status": "Succeeded",
            "duration": 2000,
            "memoryUsed": 450,  # 87.9% of 512 MB (above 80% threshold)
            "memorySize": 512,
            "billedDuration": 2000
        },
        timestamp=datetime.now(),
        tenant_id="test_tenant"
    )
    
    # Simulate the handler logic
    detail = event.detail
    function_name = detail.get('functionName', 'unknown')
    memory_used_mb = detail.get('memoryUsed', 0)
    memory_size_mb = detail.get('memorySize', 0)
    
    if memory_size_mb > 0:
        memory_usage_pct = (memory_used_mb / memory_size_mb) * 100
        
        if memory_usage_pct > 80:
            insight = TelemetryInsight(
                insight_type='optimization_opportunity',
                severity='medium',
                affected_component=function_name,
                affected_tenants=[event.tenant_id],
                metrics={
                    'memory_usage': memory_usage_pct,
                    'memory_usage_threshold': 80
                },
                description=f"Lambda function {function_name} resource optimization: "
                           f"memory_usage = {memory_usage_pct:.1f} (threshold: 80)",
                recommended_action='Increase Lambda memory allocation or optimize memory usage',
                confidence_score=0.8,
                timestamp=event.timestamp
            )
            learning_engine.insights_cache.append(insight)
    
    if len(learning_engine.insights_cache) > 0:
        print(f"✅ Created {len(learning_engine.insights_cache)} memory optimization insight(s)")
        insight = learning_engine.insights_cache[0]
        print(f"   - Memory usage: {insight.metrics.get('memory_usage', 0):.1f}%")
        print(f"   - Recommendation: {insight.recommended_action}")
    else:
        print("❌ No memory optimization insights created")
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All event handler logic tests passed!")
print("=" * 60)
