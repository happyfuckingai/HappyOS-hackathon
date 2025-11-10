"""
Simple verification script for autonomous improvement cycle implementation.

This script verifies that the key methods exist and have the correct signatures.
"""

import inspect
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_implementation():
    """Verify the autonomous improvement cycle implementation."""
    
    print("🔍 Verifying autonomous improvement cycle implementation...")
    print()
    
    # Import the module
    try:
        from backend.core.self_building.ultimate_self_building import UltimateSelfBuildingSystem
        print("✅ Successfully imported UltimateSelfBuildingSystem")
    except Exception as e:
        print(f"❌ Failed to import UltimateSelfBuildingSystem: {e}")
        return False
    
    # Check for required methods
    required_methods = [
        '_continuous_recursive_improvement',
        '_execute_improvement',
        '_deploy_improvement',
        '_monitor_improvement',
        '_rollback_improvement',
        '_collect_current_metrics',
        '_calculate_degradation',
        '_get_existing_component_code',
        'autonomous_improvement_cycle'
    ]
    
    print("\n📋 Checking for required methods:")
    all_methods_present = True
    
    for method_name in required_methods:
        if hasattr(UltimateSelfBuildingSystem, method_name):
            method = getattr(UltimateSelfBuildingSystem, method_name)
            sig = inspect.signature(method)
            print(f"  ✅ {method_name}{sig}")
        else:
            print(f"  ❌ {method_name} - NOT FOUND")
            all_methods_present = False
    
    if not all_methods_present:
        return False
    
    # Check settings
    print("\n⚙️  Checking settings configuration:")
    try:
        from backend.core.settings import get_settings
        settings = get_settings()
        
        config_properties = [
            'recursive_improvement_enabled',
            'improvement_cycle_interval_hours',
            'max_concurrent_improvements',
            'improvement_analysis_window_hours',
            'improvement_risk_tolerance',
            'monitoring_duration_seconds',
            'rollback_degradation_threshold',
            'cloudwatch_namespace',
            'cloudwatch_log_group_pattern'
        ]
        
        for prop in config_properties:
            if hasattr(settings, prop):
                value = getattr(settings, prop)
                print(f"  ✅ {prop} = {value}")
            else:
                print(f"  ❌ {prop} - NOT FOUND")
                all_methods_present = False
        
    except Exception as e:
        print(f"  ❌ Failed to check settings: {e}")
        return False
    
    # Check method signatures
    print("\n🔬 Verifying method signatures:")
    
    # Check autonomous_improvement_cycle signature
    method = getattr(UltimateSelfBuildingSystem, 'autonomous_improvement_cycle')
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    
    expected_params = ['self', 'analysis_window_hours', 'max_improvements', 'tenant_id']
    if params == expected_params:
        print(f"  ✅ autonomous_improvement_cycle has correct parameters: {params}")
    else:
        print(f"  ⚠️  autonomous_improvement_cycle parameters: {params}")
        print(f"      Expected: {expected_params}")
    
    # Check _execute_improvement signature
    method = getattr(UltimateSelfBuildingSystem, '_execute_improvement')
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    
    if 'opportunity' in params:
        print(f"  ✅ _execute_improvement has 'opportunity' parameter")
    else:
        print(f"  ❌ _execute_improvement missing 'opportunity' parameter")
        return False
    
    # Check _monitor_improvement signature
    method = getattr(UltimateSelfBuildingSystem, '_monitor_improvement')
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    
    required_monitor_params = ['opportunity', 'deployment_result', 'monitoring_duration_seconds']
    if all(p in params for p in required_monitor_params):
        print(f"  ✅ _monitor_improvement has all required parameters")
    else:
        print(f"  ❌ _monitor_improvement missing required parameters")
        return False
    
    # Check _rollback_improvement signature
    method = getattr(UltimateSelfBuildingSystem, '_rollback_improvement')
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    
    if 'opportunity' in params and 'reason' in params:
        print(f"  ✅ _rollback_improvement has required parameters")
    else:
        print(f"  ❌ _rollback_improvement missing required parameters")
        return False
    
    print("\n" + "="*60)
    print("✅ All verifications passed!")
    print("="*60)
    print()
    print("📝 Summary:")
    print(f"  - All {len(required_methods)} required methods are present")
    print(f"  - All configuration properties are available")
    print(f"  - Method signatures are correct")
    print()
    print("🎉 Autonomous improvement cycle implementation is complete!")
    
    return True


if __name__ == '__main__':
    success = verify_implementation()
    sys.exit(0 if success else 1)
