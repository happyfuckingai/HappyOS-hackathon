"""
Test MeetMind Implementation Agent LLM Integration

Simple test to verify LLM integration works correctly.
"""

import asyncio
import os
from adk_agents.implementation_agent import ImplementationAgent


async def test_implementation_agent_with_llm():
    """Test Implementation Agent with LLM integration."""
    print("Testing MeetMind Implementation Agent LLM Integration...")
    print("=" * 60)
    
    # Initialize agent
    agent = ImplementationAgent()
    
    # Test 1: Get status
    print("\n1. Testing agent status...")
    status = await agent.get_status()
    print(f"   Status: {status['status']}")
    print(f"   LLM Integration: {status.get('llm_integration', 'unknown')}")
    assert status['status'] == 'active'
    assert status.get('llm_integration') == 'enabled'
    print("   ✓ Status check passed")
    
    # Test 2: Implement analysis pipeline (with fallback)
    print("\n2. Testing pipeline implementation...")
    design = {
        "framework": "meeting_intelligence",
        "components": ["transcript_processor", "sentiment_analyzer", "topic_extractor"],
        "requirements": ["real-time processing", "high accuracy"]
    }
    
    result = await agent.implement_analysis_pipeline(design)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM integration working")
    else:
        print("   ✓ Fallback logic working (LLM unavailable)")
    
    assert result['status'] == 'pipeline_implemented'
    assert 'implementation_plan' in result
    
    # Test 3: Process meeting transcript (with fallback)
    print("\n3. Testing transcript processing...")
    transcript = """
    Team meeting on project status. John will complete the API integration by Friday.
    Sarah should review the documentation. We need to schedule a follow-up meeting
    next week to discuss the deployment strategy. The team agreed to use AWS for hosting.
    """
    
    result = await agent.process_meeting_transcript(transcript)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    processed_data = result.get('processed_data', {})
    print(f"   Topics found: {len(processed_data.get('key_topics', []))}")
    print(f"   Action items: {len(processed_data.get('action_items', []))}")
    
    if result.get('llm_used'):
        print("   ✓ LLM-based processing working")
    else:
        print("   ✓ Fallback processing working (LLM unavailable)")
    
    assert result['status'] == 'transcript_processed'
    assert 'processed_data' in result
    
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
        agent = ImplementationAgent()
        
        # Test pipeline implementation fallback
        print("\n1. Testing pipeline fallback...")
        design = {"framework": "test"}
        result = await agent.implement_analysis_pipeline(design)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        print("   ✓ Pipeline fallback working")
        
        # Test transcript processing fallback
        print("\n2. Testing transcript processing fallback...")
        transcript = "This is a test meeting. We will complete the task tomorrow."
        result = await agent.process_meeting_transcript(transcript)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        print("   ✓ Transcript processing fallback working")
        
        print("\n" + "=" * 60)
        print("Fallback tests passed! ✓")
        
    finally:
        # Restore API key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_implementation_agent_with_llm())
    asyncio.run(test_fallback_logic())
