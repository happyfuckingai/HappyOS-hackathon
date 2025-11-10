"""
Response formatting and standardization.
Handles consistent response formatting across the system.
"""

import logging
import json
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Types of responses."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    PENDING = "pending"
    REDIRECT = "redirect"


@dataclass
class FormattedResponse:
    """Standardized response format."""
    type: ResponseType
    message: str
    data: Any = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    execution_time: float = 0.0
    source: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["type"] = self.type.value
        result["timestamp"] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class ResponseFormatter:
    """Handles response formatting and standardization."""
    
    def __init__(self):
        self.formatting_rules = {}
        self.response_templates = {}
        self._load_default_templates()
    
    def format_success_response(
        self, 
        message: str, 
        data: Any = None, 
        source: str = None,
        execution_time: float = 0.0
    ) -> FormattedResponse:
        """Format a success response."""
        
        return FormattedResponse(
            type=ResponseType.SUCCESS,
            message=message,
            data=data,
            source=source,
            execution_time=execution_time,
            metadata={"formatted_at": datetime.now().isoformat()}
        )
    
    def format_error_response(
        self, 
        message: str, 
        error_details: Any = None, 
        source: str = None
    ) -> FormattedResponse:
        """Format an error response."""
        
        return FormattedResponse(
            type=ResponseType.ERROR,
            message=message,
            data=error_details,
            source=source,
            metadata={
                "error_type": type(error_details).__name__ if error_details else "Unknown",
                "formatted_at": datetime.now().isoformat()
            }
        )
    
    def format_skill_response(
        self, 
        skill_name: str, 
        result: Any, 
        execution_time: float = 0.0
    ) -> FormattedResponse:
        """Format response from skill execution."""
        
        if isinstance(result, dict) and "error" in result:
            return self.format_error_response(
                f"Skill {skill_name} failed",
                result["error"],
                source=skill_name
            )
        
        return self.format_success_response(
            f"Skill {skill_name} executed successfully",
            result,
            source=skill_name,
            execution_time=execution_time
        )
    
    def format_agent_response(
        self, 
        agent_name: str, 
        result: Any, 
        execution_time: float = 0.0
    ) -> FormattedResponse:
        """Format response from agent execution."""
        
        if isinstance(result, dict) and "error" in result:
            return self.format_error_response(
                f"Agent {agent_name} failed",
                result["error"],
                source=agent_name
            )
        
        return self.format_success_response(
            f"Agent {agent_name} completed task",
            result,
            source=agent_name,
            execution_time=execution_time
        )
    
    def format_pipeline_response(
        self, 
        pipeline_steps: List[Dict[str, Any]], 
        final_result: Any,
        total_execution_time: float = 0.0
    ) -> FormattedResponse:
        """Format response from pipeline execution."""
        
        # Check if any step failed
        failed_steps = [step for step in pipeline_steps if not step.get("success", True)]
        
        if failed_steps:
            return FormattedResponse(
                type=ResponseType.PARTIAL,
                message=f"Pipeline completed with {len(failed_steps)} failed steps",
                data=final_result,
                source="pipeline",
                execution_time=total_execution_time,
                metadata={
                    "total_steps": len(pipeline_steps),
                    "successful_steps": len(pipeline_steps) - len(failed_steps),
                    "failed_steps": failed_steps,
                    "formatted_at": datetime.now().isoformat()
                }
            )
        
        return self.format_success_response(
            f"Pipeline completed successfully with {len(pipeline_steps)} steps",
            final_result,
            source="pipeline",
            execution_time=total_execution_time
        )
    
    def format_mcp_response(
        self, 
        mcp_result: Dict[str, Any], 
        execution_time: float = 0.0
    ) -> FormattedResponse:
        """Format response from MCP routing."""
        
        if mcp_result.get("success"):
            return self.format_success_response(
                "MCP request processed successfully",
                mcp_result.get("data"),
                source="mcp",
                execution_time=execution_time
            )
        else:
            return self.format_error_response(
                "MCP request failed",
                mcp_result.get("error"),
                source="mcp"
            )
    
    def format_user_friendly_response(self, response: FormattedResponse) -> str:
        """Format response for user-friendly display."""
        
        if response.type == ResponseType.SUCCESS:
            return self._format_success_for_user(response)
        elif response.type == ResponseType.ERROR:
            return self._format_error_for_user(response)
        elif response.type == ResponseType.PARTIAL:
            return self._format_partial_for_user(response)
        else:
            return response.message
    
    def _format_success_for_user(self, response: FormattedResponse) -> str:
        """Format success response for user."""
        
        base_message = response.message
        
        # Add execution time if significant
        if response.execution_time > 1.0:
            base_message += f" (completed in {response.execution_time:.1f}s)"
        
        # Add data summary if available
        if response.data:
            data_summary = self._summarize_data_for_user(response.data)
            if data_summary:
                base_message += f"\n\n{data_summary}"
        
        return base_message
    
    def _format_error_for_user(self, response: FormattedResponse) -> str:
        """Format error response for user."""
        
        base_message = f"❌ {response.message}"
        
        # Add helpful error details without technical jargon
        if response.data:
            error_help = self._get_user_friendly_error_help(response.data)
            if error_help:
                base_message += f"\n\n💡 {error_help}"
        
        return base_message
    
    def _format_partial_for_user(self, response: FormattedResponse) -> str:
        """Format partial response for user."""
        
        base_message = f"⚠️ {response.message}"
        
        # Add details about what succeeded
        if response.metadata:
            successful = response.metadata.get("successful_steps", 0)
            total = response.metadata.get("total_steps", 0)
            
            if total > 0:
                base_message += f"\n\n✅ {successful}/{total} steps completed successfully"
        
        return base_message
    
    def _summarize_data_for_user(self, data: Any) -> Optional[str]:
        """Create user-friendly summary of response data."""
        
        if isinstance(data, dict):
            if "result" in data:
                return str(data["result"])
            elif "message" in data:
                return str(data["message"])
            elif len(data) == 1:
                return str(list(data.values())[0])
        elif isinstance(data, list):
            if len(data) == 1:
                return str(data[0])
            elif len(data) > 1:
                return f"Generated {len(data)} items"
        elif isinstance(data, str):
            return data[:200] + "..." if len(data) > 200 else data
        
        return None
    
    def _get_user_friendly_error_help(self, error_data: Any) -> Optional[str]:
        """Get user-friendly help for errors."""
        
        error_str = str(error_data).lower()
        
        if "permission" in error_str or "unauthorized" in error_str:
            return "You may not have permission to perform this action."
        elif "network" in error_str or "connection" in error_str:
            return "There seems to be a network connectivity issue. Please try again."
        elif "timeout" in error_str:
            return "The request took too long to complete. Please try again."
        elif "not found" in error_str:
            return "The requested resource could not be found."
        elif "invalid" in error_str:
            return "Please check your input and try again."
        
        return None
    
    def _load_default_templates(self):
        """Load default response templates."""
        
        self.response_templates = {
            "skill_created": "✨ New skill '{skill_name}' has been created and is ready to use!",
            "skill_executed": "✅ Skill '{skill_name}' executed successfully",
            "agent_delegated": "🤖 Task delegated to {agent_name} agent",
            "mcp_routed": "🔄 Request routed through MCP protocol",
            "pipeline_started": "🚀 Processing pipeline started",
            "pipeline_completed": "🎉 Processing pipeline completed successfully"
        }
    
    def apply_template(self, template_name: str, **kwargs) -> str:
        """Apply a response template with variables."""
        
        template = self.response_templates.get(template_name, "{message}")
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable {e} for template {template_name}")
            return template


# Global formatter instance
response_formatter = ResponseFormatter()