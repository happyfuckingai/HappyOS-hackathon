"""
Test MeetMind Architect Agent LLM Integration

Simple test to verify LLM integration works correctly.
"""

import asyncio
import os
from adk_agents.architect_agent import ArchitectAgent


async def test_architect_agent_with_llm():
    """Test Architect Agent with LLM integration."""
    print("Testing MeetMind Architect Agent LLM Integration...")
    print("=" * 60)
    
    # Initialize agent
    agent = ArchitectAgent()
    
    # Test 1: Get status
    print("\n1. Testing agent status...")
    status = await agent.get_status()
    print(f"   Status: {status['status']}")
    print(f"   LLM Integration: {status.get('llm_integration', 'unknown')}")
    assert status['status'] == 'active'
    assert status.get('llm_integration') == 'enabled'
    print("   ✓ Status check passed")
    
    # Test 2: Design analysis framework (with fallback)
    print("\n2. Testing analysis framework design...")
    requirements = {
        "functional_requirements": [
            "real_time_transcription",
            "automatic_summarization",
            "action_item_extraction"
        ],
        "non_functional_requirements": [
            "low_latency_processing",
            "high_accuracy",
            "scalable_architecture"
        ],
        "constraints": [
            "must integrate with LiveKit",
            "must use AWS services"
        ]
    }
    
    result = await agent.design_analysis_framework(requirements)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM integration working")
    else:
        print("   ✓ Fallback logic working (LLM unavailable)")
    
    assert result['status'] == 'framework_designed'
    assert 'framework' in result
    
    # Verify framework structure
    framework = result.get('framework', {})
    print(f"   Components: {len(framework.get('components', []))}")
    print(f"   Integration points: {len(framework.get('integration_points', []))}")
    
    assert 'components' in framework
    assert 'data_flow' in framework
    assert 'scalability_strategy' in framework
    
    print("   ✓ Framework structure valid")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("\nNote: If OPENAI_API_KEY is not set, fallback logic is used.")
    print("      This is expected behavior and demonstrates resilience.")


async def test_fallback_logic():
    """Test that fallback logic works without LLM."""
    print("\n\nTesting Fallback Logic (without LLM)...")
    print("=" * 60)
    
    # Temporarily remove API key to force fallback
    original_key = os.environ.get('OPENAI_API_KEY')
    if original_key:
        del os.environ['OPENAI_API_KEY']
    
    try:
        agent = ArchitectAgent()
        
        # Test framework design fallback
        print("\n1. Testing framework design fallback...")
        requirements = {"functional_requirements": ["test_requirement"]}
        result = await agent.design_analysis_framework(requirements)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        assert result['status'] == 'framework_designed'
        print("   ✓ Framework design fallback working")
        
        print("\n" + "=" * 60)
        print("Fallback tests passed! ✓")
        
    finally:
        # Restore API key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_architect_agent_with_llm())
    asyncio.run(test_fallback_logic())
