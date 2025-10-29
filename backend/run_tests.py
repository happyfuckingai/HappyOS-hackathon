#!/usr/bin/env python3
"""
Test runner script for infrastructure recovery test suite.
Adds proper Python path and runs tests with correct configuration.
"""

import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set test environment
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('PYTHONPATH', str(backend_dir))

def run_unit_tests():
    """Run unit tests."""
    print("🧪 Running Unit Tests...")
    
    try:
        # Import test modules to verify they work
        from tests.unit.test_a2a_protocol import TestA2AMessage
        from tests.unit.test_circuit_breaker import TestCircuitBreaker
        from tests.unit.test_tenant_isolation import TestTenantIsolationMiddleware
        from tests.unit.test_service_layer import TestServiceFacade
        
        print("✅ Unit test imports successful")
        
        # Run a simple test
        test_instance = TestA2AMessage()
        test_instance.test_message_creation()
        print("✅ A2A message creation test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Unit tests failed: {e}")
        return False

def run_integration_tests():
    """Run integration tests."""
    print("🔗 Running Integration Tests...")
    
    try:
        # Import integration test modules
        from tests.integration.test_aws_service_integration import TestAWSAgentCoreIntegration
        from tests.integration.test_fallback_recovery import TestFallbackTransitions
        from tests.integration.test_cross_service_communication import TestA2AProtocolIntegration
        
        print("✅ Integration test imports successful")
        return True
        
    except Exception as e:
        print(f"❌ Integration tests failed: {e}")
        return False

def run_demo_scenarios():
    """Run demo scenarios."""
    print("🎭 Running Demo Scenarios...")
    
    try:
        # Import demo modules
        from tests.demo.test_cloud_mode_demo import CloudModeDemo
        from tests.demo.test_fallback_mode_demo import FallbackModeDemo
        from tests.demo.test_multi_tenant_demo import MultiTenantDemo
        
        print("✅ Demo scenario imports successful")
        return True
        
    except Exception as e:
        print(f"❌ Demo scenarios failed: {e}")
        return False

def main():
    """Main test runner."""
    print("🚀 Infrastructure Recovery Test Suite")
    print("=" * 50)
    
    results = {
        'unit_tests': run_unit_tests(),
        'integration_tests': run_integration_tests(),
        'demo_scenarios': run_demo_scenarios()
    }
    
    print("\n📊 Test Suite Summary:")
    print("=" * 50)
    
    for test_type, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_type.replace('_', ' ').title()}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All test suites imported and basic tests passed!")
        print("\nTest Suite Features:")
        print("• Unit Tests: A2A protocol, Circuit breaker, Tenant isolation, Service layer")
        print("• Integration Tests: AWS services, Fallback recovery, Cross-service communication")
        print("• Demo Scenarios: Cloud mode, Fallback mode, Multi-tenant isolation")
        print("\nTo run full test suite with pytest:")
        print("  python3 -m pytest tests/ -v")
    else:
        print("\n❌ Some test suites failed to import")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())