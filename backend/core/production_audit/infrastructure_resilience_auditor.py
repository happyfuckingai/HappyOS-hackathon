"""Infrastructure Resilience Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class InfrastructureResilienceAuditor(AuditModule):
    """
    Auditor for infrastructure resilience and failover capabilities.
    
    Evaluates:
    - ServiceFacade implementation
    - Circuit breaker for all services (agent_core, search, compute, cache, storage, secrets, llm)
    - Failover mechanisms between AWS and local services
    - Health check implementation
    - System resilience under failure conditions
    """
    
    CATEGORY_NAME = "Infrastructure Resilience"
    CATEGORY_WEIGHT = 0.15  # 15% of overall score
    
    # Service types that should have circuit breakers
    REQUIRED_SERVICES = [
        "agent_core",
        "search",
        "compute",
        "cache",
        "storage",
        "secrets",
        "llm"
    ]
    
    def __init__(self, workspace_root: str = None):
        """Initialize Infrastructure Resilience Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.infrastructure_path = self.backend_path / "infrastructure"
        self.circuit_breaker_path = self.backend_path / "core" / "circuit_breaker"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform infrastructure resilience audit."""
        logger.info("Starting Infrastructure Resilience audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: ServiceFacade Implementation
        service_facade_check = await self._check_service_facade_implementation()
        checks.append(service_facade_check)
        if not service_facade_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="ServiceFacade implementation is incomplete or missing",
                impact="System cannot provide unified interface for AWS/local service failover",
                recommendation="Complete ServiceFacade implementation with all required service types and mode switching",
                estimated_effort="3-5 days"
            ))
        
        # Check 2: Circuit Breaker Coverage
        circuit_breaker_check = await self._check_circuit_breaker_coverage()
        checks.append(circuit_breaker_check)
        if not circuit_breaker_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Circuit breakers missing for one or more critical services",
                impact="Services may not fail gracefully, causing cascading failures",
                recommendation="Implement circuit breakers for all critical services with proper thresholds",
                estimated_effort="2-3 days"
            ))
        
        # Check 3: Failover Mechanisms
        failover_check = await self._check_failover_mechanisms()
        checks.append(failover_check)
        if not failover_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Failover mechanisms incomplete or not properly implemented",
                impact="System may not automatically switch to local services when AWS fails",
                recommendation="Implement automatic failover with proper error handling and logging",
                estimated_effort="2-3 days"
            ))
        
        # Check 4: Health Monitoring
        health_check = await self._check_health_monitoring()
        checks.append(health_check)
        if not health_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Health monitoring incomplete or missing for services",
                impact="Cannot detect service degradation or failures proactively",
                recommendation="Implement comprehensive health checks for all services with proper status reporting",
                estimated_effort="2-3 days"
            ))
        
        # Check 5: AWS Service Adapters
        aws_adapters_check = await self._check_aws_service_adapters()
        checks.append(aws_adapters_check)
        if not aws_adapters_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="AWS service adapters incomplete or missing",
                impact="Cannot utilize AWS services properly for production workloads",
                recommendation="Complete AWS service adapter implementations for all required services",
                estimated_effort="3-4 days"
            ))
        
        # Check 6: Local Service Fallbacks
        local_services_check = await self._check_local_service_fallbacks()
        checks.append(local_services_check)
        if not local_services_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Local service fallbacks incomplete or missing",
                impact="System may fail completely when AWS services are unavailable",
                recommendation="Implement local service fallbacks for all critical services",
                estimated_effort="3-4 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Infrastructure resilience is production-ready with comprehensive failover")
            recommendations.append("Continue monitoring circuit breaker metrics in production")
        else:
            recommendations.append("Complete ServiceFacade implementation before production deployment")
            recommendations.append("Ensure all critical services have circuit breakers configured")
            recommendations.append("Test failover scenarios under load to verify resilience")
            recommendations.append("Implement comprehensive health monitoring for proactive issue detection")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Infrastructure Resilience audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_service_facade_implementation(self) -> CheckResult:
        """Check ServiceFacade implementation completeness."""
        service_facade_file = self.infrastructure_path / "service_facade.py"
        
        if not service_facade_file.exists():
            return CheckResult(
                name="ServiceFacade Implementation",
                passed=False,
                score=0.0,
                details="ServiceFacade file not found",
                evidence=[]
            )
        
        content = service_facade_file.read_text()
        evidence = [f"{service_facade_file.relative_to(self.workspace_root)}"]
        
        # Check for ServiceFacade class
        has_service_facade_class = bool(re.search(r'class\s+ServiceFacade', content))
        
        # Check for service mode enum
        has_service_mode = bool(re.search(r'class\s+ServiceMode.*Enum', content, re.DOTALL))
        
        # Check for initialization method
        has_initialize = bool(re.search(r'async\s+def\s+initialize', content))
        
        # Check for AWS services initialization
        has_aws_init = bool(re.search(r'async\s+def\s+_initialize_aws_services', content))
        
        # Check for local services initialization
        has_local_init = bool(re.search(r'async\s+def\s+_initialize_local_services', content))
        
        # Check for circuit breaker initialization
        has_circuit_breaker_init = bool(re.search(r'def\s+_initialize_circuit_breakers', content))
        
        # Check for service instance getter
        has_get_service = bool(re.search(r'async\s+def\s+_get_service_instance', content))
        
        # Check for execute with circuit breaker
        has_execute_cb = bool(re.search(r'async\s+def\s+_execute_with_circuit_breaker', content))
        
        # Check for system health method
        has_system_health = bool(re.search(r'async\s+def\s+get_system_health', content))
        
        # Check for all required service facades
        service_facades_found = []
        for service in self.REQUIRED_SERVICES:
            # Convert service name to facade class name (e.g., agent_core -> AgentCoreFacade)
            facade_name = ''.join(word.capitalize() for word in service.split('_')) + 'Facade'
            if re.search(rf'class\s+{facade_name}', content):
                service_facades_found.append(service)
        
        # Calculate score
        checks = [
            has_service_facade_class,
            has_service_mode,
            has_initialize,
            has_aws_init,
            has_local_init,
            has_circuit_breaker_init,
            has_get_service,
            has_execute_cb,
            has_system_health,
            len(service_facades_found) >= len(self.REQUIRED_SERVICES) - 1  # Allow 1 missing
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 8  # At least 8 out of 10 checks should pass
        
        details = (f"ServiceFacade: {sum(checks)}/10 implementation checks passed. "
                  f"Service facades: {len(service_facades_found)}/{len(self.REQUIRED_SERVICES)} implemented")
        
        return CheckResult(
            name="ServiceFacade Implementation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_circuit_breaker_coverage(self) -> CheckResult:
        """Check circuit breaker coverage for all services."""
        service_facade_file = self.infrastructure_path / "service_facade.py"
        circuit_breaker_file = self.circuit_breaker_path / "circuit_breaker.py"
        
        evidence = []
        if not service_facade_file.exists() or not circuit_breaker_file.exists():
            return CheckResult(
                name="Circuit Breaker Coverage",
                passed=False,
                score=0.0,
                details="Required files not found",
                evidence=evidence
            )
        
        facade_content = service_facade_file.read_text()
        cb_content = circuit_breaker_file.read_text()
        
        evidence.append(f"{service_facade_file.relative_to(self.workspace_root)}")
        evidence.append(f"{circuit_breaker_file.relative_to(self.workspace_root)}")
        
        # Check for CircuitBreaker class
        has_circuit_breaker_class = bool(re.search(r'class\s+CircuitBreaker', cb_content))
        
        # Check for circuit breaker states
        has_circuit_states = bool(re.search(r'CircuitState\.(CLOSED|OPEN|HALF_OPEN)', cb_content))
        
        # Check for failure threshold configuration
        has_failure_threshold = bool(re.search(r'failure_threshold', cb_content))
        
        # Check for recovery timeout
        has_recovery_timeout = bool(re.search(r'recovery_timeout|timeout_seconds', cb_content))
        
        # Check for half-open state handling
        has_half_open = bool(re.search(r'HALF_OPEN|half_open', cb_content))
        
        # Check that circuit breakers are initialized for all services
        services_with_cb = []
        for service in self.REQUIRED_SERVICES:
            # Check if circuit breaker is created for this service
            pattern = rf"['\"]?{service}['\"]?\s*[:\]]\s*=.*[Cc]ircuit[Bb]reaker"
            if re.search(pattern, facade_content):
                services_with_cb.append(service)
        
        # Check for circuit breaker dictionary/map
        has_cb_dict = bool(re.search(r'_circuit_breakers.*Dict|circuit_breakers.*=.*\{\}', facade_content))
        
        # Check for circuit breaker initialization loop
        has_cb_init_loop = bool(re.search(r'for\s+service.*in.*service.*types|for.*in.*REQUIRED_SERVICES', facade_content))
        
        # Calculate score
        checks = [
            has_circuit_breaker_class,
            has_circuit_states,
            has_failure_threshold,
            has_recovery_timeout,
            has_half_open,
            has_cb_dict,
            has_cb_init_loop or len(services_with_cb) >= len(self.REQUIRED_SERVICES) - 1,
            len(services_with_cb) >= len(self.REQUIRED_SERVICES) * 0.7  # At least 70% coverage
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 6  # At least 6 out of 8 checks should pass
        
        details = (f"Circuit breaker: {sum(checks)}/8 checks passed. "
                  f"Services covered: {len(services_with_cb)}/{len(self.REQUIRED_SERVICES)}")
        if services_with_cb:
            details += f" ({', '.join(services_with_cb)})"
        
        return CheckResult(
            name="Circuit Breaker Coverage",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_failover_mechanisms(self) -> CheckResult:
        """Check failover mechanisms implementation."""
        service_facade_file = self.infrastructure_path / "service_facade.py"
        
        if not service_facade_file.exists():
            return CheckResult(
                name="Failover Mechanisms",
                passed=False,
                score=0.0,
                details="ServiceFacade file not found",
                evidence=[]
            )
        
        content = service_facade_file.read_text()
        evidence = [f"{service_facade_file.relative_to(self.workspace_root)}"]
        
        # Check for _execute_with_circuit_breaker method
        has_execute_cb = bool(re.search(r'async\s+def\s+_execute_with_circuit_breaker', content))
        
        # Check for AWS to local failover logic
        has_aws_to_local = bool(re.search(r'fall.*back.*to.*local|local.*service.*if.*aws.*fail', content, re.IGNORECASE))
        
        # Check for automatic failover
        has_automatic_failover = bool(re.search(r'automatic.*failover|auto.*switch', content, re.IGNORECASE))
        
        # Check for CircuitBreakerOpenError handling
        has_cb_error_handling = bool(re.search(r'CircuitBreakerOpenError|circuit.*breaker.*open', content))
        
        # Check for service mode switching
        has_mode_switching = bool(re.search(r'ServiceMode\.(AWS_ONLY|LOCAL_ONLY|HYBRID)', content))
        
        # Check for failover logging
        has_failover_logging = bool(re.search(r'logger.*fall.*back|logger.*failover', content, re.IGNORECASE))
        
        # Check for service availability check
        has_availability_check = bool(re.search(r'if.*service.*available|if.*not.*service', content))
        
        # Check for exception handling in execute method
        has_exception_handling = bool(re.search(r'try:.*await.*except.*Exception', content, re.DOTALL))
        
        # Check for functionality maintenance during failover
        has_functionality_check = bool(re.search(r'maintain.*functionality|degraded.*mode', content, re.IGNORECASE))
        
        # Calculate score
        checks = [
            has_execute_cb,
            has_aws_to_local,
            has_automatic_failover,
            has_cb_error_handling,
            has_mode_switching,
            has_failover_logging,
            has_availability_check,
            has_exception_handling,
            has_functionality_check
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 6  # At least 6 out of 9 checks should pass
        
        details = f"Failover mechanisms: {sum(checks)}/9 checks passed"
        if has_execute_cb and has_aws_to_local:
            details += " with automatic AWS-to-local failover"
        
        return CheckResult(
            name="Failover Mechanisms",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_health_monitoring(self) -> CheckResult:
        """Check health monitoring implementation."""
        service_facade_file = self.infrastructure_path / "service_facade.py"
        health_service_file = self.backend_path / "services" / "observability" / "health.py"
        
        evidence = []
        if not service_facade_file.exists():
            return CheckResult(
                name="Health Monitoring",
                passed=False,
                score=0.0,
                details="ServiceFacade file not found",
                evidence=evidence
            )
        
        facade_content = service_facade_file.read_text()
        evidence.append(f"{service_facade_file.relative_to(self.workspace_root)}")
        
        # Check for get_system_health method
        has_system_health = bool(re.search(r'async\s+def\s+get_system_health', facade_content))
        
        # Check for _check_service_health method
        has_check_service_health = bool(re.search(r'async\s+def\s+_check_service_health', facade_content))
        
        # Check for health status tracking
        has_health_tracking = bool(re.search(r'_service_health.*Dict|service_health.*=', facade_content))
        
        # Check for ServiceHealth enum usage
        has_service_health_enum = bool(re.search(r'ServiceHealth\.(HEALTHY|DEGRADED|UNHEALTHY)', facade_content))
        
        # Check for health checker integration
        has_health_checker = bool(re.search(r'_health_checker|get_health_checker', facade_content))
        
        # Check for circuit breaker state in health
        has_cb_in_health = bool(re.search(r'circuit_breaker.*state|circuit.*breaker.*in.*health', facade_content, re.IGNORECASE))
        
        # Check for overall health calculation
        has_overall_health = bool(re.search(r'_calculate_overall_health|overall.*status', facade_content))
        
        # Check health service file if it exists
        has_health_service = False
        if health_service_file.exists():
            health_content = health_service_file.read_text()
            evidence.append(f"{health_service_file.relative_to(self.workspace_root)}")
            has_health_service = bool(re.search(r'def.*health.*check|class.*Health', health_content))
        
        # Calculate score
        checks = [
            has_system_health,
            has_check_service_health,
            has_health_tracking,
            has_service_health_enum,
            has_health_checker,
            has_cb_in_health,
            has_overall_health,
            has_health_service
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 5  # At least 5 out of 8 checks should pass
        
        details = f"Health monitoring: {sum(checks)}/8 checks passed"
        if has_system_health and has_overall_health:
            details += " with comprehensive health reporting"
        
        return CheckResult(
            name="Health Monitoring",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_aws_service_adapters(self) -> CheckResult:
        """Check AWS service adapter implementations."""
        aws_services_path = self.infrastructure_path / "aws" / "services"
        
        if not aws_services_path.exists():
            return CheckResult(
                name="AWS Service Adapters",
                passed=False,
                score=0.0,
                details="AWS services directory not found",
                evidence=[]
            )
        
        evidence = []
        adapters_found = []
        
        # Expected adapter files
        expected_adapters = {
            "agent_core": ["agent_core_adapter.py", "dynamodb_adapter.py"],
            "search": ["opensearch_adapter.py", "search_adapter.py"],
            "compute": ["lambda_adapter.py", "compute_adapter.py"],
            "cache": ["elasticache_adapter.py", "cache_adapter.py"],
            "storage": ["s3_adapter.py", "storage_adapter.py"],
            "secrets": ["secrets_manager_adapter.py", "secrets_adapter.py"],
            "llm": ["llm_adapter.py", "bedrock_adapter.py"]
        }
        
        # Check for adapter files
        for service, possible_files in expected_adapters.items():
            for filename in possible_files:
                adapter_file = aws_services_path / filename
                if adapter_file.exists():
                    adapters_found.append(service)
                    evidence.append(f"{adapter_file.relative_to(self.workspace_root)}")
                    break
        
        # Check __init__.py for imports
        init_file = aws_services_path / "__init__.py"
        if init_file.exists():
            init_content = init_file.read_text()
            evidence.append(f"{init_file.relative_to(self.workspace_root)}")
            
            # Check for adapter imports
            for service in self.REQUIRED_SERVICES:
                adapter_class = ''.join(word.capitalize() for word in service.split('_')) + 'Adapter'
                if re.search(rf'AWS{adapter_class}|{adapter_class}', init_content):
                    if service not in adapters_found:
                        adapters_found.append(service)
        
        # Remove duplicates
        adapters_found = list(set(adapters_found))
        
        # Calculate score
        score = (len(adapters_found) / len(self.REQUIRED_SERVICES)) * 100
        passed = len(adapters_found) >= len(self.REQUIRED_SERVICES) * 0.7  # At least 70% coverage
        
        details = f"AWS adapters: {len(adapters_found)}/{len(self.REQUIRED_SERVICES)} services have adapters"
        if adapters_found:
            details += f" ({', '.join(adapters_found)})"
        
        return CheckResult(
            name="AWS Service Adapters",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_local_service_fallbacks(self) -> CheckResult:
        """Check local service fallback implementations."""
        local_services_path = self.infrastructure_path / "local" / "services"
        
        if not local_services_path.exists():
            return CheckResult(
                name="Local Service Fallbacks",
                passed=False,
                score=0.0,
                details="Local services directory not found",
                evidence=[]
            )
        
        evidence = []
        local_services_found = []
        
        # Expected local service files
        expected_services = {
            "agent_core": ["memory_service.py", "local_memory_service.py"],
            "search": ["search_service.py", "local_search_service.py"],
            "compute": ["job_runner.py", "local_job_runner.py"],
            "cache": ["cache_service.py", "local_cache_service.py"],
            "storage": ["file_store.py", "local_file_store_service.py"],
            "secrets": ["secrets_service.py", "local_secrets_service.py"],
            "llm": ["llm_service.py", "local_llm_service.py"]
        }
        
        # Check for local service files
        for service, possible_files in expected_services.items():
            for filename in possible_files:
                service_file = local_services_path / filename
                if service_file.exists():
                    local_services_found.append(service)
                    evidence.append(f"{service_file.relative_to(self.workspace_root)}")
                    break
        
        # Check __init__.py for imports
        init_file = local_services_path / "__init__.py"
        if init_file.exists():
            init_content = init_file.read_text()
            evidence.append(f"{init_file.relative_to(self.workspace_root)}")
            
            # Check for service imports
            for service in self.REQUIRED_SERVICES:
                service_class = ''.join(word.capitalize() for word in service.split('_')) + 'Service'
                if re.search(rf'Local{service_class}|{service_class}', init_content):
                    if service not in local_services_found:
                        local_services_found.append(service)
        
        # Remove duplicates
        local_services_found = list(set(local_services_found))
        
        # Calculate score
        score = (len(local_services_found) / len(self.REQUIRED_SERVICES)) * 100
        passed = len(local_services_found) >= len(self.REQUIRED_SERVICES) * 0.6  # At least 60% coverage
        
        details = f"Local fallbacks: {len(local_services_found)}/{len(self.REQUIRED_SERVICES)} services have local implementations"
        if local_services_found:
            details += f" ({', '.join(local_services_found)})"
        
        return CheckResult(
            name="Local Service Fallbacks",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
