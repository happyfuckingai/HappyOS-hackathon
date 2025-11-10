"""
Skill Auto-Generator - Automatically creates new skills when needed.
Part of the self-building system that generates, saves, and registers skills.
"""

import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from app.config.settings import get_settings
from app.llm.router import get_llm_client
# Provide a robust safe_execute fallback to avoid missing import issues
try:
    from app.core.error_handling.safe_executor import safe_execute  # alternate location
except Exception:
    try:
        from app.core.error_handler import safe_execute  # legacy location
    except Exception:
        async def safe_execute(func, *args, **kwargs):
            """Minimal async-safe executor fallback."""
            res = func(*args, **kwargs)
            return await res if hasattr(res, "__await__") else res

from ..config import get_config

from ..discovery.component_scanner import ComponentInfo, component_scanner
from ..registry.dynamic_registry import dynamic_registry

logger = logging.getLogger(__name__)
settings = get_settings()


class SkillAutoGenerator:
    """
    Automatically generates new skills when needed.
    Creates code, saves files, and registers skills dynamically.
    """
    
    def __init__(self):
        self.config = get_config()
        self.llm_client = None
        # Resolve skills_dir relative to project working directory to avoid PermissionError on absolute paths
        try:
            base_dir = Path(self.config.generated_skills_directory)
            if not base_dir.is_absolute():
                self.skills_dir = (Path.cwd() / base_dir).resolve()
            else:
                try:
                    base_dir.mkdir(parents=True, exist_ok=True)
                    self.skills_dir = base_dir
                except Exception:
                    self.skills_dir = (Path.cwd() / "app" / "skills" / "generated").resolve()
        except Exception:
            self.skills_dir = (Path.cwd() / "app" / "skills" / "generated").resolve()

        # self.templates_dir is unused
        self.generation_history = []
        self.initialized = False
        # Lazy directory creation: do NOT mkdir at import-time; defer to initialize()
    
    def _ensure_init_files(self):
        """Ensure __init__.py files exist in generated directories."""
        init_file = self.skills_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Auto-generated skills package."""\n')
    
    async def initialize(self):
        """Initialize the auto-generator (lazy and safe)."""
        if self.initialized:
            return
        try:
            # Ensure directories exist here (not at import-time)
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_init_files()

            # LLM client is optional; only acquire if available (UI-configured)
            try:
                self.llm_client = get_llm_client()  # router returns a client synchronously
            except Exception:
                self.llm_client = None

            self.initialized = True
            logger.info("Skill auto-generator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize skill auto-generator: {e}")
            raise
    
    async def generate_skill_for_need(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ComponentInfo]:
        """
        Generate a new skill based on user need.
        
        Args:
            user_request: The user's request that triggered the need
            context: Additional context for generation
            
        Returns:
            ComponentInfo for the generated skill, or None if failed
        """
        if not self.initialized:
            await self.initialize()
        
        if context is None:
            context = {}
        
        try:
            logger.info(f"Auto-generate skill for request prefix={user_request[:100]!r} ...")
            
            # Step 1: Analyze the request to determine skill type
            skill_type = await self._analyze_skill_type(user_request, context)
            
            # Step 2: Generate skill code
            skill_code = await self._generate_skill_code(user_request, skill_type, context)
            
            if not skill_code:
                logger.error("Failed to generate skill code")
                return None
            
            # Step 3: Validate the generated code
            if not await self._validate_skill_code(skill_code):
                logger.error("Generated skill code failed validation")
                return None
            
            # Step 4: Save the skill to file
            skill_name = self._generate_skill_name(user_request)
            file_path = await self._save_skill_file(skill_name, skill_code, user_request)
            
            if not file_path:
                logger.error("Failed to save skill file")
                return None
            
            # Step 5: Create ComponentInfo
            component = ComponentInfo(
                name=skill_name,
                type="skills",
                path=str(file_path),
                module_name=f"app.skills.generated.{skill_name}",
                last_modified=datetime.now(),
                metadata={
                    "auto_generated": True,
                    "user_request": user_request,
                    "skill_type": skill_type,
                    "generation_timestamp": datetime.now().isoformat()
                }
            )
            
            # Step 6: Register the skill
            success = await self._register_skill(component)
            
            if success:
                # Track generation
                self._track_generation(component, user_request, True)
                logger.info(f"Auto-generated and registered skill: {skill_name}")
                return component
            else:
                logger.error(f"Register auto-generated skill failed: {skill_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error auto-generating skill: {e}")
            self._track_generation(None, user_request, False, str(e))
            return None
    
    async def _analyze_skill_type(self, user_request: str, context: Dict[str, Any]) -> str:
        """Determine skill type based on simple keyword mapping."""
        
        request_lower = user_request.lower()
        
        for skill_type_key, keywords in self.config.skill_type_keywords.items():
            if any(word in request_lower for word in keywords):
                return skill_type_key
        return "general"
    
    async def _generate_skill_code(
        self, 
        user_request: str, 
        skill_type: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Generate skill code using LLM."""
        
        try:
            # Create generation prompt
            prompt = self._create_generation_prompt(user_request, skill_type, context)

            # Generate code using LLM (optional)
            if not self.llm_client:
                logger.warning("LLM client not configured; skipping code generation")
                return None

            response = await safe_execute(
                self.llm_client.generate,
                prompt,
                max_tokens=self.config.llm_max_tokens,
                temperature=self.config.llm_temperature,
            )

            if not response:
                return None

            # Normalize response to string content
            response_str = ""
            if isinstance(response, dict):
                response_str = str(response.get("content") or response.get("text") or "")
            elif isinstance(response, (list, tuple)):
                response_str = "".join(map(str, response))
            else:
                response_str = str(response)

            # Extract Python code from response
            code = self._extract_code_from_response(response_str)
            
            return code
            
        except Exception as e:
            logger.error(f"Error generating skill code: {e}")
            return None
    
    def _create_generation_prompt(
        self, 
        user_request: str, 
        skill_type: str, 
        context: Dict[str, Any]
    ) -> str:
        """Create a prompt for skill code generation."""
        
        base_template = self._get_skill_template(skill_type)
        
        prompt = f"""
You are an expert Python developer creating a new skill for the HappyOS system.

USER REQUEST: {user_request}
SKILL TYPE: {skill_type}
CONTEXT: {json.dumps(context, indent=2)}

Generate a complete Python skill that fulfills the user's request. The skill must:

1. Follow the exact template structure below
2. Include comprehensive error handling
3. Use proper type hints
4. Include detailed docstring
5. Be production-ready and secure
6. Handle edge cases gracefully

TEMPLATE STRUCTURE:
{base_template}

REQUIREMENTS:
- Function name must be 'execute_skill'
- Must be async
- Must return a dict with 'success', 'result', and 'metadata' keys
- Include proper logging
- Validate all inputs
- Handle all exceptions

Generate ONLY the Python code, no explanations or markdown formatting.
"""
        
        return prompt
    
    def _get_skill_template(self, skill_type: str) -> str:
        """Get the appropriate template for the skill type."""
        
        templates = {
            "web_scraping": '''
import logging
import aiohttp
from typing import Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Web scraping skill template."""
    if context is None:
        context = {}
    
    try:
        # Implementation here
        result = "Web scraping completed"
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_type": "web_scraping",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Web scraping failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {"skill_type": "web_scraping"}
        }
''',
            
            "api_integration": '''
import logging
import aiohttp
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """API integration skill template."""
    if context is None:
        context = {}
    
    try:
        # Implementation here
        result = "API integration completed"
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_type": "api_integration",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"API integration failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {"skill_type": "api_integration"}
        }
''',
            
            "general": '''
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """General skill template."""
    if context is None:
        context = {}
    
    try:
        # Implementation here
        result = "Skill executed successfully"
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_type": "general",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Skill execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {"skill_type": "general"}
        }
'''
        }
        
        return templates.get(skill_type, templates["general"])
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        
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
        if 'def execute_skill' in response and 'import' in response:
            return response.strip()
        
        return None
    
    async def _validate_skill_code(self, skill_code: str) -> bool:
        """Validate the generated skill code."""
        
        try:
            # Basic syntax check
            compile(skill_code, '<string>', 'exec')
            
            # Check for required function
            if 'async def execute_skill' not in skill_code:
                logger.error("Generated skill missing execute_skill function")
                return False
            
            # Check for proper return format
            if 'return {' not in skill_code or '"success"' not in skill_code:
                logger.error("Generated skill has incorrect return format")
                return False
            
            # Check for error handling
            if 'try:' not in skill_code or 'except' not in skill_code:
                logger.error("Generated skill missing error handling")
                return False
            
            return True
            
        except SyntaxError as e:
            logger.error(f"Generated skill has syntax error: {e}")
            return False
        except Exception as e:
            logger.error(f"Skill validation failed: {e}")
            return False
    
    def _generate_skill_name(self, user_request: str) -> str:
        """Generate a unique skill name based on the request."""
        
        import re
        
        # Extract key words from request
        words = re.findall(r'\b\w+\b', user_request.lower())
        key_words = [
            w for w in words
            if len(w) >= self.config.skill_name_min_keyword_length
            and w not in self.config.skill_name_stopwords
        ]
        
        # Take first few words based on config
        name_parts = key_words[:self.config.skill_name_max_parts] if key_words else self.config.skill_name_default_parts
        
        # Create base name
        base_name = '_'.join(name_parts)
        
        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return f"{base_name}_{timestamp}"
    
    async def _save_skill_file(
        self, 
        skill_name: str, 
        skill_code: str, 
        user_request: str
    ) -> Optional[Path]:
        """Save the generated skill to a file."""
        
        try:
            file_path = self.skills_dir / f"{skill_name}.py"
            
            # Create file header
            header = f'''"""
Auto-generated skill: {skill_name}
Generated: {datetime.now().isoformat()}
User request: {user_request}

This skill was automatically generated by the HappyOS self-building system.
"""

'''
            
            # Write file
            full_content = header + skill_code
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            logger.info(f"Saved auto-generated skill to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save skill file: {e}")
            return None
    
    async def _register_skill(self, component: ComponentInfo) -> bool:
        """Register the generated skill in the system."""
        
        try:
            # First, scan the component to ensure it's discovered
            await component_scanner.load_component(component)
            
            # Register in dynamic registry
            success = await dynamic_registry.register_component(component)
            
            if success:
                # Activate the component
                await dynamic_registry.activate_component(component.name)
                logger.info(f"Registered and activated auto-generated skill: {component.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to register skill: {e}")
            return False
    
    def _track_generation(
        self, 
        component: Optional[ComponentInfo], 
        user_request: str, 
        success: bool, 
        error: Optional[str] = None
    ):
        """Track skill generation for analytics."""
        
        self.generation_history.append({
            "timestamp": datetime.now(),
            "user_request": user_request,
            "skill_name": component.name if component else None,
            "success": success,
            "error": error
        })
        
        # Keep only recent history
        if len(self.generation_history) > self.config.generation_history_max_size:
            self.generation_history = self.generation_history[-self.config.generation_history_trim_to_size:]
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get skill generation statistics."""
        
        if not self.generation_history:
            return {"total_generations": 0}
        
        total = len(self.generation_history)
        successful = sum(1 for h in self.generation_history if h["success"])
        
        return {
            "total_generations": total,
            "success_rate": successful / total if total > 0 else 0,
            "recent_generations": self.generation_history[-10:],
            "successful_skills": [
                h["skill_name"] for h in self.generation_history[-20:] 
                if h["success"] and h["skill_name"]
            ]
        }


# Global auto-generator instance
skill_auto_generator = SkillAutoGenerator()


# Convenience function
async def auto_generate_skill(user_request: str, context: Optional[Dict[str, Any]] = None) -> Optional[ComponentInfo]:
    """Auto-generate a skill for a user request."""
    return await skill_auto_generator.generate_skill_for_need(user_request, context or {})