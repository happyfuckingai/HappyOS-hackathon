"""
OpenAI provider implementation for LLM service.

This module provides OpenAI-specific LLM operations using AsyncOpenAI client.
Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.
"""

import logging
import os
from typing import Any, Dict, AsyncIterator, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """
    OpenAI provider for LLM operations.
    
    Handles:
    - Completion generation with GPT models
    - Streaming completions
    - OpenAI-specific error handling
    - Token usage tracking
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            logger.warning("OpenAI API key not provided. Provider will not be functional.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
        
        self.logger = logger
        
        # Model mapping for OpenAI
        self.model_mapping = {
            "gpt-4": "gpt-4",
            "gpt-4-turbo": "gpt-4-turbo-preview",
            "gpt-3.5-turbo": "gpt-3.5-turbo",
            "gpt-3.5": "gpt-3.5-turbo",
        }
    
    def _map_model(self, model: str) -> str:
        """
        Map generic model name to OpenAI-specific model ID.
        
        Args:
            model: Generic model name
            
        Returns:
            OpenAI model ID
        """
        return self.model_mapping.get(model, model)
    
    async def generate_completion(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate completion using OpenAI.
        
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
            APIError: OpenAI API error
            RateLimitError: Rate limit exceeded
            APITimeoutError: Request timeout
            APIConnectionError: Connection error
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized. Check API key.")
        
        try:
            # Map model name
            openai_model = self._map_model(model)
            
            # Prepare request parameters
            request_params = {
                "model": openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Add response format if JSON is requested
            if response_format == "json":
                request_params["response_format"] = {"type": "json_object"}
            
            self.logger.debug(f"Calling OpenAI with model {openai_model}")
            
            # Make API call
            response = await self.client.chat.completions.create(**request_params)
            
            # Extract response data
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            
            # Extract token usage
            tokens_used = response.usage.total_tokens if response.usage else 0
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            result = {
                "content": content,
                "model": response.model,
                "tokens": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": finish_reason
            }
            
            self.logger.debug(
                f"OpenAI completion successful. Tokens: {tokens_used}, "
                f"Finish reason: {finish_reason}"
            )
            
            return result
            
        except RateLimitError as e:
            self.logger.error(f"OpenAI rate limit exceeded: {e}")
            raise
        except APITimeoutError as e:
            self.logger.error(f"OpenAI request timeout: {e}")
            raise
        except APIConnectionError as e:
            self.logger.error(f"OpenAI connection error: {e}")
            raise
        except APIError as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in OpenAI provider: {e}")
            raise
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """
        Generate streaming completion using OpenAI.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
            
        Raises:
            APIError: OpenAI API error
            RateLimitError: Rate limit exceeded
            APITimeoutError: Request timeout
            APIConnectionError: Connection error
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized. Check API key.")
        
        try:
            # Map model name
            openai_model = self._map_model(model)
            
            self.logger.debug(f"Starting OpenAI streaming with model {openai_model}")
            
            # Make streaming API call
            stream = await self.client.chat.completions.create(
                model=openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield content
            
            self.logger.debug("OpenAI streaming completed")
            
        except RateLimitError as e:
            self.logger.error(f"OpenAI rate limit exceeded during streaming: {e}")
            raise
        except APITimeoutError as e:
            self.logger.error(f"OpenAI streaming timeout: {e}")
            raise
        except APIConnectionError as e:
            self.logger.error(f"OpenAI streaming connection error: {e}")
            raise
        except APIError as e:
            self.logger.error(f"OpenAI streaming API error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in OpenAI streaming: {e}")
            raise
    
    def is_available(self) -> bool:
        """
        Check if OpenAI provider is available.
        
        Returns:
            True if API key is configured and client is initialized
        """
        return self.client is not None
