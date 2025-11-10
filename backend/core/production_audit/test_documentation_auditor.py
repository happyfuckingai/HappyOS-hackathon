"""Test for Documentation Auditor."""

import asyncio
import sys
from pathlib import Path

# Add workspace root to path
workspace_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from backend.core.production_audit.documentation_auditor import DocumentationAuditor


async def test_documentation_auditor():
    """Test the documentation auditor."""
    print("Testing Documentation Auditor...")
    print("=" * 60)
    
    # Get workspace root (3 levels up from this file)
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    # Create auditor
    auditor = DocumentationAuditor(workspace_root=str(workspace_root))
    
    # Run audit
    result = await auditor.audit()
    
    # Print results
    print(f"\nCategory: {result.category}")
    print(f"Score: {result.score:.2f}/100")
    print(f"Weight: {result.weight}")
    print(f"Timestamp: {result.timestamp}")
    
    print(f"\nChecks ({len(result.checks)}):")
    for check in result.checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"  {status} {check.name}: {check.score:.2f}/100")
        print(f"      {check.details}")
        if check.evidence:
            print(f"      Evidence: {len(check.evidence)} files")
            for evidence in check.evidence[:3]:  # Show first 3 evidence files
                print(f"        - {evidence}")
            if len(check.evidence) > 3:
                print(f"        ... and {len(check.evidence) - 3} more")
    
    print(f"\nGaps ({len(result.gaps)}):")
    for gap in result.gaps:
        print(f"  [{gap.severity.value.upper()}] {gap.description}")
        print(f"      Impact: {gap.impact}")
        print(f"      Recommendation: {gap.recommendation}")
        print(f"      Effort: {gap.estimated_effort}")
    
    print(f"\nRecommendations ({len(result.recommendations)}):")
    for rec in result.recommendations:
        print(f"  - {rec}")
    
    print("\n" + "=" * 60)
    print(f"Overall Assessment: {result.score:.2f}/100")
    
    if result.score >= 80:
        print("Status: ✓ PRODUCTION READY")
    elif result.score >= 60:
        print("Status: ⚠ ALMOST READY - Minor fixes required")
    else:
        print("Status: ✗ SIGNIFICANT WORK REQUIRED")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(test_documentation_auditor())
