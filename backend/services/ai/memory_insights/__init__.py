"""
Memory Insights Service Package

Production memory insights with AI-powered analysis, pattern recognition,
and recommendation engine.
"""

from backend.services.ai.memory_insights.service import MemoryInsightsService, get_memory_insights_service
from backend.services.ai.memory_insights.models import Pattern, Trend, Recommendation, InsightReport, PatternType, InsightType
from backend.services.ai.memory_insights.pattern_analyzer import PatternAnalyzer
from backend.services.ai.memory_insights.recommendation_engine import RecommendationEngine
from backend.services.ai.memory_insights.cache_manager import CacheManager

__all__ = [
    "MemoryInsightsService",
    "get_memory_insights_service", 
    "Pattern",
    "Trend",
    "Recommendation",
    "InsightReport",
    "PatternType",
    "InsightType",
    "PatternAnalyzer",
    "RecommendationEngine",
    "CacheManager"
]