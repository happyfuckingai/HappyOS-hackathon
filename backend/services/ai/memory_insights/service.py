"""
Memory Insights Service

Main service that orchestrates pattern analysis, trend detection, and recommendation generation
using real AI-powered analysis with embeddings-based pattern recognition.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib

from backend.services.ai.memory_insights.models import InsightReport, Pattern, Trend, Recommendation
from backend.services.ai.memory_insights.pattern_analyzer import PatternAnalyzer
from backend.services.ai.memory_insights.recommendation_engine import RecommendationEngine
from backend.services.ai.memory_insights.cache_manager import CacheManager
from backend.services.ai.client_manager import AIClientManager
from backend.services.storage.vector_service import get_vector_service
from backend.modules.database.connection import get_db
from backend.modules.models.base import Meeting

logger = logging.getLogger(__name__)


class MemoryInsightsService:
    """
    Main memory insights service that coordinates all components
    """
    
    def __init__(self, ai_client_manager: Optional[AIClientManager] = None):
        """
        Initialize memory insights service
        
        Args:
            ai_client_manager: AI client manager for LLM operations
        """
        self.ai_client = ai_client_manager
        self.vector_service = None
        self.pattern_analyzer = None
        self.recommendation_engine = None
        self.cache_manager = CacheManager(cache_ttl=3600)  # 1 hour cache
        self.is_initialized = False
        
        logger.info("MemoryInsightsService initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize the memory insights service and all components
        
        Returns:
            bool: True if initialization successful
        """
        if self.is_initialized:
            return True
        
        try:
            # Initialize cache manager
            await self.cache_manager.initialize()
            
            # Initialize vector service
            self.vector_service = await get_vector_service()
            
            # Initialize AI client if not provided
            if not self.ai_client:
                from backend.services.ai.client_manager import get_ai_client_manager
                self.ai_client = get_ai_client_manager()
            
            # Initialize pattern analyzer
            self.pattern_analyzer = PatternAnalyzer(
                ai_client=self.ai_client,
                vector_service=self.vector_service
            )
            
            # Initialize recommendation engine
            self.recommendation_engine = RecommendationEngine(
                ai_client=self.ai_client
            )
            
            self.is_initialized = True
            logger.info("MemoryInsightsService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MemoryInsightsService: {e}")
            return False
    
    async def generate_insights(self, user_id: str, meeting_id: Optional[str] = None) -> InsightReport:
        """
        Generate comprehensive insights using real AI-powered analysis
        
        Args:
            user_id: User identifier
            meeting_id: Optional specific meeting ID
            
        Returns:
            Complete insight report with patterns, trends, and recommendations
        """
        try:
            # Check cache first
            cache_key = f"insights:{user_id}:{meeting_id or 'all'}"
            cached_report = await self.cache_manager.get(cache_key)
            if cached_report:
                logger.debug(f"Cache hit for insights: {cache_key}")
                return self._deserialize_insight_report(cached_report)
            
            # Get meeting data for analysis
            meeting_data = await self._get_meeting_data(user_id, [meeting_id] if meeting_id else None)
            
            if not meeting_data:
                logger.info(f"No meeting data found for user {user_id}")
                return self._create_empty_report(user_id, meeting_id)
            
            # Analyze patterns using real embeddings and AI
            patterns = await self.pattern_analyzer.analyze_patterns(meeting_data)
            
            # Generate trends from patterns
            trends = await self._generate_trends(patterns)
            
            # Generate AI-powered recommendations
            recommendations = await self.recommendation_engine.generate_recommendations(
                user_id, patterns, trends
            )
            
            # Generate AI-powered summary
            summary = await self._generate_insight_summary(user_id, patterns, trends, recommendations)
            
            # Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(patterns, trends, recommendations)
            
            # Create insight report
            report = InsightReport(
                report_id=hashlib.sha256(f"{user_id}_{meeting_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:16],
                user_id=user_id,
                meeting_id=meeting_id,
                generated_at=datetime.now(),
                patterns=patterns,
                trends=trends,
                recommendations=recommendations,
                summary=summary,
                confidence_scores=confidence_scores,
                metadata={
                    "analysis_version": "1.0",
                    "ai_provider": "production",
                    "pattern_count": len(patterns),
                    "trend_count": len(trends),
                    "recommendation_count": len(recommendations),
                    "meeting_data_count": len(meeting_data)
                }
            )
            
            # Cache the report
            await self.cache_manager.set(cache_key, self._serialize_insight_report(report))
            
            logger.info(f"Generated insights for user {user_id}: {len(patterns)} patterns, {len(trends)} trends, {len(recommendations)} recommendations")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate insights for user {user_id}: {e}")
            return self._create_error_report(user_id, meeting_id, str(e))
    
    async def analyze_meeting_patterns(self, user_id: str, 
                                     meeting_ids: Optional[List[str]] = None,
                                     time_window_days: int = 30) -> List[Pattern]:
        """
        Analyze patterns in user's meeting data using real embeddings-based analysis
        
        Args:
            user_id: User identifier
            meeting_ids: Optional list of specific meeting IDs to analyze
            time_window_days: Time window for pattern analysis
            
        Returns:
            List of detected patterns
        """
        try:
            # Get meeting data for analysis
            meeting_data = await self._get_meeting_data(user_id, meeting_ids, time_window_days)
            
            if not meeting_data:
                logger.info(f"No meeting data found for user {user_id}")
                return []
            
            # Use pattern analyzer to detect patterns
            patterns = await self.pattern_analyzer.analyze_patterns(meeting_data)
            
            logger.info(f"Analyzed patterns for user {user_id}: {len(patterns)} patterns detected")
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to analyze meeting patterns for user {user_id}: {e}")
            return []
    
    async def build_context(self, meeting_id: str) -> Dict[str, Any]:
        """
        Build comprehensive context for a meeting using real embeddings and AI analysis
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Meeting context with related insights
        """
        try:
            # Get meeting data
            db = next(get_db())
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            
            if not meeting:
                return {"error": "Meeting not found"}
            
            # Get related content from vector search
            related_content = await self.vector_service.search_similar(
                query=meeting.name or "meeting context",
                meeting_id=meeting_id,
                limit=20
            )
            
            # Get user patterns for this meeting
            patterns = await self.analyze_meeting_patterns(
                user_id=meeting.owner_id,
                meeting_ids=[meeting_id]
            )
            
            # Build comprehensive context
            context = {
                "meeting_id": meeting_id,
                "meeting_name": meeting.name,
                "created_at": meeting.created_at.isoformat(),
                "status": meeting.status,
                "participants": [p.id for p in meeting.participants],
                "related_content": related_content,
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "type": p.pattern_type.value,
                        "description": p.description,
                        "confidence": p.confidence
                    }
                    for p in patterns
                ],
                "context_generated_at": datetime.now().isoformat(),
                "context_source": "real_ai_analysis"
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to build context for meeting {meeting_id}: {e}")
            return {"error": str(e)}
    
    async def get_recommendations(self, user_id: str, category: Optional[str] = None,
                                priority: Optional[str] = None) -> List[Recommendation]:
        """
        Get AI-powered recommendations for a user
        
        Args:
            user_id: User identifier
            category: Optional category filter
            priority: Optional priority filter
            
        Returns:
            List of recommendations
        """
        try:
            # Generate fresh insights to get recommendations
            insights = await self.generate_insights(user_id)
            
            recommendations = insights.recommendations
            
            # Apply filters
            if category:
                recommendations = [r for r in recommendations if r.category == category]
            
            if priority:
                recommendations = [r for r in recommendations if r.priority == priority]
            
            # Sort by confidence and priority
            priority_order = {"high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda r: (priority_order.get(r.priority, 0), r.confidence),
                reverse=True
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get recommendations for user {user_id}: {e}")
            return []
    
    async def _get_meeting_data(self, user_id: str, meeting_ids: Optional[List[str]], 
                              time_window_days: int = 30) -> List[Dict[str, Any]]:
        """Get meeting data for analysis with vector embeddings"""
        try:
            from datetime import timedelta
            
            # Get database session
            db = next(get_db())
            
            # Build query
            query = db.query(Meeting).filter(Meeting.owner_id == user_id)
            
            if meeting_ids:
                query = query.filter(Meeting.id.in_(meeting_ids))
            
            if time_window_days > 0:
                cutoff_date = datetime.now() - timedelta(days=time_window_days)
                query = query.filter(Meeting.created_at >= cutoff_date)
            
            meetings = query.all()
            
            # Convert to analysis format with vector embeddings
            meeting_data = []
            for meeting in meetings:
                # Get vector embeddings for meeting content
                similar_content = await self.vector_service.search_similar(
                    query=meeting.name or "meeting",
                    meeting_id=meeting.id,
                    limit=50
                )
                
                meeting_data.append({
                    "meeting_id": meeting.id,
                    "name": meeting.name,
                    "created_at": meeting.created_at,
                    "status": meeting.status,
                    "participants": [p.id for p in meeting.participants],
                    "content_embeddings": similar_content,
                    "metadata": meeting.mem0_context or {}
                })
            
            return meeting_data
            
        except Exception as e:
            logger.error(f"Failed to get meeting data: {e}")
            return []
    
    async def _generate_trends(self, patterns: List[Pattern]) -> List[Trend]:
        """Generate trends from detected patterns"""
        trends = []
        
        try:
            if not patterns:
                return trends
            
            # Group patterns by type
            pattern_types = {}
            for pattern in patterns:
                pattern_type = pattern.pattern_type.value
                if pattern_type not in pattern_types:
                    pattern_types[pattern_type] = []
                pattern_types[pattern_type].append(pattern)
            
            # Generate trends for each pattern type
            for pattern_type, type_patterns in pattern_types.items():
                if len(type_patterns) > 1:
                    # Sort by first occurrence
                    sorted_patterns = sorted(type_patterns, key=lambda x: x.first_occurrence)
                    
                    # Determine trend direction based on recent activity
                    recent_patterns = [p for p in sorted_patterns if 
                                     (datetime.now() - p.last_occurrence).days <= 30]
                    
                    if len(recent_patterns) > len(sorted_patterns) * 0.6:
                        direction = "increasing"
                    elif len(recent_patterns) < len(sorted_patterns) * 0.3:
                        direction = "decreasing"
                    else:
                        direction = "stable"
                    
                    trend = Trend(
                        trend_id=f"trend_{pattern_type}",
                        description=f"{pattern_type.replace('_', ' ').title()} trend",
                        direction=direction,
                        confidence=0.7,
                        time_period="30_days",
                        data_points=[
                            {
                                "date": p.last_occurrence.isoformat(),
                                "value": p.frequency,
                                "pattern_id": p.pattern_id
                            }
                            for p in sorted_patterns
                        ],
                        metadata={
                            "pattern_type": pattern_type,
                            "total_patterns": len(type_patterns),
                            "recent_patterns": len(recent_patterns)
                        }
                    )
                    trends.append(trend)
            
        except Exception as e:
            logger.error(f"Failed to generate trends: {e}")
        
        return trends
    
    async def _generate_insight_summary(self, user_id: str, patterns: List[Pattern], 
                                       trends: List[Trend], recommendations: List[Recommendation]) -> str:
        """Generate AI-powered insight summary"""
        try:
            if not self.ai_client:
                return self._generate_fallback_summary(patterns, trends, recommendations)
            
            # Create summary context
            summary_context = f"""
            User has {len(patterns)} patterns detected, {len(trends)} trends identified, and {len(recommendations)} recommendations generated.
            
            Key patterns: {', '.join([p.description for p in patterns[:3]])}
            Main trends: {', '.join([f"{t.description} ({t.direction})" for t in trends[:2]])}
            Top recommendations: {', '.join([r.title for r in recommendations[:3]])}
            """
            
            # Generate summary using AI
            result = await self.ai_client.summarize_meeting(
                content=f"Create a brief, actionable summary of these meeting insights: {summary_context}",
                meeting_id="insight_summary",
                user_id=user_id,
                style="brief"
            )
            
            return result.get("summary", self._generate_fallback_summary(patterns, trends, recommendations))
            
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            return self._generate_fallback_summary(patterns, trends, recommendations)
    
    def _generate_fallback_summary(self, patterns: List[Pattern], trends: List[Trend], 
                                 recommendations: List[Recommendation]) -> str:
        """Generate fallback summary without AI"""
        summary_parts = []
        
        if patterns:
            summary_parts.append(f"Detected {len(patterns)} patterns in your meetings")
            if patterns[0].pattern_type.value == "recurring_topic":
                summary_parts.append("including recurring discussion topics")
        
        if trends:
            increasing_trends = [t for t in trends if t.direction == "increasing"]
            if increasing_trends:
                summary_parts.append(f"with {len(increasing_trends)} increasing trends")
        
        if recommendations:
            high_priority = [r for r in recommendations if r.priority == "high"]
            summary_parts.append(f"Generated {len(recommendations)} recommendations")
            if high_priority:
                summary_parts.append(f"including {len(high_priority)} high-priority actions")
        
        if not summary_parts:
            return "No significant patterns or trends detected in recent meetings."
        
        return ". ".join(summary_parts) + "."
    
    def _calculate_confidence_scores(self, patterns: List[Pattern], trends: List[Trend], 
                                   recommendations: List[Recommendation]) -> Dict[str, float]:
        """Calculate overall confidence scores"""
        import numpy as np
        
        scores = {}
        
        if patterns:
            scores["pattern_analysis"] = np.mean([p.confidence for p in patterns])
        else:
            scores["pattern_analysis"] = 0.0
        
        if trends:
            scores["trend_analysis"] = np.mean([t.confidence for t in trends])
        else:
            scores["trend_analysis"] = 0.0
        
        if recommendations:
            scores["recommendations"] = np.mean([r.confidence for r in recommendations])
        else:
            scores["recommendations"] = 0.0
        
        # Overall confidence
        all_scores = [score for score in scores.values() if score > 0]
        scores["overall"] = np.mean(all_scores) if all_scores else 0.0
        
        return scores
    
    def _serialize_insight_report(self, report: InsightReport) -> Dict[str, Any]:
        """Serialize insight report for caching"""
        return {
            "report_id": report.report_id,
            "user_id": report.user_id,
            "meeting_id": report.meeting_id,
            "generated_at": report.generated_at.isoformat(),
            "summary": report.summary,
            "pattern_count": len(report.patterns),
            "trend_count": len(report.trends),
            "recommendation_count": len(report.recommendations),
            "confidence_scores": report.confidence_scores,
            "metadata": report.metadata
        }
    
    def _deserialize_insight_report(self, data: Dict[str, Any]) -> InsightReport:
        """Deserialize insight report from cache (simplified)"""
        # In a full implementation, this would properly reconstruct the full report
        # For now, return a simplified version
        return InsightReport(
            report_id=data["report_id"],
            user_id=data["user_id"],
            meeting_id=data.get("meeting_id"),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            patterns=[],  # Would be reconstructed in full implementation
            trends=[],    # Would be reconstructed in full implementation
            recommendations=[],  # Would be reconstructed in full implementation
            summary=data["summary"],
            confidence_scores=data["confidence_scores"],
            metadata=data["metadata"]
        )
    
    def _create_empty_report(self, user_id: str, meeting_id: Optional[str]) -> InsightReport:
        """Create empty insight report when no data is available"""
        return InsightReport(
            report_id="empty",
            user_id=user_id,
            meeting_id=meeting_id,
            generated_at=datetime.now(),
            patterns=[],
            trends=[],
            recommendations=[],
            summary="No meeting data available for analysis.",
            confidence_scores={},
            metadata={"status": "no_data"}
        )
    
    def _create_error_report(self, user_id: str, meeting_id: Optional[str], error: str) -> InsightReport:
        """Create error insight report"""
        return InsightReport(
            report_id="error",
            user_id=user_id,
            meeting_id=meeting_id,
            generated_at=datetime.now(),
            patterns=[],
            trends=[],
            recommendations=[],
            summary="Unable to generate insights at this time.",
            confidence_scores={},
            metadata={"error": error}
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on memory insights service"""
        health = {
            "service_initialized": self.is_initialized,
            "ai_client_available": self.ai_client is not None,
            "vector_service_available": self.vector_service is not None,
            "pattern_analyzer_available": self.pattern_analyzer is not None,
            "recommendation_engine_available": self.recommendation_engine is not None,
            "cache_stats": self.cache_manager.get_cache_stats()
        }
        
        try:
            # Test AI client
            if self.ai_client:
                ai_health = await self.ai_client.health_check()
                health["ai_client_status"] = ai_health.get("status", "unknown")
            
            # Test vector service
            if self.vector_service:
                vector_health = await self.vector_service.health_check()
                health["vector_service_status"] = "healthy" if any(vector_health.values()) else "degraded"
            
        except Exception as e:
            health["health_check_error"] = str(e)
        
        return health


# Global instance
_memory_insights_service: Optional[MemoryInsightsService] = None


async def get_memory_insights_service() -> MemoryInsightsService:
    """Get or create global memory insights service instance"""
    global _memory_insights_service
    if _memory_insights_service is None:
        _memory_insights_service = MemoryInsightsService()
        await _memory_insights_service.initialize()
    return _memory_insights_service