"""
Test LLM integration for Agent Svea agents with Swedish prompts.

This test verifies that all Agent Svea agents can:
1. Accept LLM service dependency injection
2. Use LLM for Swedish language processing
3. Fall back to rule-based logic when LLM is unavailable
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Add adk_agents directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'adk_agents'))

# Import Agent Svea agents
from coordinator_agent import CoordinatorAgent
from architect_agent import ArchitectAgent
from product_manager_agent import ProductManagerAgent
from implementation_agent import ImplementationAgent
from quality_assurance_agent import QualityAssuranceAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockLLMService:
    """Mock LLM service for testing."""
    
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
        """Mock LLM completion that returns Swedish JSON responses."""
        
        # Return mock Swedish responses based on agent
        if "coordinator" in agent_id:
            return {
                "content": """{
                    "workflow_prioritet": "hög",
                    "nödvändiga_steg": ["Validera BAS-konton", "Kontrollera momsberäkningar", "Generera SIE-export"],
                    "agent_delegering": {
                        "architect": "Designa teknisk arkitektur för svensk compliance",
                        "implementation": "Implementera BAS-kontoplan och momsberäkningar",
                        "qa": "Validera svensk regelverksefterlevnad"
                    },
                    "tidsuppskattning": "2-3 veckor",
                    "compliance_krav": ["BAS-kontoplan", "Svensk moms", "SIE-format"],
                    "risker": ["Regelverksändringar", "Integrationskomplexitet"]
                }""",
                "model": model,
                "tokens": 150
            }
        
        elif "architect" in agent_id:
            return {
                "content": """{
                    "erp_system": "ERPNext",
                    "svenska_anpassningar": ["BAS-kontoplan", "Svensk moms", "SIE-export"],
                    "moduler": ["accounting", "payroll", "reporting"],
                    "integrationer": ["Skatteverket API", "Bankgirot", "SIE-format"],
                    "compliance_funktioner": ["GDPR", "Bokföringslagen", "Momsrapportering"],
                    "teknisk_stack": {
                        "databas": "PostgreSQL",
                        "applikationsserver": "ERPNext med svenska anpassningar",
                        "cache": "Redis för prestanda"
                    },
                    "säkerhetsarkitektur": ["Kryptering", "Åtkomstkontroll", "Revisionslogg"],
                    "skalbarhet": "Horisontell skalning med lastbalansering",
                    "implementeringskrav": ["ERPNext setup", "Svenska lokaliseringar", "API-integrationer"],
                    "tidsuppskattning": "6-8 veckor"
                }""",
                "model": model,
                "tokens": 200
            }
        
        elif "product_manager" in agent_id:
            return {
                "content": """{
                    "regelverkstyp": "accounting_act",
                    "företagstyp": "general",
                    "obligatoriska_krav": ["BAS-kontoplan", "Dubbel bokföring", "10 års arkivering", "SIE-export", "Momsberäkning"],
                    "valfria_krav": ["Realtidsövervakning", "Automatisk rapportering"],
                    "implementeringsprioritet": "hög",
                    "compliance_deadline": "2024-12-31",
                    "konsekvensanalys": {
                        "utvecklingsinsats": "6-12 månader",
                        "compliance_risk": "hög",
                        "affärspåverkan": "kritisk för svensk verksamhet",
                        "teknisk_komplexitet": "medel till hög"
                    },
                    "specifika_svenska_krav": ["BAS 2019", "K-rapporter", "Skatteverkets krav"],
                    "myndighetsintegration": ["Skatteverket", "Bolagsverket"]
                }""",
                "model": model,
                "tokens": 180
            }
        
        elif "implementation" in agent_id:
            return {
                "content": """{
                    "anpassningstyp": "swedish_company_setup",
                    "implementeringssteg": ["Skapa anpassade fält", "Implementera BAS-kontoplan", "Lägg till svensk moms", "Skapa SIE-export"],
                    "filer_att_modifiera": ["accounts/account.py", "regional/sweden/setup.py"],
                    "databasändringar": ["Lägg till svenska momsfält", "Skapa BAS-mappningstabell"],
                    "svensk_bokföringslogik": ["BAS-kontovalidering", "Svensk momsberäkning"],
                    "bas_kontointegration": "4-siffriga BAS-kontonummer med typvalidering",
                    "sie_exportfunktionalitet": "SIE Type 4 format med intelligent mappning",
                    "skatteverket_integration": "API-integration för momsrapportering",
                    "testplan": ["Enhetstester", "Integrationstester", "Compliance-tester"],
                    "tidsuppskattning": "4-6 veckor",
                    "risker": ["API-ändringar", "Regelverksuppdateringar"]
                }""",
                "model": model,
                "tokens": 190
            }
        
        elif "quality_assurance" in agent_id:
            return {
                "content": """{
                    "compliance_typ": "bas_accounting",
                    "testscenarier": ["Validera kontostruktur", "Testa kontonummerformat", "Verifiera kontotypmappning", "Kontrollera balansräkning"],
                    "valideringskriterier": ["BAS-standard", "Svensk bokföringslag", "Momsregler"],
                    "svenska_regelverkskrav": ["BAS 2019", "Bokföringslagen", "Skatteverkets krav"],
                    "kritiska_kontrollpunkter": ["Kontonummervalidering", "Momsberäkningar", "SIE-format"],
                    "förväntade_resultat": {
                        "bas_kontovalidering": "100% överensstämmelse med BAS 2019",
                        "moms_beräkningar": "Korrekt för alla svenska momssatser (25%, 12%, 6%, 0%)",
                        "sie_format": "SIE Type 4 compliance"
                    },
                    "riskområden": ["Regelverksändringar", "Integrationsproblem"],
                    "rekommendationer": ["Automatiserad testning", "Kontinuerlig övervakning", "Regelverksuppdateringar"]
                }""",
                "model": model,
                "tokens": 170
            }
        
        return {
            "content": '{"status": "mock_response"}',
            "model": model,
            "tokens": 10
        }


async def test_coordinator_llm_integration():
    """Test Coordinator Agent LLM integration with Swedish prompts."""
    logger.info("Testing Coordinator Agent LLM integration...")
    
    # Create mock LLM service
    mock_llm = MockLLMService()
    
    # Create coordinator with LLM service
    coordinator = CoordinatorAgent(services={"llm_service": mock_llm})
    
    # Test compliance workflow coordination
    payload = {
        "compliance_type": "bas_accounting",
        "tenant_id": "test_tenant",
        "account_data": {"account_number": "1510"}
    }
    
    result = await coordinator._coordinate_compliance_workflow(payload)
    
    assert result["status"] == "workflow_coordinated"
    assert result.get("llm_enhanced") == True
    assert "coordination_plan" in result
    assert "workflow_prioritet" in result["coordination_plan"]
    
    logger.info("✓ Coordinator Agent LLM integration working")
    return True


async def test_architect_llm_integration():
    """Test Architect Agent LLM integration with Swedish prompts."""
    logger.info("Testing Architect Agent LLM integration...")
    
    mock_llm = MockLLMService()
    architect = ArchitectAgent(services={"llm_service": mock_llm})
    
    payload = {
        "company_type": "general",
        "modules": ["accounting", "payroll"],
        "tenant_id": "test_tenant"
    }
    
    result = await architect._design_erp_architecture(payload)
    
    assert result["status"] == "erp_architecture_designed"
    assert result.get("llm_enhanced") == True
    assert "architecture" in result
    assert "svenska_anpassningar" in result["architecture"]
    
    logger.info("✓ Architect Agent LLM integration working")
    return True


async def test_product_manager_llm_integration():
    """Test Product Manager Agent LLM integration with Swedish prompts."""
    logger.info("Testing Product Manager Agent LLM integration...")
    
    mock_llm = MockLLMService()
    pm = ProductManagerAgent(services={"llm_service": mock_llm})
    
    payload = {
        "regulation_type": "accounting_act",
        "business_type": "general",
        "tenant_id": "test_tenant"
    }
    
    result = await pm._analyze_regulatory_requirements(payload)
    
    assert result["status"] == "regulatory_requirements_analyzed"
    assert result.get("llm_enhanced") == True
    assert "analysis" in result
    assert "obligatoriska_krav" in result["analysis"]
    
    logger.info("✓ Product Manager Agent LLM integration working")
    return True


async def test_implementation_llm_integration():
    """Test Implementation Agent LLM integration with Swedish prompts."""
    logger.info("Testing Implementation Agent LLM integration...")
    
    mock_llm = MockLLMService()
    impl = ImplementationAgent(services={"llm_service": mock_llm})
    
    payload = {
        "customization_type": "swedish_company_setup",
        "requirements": ["BAS chart of accounts", "Swedish VAT"],
        "tenant_id": "test_tenant"
    }
    
    result = await impl._implement_erp_customization(payload)
    
    assert result["status"] == "erp_customization_implemented"
    assert result.get("llm_enhanced") == True
    assert "implementation_plan" in result
    assert "implementeringssteg" in result["implementation_plan"]
    
    logger.info("✓ Implementation Agent LLM integration working")
    return True


async def test_qa_llm_integration():
    """Test Quality Assurance Agent LLM integration with Swedish prompts."""
    logger.info("Testing Quality Assurance Agent LLM integration...")
    
    mock_llm = MockLLMService()
    qa = QualityAssuranceAgent(services={"llm_service": mock_llm})
    
    payload = {
        "compliance_type": "bas_accounting",
        "test_data": {"account_number": "1510"},
        "tenant_id": "test_tenant"
    }
    
    result = await qa._validate_compliance_accuracy(payload)
    
    assert result["status"] == "compliance_validation_completed"
    assert result.get("llm_enhanced") == True
    assert "validation_results" in result
    
    logger.info("✓ Quality Assurance Agent LLM integration working")
    return True


async def test_fallback_without_llm():
    """Test that agents fall back to rule-based logic without LLM."""
    logger.info("Testing fallback logic without LLM...")
    
    # Create agents without LLM service
    coordinator = CoordinatorAgent(services={})
    
    payload = {
        "compliance_type": "bas_accounting",
        "tenant_id": "test_tenant"
    }
    
    result = await coordinator._coordinate_compliance_workflow(payload)
    
    assert result["status"] == "workflow_coordinated"
    assert result.get("llm_enhanced") == False
    assert result.get("fallback_used") == True
    
    logger.info("✓ Fallback logic working correctly")
    return True


async def test_agent_status():
    """Test that agent status reflects LLM integration."""
    logger.info("Testing agent status with LLM integration...")
    
    mock_llm = MockLLMService()
    coordinator = CoordinatorAgent(services={"llm_service": mock_llm})
    
    status = await coordinator.get_status()
    
    assert status["services_available"]["llm_service"] == True
    assert status["llm_integration"]["enabled"] == True
    assert status["llm_integration"]["language"] == "svenska"
    assert status["llm_integration"]["fallback_available"] == True
    
    logger.info("✓ Agent status correctly reflects LLM integration")
    return True


async def run_all_tests():
    """Run all LLM integration tests."""
    logger.info("=" * 60)
    logger.info("Agent Svea LLM Integration Tests")
    logger.info("=" * 60)
    
    tests = [
        test_coordinator_llm_integration,
        test_architect_llm_integration,
        test_product_manager_llm_integration,
        test_implementation_llm_integration,
        test_qa_llm_integration,
        test_fallback_without_llm,
        test_agent_status
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            logger.error(f"✗ Test {test.__name__} failed: {e}")
            failed += 1
    
    logger.info("=" * 60)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
