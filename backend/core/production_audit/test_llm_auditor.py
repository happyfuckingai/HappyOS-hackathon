"""Test script for LLM Integration Auditor."""

import asyncio
import sys
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from backend.core.production_audit.llm_integration_auditor import LLMIntegrationAuditor


async def test_llm_auditor():
    """Test the LLM Integration Auditor."""
    print("=" * 80)
    print("Testing LLM Integration Auditor")
    print("=" * 80)
    
    # Get workspace root (3 levels up from this file)
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    # Create auditor
    auditor = LLMIntegrationAuditor(workspace_root=str(workspace_root))
    
    print(f"\nWorkspace root: {workspace_root}")
    print(f"Category: {auditor.get_category_name()}")
    print(f"Weight: {auditor.get_weight()}")
    
    # Run audit
    print("\nRunning audit...")
    result = await auditor.audit()
    
    # Display results
    print("\n" + "=" * 80)
    print(f"AUDIT RESULTS: {result.category}")
    print("=" * 80)
    print(f"Overall Score: {result.score:.2f}/100")
    print(f"Weight: {result.weight}")
    print(f"Timestamp: {result.timestamp}")
    
    print("\n" + "-" * 80)
    print("CHECK RESULTS:")
    print("-" * 80)
    for check in result.checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"\n{status} {check.name} - Score: {check.score:.2f}/100")
        print(f"  Details: {check.details}")
        if check.evidence:
            print(f"  Evidence ({len(check.evidence)} files):")
            for evidence in check.evidence[:3]:  # Show first 3
                print(f"    - {evidence}")
            if len(check.evidence) > 3:
                print(f"    ... and {len(check.evidence) - 3} more")
    
    print("\n" + "-" * 80)
    print(f"GAPS IDENTIFIED: {len(result.gaps)}")
    print("-" * 80)
    for i, gap in enumerate(result.gaps, 1):
        print(f"\n{i}. [{gap.severity.value.upper()}] {gap.description}")
        print(f"   Impact: {gap.impact}")
        print(f"   Recommendation: {gap.recommendation}")
        print(f"   Estimated Effort: {gap.estimated_effort}")
    
    print("\n" + "-" * 80)
    print("RECOMMENDATIONS:")
    print("-" * 80)
    for i, rec in enumerate(result.recommendations, 1):
        print(f"{i}. {rec}")
    
    print("\n" + "=" * 80)
    print("Test completed successfully!")
    print("=" * 80)
    
    return result


if __name__ == "__main__":
    asyncio.run(test_llm_auditor())
