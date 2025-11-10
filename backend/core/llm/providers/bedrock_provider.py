"""
AWS Bedrock provider implementation for LLM service.

This module provides AWS Bedrock-specific LLM operations using boto3.
Supports Claude models (Claude 3 Sonnet, Claude 3 Haiku, etc.).
"""

import logging
import json
import os
from typing import Any, Dict, AsyncIterator, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class BedrockProvider:
    """
    AWS Bedrock provider for LLM operations.
    
    Handles:
    - Completion generation with Claude models
    - Model ID mapping for Bedrock
    - Bedrock-specific error handling
    - Token usage tracking
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize AWS Bedrock provider.
        
        Args:
            region_name: AWS region. If None, reads from AWS_REGION env var.
            aws_access_key_id: AWS access key. If None, uses default credentials.
            aws_secret_access_key: AWS secret key. If None, uses default credentials.
        """
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self.logger = logger
        
        try:
            # Initialize Bedrock runtime client
            client_kwargs = {'region_name': self.region_name}
            
            if aws_access_key_id and aws_secret_access_key:
                client_kwargs['aws_access_key_id'] = aws_access_key_id
                client_kwargs['aws_secret_access_key'] = aws_secret_access_key
            
            self.client = boto3.client('bedrock-runtime', **client_kwargs)
            self.logger.info(f"Bedrock provider initialized in region {self.region_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Bedrock client: {e}")
            self.client = None
        
        # Model mapping for Bedrock Claude models
        self.model_mapping = {
            "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
            "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
            "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
            "claude-3.5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "claude-2": "anthropic.claude-v2",
            "claude-2.1": "anthropic.claude-v2:1",
            "claude": "anthropic.claude-3-sonnet-20240229-v1:0",  # Default
        }
    
    def _map_model(self, model: str) -> str:
        """
        Map generic model name to Bedrock-specific model ID.
        
        Args:
            model: Generic model name
            
        Returns:
            Bedrock model ID
        """
        return self.model_mapping.get(model, model)
    
    def _prepare_claude_request(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        Prepare request body for Claude models.
        
        Args:
            prompt: The prompt text
            temperature: Temperature setting
            max_tokens: Maximum tokens in response
            
        Returns:
            Request body dict
        """
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
    
    def _extract_claude_response(self, response_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from Claude response.
        
        Args:
            response_body: Raw response from Bedrock
            
        Returns:
            Processed response dict
        """
        # Extract content from Claude response
        content = ""
        if "content" in response_body and len(response_body["content"]) > 0:
            content = response_body["content"][0].get("text", "")
        
        # Extract token usage
        usage = response_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        
        # Extract stop reason
        stop_reason = response_body.get("stop_reason", "unknown")
        
        return {
            "content": content,
            "tokens": total_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "finish_reason": stop_reason
        }
    
    async def generate_completion(
        self,
        prompt: str,
        model: str = "claude-3-sonnet",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Generate completion using AWS Bedrock.
        
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
            ClientError: AWS Bedrock API error
            ValueError: Invalid configuration
        """
        if not self.client:
            raise ValueError("Bedrock client not initialized. Check AWS credentials.")
        
        try:
            # Map model name
            bedrock_model_id = self._map_model(model)
            
            # Add JSON instruction to prompt if needed
            if response_format == "json":
                prompt = f"{prompt}\n\nPlease respond with valid JSON only."
            
            # Prepare request body for Claude
            request_body = self._prepare_claude_request(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            self.logger.debug(f"Calling Bedrock with model {bedrock_model_id}")
            
            # Make API call to Bedrock
            response = self.client.invoke_model(
                modelId=bedrock_model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract and format response data
            result = self._extract_claude_response(response_body)
            result["model"] = bedrock_model_id
            
            self.logger.debug(
                f"Bedrock completion successful. Tokens: {result['tokens']}, "
                f"Finish reason: {result['finish_reason']}"
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                f"Bedrock API error [{error_code}]: {error_message}"
            )
            
            # Handle specific error types
            if error_code == 'ThrottlingException':
                raise Exception(f"Bedrock rate limit exceeded: {error_message}")
            elif error_code == 'ModelTimeoutException':
                raise Exception(f"Bedrock model timeout: {error_message}")
            elif error_code == 'ModelNotReadyException':
                raise Exception(f"Bedrock model not ready: {error_message}")
            elif error_code == 'ValidationException':
                raise ValueError(f"Bedrock validation error: {error_message}")
            else:
                raise Exception(f"Bedrock error: {error_message}")
                
        except BotoCoreError as e:
            self.logger.error(f"Bedrock connection error: {e}")
            raise Exception(f"Bedrock connection error: {e}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Bedrock response: {e}")
            raise Exception(f"Invalid Bedrock response format: {e}")
            
        except Exception as e:
            self.logger.error(f"Unexpected error in Bedrock provider: {e}")
            raise
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        model: str = "claude-3-sonnet",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """
        Generate streaming completion using AWS Bedrock.
        
        Note: Bedrock streaming is not yet implemented in this version.
        This method will raise NotImplementedError.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
            
        Raises:
            NotImplementedError: Streaming not yet supported for Bedrock
        """
        # Bedrock streaming requires invoke_model_with_response_stream
        # which has a different API structure. For now, we'll raise NotImplementedError
        # and can implement it in a future iteration if needed.
        
        self.logger.warning("Bedrock streaming not yet implemented")
        raise NotImplementedError(
            "Streaming completion is not yet supported for AWS Bedrock provider. "
            "Use generate_completion instead."
        )
    
    def is_available(self) -> bool:
        """
        Check if Bedrock provider is available.
        
        Returns:
            True if client is initialized and credentials are configured
        """
        return self.client is not None
    
    def get_supported_models(self) -> list:
        """
        Get list of supported model names.
        
        Returns:
            List of supported model identifiers
        """
        return list(self.model_mapping.keys())
