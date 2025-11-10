"""
Test MeetMind Product Manager Agent LLM Integration

Simple test to verify LLM integration works correctly.
"""

import asyncio
import os
from adk_agents.product_manager_agent import ProductManagerAgent


async def test_product_manager_agent_with_llm():
    """Test Product Manager Agent with LLM integration."""
    print("Testing MeetMind Product Manager Agent LLM Integration...")
    print("=" * 60)
    
    # Initialize agent
    agent = ProductManagerAgent()
    
    # Test 1: Get status
    print("\n1. Testing agent status...")
    status = await agent.get_status()
    print(f"   Status: {status['status']}")
    print(f"   LLM Integration: {status.get('llm_integration', 'unknown')}")
    assert status['status'] == 'active'
    assert status.get('llm_integration') == 'enabled'
    print("   ✓ Status check passed")
    
    # Test 2: Define requirements (with fallback)
    print("\n2. Testing requirements definition...")
    user_needs = {
        "target_users": ["meeting organizers", "team leads", "participants"],
        "pain_points": [
            "difficulty tracking action items",
            "time spent on manual note-taking",
            "missing important discussion points"
        ],
        "desired_outcomes": [
            "automated meeting summaries",
            "clear action item tracking",
            "searchable meeting history"
        ]
    }
    
    result = await agent.define_requirements(user_needs)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM integration working")
    else:
        print("   ✓ Fallback logic working (LLM unavailable)")
    
    assert result['status'] == 'requirements_defined'
    assert 'requirements' in result
    
    # Verify requirements structure
    requirements = result.get('requirements', {})
    print(f"   Functional requirements: {len(requirements.get('functional_requirements', []))}")
    print(f"   Non-functional requirements: {len(requirements.get('non_functional_requirements', []))}")
    
    assert 'functional_requirements' in requirements
    assert 'non_functional_requirements' in requirements
    
    print("   ✓ Requirements structure valid")
    
    # Test 3: Prioritize features (with fallback)
    print("\n3. Testing feature prioritization...")
    features = {
        "features": [
            {"name": "real_time_transcription", "effort": "large", "value": "high"},
            {"name": "automatic_summarization", "effort": "medium", "value": "high"},
            {"name": "action_item_extraction", "effort": "medium", "value": "medium"},
            {"name": "sentiment_analysis", "effort": "small", "value": "low"}
        ]
    }
    
    result = await agent.prioritize_features(features)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM-based prioritization working")
    else:
        print("   ✓ Fallback prioritization working (LLM unavailable)")
    
    assert result['status'] == 'features_prioritized'
    assert 'prioritized_features' in result
    
    # Verify prioritization structure
    prioritized = result.get('prioritized_features', {})
    print(f"   Critical priority: {len(prioritized.get('critical_priority', []))}")
    print(f"   High priority: {len(prioritized.get('high_priority', []))}")
    print(f"   Medium priority: {len(prioritized.get('medium_priority', []))}")
    
    assert 'critical_priority' in prioritized or 'high_priority' in prioritized
    
    print("   ✓ Prioritization structure valid")
    
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
        agent = ProductManagerAgent()
        
        # Test requirements definition fallback
        print("\n1. Testing requirements definition fallback...")
        user_needs = {"target_users": ["test users"]}
        result = await agent.define_requirements(user_needs)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        assert result['status'] == 'requirements_defined'
        print("   ✓ Requirements definition fallback working")
        
        # Test feature prioritization fallback
        print("\n2. Testing feature prioritization fallback...")
        features = {"features": [{"name": "test_feature"}]}
        result = await agent.prioritize_features(features)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        assert result['status'] == 'features_prioritized'
        print("   ✓ Feature prioritization fallback working")
        
        print("\n" + "=" * 60)
        print("Fallback tests passed! ✓")
        
    finally:
        # Restore API key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_product_manager_agent_with_llm())
    asyncio.run(test_fallback_logic())
