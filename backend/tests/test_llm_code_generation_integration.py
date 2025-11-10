"""
Integration tests for LLM code generation.

Tests component code generation, improvement code generation, code validation,
and error handling with retries.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.self_building.generators.llm_code_generator import (
    LLMCodeGenerator,
    CodeGenerationError,
    ValidationResult
)
from core.self_building.intelligence.learning_engine import (
    TelemetryInsight,
    ImprovementOpportunity
)
from datetime import datetime


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, should_fail: bool = False, fail_count: int = 0):
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.current_failures = 0
        self.call_count = 0
        self.last_prompt = None
    
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        **kwargs
    ) -> str:
        """Mock text generation."""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Fail for specified number of attempts
        if self.current_failures < self.fail_count:
            self.current_failures += 1
            raise Exception(f"LLM generation failed (attempt {self.current_failures})")
        
        if self.should_fail:
            raise Exception("LLM service unavailable")
        
        # Return mock generated code
        return '''{
            "files": {
                "test_component.py": "def test_function():\\n    \\"\\"\\"Test function.\\"\\"\\"\\n    return True\\n",
                "__init__.py": "from .test_component import test_function\\n"
            },
            "description": "Generated test component",
            "dependencies": ["typing", "asyncio"]
        }'''


class MockCircuitBreaker:
    """Mock circuit breaker for testing."""
    
    def __init__(self):
        self.is_open = False
        self.call_count = 0
    
    async def call_with_protection(self, func, *args, **kwargs):
        """Mock protected call."""
        self.call_count += 1
        
        if self.is_open:
            raise Exception("Circuit breaker is open")
        
        return await func(*args, **kwargs)


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    return MockLLMService()


@pytest.fixture
def mock_circuit_breaker():
    """Create mock circuit breaker."""
    return MockCircuitBreaker()


@pytest.fixture
def llm_code_generator(mock_llm_service, mock_circuit_breaker):
    """Create LLM code generator with mocks."""
    generator = LLMCodeGenerator()
    
    # Replace with mocks
    generator.llm_service = mock_llm_service
    generator.llm_circuit_breaker = mock_circuit_breaker
    
    return generator


class TestLLMCodeGeneratorInitialization:
    """Test LLM code generator initialization."""
    
    def test_generator_initialization(self):
        """Test generator initializes correctly."""
        generator = LLMCodeGenerator()
        
        assert generator.service_factory is not None
        assert generator.llm_service is not None
        assert generator.llm_circuit_breaker is not None
        assert generator.code_validator is not None
    
    def test_generator_attributes(self, llm_code_generator):
        """Test generator has required attributes."""
        assert hasattr(llm_code_generator, 'max_retries')
        assert hasattr(llm_code_generator, 'default_temperature')
        assert hasattr(llm_code_generator, 'default_max_tokens')
        assert llm_code_generator.max_retries >= 1
    
    @pytest.mark.asyncio
    async def test_generator_initialize(self, llm_code_generator):
        """Test generator initialization method."""
        await llm_code_generator.initialize()
        
        # Should complete without error
        assert True


class TestComponentCodeGeneration:
    """Test component code generation."""
    
    @pytest.mark.asyncio
    async def test_generate_component_code_success(self, llm_code_generator):
        """Test generating component code successfully."""
        component_type = "skill"
        requirements = {
            "name": "test_skill",
            "description": "A test skill for validation",
            "capabilities": ["test_execution"]
        }
        context = {
            "tenant_id": "test_tenant",
            "architecture": "MCP-based system"
        }
        
        result = await llm_code_generator.generate_component_code(
            component_type=component_type,
            requirements=requirements,
            context=context
        )
        
        assert isinstance(result, dict)
        assert len(result) > 0
        # Should contain at least one Python file
        assert any(path.endswith('.py') for path in result.keys())
    
    @pytest.mark.asyncio
    async def test_generate_component_code_with_insights(self, llm_code_generator):
        """Test generating component code with telemetry insights."""
        component_type = "service"
        requirements = {
            "name": "optimized_service",
            "description": "Service optimized for performance"
        }
        context = {"tenant_id": "test_tenant"}
        
        # Create telemetry insights
        insights = [
            TelemetryInsight(
                insight_type='performance_degradation',
                severity='high',
                affected_component='api',
                affected_tenants=['test_tenant'],
                metrics={'latency_ms': 500},
                description='High latency detected',
                recommended_action='Optimize queries',
                confidence_score=0.85,
                timestamp=datetime.now()
            )
        ]
        
        result = await llm_code_generator.generate_component_code(
            component_type=component_type,
            requirements=requirements,
            context=context,
            telemetry_insights=insights
        )
        
        assert isinstance(result, dict)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_generate_component_code_all_types(self, llm_code_generator):
        """Test generating all component types."""
        component_types = ["skill", "agent", "service", "plugin"]
        
        for component_type in component_types:
            requirements = {
                "name": f"test_{component_type}",
                "description": f"Test {component_type}"
            }
            context = {"tenant_id": "test_tenant"}
            
            result = await llm_code_generator.generate_component_code(
                component_type=component_type,
                requirements=requirements,
                context=context
            )
            
            assert isinstance(result, dict)
            assert len(result) > 0


class TestImprovementCodeGeneration:
    """Test improvement code generation."""
    
    @pytest.mark.asyncio
    async def test_generate_improvement_code_success(self, llm_code_generator):
        """Test generating improvement code successfully."""
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_test_1',
            title='Optimize database queries',
            description='Reduce query latency',
            impact_score=75.0,
            effort_estimate='medium',
            affected_components=['database_service'],
            telemetry_evidence=[],
            proposed_changes={
                'change_type': 'optimization',
                'targets': [{'type': 'performance', 'action': 'optimize_queries'}]
            },
            risk_level='medium'
        )
        
        existing_code = '''
def query_database(query):
    """Execute database query."""
    # Slow implementation
    return execute_query(query)
'''
        
        result = await llm_code_generator.generate_improvement_code(
            opportunity=opportunity,
            existing_code=existing_code
        )
        
        assert isinstance(result, dict)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_generate_improvement_code_with_evidence(self, llm_code_generator):
        """Test generating improvement code with telemetry evidence."""
        insights = [
            TelemetryInsight(
                insight_type='performance_degradation',
                severity='high',
                affected_component='api',
                affected_tenants=['test_tenant'],
                metrics={'latency_ms': 500, 'degradation_pct': 25},
                description='High latency in API calls',
                recommended_action='Add caching',
                confidence_score=0.9,
                timestamp=datetime.now()
            )
        ]
        
        opportunity = ImprovementOpportunity(
            opportunity_id='opp_test_2',
            title='Add caching layer',
            description='Reduce API latency with caching',
            impact_score=85.0,
            effort_estimate='low',
            affected_components=['api_service'],
            telemetry_evidence=insights,
            proposed_changes={'change_type': 'enhancement'},
            risk_level='low'
        )
        
        existing_code = '''
def api_call(endpoint):
    """Make API call."""
    return fetch_data(endpoint)
'''
        
        result = await llm_code_generator.generate_improvement_code(
            opportunity=opportunity,
            existing_code=existing_code
        )
        
        assert isinstance(result, dict)
        assert len(result) > 0


class TestPromptBuilding:
    """Test prompt building functionality."""
    
    def test_build_generation_prompt_basic(self, llm_code_generator):
        """Test building basic generation prompt."""
        component_type = "skill"
        requirements = {"name": "test_skill", "description": "Test"}
        context = {"tenant_id": "test_tenant"}
        
        prompt = llm_code_generator._build_generation_prompt(
            component_type=component_type,
            requirements=requirements,
            context=context,
            telemetry_insights=None
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "skill" in prompt.lower()
        assert "test_skill" in prompt
    
    def test_build_generation_prompt_with_insights(self, llm_code_generator):
        """Test building prompt with telemetry insights."""
        component_type = "service"
        requirements = {"name": "optimized_service"}
        context = {"architecture": "MCP-based"}
        
        insights = [
            TelemetryInsight(
                insight_type='optimization_opportunity',
                severity='medium',
                affected_component='service',
                affected_tenants=['test_tenant'],
                metrics={'cpu_usage': 80},
                description='High CPU usage',
                recommended_action='Optimize algorithms',
                confidence_score=0.8,
                timestamp=datetime.now()
            )
        ]
        
        prompt = llm_code_generator._build_generation_prompt(
            component_type=component_type,
            requirements=requirements,
            context=context,
            telemetry_insights=insights
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should include insight information
        assert "optimization" in prompt.lower() or "cpu" in prompt.lower()
    
    def test_build_generation_prompt_with_patterns(self, llm_code_generator):
        """Test building prompt with code patterns."""
        component_type = "agent"
        requirements = {"name": "test_agent"}
        context = {
            "patterns": {
                "async_function": "async def example():\n    pass",
                "error_handling": "try:\n    pass\nexcept Exception as e:\n    logger.error(e)"
            }
        }
        
        prompt = llm_code_generator._build_generation_prompt(
            component_type=component_type,
            requirements=requirements,
            context=context,
            telemetry_insights=None
        )
        
        assert isinstance(prompt, str)
        assert "async" in prompt or "example" in prompt


class TestCodeValidation:
    """Test code validation logic."""
    
    @pytest.mark.asyncio
    async def test_validate_code_success(self, llm_code_generator):
        """Test validating correct code."""
        code_files = {
            "test.py": '''
"""Test module."""
import logging

logger = logging.getLogger(__name__)

def test_function(param: str) -> str:
    """Test function with docstring."""
    try:
        logger.info(f"Processing {param}")
        return param.upper()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
'''
        }
        
        result = await llm_code_generator._validate_code(code_files)
        
        assert isinstance(result, ValidationResult)
        assert result.success is True
        assert result.quality_score > 0.5
    
    @pytest.mark.asyncio
    async def test_validate_code_syntax_error(self, llm_code_generator):
        """Test validating code with syntax error."""
        code_files = {
            "bad.py": '''
def broken_function(
    # Missing closing parenthesis
    return "broken"
'''
        }
        
        result = await llm_code_generator._validate_code(code_files)
        
        assert isinstance(result, ValidationResult)
        assert result.success is False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_validate_code_quality_metrics(self, llm_code_generator):
        """Test code quality metrics calculation."""
        good_code = {
            "quality.py": '''
"""High quality module."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def well_documented_function(param: str, optional: Optional[int] = None) -> str:
    """
    Well documented function with type hints.
    
    Args:
        param: String parameter
        optional: Optional integer parameter
        
    Returns:
        Processed string
    """
    try:
        logger.info(f"Processing {param}")
        result = param.upper()
        if optional:
            result += str(optional)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
'''
        }
        
        result = await llm_code_generator._validate_code(good_code)
        
        assert isinstance(result, ValidationResult)
        assert result.success is True
        assert result.quality_score > 0.7


class TestCodeParsing:
    """Test code parsing from LLM responses."""
    
    def test_parse_generated_code_json(self, llm_code_generator):
        """Test parsing JSON response."""
        json_response = '''{
            "files": {
                "module.py": "def hello():\\n    print('Hello')",
                "__init__.py": "from .module import hello"
            },
            "description": "Test module"
        }'''
        
        files = llm_code_generator._parse_generated_code(json_response)
        
        assert isinstance(files, dict)
        assert "module.py" in files
        assert "__init__.py" in files
        assert "hello" in files["module.py"]
    
    def test_parse_generated_code_with_metadata(self, llm_code_generator):
        """Test parsing response with metadata."""
        json_response = '''{
            "files": {
                "service.py": "class Service:\\n    pass"
            },
            "description": "Service implementation",
            "dependencies": ["asyncio", "typing"]
        }'''
        
        files = llm_code_generator._parse_generated_code(json_response)
        
        assert isinstance(files, dict)
        assert "service.py" in files
    
    def test_parse_generated_code_malformed(self, llm_code_generator):
        """Test parsing malformed response."""
        malformed_response = "Not valid JSON"
        
        with pytest.raises(Exception):
            llm_code_generator._parse_generated_code(malformed_response)


class TestErrorHandlingAndRetries:
    """Test error handling and retry logic."""
    
    @pytest.mark.asyncio
    async def test_generation_retry_on_failure(self):
        """Test generation retries on failure."""
        # Create generator with failing LLM that succeeds on 2nd attempt
        failing_llm = MockLLMService(fail_count=1)
        generator = LLMCodeGenerator()
        generator.llm_service = failing_llm
        generator.llm_circuit_breaker = MockCircuitBreaker()
        generator.max_retries = 3
        
        requirements = {"name": "test", "description": "Test"}
        context = {"tenant_id": "test"}
        
        # Should succeed after retry
        result = await generator.generate_component_code(
            component_type="skill",
            requirements=requirements,
            context=context
        )
        
        assert isinstance(result, dict)
        assert failing_llm.call_count >= 2  # At least 2 attempts
    
    @pytest.mark.asyncio
    async def test_generation_fails_after_max_retries(self):
        """Test generation fails after max retries."""
        # Create generator with always-failing LLM
        failing_llm = MockLLMService(should_fail=True)
        generator = LLMCodeGenerator()
        generator.llm_service = failing_llm
        generator.llm_circuit_breaker = MockCircuitBreaker()
        generator.max_retries = 2
        
        requirements = {"name": "test", "description": "Test"}
        context = {"tenant_id": "test"}
        
        # Should fail after retries
        with pytest.raises(CodeGenerationError):
            await generator.generate_component_code(
                component_type="skill",
                requirements=requirements,
                context=context
            )
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self):
        """Test circuit breaker protects LLM calls."""
        generator = LLMCodeGenerator()
        circuit_breaker = MockCircuitBreaker()
        generator.llm_circuit_breaker = circuit_breaker
        generator.llm_service = MockLLMService()
        
        requirements = {"name": "test", "description": "Test"}
        context = {"tenant_id": "test"}
        
        await generator.generate_component_code(
            component_type="skill",
            requirements=requirements,
            context=context
        )
        
        # Circuit breaker should have been used
        assert circuit_breaker.call_count > 0
    
    @pytest.mark.asyncio
    async def test_validation_feedback_in_retry(self):
        """Test validation feedback is used in retry."""
        generator = LLMCodeGenerator()
        generator.llm_service = MockLLMService()
        generator.llm_circuit_breaker = MockCircuitBreaker()
        
        requirements = {"name": "test", "description": "Test"}
        context = {"tenant_id": "test"}
        
        # Generate code
        result = await generator.generate_component_code(
            component_type="skill",
            requirements=requirements,
            context=context
        )
        
        # Should have validated the code
        assert isinstance(result, dict)


class TestQualityScoring:
    """Test code quality scoring."""
    
    def test_calculate_quality_score_high(self, llm_code_generator):
        """Test quality score for high-quality code."""
        high_quality_code = '''
"""Well-documented module."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def documented_function(param: str, optional: Optional[int] = None) -> str:
    """
    Function with complete documentation.
    
    Args:
        param: String parameter
        optional: Optional parameter
        
    Returns:
        Processed string
    """
    try:
        logger.info(f"Processing {param}")
        return param.upper()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
'''
        
        score = llm_code_generator._calculate_quality_score(high_quality_code)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.7
    
    def test_calculate_quality_score_low(self, llm_code_generator):
        """Test quality score for low-quality code."""
        low_quality_code = '''
def f(x):
    return x
'''
        
        score = llm_code_generator._calculate_quality_score(low_quality_code)
        
        assert 0.0 <= score <= 1.0
        assert score < 0.5
    
    def test_calculate_quality_score_medium(self, llm_code_generator):
        """Test quality score for medium-quality code."""
        medium_quality_code = '''
import logging

def process_data(data):
    """Process data."""
    try:
        return data.upper()
    except Exception as e:
        logging.error(e)
        return None
'''
        
        score = llm_code_generator._calculate_quality_score(medium_quality_code)
        
        assert 0.0 <= score <= 1.0
        assert 0.4 <= score <= 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
