"""Testing Coverage Auditor for production readiness assessment."""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from .base import AuditModule
from .models import AuditResult, CheckResult, Gap, GapSeverity

logger = logging.getLogger(__name__)


class TestingCoverageAuditor(AuditModule):
    """
    Auditor for testing coverage across all agent teams.
    
    Evaluates:
    - Total test count (target: 48+ tests)
    - Test coverage per agent team (MeetMind, Agent Svea, Felicia's Finance)
    - Fallback logic testing
    - Swedish language support testing for Agent Svea
    - Test quality (tests pass with and without API keys)
    """
    
    CATEGORY_NAME = "Testing Coverage"
    CATEGORY_WEIGHT = 0.15  # 15% of overall score
    
    # Test count targets
    MINIMUM_TESTS = 48
    RECOMMENDED_TESTS = 60
    
    def __init__(self, workspace_root: str = None):
        """Initialize Testing Coverage Auditor."""
        super().__init__(workspace_root)
        self.backend_path = Path(self.workspace_root) / "backend"
        self.tests_path = self.backend_path / "tests"
        self.agents_path = self.backend_path / "agents"
        
    def get_category_name(self) -> str:
        """Get audit category name."""
        return self.CATEGORY_NAME
    
    def get_weight(self) -> float:
        """Get category weight for overall score."""
        return self.CATEGORY_WEIGHT
    
    async def audit(self) -> AuditResult:
        """Perform testing coverage audit."""
        logger.info("Starting Testing Coverage audit...")
        
        checks = []
        gaps = []
        recommendations = []
        
        # Check 1: Total test count
        test_count_check = await self._check_test_count()
        checks.append(test_count_check)
        if not test_count_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description=f"Insufficient test coverage (found {test_count_check.details.split()[0]} tests, need {self.MINIMUM_TESTS}+)",
                impact="System may have undetected bugs that could cause production failures",
                recommendation=f"Add more tests to reach minimum of {self.MINIMUM_TESTS} tests covering all critical functionality",
                estimated_effort="3-5 days"
            ))
        
        # Check 2: Agent team coverage
        agent_coverage_check = await self._check_agent_team_coverage()
        checks.append(agent_coverage_check)
        if not agent_coverage_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.HIGH,
                description="Incomplete test coverage for one or more agent teams",
                impact="Agent teams without proper testing may fail in production",
                recommendation="Add comprehensive integration tests for all agent teams (MeetMind, Agent Svea, Felicia's Finance)",
                estimated_effort="2-3 days"
            ))
        
        # Check 3: Test quality (pass with/without API keys)
        test_quality_check = await self._check_test_quality()
        checks.append(test_quality_check)
        if not test_quality_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Tests may not handle missing API keys gracefully",
                impact="Tests may fail in CI/CD environments without API keys",
                recommendation="Ensure all tests work with fallback logic when API keys are unavailable",
                estimated_effort="1-2 days"
            ))
        
        # Check 4: Fallback logic testing
        fallback_testing_check = await self._check_fallback_testing()
        checks.append(fallback_testing_check)
        if not fallback_testing_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.CRITICAL,
                description="Insufficient testing of fallback logic",
                impact="Fallback mechanisms may not work correctly when LLM services fail",
                recommendation="Add dedicated tests for fallback logic in all agents",
                estimated_effort="2-3 days"
            ))
        
        # Check 5: Swedish language testing
        swedish_testing_check = await self._check_swedish_language_testing()
        checks.append(swedish_testing_check)
        if not swedish_testing_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.MEDIUM,
                description="Insufficient testing of Swedish language support for Agent Svea",
                impact="Agent Svea may not handle Swedish compliance correctly",
                recommendation="Add tests with Swedish prompts and validate Swedish responses",
                estimated_effort="1-2 days"
            ))
        
        # Check 6: Test coverage summary analysis
        coverage_summary_check = await self._check_coverage_summary()
        checks.append(coverage_summary_check)
        if not coverage_summary_check.passed:
            gaps.append(Gap(
                category=self.CATEGORY_NAME,
                severity=GapSeverity.LOW,
                description="Test coverage summary is missing or incomplete",
                impact="Difficult to track test coverage and identify gaps",
                recommendation="Create or update TEST_COVERAGE_SUMMARY.md with detailed coverage information",
                estimated_effort="1 day"
            ))
        
        # Generate recommendations
        if all(check.passed for check in checks):
            recommendations.append("Testing coverage is comprehensive and production-ready")
            recommendations.append("Consider adding performance and load tests for additional validation")
        else:
            recommendations.append("Increase test coverage to meet minimum requirements before production")
            recommendations.append("Ensure all tests work with fallback logic (no API keys required)")
            recommendations.append("Add dedicated tests for critical failure scenarios")
        
        # Calculate overall score
        score = self._calculate_category_score(checks)
        
        logger.info(f"Testing Coverage audit complete. Score: {score:.2f}/100")
        
        return AuditResult(
            category=self.CATEGORY_NAME,
            score=score,
            weight=self.CATEGORY_WEIGHT,
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    async def _check_test_count(self) -> CheckResult:
        """Check total number of tests across the codebase."""
        test_files = []
        total_tests = 0
        evidence = []
        
        # Find all test files
        test_patterns = [
            self.tests_path.glob("test_*.py"),
            self.agents_path.glob("*/test_*.py"),
            self.agents_path.glob("*/*/test_*.py"),
        ]
        
        for pattern in test_patterns:
            for test_file in pattern:
                if test_file.is_file() and "__pycache__" not in str(test_file):
                    test_files.append(test_file)
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                    
                    # Count test functions in file
                    try:
                        content = test_file.read_text()
                        # Count test functions (def test_* or async def test_*)
                        test_functions = re.findall(r'(?:async\s+)?def\s+test_\w+', content)
                        total_tests += len(test_functions)
                    except Exception as e:
                        logger.warning(f"Could not read test file {test_file}: {e}")
        
        # Calculate score based on test count
        if total_tests >= self.RECOMMENDED_TESTS:
            score = 100.0
        elif total_tests >= self.MINIMUM_TESTS:
            # Linear scale between minimum and recommended
            score = 80.0 + (20.0 * (total_tests - self.MINIMUM_TESTS) / (self.RECOMMENDED_TESTS - self.MINIMUM_TESTS))
        else:
            # Linear scale from 0 to 80 based on progress to minimum
            score = (total_tests / self.MINIMUM_TESTS) * 80.0
        
        passed = total_tests >= self.MINIMUM_TESTS
        
        details = (f"{total_tests} test functions found across {len(test_files)} test files "
                  f"(minimum: {self.MINIMUM_TESTS}, recommended: {self.RECOMMENDED_TESTS})")
        
        return CheckResult(
            name="Total Test Count",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence[:20]  # Limit evidence to first 20 files
        )
    
    async def _check_agent_team_coverage(self) -> CheckResult:
        """Check test coverage for each agent team."""
        teams = {
            "MeetMind": self.agents_path / "meetmind",
            "Agent Svea": self.agents_path / "agent_svea",
            "Felicia's Finance": self.agents_path / "felicias_finance"
        }
        
        team_results = {}
        evidence = []
        
        for team_name, team_path in teams.items():
            if not team_path.exists():
                team_results[team_name] = {"tests": 0, "files": []}
                continue
            
            test_files = list(team_path.glob("test_*.py"))
            test_count = 0
            
            for test_file in test_files:
                try:
                    content = test_file.read_text()
                    test_functions = re.findall(r'(?:async\s+)?def\s+test_\w+', content)
                    test_count += len(test_functions)
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                except Exception as e:
                    logger.warning(f"Could not read test file {test_file}: {e}")
            
            team_results[team_name] = {
                "tests": test_count,
                "files": len(test_files)
            }
        
        # Calculate score based on team coverage
        teams_with_tests = sum(1 for result in team_results.values() if result["tests"] >= 5)
        teams_with_good_coverage = sum(1 for result in team_results.values() if result["tests"] >= 10)
        
        # Score: 50% for having tests, 50% for good coverage
        score = (teams_with_tests / len(teams)) * 50 + (teams_with_good_coverage / len(teams)) * 50
        passed = teams_with_tests == len(teams) and teams_with_good_coverage >= 2
        
        details_parts = []
        for team_name, result in team_results.items():
            details_parts.append(f"{team_name}: {result['tests']} tests in {result['files']} files")
        
        details = "; ".join(details_parts)
        
        return CheckResult(
            name="Agent Team Test Coverage",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_test_quality(self) -> CheckResult:
        """Check if tests handle missing API keys gracefully."""
        test_files = []
        evidence = []
        
        # Find all test files
        for test_file in self.tests_path.glob("test_*.py"):
            if test_file.is_file():
                test_files.append(test_file)
        
        for test_file in self.agents_path.glob("*/test_*.py"):
            if test_file.is_file():
                test_files.append(test_file)
        
        tests_with_api_key_handling = 0
        tests_with_mock_llm = 0
        tests_with_fallback_validation = 0
        
        for test_file in test_files:
            try:
                content = test_file.read_text()
                
                # Check for API key handling
                if re.search(r'OPENAI_API_KEY|API_KEY|api_key', content):
                    tests_with_api_key_handling += 1
                    
                # Check for mock LLM usage
                if re.search(r'mock.*llm|MockLLM|mock_llm_service', content, re.IGNORECASE):
                    tests_with_mock_llm += 1
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                
                # Check for fallback validation
                if re.search(r'fallback|without.*llm|no.*api', content, re.IGNORECASE):
                    tests_with_fallback_validation += 1
                    
            except Exception as e:
                logger.warning(f"Could not read test file {test_file}: {e}")
        
        # Calculate score
        total_files = len(test_files)
        if total_files == 0:
            return CheckResult(
                name="Test Quality",
                passed=False,
                score=0.0,
                details="No test files found",
                evidence=[]
            )
        
        api_key_score = (tests_with_api_key_handling / total_files) * 40
        mock_score = (tests_with_mock_llm / total_files) * 30
        fallback_score = (tests_with_fallback_validation / total_files) * 30
        
        score = api_key_score + mock_score + fallback_score
        passed = (tests_with_api_key_handling >= total_files * 0.3 and 
                 tests_with_fallback_validation >= 3)
        
        details = (f"Test quality: {tests_with_api_key_handling}/{total_files} handle API keys, "
                  f"{tests_with_mock_llm} use mocks, "
                  f"{tests_with_fallback_validation} validate fallback")
        
        return CheckResult(
            name="Test Quality",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence[:10]
        )
    
    async def _check_fallback_testing(self) -> CheckResult:
        """Check if fallback logic is properly tested."""
        test_files = []
        evidence = []
        
        # Find all test files
        for test_file in self.tests_path.glob("test_*.py"):
            if test_file.is_file():
                test_files.append(test_file)
        
        for test_file in self.agents_path.glob("*/test_*.py"):
            if test_file.is_file():
                test_files.append(test_file)
        
        fallback_test_count = 0
        files_with_fallback_tests = []
        
        for test_file in test_files:
            try:
                content = test_file.read_text()
                
                # Look for fallback-related test functions
                fallback_tests = re.findall(
                    r'(?:async\s+)?def\s+(test_\w*fallback\w*|test_\w*without_\w*llm\w*|test_\w*no_\w*api\w*)',
                    content,
                    re.IGNORECASE
                )
                
                if fallback_tests:
                    fallback_test_count += len(fallback_tests)
                    files_with_fallback_tests.append(test_file)
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                
                # Also check for fallback assertions in any test
                if re.search(r'assert.*fallback|fallback.*assert', content, re.IGNORECASE):
                    if test_file not in files_with_fallback_tests:
                        files_with_fallback_tests.append(test_file)
                        evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                        
            except Exception as e:
                logger.warning(f"Could not read test file {test_file}: {e}")
        
        # Calculate score
        # Target: at least 10 fallback tests across 5+ files
        test_count_score = min(fallback_test_count / 10, 1.0) * 60
        file_coverage_score = min(len(files_with_fallback_tests) / 5, 1.0) * 40
        
        score = test_count_score + file_coverage_score
        passed = fallback_test_count >= 10 and len(files_with_fallback_tests) >= 5
        
        details = (f"Fallback testing: {fallback_test_count} fallback tests found "
                  f"across {len(files_with_fallback_tests)} test files")
        
        return CheckResult(
            name="Fallback Logic Testing",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_swedish_language_testing(self) -> CheckResult:
        """Check if Swedish language support is tested for Agent Svea."""
        agent_svea_path = self.agents_path / "agent_svea"
        
        if not agent_svea_path.exists():
            return CheckResult(
                name="Swedish Language Testing",
                passed=False,
                score=0.0,
                details="Agent Svea directory not found",
                evidence=[]
            )
        
        test_files = list(agent_svea_path.glob("test_*.py"))
        evidence = []
        
        swedish_test_count = 0
        files_with_swedish_tests = []
        
        for test_file in test_files:
            try:
                content = test_file.read_text()
                
                # Look for Swedish language indicators
                swedish_patterns = [
                    r'svenska|swedish|svensk',
                    r'BAS|SIE|bokföring',
                    r'moms|VAT.*svensk',
                    r'GDPR.*svensk|svensk.*GDPR',
                    r'ERPNext.*svensk|svensk.*ERP'
                ]
                
                has_swedish = False
                for pattern in swedish_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        has_swedish = True
                        break
                
                if has_swedish:
                    # Count test functions in this file
                    test_functions = re.findall(r'(?:async\s+)?def\s+test_\w+', content)
                    swedish_test_count += len(test_functions)
                    files_with_swedish_tests.append(test_file)
                    evidence.append(f"{test_file.relative_to(self.workspace_root)}")
                    
            except Exception as e:
                logger.warning(f"Could not read test file {test_file}: {e}")
        
        # Calculate score
        # Target: at least 5 tests with Swedish content across 2+ files
        test_count_score = min(swedish_test_count / 5, 1.0) * 70
        file_coverage_score = min(len(files_with_swedish_tests) / 2, 1.0) * 30
        
        score = test_count_score + file_coverage_score
        passed = swedish_test_count >= 5 and len(files_with_swedish_tests) >= 2
        
        details = (f"Swedish language testing: {swedish_test_count} tests with Swedish content "
                  f"found across {len(files_with_swedish_tests)} test files")
        
        return CheckResult(
            name="Swedish Language Testing",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence
        )
    
    async def _check_coverage_summary(self) -> CheckResult:
        """Check if test coverage summary document exists and is complete."""
        summary_file = self.tests_path / "TEST_COVERAGE_SUMMARY.md"
        
        if not summary_file.exists():
            return CheckResult(
                name="Test Coverage Summary",
                passed=False,
                score=0.0,
                details="TEST_COVERAGE_SUMMARY.md not found",
                evidence=[]
            )
        
        try:
            content = summary_file.read_text()
            evidence = [f"{summary_file.relative_to(self.workspace_root)}"]
            
            # Check for key sections
            has_overview = bool(re.search(r'##\s*Overview', content, re.IGNORECASE))
            has_test_files = bool(re.search(r'##\s*Test Files', content, re.IGNORECASE))
            has_coverage_table = bool(re.search(r'\|.*Requirement.*\|.*Description.*\|', content))
            has_execution_instructions = bool(re.search(r'##\s*Test Execution', content, re.IGNORECASE))
            has_test_count = bool(re.search(r'\d+\s+tests?', content, re.IGNORECASE))
            
            # Check for agent team coverage
            has_meetmind = bool(re.search(r'MeetMind', content, re.IGNORECASE))
            has_agent_svea = bool(re.search(r'Agent Svea', content, re.IGNORECASE))
            has_felicias = bool(re.search(r'Felicia.*Finance', content, re.IGNORECASE))
            
            # Calculate score
            checks = [
                has_overview,
                has_test_files,
                has_coverage_table,
                has_execution_instructions,
                has_test_count,
                has_meetmind,
                has_agent_svea,
                has_felicias
            ]
            
            score = (sum(checks) / len(checks)) * 100
            passed = sum(checks) >= 6  # At least 6 out of 8 checks should pass
            
            details = (f"Coverage summary: {sum(checks)}/{len(checks)} key sections present "
                      f"(overview, test files, coverage table, execution instructions, agent teams)")
            
            return CheckResult(
                name="Test Coverage Summary",
                passed=passed,
                score=score,
                details=details,
                evidence=evidence
            )
            
        except Exception as e:
            logger.warning(f"Could not read coverage summary: {e}")
            return CheckResult(
                name="Test Coverage Summary",
                passed=False,
                score=0.0,
                details=f"Error reading coverage summary: {e}",
                evidence=[]
            )
