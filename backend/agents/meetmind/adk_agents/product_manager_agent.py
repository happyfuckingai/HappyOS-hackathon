"""
MeetMind Product Manager Agent

Manages meeting intelligence product requirements and strategy.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ProductManagerAgent:
    """
    MeetMind Product Manager Agent - Manages product requirements and strategy.
    
    Responsible for defining product requirements, managing feature roadmaps,
    and ensuring meeting intelligence solutions meet user needs.
    """
    
    def __init__(self, services: Optional[Dict[str, Any]] = None):
        self.services = services or {}
        self.logger = logger
        
        # Initialize LLM client (same pattern as Felicia's Finance)
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.llm_client = AsyncOpenAI(api_key=api_key)
        else:
            self.llm_client = None
            self.logger.warning("OPENAI_API_KEY not set, LLM features will use fallback logic")
        
        self.agent_id = "meetmind.product_manager"
        
    async def define_requirements(self, user_needs: Dict[str, Any]) -> Dict[str, Any]:
        """Define product requirements based on user needs using LLM."""
        # Check if LLM client is available
        if not self.llm_client:
            return self._fallback_define_requirements(user_needs)
        
        try:
            # Use LLM for intelligent requirements analysis
            prompt = f"""
            Analyze these user needs and define comprehensive product requirements for a meeting intelligence system:
            
            User Needs: {json.dumps(user_needs, indent=2)}
            
            Provide a JSON response with:
            {{
                "functional_requirements": [
                    {{
                        "requirement": "requirement description",
                        "priority": "must_have|should_have|nice_to_have",
                        "user_story": "As a [user], I want [feature] so that [benefit]",
                        "acceptance_criteria": ["criterion1", "criterion2"],
                        "estimated_effort": "small|medium|large"
                    }}
                ],
                "non_functional_requirements": [
                    {{
                        "category": "performance|security|scalability|reliability",
                        "requirement": "requirement description",
                        "metric": "measurable metric",
                        "target": "target value",
                        "priority": "critical|high|medium|low"
                    }}
                ],
                "user_experience_requirements": [
                    {{
                        "aspect": "usability|accessibility|responsiveness",
                        "requirement": "requirement description",
                        "success_metric": "how to measure success",
                        "priority": "high|medium|low"
                    }}
                ],
                "technical_constraints": ["constraint1", "constraint2"],
                "business_constraints": ["constraint1", "constraint2"],
                "assumptions": ["assumption1", "assumption2"],
                "dependencies": ["dependency1", "dependency2"],
                "risks": [
                    {{
                        "risk": "risk description",
                        "impact": "high|medium|low",
                        "mitigation": "mitigation strategy"
                    }}
                ]
            }}
            """
            
            response = await self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            
            # Parse LLM response
            llm_content = response.choices[0].message.content
            requirements = json.loads(llm_content)
            
            return {
                "agent": "product_manager",
                "status": "requirements_defined",
                "requirements": requirements,
                "llm_used": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based logic
            return self._fallback_define_requirements(user_needs)
    
    def _fallback_define_requirements(self, user_needs: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback requirements definition using rule-based logic."""
        self.logger.warning("Using fallback logic for requirements definition")
        
        requirements = {
            "functional_requirements": [
                {
                    "requirement": "Real-time transcription of meeting audio",
                    "priority": "must_have",
                    "user_story": "As a meeting participant, I want real-time transcription so that I can follow along and review what was said",
                    "acceptance_criteria": [
                        "Transcription appears within 2 seconds of speech",
                        "Accuracy > 90% for clear audio",
                        "Supports multiple speakers"
                    ],
                    "estimated_effort": "large"
                },
                {
                    "requirement": "Automatic meeting summarization",
                    "priority": "must_have",
                    "user_story": "As a meeting participant, I want automatic summaries so that I can quickly review key points",
                    "acceptance_criteria": [
                        "Summary generated within 30 seconds of meeting end",
                        "Includes key topics and decisions",
                        "Length is 10-20% of original transcript"
                    ],
                    "estimated_effort": "medium"
                },
                {
                    "requirement": "Action item extraction",
                    "priority": "should_have",
                    "user_story": "As a team lead, I want action items extracted so that I can track follow-ups",
                    "acceptance_criteria": [
                        "Identifies tasks with assignees",
                        "Extracts deadlines when mentioned",
                        "Categorizes by priority"
                    ],
                    "estimated_effort": "medium"
                },
                {
                    "requirement": "Topic detection and categorization",
                    "priority": "should_have",
                    "user_story": "As a meeting organizer, I want topics detected so that I can organize discussions",
                    "acceptance_criteria": [
                        "Identifies 3-5 main topics per meeting",
                        "Groups related discussion segments",
                        "Provides topic timestamps"
                    ],
                    "estimated_effort": "medium"
                },
                {
                    "requirement": "Participant analysis and insights",
                    "priority": "nice_to_have",
                    "user_story": "As a manager, I want participant insights so that I can understand engagement",
                    "acceptance_criteria": [
                        "Tracks speaking time per participant",
                        "Analyzes sentiment of contributions",
                        "Identifies key contributors"
                    ],
                    "estimated_effort": "small"
                }
            ],
            "non_functional_requirements": [
                {
                    "category": "performance",
                    "requirement": "Low latency processing",
                    "metric": "End-to-end processing time",
                    "target": "< 3 seconds",
                    "priority": "critical"
                },
                {
                    "category": "performance",
                    "requirement": "High transcription accuracy",
                    "metric": "Word Error Rate (WER)",
                    "target": "< 10%",
                    "priority": "critical"
                },
                {
                    "category": "scalability",
                    "requirement": "Support concurrent meetings",
                    "metric": "Concurrent meeting capacity",
                    "target": "50+ meetings",
                    "priority": "high"
                },
                {
                    "category": "security",
                    "requirement": "Secure data handling",
                    "metric": "Compliance with security standards",
                    "target": "GDPR, SOC 2 compliant",
                    "priority": "critical"
                },
                {
                    "category": "reliability",
                    "requirement": "High availability",
                    "metric": "System uptime",
                    "target": "99.9%",
                    "priority": "high"
                }
            ],
            "user_experience_requirements": [
                {
                    "aspect": "usability",
                    "requirement": "Intuitive interface with minimal learning curve",
                    "success_metric": "Users can start a meeting within 30 seconds",
                    "priority": "high"
                },
                {
                    "aspect": "accessibility",
                    "requirement": "WCAG 2.1 AA compliance",
                    "success_metric": "Passes automated accessibility tests",
                    "priority": "high"
                },
                {
                    "aspect": "responsiveness",
                    "requirement": "Real-time feedback on all actions",
                    "success_metric": "UI updates within 100ms of user action",
                    "priority": "medium"
                }
            ],
            "technical_constraints": [
                "Must integrate with existing LiveKit infrastructure",
                "Must support WebSocket for real-time communication",
                "Must use AWS services for cloud deployment"
            ],
            "business_constraints": [
                "Development timeline: 3 months",
                "Budget: Limited to existing AWS credits",
                "Team size: 3-5 developers"
            ],
            "assumptions": [
                "Users have stable internet connection (> 1 Mbps)",
                "Meetings are primarily in English",
                "Audio quality is generally good (> 16kHz)"
            ],
            "dependencies": [
                "LiveKit for video/audio infrastructure",
                "AWS Bedrock for LLM capabilities",
                "OpenSearch for search functionality"
            ],
            "risks": [
                {
                    "risk": "Transcription accuracy may be poor in noisy environments",
                    "impact": "high",
                    "mitigation": "Implement noise cancellation and provide manual correction tools"
                },
                {
                    "risk": "LLM costs may exceed budget with high usage",
                    "impact": "medium",
                    "mitigation": "Implement caching and rate limiting"
                },
                {
                    "risk": "Real-time processing may have latency issues at scale",
                    "impact": "high",
                    "mitigation": "Implement horizontal scaling and load balancing"
                }
            ]
        }
        
        return {
            "agent": "product_manager",
            "status": "requirements_defined",
            "requirements": requirements,
            "llm_used": False,
            "fallback": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def prioritize_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Prioritize features based on business value and user impact using LLM."""
        # Check if LLM client is available
        if not self.llm_client:
            return self._fallback_prioritize_features(features)
        
        try:
            # Use LLM for intelligent feature prioritization
            prompt = f"""
            Prioritize these features for a meeting intelligence system based on business value, user impact, and implementation effort:
            
            Features: {json.dumps(features, indent=2)}
            
            Provide a JSON response with:
            {{
                "prioritization_framework": {{
                    "criteria": ["business_value", "user_impact", "implementation_effort", "risk"],
                    "methodology": "description of prioritization approach"
                }},
                "critical_priority": [
                    {{
                        "feature": "feature name",
                        "business_value": "high|medium|low",
                        "user_impact": "high|medium|low",
                        "implementation_effort": "small|medium|large",
                        "rationale": "why this is critical",
                        "dependencies": ["dependency1"],
                        "estimated_timeline": "time estimate"
                    }}
                ],
                "high_priority": [
                    {{
                        "feature": "feature name",
                        "business_value": "high|medium|low",
                        "user_impact": "high|medium|low",
                        "implementation_effort": "small|medium|large",
                        "rationale": "why this is high priority",
                        "dependencies": ["dependency1"],
                        "estimated_timeline": "time estimate"
                    }}
                ],
                "medium_priority": [
                    {{
                        "feature": "feature name",
                        "business_value": "high|medium|low",
                        "user_impact": "high|medium|low",
                        "implementation_effort": "small|medium|large",
                        "rationale": "why this is medium priority",
                        "dependencies": ["dependency1"],
                        "estimated_timeline": "time estimate"
                    }}
                ],
                "low_priority": [
                    {{
                        "feature": "feature name",
                        "business_value": "high|medium|low",
                        "user_impact": "high|medium|low",
                        "implementation_effort": "small|medium|large",
                        "rationale": "why this is low priority",
                        "dependencies": ["dependency1"],
                        "estimated_timeline": "time estimate"
                    }}
                ],
                "deferred": [
                    {{
                        "feature": "feature name",
                        "rationale": "why this is deferred",
                        "reconsider_when": "conditions for reconsidering"
                    }}
                ],
                "roadmap_phases": [
                    {{
                        "phase": "phase name (e.g., MVP, Phase 2)",
                        "duration": "time estimate",
                        "features": ["feature1", "feature2"],
                        "goals": ["goal1", "goal2"]
                    }}
                ],
                "trade_offs": [
                    {{
                        "decision": "trade-off decision",
                        "chosen": "what was chosen",
                        "alternative": "what was not chosen",
                        "rationale": "why this trade-off was made"
                    }}
                ]
            }}
            """
            
            response = await self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            
            # Parse LLM response
            llm_content = response.choices[0].message.content
            prioritized_features = json.loads(llm_content)
            
            return {
                "agent": "product_manager",
                "status": "features_prioritized",
                "prioritized_features": prioritized_features,
                "llm_used": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based logic
            return self._fallback_prioritize_features(features)
    
    def _fallback_prioritize_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback feature prioritization using rule-based logic."""
        self.logger.warning("Using fallback logic for feature prioritization")
        
        prioritized_features = {
            "prioritization_framework": {
                "criteria": ["business_value", "user_impact", "implementation_effort", "risk"],
                "methodology": "MoSCoW method with effort-impact matrix"
            },
            "critical_priority": [
                {
                    "feature": "real_time_transcription",
                    "business_value": "high",
                    "user_impact": "high",
                    "implementation_effort": "large",
                    "rationale": "Core functionality without which the product cannot function",
                    "dependencies": [],
                    "estimated_timeline": "6 weeks"
                },
                {
                    "feature": "meeting_recording",
                    "business_value": "high",
                    "user_impact": "high",
                    "implementation_effort": "medium",
                    "rationale": "Essential for post-meeting review and compliance",
                    "dependencies": ["real_time_transcription"],
                    "estimated_timeline": "3 weeks"
                }
            ],
            "high_priority": [
                {
                    "feature": "automatic_summarization",
                    "business_value": "high",
                    "user_impact": "high",
                    "implementation_effort": "medium",
                    "rationale": "High user demand and differentiating feature",
                    "dependencies": ["real_time_transcription"],
                    "estimated_timeline": "4 weeks"
                },
                {
                    "feature": "action_item_extraction",
                    "business_value": "medium",
                    "user_impact": "high",
                    "implementation_effort": "medium",
                    "rationale": "Directly improves productivity and follow-through",
                    "dependencies": ["automatic_summarization"],
                    "estimated_timeline": "3 weeks"
                }
            ],
            "medium_priority": [
                {
                    "feature": "topic_detection",
                    "business_value": "medium",
                    "user_impact": "medium",
                    "implementation_effort": "medium",
                    "rationale": "Useful for organizing and searching meetings",
                    "dependencies": ["automatic_summarization"],
                    "estimated_timeline": "3 weeks"
                },
                {
                    "feature": "sentiment_analysis",
                    "business_value": "low",
                    "user_impact": "medium",
                    "implementation_effort": "small",
                    "rationale": "Provides insights but not essential for core workflow",
                    "dependencies": ["real_time_transcription"],
                    "estimated_timeline": "2 weeks"
                }
            ],
            "low_priority": [
                {
                    "feature": "participant_analysis",
                    "business_value": "low",
                    "user_impact": "low",
                    "implementation_effort": "small",
                    "rationale": "Nice to have but limited immediate value",
                    "dependencies": ["real_time_transcription"],
                    "estimated_timeline": "2 weeks"
                },
                {
                    "feature": "multi_language_support",
                    "business_value": "medium",
                    "user_impact": "low",
                    "implementation_effort": "large",
                    "rationale": "Important for global expansion but not for initial market",
                    "dependencies": ["real_time_transcription"],
                    "estimated_timeline": "8 weeks"
                }
            ],
            "deferred": [
                {
                    "feature": "video_analysis",
                    "rationale": "High complexity and unclear ROI at this stage",
                    "reconsider_when": "After achieving product-market fit with core features"
                },
                {
                    "feature": "ai_meeting_assistant",
                    "rationale": "Requires significant AI infrastructure investment",
                    "reconsider_when": "After establishing stable user base and revenue"
                }
            ],
            "roadmap_phases": [
                {
                    "phase": "MVP (Minimum Viable Product)",
                    "duration": "3 months",
                    "features": [
                        "real_time_transcription",
                        "meeting_recording",
                        "automatic_summarization"
                    ],
                    "goals": [
                        "Validate core value proposition",
                        "Achieve 100 active users",
                        "Gather user feedback"
                    ]
                },
                {
                    "phase": "Phase 2 (Enhanced Intelligence)",
                    "duration": "2 months",
                    "features": [
                        "action_item_extraction",
                        "topic_detection",
                        "sentiment_analysis"
                    ],
                    "goals": [
                        "Increase user engagement",
                        "Improve retention rate",
                        "Expand feature set"
                    ]
                },
                {
                    "phase": "Phase 3 (Advanced Features)",
                    "duration": "3 months",
                    "features": [
                        "participant_analysis",
                        "multi_language_support",
                        "advanced_search"
                    ],
                    "goals": [
                        "Scale to 1000+ users",
                        "Enter international markets",
                        "Establish competitive moat"
                    ]
                }
            ],
            "trade_offs": [
                {
                    "decision": "Transcription accuracy vs. latency",
                    "chosen": "Balanced approach with 90% accuracy and < 2s latency",
                    "alternative": "95% accuracy with 5s latency",
                    "rationale": "Real-time experience is more important than perfect accuracy for MVP"
                },
                {
                    "decision": "Feature breadth vs. depth",
                    "chosen": "Fewer features with high quality",
                    "alternative": "Many features with basic implementation",
                    "rationale": "Better to excel at core features than be mediocre at many"
                },
                {
                    "decision": "Build vs. buy for transcription",
                    "chosen": "Use existing transcription service (AWS Transcribe)",
                    "alternative": "Build custom transcription model",
                    "rationale": "Faster time to market and lower initial investment"
                }
            ]
        }
        
        return {
            "agent": "product_manager",
            "status": "features_prioritized",
            "prioritized_features": prioritized_features,
            "llm_used": False,
            "fallback": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get product manager agent status."""
        return {
            "agent": "product_manager",
            "status": "active",
            "role": "meeting_intelligence_product_management",
            "specialties": ["requirements_analysis", "feature_prioritization", "product_strategy"],
            "llm_integration": "enabled",
            "timestamp": datetime.utcnow().isoformat()
        }