"""Test for Infrastructure Resilience Auditor."""

import asyncio
import sys
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from backend.core.production_audit.infrastructure_resilience_auditor import InfrastructureResilienceAuditor


async def main():
    """Test the Infrastructure Resilience Auditor."""
    print("Testing Infrastructure Resilience Auditor...")
    print("=" * 80)
    
    # Get workspace root (3 levels up from this file)
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    # Create auditor
    auditor = InfrastructureResilienceAuditor(workspace_root=str(workspace_root))
    
    # Run audit
    result = await auditor.audit()
    
    # Print results
    print(f"\nCategory: {result.category}")
    print(f"Score: {result.score:.2f}/100")
    print(f"Weight: {result.weight}")
    print(f"Timestamp: {result.timestamp}")
    print()
    
    print("Checks:")
    print("-" * 80)
    for check in result.checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"{status} {check.name}: {check.score:.2f}/100")
        print(f"   {check.details}")
        if check.evidence:
            print(f"   Evidence: {len(check.evidence)} file(s)")
        print()
    
    print("Gaps:")
    print("-" * 80)
    if result.gaps:
        for gap in result.gaps:
            print(f"[{gap.severity.value.upper()}] {gap.description}")
            print(f"   Impact: {gap.impact}")
            print(f"   Recommendation: {gap.recommendation}")
            print(f"   Estimated effort: {gap.estimated_effort}")
            print()
    else:
        print("No gaps identified!")
        print()
    
    print("Recommendations:")
    print("-" * 80)
    for rec in result.recommendations:
        print(f"• {rec}")
    print()
    
    print("=" * 80)
    print(f"Overall Assessment: {result.score:.2f}/100")
    if result.score >= 80:
        print("Status: ✓ Production Ready")
    elif result.score >= 60:
        print("Status: ⚠ Almost Ready - Minor fixes required")
    else:
        print("Status: ✗ Significant Work Required")


if __name__ == "__main__":
    asyncio.run(main())
