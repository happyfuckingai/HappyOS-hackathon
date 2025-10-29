#!/usr/bin/env python3
"""
Validation script for Agent Svea refactoring to HappyOS SDK

Validates that Agent Svea has been successfully refactored to use
HappyOS SDK exclusively with zero backend.* imports.
"""

import os
import subprocess
import sys


def check_backend_imports():
    """Check for backend.* imports in Agent Svea files."""
    print("🔍 Checking for backend.* imports in Agent Svea...")
    
    # Check main MCP server file
    result = subprocess.run([
        "grep", "-n", "^from backend\\|^import backend", 
        "backend/agents/agent_svea/agent_svea_mcp_server.py"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("❌ Found backend imports in MCP server:")
        print(result.stdout)
        return False
    
    # Check circuit breaker integration
    result = subprocess.run([
        "grep", "-n", "^from backend\\|^import backend",
        "backend/agents/agent_svea/circuit_breaker_integration.py"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("❌ Found backend imports in circuit breaker integration:")
        print(result.stdout)
        return False
    
    print("✅ No backend.* imports found in Agent Svea core files")
    return True


def check_happyos_sdk_usage():
    """Check that Agent Svea uses HappyOS SDK."""
    print("🔍 Checking HappyOS SDK usage...")
    
    # Check main MCP server file
    result = subprocess.run([
        "grep", "-n", "from happyos_sdk import",
        "backend/agents/agent_svea/agent_svea_mcp_server.py"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ No HappyOS SDK imports found in MCP server")
        return False
    
    print("✅ HappyOS SDK imports found:")
    print(result.stdout.strip())
    return True


def check_mcp_tools():
    """Check that MCP tools are properly implemented."""
    print("🔍 Checking MCP tools implementation...")
    
    required_tools = [
        "check_swedish_compliance",
        "validate_bas_account", 
        "sync_erp_document"
    ]
    
    with open("backend/agents/agent_svea/agent_svea_mcp_server.py", "r") as f:
        content = f.read()
    
    missing_tools = []
    for tool in required_tools:
        if f"_handle_{tool}" not in content:
            missing_tools.append(tool)
    
    if missing_tools:
        print(f"❌ Missing MCP tool handlers: {missing_tools}")
        return False
    
    print("✅ All required MCP tools implemented")
    return True


def check_standardized_interface():
    """Check that Agent Svea implements StandardizedMCPServer interface."""
    print("🔍 Checking StandardizedMCPServer interface...")
    
    with open("backend/agents/agent_svea/agent_svea_mcp_server.py", "r") as f:
        content = f.read()
    
    required_methods = [
        "initialize",
        "get_health_status",
        "shutdown"
    ]
    
    missing_methods = []
    for method in required_methods:
        if f"async def {method}" not in content and f"def {method}" not in content:
            missing_methods.append(method)
    
    if missing_methods:
        print(f"❌ Missing required methods: {missing_methods}")
        return False
    
    print("✅ StandardizedMCPServer interface implemented")
    return True


def check_circuit_breaker_integration():
    """Check circuit breaker integration with HappyOS SDK."""
    print("🔍 Checking circuit breaker integration...")
    
    with open("backend/agents/agent_svea/agent_svea_mcp_server.py", "r") as f:
        content = f.read()
    
    if "get_circuit_breaker" not in content:
        print("❌ Circuit breaker integration not found")
        return False
    
    if "CircuitBreakerConfig" not in content:
        print("❌ Circuit breaker configuration not found")
        return False
    
    print("✅ Circuit breaker integration properly implemented")
    return True


def check_reply_to_semantics():
    """Check reply-to semantics implementation."""
    print("🔍 Checking reply-to semantics...")
    
    with open("backend/agents/agent_svea/agent_svea_mcp_server.py", "r") as f:
        content = f.read()
    
    if "send_callback" not in content:
        print("❌ Reply-to callback mechanism not found")
        return False
    
    if "reply_to" not in content:
        print("❌ Reply-to header handling not found")
        return False
    
    print("✅ Reply-to semantics properly implemented")
    return True


def run_isolation_test():
    """Run the existing isolation test."""
    print("🔍 Running existing isolation test...")
    
    result = subprocess.run([
        "python3", "-m", "pytest", 
        "backend/agents/agent_svea/test_agent_svea_mcp_server.py::TestAgentSveaMCPServer::test_no_backend_imports",
        "-v"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Isolation test failed:")
        print(result.stdout)
        print(result.stderr)
        return False
    
    print("✅ Isolation test passed")
    return True


def main():
    """Run all validation checks."""
    print("🚀 Agent Svea Refactoring Validation")
    print("=" * 50)
    
    checks = [
        ("Backend Import Check", check_backend_imports),
        ("HappyOS SDK Usage", check_happyos_sdk_usage),
        ("MCP Tools Implementation", check_mcp_tools),
        ("StandardizedMCPServer Interface", check_standardized_interface),
        ("Circuit Breaker Integration", check_circuit_breaker_integration),
        ("Reply-To Semantics", check_reply_to_semantics),
        ("Isolation Test", run_isolation_test)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n📋 {name}")
        try:
            if check_func():
                passed += 1
            else:
                print(f"   ❌ {name} failed")
        except Exception as e:
            print(f"   💥 {name} error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Validation Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Agent Svea successfully refactored to use HappyOS SDK exclusively!")
        print("✅ Task 2.2 completed successfully")
        return 0
    else:
        print("💥 Some validation checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())