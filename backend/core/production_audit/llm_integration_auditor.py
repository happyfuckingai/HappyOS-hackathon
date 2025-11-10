"""LLM Integration Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class LLMIntegrationAuditor(AuditModule):
    """
    Auditor for LLM integration across all agent teams.
    
    Evaluates:
    - MeetMind team (5 agents): coordinator, architect, PM, implementation, QA
    - Agent Svea team (5 agents + Swedish support): coordinator, architect, PM, implementation, QA
    - Felicia's Finance team (6 agents): coordinator, architect, PM, implementation, QA, banking
    - Fallback logic for all agents
    - Multi-provider support (Bedrock, OpenAI, local)
    """
    
    CATEGORY_NAME = "LLM Integration"
    CATEGORY_WEIGHT = 0.15  # 15% of overall score
    
    # Agent team definitions
    MEETMIND_AGENTS = ["coordinator", "architect", "product_manager", "implementation", "quality_assurance"]
    AGENT_SVEA_AGENTS = ["coordinator", "architect", "product_manager", "implementation", "quality_assurance"]
    FELICIAS_FINANCE_AGENTS = ["coordinator", "architect", "product_manager", "implementation", "quality_assurance", "banking"]
    
    def __init__(self, workspace_root: str = None):
        """Initialize LLM Integration Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.agents_path = self.backend_path / "agents"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform LLM integration audit."""
        logger.info("Starting LLM Integration audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: MeetMind LLM Integration
        meetmind_check = await self._check_meetmind_integration()
        checks.append(meetmind_check)
        if not meetmind_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="MeetMind team has incomplete LLM integration",
                impact="MeetMind agents may not function optimally without proper LLM integration",
                recommendation="Complete LLM integration for all MeetMind agents using centralized LLMService",
                estimated_effort="2-3 days"
            ))
        
        # Check 2: Agent Svea LLM Integration
        agent_svea_check = await self._check_agent_svea_integration()
        checks.append(agent_svea_check)
        if not agent_svea_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Agent Svea team has incomplete LLM integration or missing Swedish support",
                impact="Agent Svea may not handle Swedish compliance correctly",
                recommendation="Complete LLM integration with Swedish language support for all Agent Svea agents",
                estimated_effort="2-3 days"
            ))
        
        # Check 3: Felicia's Finance LLM Integration
        felicias_check = await self._check_felicias_finance_integration()
        checks.append(felicias_check)
        if not felicias_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Felicia's Finance team has incomplete LLM integration",
                impact="Financial agents may not provide accurate analysis without proper LLM integration",
                recommendation="Complete refactoring to centralized LLMService for all Felicia's Finance agents",
                estimated_effort="3-4 days"
            ))
        
        # Check 4: Fallback Logic
        fallback_check = await self._check_fallback_logic()
        checks.append(fallback_check)
        if not fallback_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Missing or incomplete fallback logic for agents",
                impact="System may fail completely when LLM services are unavailable",
                recommendation="Implement comprehensive fallback logic for all agents with rule-based alternatives",
                estimated_effort="3-5 days"
            ))
        
        # Check 5: Multi-Provider Support
        multi_provider_check = await self._check_multi_provider_support()
        checks.append(multi_provider_check)
        if not multi_provider_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Incomplete multi-provider support for LLM services",
                impact="System may not failover properly between AWS Bedrock, OpenAI, and local providers",
                recommendation="Ensure LLMService supports automatic failover between Bedrock, OpenAI, and local fallback",
                estimated_effort="2-3 days"
            ))
        
        # Check 6: Test Coverage
        test_coverage_check = await self._check_test_coverage()
        checks.append(test_coverage_check)
        if not test_coverage_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Insufficient test coverage for LLM integration",
                impact="LLM integration issues may not be caught before production",
                recommendation="Add comprehensive tests for all agents with and without LLM API keys",
                estimated_effort="2-3 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("LLM integration is production-ready across all agent teams")
        else:
            recommendations.append("Complete LLM integration for all agent teams before production deployment")
            recommendations.append("Ensure all agents have robust fallback logic for LLM unavailability")
            recommendations.append("Verify multi-provider failover works correctly under load")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"LLM Integration audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_meetmind_integration(self) -> CheckResult:
        """Check MeetMind team LLM integration."""
        meetmind_path = self.agents_path / "meetmind" / "adk_agents"
        
        if not meetmind_path.exists():
            return CheckResult(
                name="MeetMind LLM Integration",
                passed=False,
                score=0.0,
                details="MeetMind agents directory not found",
                evidence=[]
            )
        
        integrated_agents = []
        evidence = []
        
        for agent_name in self.MEETMIND_AGENTS:
            agent_file = meetmind_path / f"{agent_name}_agent.py"
            
            if not agent_file.exists():
                continue
            
            content = agent_file.read_text()
            
            # Check for LLM client initialization
            has_llm_client = bool(re.search(r'self\.llm_client\s*=', content))
            
            # Check for LLM usage
            has_llm_usage = bool(re.search(r'await\s+self\.llm_client\.', content))
            
            # Check for fallback method
            has_fallback = bool(re.search(r'def\s+_fallback_', content))
            
            if has_llm_client and (has_llm_usage or has_fallback):
                integrated_agents.append(agent_name)
                evidence.append(f"{agent_file.relative_to(self.workspace_root)}")
        
        # Score based on percentage of agents with LLM integration
        score = (len(integrated_agents) / len(self.MEETMIND_AGENTS)) * 100
        passed = len(integrated_agents) == len(self.MEETMIND_AGENTS)
        
        details = f"MeetMind: {len(integrated_agents)}/{len(self.MEETMIND_AGENTS)} agents have LLM integration"
        if integrated_agents:
            details += f" (integrated: {', '.join(integrated_agents)})"
        
        return CheckResult(
            name="MeetMind LLM Integration",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_agent_svea_integration(self) -> CheckResult:
        """Check Agent Svea team LLM integration with Swedish support."""
        agent_svea_path = self.agents_path / "agent_svea" / "adk_agents"
        
        if not agent_svea_path.exists():
            return CheckResult(
                name="Agent Svea LLM Integration",
                passed=False,
                score=0.0,
                details="Agent Svea agents directory not found",
                evidence=[]
            )
        
        integrated_agents = []
        swedish_support_count = 0
        evidence = []
        
        for agent_name in self.AGENT_SVEA_AGENTS:
            agent_file = agent_svea_path / f"{agent_name}_agent.py"
            
            if not agent_file.exists():
                continue
            
            content = agent_file.read_text()
            
            # Check for LLM service integration
            has_llm_service = bool(re.search(r'self\.llm_service', content))
            
            # Check for Swedish language support
            has_swedish = bool(re.search(r'svenska|swedish|svensk', content, re.IGNORECASE))
            
            # Check for fallback method
            has_fallback = bool(re.search(r'def\s+_fallback_', content))
            
            if has_llm_service or has_fallback:
                integrated_agents.append(agent_name)
                evidence.append(f"{agent_file.relative_to(self.workspace_root)}")
                
                if has_swedish:
                    swedish_support_count += 1
        
        # Score based on integration and Swedish support
        integration_score = (len(integrated_agents) / len(self.AGENT_SVEA_AGENTS)) * 70
        swedish_score = (swedish_support_count / len(self.AGENT_SVEA_AGENTS)) * 30
        score = integration_score + swedish_score
        
        passed = (len(integrated_agents) == len(self.AGENT_SVEA_AGENTS) and 
                 swedish_support_count >= len(self.AGENT_SVEA_AGENTS) // 2)
        
        details = (f"Agent Svea: {len(integrated_agents)}/{len(self.AGENT_SVEA_AGENTS)} agents have LLM integration, "
                  f"{swedish_support_count} with Swedish support")
        
        return CheckResult(
            name="Agent Svea LLM Integration",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_felicias_finance_integration(self) -> CheckResult:
        """Check Felicia's Finance team LLM integration."""
        felicias_path = self.agents_path / "felicias_finance" / "adk_agents"
        
        if not felicias_path.exists():
            return CheckResult(
                name="Felicia's Finance LLM Integration",
                passed=False,
                score=0.0,
                details="Felicia's Finance agents directory not found",
                evidence=[]
            )
        
        integrated_agents = []
        evidence = []
        
        # Check agents directory
        agents_dir = felicias_path / "agents"
        if agents_dir.exists():
            for agent_name in self.FELICIAS_FINANCE_AGENTS:
                agent_file = agents_dir / f"{agent_name}_agent.py"
                
                if not agent_file.exists():
                    continue
                
                content = agent_file.read_text()
                
                # Check for LLM service integration
                has_llm_service = bool(re.search(r'llm_service|LLMService', content))
                
                # Check for fallback
                has_fallback = bool(re.search(r'fallback', content, re.IGNORECASE))
                
                if has_llm_service or has_fallback:
                    integrated_agents.append(agent_name)
                    evidence.append(f"{agent_file.relative_to(self.workspace_root)}")
        
        # Also check main.py and adk_integration.py
        main_file = felicias_path / "main.py"
        if main_file.exists():
            evidence.append(f"{main_file.relative_to(self.workspace_root)}")
        
        adk_file = felicias_path / "adk" / "adk_integration.py"
        if adk_file.exists():
            evidence.append(f"{adk_file.relative_to(self.workspace_root)}")
        
        # Score based on percentage of agents with LLM integration
        score = (len(integrated_agents) / len(self.FELICIAS_FINANCE_AGENTS)) * 100
        passed = len(integrated_agents) >= len(self.FELICIAS_FINANCE_AGENTS) - 1  # Allow 1 missing
        
        details = f"Felicia's Finance: {len(integrated_agents)}/{len(self.FELICIAS_FINANCE_AGENTS)} agents have LLM integration"
        
        return CheckResult(
            name="Felicia's Finance LLM Integration",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_fallback_logic(self) -> CheckResult:
        """Check fallback logic implementation across all agents."""
        all_agents = {
            "meetmind": (self.agents_path / "meetmind" / "adk_agents", self.MEETMIND_AGENTS),
            "agent_svea": (self.agents_path / "agent_svea" / "adk_agents", self.AGENT_SVEA_AGENTS),
            "felicias_finance": (self.agents_path / "felicias_finance" / "adk_agents" / "agents", self.FELICIAS_FINANCE_AGENTS)
        }
        
        agents_with_fallback = []
        total_agents = 0
        evidence = []
        
        for team_name, (team_path, agent_list) in all_agents.items():
            if not team_path.exists():
                continue
            
            for agent_name in agent_list:
                total_agents += 1
                agent_file = team_path / f"{agent_name}_agent.py"
                
                if not agent_file.exists():
                    continue
                
                content = agent_file.read_text()
                
                # Check for fallback methods
                has_fallback_method = bool(re.search(r'def\s+_fallback_\w+', content))
                
                # Check for fallback usage in exception handling
                has_fallback_usage = bool(re.search(r'return\s+.*_fallback_|return\s+self\._fallback_', content))
                
                # Check for LLM availability check
                has_availability_check = bool(re.search(r'if\s+.*llm_client|if\s+.*llm_service|if\s+not\s+self\.llm', content))
                
                if has_fallback_method and (has_fallback_usage or has_availability_check):
                    agents_with_fallback.append(f"{team_name}.{agent_name}")
                    evidence.append(f"{agent_file.relative_to(self.workspace_root)}")
        
        # Score based on percentage of agents with fallback logic
        score = (len(agents_with_fallback) / total_agents * 100) if total_agents > 0 else 0
        passed = len(agents_with_fallback) >= total_agents * 0.8  # At least 80% should have fallback
        
        details = f"Fallback logic: {len(agents_with_fallback)}/{total_agents} agents have fallback implementation"
        
        return CheckResult(
            name="Fallback Logic Implementation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_multi_provider_support(self) -> CheckResult:
        """Check multi-provider support in LLM service."""
        llm_service_path = self.backend_path / "core" / "llm" / "llm_service.py"
        
        if not llm_service_path.exists():
            return CheckResult(
                name="Multi-Provider Support",
                passed=False,
                score=0.0,
                details="LLM service file not found",
                evidence=[]
            )
        
        content = llm_service_path.read_text()
        evidence = [f"{llm_service_path.relative_to(self.workspace_root)}"]
        
        # Check for provider routing
        has_provider_routing = bool(re.search(r'_route_to_provider|route.*provider', content, re.IGNORECASE))
        
        # Check for multiple providers
        has_bedrock = bool(re.search(r'bedrock|aws.*llm', content, re.IGNORECASE))
        has_openai = bool(re.search(r'openai', content, re.IGNORECASE))
        has_local = bool(re.search(r'local|fallback.*provider', content, re.IGNORECASE))
        
        # Check for circuit breaker integration
        has_circuit_breaker = bool(re.search(r'circuit_breaker', content, re.IGNORECASE))
        
        # Check for failover logic
        has_failover = bool(re.search(r'failover|try.*except.*provider', content, re.IGNORECASE))
        
        # Check providers directory
        providers_path = self.backend_path / "core" / "llm" / "providers"
        provider_files = []
        if providers_path.exists():
            provider_files = list(providers_path.glob("*.py"))
            evidence.extend([f"{f.relative_to(self.workspace_root)}" for f in provider_files if f.name != "__init__.py"])
        
        # Calculate score
        checks = [
            has_provider_routing,
            has_bedrock,
            has_openai,
            has_local or has_failover,
            has_circuit_breaker,
            len(provider_files) >= 2
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 4  # At least 4 out of 6 checks should pass
        
        providers_found = []
        if has_bedrock:
            providers_found.append("Bedrock")
        if has_openai:
            providers_found.append("OpenAI")
        if has_local:
            providers_found.append("Local")
        
        details = f"Multi-provider support: {', '.join(providers_found) if providers_found else 'None found'}"
        if has_provider_routing:
            details += " with routing logic"
        if has_circuit_breaker:
            details += " and circuit breaker"
        
        return CheckResult(
            name="Multi-Provider Support",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_test_coverage(self) -> CheckResult:
        """Check test coverage for LLM integration."""
        test_files = []
        evidence = []
        
        # Find all LLM integration test files
        for team in ["meetmind", "agent_svea", "felicias_finance"]:
            team_path = self.agents_path / team
            if not team_path.exists():
                continue
            
            # Find test files
            for test_file in team_path.glob("test_*llm*.py"):
                test_files.append(test_file)
                evidence.append(f"{test_file.relative_to(self.workspace_root)}")
            
            for test_file in team_path.glob("test_*agent*.py"):
                content = test_file.read_text()
                if "llm" in content.lower() or "fallback" in content.lower():
                    test_files.append(test_file)
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
        
        # Check backend tests
        backend_tests_path = self.backend_path / "tests"
        if backend_tests_path.exists():
            for test_file in backend_tests_path.glob("test_*llm*.py"):
                test_files.append(test_file)
                evidence.append(f"{test_file.relative_to(self.workspace_root)}")
        
        # Analyze test content
        tests_with_fallback = 0
        tests_with_api_keys = 0
        
        for test_file in test_files:
            content = test_file.read_text()
            
            if re.search(r'fallback|without.*llm|no.*api.*key', content, re.IGNORECASE):
                tests_with_fallback += 1
            
            if re.search(r'api.*key|openai_key|bedrock', content, re.IGNORECASE):
                tests_with_api_keys += 1
        
        # Calculate score
        has_tests = len(test_files) > 0
        has_sufficient_tests = len(test_files) >= 10  # At least 10 LLM-related tests
        has_fallback_tests = tests_with_fallback >= 3  # At least 3 fallback tests
        has_provider_tests = tests_with_api_keys >= 3  # At least 3 provider tests
        
        checks = [has_tests, has_sufficient_tests, has_fallback_tests, has_provider_tests]
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 4 checks should pass
        
        details = (f"Test coverage: {len(test_files)} LLM-related test files found, "
                  f"{tests_with_fallback} with fallback tests, "
                  f"{tests_with_api_keys} with provider tests")
        
        return CheckResult(
            name="LLM Integration Test Coverage",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
