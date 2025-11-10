"""Deployment Readiness Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class DeploymentReadinessAuditor(AuditModule):
    """
    Auditor for deployment readiness.
    
    Evaluates:
    - Docker images and containerization
    - AWS CDK infrastructure code
    - Deployment guide documentation
    - Rollback procedures
    - Health check endpoints
    """
    
    CATEGORY_NAME = "Deployment Readiness"
    CATEGORY_WEIGHT = 0.15  # 15% of overall score
    
    def __init__(self, workspace_root: str = None):
        """Initialize Deployment Readiness Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.docs_path = Path(self.workspace_root) / "docs"
        self.iac_path = self.backend_path / "infrastructure" / "aws" / "iac"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform deployment readiness audit."""
        logger.info("Starting Deployment Readiness audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: Docker Images
        docker_check = await self._check_docker_images()
        checks.append(docker_check)
        if not docker_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Incomplete Docker containerization",
                impact="Cannot deploy to production without proper containerization",
                recommendation="Create Dockerfiles for all services and test image builds",
                estimated_effort="2-3 days"
            ))
        
        # Check 2: AWS CDK Infrastructure Code
        cdk_check = await self._check_aws_cdk_code()
        checks.append(cdk_check)
        if not cdk_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="AWS CDK infrastructure code is incomplete or missing",
                impact="Cannot provision AWS infrastructure for production deployment",
                recommendation="Complete AWS CDK stacks for all required infrastructure components",
                estimated_effort="3-5 days"
            ))
        
        # Check 3: Deployment Guide
        deployment_guide_check = await self._check_deployment_guide()
        checks.append(deployment_guide_check)
        if not deployment_guide_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Deployment guide is incomplete or missing critical sections",
                impact="Team may struggle with deployment, increasing risk of errors",
                recommendation="Complete deployment guide with all required sections and examples",
                estimated_effort="1-2 days"
            ))
        
        # Check 4: Rollback Procedures
        rollback_check = await self._check_rollback_procedures()
        checks.append(rollback_check)
        if not rollback_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Rollback procedures are not documented or incomplete",
                impact="Cannot safely recover from failed deployments, risking extended downtime",
                recommendation="Document comprehensive rollback procedures for all deployment scenarios",
                estimated_effort="1-2 days"
            ))
        
        # Check 5: Health Check Endpoints
        health_check = await self._check_health_endpoints()
        checks.append(health_check)
        if not health_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Health check endpoints are missing or incomplete",
                impact="Cannot monitor service health or perform automated health checks",
                recommendation="Implement /health endpoints for all services with proper status reporting",
                estimated_effort="1-2 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Deployment infrastructure is production-ready")
        else:
            recommendations.append("Complete Docker containerization for all services")
            recommendations.append("Ensure AWS CDK infrastructure code is complete and tested")
            recommendations.append("Document comprehensive rollback procedures")
            recommendations.append("Implement health check endpoints for all services")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Deployment Readiness audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_docker_images(self) -> CheckResult:
        """Check Docker images and containerization."""
        dockerfiles = []
        evidence = []
        
        # Search for Dockerfiles
        for dockerfile in Path(self.workspace_root).rglob("Dockerfile*"):
            # Skip hidden directories and test files
            if any(part.startswith('.') for part in dockerfile.parts):
                continue
            
            dockerfiles.append(dockerfile)
            evidence.append(f"{dockerfile.relative_to(self.workspace_root)}")
        
        # Check for docker-compose files
        docker_compose_files = []
        for compose_file in Path(self.workspace_root).rglob("docker-compose*.yml"):
            if any(part.startswith('.') for part in compose_file.parts):
                continue
            docker_compose_files.append(compose_file)
            evidence.append(f"{compose_file.relative_to(self.workspace_root)}")
        
        for compose_file in Path(self.workspace_root).rglob("docker-compose*.yaml"):
            if any(part.startswith('.') for part in compose_file.parts):
                continue
            docker_compose_files.append(compose_file)
            evidence.append(f"{compose_file.relative_to(self.workspace_root)}")
        
        # Analyze Dockerfile quality
        multi_stage_builds = 0
        proper_base_images = 0
        
        for dockerfile in dockerfiles:
            try:
                content = dockerfile.read_text()
                
                # Check for multi-stage builds
                if re.search(r'FROM.*AS\s+\w+', content, re.IGNORECASE):
                    multi_stage_builds += 1
                
                # Check for proper base images (python, node, etc.)
                if re.search(r'FROM\s+(python|node|alpine|ubuntu|debian):', content, re.IGNORECASE):
                    proper_base_images += 1
            except Exception as e:
                logger.warning(f"Failed to read Dockerfile {dockerfile}: {e}")
        
        # Calculate score
        has_dockerfiles = len(dockerfiles) > 0
        has_compose = len(docker_compose_files) > 0
        has_multi_stage = multi_stage_builds > 0
        has_proper_bases = proper_base_images >= len(dockerfiles) * 0.8 if dockerfiles else False
        
        checks = [has_dockerfiles, has_compose, has_multi_stage, has_proper_bases]
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 2  # At least 2 out of 4 checks should pass
        
        details = (f"Containerization: {len(dockerfiles)} Dockerfiles found, "
                  f"{len(docker_compose_files)} docker-compose files, "
                  f"{multi_stage_builds} with multi-stage builds")
        
        return CheckResult(
            name="Docker Images and Containerization",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_aws_cdk_code(self) -> CheckResult:
        """Check AWS CDK infrastructure code."""
        if not self.iac_path.exists():
            return CheckResult(
                name="AWS CDK Infrastructure Code",
                passed=False,
                score=0.0,
                details="AWS CDK directory not found",
                evidence=[]
            )
        
        evidence = []
        
        # Check for CDK app entry point
        app_file = self.iac_path / "app.py"
        has_app = app_file.exists()
        if has_app:
            evidence.append(f"{app_file.relative_to(self.workspace_root)}")
        
        # Check for cdk.json
        cdk_json = self.iac_path / "cdk.json"
        has_cdk_json = cdk_json.exists()
        if has_cdk_json:
            evidence.append(f"{cdk_json.relative_to(self.workspace_root)}")
        
        # Check for stacks directory
        stacks_path = self.iac_path / "stacks"
        stack_files = []
        if stacks_path.exists():
            stack_files = list(stacks_path.glob("*_stack.py"))
            evidence.extend([f"{f.relative_to(self.workspace_root)}" for f in stack_files])
        
        # Check for requirements.txt
        requirements_file = self.iac_path / "requirements.txt"
        has_requirements = requirements_file.exists()
        if has_requirements:
            evidence.append(f"{requirements_file.relative_to(self.workspace_root)}")
        
        # Check for README
        readme_file = self.iac_path / "README.md"
        has_readme = readme_file.exists()
        if has_readme:
            evidence.append(f"{readme_file.relative_to(self.workspace_root)}")
        
        # Analyze stack completeness
        expected_stacks = ["vpc", "lambda", "api_gateway", "opensearch", "elasticache", 
                          "cloudwatch", "kms_secrets", "iam"]
        found_stacks = [f.stem.replace("_stack", "") for f in stack_files]
        stack_coverage = len([s for s in expected_stacks if s in found_stacks]) / len(expected_stacks)
        
        # Check if CDK can synthesize
        has_synth_capability = has_app and has_cdk_json and len(stack_files) > 0
        
        # Calculate score
        checks = [
            has_app,
            has_cdk_json,
            len(stack_files) >= 5,  # At least 5 stacks
            stack_coverage >= 0.6,  # At least 60% of expected stacks
            has_requirements,
            has_readme,
            has_synth_capability
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 5  # At least 5 out of 7 checks should pass
        
        details = (f"AWS CDK: {len(stack_files)} stacks found "
                  f"({int(stack_coverage * 100)}% coverage of expected stacks), "
                  f"{'can' if has_synth_capability else 'cannot'} synthesize")
        
        return CheckResult(
            name="AWS CDK Infrastructure Code",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_deployment_guide(self) -> CheckResult:
        """Check deployment guide documentation."""
        deployment_guide = self.docs_path / "llm_deployment_guide.md"
        
        if not deployment_guide.exists():
            return CheckResult(
                name="Deployment Guide Documentation",
                passed=False,
                score=0.0,
                details="Deployment guide not found",
                evidence=[]
            )
        
        evidence = [f"{deployment_guide.relative_to(self.workspace_root)}"]
        
        try:
            content = deployment_guide.read_text()
            
            # Check for required sections
            required_sections = {
                "prerequisites": bool(re.search(r'##\s*Prerequisites', content, re.IGNORECASE)),
                "local_setup": bool(re.search(r'##\s*Local.*Setup', content, re.IGNORECASE)),
                "aws_setup": bool(re.search(r'##\s*AWS.*Setup', content, re.IGNORECASE)),
                "production_deployment": bool(re.search(r'##\s*Production.*Deployment', content, re.IGNORECASE)),
                "monitoring": bool(re.search(r'##\s*Monitoring', content, re.IGNORECASE)),
                "troubleshooting": bool(re.search(r'##\s*Troubleshooting', content, re.IGNORECASE)),
                "rollback": bool(re.search(r'##\s*Rollback', content, re.IGNORECASE))
            }
            
            # Check for code examples
            has_code_examples = len(re.findall(r'```', content)) >= 10
            
            # Check for AWS service mentions
            aws_services = ["Bedrock", "ElastiCache", "DynamoDB", "CloudWatch", "Secrets Manager"]
            aws_coverage = sum(1 for service in aws_services if service in content) / len(aws_services)
            
            # Check for environment configuration
            has_env_config = bool(re.search(r'\.env|environment.*variable', content, re.IGNORECASE))
            
            # Check for health check verification
            has_health_check = bool(re.search(r'/health|health.*check', content, re.IGNORECASE))
            
            # Calculate score
            section_score = sum(required_sections.values()) / len(required_sections)
            
            checks = [
                section_score >= 0.7,  # At least 70% of sections present
                has_code_examples,
                aws_coverage >= 0.6,  # At least 60% of AWS services mentioned
                has_env_config,
                has_health_check
            ]
            
            score = (sum(checks) / len(checks)) * 100
            passed = sum(checks) >= 4  # At least 4 out of 5 checks should pass
            
            sections_found = sum(required_sections.values())
            details = (f"Deployment guide: {sections_found}/{len(required_sections)} required sections, "
                      f"{int(aws_coverage * 100)}% AWS service coverage, "
                      f"{'includes' if has_code_examples else 'missing'} code examples")
            
            return CheckResult(
                name="Deployment Guide Documentation",
                passed=passed,
                score=score,
                details=details,
                evidence=evidence
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze deployment guide: {e}")
            return CheckResult(
                name="Deployment Guide Documentation",
                passed=False,
                score=0.0,
                details=f"Failed to analyze: {str(e)}",
                evidence=evidence
            )
    
    async def _check_rollback_procedures(self) -> CheckResult:
        """Check rollback procedures documentation."""
        evidence = []
        
        # Check deployment guide for rollback section
        deployment_guide = self.docs_path / "llm_deployment_guide.md"
        has_rollback_section = False
        rollback_procedures = []
        
        if deployment_guide.exists():
            evidence.append(f"{deployment_guide.relative_to(self.workspace_root)}")
            
            try:
                content = deployment_guide.read_text()
                
                # Check for rollback section
                has_rollback_section = bool(re.search(r'##\s*Rollback', content, re.IGNORECASE))
                
                # Check for specific rollback procedures
                rollback_keywords = [
                    "rollback to previous version",
                    "emergency disable",
                    "restore from backup",
                    "cdk.*rollback|cloudformation.*rollback",
                    "docker.*rollback|container.*rollback"
                ]
                
                for keyword in rollback_keywords:
                    if re.search(keyword, content, re.IGNORECASE):
                        rollback_procedures.append(keyword.split('|')[0])
                
            except Exception as e:
                logger.warning(f"Failed to analyze deployment guide for rollback: {e}")
        
        # Check for rollback scripts
        rollback_scripts = []
        for script_file in Path(self.workspace_root).rglob("*rollback*.py"):
            if any(part.startswith('.') for part in script_file.parts):
                continue
            rollback_scripts.append(script_file)
            evidence.append(f"{script_file.relative_to(self.workspace_root)}")
        
        for script_file in Path(self.workspace_root).rglob("*rollback*.sh"):
            if any(part.startswith('.') for part in script_file.parts):
                continue
            rollback_scripts.append(script_file)
            evidence.append(f"{script_file.relative_to(self.workspace_root)}")
        
        # Check CDK for rollback support
        has_cdk_rollback = False
        if self.iac_path.exists():
            for cdk_file in self.iac_path.rglob("*.py"):
                try:
                    content = cdk_file.read_text()
                    if re.search(r'rollback|cancel.*update|restore', content, re.IGNORECASE):
                        has_cdk_rollback = True
                        evidence.append(f"{cdk_file.relative_to(self.workspace_root)}")
                        break
                except Exception:
                    pass
        
        # Calculate score
        checks = [
            has_rollback_section,
            len(rollback_procedures) >= 3,  # At least 3 rollback procedures documented
            len(rollback_scripts) > 0,  # Has rollback scripts
            has_cdk_rollback  # CDK supports rollback
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 2  # At least 2 out of 4 checks should pass
        
        details = (f"Rollback procedures: {len(rollback_procedures)} procedures documented, "
                  f"{len(rollback_scripts)} rollback scripts, "
                  f"{'has' if has_cdk_rollback else 'missing'} CDK rollback support")
        
        return CheckResult(
            name="Rollback Procedures",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_health_endpoints(self) -> CheckResult:
        """Check health check endpoints implementation."""
        evidence = []
        health_endpoints = []
        
        # Search for health endpoint implementations
        health_patterns = [
            r'@\w+\.(get|route)\(["\'].*health',
            r'def\s+\w*health\w*\(',
            r'router\s*=.*health',
            r'app\.get\(["\'].*health'
        ]
        
        # Check backend routes
        routes_path = self.backend_path / "routes"
        if routes_path.exists():
            for route_file in routes_path.glob("*.py"):
                try:
                    content = route_file.read_text()
                    
                    for pattern in health_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            health_endpoints.append(route_file.name)
                            evidence.append(f"{route_file.relative_to(self.workspace_root)}")
                            break
                except Exception as e:
                    logger.warning(f"Failed to analyze {route_file}: {e}")
        
        # Check agent MCP servers
        agents_path = self.backend_path / "agents"
        if agents_path.exists():
            for agent_dir in agents_path.iterdir():
                if not agent_dir.is_dir() or agent_dir.name.startswith('.'):
                    continue
                
                # Check MCP server files
                for mcp_file in agent_dir.glob("*_mcp_server*.py"):
                    try:
                        content = mcp_file.read_text()
                        
                        for pattern in health_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                health_endpoints.append(f"{agent_dir.name}/{mcp_file.name}")
                                evidence.append(f"{mcp_file.relative_to(self.workspace_root)}")
                                break
                    except Exception as e:
                        logger.warning(f"Failed to analyze {mcp_file}: {e}")
        
        # Check main.py for health endpoint
        main_file = self.backend_path / "main.py"
        has_main_health = False
        if main_file.exists():
            try:
                content = main_file.read_text()
                for pattern in health_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        has_main_health = True
                        evidence.append(f"{main_file.relative_to(self.workspace_root)}")
                        break
            except Exception:
                pass
        
        # Check for health check in deployment guide
        has_health_docs = False
        deployment_guide = self.docs_path / "llm_deployment_guide.md"
        if deployment_guide.exists():
            try:
                content = deployment_guide.read_text()
                if re.search(r'/health|health.*endpoint|health.*check', content, re.IGNORECASE):
                    has_health_docs = True
            except Exception:
                pass
        
        # Calculate score
        has_health_routes = len(health_endpoints) > 0
        has_multiple_health = len(health_endpoints) >= 3  # At least 3 services with health checks
        has_unified_health = any('unified' in endpoint.lower() or 'health_routes' in endpoint.lower() 
                                for endpoint in health_endpoints)
        
        checks = [
            has_health_routes,
            has_multiple_health,
            has_main_health,
            has_unified_health,
            has_health_docs
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 5 checks should pass
        
        details = (f"Health endpoints: {len(health_endpoints)} services with health checks, "
                  f"{'includes' if has_unified_health else 'missing'} unified health endpoint, "
                  f"{'documented' if has_health_docs else 'not documented'}")
        
        return CheckResult(
            name="Health Check Endpoints",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
