# Deployment Readiness Auditor - Usage Guide

## Quick Start

### Running the Auditor

```python
import asyncio
from backend.core.production_audit.deployment_readiness_auditor import DeploymentReadinessAuditor

async def run_audit():
    # Create auditor instance
    auditor = DeploymentReadinessAuditor(workspace_root=".")
    
    # Run the audit
    result = await auditor.audit()
    
    # Print summary
    print(f"Category: {result.category}")
    print(f"Score: {result.score:.2f}/100")
    print(f"Status: {'PASS' if result.score >= 80 else 'NEEDS WORK'}")
    
    return result

# Run the audit
result = asyncio.run(run_audit())
```

### Using the Test Script

```bash
# Run the test script
python3 backend/core/production_audit/test_deployment_auditor.py
```

## What It Checks

### 1. Docker Images and Containerization
- Searches for Dockerfiles across the project
- Checks for docker-compose configuration
- Validates multi-stage builds
- Verifies proper base images

**Scoring:**
- Has Dockerfiles: 25%
- Has docker-compose: 25%
- Uses multi-stage builds: 25%
- Proper base images: 25%

### 2. AWS CDK Infrastructure Code
- Validates CDK app entry point (app.py)
- Checks for cdk.json configuration
- Counts infrastructure stacks
- Verifies stack coverage (VPC, Lambda, API Gateway, etc.)
- Checks for requirements.txt and README
- Validates synthesis capability

**Scoring:**
- Has app.py: 14%
- Has cdk.json: 14%
- Has 5+ stacks: 14%
- 60%+ stack coverage: 14%
- Has requirements.txt: 14%
- Has README: 14%
- Can synthesize: 14%

### 3. Deployment Guide Documentation
- Checks for required sections:
  - Prerequisites
  - Local Setup
  - AWS Setup
  - Production Deployment
  - Monitoring
  - Troubleshooting
  - Rollback
- Validates code examples
- Checks AWS service coverage
- Verifies environment configuration
- Validates health check documentation

**Scoring:**
- 70%+ sections present: 20%
- Has code examples: 20%
- 60%+ AWS service coverage: 20%
- Has environment config: 20%
- Has health check docs: 20%

### 4. Rollback Procedures
- Checks for rollback section in deployment guide
- Validates documented rollback procedures
- Searches for rollback scripts
- Verifies CDK rollback support

**Scoring:**
- Has rollback section: 25%
- 3+ procedures documented: 25%
- Has rollback scripts: 25%
- CDK rollback support: 25%

### 5. Health Check Endpoints
- Searches for health endpoint implementations
- Checks backend routes
- Validates agent MCP server health checks
- Verifies main application health endpoint
- Checks for unified health monitoring
- Validates health check documentation

**Scoring:**
- Has health routes: 20%
- 3+ services with health checks: 20%
- Main app health endpoint: 20%
- Unified health endpoint: 20%
- Health check documentation: 20%

## Understanding the Results

### AuditResult Object

```python
@dataclass
class AuditResult:
    category: str              # "Deployment Readiness"
    score: float              # 0-100
    weight: float             # 0.15 (15% of overall score)
    checks: List[CheckResult] # Individual check results
    gaps: List[Gap]           # Identified gaps
    recommendations: List[str] # Actionable recommendations
    timestamp: datetime       # When audit was run
```

### CheckResult Object

```python
@dataclass
class CheckResult:
    name: str          # Check name
    passed: bool       # True if check passed
    score: float       # 0-100
    details: str       # Human-readable details
    evidence: List[str] # File paths as evidence
```

### Gap Object

```python
@dataclass
class Gap:
    category: str           # "Deployment Readiness"
    severity: GapSeverity  # CRITICAL, HIGH, MEDIUM, LOW
    description: str       # What's missing
    impact: str           # Impact of the gap
    recommendation: str   # How to fix it
    estimated_effort: str # Time estimate
    dependencies: List[str] # Dependencies
```

## Interpreting Scores

### Overall Score Ranges

- **80-100**: Production Ready ✓
  - All critical checks pass
  - Minor improvements optional
  - Safe to deploy to production

- **60-79**: Almost Ready ⚠
  - Most checks pass
  - Some improvements needed
  - Can deploy with caution

- **0-59**: Significant Work Required ✗
  - Multiple checks fail
  - Critical gaps present
  - Not ready for production

### Individual Check Scores

Each check is scored 0-100:
- **100**: Perfect implementation
- **75-99**: Good, minor improvements possible
- **50-74**: Acceptable, some work needed
- **25-49**: Needs improvement
- **0-24**: Critical issues

## Example Output

```
Testing Deployment Readiness Auditor...
============================================================

Category: Deployment Readiness
Score: 86.00/100
Weight: 0.15
Timestamp: 2025-11-10 14:14:43

Checks (5):
  ✓ PASS Docker Images and Containerization: 50.00/100
      Containerization: 1 Dockerfiles found, 0 docker-compose files, 0 with multi-stage builds
      Evidence: 1 files
      
  ✓ PASS AWS CDK Infrastructure Code: 100.00/100
      AWS CDK: 9 stacks found (100% coverage of expected stacks), can synthesize
      Evidence: 13 files
      
  ✓ PASS Deployment Guide Documentation: 100.00/100
      Deployment guide: 7/7 required sections, 100% AWS service coverage, includes code examples
      Evidence: 1 files
      
  ✓ PASS Rollback Procedures: 100.00/100
      Rollback procedures: 4 procedures documented, 1 rollback scripts, has CDK rollback support
      Evidence: 3 files
      
  ✓ PASS Health Check Endpoints: 80.00/100
      Health endpoints: 15 services with health checks, includes unified health endpoint, documented
      Evidence: 15 files

Gaps (0):

Recommendations (1):
  - Deployment infrastructure is production-ready

Overall Assessment: 86.00/100
Status: ✓ PRODUCTION READY
```

## Common Issues and Solutions

### Issue: Low Docker Score

**Problem:** Only 1 Dockerfile found, no docker-compose

**Solution:**
1. Create Dockerfiles for each service:
   - `backend/Dockerfile` - Main backend application
   - `backend/agents/meetmind/Dockerfile` - MeetMind agents
   - `backend/agents/agent_svea/Dockerfile` - Agent Svea
2. Create `docker-compose.yml` for local development
3. Implement multi-stage builds to reduce image size

### Issue: Missing Rollback Procedures

**Problem:** Rollback section not found in deployment guide

**Solution:**
1. Add "Rollback Procedures" section to deployment guide
2. Document at least 3 rollback scenarios:
   - Rollback to previous version
   - Emergency disable
   - Restore from backup
3. Create rollback scripts in `scripts/` directory
4. Test rollback procedures

### Issue: No Health Endpoints

**Problem:** Health check endpoints not found

**Solution:**
1. Add health endpoint to main application:
   ```python
   @app.get("/health")
   async def health_check():
       return {"status": "healthy"}
   ```
2. Add health endpoints to each agent MCP server
3. Create unified health endpoint that aggregates all services
4. Document health check usage in deployment guide

## Integration with Full Audit

The Deployment Readiness Auditor is part of the complete production readiness audit framework:

```python
from backend.core.production_audit.deployment_readiness_auditor import DeploymentReadinessAuditor
from backend.core.production_audit.llm_integration_auditor import LLMIntegrationAuditor
# ... other auditors

async def run_full_audit():
    auditors = [
        LLMIntegrationAuditor(),
        DeploymentReadinessAuditor(),
        # ... other auditors
    ]
    
    results = []
    for auditor in auditors:
        result = await auditor.audit()
        results.append(result)
    
    # Calculate overall score
    overall_score = sum(r.score * r.weight for r in results)
    
    return overall_score, results
```

## Requirements Coverage

This auditor satisfies the following requirements from the spec:

- **Requirement 6.1**: Verifies Docker images through Dockerfile analysis
- **Requirement 6.2**: Checks AWS CDK code completeness
- **Requirement 6.3**: Validates deployment guide documentation
- **Requirement 6.4**: Confirms rollback procedures are documented
- **Requirement 6.5**: Verifies health check endpoints exist

## Next Steps

After running the Deployment Readiness Auditor:

1. Review the score and individual check results
2. Address any identified gaps (prioritize CRITICAL and HIGH severity)
3. Implement recommendations
4. Re-run the audit to verify improvements
5. Proceed with other auditors (Documentation, Performance, etc.)

## Support

For issues or questions:
- Check the implementation: `backend/core/production_audit/deployment_readiness_auditor.py`
- Review test script: `backend/core/production_audit/test_deployment_auditor.py`
- See summary: `backend/core/production_audit/DEPLOYMENT_READINESS_AUDITOR_SUMMARY.md`

---

**Last Updated:** November 10, 2025  
**Version:** 1.0.0  
**Status:** Production Ready
