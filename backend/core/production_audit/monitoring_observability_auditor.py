"""Monitoring and Observability Auditor for production readiness assessment."""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class MonitoringObservabilityAuditor(AuditModule):
    """
    Auditor for monitoring and observability infrastructure.
    
    Evaluates:
    - CloudWatch dashboards and metrics
    - Prometheus metrics implementation
    - Alarm configuration
    - Structured logging with trace IDs
    """
    
    CATEGORY_NAME = "Monitoring and Observability"
    CATEGORY_WEIGHT = 0.12  # 12% of overall score
    
    def __init__(self, workspace_root: str = None):
        """Initialize Monitoring and Observability Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.observability_modules_path = self.backend_path / "modules" / "observability"
        self.observability_services_path = self.backend_path / "services" / "observability"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform monitoring and observability audit."""
        logger.info("Starting Monitoring and Observability audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: CloudWatch Dashboards
        dashboards_check = await self._check_cloudwatch_dashboards()
        checks.append(dashboards_check)
        if not dashboards_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Missing or incomplete CloudWatch dashboards",
                impact="Limited visibility into system health and LLM usage patterns",
                recommendation="Create comprehensive CloudWatch dashboards for LLM usage, agent health, and system metrics",
                estimated_effort="2-3 days"
            ))
        
        # Check 2: Prometheus Metrics
        prometheus_check = await self._check_prometheus_metrics()
        checks.append(prometheus_check)
        if not prometheus_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Incomplete Prometheus metrics implementation",
                impact="Reduced ability to monitor system performance and detect issues",
                recommendation="Implement comprehensive Prometheus metrics for all critical operations",
                estimated_effort="2-3 days"
            ))
        
        # Check 3: Alarm Configuration
        alarms_check = await self._check_alarm_configuration()
        checks.append(alarms_check)
        if not alarms_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Missing or incomplete alarm configuration",
                impact="System issues may not be detected and alerted in time",
                recommendation="Configure alarms for high error rates, high costs, circuit breaker trips, and latency issues",
                estimated_effort="1-2 days"
            ))
        
        # Check 4: Structured Logging
        logging_check = await self._check_structured_logging()
        checks.append(logging_check)
        if not logging_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Incomplete structured logging implementation",
                impact="Difficult to trace requests and debug issues in production",
                recommendation="Implement structured logging with trace IDs, tenant IDs, and cost tracking",
                estimated_effort="2-3 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Monitoring and observability infrastructure is production-ready")
        else:
            recommendations.append("Complete monitoring infrastructure before production deployment")
            recommendations.append("Ensure all critical metrics are tracked and alerted")
            recommendations.append("Implement comprehensive structured logging for debugging")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Monitoring and Observability audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_cloudwatch_dashboards(self) -> CheckResult:
        """Check CloudWatch dashboard implementation."""
        dashboards_path = self.observability_modules_path / "dashboards"
        
        if not dashboards_path.exists():
            return CheckResult(
                name="CloudWatch Dashboards",
                passed=False,
                score=0.0,
                details="Dashboards directory not found",
                evidence=[]
            )
        
        evidence = []
        dashboard_files = []
        
        # Find dashboard files
        for dashboard_file in dashboards_path.glob("*.json"):
            dashboard_files.append(dashboard_file)
            evidence.append(f"{dashboard_file.relative_to(self.workspace_root)}")
        
        # Check CloudWatch implementation
        cloudwatch_file = self.observability_modules_path / "cloudwatch.py"
        has_cloudwatch_impl = False
        has_dashboard_creation = False
        has_metrics_recording = False
        
        if cloudwatch_file.exists():
            evidence.append(f"{cloudwatch_file.relative_to(self.workspace_root)}")
            content = cloudwatch_file.read_text()
            
            has_cloudwatch_impl = bool(re.search(r'class\s+CloudWatch', content))
            has_dashboard_creation = bool(re.search(r'create.*dashboard|put_dashboard', content, re.IGNORECASE))
            has_metrics_recording = bool(re.search(r'put_metric|record.*metric', content, re.IGNORECASE))
        
        # Check for LLM usage dashboard
        has_llm_dashboard = any("llm" in f.name.lower() for f in dashboard_files)
        
        # Check for agent health dashboard
        has_agent_dashboard = any("agent" in f.name.lower() for f in dashboard_files)
        
        # Calculate score
        checks = [
            len(dashboard_files) > 0,
            has_cloudwatch_impl,
            has_dashboard_creation,
            has_metrics_recording,
            has_llm_dashboard
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 5 checks should pass
        
        details = f"CloudWatch: {len(dashboard_files)} dashboard files found"
        if has_cloudwatch_impl:
            details += ", implementation present"
        if has_llm_dashboard:
            details += ", LLM dashboard exists"
        if has_agent_dashboard:
            details += ", agent dashboard exists"
        
        return CheckResult(
            name="CloudWatch Dashboards",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_prometheus_metrics(self) -> CheckResult:
        """Check Prometheus metrics implementation."""
        metrics_file = self.observability_services_path / "metrics.py"
        
        if not metrics_file.exists():
            return CheckResult(
                name="Prometheus Metrics",
                passed=False,
                score=0.0,
                details="Metrics file not found",
                evidence=[]
            )
        
        content = metrics_file.read_text()
        evidence = [f"{metrics_file.relative_to(self.workspace_root)}"]
        
        # Check for prometheus_client usage
        has_prometheus_import = bool(re.search(r'from\s+prometheus_client\s+import|import\s+prometheus_client', content))
        
        # Check for metric types
        has_counter = bool(re.search(r'Counter\(', content))
        has_histogram = bool(re.search(r'Histogram\(', content))
        has_gauge = bool(re.search(r'Gauge\(', content))
        
        # Check for specific metrics
        has_http_metrics = bool(re.search(r'http_request|http_response', content, re.IGNORECASE))
        has_ai_metrics = bool(re.search(r'ai_request|llm_request|ai_cost|llm_cost', content, re.IGNORECASE))
        has_db_metrics = bool(re.search(r'db_query|database', content, re.IGNORECASE))
        has_error_metrics = bool(re.search(r'error|exception', content, re.IGNORECASE))
        
        # Check for circuit breaker metrics
        has_circuit_breaker_metrics = bool(re.search(r'circuit.*breaker', content, re.IGNORECASE))
        
        # Check for cost tracking
        has_cost_tracking = bool(re.search(r'cost|tokens.*used', content, re.IGNORECASE))
        
        # Check for metrics collector class
        has_metrics_collector = bool(re.search(r'class\s+MetricsCollector', content))
        
        # Calculate score
        checks = [
            has_prometheus_import,
            has_counter and has_histogram and has_gauge,
            has_http_metrics,
            has_ai_metrics,
            has_db_metrics,
            has_error_metrics,
            has_cost_tracking,
            has_metrics_collector
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 6  # At least 6 out of 8 checks should pass
        
        metric_types = []
        if has_http_metrics:
            metric_types.append("HTTP")
        if has_ai_metrics:
            metric_types.append("AI/LLM")
        if has_db_metrics:
            metric_types.append("Database")
        if has_error_metrics:
            metric_types.append("Errors")
        if has_circuit_breaker_metrics:
            metric_types.append("Circuit Breaker")
        
        details = f"Prometheus metrics: {', '.join(metric_types) if metric_types else 'None found'}"
        if has_cost_tracking:
            details += " with cost tracking"
        
        return CheckResult(
            name="Prometheus Metrics",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_alarm_configuration(self) -> CheckResult:
        """Check alarm configuration for system monitoring."""
        evidence = []
        
        # Check CloudWatch alarms in cloudwatch.py
        cloudwatch_file = self.observability_modules_path / "cloudwatch.py"
        has_alarm_creation = False
        has_error_alarm = False
        has_latency_alarm = False
        has_cost_alarm = False
        
        if cloudwatch_file.exists():
            evidence.append(f"{cloudwatch_file.relative_to(self.workspace_root)}")
            content = cloudwatch_file.read_text()
            
            has_alarm_creation = bool(re.search(r'create.*alarm|put_metric_alarm', content, re.IGNORECASE))
            has_error_alarm = bool(re.search(r'error.*alarm|high.*error', content, re.IGNORECASE))
            has_latency_alarm = bool(re.search(r'latency.*alarm|high.*latency', content, re.IGNORECASE))
            has_cost_alarm = bool(re.search(r'cost.*alarm|budget.*alarm', content, re.IGNORECASE))
        
        # Check for alarm definitions in infrastructure
        iac_path = self.backend_path / "infrastructure" / "aws" / "iac"
        alarm_files = []
        
        if iac_path.exists():
            for alarm_file in iac_path.rglob("*alarm*.py"):
                alarm_files.append(alarm_file)
                evidence.append(f"{alarm_file.relative_to(self.workspace_root)}")
        
        # Check for circuit breaker alarms
        circuit_breaker_path = self.backend_path / "core" / "circuit_breaker"
        has_circuit_breaker_monitoring = False
        
        if circuit_breaker_path.exists():
            for cb_file in circuit_breaker_path.glob("*.py"):
                content = cb_file.read_text()
                if re.search(r'alarm|alert|notify', content, re.IGNORECASE):
                    has_circuit_breaker_monitoring = True
                    evidence.append(f"{cb_file.relative_to(self.workspace_root)}")
                    break
        
        # Calculate score
        checks = [
            has_alarm_creation,
            has_error_alarm,
            has_latency_alarm,
            len(alarm_files) > 0 or has_cost_alarm,
            has_circuit_breaker_monitoring
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 5 checks should pass
        
        alarm_types = []
        if has_error_alarm:
            alarm_types.append("error rate")
        if has_latency_alarm:
            alarm_types.append("latency")
        if has_cost_alarm:
            alarm_types.append("cost")
        if has_circuit_breaker_monitoring:
            alarm_types.append("circuit breaker")
        
        details = f"Alarms: {', '.join(alarm_types) if alarm_types else 'None found'}"
        if len(alarm_files) > 0:
            details += f", {len(alarm_files)} alarm definition files"
        
        return CheckResult(
            name="Alarm Configuration",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_structured_logging(self) -> CheckResult:
        """Check structured logging implementation with trace IDs."""
        logger_file = self.observability_services_path / "logger.py"
        
        if not logger_file.exists():
            return CheckResult(
                name="Structured Logging",
                passed=False,
                score=0.0,
                details="Logger file not found",
                evidence=[]
            )
        
        content = logger_file.read_text()
        evidence = [f"{logger_file.relative_to(self.workspace_root)}"]
        
        # Check for structured logging implementation
        has_json_formatter = bool(re.search(r'class\s+.*Formatter|json\.dumps|JSONFormatter', content))
        
        # Check for context variables (trace IDs)
        has_context_vars = bool(re.search(r'ContextVar|contextvars|request_id|trace_id', content, re.IGNORECASE))
        
        # Check for request tracking
        has_request_tracking = bool(re.search(r'request_id|meeting_id|user_id', content, re.IGNORECASE))
        
        # Check for tenant ID logging
        has_tenant_logging = bool(re.search(r'tenant_id', content, re.IGNORECASE))
        
        # Check for cost logging
        has_cost_logging = bool(re.search(r'cost|tokens.*used', content, re.IGNORECASE))
        
        # Check for latency logging
        has_latency_logging = bool(re.search(r'duration|latency|elapsed', content, re.IGNORECASE))
        
        # Check for structured logger class
        has_logger_class = bool(re.search(r'class\s+.*Logger', content))
        
        # Check for log methods with extra fields
        has_extra_fields = bool(re.search(r'extra\s*=|kwargs|\*\*extra', content))
        
        # Check for AI/LLM specific logging
        has_ai_logging = bool(re.search(r'log_ai|ai_provider|ai_model', content, re.IGNORECASE))
        
        # Calculate score
        checks = [
            has_json_formatter,
            has_context_vars or has_request_tracking,
            has_tenant_logging,
            has_cost_logging,
            has_latency_logging,
            has_logger_class,
            has_extra_fields,
            has_ai_logging
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 6  # At least 6 out of 8 checks should pass
        
        features = []
        if has_json_formatter:
            features.append("JSON formatting")
        if has_context_vars or has_request_tracking:
            features.append("trace IDs")
        if has_tenant_logging:
            features.append("tenant tracking")
        if has_cost_logging:
            features.append("cost tracking")
        if has_ai_logging:
            features.append("AI logging")
        
        details = f"Structured logging: {', '.join(features) if features else 'Basic implementation'}"
        
        return CheckResult(
            name="Structured Logging",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
