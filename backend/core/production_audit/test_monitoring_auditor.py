"""Test for Monitoring and Observability Auditor."""

import asyncio
import sys
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from backend.core.production_audit.monitoring_observability_auditor import MonitoringObservabilityAuditor


async def test_monitoring_auditor():
    """Test the monitoring and observability auditor."""
    print("Testing Monitoring and Observability Auditor...")
    print("=" * 80)
    
    # Get workspace root (3 levels up from this file)
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    # Create auditor
    auditor = MonitoringObservabilityAuditor(workspace_root=str(workspace_root))
    
    # Run audit
    result = await auditor.audit()
    
    # Print results
    print(f"\nCategory: {result.category}")
    print(f"Score: {result.score:.2f}/100")
    print(f"Weight: {result.weight}")
    print(f"\nChecks ({len(result.checks)}):")
    print("-" * 80)
    
    for check in result.checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"{status} {check.name}: {check.score:.2f}/100")
        print(f"   Details: {check.details}")
        if check.evidence:
            print(f"   Evidence: {len(check.evidence)} files")
            for evidence in check.evidence[:3]:  # Show first 3
                print(f"     - {evidence}")
            if len(check.evidence) > 3:
                print(f"     ... and {len(check.evidence) - 3} more")
        print()
    
    print(f"\nGaps ({len(result.gaps)}):")
    print("-" * 80)
    
    for gap in result.gaps:
        print(f"[{gap.severity.value.upper()}] {gap.description}")
        print(f"   Impact: {gap.impact}")
        print(f"   Recommendation: {gap.recommendation}")
        print(f"   Estimated effort: {gap.estimated_effort}")
        print()
    
    print(f"\nRecommendations:")
    print("-" * 80)
    for rec in result.recommendations:
        print(f"• {rec}")
    
    print("\n" + "=" * 80)
    print(f"Overall Assessment: {result.score:.2f}/100")
    
    if result.score >= 80:
        print("Status: ✓ Production Ready")
    elif result.score >= 60:
        print("Status: ⚠ Almost Ready - Minor fixes required")
    else:
        print("Status: ✗ Significant Work Required")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(test_monitoring_auditor())
    
    # Exit with appropriate code
    sys.exit(0 if result.score >= 60 else 1)
