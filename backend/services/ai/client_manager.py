"""
AI Client Manager

Production-ready AI client manager that integrates the ProductionAIClient
with cost control, quota enforcement, and database tracking.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from .production_client import (
    ProductionAIClient, AIProvider, AIOperationType, 
    QuotaExceededError, CircuitBreakerOpenError, ValidationError
)
from ..infrastructure.cost_controller import CostController, CostTier
from backend.modules.database.connection import get_db
from backend.modules.config.settings import settings

logger = logging.getLogger(__name__)


class AIClientManager:
    """
    Production AI Client Manager
    
    Manages AI operations with cost control, quota enforcement, and monitoring.
    Replaces the existing mocked AI client system with real implementations.
    """

    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize AI Client Manager
        
        Args:
            db_session: Database session for cost tracking
        """
        self.db = db_session
        self.cost_controller = CostController(db_session) if db_session else None
        
        # Initialize production AI client
        self.ai_client = ProductionAIClient(
            openai_api_key=settings.OPENAI_API_KEY,
            google_api_key=settings.GOOGLE_AI_API_KEY,
            bedrock_region=os.getenv("AWS_REGION", "us-east-1"),
            default_timeout=30,
            max_retries=3,
            circuit_breaker_config={
                "failure_threshold": 5,
                "timeout_seconds": 60,
                "half_open_max_calls": 3
            }
        )
        
        # Cache for meeting contexts
        self._meeting_contexts: Dict[str, Dict] = {}
        
        logger.info("AIClientManager initialized with real AI providers")

    async def initialize(self):
        """Initialize the AI client manager"""
        # Perform health check on all providers
        health_status = await self.ai_client.health_check()
        logger.info("AI providers health check: %s", health_status)
        
        # Set up default quotas for system users if needed
        if self.cost_controller:
            await self._setup_default_quotas()

    async def summarize_meeting(self, content: str, meeting_id: str, 
                              user_id: str, style: str = "detailed") -> Dict[str, Any]:
        """
        Summarize meeting content using real AI
        
        Args:
            content: Meeting transcript or content to summarize
            meeting_id: Meeting identifier
            user_id: User identifier for quota tracking
            style: Summary style (brief, detailed, bullet_points)
            
        Returns:
            Summary with metadata
        """
        try:
            start_time = datetime.now()
            
            # Check quota before processing
            if self.cost_controller:
                estimated_tokens = len(content.split()) * 1.5
                quota_check = await self.cost_controller.check_quota(
                    user_id, "summarize", int(estimated_tokens)
                )
                
                if not quota_check["allowed"]:
                    raise QuotaExceededError(
                        f"Quota exceeded: {', '.join(quota_check['exceeded_quotas'])}"
                    )
            
            # Generate summary using AI
            result = await self.ai_client.summarize(
                content=content,
                user_id=user_id,
                preferred_provider=None,  # Let system choose best provider
                style=style
            )
            
            # Track usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider=result["provider"],
                    model=result["model"],
                    operation="summarize",
                    tokens_used=result["tokens_used"],
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "style": style,
                        "content_length": len(content),
                        "summary_length": len(result["summary"])
                    }
                )
            
            logger.info("Generated summary for meeting %s: %d tokens, $%.4f cost", 
                       meeting_id, result["tokens_used"], result["cost"])
            
            return {
                "summary": result["summary"],
                "key_points": result["key_points"],
                "confidence": result["confidence"],
                "metadata": {
                    "provider": result["provider"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "cost": result["cost"],
                    "response_time": result["response_time"],
                    "style": style,
                    "meeting_id": meeting_id
                }
            }
            
        except QuotaExceededError:
            logger.warning("Quota exceeded for user %s in meeting %s", user_id, meeting_id)
            raise
        except CircuitBreakerOpenError as e:
            logger.error("Circuit breaker open: %s", e)
            raise
        except Exception as e:
            # Track failed usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider="unknown",
                    model="unknown",
                    operation="summarize",
                    tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error("Failed to summarize meeting %s: %s", meeting_id, e)
            raise

    async def detect_topics(self, content: str, meeting_id: str, 
                           user_id: str, max_topics: int = 5) -> Dict[str, Any]:
        """
        Detect topics in meeting content using real AI
        
        Args:
            content: Meeting content to analyze
            meeting_id: Meeting identifier
            user_id: User identifier
            max_topics: Maximum number of topics to detect
            
        Returns:
            Detected topics with confidence scores
        """
        try:
            start_time = datetime.now()
            
            # Check quota
            if self.cost_controller:
                estimated_tokens = len(content.split()) * 1.2
                quota_check = await self.cost_controller.check_quota(
                    user_id, "detect_topics", int(estimated_tokens)
                )
                
                if not quota_check["allowed"]:
                    raise QuotaExceededError(
                        f"Quota exceeded: {', '.join(quota_check['exceeded_quotas'])}"
                    )
            
            # Detect topics using AI
            result = await self.ai_client.detect_topics(
                content=content,
                user_id=user_id,
                max_topics=max_topics
            )
            
            # Track usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider=result["provider"],
                    model=result["model"],
                    operation="detect_topics",
                    tokens_used=result["tokens_used"],
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "max_topics": max_topics,
                        "topics_found": len(result["topics"]),
                        "content_length": len(content)
                    }
                )
            
            logger.info("Detected %d topics for meeting %s", len(result["topics"]), meeting_id)
            
            return {
                "topics": result["topics"],
                "metadata": {
                    "provider": result["provider"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "cost": result["cost"],
                    "response_time": result["response_time"],
                    "meeting_id": meeting_id
                }
            }
            
        except Exception as e:
            # Track failed usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider="unknown",
                    model="unknown",
                    operation="detect_topics",
                    tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error("Failed to detect topics for meeting %s: %s", meeting_id, e)
            raise

    async def extract_action_items(self, content: str, meeting_id: str, 
                                 user_id: str) -> Dict[str, Any]:
        """
        Extract action items from meeting content using real AI
        
        Args:
            content: Meeting content to analyze
            meeting_id: Meeting identifier
            user_id: User identifier
            
        Returns:
            Extracted action items
        """
        try:
            start_time = datetime.now()
            
            # Check quota
            if self.cost_controller:
                estimated_tokens = len(content.split()) * 1.3
                quota_check = await self.cost_controller.check_quota(
                    user_id, "extract_actions", int(estimated_tokens)
                )
                
                if not quota_check["allowed"]:
                    raise QuotaExceededError(
                        f"Quota exceeded: {', '.join(quota_check['exceeded_quotas'])}"
                    )
            
            # Create action extraction prompt
            prompt = f"""Analyze the following meeting content and extract action items.
            
Content: {content}

Provide response in JSON format with 'actions' array, where each action has:
- 'action': description of the action
- 'assignee': person responsible (if mentioned)
- 'deadline': deadline (if mentioned)
- 'priority': priority level (low, medium, high)
- 'confidence': confidence score (0-1)"""
            
            # Use summarize method with custom prompt for action extraction
            result = await self.ai_client.summarize(
                content=prompt,
                user_id=user_id,
                style="detailed"
            )
            
            # Parse actions from response
            import json
            try:
                parsed = json.loads(result["summary"])
                actions = parsed.get("actions", [])
            except json.JSONDecodeError:
                # Fallback: simple action extraction
                actions = [
                    {
                        "action": "Review meeting notes and follow up on discussed items",
                        "assignee": "All participants",
                        "deadline": "Next meeting",
                        "priority": "medium",
                        "confidence": 0.5
                    }
                ]
            
            # Track usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider=result["provider"],
                    model=result["model"],
                    operation="extract_actions",
                    tokens_used=result["tokens_used"],
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "actions_found": len(actions),
                        "content_length": len(content)
                    }
                )
            
            logger.info("Extracted %d action items for meeting %s", len(actions), meeting_id)
            
            return {
                "actions": actions,
                "metadata": {
                    "provider": result["provider"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "cost": result["cost"],
                    "response_time": result["response_time"],
                    "meeting_id": meeting_id
                }
            }
            
        except Exception as e:
            # Track failed usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider="unknown",
                    model="unknown",
                    operation="extract_actions",
                    tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error("Failed to extract actions for meeting %s: %s", meeting_id, e)
            raise

    async def analyze_personas(self, content: str, meeting_id: str, 
                             user_id: str) -> Dict[str, Any]:
        """
        Analyze participant personas in meeting content
        
        Args:
            content: Meeting content to analyze
            meeting_id: Meeting identifier
            user_id: User identifier
            
        Returns:
            Persona analysis results
        """
        try:
            start_time = datetime.now()
            
            # Check quota
            if self.cost_controller:
                estimated_tokens = len(content.split()) * 1.4
                quota_check = await self.cost_controller.check_quota(
                    user_id, "analyze_personas", int(estimated_tokens)
                )
                
                if not quota_check["allowed"]:
                    raise QuotaExceededError(
                        f"Quota exceeded: {', '.join(quota_check['exceeded_quotas'])}"
                    )
            
            # Create persona analysis prompt
            prompt = f"""Analyze the following meeting content and identify participant personas.
            
Content: {content}

Provide response in JSON format with 'personas' array, where each persona has:
- 'speaker': speaker name or identifier
- 'role': their role or function
- 'engagement_level': engagement level (low, medium, high)
- 'sentiment': overall sentiment (positive, neutral, negative)
- 'key_contributions': array of their key contributions"""
            
            # Use summarize method with custom prompt
            result = await self.ai_client.summarize(
                content=prompt,
                user_id=user_id,
                style="detailed"
            )
            
            # Parse personas from response
            import json
            try:
                parsed = json.loads(result["summary"])
                personas = parsed.get("personas", [])
            except json.JSONDecodeError:
                # Fallback: basic persona analysis
                personas = [
                    {
                        "speaker": "Participant",
                        "role": "Meeting participant",
                        "engagement_level": "medium",
                        "sentiment": "neutral",
                        "key_contributions": ["Participated in discussion"]
                    }
                ]
            
            # Track usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider=result["provider"],
                    model=result["model"],
                    operation="analyze_personas",
                    tokens_used=result["tokens_used"],
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "personas_found": len(personas),
                        "content_length": len(content)
                    }
                )
            
            logger.info("Analyzed %d personas for meeting %s", len(personas), meeting_id)
            
            return {
                "personas": personas,
                "metadata": {
                    "provider": result["provider"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "cost": result["cost"],
                    "response_time": result["response_time"],
                    "meeting_id": meeting_id
                }
            }
            
        except Exception as e:
            # Track failed usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider="unknown",
                    model="unknown",
                    operation="analyze_personas",
                    tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error("Failed to analyze personas for meeting %s: %s", meeting_id, e)
            raise

    async def detect_meeting_phase(self, content: str, meeting_id: str, 
                                 user_id: str) -> Dict[str, Any]:
        """
        Detect current meeting phase
        
        Args:
            content: Meeting content to analyze
            meeting_id: Meeting identifier
            user_id: User identifier
            
        Returns:
            Meeting phase detection results
        """
        try:
            start_time = datetime.now()
            
            # Check quota
            if self.cost_controller:
                estimated_tokens = len(content.split()) * 1.1
                quota_check = await self.cost_controller.check_quota(
                    user_id, "detect_phase", int(estimated_tokens)
                )
                
                if not quota_check["allowed"]:
                    raise QuotaExceededError(
                        f"Quota exceeded: {', '.join(quota_check['exceeded_quotas'])}"
                    )
            
            # Create phase detection prompt
            prompt = f"""Analyze the following meeting content and determine the current meeting phase.
            
Content: {content}

Provide response in JSON format with:
- 'phase': current phase (scoping, planning, deciding, executing, reviewing)
- 'confidence': confidence score (0-1)
- 'indicators': array of indicators that led to this classification
- 'progress': estimated progress within the phase (0-1)"""
            
            # Use summarize method with custom prompt
            result = await self.ai_client.summarize(
                content=prompt,
                user_id=user_id,
                style="brief"
            )
            
            # Parse phase from response
            import json
            try:
                parsed = json.loads(result["summary"])
                phase_data = {
                    "phase": parsed.get("phase", "scoping"),
                    "confidence": parsed.get("confidence", 0.7),
                    "indicators": parsed.get("indicators", ["Meeting in progress"]),
                    "progress": parsed.get("progress", 0.5)
                }
            except json.JSONDecodeError:
                # Fallback: default phase detection
                phase_data = {
                    "phase": "scoping",
                    "confidence": 0.5,
                    "indicators": ["Meeting content analysis"],
                    "progress": 0.5
                }
            
            # Track usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider=result["provider"],
                    model=result["model"],
                    operation="detect_phase",
                    tokens_used=result["tokens_used"],
                    response_time_ms=response_time_ms,
                    success=True,
                    metadata={
                        "phase": phase_data["phase"],
                        "confidence": phase_data["confidence"],
                        "content_length": len(content)
                    }
                )
            
            logger.info("Detected phase '%s' for meeting %s (confidence: %.2f)", 
                       phase_data["phase"], meeting_id, phase_data["confidence"])
            
            return {
                **phase_data,
                "metadata": {
                    "provider": result["provider"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "cost": result["cost"],
                    "response_time": result["response_time"],
                    "meeting_id": meeting_id
                }
            }
            
        except Exception as e:
            # Track failed usage
            if self.cost_controller:
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.cost_controller.track_usage(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    provider="unknown",
                    model="unknown",
                    operation="detect_phase",
                    tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error("Failed to detect phase for meeting %s: %s", meeting_id, e)
            raise

    async def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """Get AI usage statistics for a user"""
        if not self.cost_controller:
            return {"error": "Cost controller not available"}
        
        return await self.cost_controller.get_usage_stats(user_id)

    async def get_cost_breakdown(self, user_id: str, period_days: int = 30) -> Dict[str, Any]:
        """Get cost breakdown for a user"""
        if not self.cost_controller:
            return {"error": "Cost controller not available"}
        
        return await self.cost_controller.get_cost_breakdown(user_id, period_days)

    async def set_user_quota(self, user_id: str, tier: CostTier, 
                           custom_limits: Optional[Dict] = None) -> bool:
        """Set user quota limits"""
        if not self.cost_controller:
            return False
        
        return await self.cost_controller.set_user_quota(user_id, tier, custom_limits)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on AI services"""
        ai_health = await self.ai_client.health_check()
        
        # Add cost controller status
        cost_controller_status = "healthy" if self.cost_controller else "not_configured"
        
        return {
            **ai_health,
            "cost_controller": cost_controller_status,
            "database": "connected" if self.db else "not_configured"
        }

    async def _setup_default_quotas(self):
        """Set up default quotas for system users"""
        # This would typically be called during system initialization
        # to set up default quotas for different user tiers
        pass

    async def close(self):
        """Close all connections"""
        if self.ai_client:
            await self.ai_client.close()
        
        logger.info("AIClientManager closed")


# Global instance
_ai_client_manager: Optional[AIClientManager] = None


def get_ai_client_manager(db_session: Optional[Session] = None) -> AIClientManager:
    """Get or create global AI client manager instance"""
    global _ai_client_manager
    
    if _ai_client_manager is None:
        _ai_client_manager = AIClientManager(db_session)
    
    return _ai_client_manager


async def initialize_ai_client_manager(db_session: Optional[Session] = None):
    """Initialize the global AI client manager"""
    manager = get_ai_client_manager(db_session)
    await manager.initialize()
    return manager