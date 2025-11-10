"""
Skill generation prompts.
Separated from generator for clean architecture.
"""

from typing import Dict, Any, List


class SkillPrompts:
    """Manages prompts for skill generation."""
    
    def __init__(self):
        self.base_prompts = self._load_base_prompts()
        self.template_prompts = self._load_template_prompts()
    
    def get_skill_generation_prompt(
        self, 
        intent: str, 
        user_request: str, 
        context: Dict[str, Any],
        existing_skills: List[str] = None
    ) -> str:
        """Get prompt for generating a new skill."""
        
        if existing_skills is None:
            existing_skills = []
        
        return f"""
{self.base_prompts['skill_generation']}

USER REQUEST: {user_request}
INTENT: {intent}
CONTEXT: {context}

EXISTING SKILLS: {', '.join(existing_skills) if existing_skills else 'None'}

{self.base_prompts['skill_requirements']}

{self.base_prompts['skill_template']}
"""
    
    def get_skill_validation_prompt(self, skill_code: str, intent: str) -> str:
        """Get prompt for validating generated skill."""
        
        return f"""
{self.base_prompts['skill_validation']}

SKILL CODE:
```python
{skill_code}
```

INTENDED PURPOSE: {intent}

{self.base_prompts['validation_criteria']}
"""
    
    def get_skill_improvement_prompt(
        self, 
        skill_code: str, 
        error_message: str, 
        intent: str
    ) -> str:
        """Get prompt for improving a skill that failed."""
        
        return f"""
{self.base_prompts['skill_improvement']}

ORIGINAL SKILL CODE:
```python
{skill_code}
```

ERROR MESSAGE: {error_message}
INTENDED PURPOSE: {intent}

{self.base_prompts['improvement_guidelines']}
"""
    
    def get_skill_documentation_prompt(self, skill_code: str, skill_name: str) -> str:
        """Get prompt for generating skill documentation."""
        
        return f"""
{self.base_prompts['skill_documentation']}

SKILL NAME: {skill_name}
SKILL CODE:
```python
{skill_code}
```

{self.base_prompts['documentation_format']}
"""
    
    def _load_base_prompts(self) -> Dict[str, str]:
        """Load base prompts for skill generation."""
        
        return {
            "skill_generation": """
You are an expert Python developer creating a new skill for the HappyOS system.
Generate clean, efficient, and well-documented Python code that fulfills the user's request.
""",
            
            "skill_requirements": """
REQUIREMENTS:
1. Create a single Python function that handles the request
2. Use type hints for all parameters and return values
3. Include comprehensive error handling
4. Add detailed docstring explaining the function
5. Import only necessary modules
6. Make the code production-ready and secure
7. Follow Python best practices and PEP 8
8. Handle edge cases gracefully
""",
            
            "skill_template": """
TEMPLATE STRUCTURE:
```python
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

async def execute_skill(request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    \"\"\"
    [Detailed description of what this skill does]
    
    Args:
        request: The user's request string
        context: Additional context information
        
    Returns:
        Dict containing the result and metadata
        
    Raises:
        Exception: When [specific error conditions]
    \"\"\"
    if context is None:
        context = {}
    
    try:
        # Your implementation here
        result = "Your result"
        
        return {
            "success": True,
            "result": result,
            "metadata": {
                "skill_name": "your_skill_name",
                "execution_time": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Skill execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata": {
                "skill_name": "your_skill_name",
                "error_type": type(e).__name__
            }
        }
```

Generate ONLY the Python code, no explanations or markdown.
""",
            
            "skill_validation": """
Validate this generated skill code for correctness, security, and best practices.
Check for:
1. Syntax errors
2. Security vulnerabilities
3. Performance issues
4. Missing error handling
5. Incorrect type hints
6. Missing imports
7. Logic errors
""",
            
            "validation_criteria": """
Respond with JSON:
{
    "valid": true/false,
    "issues": ["list of issues found"],
    "suggestions": ["list of improvement suggestions"],
    "security_score": 0-10,
    "quality_score": 0-10
}
""",
            
            "skill_improvement": """
Improve this skill code to fix the error and enhance its functionality.
Focus on:
1. Fixing the specific error
2. Adding better error handling
3. Improving code quality
4. Enhancing performance
5. Adding missing functionality
""",
            
            "improvement_guidelines": """
Generate the improved Python code following the same template structure.
Make minimal changes to fix the issue while maintaining the original intent.
""",
            
            "skill_documentation": """
Generate comprehensive documentation for this skill including:
1. Purpose and functionality
2. Parameters and return values
3. Usage examples
4. Error conditions
5. Dependencies
""",
            
            "documentation_format": """
Format as markdown:
# Skill Name

## Description
[What the skill does]

## Parameters
- `request` (str): [Description]
- `context` (Dict[str, Any]): [Description]

## Returns
Dict containing:
- `success` (bool): [Description]
- `result` (Any): [Description]
- `metadata` (Dict): [Description]

## Usage Examples
```python
# Example usage
```

## Error Handling
[Description of error conditions]

## Dependencies
[List of required modules]
"""
        }
    
    def _load_template_prompts(self) -> Dict[str, str]:
        """Load template-specific prompts."""
        
        return {
            "web_scraping": """
For web scraping skills, ensure you:
1. Use requests or aiohttp for HTTP requests
2. Add proper headers and user agents
3. Implement rate limiting
4. Handle HTTP errors gracefully
5. Parse HTML with BeautifulSoup or similar
6. Respect robots.txt
""",
            
            "data_processing": """
For data processing skills, ensure you:
1. Validate input data format
2. Handle missing or malformed data
3. Use appropriate data structures
4. Implement efficient algorithms
5. Add progress tracking for large datasets
6. Include data validation
""",
            
            "api_integration": """
For API integration skills, ensure you:
1. Use proper authentication
2. Handle rate limits
3. Implement retry logic
4. Validate API responses
5. Handle API errors gracefully
6. Cache responses when appropriate
""",
            
            "file_operations": """
For file operation skills, ensure you:
1. Validate file paths and permissions
2. Handle file not found errors
3. Use context managers for file operations
4. Support different file formats
5. Implement backup mechanisms
6. Add progress tracking for large files
"""
        }
    
    def get_template_prompt(self, skill_type: str) -> str:
        """Get template-specific prompt for skill type."""
        return self.template_prompts.get(skill_type, "")


# Global prompts instance
skill_prompts = SkillPrompts()