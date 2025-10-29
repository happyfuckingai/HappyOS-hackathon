"""
Recommendation Engine Module

Generates AI-powered recommendations based on patterns and trends.
"""

import logging
from typing import List, Optional

from backend.services.ai.memory_insights.models import Pattern, Trend, Recommendation, PatternType
from backend.services.ai.client_manager import AIClientManager

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Generates recommendations based on patterns and trends"""
    
    def __init__(self, ai_client: Optional[AIClientManager] = None):
        self.ai_client = ai_client
    
    async def generate_recommendations(self, user_id: str, patterns: List[Pattern], 
                                     trends: List[Trend]) -> List[Recommendation]:
        """
        Generate AI-powered recommendations
        
        Args:
            user_id: User identifier
            patterns: Detected patterns
            trends: Detected trends
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        try:
            if not patterns:
                return recommendations
            
            # Generate AI-powered recommendations
            if self.ai_client:
                ai_recommendations = await self._generate_ai_recommendations(user_id, patterns, trends)
                recommendations.extend(ai_recommendations)
            
            # Generate pattern-specific recommendations
            pattern_recommendations = self._generate_pattern_recommendations(patterns)
            recommendations.extend(pattern_recommendations)
            
            # Sort by priority and confidence
            priority_order = {"high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda r: (priority_order.get(r.priority, 0), r.confidence),
                reverse=True
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return []
    
    async def _generate_ai_recommendations(self, user_id: str, patterns: List[Pattern], 
                                         trends: List[Trend]) -> List[Recommendation]:
        """Generate recommendations using AI"""
        recommendations = []
        
        try:
            # Create context for AI recommendation generation
            context = self._create_recommendation_context(patterns, trends)
            
            # Use AI to generate recommendations
            result = await self.ai_client.extract_action_items(
                content=f"Based on these meeting patterns and trends, provide actionable recommendations for improving meeting effectiveness: {context}",
                meeting_id="recommendation_analysis",
                user_id=user_id
            )
            
            # Convert AI actions to recommendations
            for i, action in enumerate(result.get("actions", [])):
                recommendation = Recommendation(
                    recommendation_id=f"ai_rec_{i}",
                    title=action.get("action", "Improve meeting effectiveness"),
                    description=action.get("action", ""),
                    priority=action.get("priority", "medium"),
                    category="meeting_optimization",
                    confidence=action.get("confidence", 0.7),
                    actionable_steps=[action.get("action", "")],
                    related_patterns=[p.pattern_id for p in patterns[:3]],
                    metadata={
                        "ai_generated": True,
                        "assignee": action.get("assignee", "Meeting organizer"),
                        "deadline": action.get("deadline", "Next meeting")
                    }
                )
                recommendations.append(recommendation)
            
        except Exception as e:
            logger.error(f"Failed to generate AI recommendations: {e}")
        
        return recommendations
    
    def _create_recommendation_context(self, patterns: List[Pattern], trends: List[Trend]) -> str:
        """Create context string for AI recommendation generation"""
        context_parts = []
        
        # Add pattern information
        if patterns:
            context_parts.append("Detected Patterns:")
            for pattern in patterns[:5]:  # Limit to top 5 patterns
                context_parts.append(f"- {pattern.description} (confidence: {pattern.confidence:.2f})")
        
        # Add trend information
        if trends:
            context_parts.append("\nTrends:")
            for trend in trends[:3]:  # Limit to top 3 trends
                context_parts.append(f"- {trend.description}: {trend.direction}")
        
        return "\n".join(context_parts)
    
    def _generate_pattern_recommendations(self, patterns: List[Pattern]) -> List[Recommendation]:
        """Generate specific recommendations based on patterns"""
        recommendations = []
        
        try:
            for pattern in patterns:
                if pattern.pattern_type == PatternType.RECURRING_TOPIC:
                    rec = Recommendation(
                        recommendation_id=f"pattern_rec_{pattern.pattern_id}",
                        title="Optimize recurring topic discussions",
                        description=f"Consider creating a dedicated workflow for '{pattern.description}' since it appears frequently",
                        priority="medium",
                        category="topic_optimization",
                        confidence=pattern.confidence,
                        actionable_steps=[
                            "Create a standard agenda template for this topic",
                            "Assign a dedicated facilitator",
                            "Set up pre-meeting preparation guidelines"
                        ],
                        related_patterns=[pattern.pattern_id]
                    )
                    recommendations.append(rec)
                
                elif pattern.pattern_type == PatternType.MEETING_FREQUENCY:
                    rec = Recommendation(
                        recommendation_id=f"pattern_rec_{pattern.pattern_id}",
                        title="Maintain meeting rhythm",
                        description="Your regular meeting schedule is working well - consider maintaining this cadence",
                        priority="low",
                        category="scheduling",
                        confidence=pattern.confidence,
                        actionable_steps=[
                            "Continue current meeting frequency",
                            "Set up recurring calendar invites",
                            "Monitor for schedule conflicts"
                        ],
                        related_patterns=[pattern.pattern_id]
                    )
                    recommendations.append(rec)
                
                elif pattern.pattern_type == PatternType.PARTICIPANT_BEHAVIOR:
                    rec = Recommendation(
                        recommendation_id=f"pattern_rec_{pattern.pattern_id}",
                        title="Leverage core team consistency",
                        description="You have a consistent core team - consider leveraging this for better meeting outcomes",
                        priority="medium",
                        category="team_optimization",
                        confidence=pattern.confidence,
                        actionable_steps=[
                            "Assign rotating meeting roles to core participants",
                            "Create team-specific meeting templates",
                            "Consider advanced topics for this stable group"
                        ],
                        related_patterns=[pattern.pattern_id]
                    )
                    recommendations.append(rec)
                
                elif pattern.pattern_type == PatternType.DECISION_PATTERN:
                    rec = Recommendation(
                        recommendation_id=f"pattern_rec_{pattern.pattern_id}",
                        title="Formalize decision-making process",
                        description="Your team shows consistent decision-making patterns - consider formalizing the process",
                        priority="high",
                        category="process_improvement",
                        confidence=pattern.confidence,
                        actionable_steps=[
                            "Document the decision-making framework",
                            "Create decision templates",
                            "Set up decision tracking system"
                        ],
                        related_patterns=[pattern.pattern_id]
                    )
                    recommendations.append(rec)
        
        except Exception as e:
            logger.error(f"Failed to generate pattern recommendations: {e}")
        
        return recommendations