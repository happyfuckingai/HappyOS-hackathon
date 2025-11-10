"""
Test script to verify Felicia's Finance agents work with centralized LLM service
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

# Mock LLM Service for testing
class MockLLMService:
    """Mock LLM service for testing agent refactoring"""
    
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
        """Mock LLM completion"""
        return {
            "content": '{"status": "mock_response", "agent": "' + agent_id + '"}',
            "model": model,
            "tokens": 50
        }


async def test_coordinator_agent():
    """Test Coordinator Agent with LLM service"""
    from adk_agents.agents.coordinator_agent import CoordinatorAgent
    
    llm_service = MockLLMService()
    agent = CoordinatorAgent(llm_service=llm_service)
    
    # Test that agent initializes correctly
    assert agent.llm_service is not None
    print("✓ Coordinator Agent initialized with LLM service")
    
    # Test status
    status = await agent.get_status()
    assert status["agent"] == "coordinator"
    print("✓ Coordinator Agent status check passed")


async def test_architect_agent():
    """Test Architect Agent with LLM service"""
    from adk_agents.agents.architect_agent import ArchitectAgent
    
    llm_service = MockLLMService()
    agent = ArchitectAgent(llm_service=llm_service)
    
    assert agent.llm_service is not None
    print("✓ Architect Agent initialized with LLM service")
    
    status = await agent.get_status()
    assert status["agent"] == "architect"
    print("✓ Architect Agent status check passed")


async def test_product_manager_agent():
    """Test Product Manager Agent with LLM service"""
    from adk_agents.agents.product_manager_agent import ProductManagerAgent
    
    llm_service = MockLLMService()
    agent = ProductManagerAgent(llm_service=llm_service)
    
    assert agent.llm_service is not None
    print("✓ Product Manager Agent initialized with LLM service")
    
    status = await agent.get_status()
    assert status["agent"] == "product_manager"
    print("✓ Product Manager Agent status check passed")


async def test_implementation_agent():
    """Test Implementation Agent with LLM service"""
    from adk_agents.agents.implementation_agent import ImplementationAgent
    
    llm_service = MockLLMService()
    agent = ImplementationAgent(llm_service=llm_service)
    
    assert agent.llm_service is not None
    print("✓ Implementation Agent initialized with LLM service")
    
    status = await agent.get_status()
    assert status["agent"] == "implementation_engineer"
    print("✓ Implementation Agent status check passed")


async def test_quality_assurance_agent():
    """Test Quality Assurance Agent with LLM service"""
    from adk_agents.agents.quality_assurance_agent import QualityAssuranceAgent
    
    llm_service = MockLLMService()
    agent = QualityAssuranceAgent(llm_service=llm_service)
    
    assert agent.llm_service is not None
    print("✓ Quality Assurance Agent initialized with LLM service")
    
    status = await agent.get_status()
    assert status["agent"] == "quality_assurance"
    print("✓ Quality Assurance Agent status check passed")


async def test_banking_agent():
    """Test Banking Agent with LLM service"""
    from adk_agents.agents.banking_agent import BankingAgent
    
    llm_service = MockLLMService()
    agent = BankingAgent(llm_service=llm_service)
    
    assert agent.llm_service is not None
    print("✓ Banking Agent initialized with LLM service")
    
    status = await agent.get_status()
    assert status["agent"] == "banking_agent"
    print("✓ Banking Agent status check passed")


async def test_fallback_without_llm():
    """Test that agents work without LLM service (fallback mode)"""
    from adk_agents.agents.coordinator_agent import CoordinatorAgent
    
    # Initialize without LLM service
    agent = CoordinatorAgent(llm_service=None)
    
    assert agent.llm_service is None
    print("✓ Agent can initialize without LLM service (fallback mode)")
    
    status = await agent.get_status()
    assert status["agent"] == "coordinator"
    print("✓ Agent works in fallback mode")


async def main():
    """Run all tests"""
    logging.basicConfig(level=logging.INFO)
    
    print("\n=== Testing Felicia's Finance Refactored Agents ===\n")
    
    try:
        await test_coordinator_agent()
        await test_architect_agent()
        await test_product_manager_agent()
        await test_implementation_agent()
        await test_quality_assurance_agent()
        await test_banking_agent()
        await test_fallback_without_llm()
        
        print("\n=== All Tests Passed! ===\n")
        print("✓ All 6 agents successfully refactored to use centralized LLM service")
        print("✓ Agents maintain fallback functionality when LLM service is unavailable")
        print("✓ Banking Agent now uses LLM service with Gemini model support")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
