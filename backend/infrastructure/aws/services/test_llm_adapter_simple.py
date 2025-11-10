"""
Simple standalone test for cost calculator (no external dependencies).
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, project_root)

from backend.core.llm.cost_calculator import LLMCostCalculator


def test_cost_calculator():
    """Test cost calculator functionality."""
    print("\n=== Testing Cost Calculator ===")
    
    # Test GPT-4 cost calculation
    cost = LLMCostCalculator.calculate_cost(
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50
    )
    print(f"✓ GPT-4 cost (100 input + 50 output tokens): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    assert cost == 0.006, f"Expected $0.006, got ${cost}"
    
    # Test Claude cost calculation
    cost = LLMCostCalculator.calculate_cost(
        model="claude-3-sonnet",
        prompt_tokens=100,
        completion_tokens=50
    )
    print(f"✓ Claude-3-Sonnet cost (100 input + 50 output tokens): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    
    # Test Gemini cost calculation
    cost = LLMCostCalculator.calculate_cost(
        model="gemini-1.5-flash",
        prompt_tokens=100,
        completion_tokens=50
    )
    print(f"✓ Gemini-1.5-Flash cost (100 input + 50 output tokens): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    
    # Test model comparison
    models = ["gpt-4", "gpt-3.5-turbo", "claude-3-haiku", "gemini-1.5-flash"]
    costs = LLMCostCalculator.compare_model_costs(models, 100, 50)
    print(f"\n✓ Model cost comparison (100 input + 50 output tokens):")
    for model, cost in sorted(costs.items(), key=lambda x: x[1]):
        print(f"    {model:20s}: ${cost:.6f}")
    
    # Test cheapest model
    cheapest_model, cheapest_cost = LLMCostCalculator.get_cheapest_model(models, 100, 50)
    print(f"\n✓ Cheapest model: {cheapest_model} at ${cheapest_cost:.6f}")
    assert cheapest_model in models, "Cheapest model should be in the list"
    
    # Test monthly cost estimation
    estimate = LLMCostCalculator.estimate_monthly_cost(
        model="gpt-4",
        requests_per_day=1000,
        avg_prompt_tokens=100,
        avg_completion_tokens=50
    )
    print(f"\n✓ Monthly cost estimate for GPT-4 (1000 req/day):")
    print(f"    Cost per request: ${estimate['cost_per_request']:.6f}")
    print(f"    Daily cost: ${estimate['daily_cost']:.2f}")
    print(f"    Monthly cost: ${estimate['monthly_cost']:.2f}")
    assert estimate['monthly_cost'] > 0, "Monthly cost should be positive"
    
    # Test total tokens calculation
    cost = LLMCostCalculator.calculate_cost_from_total_tokens(
        model="gpt-4",
        total_tokens=150,
        input_ratio=0.67  # 100 input, 50 output
    )
    print(f"\n✓ Cost from total tokens (150 total, 67% input): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    
    # Test model pricing retrieval
    pricing = LLMCostCalculator.get_model_pricing("gpt-4")
    print(f"\n✓ GPT-4 pricing info:")
    print(f"    Provider: {pricing.provider}")
    print(f"    Input: ${pricing.input_cost_per_1k:.4f}/1k tokens")
    print(f"    Output: ${pricing.output_cost_per_1k:.4f}/1k tokens")
    assert pricing is not None, "Should return pricing info"
    assert pricing.provider == "openai", "GPT-4 should be OpenAI"
    
    print("\n✓ All cost calculator tests passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Cost Calculator - Verification Tests")
    print("=" * 60)
    
    try:
        test_cost_calculator()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
