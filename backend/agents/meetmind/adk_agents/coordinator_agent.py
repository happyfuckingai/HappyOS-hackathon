"""
MeetMind Coordinator Agent

Orchestrates meeting intelligence workflows and coordinates with other agents.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class CoordinatorAgent:
    """
    MeetMind Coordinator Agent - Orchestrates meeting intelligence workflows.
    
    Coordinates between architect, implementation, product manager, and QA agents
    to deliver comprehensive meeting intelligence solutions.
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
        
        self.agent_id = "meetmind.coordinator"
        self.active_workflows = {}
        
    async def coordinate_meeting_analysis(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate comprehensive meeting analysis workflow using LLM."""
        # Check if LLM client is available
        if not self.llm_client:
            return self._fallback_coordination(meeting_data)
        
        try:
            # Use LLM for intelligent workflow coordination
            prompt = f"""
            Analyze this meeting data and create a coordination plan for meeting intelligence workflow:
            
            Meeting Data: {json.dumps(meeting_data, indent=2)}
            
            Provide a JSON response with:
            {{
                "workflow_id": "unique_workflow_identifier",
                "analysis_tasks": [
                    {{
                        "task": "task_name",
                        "agent": "responsible_agent",
                        "priority": "high|medium|low",
                        "dependencies": ["dependency1"],
                        "estimated_duration": "time estimate"
                    }}
                ],
                "execution_order": ["task1", "task2", "task3"],
                "parallel_tasks": [["task1", "task2"]],
                "critical_path": ["task1", "task3"],
                "resource_allocation": {{
                    "architect": "design_framework",
                    "implementation": "process_transcript",
                    "product_manager": "define_requirements",
                    "quality_assurance": "validate_results"
                }},
                "estimated_completion_time": "time estimate",
                "risk_factors": ["risk1", "risk2"],
                "success_criteria": ["criterion1", "criterion2"]
            }}
            """
            
            response = await self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse LLM response
            llm_content = response.choices[0].message.content
            coordination_plan = json.loads(llm_content)
            
            # Generate workflow ID
            workflow_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # Store workflow
            self.active_workflows[workflow_id] = {
                "meeting_data": meeting_data,
                "coordination_plan": coordination_plan,
                "status": "in_progress",
                "started_at": datetime.utcnow().isoformat()
            }
            
            return {
                "agent": "coordinator",
                "status": "workflow_started",
                "workflow_id": workflow_id,
                "meeting_id": meeting_data.get("meeting_id"),
                "coordination_plan": coordination_plan,
                "llm_used": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based logic
            return self._fallback_coordination(meeting_data)
    
    def _fallback_coordination(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback coordination using rule-based logic."""
        self.logger.warning("Using fallback logic for workflow coordination")
        
        workflow_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Rule-based coordination plan
        coordination_plan = {
            "workflow_id": workflow_id,
            "analysis_tasks": [
                {
                    "task": "design_analysis_framework",
                    "agent": "architect",
                    "priority": "high",
                    "dependencies": [],
                    "estimated_duration": "5 minutes"
                },
                {
                    "task": "define_requirements",
                    "agent": "product_manager",
                    "priority": "high",
                    "dependencies": [],
                    "estimated_duration": "3 minutes"
                },
                {
                    "task": "implement_analysis_pipeline",
                    "agent": "implementation",
                    "priority": "high",
                    "dependencies": ["design_analysis_framework"],
                    "estimated_duration": "10 minutes"
                },
                {
                    "task": "process_transcript",
                    "agent": "implementation",
                    "priority": "high",
                    "dependencies": ["implement_analysis_pipeline"],
                    "estimated_duration": "5 minutes"
                },
                {
                    "task": "validate_quality",
                    "agent": "quality_assurance",
                    "priority": "medium",
                    "dependencies": ["process_transcript"],
                    "estimated_duration": "3 minutes"
                }
            ],
            "execution_order": [
                "design_analysis_framework",
                "define_requirements",
                "implement_analysis_pipeline",
                "process_transcript",
                "validate_quality"
            ],
            "parallel_tasks": [
                ["design_analysis_framework", "define_requirements"]
            ],
            "critical_path": [
                "design_analysis_framework",
                "implement_analysis_pipeline",
                "process_transcript"
            ],
            "resource_allocation": {
                "architect": "design_framework",
                "implementation": "process_transcript",
                "product_manager": "define_requirements",
                "quality_assurance": "validate_results"
            },
            "estimated_completion_time": "26 minutes",
            "risk_factors": [
                "Transcript quality may affect analysis accuracy",
                "High participant count may increase processing time"
            ],
            "success_criteria": [
                "All tasks completed successfully",
                "Quality validation passed",
                "Results delivered within estimated time"
            ]
        }
        
        # Store workflow
        self.active_workflows[workflow_id] = {
            "meeting_data": meeting_data,
            "coordination_plan": coordination_plan,
            "status": "in_progress",
            "started_at": datetime.utcnow().isoformat()
        }
        
        return {
            "agent": "coordinator",
            "status": "workflow_started",
            "workflow_id": workflow_id,
            "meeting_id": meeting_data.get("meeting_id"),
            "coordination_plan": coordination_plan,
            "llm_used": False,
            "fallback": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get coordinator agent status."""
        return {
            "agent": "coordinator",
            "status": "active",
            "role": "meeting_workflow_orchestration",
            "active_workflows": len(self.active_workflows),
            "specialties": ["workflow_coordination", "meeting_intelligence"],
            "llm_integration": "enabled",
            "timestamp": datetime.utcnow().isoformat()
        }