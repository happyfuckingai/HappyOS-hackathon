"""
Code Validator Module

This module provides functionality for validating generated code.
"""

import os
import logging
import asyncio
import tempfile
from typing import Dict, Any, Optional, List, Union
import subprocess
import json
import re
from pathlib import Path

from .code_generator import CodeType

# Configure logging
logger = logging.getLogger(__name__)

class CodeValidator:
    """
    Class for validating generated code.
    """
    
    def __init__(self):
        """Initialize the code validator."""
        # Check for available validation tools
        self.has_pylint = self._check_tool_available("pylint")
        self.has_eslint = self._check_tool_available("eslint")
        self.has_jsonlint = self._check_tool_available("jsonlint")
        self.has_yamllint = self._check_tool_available("yamllint")
        
        logger.info(f"Code validator initialized with tools: "
                   f"pylint={self.has_pylint}, "
                   f"eslint={self.has_eslint}, "
                   f"jsonlint={self.has_jsonlint}, "
                   f"yamllint={self.has_yamllint}")
    
    async def validate_code(
        self,
        code: str,
        code_type: Union[CodeType, str],
        strict: bool = False
    ) -> Dict[str, Any]:
        """
        Validate code.
        
        Args:
            code: The code to validate
            code_type: The type of code
            strict: Whether to use strict validation
            
        Returns:
            Dictionary containing validation results
        """
        # Convert string code type to enum if necessary
        if isinstance(code_type, str):
            try:
                code_type = CodeType(code_type)
            except ValueError:
                code_type = CodeType.OTHER
        
        # Select validation method based on code type
        if code_type in [CodeType.PYTHON_MODULE, CodeType.PYTHON_CLASS, CodeType.PYTHON_FUNCTION]:
            return await self.validate_python(code, strict)
        elif code_type in [CodeType.JAVASCRIPT_MODULE, CodeType.JAVASCRIPT_COMPONENT, CodeType.JAVASCRIPT_FUNCTION]:
            return await self.validate_javascript(code, strict)
        elif code_type == CodeType.JSON:
            return await self.validate_json(code)
        elif code_type == CodeType.YAML:
            return await self.validate_yaml(code)
        elif code_type == CodeType.CSS:
            return await self.validate_css(code)
        elif code_type == CodeType.HTML:
            return await self.validate_html(code)
        elif code_type == CodeType.SQL:
            return await self.validate_sql(code)
        else:
            # For other types, just check for basic syntax
            return await self.validate_basic_syntax(code)
    
    async def validate_python(self, code: str, strict: bool = False) -> Dict[str, Any]:
        """
        Validate Python code.
        
        Args:
            code: The Python code to validate
            strict: Whether to use strict validation (pylint)
            
        Returns:
            Dictionary containing validation results
        """
        # First, check for basic syntax errors
        syntax_result = await self._check_python_syntax(code)
        
        if not syntax_result["valid"]:
            return syntax_result
        
        # If strict validation is requested and pylint is available, use it
        if strict and self.has_pylint:
            return await self._run_pylint(code)
        
        return syntax_result
    
    async def _check_python_syntax(self, code: str) -> Dict[str, Any]:
        """
        Check Python code for syntax errors.
        
        Args:
            code: The Python code to check
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Try to compile the code to check for syntax errors
            compile(code, "<string>", "exec")
            return {"valid": True, "errors": []}
        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [{
                    "line": e.lineno,
                    "column": e.offset,
                    "message": str(e),
                    "severity": "error"
                }]
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [{
                    "line": 0,
                    "column": 0,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def _run_pylint(self, code: str) -> Dict[str, Any]:
        """
        Run pylint on Python code.
        
        Args:
            code: The Python code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                temp_file.write(code.encode())
                temp_path = temp_file.name
            
            # Run pylint
            process = await asyncio.create_subprocess_exec(
                "pylint", "--output-format=json", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            # Parse pylint output
            if stdout:
                try:
                    pylint_results = json.loads(stdout.decode())
                    
                    # Convert pylint results to our format
                    errors = []
                    for result in pylint_results:
                        errors.append({
                            "line": result.get("line", 0),
                            "column": result.get("column", 0),
                            "message": result.get("message", ""),
                            "severity": self._map_pylint_severity(result.get("type", ""))
                        })
                    
                    # Determine if code is valid (no errors)
                    valid = not any(error["severity"] == "error" for error in errors)
                    
                    return {"valid": valid, "errors": errors}
                except json.JSONDecodeError:
                    logger.error(f"Error parsing pylint output: {stdout.decode()}")
            
            # If we couldn't parse pylint output, fall back to basic syntax check
            return await self._check_python_syntax(code)
        except Exception as e:
            logger.error(f"Error running pylint: {str(e)}")
            return await self._check_python_syntax(code)
    
    def _map_pylint_severity(self, pylint_type: str) -> str:
        """
        Map pylint message type to severity.
        
        Args:
            pylint_type: The pylint message type
            
        Returns:
            Severity as a string
        """
        severity_map = {
            "fatal": "error",
            "error": "error",
            "warning": "warning",
            "convention": "info",
            "refactor": "info",
            "info": "info"
        }
        
        return severity_map.get(pylint_type.lower(), "info")
    
    async def validate_javascript(self, code: str, strict: bool = False) -> Dict[str, Any]:
        """
        Validate JavaScript code.
        
        Args:
            code: The JavaScript code to validate
            strict: Whether to use strict validation (eslint)
            
        Returns:
            Dictionary containing validation results
        """
        # First, check for basic syntax errors
        syntax_result = await self._check_javascript_syntax(code)
        
        if not syntax_result["valid"]:
            return syntax_result
        
        # If strict validation is requested and eslint is available, use it
        if strict and self.has_eslint:
            return await self._run_eslint(code)
        
        return syntax_result
    
    async def _check_javascript_syntax(self, code: str) -> Dict[str, Any]:
        """
        Check JavaScript code for syntax errors.
        
        Args:
            code: The JavaScript code to check
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as temp_file:
                temp_file.write(code.encode())
                temp_path = temp_file.name
            
            # Run node to check syntax
            process = await asyncio.create_subprocess_exec(
                "node", "--check", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            # Check for syntax errors
            if process.returncode != 0:
                # Parse error message
                error_msg = stderr.decode()
                line_match = re.search(r"line (\d+)", error_msg)
                column_match = re.search(r"column (\d+)", error_msg)
                
                line = int(line_match.group(1)) if line_match else 0
                column = int(column_match.group(1)) if column_match else 0
                
                return {
                    "valid": False,
                    "errors": [{
                        "line": line,
                        "column": column,
                        "message": error_msg,
                        "severity": "error"
                    }]
                }
            
            return {"valid": True, "errors": []}
        except Exception as e:
            logger.error(f"Error checking JavaScript syntax: {str(e)}")
            return {
                "valid": False,
                "errors": [{
                    "line": 0,
                    "column": 0,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def _run_eslint(self, code: str) -> Dict[str, Any]:
        """
        Run eslint on JavaScript code.
        
        Args:
            code: The JavaScript code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as temp_file:
                temp_file.write(code.encode())
                temp_path = temp_file.name
            
            # Run eslint
            process = await asyncio.create_subprocess_exec(
                "eslint", "--format=json", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            # Parse eslint output
            if stdout:
                try:
                    eslint_results = json.loads(stdout.decode())
                    
                    # Convert eslint results to our format
                    errors = []
                    for file_result in eslint_results:
                        for message in file_result.get("messages", []):
                            errors.append({
                                "line": message.get("line", 0),
                                "column": message.get("column", 0),
                                "message": message.get("message", ""),
                                "severity": "error" if message.get("severity") == 2 else "warning"
                            })
                    
                    # Determine if code is valid (no errors)
                    valid = not any(error["severity"] == "error" for error in errors)
                    
                    return {"valid": valid, "errors": errors}
                except json.JSONDecodeError:
                    logger.error(f"Error parsing eslint output: {stdout.decode()}")
            
            # If we couldn't parse eslint output, fall back to basic syntax check
            return await self._check_javascript_syntax(code)
        except Exception as e:
            logger.error(f"Error running eslint: {str(e)}")
            return await self._check_javascript_syntax(code)
    
    async def validate_json(self, code: str) -> Dict[str, Any]:
        """
        Validate JSON code.
        
        Args:
            code: The JSON code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Try to parse the JSON
            json.loads(code)
            return {"valid": True, "errors": []}
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "errors": [{
                    "line": e.lineno,
                    "column": e.colno,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def validate_yaml(self, code: str) -> Dict[str, Any]:
        """
        Validate YAML code.
        
        Args:
            code: The YAML code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Try to import PyYAML
            import yaml
            
            # Try to parse the YAML
            yaml.safe_load(code)
            return {"valid": True, "errors": []}
        except ImportError:
            logger.warning("PyYAML not available. Install with: pip install pyyaml")
            return {"valid": True, "errors": []}  # Assume valid if we can't check
        except yaml.YAMLError as e:
            # Extract line and column information if available
            line = e.problem_mark.line + 1 if hasattr(e, "problem_mark") else 0
            column = e.problem_mark.column + 1 if hasattr(e, "problem_mark") else 0
            
            return {
                "valid": False,
                "errors": [{
                    "line": line,
                    "column": column,
                    "message": str(e),
                    "severity": "error"
                }]
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [{
                    "line": 0,
                    "column": 0,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def validate_css(self, code: str) -> Dict[str, Any]:
        """
        Validate CSS code.
        
        Args:
            code: The CSS code to validate
            
        Returns:
            Dictionary containing validation results
        """
        # Basic CSS validation (check for matching braces)
        open_braces = code.count("{")
        close_braces = code.count("}")
        
        if open_braces != close_braces:
            return {
                "valid": False,
                "errors": [{
                    "line": 0,
                    "column": 0,
                    "message": f"Mismatched braces: {open_braces} opening vs {close_braces} closing",
                    "severity": "error"
                }]
            }
        
        return {"valid": True, "errors": []}
    
    async def validate_html(self, code: str) -> Dict[str, Any]:
        """
        Validate HTML code.
        
        Args:
            code: The HTML code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Try to import html5lib
            import html5lib
            
            # Parse HTML
            parser = html5lib.HTMLParser(strict=True)
            parser.parse(code)
            
            return {"valid": True, "errors": []}
        except ImportError:
            logger.warning("html5lib not available. Install with: pip install html5lib")
            return {"valid": True, "errors": []}  # Assume valid if we can't check
        except Exception as e:
            # Extract line and column information if possible
            line_match = re.search(r"line (\d+)", str(e))
            column_match = re.search(r"column (\d+)", str(e))
            
            line = int(line_match.group(1)) if line_match else 0
            column = int(column_match.group(1)) if column_match else 0
            
            return {
                "valid": False,
                "errors": [{
                    "line": line,
                    "column": column,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def validate_sql(self, code: str) -> Dict[str, Any]:
        """
        Validate SQL code.
        
        Args:
            code: The SQL code to validate
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Try to import sqlparse
            import sqlparse
            
            # Parse SQL
            statements = sqlparse.parse(code)
            
            # Check for basic syntax issues
            for statement in statements:
                # Check for unbalanced parentheses
                open_parens = str(statement).count("(")
                close_parens = str(statement).count(")")
                
                if open_parens != close_parens:
                    return {
                        "valid": False,
                        "errors": [{
                            "line": 0,
                            "column": 0,
                            "message": f"Unbalanced parentheses: {open_parens} opening vs {close_parens} closing",
                            "severity": "error"
                        }]
                    }
            
            return {"valid": True, "errors": []}
        except ImportError:
            logger.warning("sqlparse not available. Install with: pip install sqlparse")
            return {"valid": True, "errors": []}  # Assume valid if we can't check
        except Exception as e:
            return {
                "valid": False,
                "errors": [{
                    "line": 0,
                    "column": 0,
                    "message": str(e),
                    "severity": "error"
                }]
            }
    
    async def validate_basic_syntax(self, code: str) -> Dict[str, Any]:
        """
        Perform basic syntax validation.
        
        Args:
            code: The code to validate
            
        Returns:
            Dictionary containing validation results
        """
        # Check for unbalanced brackets and parentheses
        open_parens = code.count("(")
        close_parens = code.count(")")
        open_brackets = code.count("[")
        close_brackets = code.count("]")
        open_braces = code.count("{")
        close_braces = code.count("}")
        
        errors = []
        
        if open_parens != close_parens:
            errors.append({
                "line": 0,
                "column": 0,
                "message": f"Unbalanced parentheses: {open_parens} opening vs {close_parens} closing",
                "severity": "error"
            })
        
        if open_brackets != close_brackets:
            errors.append({
                "line": 0,
                "column": 0,
                "message": f"Unbalanced brackets: {open_brackets} opening vs {close_brackets} closing",
                "severity": "error"
            })
        
        if open_braces != close_braces:
            errors.append({
                "line": 0,
                "column": 0,
                "message": f"Unbalanced braces: {open_braces} opening vs {close_braces} closing",
                "severity": "error"
            })
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    def _check_tool_available(self, tool_name: str) -> bool:
        """
        Check if a validation tool is available.
        
        Args:
            tool_name: The name of the tool
            
        Returns:
            True if the tool is available, False otherwise
        """
        try:
            subprocess.run(
                [tool_name, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False