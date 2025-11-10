"""
Request analysis and intent classification.
Separated from orchestrator for clean architecture.
"""

import logging
import json
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from app.llm.router import get_llm_client
from app.core.error_handler import safe_execute

logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Types of user requests."""
    SKILL_AVAILABLE = "skill_available"
    AGENT_AVAILABLE = "agent_available"
    NEEDS_NEW_SKILL = "needs_new_skill"
    TOO_COMPLEX = "too_complex"
    UNCLEAR = "unclear"


@dataclass
class RequestAnalysis:
    """Result of request analysis."""
    request_type: RequestType
    confidence: float
    suggested_skill: Optional[str] = None
    suggested_agent: Optional[str] = None
    complexity_score: float = 0.0
    reasoning: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RequestAnalyzer:
    """Analyzes user requests to determine processing strategy."""
    
    def __init__(self):
        self.llm_client = None
        self._analysis_cache = {}
    
    async def initialize(self):
        """Initialize the analyzer."""
        self.llm_client = get_llm_client()
    
    async def analyze_request(self, user_request: str, context: Dict[str, Any] = None) -> RequestAnalysis:
        """
        Analyze user request to determine processing strategy.
        
        Args:
            user_request: The user's request text
            context: Additional context information
            
        Returns:
            RequestAnalysis with processing recommendations
        """
        if context is None:
            context = {}
        
        # Check cache first
        cache_key = f"{user_request}:{hash(str(context))}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]
        
        try:
            analysis = await self._perform_analysis(user_request, context)
            self._analysis_cache[cache_key] = analysis
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing request: {e}")
            return RequestAnalysis(
                request_type=RequestType.UNCLEAR,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}"
            )
    
    async def _perform_analysis(self, user_request: str, context: Dict[str, Any]) -> RequestAnalysis:
        """Perform the actual analysis using LLM."""
        
        analysis_prompt = self._build_analysis_prompt(user_request, context)
        
        response = await safe_execute(
            self.llm_client.generate,
            analysis_prompt,
            max_tokens=500,
            temperature=0.1
        )
        
        if not response:
            return RequestAnalysis(
                request_type=RequestType.UNCLEAR,
                confidence=0.0,
                reasoning="No response from LLM"
            )
        
        return self._parse_analysis_response(response, user_request)
    
    def _build_analysis_prompt(self, user_request: str, context: Dict[str, Any]) -> str:
        """Build prompt for request analysis."""
        
        return f"""
Analyze this user request and determine the best processing strategy.

User Request: "{user_request}"
Context: {json.dumps(context, indent=2)}

Classify the request into one of these categories:
1. SKILL_AVAILABLE - Can be handled by existing skills
2. AGENT_AVAILABLE - Can be handled by existing agents  
3. NEEDS_NEW_SKILL - Requires creating a new skill
4. TOO_COMPLEX - Too complex for current system
5. UNCLEAR - Request is unclear or ambiguous

Provide your analysis in this JSON format:
{{
    "request_type": "SKILL_AVAILABLE|AGENT_AVAILABLE|NEEDS_NEW_SKILL|TOO_COMPLEX|UNCLEAR",
    "confidence": 0.0-1.0,
    "suggested_skill": "skill_name or null",
    "suggested_agent": "agent_name or null", 
    "complexity_score": 0.0-1.0,
    "reasoning": "Brief explanation of your analysis"
}}
"""
    
    def _parse_analysis_response(self, response: str, original_request: str) -> RequestAnalysis:
        """Parse LLM response into RequestAnalysis."""
        
        try:
            import json
            data = json.loads(response.strip())
            
            return RequestAnalysis(
                request_type=RequestType(data.get("request_type", "UNCLEAR")),
                confidence=float(data.get("confidence", 0.0)),
                suggested_skill=data.get("suggested_skill"),
                suggested_agent=data.get("suggested_agent"),
                complexity_score=float(data.get("complexity_score", 0.0)),
                reasoning=data.get("reasoning", ""),
                metadata={"original_request": original_request}
            )
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return RequestAnalysis(
                request_type=RequestType.UNCLEAR,
                confidence=0.0,
                reasoning=f"Failed to parse response: {str(e)}"
            )
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self._analysis_cache.clear()


# Global analyzer instance
request_analyzer = RequestAnalyzer()
