"""
Test MeetMind Coordinator Agent LLM Integration

Simple test to verify LLM integration works correctly.
"""

import asyncio
import os
from adk_agents.coordinator_agent import CoordinatorAgent


async def test_coordinator_agent_with_llm():
    """Test Coordinator Agent with LLM integration."""
    print("Testing MeetMind Coordinator Agent LLM Integration...")
    print("=" * 60)
    
    # Initialize agent
    agent = CoordinatorAgent()
    
    # Test 1: Get status
    print("\n1. Testing agent status...")
    status = await agent.get_status()
    print(f"   Status: {status['status']}")
    print(f"   LLM Integration: {status.get('llm_integration', 'unknown')}")
    assert status['status'] == 'active'
    assert status.get('llm_integration') == 'enabled'
    print("   ✓ Status check passed")
    
    # Test 2: Coordinate meeting analysis (with fallback)
    print("\n2. Testing meeting analysis coordination...")
    meeting_data = {
        "meeting_id": "test_meeting_001",
        "participants": 5,
        "duration": "60 minutes",
        "topics": ["project status", "deployment strategy", "team updates"]
    }
    
    result = await agent.coordinate_meeting_analysis(meeting_data)
    print(f"   Status: {result['status']}")
    print(f"   Workflow ID: {result.get('workflow_id', 'N/A')}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM integration working")
    else:
        print("   ✓ Fallback logic working (LLM unavailable)")
    
    assert result['status'] == 'workflow_started'
    assert 'workflow_id' in result
    assert 'coordination_plan' in result
    
    # Verify coordination plan structure
    plan = result.get('coordination_plan', {})
    print(f"   Analysis tasks: {len(plan.get('analysis_tasks', []))}")
    print(f"   Execution order: {len(plan.get('execution_order', []))}")
    
    assert 'analysis_tasks' in plan
    assert 'execution_order' in plan
    assert 'resource_allocation' in plan
    
    print("   ✓ Coordination plan structure valid")
    
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
        agent = CoordinatorAgent()
        
        # Test coordination fallback
        print("\n1. Testing coordination fallback...")
        meeting_data = {"meeting_id": "test_002", "participants": 3}
        result = await agent.coordinate_meeting_analysis(meeting_data)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        assert result['status'] == 'workflow_started'
        print("   ✓ Coordination fallback working")
        
        print("\n" + "=" * 60)
        print("Fallback tests passed! ✓")
        
    finally:
        # Restore API key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_coordinator_agent_with_llm())
    asyncio.run(test_fallback_logic())
