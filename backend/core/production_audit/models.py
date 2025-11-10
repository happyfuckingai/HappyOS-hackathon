"""Data models for production readiness audit."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List


class GapSeverity(Enum):
    """Severity levels for identified gaps."""
    
    CRITICAL = "critical"  # Must be fixed before production
    HIGH = "high"          # Should be fixed before production
    MEDIUM = "medium"      # Can be fixed after launch
    LOW = "low"            # Nice-to-have improvements


@dataclass
class CheckResult:
    """Result of a single audit check."""
    
    name: str
    passed: bool
    score: float  # 0-100
    details: str
    evidence: List[str] = field(default_factory=list)  # File paths, test results, etc.


@dataclass
class Gap:
    """Identified gap in production readiness."""
    
    category: str
    severity: GapSeverity
    description: str
    impact: str
    recommendation: str
    estimated_effort: str  # "1 day", "1 week", etc.
    dependencies: List[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Result of an audit module execution."""
    
    category: str
    score: float  # 0-100
    weight: float  # 0.0-1.0
    checks: List[CheckResult]
    gaps: List[Gap]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RoadmapItem:
    """Action item in the production readiness roadmap."""
    
    priority: int  # 1 = highest
    title: str
    description: str
    estimated_effort: str
    dependencies: List[str] = field(default_factory=list)
    category: str = ""


@dataclass
class ProductionReadinessReport:
    """Complete production readiness audit report."""
    
    overall_score: float  # 0-100
    category_scores: Dict[str, float]
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    gaps_by_category: Dict[str, List[Gap]]
    recommendations: List[str]
    roadmap: List[RoadmapItem]
    generated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def production_ready(self) -> bool:
        """Determine if system is production ready (score > 80)."""
        return self.overall_score > 80
    
    @property
    def readiness_status(self) -> str:
        """Get human-readable readiness status."""
        if self.overall_score > 80:
            return "Production Ready"
        elif self.overall_score >= 60:
            return "Almost Ready - Minor fixes required"
        else:
            return "Significant Work Required"
