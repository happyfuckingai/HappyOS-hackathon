"""Tests for production audit framework base classes and models."""

import pytest
from datetime import datetime

from backend.core.production_audit import (
    AuditModule,
    AuditResult,
    CheckResult,
    Gap,
    GapSeverity,
    ProductionReadinessReport,
    RoadmapItem,
    ScoringEngine,
)


class MockAuditModule(AuditModule):
    """Mock audit module for testing."""
    
    async def audit(self) -> AuditResult:
        checks = [
            CheckResult(
                name="test_check_1",
                passed=True,
                score=100.0,
                details="Check passed",
                evidence=["file1.py"],
            ),
            CheckResult(
                name="test_check_2",
                passed=False,
                score=0.0,
                details="Check failed",
                evidence=["file2.py"],
            ),
        ]
        
        gaps = [
            Gap(
                category="Test Category",
                severity=GapSeverity.HIGH,
                description="Test gap",
                impact="Test impact",
                recommendation="Fix this",
                estimated_effort="1 day",
                dependencies=[],
            )
        ]
        
        return AuditResult(
            category=self.get_category_name(),
            score=50.0,
            weight=self.get_weight(),
            checks=checks,
            gaps=gaps,
            recommendations=["Test recommendation"],
        )
    
    def get_category_name(self) -> str:
        return "Test Category"
    
    def get_weight(self) -> float:
        return 0.5


def test_gap_severity_enum():
    """Test GapSeverity enum values."""
    assert GapSeverity.CRITICAL.value == "critical"
    assert GapSeverity.HIGH.value == "high"
    assert GapSeverity.MEDIUM.value == "medium"
    assert GapSeverity.LOW.value == "low"


def test_check_result_creation():
    """Test CheckResult dataclass creation."""
    check = CheckResult(
        name="test_check",
        passed=True,
        score=85.5,
        details="Test details",
        evidence=["file1.py", "file2.py"],
    )
    
    assert check.name == "test_check"
    assert check.passed is True
    assert check.score == 85.5
    assert check.details == "Test details"
    assert len(check.evidence) == 2


def test_gap_creation():
    """Test Gap dataclass creation."""
    gap = Gap(
        category="LLM Integration",
        severity=GapSeverity.CRITICAL,
        description="Missing fallback logic",
        impact="System fails when LLM is unavailable",
        recommendation="Implement fallback logic",
        estimated_effort="2 days",
        dependencies=["circuit_breaker"],
    )
    
    assert gap.category == "LLM Integration"
    assert gap.severity == GapSeverity.CRITICAL
    assert gap.description == "Missing fallback logic"
    assert len(gap.dependencies) == 1


def test_audit_result_creation():
    """Test AuditResult dataclass creation."""
    checks = [
        CheckResult("check1", True, 100.0, "Passed", []),
        CheckResult("check2", False, 0.0, "Failed", []),
    ]
    
    gaps = [
        Gap(
            "Test", GapSeverity.HIGH, "Gap", "Impact", "Fix", "1 day", []
        )
    ]
    
    result = AuditResult(
        category="Test Category",
        score=75.0,
        weight=0.3,
        checks=checks,
        gaps=gaps,
        recommendations=["Recommendation 1"],
    )
    
    assert result.category == "Test Category"
    assert result.score == 75.0
    assert result.weight == 0.3
    assert len(result.checks) == 2
    assert len(result.gaps) == 1
    assert len(result.recommendations) == 1


def test_production_readiness_report_properties():
    """Test ProductionReadinessReport properties."""
    report = ProductionReadinessReport(
        overall_score=85.0,
        category_scores={"LLM": 90.0, "Infrastructure": 80.0},
        total_gaps=5,
        critical_gaps=1,
        high_gaps=2,
        medium_gaps=1,
        low_gaps=1,
        gaps_by_category={},
        recommendations=[],
        roadmap=[],
    )
    
    assert report.production_ready is True
    assert report.readiness_status == "Production Ready"
    
    report.overall_score = 70.0
    assert report.production_ready is False
    assert report.readiness_status == "Almost Ready - Minor fixes required"
    
    report.overall_score = 50.0
    assert report.readiness_status == "Significant Work Required"


@pytest.mark.asyncio
async def test_audit_module_base_class():
    """Test AuditModule base class functionality."""
    module = MockAuditModule()
    
    assert module.get_category_name() == "Test Category"
    assert module.get_weight() == 0.5
    
    result = await module.audit()
    assert result.category == "Test Category"
    assert result.score == 50.0
    assert len(result.checks) == 2
    assert len(result.gaps) == 1


def test_scoring_engine_calculate_overall_score():
    """Test ScoringEngine overall score calculation."""
    engine = ScoringEngine()
    
    results = [
        AuditResult("Cat1", 80.0, 0.5, [], [], []),
        AuditResult("Cat2", 60.0, 0.5, [], [], []),
    ]
    
    overall = engine.calculate_overall_score(results)
    assert overall == 70.0  # (80 * 0.5 + 60 * 0.5) / 1.0


def test_scoring_engine_calculate_category_scores():
    """Test ScoringEngine category score extraction."""
    engine = ScoringEngine()
    
    results = [
        AuditResult("LLM Integration", 85.0, 0.3, [], [], []),
        AuditResult("Infrastructure", 75.0, 0.3, [], [], []),
        AuditResult("Testing", 90.0, 0.4, [], [], []),
    ]
    
    scores = engine.calculate_category_scores(results)
    assert scores["LLM Integration"] == 85.0
    assert scores["Infrastructure"] == 75.0
    assert scores["Testing"] == 90.0


def test_scoring_engine_count_gaps_by_severity():
    """Test ScoringEngine gap counting."""
    engine = ScoringEngine()
    
    gaps_by_category = {
        "LLM": [
            Gap("LLM", GapSeverity.CRITICAL, "Gap1", "Impact", "Fix", "1d", []),
            Gap("LLM", GapSeverity.HIGH, "Gap2", "Impact", "Fix", "1d", []),
        ],
        "Infrastructure": [
            Gap("Infra", GapSeverity.MEDIUM, "Gap3", "Impact", "Fix", "1d", []),
            Gap("Infra", GapSeverity.LOW, "Gap4", "Impact", "Fix", "1d", []),
        ],
    }
    
    counts = engine.count_gaps_by_severity(gaps_by_category)
    assert counts["critical"] == 1
    assert counts["high"] == 1
    assert counts["medium"] == 1
    assert counts["low"] == 1
    assert counts["total"] == 4


def test_scoring_engine_generate_roadmap():
    """Test ScoringEngine roadmap generation."""
    engine = ScoringEngine()
    
    gaps_by_category = {
        "LLM": [
            Gap("LLM", GapSeverity.HIGH, "Gap2", "Impact", "Fix2", "2d", []),
            Gap("LLM", GapSeverity.CRITICAL, "Gap1", "Impact", "Fix1", "1d", []),
        ],
        "Infrastructure": [
            Gap("Infra", GapSeverity.LOW, "Gap4", "Impact", "Fix4", "1d", []),
            Gap("Infra", GapSeverity.MEDIUM, "Gap3", "Impact", "Fix3", "1d", []),
        ],
    }
    
    roadmap = engine.generate_roadmap(gaps_by_category)
    
    # Should be sorted by severity: CRITICAL, HIGH, MEDIUM, LOW
    assert len(roadmap) == 4
    assert roadmap[0].title == "Gap1"  # CRITICAL first
    assert roadmap[1].title == "Gap2"  # HIGH second
    assert roadmap[2].title == "Gap3"  # MEDIUM third
    assert roadmap[3].title == "Gap4"  # LOW last


def test_scoring_engine_generate_report():
    """Test ScoringEngine complete report generation."""
    engine = ScoringEngine()
    
    gaps = [
        Gap("LLM", GapSeverity.CRITICAL, "Critical gap", "Impact", "Fix", "1d", []),
        Gap("LLM", GapSeverity.HIGH, "High gap", "Impact", "Fix", "2d", []),
    ]
    
    results = [
        AuditResult(
            "LLM Integration",
            80.0,
            0.5,
            [],
            gaps,
            ["Recommendation 1"],
        ),
        AuditResult(
            "Infrastructure",
            90.0,
            0.5,
            [],
            [],
            ["Recommendation 2"],
        ),
    ]
    
    report = engine.generate_report(results)
    
    assert report.overall_score == 85.0
    assert len(report.category_scores) == 2
    assert report.total_gaps == 2
    assert report.critical_gaps == 1
    assert report.high_gaps == 1
    assert len(report.recommendations) == 2
    assert len(report.roadmap) == 2
    assert report.production_ready is True
