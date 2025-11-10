"""
Integration tests for Self-Building MCP Server.

Tests MCP tool endpoints, authentication, and error handling.

Requirements: 1.1, 1.2, 1.3, 1.5
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


# Mock the self-building system before importing the server
class MockUltimateSelfBuildingSystem:
    """Mock self-building system for testing."""
    
    def __init__(self):
        self.running = True
        self.learning_engine = Mock()
        self.llm_code_generator = Mock()
    
    async def autonomous_improvement_cycle(
        self,
        analysis_window_hours: int = 24,
        max_improvements: int = 3,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """Mock improvement cycle."""
        return {
            "success": True,
            "cycle_id": "test_cycle_123",
            "insights_generated": 5,
            "opportunities_identified": 3,
            "improvements_executed": 2,
            "successful": 2,
            "failed": 0,
            "rolled_back": 0,
        }
    
    async def handle_generation_candidate_request(
        self,
        user_request: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Mock component generation."""
        return {
            "success": True,
            "component_name": "test_component",
            "file_path": "/tmp/test_component.py",
            "auto_generated": True,
        }
    
    async def shutdown(self):
        """Mock shutdown."""
        self.running = False


# Mock functions
mock_system = MockUltimateSelfBuildingSystem()


async def mock_get_ultimate_system_status():
    """Mock system status."""
    return {
        "system_health": "healthy",
        "active_improvements": 2,
        "evolution_level": 3,
        "components": {
            "total": 50,
            "auto_generated": 10,
            "manually_created": 40,
        },
        "uptime_seconds": 3600,
    }


async def mock_initialize_ultimate_self_building():
    """Mock initialization."""
    pass


# Patch the imports before importing the server
sys.modules['backend.core.inspiration.core.self_building.ultimate_self_building'] = Mock(
    ultimate_self_building_system=mock_system,
    initialize_ultimate_self_building=mock_initialize_ultimate_self_building,
    get_ultimate_system_status=mock_get_ultimate_system_status,
)

# Now import the server
from agents.self_building.self_building_mcp_server import app, API_KEY


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": f"Bearer {API_KEY}"}


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_success(self, client):
        """Test health check returns success."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] in ["ok", "degraded"]
        assert data["agent"] == "self-building"
        assert "version" in data
        assert "system_ready" in data
        assert "features" in data
        assert "timestamp" in data
    
    def test_health_check_features(self, client):
        """Test health check includes feature flags."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        features = data["features"]
        assert "autonomous_improvements" in features
        assert "component_generation" in features
        assert "cloudwatch_streaming" in features
        assert "improvement_rollback" in features


class TestTriggerImprovementCycle:
    """Test trigger_improvement_cycle MCP tool."""
    
    def test_trigger_improvement_cycle_success(self, client, auth_headers):
        """Test triggering improvement cycle successfully."""
        # Note: MCP tools are accessed via the /mcp endpoint
        # For testing, we'll test the underlying function directly
        from agents.self_building.self_building_mcp_server import trigger_improvement_cycle
        
        result = asyncio.run(trigger_improvement_cycle(
            analysis_window_hours=24,
            max_improvements=3,
            tenant_id=None
        ))
        
        # Parse JSON response
        data = json.loads(result)
        
        assert data["success"] is True
        assert "data" in data
        assert "timestamp" in data
    
    def test_trigger_improvement_cycle_with_tenant(self, client, auth_headers):
        """Test triggering improvement cycle with tenant_id."""
        from agents.self_building.self_building_mcp_server import trigger_improvement_cycle
        
        result = asyncio.run(trigger_improvement_cycle(
            analysis_window_hours=12,
            max_improvements=2,
            tenant_id="test_tenant"
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True
        if "data" in data:
            assert data["data"]["analysis_window_hours"] == 12
            assert data["data"]["max_improvements"] == 2
    
    def test_trigger_improvement_cycle_custom_params(self, client, auth_headers):
        """Test triggering improvement cycle with custom parameters."""
        from agents.self_building.self_building_mcp_server import trigger_improvement_cycle
        
        result = asyncio.run(trigger_improvement_cycle(
            analysis_window_hours=6,
            max_improvements=1,
            tenant_id="custom_tenant"
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True


class TestGenerateComponent:
    """Test generate_component MCP tool."""
    
    def test_generate_component_success(self, client, auth_headers):
        """Test generating component successfully."""
        from agents.self_building.self_building_mcp_server import generate_component
        
        requirements = {
            "name": "test_skill",
            "description": "A test skill for unit testing",
            "capabilities": ["test_execution", "result_validation"]
        }
        
        result = asyncio.run(generate_component(
            component_type="skill",
            requirements=requirements,
            context={"tenant_id": "test_tenant"}
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True
        if "data" in data:
            assert data["data"]["component_type"] == "skill"
            assert "component_id" in data["data"]
            assert "generated_at" in data["data"]
    
    def test_generate_component_invalid_type(self, client, auth_headers):
        """Test generating component with invalid type."""
        from agents.self_building.self_building_mcp_server import generate_component
        
        requirements = {"name": "test"}
        
        result = asyncio.run(generate_component(
            component_type="invalid_type",
            requirements=requirements
        ))
        
        data = json.loads(result)
        
        assert data["success"] is False
        assert "error" in data
        assert "Invalid component_type" in data["error"]
    
    def test_generate_component_missing_requirements(self, client, auth_headers):
        """Test generating component without requirements."""
        from agents.self_building.self_building_mcp_server import generate_component
        
        result = asyncio.run(generate_component(
            component_type="skill",
            requirements={}
        ))
        
        data = json.loads(result)
        
        assert data["success"] is False
        assert "error" in data
    
    def test_generate_component_all_types(self, client, auth_headers):
        """Test generating all valid component types."""
        from agents.self_building.self_building_mcp_server import generate_component
        
        valid_types = ["skill", "agent", "service", "plugin"]
        
        for component_type in valid_types:
            requirements = {
                "name": f"test_{component_type}",
                "description": f"Test {component_type}"
            }
            
            result = asyncio.run(generate_component(
                component_type=component_type,
                requirements=requirements
            ))
            
            data = json.loads(result)
            
            # Should succeed or fail gracefully
            assert "success" in data
            assert "timestamp" in data


class TestGetSystemStatus:
    """Test get_system_status MCP tool."""
    
    def test_get_system_status_success(self, client, auth_headers):
        """Test getting system status successfully."""
        from agents.self_building.self_building_mcp_server import get_system_status
        
        result = asyncio.run(get_system_status())
        
        data = json.loads(result)
        
        assert data["success"] is True
        assert "data" in data
        
        status = data["data"]
        assert "system_health" in status
        assert "server" in status
        assert "configuration" in status
    
    def test_get_system_status_includes_config(self, client, auth_headers):
        """Test system status includes configuration."""
        from agents.self_building.self_building_mcp_server import get_system_status
        
        result = asyncio.run(get_system_status())
        
        data = json.loads(result)
        
        assert data["success"] is True
        config = data["data"]["configuration"]
        
        assert "autonomous_improvements_enabled" in config
        assert "component_generation_enabled" in config
        assert "cloudwatch_streaming_enabled" in config
        assert "improvement_rollback_enabled" in config
    
    def test_get_system_status_includes_server_info(self, client, auth_headers):
        """Test system status includes server information."""
        from agents.self_building.self_building_mcp_server import get_system_status
        
        result = asyncio.run(get_system_status())
        
        data = json.loads(result)
        
        assert data["success"] is True
        server = data["data"]["server"]
        
        assert "host" in server
        assert "port" in server
        assert "version" in server


class TestQueryTelemetryInsights:
    """Test query_telemetry_insights MCP tool."""
    
    def test_query_telemetry_insights_success(self, client, auth_headers):
        """Test querying telemetry insights successfully."""
        from agents.self_building.self_building_mcp_server import query_telemetry_insights
        
        result = asyncio.run(query_telemetry_insights(
            metric_name="latency_ms",
            time_range_hours=1,
            tenant_id=None
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True
        assert "data" in data
        
        insights = data["data"]
        assert "query" in insights
        assert "insights" in insights
        assert "recommendations" in insights
    
    def test_query_telemetry_insights_with_metric(self, client, auth_headers):
        """Test querying specific metric insights."""
        from agents.self_building.self_building_mcp_server import query_telemetry_insights
        
        result = asyncio.run(query_telemetry_insights(
            metric_name="error_rate",
            time_range_hours=2,
            tenant_id="test_tenant"
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True
        query = data["data"]["query"]
        
        assert query["metric_name"] == "error_rate"
        assert query["time_range_hours"] == 2
    
    def test_query_telemetry_insights_no_metric(self, client, auth_headers):
        """Test querying all telemetry insights."""
        from agents.self_building.self_building_mcp_server import query_telemetry_insights
        
        result = asyncio.run(query_telemetry_insights(
            metric_name=None,
            time_range_hours=24
        ))
        
        data = json.loads(result)
        
        assert data["success"] is True


class TestAuthentication:
    """Test authentication and error handling."""
    
    def test_health_no_auth_required(self, client):
        """Test health endpoint doesn't require authentication."""
        response = client.get("/health")
        
        assert response.status_code == 200
    
    def test_invalid_api_key(self, client):
        """Test request with invalid API key."""
        # Note: MCP tools don't use HTTP auth directly in FastMCP
        # This test verifies the auth mechanism exists
        from agents.self_building.self_building_mcp_server import verify_api_key
        from fastapi.security import HTTPAuthorizationCredentials
        
        # Test with invalid credentials
        invalid_creds = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_key"
        )
        
        with pytest.raises(Exception):
            asyncio.run(verify_api_key(invalid_creds))
    
    def test_missing_api_key(self, client):
        """Test request without API key."""
        from agents.self_building.self_building_mcp_server import verify_api_key
        
        # Test with no credentials
        with pytest.raises(Exception):
            asyncio.run(verify_api_key(None))


class TestErrorHandling:
    """Test error handling in MCP tools."""
    
    def test_trigger_improvement_cycle_error(self, client, auth_headers):
        """Test error handling in improvement cycle."""
        from agents.self_building.self_building_mcp_server import trigger_improvement_cycle
        
        # Mock system to raise error
        with patch('agents.self_building.self_building_mcp_server.ultimate_self_building_system', None):
            result = asyncio.run(trigger_improvement_cycle())
            
            data = json.loads(result)
            
            assert data["success"] is False
            assert "error" in data
    
    def test_generate_component_error(self, client, auth_headers):
        """Test error handling in component generation."""
        from agents.self_building.self_building_mcp_server import generate_component
        
        # Test with empty requirements
        result = asyncio.run(generate_component(
            component_type="skill",
            requirements={}
        ))
        
        data = json.loads(result)
        
        assert data["success"] is False
        assert "error" in data
    
    def test_get_system_status_error(self, client, auth_headers):
        """Test error handling in system status."""
        from agents.self_building.self_building_mcp_server import get_system_status
        
        # Mock system to be None
        with patch('agents.self_building.self_building_mcp_server.ultimate_self_building_system', None):
            result = asyncio.run(get_system_status())
            
            data = json.loads(result)
            
            assert data["success"] is False
            assert "error" in data


def test_json_serialization():
    """Test JSON serialization helper."""
    from agents.self_building.self_building_mcp_server import _json_default
    
    # Test datetime serialization
    dt = datetime.now()
    result = _json_default(dt)
    assert isinstance(result, str)
    assert "T" in result  # ISO format
    
    # Test other object serialization
    obj = {"key": "value"}
    result = _json_default(obj)
    assert isinstance(result, str)


def test_format_tool_response():
    """Test tool response formatting."""
    from agents.self_building.self_building_mcp_server import _format_tool_response
    
    # Test success response
    result = _format_tool_response(True, data={"test": "data"})
    data = json.loads(result)
    
    assert data["success"] is True
    assert data["data"] == {"test": "data"}
    assert "timestamp" in data
    
    # Test error response
    result = _format_tool_response(False, error="Test error")
    data = json.loads(result)
    
    assert data["success"] is False
    assert data["error"] == "Test error"
    assert "timestamp" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
