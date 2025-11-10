"""
Code Generator Module

This module provides functionality for generating code using various AI services
and saving it to the appropriate locations.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from pathlib import Path
import json
import re

from app.core.owl import OwlClient
from app.core.camel.camel_client import CamelClient
from app.core.error_handling.retry_manager import retry_with_backoff
from app.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

class CodeType(Enum):
    """Types of code that can be generated."""
    PYTHON_MODULE = "python_module"
    PYTHON_CLASS = "python_class"
    PYTHON_FUNCTION = "python_function"
    JAVASCRIPT_MODULE = "javascript_module"
    JAVASCRIPT_COMPONENT = "javascript_component"
    JAVASCRIPT_FUNCTION = "javascript_function"
    CSS = "css"
    HTML = "html"
    SQL = "sql"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"
    OTHER = "other"

class CodeGenerator:
    """
    Class for generating code using AI services and saving it to the appropriate locations.
    """
    
    def __init__(self, owl_client: Optional[OwlClient] = None, camel_client: Optional[CamelClient] = None):
        """
        Initialize the code generator.
        
        Args:
            owl_client: Optional Owl client instance
            camel_client: Optional CAMEL client instance
        """
        self.owl_client = owl_client or OwlClient()
        self.camel_client = camel_client or CamelClient()
        self.settings = get_settings()
        
        # Define base directories for different types of code
        self.base_dirs = {
            CodeType.PYTHON_MODULE: Path(self.settings.code_generation.python_modules_dir),
            CodeType.PYTHON_CLASS: Path(self.settings.code_generation.python_classes_dir),
            CodeType.PYTHON_FUNCTION: Path(self.settings.code_generation.python_functions_dir),
            CodeType.JAVASCRIPT_MODULE: Path(self.settings.code_generation.javascript_modules_dir),
            CodeType.JAVASCRIPT_COMPONENT: Path(self.settings.code_generation.javascript_components_dir),
            CodeType.JAVASCRIPT_FUNCTION: Path(self.settings.code_generation.javascript_functions_dir),
            CodeType.CSS: Path(self.settings.code_generation.css_dir),
            CodeType.HTML: Path(self.settings.code_generation.html_dir),
            CodeType.SQL: Path(self.settings.code_generation.sql_dir),
            CodeType.YAML: Path(self.settings.code_generation.yaml_dir),
            CodeType.JSON: Path(self.settings.code_generation.json_dir),
            CodeType.MARKDOWN: Path(self.settings.code_generation.markdown_dir),
            CodeType.OTHER: Path(self.settings.code_generation.other_dir),
        }
        
        # Create directories if they don't exist
        for directory in self.base_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)
    
    async def generate_code(
        self,
        prompt: str,
        code_type: Union[CodeType, str],
        filename: Optional[str] = None,
        use_owl: bool = True,
        additional_context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        save_to_file: bool = True,
        validate_code: bool = True
    ) -> Dict[str, Any]:
        """
        Generate code based on a prompt.
        
        Args:
            prompt: The prompt describing the code to generate
            code_type: The type of code to generate
            filename: Optional filename to save the code to
            use_owl: Whether to use Owl for code generation
            additional_context: Additional context for code generation
            max_tokens: Maximum tokens for generation
            temperature: Temperature for generation
            save_to_file: Whether to save the generated code to a file
            validate_code: Whether to validate the generated code
            
        Returns:
            Dictionary containing the generated code and metadata
        """
        # Convert string code type to enum if necessary
        if isinstance(code_type, str):
            try:
                code_type = CodeType(code_type)
            except ValueError:
                code_type = CodeType.OTHER
        
        # Determine language based on code type
        language = self._get_language_from_code_type(code_type)
        
        # Generate code using Owl or CAMEL
        if use_owl and self.owl_client.is_available():
            code_result = await self._generate_code_with_owl(
                prompt=prompt,
                language=language,
                additional_context=additional_context,
                max_tokens=max_tokens,
                temperature=temperature
            )
        else:
            code_result = await self._generate_code_with_camel(
                prompt=prompt,
                language=language,
                additional_context=additional_context,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        # Extract code from result
        code = code_result.get("code", "")
        
        # Validate code if requested
        validation_result = {"valid": True, "errors": []}
        if validate_code and code:
            from .code_validator import CodeValidator
            validator = CodeValidator()
            validation_result = await validator.validate_code(code, code_type)
        
        # Save code to file if requested
        file_path = None
        if save_to_file and code and validation_result["valid"]:
            file_path = await self.save_code_to_file(code, code_type, filename)
        
        # Prepare result
        result = {
            "code": code,
            "code_type": code_type.value,
            "language": language,
            "validation": validation_result,
            "file_path": str(file_path) if file_path else None,
            "metadata": code_result.get("metadata", {})
        }
        
        return result
    
    async def _generate_code_with_owl(
        self,
        prompt: str,
        language: str,
        additional_context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate code using Owl.
        
        Args:
            prompt: The prompt describing the code to generate
            language: The programming language
            additional_context: Additional context for code generation
            max_tokens: Maximum tokens for generation
            temperature: Temperature for generation
            
        Returns:
            Dictionary containing the generated code and metadata
        """
        try:
            # Prepare context
            context = additional_context or {}
            
            # Call Owl API
            response = await retry_with_backoff(
                self.owl_client.generate_code,
                prompt=prompt,
                language=language,
                max_tokens=max_tokens,
                temperature=temperature,
                **context
            )
            
            if response.success:
                return {
                    "code": response.data.get("code", ""),
                    "metadata": {
                        "source": "owl",
                        "model": response.data.get("model", "unknown"),
                        "timestamp": response.timestamp.isoformat() if hasattr(response, "timestamp") else None
                    }
                }
            else:
                logger.error(f"Error generating code with Owl: {response.message}")
                return {"code": "", "metadata": {"error": response.message}}
        except Exception as e:
            logger.error(f"Exception generating code with Owl: {str(e)}")
            return {"code": "", "metadata": {"error": str(e)}}
    
    async def _generate_code_with_camel(
        self,
        prompt: str,
        language: str,
        additional_context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate code using CAMEL.
        
        Args:
            prompt: The prompt describing the code to generate
            language: The programming language
            additional_context: Additional context for code generation
            max_tokens: Maximum tokens for generation
            temperature: Temperature for generation
            
        Returns:
            Dictionary containing the generated code and metadata
        """
        try:
            # Check if CAMEL is available
            if not self.camel_client.is_available():
                logger.warning("CAMEL is not available for code generation")
                return {"code": "", "metadata": {"error": "CAMEL is not available"}}
            
            # Create agents
            user_agent = self.camel_client.create_agent_from_template("user_proxy")
            assistant_agent = self.camel_client.create_agent_from_template("assistant")
            
            if not user_agent or not assistant_agent:
                logger.error("Failed to create CAMEL agents for code generation")
                return {"code": "", "metadata": {"error": "Failed to create CAMEL agents"}}
            
            # Prepare prompt
            code_prompt = f"Generate {language} code for the following task: {prompt}"
            if additional_context:
                context_str = json.dumps(additional_context, indent=2)
                code_prompt += f"\n\nAdditional context:\n{context_str}"
            
            # Run conversation
            messages = await self.camel_client.run_conversation(
                user_agent,
                assistant_agent,
                initial_message=code_prompt,
                max_turns=3
            )
            
            # Extract code from conversation
            code = self._extract_code_from_messages(messages, language)
            
            return {
                "code": code,
                "metadata": {
                    "source": "camel",
                    "model": self.camel_client.config.default_model,
                    "message_count": len(messages)
                }
            }
        except Exception as e:
            logger.error(f"Exception generating code with CAMEL: {str(e)}")
            return {"code": "", "metadata": {"error": str(e)}}
    
    def _extract_code_from_messages(self, messages: List[Dict[str, Any]], language: str) -> str:
        """
        Extract code from CAMEL conversation messages.
        
        Args:
            messages: List of messages from the conversation
            language: The programming language
            
        Returns:
            Extracted code as a string
        """
        # Join all assistant messages
        assistant_messages = [msg["content"] for msg in messages if msg["role"] == "assistant"]
        full_text = "\n".join(assistant_messages)
        
        # Extract code blocks
        code_blocks = []
        
        # Try to extract code blocks with language tag
        pattern = rf"```{language}(.*?)```"
        matches = re.findall(pattern, full_text, re.DOTALL)
        if matches:
            code_blocks.extend(matches)
        
        # Try to extract generic code blocks
        if not code_blocks:
            pattern = r"```(.*?)```"
            matches = re.findall(pattern, full_text, re.DOTALL)
            code_blocks.extend(matches)
        
        # If no code blocks found, try to extract based on indentation
        if not code_blocks:
            lines = full_text.split("\n")
            code_lines = []
            in_code_block = False
            
            for line in lines:
                if line.strip().startswith("def ") or line.strip().startswith("class "):
                    in_code_block = True
                    code_lines.append(line)
                elif in_code_block and line.startswith("    "):
                    code_lines.append(line)
                elif in_code_block and not line.strip():
                    code_lines.append(line)
                elif in_code_block:
                    in_code_block = False
            
            if code_lines:
                code_blocks.append("\n".join(code_lines))
        
        # Return the longest code block
        if code_blocks:
            return max(code_blocks, key=len).strip()
        
        return ""
    
    async def save_code_to_file(
        self,
        code: str,
        code_type: Union[CodeType, str],
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Save generated code to a file.
        
        Args:
            code: The code to save
            code_type: The type of code
            filename: Optional filename to save the code to
            
        Returns:
            Path to the saved file or None if saving failed
        """
        try:
            # Convert string code type to enum if necessary
            if isinstance(code_type, str):
                try:
                    code_type = CodeType(code_type)
                except ValueError:
                    code_type = CodeType.OTHER
            
            # Get base directory for this code type
            base_dir = self.base_dirs[code_type]
            
            # Generate filename if not provided
            if not filename:
                extension = self._get_extension_from_code_type(code_type)
                timestamp = asyncio.get_event_loop().time()
                filename = f"generated_{int(timestamp)}{extension}"
            elif not Path(filename).suffix:
                # Add extension if not present
                extension = self._get_extension_from_code_type(code_type)
                filename = f"{filename}{extension}"
            
            # Create full file path
            file_path = base_dir / filename
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write code to file
            with open(file_path, "w") as f:
                f.write(code)
            
            logger.info(f"Saved generated code to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving code to file: {str(e)}")
            return None
    
    def _get_language_from_code_type(self, code_type: CodeType) -> str:
        """
        Get the programming language from the code type.
        
        Args:
            code_type: The type of code
            
        Returns:
            The programming language as a string
        """
        language_map = {
            CodeType.PYTHON_MODULE: "python",
            CodeType.PYTHON_CLASS: "python",
            CodeType.PYTHON_FUNCTION: "python",
            CodeType.JAVASCRIPT_MODULE: "javascript",
            CodeType.JAVASCRIPT_COMPONENT: "javascript",
            CodeType.JAVASCRIPT_FUNCTION: "javascript",
            CodeType.CSS: "css",
            CodeType.HTML: "html",
            CodeType.SQL: "sql",
            CodeType.YAML: "yaml",
            CodeType.JSON: "json",
            CodeType.MARKDOWN: "markdown",
        }
        
        return language_map.get(code_type, "text")
    
    def _get_extension_from_code_type(self, code_type: CodeType) -> str:
        """
        Get the file extension from the code type.
        
        Args:
            code_type: The type of code
            
        Returns:
            The file extension as a string
        """
        extension_map = {
            CodeType.PYTHON_MODULE: ".py",
            CodeType.PYTHON_CLASS: ".py",
            CodeType.PYTHON_FUNCTION: ".py",
            CodeType.JAVASCRIPT_MODULE: ".js",
            CodeType.JAVASCRIPT_COMPONENT: ".jsx",
            CodeType.JAVASCRIPT_FUNCTION: ".js",
            CodeType.CSS: ".css",
            CodeType.HTML: ".html",
            CodeType.SQL: ".sql",
            CodeType.YAML: ".yaml",
            CodeType.JSON: ".json",
            CodeType.MARKDOWN: ".md",
        }
        
        return extension_map.get(code_type, ".txt")