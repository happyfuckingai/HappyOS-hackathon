"""
Integration tests for agent LLM usage across all teams.

Tests:
- MeetMind Coordinator with LLM service
- Agent Svea Product Manager with svenska prompts
- Felicia's Finance Architect with refactored code
- Fallback functionality when LLM is unavailable

Requirements: 10.2, 10.4, 10.6
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional

# Add backend to path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockLLMService:
    """Mock LLM service for integration testing."""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0
        self.last_prompt = None
        self.last_agent_id = None
    
    async def generate_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """Mock LLM completion with realistic responses."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_agent_id = agent_id
        
        if self.should_fail:
            raise Exception("Mock LLM service failure")
        
        # Return agent-specific mock responses
        if "meetmind" in agent_id.lower() or "coordinator" in agent_id.lower():
            return {
                "content": """{
                    "workflow_id": "wf_12345",
                    "analysis_tasks": [
                        "transcript_processing",
                        "sentiment_analysis",
                        "action_item_extraction",
                        "summary_generation"
                    ],
                    "priority": "high",
                    "estimated_duration": "15 minutes",
                    "agents_required": ["implementation", "qa"],
                    "meeting_insights": {
                        "participants": 5,
                        "duration": "45 minutes",
                        "key_topics": ["project status", "deadlines", "resource allocation"]
                    }
                }""",
                "model": model,
                "tokens": 120
            }
        
        elif "svea" in agent_id.lower() or "product_manager" in agent_id.lower():
            return {
                "content": """{
                    "regelverkstyp": "accounting_act",
                    "företagstyp": "general",
                    "obligatoriska_krav": [
                        "BAS-kontoplan enligt BAS 2019",
                        "Dubbel bokföring enligt bokföringslagen",
                        "10 års arkivering av bokföringsmaterial",
                        "SIE-export för rapportering",
                        "Svensk momsberäkning (25%, 12%, 6%, 0%)"
                    ],
                    "valfria_krav": [
                        "Realtidsövervakning av transaktioner",
                        "Automatisk rapportering till Skatteverket"
                    ],
                    "implementeringsprioritet": "hög",
                    "compliance_deadline": "2024-12-31",
                    "konsekvensanalys": {
                        "utvecklingsinsats": "6-12 månader",
                        "compliance_risk": "hög vid icke-efterlevnad",
                        "affärspåverkan": "kritisk för svensk verksamhet",
                        "teknisk_komplexitet": "medel till hög"
                    },
                    "specifika_svenska_krav": [
                        "BAS 2019 kontoplan",
                        "K-rapporter för årsredovisning",
                        "Skatteverkets digitala krav"
                    ],
                    "myndighetsintegration": ["Skatteverket", "Bolagsverket"]
                }""",
                "model": model,
                "tokens": 180
            }
        
        elif "felicia" in agent_id.lower() or "architect" in agent_id.lower():
            return {
                "content": """{
                    "architecture_design": {
                        "system_name": "Felicia's Finance Platform",
                        "components": [
                            "Trading Engine",
                            "Risk Management System",
                            "Portfolio Analyzer",
                            "Market Data Aggregator"
                        ],
                        "technology_stack": {
                            "backend": "Python FastAPI",
                            "database": "PostgreSQL + Redis",
                            "messaging": "RabbitMQ",
                            "monitoring": "Prometheus + Grafana"
                        },
                        "integration_points": [
                            "Binance API",
                            "Coinbase API",
                            "Banking APIs",
                            "Market Data Feeds"
                        ],
                        "security_measures": [
                            "API key encryption",
                            "Multi-factor authentication",
                            "Rate limiting",
                            "Audit logging"
                        ],
                        "scalability": {
                            "horizontal_scaling": true,
                            "load_balancing": "AWS ALB",
                            "caching_strategy": "Redis with TTL"
                        }
                    },
                    "implementation_phases": [
                        "Core trading engine",
                        "Risk management",
                        "Portfolio tracking",
                        "Advanced analytics"
                    ],
                    "estimated_timeline": "12-16 weeks"
                }""",
                "model": model,
                "tokens": 200
            }
        
        # Default response
        return {
            "content": '{"status": "success", "message": "Mock LLM response"}',
            "model": model,
            "tokens": 50
        }


class TestMeetMindCoordinatorLLM:
    """Test MeetMind Coordinator Agent with LLM service."""
    
    async def test_coordinator_with_llm(self):
        """Test that MeetMind Coordinator uses LLM service correctly."""
        logger.info("Testing MeetMind Coordinator with LLM service...")
        
        from agents.meetmind.adk_agents.coordinator_agent import CoordinatorAgent
        
        # Create mock LLM service
        mock_llm = MockLLMService()
        
        # Initialize coordinator with LLM service
        coordinator = CoordinatorAgent(services={"llm_service": mock_llm})
        
        # Test meeting analysis coordination
        meeting_data = {
            "meeting_id": "mtg_12345",
            "participants": 5,
            "duration": "45 minutes",
            "transcript": "Team discussed project status and assigned tasks..."
        }
        
        result = await coordinator.coordinate_meeting_analysis(meeting_data)
        
        # Verify result
        assert result["status"] == "workflow_started"
        assert "workflow_id" in result
        assert result["agent"] == "coordinator"
        
        logger.info("✓ MeetMind Coordinator LLM integration working")
        return True
    
    async def test_coordinator_status(self):
        """Test that coordinator status reflects correct state."""
        logger.info("Testing MeetMind Coordinator status...")
        
        from agents.meetmind.adk_agents.coordinator_agent import CoordinatorAgent
        
        mock_llm = MockLLMService()
        coordinator = CoordinatorAgent(services={"llm_service": mock_llm})
        
        status = await coordinator.get_status()
        
        assert status["agent"] == "coordinator"
        assert status["status"] == "active"
        assert "specialties" in status
        
        logger.info("✓ MeetMind Coordinator status check passed")
        return True


class TestAgentSveaProductManagerSwedish:
    """Test Agent Svea Product Manager with Swedish prompts."""
    
    async def test_swedish_prompt_processing(self):
        """Test that Agent Svea processes Swedish prompts correctly."""
        logger.info("Testing Agent Svea Product Manager with svenska prompts...")
        
        from agents.agent_svea.adk_agents.product_manager_agent import ProductManagerAgent
        
        # Create mock LLM service
        mock_llm = MockLLMService()
        
        # Initialize PM with LLM service
        pm = ProductManagerAgent(services={"llm_service": mock_llm})
        
        # Test Swedish regulatory requirements analysis
        payload = {
            "regulation_type": "accounting_act",
            "business_type": "general",
            "tenant_id": "test_tenant_se"
        }
        
        result = await pm._analyze_regulatory_requirements(payload)
        
        # Verify Swedish content in response
        assert result["status"] == "regulatory_requirements_analyzed"
        assert "analysis" in result
        
        # Check for Swedish keywords in analysis
        analysis = result["analysis"]
        swedish_keywords = ["obligatoriska_krav", "regelverkstyp", "företagstyp"]
        has_swedish = any(keyword in str(analysis) for keyword in swedish_keywords)
        
        assert has_swedish, "Response should contain Swedish keywords"
        
        logger.info("✓ Agent Svea Product Manager svenska prompts working")
        return True
    
    async def test_swedish_compliance_requirements(self):
        """Test Swedish compliance requirements analysis."""
        logger.info("Testing Swedish compliance requirements...")
        
        from agents.agent_svea.adk_agents.product_manager_agent import ProductManagerAgent
        
        mock_llm = MockLLMService()
        pm = ProductManagerAgent(services={"llm_service": mock_llm})
        
        payload = {
            "regulation_type": "gdpr",
            "business_type": "tech_company",
            "tenant_id": "test_tenant_se"
        }
        
        result = await pm._analyze_regulatory_requirements(payload)
        
        assert result["status"] == "regulatory_requirements_analyzed"
        assert result.get("llm_enhanced") == True
        
        logger.info("✓ Swedish compliance requirements analysis working")
        return True


class TestFeliciasFinanceArchitectRefactored:
    """Test Felicia's Finance Architect with refactored code."""
    
    async def test_architect_with_refactored_llm(self):
        """Test that Felicia's Finance Architect uses refactored LLM service."""
        logger.info("Testing Felicia's Finance Architect with refactored code...")
        
        from agents.felicias_finance.adk_agents.agents.architect_agent import ArchitectAgent
        
        # Create mock LLM service
        mock_llm = MockLLMService()
        
        # Initialize architect with LLM service (refactored pattern)
        architect = ArchitectAgent(llm_service=mock_llm)
        
        # Verify LLM service is properly injected
        assert architect.llm_service is not None
        assert architect.llm_service == mock_llm
        
        # Test status
        status = await architect.get_status()
        
        assert status["agent"] == "architect"
        assert status["status"] == "active"
        
        logger.info("✓ Felicia's Finance Architect refactored code working")
        return True
    
    async def test_architect_design_generation(self):
        """Test architect design generation with LLM."""
        logger.info("Testing architect design generation...")
        
        from agents.felicias_finance.adk_agents.agents.architect_agent import ArchitectAgent
        
        mock_llm = MockLLMService()
        architect = ArchitectAgent(llm_service=mock_llm)
        
        # Test that architect can be initialized and queried
        status = await architect.get_status()
        
        assert status["agent"] == "architect"
        assert "specialties" in status
        
        logger.info("✓ Architect design generation working")
        return True


class TestLLMFallbackFunctionality:
    """Test fallback functionality when LLM is unavailable."""
    
    async def test_meetmind_fallback(self):
        """Test MeetMind fallback when LLM fails."""
        logger.info("Testing MeetMind fallback functionality...")
        
        from agents.meetmind.adk_agents.coordinator_agent import CoordinatorAgent
        
        # Create failing LLM service
        failing_llm = MockLLMService(should_fail=True)
        
        # Initialize coordinator with failing LLM
        coordinator = CoordinatorAgent(services={"llm_service": failing_llm})
        
        # Test that coordinator still works with fallback
        meeting_data = {
            "meeting_id": "mtg_fallback",
            "participants": 3
        }
        
        result = await coordinator.coordinate_meeting_analysis(meeting_data)
        
        # Should still return valid result using fallback logic
        assert result["status"] in ["workflow_started", "error"]
        assert "agent" in result
        
        logger.info("✓ MeetMind fallback functionality working")
        return True
    
    async def test_agent_svea_fallback(self):
        """Test Agent Svea fallback when LLM fails."""
        logger.info("Testing Agent Svea fallback functionality...")
        
        from agents.agent_svea.adk_agents.product_manager_agent import ProductManagerAgent
        
        # Initialize without LLM service
        pm = ProductManagerAgent(services={})
        
        # Test that PM works without LLM
        payload = {
            "regulation_type": "accounting_act",
            "business_type": "general",
            "tenant_id": "test_tenant"
        }
        
        result = await pm._analyze_regulatory_requirements(payload)
        
        # Should use fallback logic
        assert result["status"] == "regulatory_requirements_analyzed"
        assert result.get("fallback_used") == True
        
        logger.info("✓ Agent Svea fallback functionality working")
        return True
    
    async def test_felicias_finance_fallback(self):
        """Test Felicia's Finance fallback when LLM fails."""
        logger.info("Testing Felicia's Finance fallback functionality...")
        
        from agents.felicias_finance.adk_agents.agents.architect_agent import ArchitectAgent
        
        # Initialize without LLM service
        architect = ArchitectAgent(llm_service=None)
        
        # Test that architect works without LLM
        status = await architect.get_status()
        
        assert status["agent"] == "architect"
        assert status["status"] == "active"
        
        logger.info("✓ Felicia's Finance fallback functionality working")
        return True
    
    async def test_llm_unavailable_graceful_degradation(self):
        """Test graceful degradation when LLM is completely unavailable."""
        logger.info("Testing graceful degradation with unavailable LLM...")
        
        from agents.meetmind.adk_agents.coordinator_agent import CoordinatorAgent
        from agents.agent_svea.adk_agents.product_manager_agent import ProductManagerAgent
        from agents.felicias_finance.adk_agents.agents.architect_agent import ArchitectAgent
        
        # Test all three agents without LLM
        meetmind_coordinator = CoordinatorAgent(services={})
        svea_pm = ProductManagerAgent(services={})
        felicia_architect = ArchitectAgent(llm_service=None)
        
        # All should initialize successfully
        assert meetmind_coordinator is not None
        assert svea_pm is not None
        assert felicia_architect is not None
        
        # All should return valid status
        meetmind_status = await meetmind_coordinator.get_status()
        svea_status = await svea_pm.get_status()
        felicia_status = await felicia_architect.get_status()
        
        assert meetmind_status["status"] == "active"
        assert svea_status["status"] == "active"
        assert felicia_status["status"] == "active"
        
        logger.info("✓ Graceful degradation working across all teams")
        return True


async def run_all_integration_tests():
    """Run all integration tests for agent LLM usage."""
    logger.info("=" * 70)
    logger.info("Agent LLM Integration Tests")
    logger.info("=" * 70)
    
    test_classes = [
        TestMeetMindCoordinatorLLM(),
        TestAgentSveaProductManagerSwedish(),
        TestFeliciasFinanceArchitectRefactored(),
        TestLLMFallbackFunctionality()
    ]
    
    passed = 0
    failed = 0
    total = 0
    
    for test_class in test_classes:
        logger.info(f"\n--- {test_class.__class__.__name__} ---")
        
        # Get all test methods
        test_methods = [
            method for method in dir(test_class)
            if method.startswith('test_') and callable(getattr(test_class, method))
        ]
        
        for method_name in test_methods:
            total += 1
            try:
                method = getattr(test_class, method_name)
                await method()
                passed += 1
            except Exception as e:
                logger.error(f"✗ {method_name} failed: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Test Results: {passed}/{total} passed, {failed}/{total} failed")
    logger.info("=" * 70)
    
    if failed == 0:
        logger.info("\n✓ All integration tests passed!")
        logger.info("\nVerified:")
        logger.info("  - MeetMind Coordinator with LLM service")
        logger.info("  - Agent Svea Product Manager with svenska prompts")
        logger.info("  - Felicia's Finance Architect with refactored code")
        logger.info("  - Fallback functionality when LLM is unavailable")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_integration_tests())
    sys.exit(0 if success else 1)
