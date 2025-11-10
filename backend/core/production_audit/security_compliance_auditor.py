"""Security and Compliance Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class SecurityComplianceAuditor(AuditModule):
    """
    Auditor for security and compliance across the system.
    
    Evaluates:
    - API key security (no hardcoded keys)
    - Multi-tenant isolation (middleware and tenant_id usage)
    - GDPR compliance for Agent Svea (EU region usage)
    - PII handling (masking implementation)
    """
    
    CATEGORY_NAME = "Security and Compliance"
    CATEGORY_WEIGHT = 0.15  # 15% of overall score
    
    # Patterns for detecting hardcoded API keys
    API_KEY_PATTERNS = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI keys
        r'AIza[a-zA-Z0-9_-]{35}',  # Google API keys
        r'AKIA[0-9A-Z]{16}',  # AWS access keys
        r'["\']api[_-]?key["\']\s*[:=]\s*["\'][a-zA-Z0-9]{20,}["\']',  # Generic API keys
        r'["\']secret[_-]?key["\']\s*[:=]\s*["\'][a-zA-Z0-9]{20,}["\']',  # Secret keys
        r'["\']password["\']\s*[:=]\s*["\'][^"\']{8,}["\']',  # Passwords
        r'Bearer\s+[a-zA-Z0-9_-]{20,}',  # Bearer tokens
    ]
    
    # File extensions to scan for security issues
    SCANNABLE_EXTENSIONS = {'.py', '.js', '.ts', '.tsx', '.yaml', '.yml', '.json', '.env.example'}
    
    # Directories to exclude from scanning
    EXCLUDED_DIRS = {
        'node_modules', '.git', '__pycache__', '.pytest_cache', 
        'venv', 'env', '.venv', 'dist', 'build', '.next'
    }
    
    def __init__(self, workspace_root: str = None):
        """Initialize Security and Compliance Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.frontend_path = Path(self.workspace_root) / "frontend"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform security and compliance audit."""
        logger.info("Starting Security and Compliance audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: API Key Security
        api_key_check = await self._check_api_key_security()
        checks.append(api_key_check)
        if not api_key_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Hardcoded API keys or secrets found in codebase",
                impact="Exposed credentials could lead to unauthorized access and security breaches",
                recommendation="Move all API keys to AWS Secrets Manager or environment variables. Remove hardcoded credentials from code.",
                estimated_effort="1-2 days"
            ))
        
        # Check 2: Multi-Tenant Isolation
        multi_tenant_check = await self._check_multi_tenant_isolation()
        checks.append(multi_tenant_check)
        if not multi_tenant_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Incomplete multi-tenant isolation implementation",
                impact="Data leakage between tenants could occur, violating data privacy requirements",
                recommendation="Implement tenant_id validation in all middleware and database queries. Ensure complete data isolation.",
                estimated_effort="3-5 days"
            ))
        
        # Check 3: GDPR Compliance for Agent Svea
        gdpr_check = await self._check_gdpr_compliance()
        checks.append(gdpr_check)
        if not gdpr_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="GDPR compliance not fully implemented for Agent Svea",
                impact="Non-compliance with EU data protection regulations could result in fines",
                recommendation="Ensure Agent Svea uses EU regions for data storage and processing. Implement data retention and deletion policies.",
                estimated_effort="2-3 days"
            ))
        
        # Check 4: PII Handling
        pii_check = await self._check_pii_handling()
        checks.append(pii_check)
        if not pii_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="PII masking or protection not fully implemented",
                impact="Sensitive personal data could be exposed in logs or sent to external LLM services",
                recommendation="Implement PII detection and masking before logging or sending data to LLMs. Use data classification.",
                estimated_effort="3-4 days"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Security and compliance measures are production-ready")
            recommendations.append("Continue regular security audits and penetration testing")
        else:
            if not api_key_check.passed:
                recommendations.append("CRITICAL: Remove all hardcoded API keys immediately")
            if not multi_tenant_check.passed:
                recommendations.append("CRITICAL: Complete multi-tenant isolation before production deployment")
            if not gdpr_check.passed:
                recommendations.append("Ensure GDPR compliance for EU customers, especially Agent Svea")
            if not pii_check.passed:
                recommendations.append("Implement comprehensive PII protection across all data flows")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Security and Compliance audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_api_key_security(self) -> CheckResult:
        """Check for hardcoded API keys and secrets in codebase."""
        logger.info("Checking for hardcoded API keys...")
        
        violations = []
        evidence = []
        files_scanned = 0
        
        # Scan backend and frontend directories
        for base_path in [self.backend_path, self.frontend_path]:
            if not base_path.exists():
                continue
            
            for file_path in self._get_scannable_files(base_path):
                files_scanned += 1
                
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # Skip if it's an example or test file with dummy keys
                    if self._is_example_or_test_file(file_path):
                        continue
                    
                    # Check for API key patterns
                    for pattern in self.API_KEY_PATTERNS:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Get context around the match
                            start = max(0, match.start() - 50)
                            end = min(len(content), match.end() + 50)
                            context = content[start:end].replace('\n', ' ')
                            
                            # Skip if it's a comment explaining the pattern
                            if self._is_safe_context(context):
                                continue
                            
                            violations.append({
                                'file': str(file_path.relative_to(self.workspace_root)),
                                'pattern': pattern,
                                'context': context[:100]
                            })
                            evidence.append(f"{file_path.relative_to(self.workspace_root)}")
                            break  # Only report once per file
                
                except Exception as e:
                    logger.warning(f"Error scanning {file_path}: {e}")
        
        # Check for proper secrets management
        secrets_manager_usage = self._check_secrets_manager_usage()
        env_var_usage = self._check_env_var_usage()
        
        # Calculate score
        has_no_violations = len(violations) == 0
        uses_secrets_manager = secrets_manager_usage
        uses_env_vars = env_var_usage
        has_env_example = (Path(self.workspace_root) / ".env.example").exists()
        
        checks = [has_no_violations, uses_secrets_manager, uses_env_vars, has_env_example]
        score = (sum(checks) / len(checks)) * 100
        passed = has_no_violations and (uses_secrets_manager or uses_env_vars)
        
        details = f"API Key Security: Scanned {files_scanned} files, found {len(violations)} potential violations"
        if uses_secrets_manager:
            details += ", uses AWS Secrets Manager"
        if uses_env_vars:
            details += ", uses environment variables"
        
        if violations:
            details += f". Violations in: {', '.join(set(v['file'] for v in violations[:5]))}"
        
        return CheckResult(
            name="API Key Security",
            passed=passed,
            score=score,
            details=details,
            evidence=list(set(evidence))[:10]  # Limit evidence to 10 files
        )
    
    async def _check_multi_tenant_isolation(self) -> CheckResult:
        """Check multi-tenant isolation implementation."""
        logger.info("Checking multi-tenant isolation...")
        
        evidence = []
        
        # Check for tenant isolation middleware
        middleware_path = self.backend_path / "middleware" / "tenant_isolation_middleware.py"
        has_middleware = middleware_path.exists()
        if has_middleware:
            evidence.append(f"{middleware_path.relative_to(self.workspace_root)}")
        
        # Check for tenant_id in auth module
        auth_path = self.backend_path / "modules" / "auth" / "tenant_isolation.py"
        has_auth_isolation = auth_path.exists()
        if has_auth_isolation:
            evidence.append(f"{auth_path.relative_to(self.workspace_root)}")
        
        # Check for tenant_id usage in database queries
        tenant_id_usage_count = 0
        database_files = []
        
        # Scan repository and database modules
        repo_path = self.backend_path / "modules" / "database" / "repository"
        if repo_path.exists():
            for py_file in repo_path.glob("*.py"):
                content = py_file.read_text()
                if re.search(r'tenant_id', content, re.IGNORECASE):
                    tenant_id_usage_count += 1
                    database_files.append(py_file)
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
        
        # Check for tenant context in models
        models_path = self.backend_path / "modules" / "models"
        tenant_models = []
        if models_path.exists():
            for py_file in models_path.glob("*.py"):
                content = py_file.read_text()
                if re.search(r'tenant_id.*:.*str|tenant_id.*=.*Field', content):
                    tenant_models.append(py_file)
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
        
        # Check for tenant validation in routes
        routes_path = self.backend_path / "routes"
        tenant_validated_routes = 0
        if routes_path.exists():
            for py_file in routes_path.glob("*_routes.py"):
                content = py_file.read_text()
                if re.search(r'tenant_id|get_current_tenant', content, re.IGNORECASE):
                    tenant_validated_routes += 1
        
        # Check for tenant context provider
        tenant_context_path = self.backend_path / "core" / "tenants"
        has_tenant_context = tenant_context_path.exists()
        if has_tenant_context:
            evidence.append(f"{tenant_context_path.relative_to(self.workspace_root)}")
        
        # Calculate score
        checks = [
            has_middleware,
            has_auth_isolation,
            tenant_id_usage_count >= 3,  # At least 3 database files use tenant_id
            len(tenant_models) >= 2,  # At least 2 models have tenant_id
            tenant_validated_routes >= 3,  # At least 3 routes validate tenant
            has_tenant_context
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 5  # At least 5 out of 6 checks should pass
        
        details = (f"Multi-tenant isolation: middleware={has_middleware}, "
                  f"auth_isolation={has_auth_isolation}, "
                  f"tenant_id_in_db={tenant_id_usage_count} files, "
                  f"tenant_models={len(tenant_models)}, "
                  f"validated_routes={tenant_validated_routes}")
        
        return CheckResult(
            name="Multi-Tenant Isolation",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence[:15]  # Limit evidence
        )
    
    async def _check_gdpr_compliance(self) -> CheckResult:
        """Check GDPR compliance for Agent Svea."""
        logger.info("Checking GDPR compliance...")
        
        evidence = []
        
        # Check Agent Svea configuration for EU region
        agent_svea_path = self.backend_path / "agents" / "agent_svea"
        
        eu_region_configured = False
        data_retention_policy = False
        right_to_deletion = False
        
        if agent_svea_path.exists():
            # Check for EU region configuration
            for config_file in agent_svea_path.rglob("*.py"):
                content = config_file.read_text()
                
                # Check for EU region
                if re.search(r'eu-west|eu-central|eu-north|europe', content, re.IGNORECASE):
                    eu_region_configured = True
                    evidence.append(f"{config_file.relative_to(self.workspace_root)}")
                
                # Check for data retention
                if re.search(r'retention|delete.*after|expire', content, re.IGNORECASE):
                    data_retention_policy = True
                
                # Check for deletion capability
                if re.search(r'delete.*user.*data|right.*to.*deletion|gdpr.*delete', content, re.IGNORECASE):
                    right_to_deletion = True
        
        # Check for GDPR compliance service
        compliance_service_path = agent_svea_path / "services" / "compliance_service.py"
        has_compliance_service = compliance_service_path.exists()
        if has_compliance_service:
            evidence.append(f"{compliance_service_path.relative_to(self.workspace_root)}")
            
            content = compliance_service_path.read_text()
            if re.search(r'gdpr', content, re.IGNORECASE):
                data_retention_policy = True
        
        # Check infrastructure configuration
        iac_path = self.backend_path / "infrastructure" / "aws" / "iac"
        if iac_path.exists():
            for iac_file in iac_path.rglob("*.py"):
                content = iac_file.read_text()
                if re.search(r'eu-west|eu-central|eu-north', content, re.IGNORECASE):
                    eu_region_configured = True
                    evidence.append(f"{iac_file.relative_to(self.workspace_root)}")
        
        # Check for data portability
        data_portability = False
        if agent_svea_path.exists():
            for py_file in agent_svea_path.rglob("*.py"):
                content = py_file.read_text()
                if re.search(r'export.*data|data.*portability', content, re.IGNORECASE):
                    data_portability = True
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
                    break
        
        # Calculate score
        checks = [
            eu_region_configured,
            has_compliance_service,
            data_retention_policy,
            right_to_deletion,
            data_portability
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 5 checks should pass
        
        details = (f"GDPR compliance: EU_region={eu_region_configured}, "
                  f"compliance_service={has_compliance_service}, "
                  f"retention_policy={data_retention_policy}, "
                  f"right_to_deletion={right_to_deletion}, "
                  f"data_portability={data_portability}")
        
        return CheckResult(
            name="GDPR Compliance",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_pii_handling(self) -> CheckResult:
        """Check PII handling and masking implementation."""
        logger.info("Checking PII handling...")
        
        evidence = []
        
        # Check for PII masking implementation
        pii_masking_files = []
        
        # Search for PII-related code
        for base_path in [self.backend_path]:
            if not base_path.exists():
                continue
            
            for py_file in base_path.rglob("*.py"):
                if any(excluded in py_file.parts for excluded in self.EXCLUDED_DIRS):
                    continue
                
                try:
                    content = py_file.read_text()
                    
                    # Check for PII masking functions
                    if re.search(r'mask.*pii|pii.*mask|redact|sanitize.*pii', content, re.IGNORECASE):
                        pii_masking_files.append(py_file)
                        evidence.append(f"{py_file.relative_to(self.workspace_root)}")
                
                except Exception as e:
                    logger.warning(f"Error scanning {py_file}: {e}")
        
        has_pii_masking = len(pii_masking_files) > 0
        
        # Check logging configuration for PII protection
        logging_files = []
        pii_protected_logging = False
        
        observability_path = self.backend_path / "modules" / "observability"
        if observability_path.exists():
            for py_file in observability_path.glob("*.py"):
                content = py_file.read_text()
                
                # Check for structured logging with PII protection
                if re.search(r'structlog|logging', content):
                    logging_files.append(py_file)
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
                    
                    if re.search(r'mask|redact|sanitize|pii', content, re.IGNORECASE):
                        pii_protected_logging = True
        
        # Check for PII detection before LLM calls
        pii_detection_before_llm = False
        llm_service_path = self.backend_path / "core" / "llm" / "llm_service.py"
        
        if llm_service_path.exists():
            content = llm_service_path.read_text()
            evidence.append(f"{llm_service_path.relative_to(self.workspace_root)}")
            
            # Check for PII detection or masking before LLM calls
            if re.search(r'mask.*before|sanitize.*before|pii.*check', content, re.IGNORECASE):
                pii_detection_before_llm = True
        
        # Check for data classification
        has_data_classification = False
        for py_file in self.backend_path.rglob("*.py"):
            if any(excluded in py_file.parts for excluded in self.EXCLUDED_DIRS):
                continue
            
            try:
                content = py_file.read_text()
                if re.search(r'class.*DataClassification|data.*classification|sensitive.*data', content, re.IGNORECASE):
                    has_data_classification = True
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
                    break
            except Exception:
                pass
        
        # Check for encryption of sensitive data
        has_encryption = False
        for py_file in self.backend_path.rglob("*.py"):
            if any(excluded in py_file.parts for excluded in self.EXCLUDED_DIRS):
                continue
            
            try:
                content = py_file.read_text()
                if re.search(r'encrypt|cipher|kms|cryptography', content, re.IGNORECASE):
                    has_encryption = True
                    evidence.append(f"{py_file.relative_to(self.workspace_root)}")
                    break
            except Exception:
                pass
        
        # Calculate score
        checks = [
            has_pii_masking,
            pii_protected_logging or len(logging_files) > 0,
            pii_detection_before_llm,
            has_data_classification,
            has_encryption
        ]
        
        score = (sum(checks) / len(checks)) * 100
        passed = sum(checks) >= 3  # At least 3 out of 5 checks should pass
        
        details = (f"PII handling: masking={has_pii_masking}, "
                  f"protected_logging={pii_protected_logging}, "
                  f"llm_protection={pii_detection_before_llm}, "
                  f"classification={has_data_classification}, "
                  f"encryption={has_encryption}")
        
        return CheckResult(
            name="PII Handling",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence[:15]  # Limit evidence
        )
    
    def _get_scannable_files(self, base_path: Path) -> List[Path]:
        """Get list of files to scan for security issues."""
        scannable_files = []
        
        for file_path in base_path.rglob("*"):
            # Skip directories
            if not file_path.is_file():
                continue
            
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in self.EXCLUDED_DIRS):
                continue
            
            # Only scan specific file types
            if file_path.suffix in self.SCANNABLE_EXTENSIONS:
                scannable_files.append(file_path)
        
        return scannable_files
    
    def _is_example_or_test_file(self, file_path: Path) -> bool:
        """Check if file is an example or test file."""
        name_lower = file_path.name.lower()
        
        # Check filename
        if any(keyword in name_lower for keyword in ['example', 'test', 'mock', 'dummy', 'sample']):
            return True
        
        # Check if in test directory
        if 'test' in file_path.parts or '__tests__' in file_path.parts:
            return True
        
        # Check for .env.example
        if file_path.name == '.env.example':
            return True
        
        return False
    
    def _is_safe_context(self, context: str) -> bool:
        """Check if the context around a potential key is safe (e.g., comment, documentation)."""
        context_lower = context.lower()
        
        # Check for comments
        if '#' in context or '//' in context or '/*' in context:
            return True
        
        # Check for documentation keywords
        safe_keywords = ['example', 'placeholder', 'your_key_here', 'replace', 'dummy', 'test']
        if any(keyword in context_lower for keyword in safe_keywords):
            return True
        
        return False
    
    def _check_secrets_manager_usage(self) -> bool:
        """Check if AWS Secrets Manager is used."""
        secrets_path = self.backend_path / "infrastructure" / "aws" / "services" / "secrets_manager.py"
        
        if not secrets_path.exists():
            return False
        
        content = secrets_path.read_text()
        return bool(re.search(r'get_secret|SecretsManager', content))
    
    def _check_env_var_usage(self) -> bool:
        """Check if environment variables are used for configuration."""
        settings_path = self.backend_path / "core" / "settings.py"
        
        if not settings_path.exists():
            # Try alternative location
            settings_path = self.backend_path / "modules" / "config" / "settings.py"
        
        if not settings_path.exists():
            return False
        
        content = settings_path.read_text()
        return bool(re.search(r'os\.environ|getenv|BaseSettings|Field.*env', content))
