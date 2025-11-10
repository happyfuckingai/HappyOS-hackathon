"""
Clean skill generator.
Uses separated modules for prompts, templates, and validation.
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

from app.config.settings import get_settings
from app.core.error_handler import safe_execute, HappyOSError
from app.core.performance import monitor_performance
from app.llm.router import get_llm_client

# Import separated modules
from .prompts.skill_prompts import skill_prompts
from .templates.skill_templates import skill_templates
from .validation.skill_validator import skill_validator, ValidationResult

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SkillGenerationRequest:
    """Request for generating a new skill."""
    intent: str
    user_request: str
    context: Dict[str, Any]
    entities: List[str]
    expected_output: str
    priority: str = "normal"


@dataclass
class SkillGenerationResult:
    """Result of skill generation."""
    success: bool
    skill_name: Optional[str] = None
    skill_code: Optional[str] = None
    file_path: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CleanSkillGenerator:
    """
    Clean skill generator using separated modules.
    No monster file - each responsibility is handled separately.
    """
    
    def __init__(self):
        self.llm_client = None
        self.skills_dir = Path("app/skills") # Changed to hardcoded path, similar to SkillGenerator
        self.generation_history = []
        self.initialized = False
    
    async def initialize(self):
        """Initialize the skill generator."""
        if self.initialized:
            return
        
        try:
            self.llm_client = await get_llm_client()
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            self.initialized = True
            logger.info("Clean skill generator initialized")
        except Exception as e:
            logger.error(f"Error initializing skill generator: {e}")
            raise HappyOSError(f"Skill generator initialization failed: {e}")
    
    @monitor_performance
    async def generate_skill(
        self, 
        request: SkillGenerationRequest
    ) -> SkillGenerationResult:
        """
        Generate a new skill based on the request.
        
        Args:
            request: SkillGenerationRequest with generation details
            
        Returns:
            SkillGenerationResult with generation outcome
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Step 1: Determine skill type and template
            skill_type = await self._determine_skill_type(request)
            
            # Step 2: Generate skill code
            skill_code = await self._generate_skill_code(request, skill_type)
            
            if not skill_code:
                return SkillGenerationResult(
                    success=False,
                    error="Failed to generate skill code",
                    execution_time=time.time() - start_time
                )
            
            # Step 3: Validate generated skill
            validation_result = await skill_validator.validate_skill(
                skill_code, 
                request.intent
            )
            
            # Step 4: Improve skill if validation failed
            if not validation_result.valid and validation_result.security_score >= 5:
                skill_code = await self._improve_skill_code(
                    skill_code, 
                    validation_result, 
                    request
                )
                
                # Re-validate improved skill
                validation_result = await skill_validator.validate_skill(
                    skill_code, 
                    request.intent
                )
            
            # Step 5: Save skill if valid
            skill_name = None
            file_path = None
            
            if validation_result.valid:
                skill_name = self._generate_skill_name(request.intent)
                file_path = await self._save_skill(skill_name, skill_code)
            
            execution_time = time.time() - start_time
            
            result = SkillGenerationResult(
                success=validation_result.valid,
                skill_name=skill_name,
                skill_code=skill_code,
                file_path=file_path,
                validation_result=validation_result,
                error=None if validation_result.valid else "Skill validation failed",
                execution_time=execution_time,
                metadata={
                    "skill_type": skill_type,
                    "request_intent": request.intent,
                    "generation_attempts": 1  # Could be more if we retry
                }
            )
            
            # Track generation
            self._track_generation(result, request)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error generating skill: {e}")
            
            return SkillGenerationResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _determine_skill_type(self, request: SkillGenerationRequest) -> str:
        """Determine the type of skill to generate."""
        
        request_lower = request.user_request.lower()
        
        # Simple heuristics for skill type detection
        if any(word in request_lower for word in ["scrape", "web", "url", "website", "html"]):
            return "web_scraping"
        elif any(word in request_lower for word in ["api", "rest", "http", "endpoint"]):
            return "api_integration"
        elif any(word in request_lower for word in ["file", "read", "write", "save", "load"]):
            return "file_operations"
        elif any(word in request_lower for word in ["data", "process", "analyze", "filter", "sort"]):
            return "data_processing"
        else:
            return "base"
    
    async def _generate_skill_code(
        self, 
        request: SkillGenerationRequest, 
        skill_type: str
    ) -> Optional[str]:
        """Generate skill code using LLM."""
        
        try:
            # Get appropriate prompt
            prompt = skill_prompts.get_skill_generation_prompt(
                request.intent,
                request.user_request,
                request.context
            )
            
            # Add template-specific guidance
            template_prompt = skill_prompts.get_template_prompt(skill_type)
            if template_prompt:
                prompt += f"\n\n{template_prompt}"
            
            # Generate code
            response = await safe_execute(
                self.llm_client.generate,
                prompt,
                max_tokens=2000,
                temperature=0.1
            )
            
            if not response:
                return None
            
            # Extract Python code from response
            code = self._extract_code_from_response(response)
            
            return code
            
        except Exception as e:
            logger.error(f"Error generating skill code: {e}")
            return None
    
    async def _improve_skill_code(
        self, 
        skill_code: str, 
        validation_result: ValidationResult, 
        request: SkillGenerationRequest
    ) -> str:
        """Improve skill code based on validation issues."""
        
        try:
            # Create improvement prompt
            error_message = "; ".join(validation_result.issues)
            
            prompt = skill_prompts.get_skill_improvement_prompt(
                skill_code,
                error_message,
                request.intent
            )
            
            # Generate improved code
            response = await safe_execute(
                self.llm_client.generate,
                prompt,
                max_tokens=2000,
                temperature=0.1
            )
            
            if response:
                improved_code = self._extract_code_from_response(response)
                return improved_code if improved_code else skill_code
            
            return skill_code
            
        except Exception as e:
            logger.error(f"Error improving skill code: {e}")
            return skill_code
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        
        # Look for code blocks
        import re
        
        # Try to find code in triple backticks
        code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Try to find code in single backticks
        code_match = re.search(r'```\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # If no code blocks, assume entire response is code
        # but validate it looks like Python
        if 'def ' in response and 'import ' in response:
            return response.strip()
        
        return None
    
    def _generate_skill_name(self, intent: str) -> str:
        """Generate a unique skill name."""
        
        # Clean intent for filename
        import re
        clean_intent = re.sub(r'[^a-zA-Z0-9_]', '_', intent.lower())
        clean_intent = re.sub(r'_+', '_', clean_intent).strip('_')
        
        # Add timestamp for uniqueness
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return f"{clean_intent}_{timestamp}"
    
    async def _save_skill(self, skill_name: str, skill_code: str) -> str:
        """Save generated skill to file."""
        
        try:
            file_path = self.skills_dir / f"{skill_name}.py"
            
            # Add header comment
            header = f'''"""
Generated skill: {skill_name}
Created: {datetime.now().isoformat()}
Auto-generated by HappyOS Skill Generator
"""

'''
            
            full_code = header + skill_code
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_code)
            
            logger.info(f"Skill saved to {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving skill: {e}")
            raise
    
    def _track_generation(
        self, 
        result: SkillGenerationResult, 
        request: SkillGenerationRequest
    ):
        """Track skill generation for analytics."""
        
        self.generation_history.append({
            "timestamp": datetime.now(),
            "success": result.success,
            "skill_name": result.skill_name,
            "intent": request.intent,
            "execution_time": result.execution_time,
            "validation_score": (
                result.validation_result.quality_score 
                if result.validation_result else 0
            )
        })
        
        # Keep only recent history
        if len(self.generation_history) > 1000:
            self.generation_history = self.generation_history[-500:]
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get skill generation statistics."""
        
        if not self.generation_history:
            return {"total_generations": 0}
        
        total = len(self.generation_history)
        successful = sum(1 for h in self.generation_history if h["success"])
        
        avg_time = sum(h["execution_time"] for h in self.generation_history) / total
        avg_quality = sum(h["validation_score"] for h in self.generation_history) / total
        
        return {
            "total_generations": total,
            "success_rate": successful / total,
            "avg_execution_time": avg_time,
            "avg_quality_score": avg_quality,
            "recent_skills": [
                h["skill_name"] for h in self.generation_history[-10:] 
                if h["success"] and h["skill_name"]
            ]
        }


# Global clean skill generator instance
clean_skill_generator = CleanSkillGenerator()


# Compatibility function for existing code
async def generate_skill_for_request(user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Compatibility function for existing code.
    Routes to the clean skill generator.
    """
    if context is None:
        context = {}
    
    # Create request object
    request = SkillGenerationRequest(
        intent=context.get("intent", user_request[:50]),
        user_request=user_request,
        context=context,
        entities=context.get("entities", []),
        expected_output=context.get("expected_output", "")
    )
    
    # Generate skill
    result = await clean_skill_generator.generate_skill(request)
    
    # Return in format expected by existing code
    if result.success:
        return {
            "success": True,
            "skill_name": result.skill_name,
            "file_path": result.file_path,
            "validation": result.validation_result.__dict__ if result.validation_result else None
        }
    else:
        return {
            "success": False,
            "error": result.error,
            "validation": result.validation_result.__dict__ if result.validation_result else None
        }