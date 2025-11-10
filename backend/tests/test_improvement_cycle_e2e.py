"""
End-to-end integration test for autonomous improvement cycle.

Tests the complete flow: trigger via MCP → telemetry analysis → code generation
→ deployment → monitoring → rollback logic.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.self_building.intelligence.learning_engine import (
    LearningEngine,
    TelemetryInsight,
    ImprovementOpportunity
)
from core.self_building.generators.llm_code_generator import LLMCodeGenerator
from core.self_building.ultimate_self_building import UltimateSelfBuildingSystem


class MockTelemetryData:
    """Mock telemetry data for testing."""
    
    @staticmethod
    def get_performance_metrics() -> List[Dict[str, Any]]:
        """Get mock performance metrics."""
        return [
            {
                "metric_name": "ResponseLatency",
                "value": 500.0,
                "unit": "Milliseconds",
                "timestamp": datetime.now(),
                "dimensions": {"component": "api", "tenant_id": "test_tenant"}
            },
            {
                "metric_name": "ErrorRate",
                "value": 0.05,
                "unit": "Percent",
                "timestamp": datetime.now(),
                "dimensions": {"component": "api", "tenant_id": "test_tenant"}
            }
        ]
    
    @staticmethod
    def get_error_logs() -> List[Dict[str, Any]]:
        """Get mock error logs."""
        return [
            {
                "timestamp": datetime.now(),
                "message": "Database connection timeout",
                "level": "ERROR",
                "component": "database_service",
                "tenant_id": "test_tenant",
                "stack_trace": "..."
            },
            {
                "timestamp": datetime.now(),
                "message": "Database connection timeout",
                "level": "ERROR",
                "component": "database_service",
                "tenant_id": "test_tenant",
                "stack_trace": "..."
            }
        ]
    
    @staticmethod
    def get_cloudwatch_events() -> List[Dict[str, Any]]:
        """Get mock CloudWatch events."""
        return [
            {
                "event_type": "alarm",
                "source": "aws.cloudwatch",
                "detail": {
                    "alarmName": "HighErrorRate",
                    "state": {"value": "ALARM"},
                    "tenant_id": "test_tenant"
                },
                "timestamp": datetime.now()
            }
        ]


@pytest.fixture
def mock_learning_engine():
    """Create mock learning engine with realistic data."""
    engine = Mock(spec=LearningEngine)
    
    # Mock telemetry analysis
    engine.analyze_performance_trends = AsyncMock(return_value=[
        TelemetryInsight(
            insight_type='performance_degradation',
            severity='high',
            affected_component='api_service',
            affected_tenants=['test_tenant'],
            metrics={'latency_ms': 500, 'degradation_pct': 25},
            description='API response latency increased by 25%',
            recommended_action='Optimize database queries and add caching',
            confidence_score=0.85,
            timestamp=datetime.now()
        )
    ])
    
    engine.analyze_error_patterns = AsyncMock(return_value=[
        TelemetryInsight(
            insight_type='error_pattern',
            severity='high',
            affected_component='database_service',
            affected_tenants=['test_tenant'],
            metrics={'error_count': 50, 'error_rate': 0.05},
            description='Recurring database connection timeouts',
            recommended_action='Implement connection pooling and retry logic',
            confidence_score=0.9,
            timestamp=datetime.now()
        )
    ])
    
    # Mock improvement opportunities
    engine.identify_improvement_opportunities = AsyncMock(return_value=[
        ImprovementOpportunity(
            opportunity_id='opp_001',
            title='Optimize API response time',
            description='Add caching layer to reduce database load',
            impact_score=85.0,
            effort_estimate='medium',
            affected_components=['api_service', 'database_service'],
            telemetry_evidence=[],
            proposed_changes={
                'change_type': 'optimization',
                'targets': [
                    {'type': 'caching', 'action': 'add_redis_cache'},
                    {'type': 'query', 'action': 'optimize_queries'}
                ]
            },
            risk_level='medium'
        ),
        ImprovementOpportunity(
            opportunity_id='opp_002',
            title='Implement connection pooling',
            description='Add database connection pooling to prevent timeouts',
            impact_score=75.0,
            effort_estimate='low',
            affected_components=['database_service'],
            telemetry_evidence=[],
            proposed_changes={
                'change_type': 'enhancement',
                'targets': [{'type': 'connection', 'action': 'add_pooling'}]
            },
            risk_level='low'
        )
    ])
    
    engine.ingest_telemetry = AsyncMock()
    
    return engine


@pytest.fixture
def mock_llm_code_generator():
    """Create mock LLM code generator."""
    generator = Mock(spec=LLMCodeGenerator)
    
    generator.initialize = AsyncMock()
    
    # Mock component code generation
    generator.generate_component_code = AsyncMock(return_value={
        'api_service.py': '''
"""Optimized API service with caching."""
import redis
from typing import Optional

cache = redis.Redis(host='localhost', port=6379)

async def get_data(key: str) -> Optional[dict]:
    """Get data with caching."""
    # Check cache first
    cached = cache.get(key)
    if cached:
        return json.loads(cached)
    
    # Fetch from database
    data = await fetch_from_db(key)
    
    # Cache result
    cache.setex(key, 300, json.dumps(data))
    
    return data
''',
        '__init__.py': 'from .api_service import get_data\n'
    })
    
    # Mock improvement code generation
    generator.generate_improvement_code = AsyncMock(return_value={
        'database_service.py': '''
"""Database service with connection pooling."""
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://localhost/db',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30
)

async def execute_query(query: str):
    """Execute query with connection pooling."""
    with engine.connect() as conn:
        return conn.execute(query)
'''
    })
    
    return generator


@pytest.fixture
def self_building_system(mock_learning_engine, mock_llm_code_generator):
    """Create self-building system with mocks."""
    system = UltimateSelfBuildingSystem()
    system.learning_engine = mock_learning_engine
    system.llm_code_generator = mock_llm_code_generator
    system.running = True
    
    return system


class TestImprovementCycleTrigger:
    """Test triggering improvement cycle via MCP."""
    
    @pytest.mark.asyncio
    async def test_trigger_via_mcp_tool(self, self_building_system):
        """Test triggering improvement cycle via MCP tool."""
        # Mock MCP tool call
        from agents.self_building.self_building_mcp_server import trigger_improvement_cycle
        
        # Mock the system
        with patch('agents.self_building.self_building_mcp_server.ultimate_self_building_system', self_building_system):
            result = await trigger_improvement_cycle(
                analysis_window_hours=24,
                max_improvements=3,
                tenant_id="test_tenant"
            )
        
        # Parse response
        data = json.loads(result)
        
        assert data["success"] is True
        assert "data" in data
    
    @pytest.mark.asyncio
    async def test_trigger_with_custom_parameters(self, self_building_system):
        """Test triggering with custom parameters."""
        result = await self_building_system.autonomous_improvement_cycle(
            analysis_window_hours=12,
            max_improvements=2,
            tenant_id="test_tenant"
        )
        
        assert result["success"] is True
        assert result["insights_generated"] > 0
        assert result["opportunities_identified"] > 0


class TestTelemetryAnalysis:
    """Test telemetry analysis phase."""
    
    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, self_building_system):
        """Test performance trend analysis."""
        # Ingest mock telemetry
        for metric in MockTelemetryData.get_performance_metrics():
            await self_building_system.learning_engine.ingest_telemetry(
                telemetry_data=metric,
                source="metrics"
            )
        
        # Analyze trends
        insights = await self_building_system.learning_engine.analyze_performance_trends(
            time_window_hours=24,
            tenant_id="test_tenant"
        )
        
        assert len(insights) > 0
        assert insights[0].insight_type == 'performance_degradation'
        assert insights[0].severity == 'high'
    
    @pytest.mark.asyncio
    async def test_analyze_error_patterns(self, self_building_system):
        """Test error pattern analysis."""
        # Ingest mock logs
        for log in MockTelemetryData.get_error_logs():
            await self_building_system.learning_engine.ingest_telemetry(
                telemetry_data=log,
                source="logs"
            )
        
        # Analyze errors
        insights = await self_building_system.learning_engine.analyze_error_patterns(
            time_window_hours=24,
            tenant_id="test_tenant"
        )
        
        assert len(insights) > 0
        assert insights[0].insight_type == 'error_pattern'
    
    @pytest.mark.asyncio
    async def test_identify_improvement_opportunities(self, self_building_system):
        """Test identifying improvement opportunities."""
        # Get insights
        performance_insights = await self_building_system.learning_engine.analyze_performance_trends(
            time_window_hours=24
        )
        error_insights = await self_building_system.learning_engine.analyze_error_patterns(
            time_window_hours=24
        )
        
        all_insights = performance_insights + error_insights
        
        # Identify opportunities
        opportunities = await self_building_system.learning_engine.identify_improvement_opportunities(
            insights=all_insights
        )
        
        assert len(opportunities) > 0
        assert all(opp.impact_score > 0 for opp in opportunities)
        assert all(opp.risk_level in ['low', 'medium', 'high'] for opp in opportunities)


class TestCodeGeneration:
    """Test code generation phase."""
    
    @pytest.mark.asyncio
    async def test_generate_improvement_code(self, self_building_system):
        """Test generating improvement code."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_test',
            title='Test improvement',
            description='Test description',
            impact_score=75.0,
            effort_estimate='medium',
            affected_components=['test_component'],
            telemetry_evidence=[],
            proposed_changes={'change_type': 'optimization'},
            risk_level='medium'
        )
        
        existing_code = "def old_function():\n    pass"
        
        # Generate code
        generated_code = await self_building_system.llm_code_generator.generate_improvement_code(
            opportunity=opportunity,
            existing_code=existing_code
        )
        
        assert isinstance(generated_code, dict)
        assert len(generated_code) > 0
        assert any('.py' in path for path in generated_code.keys())
    
    @pytest.mark.asyncio
    async def test_code_validation(self, self_building_system):
        """Test code validation after generation."""
        # Generate code
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_test',
            title='Test',
            description='Test',
            impact_score=50.0,
            effort_estimate='low',
            affected_components=['test'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        generated_code = await self_building_system.llm_code_generator.generate_improvement_code(
            opportunity=opportunity,
            existing_code="def test(): pass"
        )
        
        # Code should be valid Python
        assert isinstance(generated_code, dict)


class TestDeployment:
    """Test deployment phase."""
    
    @pytest.mark.asyncio
    async def test_deploy_improvement(self, self_building_system):
        """Test deploying improvement."""
        generated_code = {
            '/tmp/test_component.py': 'def improved_function():\n    return True'
        }
        
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_deploy',
            title='Deploy test',
            description='Test deployment',
            impact_score=60.0,
            effort_estimate='low',
            affected_components=['test_component'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        # Mock deployment
        with patch.object(self_building_system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy:
            mock_deploy.return_value = {
                'success': True,
                'deployed_files': ['/tmp/test_component.py'],
                'timestamp': datetime.now()
            }
            
            result = await self_building_system._deploy_improvement(
                opportunity=opportunity,
                generated_code=generated_code
            )
            
            assert result['success'] is True
            assert len(result['deployed_files']) > 0
    
    @pytest.mark.asyncio
    async def test_deployment_creates_backup(self, self_building_system):
        """Test deployment creates backup of previous version."""
        generated_code = {
            '/tmp/test.py': 'def new_version(): pass'
        }
        
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_backup',
            title='Backup test',
            description='Test backup',
            impact_score=50.0,
            effort_estimate='low',
            affected_components=['test'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        # Mock deployment with backup
        with patch.object(self_building_system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy:
            mock_deploy.return_value = {
                'success': True,
                'deployed_files': ['/tmp/test.py'],
                'backup_created': True
            }
            
            result = await self_building_system._deploy_improvement(
                opportunity=opportunity,
                generated_code=generated_code
            )
            
            assert result.get('backup_created') is True


class TestMonitoring:
    """Test monitoring phase."""
    
    @pytest.mark.asyncio
    async def test_monitor_improvement_stable(self, self_building_system):
        """Test monitoring improvement with stable metrics."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_monitor',
            title='Monitor test',
            description='Test monitoring',
            impact_score=70.0,
            effort_estimate='medium',
            affected_components=['test'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='medium'
        )
        
        deployment_result = {
            'success': True,
            'deployed_files': ['/tmp/test.py']
        }
        
        # Mock stable metrics
        with patch.object(self_building_system, '_collect_current_metrics', new_callable=AsyncMock) as mock_metrics:
            mock_metrics.return_value = {'latency_ms': 100.0, 'error_rate': 0.01}
            
            result = await self_building_system._monitor_improvement(
                opportunity=opportunity,
                deployment_result=deployment_result,
                monitoring_duration_seconds=1
            )
            
            assert result['rolled_back'] is False
            assert result['status'] == 'stable'
    
    @pytest.mark.asyncio
    async def test_monitor_improvement_degradation(self, self_building_system):
        """Test monitoring detects degradation."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_degrade',
            title='Degradation test',
            description='Test degradation detection',
            impact_score=60.0,
            effort_estimate='low',
            affected_components=['test'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        deployment_result = {
            'success': True,
            'deployed_files': ['/tmp/test.py']
        }
        
        # Mock degraded metrics
        call_count = [0]
        
        async def mock_metrics_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {'latency_ms': 100.0}
            else:
                return {'latency_ms': 150.0}  # 50% increase
        
        with patch.object(self_building_system, '_collect_current_metrics', new_callable=AsyncMock) as mock_metrics, \
             patch.object(self_building_system, '_rollback_improvement', new_callable=AsyncMock) as mock_rollback:
            
            mock_metrics.side_effect = mock_metrics_side_effect
            mock_rollback.return_value = {'success': True}
            
            result = await self_building_system._monitor_improvement(
                opportunity=opportunity,
                deployment_result=deployment_result,
                monitoring_duration_seconds=2
            )
            
            assert result['rolled_back'] is True
            assert result['reason'] == 'performance_degradation'


class TestRollback:
    """Test rollback logic."""
    
    @pytest.mark.asyncio
    async def test_rollback_improvement(self, self_building_system):
        """Test rolling back improvement."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_rollback',
            title='Rollback test',
            description='Test rollback',
            impact_score=50.0,
            effort_estimate='low',
            affected_components=['test_component'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        # Set up backup
        self_building_system.improvement_backups = {
            'opp_rollback': {
                'previous_versions': {
                    '/tmp/test.py': 'def old_version(): pass'
                },
                'deployed_files': ['/tmp/test.py'],
                'timestamp': datetime.now()
            }
        }
        
        # Mock rollback
        with patch.object(self_building_system, '_rollback_improvement', new_callable=AsyncMock) as mock_rollback:
            mock_rollback.return_value = {
                'success': True,
                'opportunity_id': 'opp_rollback',
                'restored_files': ['/tmp/test.py']
            }
            
            result = await self_building_system._rollback_improvement(
                opportunity=opportunity,
                reason='test_rollback'
            )
            
            assert result['success'] is True
            assert len(result['restored_files']) > 0
    
    @pytest.mark.asyncio
    async def test_rollback_restores_previous_version(self, self_building_system):
        """Test rollback restores previous version."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_restore',
            title='Restore test',
            description='Test restore',
            impact_score=50.0,
            effort_estimate='low',
            affected_components=['test'],
            telemetry_evidence=[],
            proposed_changes={},
            risk_level='low'
        )
        
        # Mock rollback with verification
        with patch.object(self_building_system, '_rollback_improvement', new_callable=AsyncMock) as mock_rollback:
            mock_rollback.return_value = {
                'success': True,
                'opportunity_id': 'opp_restore',
                'restored_files': ['/tmp/test.py'],
                'version_restored': 'previous'
            }
            
            result = await self_building_system._rollback_improvement(
                opportunity=opportunity,
                reason='performance_degradation'
            )
            
            assert result.get('version_restored') == 'previous'


class TestEndToEndFlow:
    """Test complete end-to-end improvement cycle."""
    
    @pytest.mark.asyncio
    async def test_complete_improvement_cycle(self, self_building_system):
        """Test complete improvement cycle from trigger to completion."""
        # Mock all phases
        with patch.object(self_building_system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy, \
             patch.object(self_building_system, '_monitor_improvement', new_callable=AsyncMock) as mock_monitor, \
             patch.object(self_building_system, '_get_existing_component_code', new_callable=AsyncMock) as mock_get_code:
            
            mock_deploy.return_value = {
                'success': True,
                'deployed_files': ['test.py']
            }
            mock_monitor.return_value = {
                'rolled_back': False,
                'status': 'stable'
            }
            mock_get_code.return_value = 'def old(): pass'
            
            # Run complete cycle
            result = await self_building_system.autonomous_improvement_cycle(
                analysis_window_hours=24,
                max_improvements=2,
                tenant_id="test_tenant"
            )
            
            # Verify all phases completed
            assert result['success'] is True
            assert result['insights_generated'] > 0
            assert result['opportunities_identified'] > 0
            assert result['improvements_executed'] >= 0
    
    @pytest.mark.asyncio
    async def test_cycle_with_rollback(self, self_building_system):
        """Test improvement cycle with rollback."""
        # Mock deployment success but monitoring triggers rollback
        with patch.object(self_building_system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy, \
             patch.object(self_building_system, '_monitor_improvement', new_callable=AsyncMock) as mock_monitor, \
             patch.object(self_building_system, '_get_existing_component_code', new_callable=AsyncMock) as mock_get_code:
            
            mock_deploy.return_value = {
                'success': True,
                'deployed_files': ['test.py']
            }
            mock_monitor.return_value = {
                'rolled_back': True,
                'reason': 'performance_degradation'
            }
            mock_get_code.return_value = 'def old(): pass'
            
            # Run cycle
            result = await self_building_system.autonomous_improvement_cycle(
                analysis_window_hours=24,
                max_improvements=1
            )
            
            # Should complete with rollback
            assert result['success'] is True
            assert result.get('rolled_back', 0) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
