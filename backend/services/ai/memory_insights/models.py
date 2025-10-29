"""
Memory Insights Data Models

Data structures for patterns, trends, recommendations, and insight reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional


class InsightType(str, Enum):
    """Types of memory insights"""
    PATTERN = "pattern"
    TREND = "trend"
    RECOMMENDATION = "recommendation"
    SUMMARY = "summary"
    RELATIONSHIP = "relationship"


class PatternType(str, Enum):
    """Types of patterns that can be detected"""
    RECURRING_TOPIC = "recurring_topic"
    MEETING_FREQUENCY = "meeting_frequency"
    PARTICIPANT_BEHAVIOR = "participant_behavior"
    DECISION_PATTERN = "decision_pattern"
    ACTION_COMPLETION = "action_completion"


@dataclass
class Pattern:
    """Detected pattern in meeting data"""
    pattern_id: str
    pattern_type: PatternType
    description: str
    confidence: float
    frequency: int
    first_occurrence: datetime
    last_occurrence: datetime
    related_meetings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trend:
    """Detected trend in meeting data"""
    trend_id: str
    description: str
    direction: str  # "increasing", "decreasing", "stable"
    confidence: float
    time_period: str
    data_points: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """AI-generated recommendation"""
    recommendation_id: str
    title: str
    description: str
    priority: str  # "low", "medium", "high"
    category: str
    confidence: float
    actionable_steps: List[str]
    related_patterns: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightReport:
    """Complete insight report for a user or meeting"""
    report_id: str
    user_id: str
    meeting_id: Optional[str]
    generated_at: datetime
    patterns: List[Pattern]
    trends: List[Trend]
    recommendations: List[Recommendation]
    summary: str
    confidence_scores: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)