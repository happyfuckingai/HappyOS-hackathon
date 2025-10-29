#!/usr/bin/env python3
"""
Simple validation script for MCP Security Implementation

This script validates the MCP security components without requiring
full backend infrastructure dependencies.
"""

import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mcp_headers():
    """Test MCP headers functionality"""
    print("Testing MCP Headers...")
    
    try:
        from modules.auth.mcp_tenant_isolation import MCPHeaders
        
        # Create headers
        headers = MCPHeaders(
            tenant_id="test_tenant",
            trace_id=str(uuid4()),
            conversation_id=str(uuid4()),
            caller="test_agent",
            reply_to="mcp://meetmind/ingest_result"
        )
        
        # Test to_dict conversion
        header_dict = headers.to_dict()
        assert "X-MCP-Tenant-ID" in header_dict
        assert header_dict["X-MCP-Tenant-ID"] == "test_tenant"
        
        # Test from_dict conversion
        reconstructed = MCPHeaders.from_dict(header_dict)
        assert reconstructed.tenant_id == headers.tenant_id
        assert reconstructed.caller == headers.caller
        
        print("✓ MCP Headers validation passed")
        return True
        
    except Exception as e:
        print(f"✗ MCP Headers validation failed: {e}")
        return False

def test_mcp_signing():
    """Test MCP signing functionality"""
    print("Testing MCP Signing...")
    
    try:
        from modules.auth.mcp_security import MCPSigningService
        from modules.auth.mcp_tenant_isolation import MCPHeaders
        
        # Create signing service
        signing_service = MCPSigningService()
        
        # Create headers
        headers = MCPHeaders(
            tenant_id="test_tenant",
            trace_id=str(uuid4()),
            conversation_id=str(uuid4()),
            caller="agent_svea"
        )
        
        # Sign headers
        signed_headers = signing_service.sign_mcp_headers(headers, "agent_svea")
        assert signed_headers.auth_sig is not None
        assert signed_headers.timestamp is not None
        
        # Verify signature
        is_valid = signing_service.verify_mcp_signature(signed_headers)
        assert is_valid
        
        print("✓ MCP Signing validation passed")
        return True
        
    except Exception as e:
        print(f"✗ MCP Signing validation failed: {e}")
        return False

def test_mcp_tenant_isolation():
    """Test MCP tenant isolation functionality"""
    print("Testing MCP Tenant Isolation...")
    
    try:
        from modules.auth.mcp_tenant_isolation import MCPTenantIsolationService, MCPHeaders
        
        # Create tenant service
        tenant_service = MCPTenantIsolationService()
        
        # Create valid headers
        headers = MCPHeaders(
            tenant_id="agentsvea",
            trace_id=str(uuid4()),
            conversation_id=str(uuid4()),
            caller="agent_svea"
        )
        
        # Test valid access
        try:
            tenant_service.validate_mcp_access(headers, "agent_svea", "check_compliance")
            print("✓ Valid access allowed")
        except Exception as e:
            print(f"✗ Valid access should be allowed: {e}")
            return False
        
        # Test invalid agent access
        headers.caller = "unknown_agent"
        try:
            tenant_service.validate_mcp_access(headers, "agent_svea", "check_compliance")
            print("✗ Invalid access should be denied")
            return False
        except Exception:
            print("✓ Invalid access correctly denied")
        
        print("✓ MCP Tenant Isolation validation passed")
        return True
        
    except Exception as e:
        print(f"✗ MCP Tenant Isolation validation failed: {e}")
        return False

def test_mcp_audit_logging():
    """Test MCP audit logging functionality"""
    print("Testing MCP Audit Logging...")
    
    try:
        from modules.auth.mcp_audit_logging import MCPAuditLogger, MCPEventType
        from modules.auth.mcp_tenant_isolation import MCPHeaders
        
        # Create audit logger
        audit_logger = MCPAuditLogger()
        
        # Create headers
        headers = MCPHeaders(
            tenant_id="test_tenant",
            trace_id=str(uuid4()),
            conversation_id=str(uuid4()),
            caller="test_agent"
        )
        
        # Log tool call
        audit_logger.log_mcp_tool_call(
            headers=headers,
            target_agent="agent_svea",
            tool_name="check_compliance",
            arguments={"test": "data"},
            success=True,
            response_time_ms=150.5
        )
        
        # Get audit events
        events = audit_logger.get_mcp_audit_events(tenant_id="test_tenant")
        assert len(events) > 0
        
        event = events[0]
        assert event.event_type == MCPEventType.TOOL_CALL
        assert event.tenant_id == "test_tenant"
        assert event.success
        
        print("✓ MCP Audit Logging validation passed")
        return True
        
    except Exception as e:
        print(f"✗ MCP Audit Logging validation failed: {e}")
        return False

def test_workflow_audit():
    """Test workflow audit functionality"""
    print("Testing Workflow Audit...")
    
    try:
        from modules.auth.mcp_audit_logging import MCPAuditLogger
        
        # Create audit logger
        audit_logger = MCPAuditLogger()
        
        workflow_id = str(uuid4())
        
        # Start workflow audit
        audit_logger.start_workflow_audit_trail(
            workflow_id=workflow_id,
            workflow_type="compliance_check",
            tenant_id="test_tenant",
            initiator_agent="communications_agent",
            participating_agents=["agent_svea", "felicias_finance", "meetmind"]
        )
        
        # Get workflow trail
        trail = audit_logger.get_workflow_audit_trail(workflow_id)
        assert trail is not None
        assert trail.workflow_id == workflow_id
        assert trail.status == "running"
        
        # Complete workflow
        audit_logger.complete_workflow_audit_trail(
            workflow_id=workflow_id,
            success=True,
            performance_summary={"total_time_ms": 1500}
        )
        
        # Check completion
        trail = audit_logger.get_workflow_audit_trail(workflow_id)
        assert trail.status == "completed"
        assert trail.end_time is not None
        
        print("✓ Workflow Audit validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Workflow Audit validation failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("=== MCP Security Implementation Validation ===\n")
    
    tests = [
        test_mcp_headers,
        test_mcp_signing,
        test_mcp_tenant_isolation,
        test_mcp_audit_logging,
        test_workflow_audit
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=== Validation Summary ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All MCP Security components validated successfully!")
        return 0
    else:
        print("✗ Some MCP Security components failed validation")
        return 1

if __name__ == "__main__":
    sys.exit(main())