"""
Google GenAI provider implementation for LLM service.

This module provides Google GenAI-specific LLM operations using google.generativeai.
Supports Gemini models (Gemini 1.5 Flash, Gemini 1.5 Pro, etc.).
"""

import logging
import os
from typing import Any, Dict, AsyncIterator, Optional

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("google.generativeai not installed. Google GenAI provider will not be available.")

logger = logging.getLogger(__name__)


class GoogleGenAIProvider:
    """
    Google GenAI provider for LLM operations.
    
    Handles:
    - Completion generation with Gemini models
    - Streaming completions
    - Google GenAI-specific error handling
    - Token usage tracking
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Google GenAI provider.
        
        Args:
            api_key: Google API key. If None, reads from GOOGLE_API_KEY env var.
        """
        if not GENAI_AVAILABLE:
            self.client = None
            self.logger = logger
            self.logger.error("google.generativeai package not available")
            return
        
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            logger.warning("Google API key not provided. Provider will not be functional.")
            self.client = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.client = genai
                self.logger = logger
                self.logger.info("Google GenAI provider initialized")
            except Exception as e:
                self.logger = logger
                self.logger.error(f"Failed to configure Google GenAI: {e}")
                self.client = None
        
        # Model mapping for Google GenAI
        self.model_mapping = {
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-pro": "gemini-pro",
            "gemini-flash": "gemini-1.5-flash",  # Alias
            "gemini": "gemini-1.5-flash",  # Default
        }
    
    def _map_model(self, model: str) -> str:
        """
        Map generic model name to Google GenAI-specific model ID.
        
        Args:
            model: Generic model name
            
        Returns:
            Google GenAI model ID
        """
        return self.model_mapping.get(model, model)
    
    def _extract_token_count(self, response) -> Dict[str, int]:
        """
        Extract token count from response metadata.
        
        Args:
            response: Response from GenAI
            
        Returns:
            Dict with token counts
        """
        try:
            # Try to get usage metadata if available
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                return {
                    "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                    "completion_tokens": getattr(usage, 'candidates_token_count', 0),
                    "total_tokens": getattr(usage, 'total_token_count', 0)
                }
        except Exception as e:
            self.logger.debug(f"Could not extract token count: {e}")
        
        # Return zeros if not available
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    
    async def generate_completion(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate completion using Google GenAI.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Expected response format ("json" or "text")
            
        Returns:
            Dict containing:
                - content: Generated text
                - model: Model used
                - tokens: Token usage
                - finish_reason: Completion finish reason
                
        Raises:
            ValueError: Invalid configuration
            Exception: Google GenAI API error
        """
        if not GENAI_AVAILABLE:
            raise ValueError("google.generativeai package not installed")
        
        if not self.client:
            raise ValueError("Google GenAI client not initialized. Check API key.")
        
        try:
            # Map model name
            genai_model = self._map_model(model)
            
            # Add JSON instruction to prompt if needed
            if response_format == "json":
                prompt = f"{prompt}\n\nPlease respond with valid JSON only."
            
            # Create generation config
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            self.logger.debug(f"Calling Google GenAI with model {genai_model}")
            
            # Create model instance
            model_instance = self.client.GenerativeModel(genai_model)
            
            # Generate content
            response = model_instance.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract response text
            content = response.text if hasattr(response, 'text') else ""
            
            # Extract token usage
            token_counts = self._extract_token_count(response)
            
            # Extract finish reason
            finish_reason = "stop"
            if hasattr(response, 'candidates') and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = str(candidate.finish_reason)
            
            result = {
                "content": content,
                "model": genai_model,
                "tokens": token_counts["total_tokens"],
                "prompt_tokens": token_counts["prompt_tokens"],
                "completion_tokens": token_counts["completion_tokens"],
                "finish_reason": finish_reason
            }
            
            self.logger.debug(
                f"Google GenAI completion successful. Tokens: {result['tokens']}, "
                f"Finish reason: {finish_reason}"
            )
            
            return result
            
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Google GenAI error: {error_message}")
            
            # Handle specific error types
            if "quota" in error_message.lower() or "rate" in error_message.lower():
                raise Exception(f"Google GenAI rate limit exceeded: {error_message}")
            elif "timeout" in error_message.lower():
                raise Exception(f"Google GenAI timeout: {error_message}")
            elif "api key" in error_message.lower() or "authentication" in error_message.lower():
                raise ValueError(f"Google GenAI authentication error: {error_message}")
            else:
                raise Exception(f"Google GenAI error: {error_message}")
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """
        Generate streaming completion using Google GenAI.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
            
        Raises:
            ValueError: Invalid configuration
            Exception: Google GenAI API error
        """
        if not GENAI_AVAILABLE:
            raise ValueError("google.generativeai package not installed")
        
        if not self.client:
            raise ValueError("Google GenAI client not initialized. Check API key.")
        
        try:
            # Map model name
            genai_model = self._map_model(model)
            
            # Create generation config
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            self.logger.debug(f"Starting Google GenAI streaming with model {genai_model}")
            
            # Create model instance
            model_instance = self.client.GenerativeModel(genai_model)
            
            # Generate content with streaming
            response = model_instance.generate_content(
                prompt,
                generation_config=generation_config,
                stream=True
            )
            
            # Yield chunks as they arrive
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
            
            self.logger.debug("Google GenAI streaming completed")
            
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Google GenAI streaming error: {error_message}")
            
            # Handle specific error types
            if "quota" in error_message.lower() or "rate" in error_message.lower():
                raise Exception(f"Google GenAI rate limit exceeded: {error_message}")
            elif "timeout" in error_message.lower():
                raise Exception(f"Google GenAI timeout: {error_message}")
            elif "api key" in error_message.lower() or "authentication" in error_message.lower():
                raise ValueError(f"Google GenAI authentication error: {error_message}")
            else:
                raise Exception(f"Google GenAI streaming error: {error_message}")
    
    def is_available(self) -> bool:
        """
        Check if Google GenAI provider is available.
        
        Returns:
            True if API key is configured and client is initialized
        """
        return GENAI_AVAILABLE and self.client is not None
    
    def get_supported_models(self) -> list:
        """
        Get list of supported model names.
        
        Returns:
            List of supported model identifiers
        """
        return list(self.model_mapping.keys())
