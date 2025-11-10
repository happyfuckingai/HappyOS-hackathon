"""
Test MeetMind Quality Assurance Agent LLM Integration

Simple test to verify LLM integration works correctly.
"""

import asyncio
import os
from adk_agents.quality_assurance_agent import QualityAssuranceAgent


async def test_quality_assurance_agent_with_llm():
    """Test Quality Assurance Agent with LLM integration."""
    print("Testing MeetMind Quality Assurance Agent LLM Integration...")
    print("=" * 60)
    
    # Initialize agent
    agent = QualityAssuranceAgent()
    
    # Test 1: Get status
    print("\n1. Testing agent status...")
    status = await agent.get_status()
    print(f"   Status: {status['status']}")
    print(f"   LLM Integration: {status.get('llm_integration', 'unknown')}")
    assert status['status'] == 'active'
    assert status.get('llm_integration') == 'enabled'
    print("   ✓ Status check passed")
    
    # Test 2: Validate analysis quality (with fallback)
    print("\n2. Testing quality validation...")
    analysis_results = {
        "processed_data": {
            "summary": "Team discussed project status and assigned tasks",
            "key_topics": ["project status", "task assignment", "deadlines"],
            "action_items": [
                {
                    "task": "Complete API integration",
                    "assignee": "John",
                    "priority": "high",
                    "deadline": "Friday"
                }
            ],
            "decisions_made": ["Use AWS for hosting"],
            "sentiment": "positive"
        }
    }
    
    result = await agent.validate_analysis_quality(analysis_results)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    validation_result = result.get('validation_result', {})
    quality_metrics = validation_result.get('quality_metrics', {})
    print(f"   Overall Quality Score: {quality_metrics.get('overall_quality_score', 'N/A')}")
    print(f"   Passed Quality Gates: {validation_result.get('passed_quality_gates', False)}")
    
    if result.get('llm_used'):
        print("   ✓ LLM integration working")
    else:
        print("   ✓ Fallback logic working (LLM unavailable)")
    
    assert result['status'] == 'validation_completed'
    assert 'validation_result' in result
    
    # Test 3: Test system performance (with fallback)
    print("\n3. Testing performance testing...")
    test_scenarios = {
        "scenarios": [
            {
                "name": "high_load",
                "concurrent_meetings": 100,
                "participants_per_meeting": 50
            },
            {
                "name": "long_duration",
                "meeting_duration": "4 hours",
                "transcription_volume": "high"
            }
        ]
    }
    
    result = await agent.test_system_performance(test_scenarios)
    print(f"   Status: {result['status']}")
    print(f"   LLM Used: {result.get('llm_used', False)}")
    print(f"   Fallback: {result.get('fallback', False)}")
    
    performance_results = result.get('performance_results', {})
    latency_metrics = performance_results.get('latency_metrics', {})
    print(f"   Transcription Latency: {latency_metrics.get('transcription_latency', 'N/A')}")
    print(f"   Analysis Latency: {latency_metrics.get('analysis_latency', 'N/A')}")
    
    if result.get('llm_used'):
        print("   ✓ LLM-based performance testing working")
    else:
        print("   ✓ Fallback performance testing working (LLM unavailable)")
    
    assert result['status'] == 'performance_tested'
    assert 'performance_results' in result
    
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
        agent = QualityAssuranceAgent()
        
        # Test quality validation fallback
        print("\n1. Testing quality validation fallback...")
        analysis_results = {
            "processed_data": {
                "summary": "Test meeting summary",
                "key_topics": ["topic1", "topic2"],
                "action_items": [{"task": "test task"}]
            }
        }
        result = await agent.validate_analysis_quality(analysis_results)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        print("   ✓ Quality validation fallback working")
        
        # Test performance testing fallback
        print("\n2. Testing performance testing fallback...")
        test_scenarios = {"scenarios": [{"name": "test"}]}
        result = await agent.test_system_performance(test_scenarios)
        
        assert result.get('fallback') == True
        assert result.get('llm_used') == False
        print("   ✓ Performance testing fallback working")
        
        print("\n" + "=" * 60)
        print("Fallback tests passed! ✓")
        
    finally:
        # Restore API key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_quality_assurance_agent_with_llm())
    asyncio.run(test_fallback_logic())
