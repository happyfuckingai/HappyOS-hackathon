"""Documentation Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class DocumentationAuditor(AuditModule):
    """
    Auditor for documentation completeness and quality.
    
    Evaluates:
    - README files for each agent team
    - API documentation (backend/core/llm/README.md)
    - Architecture diagrams (Mermaid diagrams in documentation)
    - Troubleshooting guide in deployment documentation
    - Operational documentation
    """
    
    CATEGORY_NAME = "Documentation"
    CATEGORY_WEIGHT = 0.10  # 10% of overall score
    
    def __init__(self, workspace_root: str = None):
        """Initialize Documentation Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.docs_path = Path(self.workspace_root) / "docs"
        self.agents_path = self.backend_path / "agents"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform documentation audit."""
        logger.info("Starting Documentation audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: Agent Team Documentation
        agent_docs_check = await self._check_agent_documentation()
        checks.append(agent_docs_check)
        if not agent_docs_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Agent team documentation is incomplete",
                impact="New developers will struggle to understand agent implementations",
                recommendation="Complete README files for all agent teams with LLM integration examples",
                estimated_effort="2-3 days"
            ))
        
        # Check 2: API Documentation
        api_docs_check = await self._check_api_documentation()
        checks.append(api_docs_check)
        if not api_docs_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="API documentation is incomplete or missing",
                impact="Developers cannot effectively use core services without proper documentation",
                recommendation="Complete API documentation for LLM Service, ServiceFacade, and agent interfaces",
                estimated_effort="2-3 days"
            ))
        
        # Check 3: Architecture Documentation
        architecture_docs_check = await self._check_architecture_documentation()
        checks.append(architecture_docs_check)
        if not architecture_docs_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Architecture diagrams and documentation are incomplete",
                impact="Team lacks clear understanding of system architecture and data flows",
                recommendation="Create comprehensive architecture diagrams using Mermaid for all major components",
                estimated_effort="2-3 days"
            ))
        
        # Check 4: Operational Documentation
        operational_docs_check = await self._check_operational_documentation()
        checks.append(operational_docs_check)
        if not operational_docs_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Operational documentation (troubleshooting, monitoring, runbooks) is incomplete",
                impact="Operations team cannot effectively maintain and troubleshoot the system",
                recommendation="Create comprehensive operational documentation including troubleshooting guides and runbooks",
                estimated_effort="3-4 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Documentation is comprehensive and production-ready")
        else:
            recommendations.append("Complete README files for all agent teams with examples")
            recommendations.append("Document all public APIs with usage examples")
            recommendations.append("Create architecture diagrams for system components and data flows")
            recommendations.append("Develop comprehensive troubleshooting guides and operational runbooks")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Documentation audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_agent_documentation(self) -> CheckResult:
        """Check README files for each agent team."""
        evidence = []
        agent_teams = {
            "meetmind": False,
            "agent_svea": False,
            "felicias_finance": False
        }
        
        llm_integration_examples = {
            "meetmind": False,
            "agent_svea": False,
            "felicias_finance": False
        }
        
        if not self.agents_path.exists():
            return CheckResult(
                name="Agent Team Documentation",
                passed=False,
                score=0.0,
                details="Agents directory not found",
                evidence=[]
            )
        
        # Check each agent team
        for agent_name in agent_teams.keys():
            agent_dir = self.agents_path / agent_name
            if not agent_dir.exists():
                continue
            
            # Check for README
            readme_file = agent_dir / "README.md"
            if readme_file.exists():
                agent_teams[agent_name] = True
                evidence.append(f"{readme_file.relative_to(self.workspace_root)}")
                
                try:
                    content = readme_file.read_text()
                    
                    # Check for LLM integration examples
                    llm_keywords = [
                        r'LLM.*integration',
                        r'LLMService',
                        r'llm_service',
                        r'Bedrock',
                        r'OpenAI',
                        r'```python.*llm',
                        r'example.*llm',
                        r'usage.*llm'
                    ]
                    
                    for keyword in llm_keywords:
                        if re.search(keyword, content, re.IGNORECASE):
                            llm_integration_examples[agent_name] = True
                            break
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze {readme_file}: {e}")
        
        # Calculate score
        teams_with_readme = sum(agent_teams.values())
        teams_with_llm_examples = sum(llm_integration_examples.values())
        total_teams = len(agent_teams)
        
        readme_coverage = teams_with_readme / total_teams
        llm_example_coverage = teams_with_llm_examples / total_teams
        
        checks = [
            readme_coverage >= 0.66,  # At least 2 out of 3 teams have README
            llm_example_coverage >= 0.66,  # At least 2 out of 3 teams have LLM examples
            teams_with_readme == total_teams,  # All teams have README
            teams_with_llm_examples >= 2  # At least 2 teams have LLM examples
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 4 checks should pass
        
        details = (f"Agent documentation: {teams_with_readme}/{total_teams} teams have README, "
                  f"{teams_with_llm_examples}/{total_teams} teams have LLM integration examples")
        
        return CheckResult(
            name="Agent Team Documentation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_api_documentation(self) -> CheckResult:
        """Check API documentation for core services."""
        evidence = []
        
        # Check LLM Service documentation
        llm_readme = self.backend_path / "core" / "llm" / "README.md"
        has_llm_docs = llm_readme.exists()
        llm_api_documented = False
        llm_has_examples = False
        
        if has_llm_docs:
            evidence.append(f"{llm_readme.relative_to(self.workspace_root)}")
            
            try:
                content = llm_readme.read_text()
                
                # Check for API documentation
                api_patterns = [
                    r'##\s*API',
                    r'##\s*Usage',
                    r'##\s*Methods',
                    r'def\s+\w+\(',
                    r'class\s+\w+'
                ]
                
                for pattern in api_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        llm_api_documented = True
                        break
                
                # Check for code examples
                code_blocks = len(re.findall(r'```', content))
                llm_has_examples = code_blocks >= 4  # At least 2 code examples (opening and closing ```)
                
            except Exception as e:
                logger.warning(f"Failed to analyze {llm_readme}: {e}")
        
        # Check ServiceFacade documentation
        service_facade_file = self.backend_path / "infrastructure" / "service_facade.py"
        has_facade_docs = False
        
        if service_facade_file.exists():
            try:
                content = service_facade_file.read_text()
                
                # Check for docstrings
                docstring_count = len(re.findall(r'"""[\s\S]*?"""', content))
                has_facade_docs = docstring_count >= 5  # At least 5 docstrings
                
                if has_facade_docs:
                    evidence.append(f"{service_facade_file.relative_to(self.workspace_root)}")
                
            except Exception as e:
                logger.warning(f"Failed to analyze {service_facade_file}: {e}")
        
        # Check agent interfaces documentation
        interfaces_file = self.backend_path / "core" / "interfaces.py"
        has_interface_docs = False
        
        if interfaces_file.exists():
            try:
                content = interfaces_file.read_text()
                
                # Check for docstrings
                docstring_count = len(re.findall(r'"""[\s\S]*?"""', content))
                has_interface_docs = docstring_count >= 3  # At least 3 docstrings
                
                if has_interface_docs:
                    evidence.append(f"{interfaces_file.relative_to(self.workspace_root)}")
                
            except Exception as e:
                logger.warning(f"Failed to analyze {interfaces_file}: {e}")
        
        # Check for general backend README
        backend_readme = self.backend_path / "README.md"
        has_backend_readme = backend_readme.exists()
        backend_has_api_docs = False
        
        if has_backend_readme:
            evidence.append(f"{backend_readme.relative_to(self.workspace_root)}")
            
            try:
                content = backend_readme.read_text()
                
                # Check for API documentation sections
                api_keywords = [
                    r'##\s*API',
                    r'##\s*Services',
                    r'##\s*Architecture',
                    r'##\s*Usage'
                ]
                
                for keyword in api_keywords:
                    if re.search(keyword, content, re.IGNORECASE):
                        backend_has_api_docs = True
                        break
                
            except Exception as e:
                logger.warning(f"Failed to analyze {backend_readme}: {e}")
        
        # Calculate score
        checks = [
            has_llm_docs,
            llm_api_documented,
            llm_has_examples,
            has_facade_docs,
            has_interface_docs,
            has_backend_readme,
            backend_has_api_docs
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 5  # At least 5 out of 7 checks should pass
        
        components_documented = sum([has_llm_docs, has_facade_docs, has_interface_docs])
        details = (f"API documentation: {components_documented}/3 core components documented, "
                  f"{'includes' if llm_has_examples else 'missing'} code examples, "
                  f"{'has' if backend_has_api_docs else 'missing'} backend API overview")
        
        return CheckResult(
            name="API Documentation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_architecture_documentation(self) -> CheckResult:
        """Check architecture diagrams and documentation."""
        evidence = []
        
        # Search for Mermaid diagrams in all markdown files
        mermaid_diagrams = []
        architecture_docs = []
        
        # Check common documentation locations
        doc_locations = [
            self.docs_path,
            self.backend_path,
            Path(self.workspace_root) / "hackathon_submissions" / "architecture_diagrams"
        ]
        
        for doc_location in doc_locations:
            if not doc_location.exists():
                continue
            
            for md_file in doc_location.rglob("*.md"):
                # Skip hidden directories
                if any(part.startswith('.') for part in md_file.parts):
                    continue
                
                try:
                    content = md_file.read_text()
                    
                    # Check for Mermaid diagrams
                    mermaid_count = len(re.findall(r'```mermaid', content, re.IGNORECASE))
                    if mermaid_count > 0:
                        mermaid_diagrams.append((md_file, mermaid_count))
                        evidence.append(f"{md_file.relative_to(self.workspace_root)} ({mermaid_count} diagrams)")
                    
                    # Check for architecture documentation
                    architecture_keywords = [
                        r'##\s*Architecture',
                        r'##\s*System.*Design',
                        r'##\s*Component.*Diagram',
                        r'##\s*Data.*Flow',
                        r'##\s*Deployment.*Architecture'
                    ]
                    
                    for keyword in architecture_keywords:
                        if re.search(keyword, content, re.IGNORECASE):
                            if md_file not in [d[0] for d in architecture_docs]:
                                architecture_docs.append((md_file, keyword))
                            break
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze {md_file}: {e}")
        
        # Check for specific architecture documentation
        has_system_architecture = False
        has_data_flow = False
        has_deployment_architecture = False
        has_failover_flow = False
        
        for doc_file, _ in architecture_docs:
            try:
                content = doc_file.read_text()
                
                if re.search(r'system.*architecture|overall.*architecture', content, re.IGNORECASE):
                    has_system_architecture = True
                
                if re.search(r'data.*flow|information.*flow', content, re.IGNORECASE):
                    has_data_flow = True
                
                if re.search(r'deployment.*architecture|infrastructure.*architecture', content, re.IGNORECASE):
                    has_deployment_architecture = True
                
                if re.search(r'failover|circuit.*breaker|resilience.*flow', content, re.IGNORECASE):
                    has_failover_flow = True
                
            except Exception:
                pass
        
        # Calculate score
        total_mermaid_diagrams = sum(count for _, count in mermaid_diagrams)
        has_multiple_diagrams = total_mermaid_diagrams >= 3
        has_architecture_docs = len(architecture_docs) > 0
        
        checks = [
            has_multiple_diagrams,  # At least 3 Mermaid diagrams
            has_architecture_docs,  # Has architecture documentation
            has_system_architecture,  # Has system architecture documentation
            has_data_flow,  # Has data flow documentation
            has_deployment_architecture,  # Has deployment architecture
            has_failover_flow  # Has failover flow documentation
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 4  # At least 4 out of 6 checks should pass
        
        details = (f"Architecture documentation: {total_mermaid_diagrams} Mermaid diagrams, "
                  f"{len(architecture_docs)} architecture documents, "
                  f"{sum([has_system_architecture, has_data_flow, has_deployment_architecture, has_failover_flow])}/4 key diagrams present")
        
        return CheckResult(
            name="Architecture Documentation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_operational_documentation(self) -> CheckResult:
        """Check operational documentation (troubleshooting, monitoring, runbooks)."""
        evidence = []
        
        # Check deployment guide for troubleshooting
        deployment_guide = self.docs_path / "llm_deployment_guide.md"
        has_troubleshooting = False
        troubleshooting_topics = 0
        
        if deployment_guide.exists():
            evidence.append(f"{deployment_guide.relative_to(self.workspace_root)}")
            
            try:
                content = deployment_guide.read_text()
                
                # Check for troubleshooting section
                has_troubleshooting = bool(re.search(r'##\s*Troubleshooting', content, re.IGNORECASE))
                
                # Count troubleshooting topics
                troubleshooting_keywords = [
                    r'connection.*fail',
                    r'authentication.*error',
                    r'timeout',
                    r'circuit.*breaker.*open',
                    r'llm.*error',
                    r'deployment.*fail',
                    r'health.*check.*fail'
                ]
                
                for keyword in troubleshooting_keywords:
                    if re.search(keyword, content, re.IGNORECASE):
                        troubleshooting_topics += 1
                
            except Exception as e:
                logger.warning(f"Failed to analyze {deployment_guide}: {e}")
        
        # Check for monitoring guide
        has_monitoring_guide = False
        monitoring_topics = 0
        
        # Check in deployment guide
        if deployment_guide.exists():
            try:
                content = deployment_guide.read_text()
                
                if re.search(r'##\s*Monitoring', content, re.IGNORECASE):
                    has_monitoring_guide = True
                    
                    # Count monitoring topics
                    monitoring_keywords = [
                        r'CloudWatch',
                        r'Prometheus',
                        r'metrics',
                        r'dashboard',
                        r'alarm',
                        r'alert'
                    ]
                    
                    for keyword in monitoring_keywords:
                        if re.search(keyword, content, re.IGNORECASE):
                            monitoring_topics += 1
                
            except Exception:
                pass
        
        # Check for separate monitoring documentation
        for doc_file in self.docs_path.rglob("*monitor*.md") if self.docs_path.exists() else []:
            if not has_monitoring_guide:
                has_monitoring_guide = True
                evidence.append(f"{doc_file.relative_to(self.workspace_root)}")
        
        # Check for runbook
        has_runbook = False
        runbook_procedures = 0
        
        for doc_file in Path(self.workspace_root).rglob("*runbook*.md"):
            if any(part.startswith('.') for part in doc_file.parts):
                continue
            
            has_runbook = True
            evidence.append(f"{doc_file.relative_to(self.workspace_root)}")
            
            try:
                content = doc_file.read_text()
                
                # Count procedures
                procedure_patterns = [
                    r'##\s*Procedure',
                    r'##\s*Steps',
                    r'###\s*\d+\.',
                    r'##\s*Emergency',
                    r'##\s*Incident'
                ]
                
                for pattern in procedure_patterns:
                    runbook_procedures += len(re.findall(pattern, content, re.IGNORECASE))
                
            except Exception:
                pass
        
        # Check for operational procedures in other docs
        operational_docs = []
        
        for doc_location in [self.docs_path, self.backend_path]:
            if not doc_location.exists():
                continue
            
            for md_file in doc_location.rglob("*.md"):
                if any(part.startswith('.') for part in md_file.parts):
                    continue
                
                try:
                    content = md_file.read_text()
                    
                    operational_keywords = [
                        r'##\s*Operations',
                        r'##\s*Maintenance',
                        r'##\s*Backup',
                        r'##\s*Recovery',
                        r'##\s*Scaling'
                    ]
                    
                    for keyword in operational_keywords:
                        if re.search(keyword, content, re.IGNORECASE):
                            if md_file not in operational_docs:
                                operational_docs.append(md_file)
                                evidence.append(f"{md_file.relative_to(self.workspace_root)}")
                            break
                    
                except Exception:
                    pass
        
        # Calculate score
        checks = [
            has_troubleshooting,
            troubleshooting_topics >= 3,  # At least 3 troubleshooting topics
            has_monitoring_guide,
            monitoring_topics >= 3,  # At least 3 monitoring topics
            has_runbook or len(operational_docs) > 0,  # Has runbook or operational docs
            runbook_procedures >= 3 or len(operational_docs) >= 2  # Has procedures
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 4  # At least 4 out of 6 checks should pass
        
        details = (f"Operational documentation: "
                  f"{'has' if has_troubleshooting else 'missing'} troubleshooting guide ({troubleshooting_topics} topics), "
                  f"{'has' if has_monitoring_guide else 'missing'} monitoring guide ({monitoring_topics} topics), "
                  f"{'has' if has_runbook or operational_docs else 'missing'} runbook/operational procedures")
        
        return CheckResult(
            name="Operational Documentation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
