"""Tests for Testing Coverage Auditor."""

import asyncio
import sys
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from backend.core.production_audit.testing_coverage_auditor import TestingCoverageAuditor


async def test_testing_coverage_auditor():
    """Test the Testing Coverage Auditor."""
    print("=" * 80)
    print("Testing Coverage Auditor Test")
    print("=" * 80)
    
    # Initialize auditor with workspace root
    auditor = TestingCoverageAuditor(workspace_root=str(workspace_root))
    
    print(f"\nWorkspace root: {workspace_root}")
    print(f"Category: {auditor.get_category_name()}")
    print(f"Weight: {auditor.get_weight()}")
    
    # Run audit
    print("\nRunning audit...")
    result = await auditor.audit()
    
    # Print results
    print("\n" + "=" * 80)
    print(f"AUDIT RESULTS: {result.category}")
    print("=" * 80)
    print(f"Overall Score: {result.score:.2f}/100")
    print(f"Weight: {result.weight}")
    print(f"Timestamp: {result.timestamp}")
    
    print("\n" + "-" * 80)
    print("CHECKS:")
    print("-" * 80)
    for i, check in enumerate(result.checks, 1):
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"\n{i}. {check.name} [{status}]")
        print(f"   Score: {check.score:.2f}/100")
        print(f"   Details: {check.details}")
        if check.evidence:
            print(f"   Evidence: {len(check.evidence)} files")
            for evidence in check.evidence[:3]:
                print(f"     - {evidence}")
            if len(check.evidence) > 3:
                print(f"     ... and {len(check.evidence) - 3} more")
    
    print("\n" + "-" * 80)
    print("GAPS:")
    print("-" * 80)
    if result.gaps:
        for i, gap in enumerate(result.gaps, 1):
            print(f"\n{i}. [{gap.severity.value.upper()}] {gap.description}")
            print(f"   Impact: {gap.impact}")
            print(f"   Recommendation: {gap.recommendation}")
            print(f"   Estimated Effort: {gap.estimated_effort}")
    else:
        print("No gaps identified - testing coverage is excellent!")
    
    print("\n" + "-" * 80)
    print("RECOMMENDATIONS:")
    print("-" * 80)
    for i, rec in enumerate(result.recommendations, 1):
        print(f"{i}. {rec}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return result


if __name__ == "__main__":
    result = asyncio.run(test_testing_coverage_auditor())
    
    # Exit with appropriate code
    if result.score >= 80:
        print("\n✓ Testing coverage is PRODUCTION READY")
        sys.exit(0)
    elif result.score >= 60:
        print("\n⚠ Testing coverage is ALMOST READY - minor improvements needed")
        sys.exit(0)
    else:
        print("\n✗ Testing coverage needs SIGNIFICANT WORK")
        sys.exit(1)
