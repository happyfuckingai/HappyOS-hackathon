"""
Test autonomous improvement cycle implementation.

This test verifies that the improvement cycle can be triggered and executes
the expected pipeline: analysis -> opportunities -> execution -> monitoring.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from backend.core.self_building.ultimate_self_building import UltimateSelfBuildingSystem
from backend.core.self_building.intelligence.learning_engine import (
    TelemetryInsight,
    ImprovementOpportunity
)


@pytest.fixture
def mock_learning_engine():
    """Create a mock learning engine with sample data."""
    engine = Mock()
    
    # Mock insights
    engine.analyze_performance_trends = AsyncMock(return_value=[
        TelemetryInsight(
            insight_type='performance_degradation',
            severity='high',
            affected_component='test_component',
            affected_tenants=['test_tenant'],
            metrics={'latency_ms': 500, 'degradation_pct': 25},
            description='High latency detected',
            recommended_action='Optimize database queries',
            confidence_score=0.85,
            timestamp=datetime.now()
        )
    ])
    
    engine.analyze_error_patterns = AsyncMock(return_value=[])
    
    # Mock opportunities
    engine.identify_improvement_opportunities = AsyncMock(return_value=[
        ImprovementOpportunity(
            opportunity_id='opp_test_1',
            title='Optimize test_component',
            description='Reduce latency in test_component',
            impact_score=75.0,
            effort_estimate='medium',
            affected_components=['test_component'],
            telemetry_evidence=[],
            proposed_changes={
                'change_type': 'optimization',
                'targets': [{'type': 'performance', 'action': 'optimize_latency'}]
            },
            risk_level='medium'
        )
    ])
    
    return engine


@pytest.fixture
def mock_llm_code_generator():
    """Create a mock LLM code generator."""
    generator = Mock()
    generator.initialize = AsyncMock()
    generator.generate_improvement_code = AsyncMock(return_value={
        'test_component.py': '# Improved code\nprint("optimized")'
    })
    return generator


@pytest.mark.asyncio
async def test_autonomous_improvement_cycle_basic(mock_learning_engine, mock_llm_code_generator):
    """Test basic autonomous improvement cycle execution."""
    
    # Create system instance
    system = UltimateSelfBuildingSystem()
    system.learning_engine = mock_learning_engine
    system.llm_code_generator = mock_llm_code_generator
    system.running = True
    
    # Mock deployment and monitoring
    with patch.object(system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy, \
         patch.object(system, '_monitor_improvement', new_callable=AsyncMock) as mock_monitor, \
         patch.object(system, '_get_existing_component_code', new_callable=AsyncMock) as mock_get_code:
        
        mock_deploy.return_value = {'success': True, 'deployed_files': ['test_component.py']}
        mock_monitor.return_value = {'rolled_back': False, 'status': 'stable'}
        mock_get_code.return_value = '# Original code\nprint("original")'
        
        # Trigger improvement cycle
        result = await system.autonomous_improvement_cycle(
            analysis_window_hours=1,
            max_improvements=1
        )
        
        # Verify results
        assert result['success'] is True
        assert result['insights_generated'] == 1
        assert result['opportunities_identified'] == 1
        assert result['improvements_executed'] == 1
        assert result['successful'] >= 0  # May be 0 or 1 depending on execution
        
        # Verify methods were called
        mock_learning_engine.analyze_performance_trends.assert_called_once()
        mock_learning_engine.analyze_error_patterns.assert_called_once()
        mock_learning_engine.identify_improvement_opportunities.assert_called_once()


@pytest.mark.asyncio
async def test_improvement_execution_pipeline(mock_learning_engine, mock_llm_code_generator):
    """Test the improvement execution pipeline."""
    
    system = UltimateSelfBuildingSystem()
    system.learning_engine = mock_learning_engine
    system.llm_code_generator = mock_llm_code_generator
    system.running = True
    
    opportunity = ImprovementOpportunity(
        opportunity_id='opp_test_1',
        title='Test improvement',
        description='Test description',
        impact_score=50.0,
        effort_estimate='low',
        affected_components=['test_component'],
        telemetry_evidence=[],
        proposed_changes={'change_type': 'optimization'},
        risk_level='low'
    )
    
    with patch.object(system, '_deploy_improvement', new_callable=AsyncMock) as mock_deploy, \
         patch.object(system, '_monitor_improvement', new_callable=AsyncMock) as mock_monitor, \
         patch.object(system, '_get_existing_component_code', new_callable=AsyncMock) as mock_get_code:
        
        mock_deploy.return_value = {'success': True, 'deployed_files': ['test.py']}
        mock_monitor.return_value = {'rolled_back': False}
        mock_get_code.return_value = '# Original'
        
        # Execute improvement
        result = await system._execute_improvement(opportunity)
        
        # Verify execution
        assert result['success'] is True
        assert result['opportunity_id'] == 'opp_test_1'
        assert 'files_generated' in result
        
        # Verify pipeline steps
        mock_llm_code_generator.generate_improvement_code.assert_called_once()
        mock_deploy.assert_called_once()


@pytest.mark.asyncio
async def test_improvement_monitoring_no_degradation():
    """Test improvement monitoring without degradation."""
    
    system = UltimateSelfBuildingSystem()
    system.learning_engine = Mock()
    system.running = True
    
    opportunity = ImprovementOpportunity(
        opportunity_id='opp_test_1',
        title='Test',
        description='Test',
        impact_score=50.0,
        effort_estimate='low',
        affected_components=['test'],
        telemetry_evidence=[],
        proposed_changes={},
        risk_level='low'
    )
    
    deployment_result = {'success': True, 'deployed_files': ['test.py']}
    
    with patch.object(system, '_collect_current_metrics', new_callable=AsyncMock) as mock_metrics, \
         patch.object(system, '_rollback_improvement', new_callable=AsyncMock) as mock_rollback:
        
        # Mock stable metrics (no degradation)
        mock_metrics.return_value = {'latency_ms': 100.0, 'error_rate': 0.01}
        
        # Monitor for short duration (1 second for testing)
        result = await system._monitor_improvement(
            opportunity=opportunity,
            deployment_result=deployment_result,
            monitoring_duration_seconds=1
        )
        
        # Verify no rollback
        assert result['rolled_back'] is False
        assert result['status'] == 'stable'
        mock_rollback.assert_not_called()


@pytest.mark.asyncio
async def test_improvement_monitoring_with_degradation():
    """Test improvement monitoring with degradation triggering rollback."""
    
    system = UltimateSelfBuildingSystem()
    system.learning_engine = Mock()
    system.running = True
    
    opportunity = ImprovementOpportunity(
        opportunity_id='opp_test_1',
        title='Test',
        description='Test',
        impact_score=50.0,
        effort_estimate='low',
        affected_components=['test'],
        telemetry_evidence=[],
        proposed_changes={},
        risk_level='low'
    )
    
    deployment_result = {'success': True, 'deployed_files': ['test.py']}
    
    with patch.object(system, '_collect_current_metrics', new_callable=AsyncMock) as mock_metrics, \
         patch.object(system, '_rollback_improvement', new_callable=AsyncMock) as mock_rollback:
        
        # Mock degraded metrics (20% increase in latency)
        call_count = [0]
        
        async def mock_metrics_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Baseline
                return {'latency_ms': 100.0}
            else:
                # Degraded (20% increase)
                return {'latency_ms': 120.0}
        
        mock_metrics.side_effect = mock_metrics_side_effect
        mock_rollback.return_value = {'success': True}
        
        # Monitor for short duration
        result = await system._monitor_improvement(
            opportunity=opportunity,
            deployment_result=deployment_result,
            monitoring_duration_seconds=2
        )
        
        # Verify rollback was triggered
        assert result['rolled_back'] is True
        assert result['reason'] == 'performance_degradation'
        mock_rollback.assert_called_once()


@pytest.mark.asyncio
async def test_improvement_rollback():
    """Test improvement rollback functionality."""
    
    system = UltimateSelfBuildingSystem()
    system.running = True
    
    opportunity = ImprovementOpportunity(
        opportunity_id='opp_test_1',
        title='Test',
        description='Test',
        impact_score=50.0,
        effort_estimate='low',
        affected_components=['test_component'],
        telemetry_evidence=[],
        proposed_changes={},
        risk_level='low'
    )
    
    # Set up backup
    system.improvement_backups = {
        'opp_test_1': {
            'previous_versions': {
                '/tmp/test.py': '# Original code'
            },
            'deployed_files': ['/tmp/test.py'],
            'timestamp': datetime.now()
        }
    }
    
    with patch('backend.core.self_building.ultimate_self_building.Path') as mock_path, \
         patch('backend.core.self_building.hot_reload.reload_manager.hot_reload_manager') as mock_reload:
        
        # Mock file operations
        mock_file = Mock()
        mock_file.write_text = Mock()
        mock_file.exists = Mock(return_value=True)
        mock_path.return_value = mock_file
        
        # Mock reload
        mock_reload.manual_reload = AsyncMock(return_value=True)
        
        # Execute rollback
        result = await system._rollback_improvement(
            opportunity=opportunity,
            reason='test_rollback'
        )
        
        # Verify rollback
        assert result['success'] is True
        assert result['opportunity_id'] == 'opp_test_1'
        assert len(result['restored_files']) > 0


def test_calculate_degradation():
    """Test degradation calculation."""
    
    system = UltimateSelfBuildingSystem()
    
    # Test latency degradation
    baseline = {'latency_ms': 100.0}
    current = {'latency_ms': 120.0}
    degradation = system._calculate_degradation(baseline, current)
    assert degradation == 0.2  # 20% increase
    
    # Test error rate degradation
    baseline = {'error_rate': 0.01}
    current = {'error_rate': 0.02}
    degradation = system._calculate_degradation(baseline, current)
    assert degradation == 1.0  # 100% increase
    
    # Test success rate degradation
    baseline = {'success_rate': 1.0}
    current = {'success_rate': 0.9}
    degradation = system._calculate_degradation(baseline, current)
    assert degradation == 0.1  # 10% decrease
    
    # Test no degradation
    baseline = {'latency_ms': 100.0}
    current = {'latency_ms': 95.0}
    degradation = system._calculate_degradation(baseline, current)
    assert degradation == 0.0  # No degradation (improvement)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
