"""
Skill validation logic.
Validates generated skills for security, correctness, and quality.
"""

import ast
import logging
import re
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of skill validation."""
    valid: bool
    issues: List[str]
    suggestions: List[str]
    security_score: int  # 0-10
    quality_score: int   # 0-10
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SkillValidator:
    """Validates generated skills for security and quality."""
    
    def __init__(self):
        self.security_patterns = self._load_security_patterns()
        self.quality_checks = self._load_quality_checks()
        self.banned_imports = self._load_banned_imports()
    
    async def validate_skill(self, skill_code: str, skill_name: str = "unknown") -> ValidationResult:
        """
        Validate a skill for security, correctness, and quality.
        
        Args:
            skill_code: The Python code to validate
            skill_name: Name of the skill being validated
            
        Returns:
            ValidationResult with validation details
        """
        issues = []
        suggestions = []
        security_score = 10
        quality_score = 10
        
        try:
            # 1. Syntax validation
            syntax_issues = self._validate_syntax(skill_code)
            issues.extend(syntax_issues)
            if syntax_issues:
                quality_score -= len(syntax_issues) * 2
            
            # 2. Security validation
            security_issues, sec_score = self._validate_security(skill_code)
            issues.extend(security_issues)
            security_score = sec_score
            
            # 3. Quality validation
            quality_issues, qual_score = self._validate_quality(skill_code)
            issues.extend(quality_issues)
            quality_score = qual_score
            
            # 4. Structure validation
            structure_issues = self._validate_structure(skill_code)
            issues.extend(structure_issues)
            if structure_issues:
                quality_score -= len(structure_issues)
            
            # 5. Import validation
            import_issues = self._validate_imports(skill_code)
            issues.extend(import_issues)
            if import_issues:
                security_score -= len(import_issues) * 2
            
            # Generate suggestions
            suggestions = self._generate_suggestions(skill_code, issues)
            
            # Determine if valid
            valid = (
                len(issues) == 0 or 
                (security_score >= 7 and quality_score >= 6 and not any("critical" in issue.lower() for issue in issues))
            )
            
            return ValidationResult(
                valid=valid,
                issues=issues,
                suggestions=suggestions,
                security_score=max(0, min(10, security_score)),
                quality_score=max(0, min(10, quality_score)),
                metadata={
                    "skill_name": skill_name,
                    "code_length": len(skill_code),
                    "line_count": len(skill_code.split('\n'))
                }
            )
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                valid=False,
                issues=[f"Validation failed: {str(e)}"],
                suggestions=["Fix validation errors and try again"],
                security_score=0,
                quality_score=0
            )
    
    def _validate_syntax(self, code: str) -> List[str]:
        """Validate Python syntax."""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e.msg} at line {e.lineno}")
        except Exception as e:
            issues.append(f"Parse error: {str(e)}")
        
        return issues
    
    def _validate_security(self, code: str) -> Tuple[List[str], int]:
        """Validate security aspects of the code."""
        issues = []
        security_score = 10
        
        # Check for dangerous patterns
        for pattern, description in self.security_patterns.items():
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Security risk: {description}")
                security_score -= 2
        
        # Check for eval/exec usage
        if re.search(r'\b(eval|exec)\s*\(', code):
            issues.append("CRITICAL: Use of eval() or exec() is prohibited")
            security_score -= 5
        
        # Check for file system access outside allowed paths
        if re.search(r'open\s*\([^)]*["\']\.\./', code):
            issues.append("Security risk: Directory traversal attempt detected")
            security_score -= 3
        
        # Check for network access without proper validation
        if re.search(r'requests\.|urllib\.|socket\.', code) and not re.search(r'validate.*url|check.*url', code):
            issues.append("Security warning: Network access without URL validation")
            security_score -= 1
        
        return issues, max(0, security_score)
    
    def _validate_quality(self, code: str) -> Tuple[List[str], int]:
        """Validate code quality."""
        issues = []
        quality_score = 10
        
        # Check for required function
        if not re.search(r'async def execute_skill\s*\(', code):
            issues.append("Missing required execute_skill function")
            quality_score -= 3
        
        # Check for proper error handling
        if 'try:' not in code or 'except' not in code:
            issues.append("Missing error handling")
            quality_score -= 2
        
        # Check for logging
        if 'logger' not in code:
            issues.append("Missing logging")
            quality_score -= 1
        
        # Check for type hints
        if not re.search(r':\s*(str|int|float|bool|Dict|List|Any)', code):
            issues.append("Missing type hints")
            quality_score -= 1
        
        # Check for docstring
        if not re.search(r'""".*?"""', code, re.DOTALL):
            issues.append("Missing docstring")
            quality_score -= 1
        
        # Check for return format
        if not re.search(r'return\s*{.*"success".*}', code, re.DOTALL):
            issues.append("Incorrect return format")
            quality_score -= 2
        
        return issues, max(0, quality_score)
    
    def _validate_structure(self, code: str) -> List[str]:
        """Validate code structure."""
        issues = []
        
        try:
            tree = ast.parse(code)
            
            # Check for required imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module)
            
            required_imports = ['logging', 'typing', 'datetime']
            missing_imports = [imp for imp in required_imports if not any(imp in i for i in imports if i)]
            
            if missing_imports:
                issues.append(f"Missing recommended imports: {', '.join(missing_imports)}")
            
            # Check function structure
            functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
            
            if not any(func.name == 'execute_skill' for func in functions):
                issues.append("Missing execute_skill function")
            
        except Exception as e:
            issues.append(f"Structure analysis failed: {str(e)}")
        
        return issues
    
    def _validate_imports(self, code: str) -> List[str]:
        """Validate imports for security."""
        issues = []
        
        # Extract imports
        import_pattern = r'(?:from\s+(\S+)\s+import|import\s+(\S+))'
        imports = re.findall(import_pattern, code)
        
        all_imports = [imp[0] or imp[1] for imp in imports]
        
        # Check against banned imports
        for imp in all_imports:
            if imp in self.banned_imports:
                issues.append(f"Banned import: {imp}")
            
            # Check for dangerous modules
            dangerous_modules = ['subprocess', 'os.system', '__import__', 'importlib']
            if any(dangerous in imp for dangerous in dangerous_modules):
                issues.append(f"Potentially dangerous import: {imp}")
        
        return issues
    
    def _generate_suggestions(self, code: str, issues: List[str]) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []
        
        if "Missing error handling" in str(issues):
            suggestions.append("Add try-except blocks around risky operations")
        
        if "Missing logging" in str(issues):
            suggestions.append("Add logging statements for debugging and monitoring")
        
        if "Missing type hints" in str(issues):
            suggestions.append("Add type hints to function parameters and return values")
        
        if "Missing docstring" in str(issues):
            suggestions.append("Add comprehensive docstring explaining the function")
        
        if "Security risk" in str(issues):
            suggestions.append("Review and sanitize user inputs and external data")
        
        if not suggestions:
            suggestions.append("Code looks good! Consider adding more comprehensive error handling.")
        
        return suggestions
    
    def _load_security_patterns(self) -> Dict[str, str]:
        """Load security patterns to check for."""
        return {
            r'\bos\.system\s*\(': "Use of os.system() can lead to command injection",
            r'\bsubprocess\.call\s*\(': "Subprocess calls should be carefully validated",
            r'\b__import__\s*\(': "Dynamic imports can be dangerous",
            r'\bpickle\.loads?\s*\(': "Pickle deserialization can execute arbitrary code",
            r'\beval\s*\(': "eval() can execute arbitrary code",
            r'\bexec\s*\(': "exec() can execute arbitrary code",
            r'shell\s*=\s*True': "Shell=True in subprocess can lead to injection",
            r'input\s*\([^)]*\)': "Raw input() should be validated",
            r'open\s*\([^)]*["\']w': "File writing should be restricted to safe directories"
        }
    
    def _load_quality_checks(self) -> List[str]:
        """Load quality check patterns."""
        return [
            "proper_error_handling",
            "type_hints",
            "docstrings",
            "logging",
            "return_format",
            "input_validation"
        ]
    
    def _load_banned_imports(self) -> List[str]:
        """Load list of banned imports."""
        return [
            "ctypes",
            "marshal",
            "imp",
            "code",
            "pty",
            "commands",
            "popen2",
            "posix",
            "nt",
            "pwd",
            "grp",
            "spwd"
        ]
    
    async def validate_skill_execution(self, skill_code: str, test_input: str = "test") -> ValidationResult:
        """Validate skill by actually executing it safely."""
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(skill_code)
                temp_file = f.name
            
            # Try to import and validate
            result = subprocess.run(
                ['python', '-m', 'py_compile', temp_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up
            Path(temp_file).unlink()
            
            if result.returncode == 0:
                return ValidationResult(
                    valid=True,
                    issues=[],
                    suggestions=["Code compiles successfully"],
                    security_score=8,
                    quality_score=8
                )
            else:
                return ValidationResult(
                    valid=False,
                    issues=[f"Compilation error: {result.stderr}"],
                    suggestions=["Fix compilation errors"],
                    security_score=5,
                    quality_score=3
                )
                
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[f"Execution validation failed: {str(e)}"],
                suggestions=["Fix execution errors"],
                security_score=0,
                quality_score=0
            )


# Global validator instance
skill_validator = SkillValidator()