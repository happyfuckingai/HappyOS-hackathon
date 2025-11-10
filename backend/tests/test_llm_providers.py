"""
Unit tests for LLM provider implementations.

Tests:
- OpenAIProvider with mock AsyncOpenAI
- BedrockProvider with mock boto3 client
- GoogleGenAIProvider with mock genai client
- Error handling for each provider
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

# Add backend to path for absolute imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Import the providers to test
from backend.core.llm.providers.openai_provider import OpenAIProvider
from backend.core.llm.providers.bedrock_provider import BedrockProvider
from backend.core.llm.providers.google_genai_provider import GoogleGenAIProvider


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""
    
    @pytest.mark.asyncio
    async def test_initialization_with_api_key(self):
        """Test provider initialization with API key."""
        provider = OpenAIProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.client is not None
        assert provider.is_available()
    
    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider()
            
            assert provider.client is None
            assert not provider.is_available()
    
    @pytest.mark.asyncio
    async def test_model_mapping(self):
        """Test model name mapping."""
        provider = OpenAIProvider(api_key="test-key")
        
        assert provider._map_model("gpt-4") == "gpt-4"
        assert provider._map_model("gpt-4-turbo") == "gpt-4-turbo-preview"
        assert provider._map_model("gpt-3.5") == "gpt-3.5-turbo"
        assert provider._map_model("unknown-model") == "unknown-model"
    
    @pytest.mark.asyncio
    async def test_generate_completion_success(self):
        """Test successful completion generation."""
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock the AsyncOpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            result = await provider.generate_completion(
                prompt="Test prompt",
                model="gpt-4",
                temperature=0.3,
                max_tokens=500,
                response_format="json"
            )
            
            assert result["content"] == "Test response"
            assert result["model"] == "gpt-4"
            assert result["tokens"] == 100
            assert result["prompt_tokens"] == 50
            assert result["completion_tokens"] == 50
            assert result["finish_reason"] == "stop"
            
            # Verify API was called with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["model"] == "gpt-4"
            assert call_kwargs["temperature"] == 0.3
            assert call_kwargs["max_tokens"] == 500
            assert call_kwargs["response_format"] == {"type": "json_object"}
    
    @pytest.mark.asyncio
    async def test_generate_completion_text_format(self):
        """Test completion generation with text format."""
        provider = OpenAIProvider(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            result = await provider.generate_completion(
                prompt="Test prompt",
                model="gpt-4",
                temperature=0.3,
                max_tokens=500,
                response_format="text"
            )
            
            # Verify response_format was not added for text
            call_kwargs = mock_create.call_args[1]
            assert "response_format" not in call_kwargs
    
    @pytest.mark.asyncio
    async def test_generate_completion_without_client(self):
        """Test completion generation without initialized client."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider()
            
            with pytest.raises(ValueError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                )
            
            assert "not initialized" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_completion_rate_limit_error(self):
        """Test handling of rate limit errors."""
        from openai import RateLimitError
        
        provider = OpenAIProvider(api_key="test-key")
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(),
                body=None
            )
            
            with pytest.raises(RateLimitError):
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                )
    
    @pytest.mark.asyncio
    async def test_generate_completion_timeout_error(self):
        """Test handling of timeout errors."""
        from openai import APITimeoutError
        
        provider = OpenAIProvider(api_key="test-key")
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = APITimeoutError(request=MagicMock())
            
            with pytest.raises(APITimeoutError):
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                )
    
    @pytest.mark.asyncio
    async def test_generate_completion_connection_error(self):
        """Test handling of connection errors."""
        from openai import APIConnectionError
        
        provider = OpenAIProvider(api_key="test-key")
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = APIConnectionError(request=MagicMock())
            
            with pytest.raises(APIConnectionError):
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                )
    
    @pytest.mark.asyncio
    async def test_generate_completion_api_error(self):
        """Test handling of general API errors."""
        from openai import APIError
        
        provider = OpenAIProvider(api_key="test-key")
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = APIError(
                message="API error",
                request=MagicMock(),
                body=None
            )
            
            with pytest.raises(APIError):
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                )
    
    @pytest.mark.asyncio
    async def test_generate_streaming_completion_success(self):
        """Test successful streaming completion."""
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock streaming response
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
            ]
            for chunk in chunks:
                yield chunk
        
        with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_stream()
            
            result_chunks = []
            async for chunk in provider.generate_streaming_completion(
                prompt="Test prompt",
                model="gpt-4"
            ):
                result_chunks.append(chunk)
            
            assert result_chunks == ["Hello", " world", "!"]
    
    @pytest.mark.asyncio
    async def test_generate_streaming_completion_without_client(self):
        """Test streaming completion without initialized client."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider()
            
            with pytest.raises(ValueError) as exc_info:
                async for _ in provider.generate_streaming_completion(
                    prompt="Test prompt",
                    model="gpt-4"
                ):
                    pass
            
            assert "not initialized" in str(exc_info.value)



class TestBedrockProvider:
    """Test suite for BedrockProvider."""
    
    @pytest.mark.asyncio
    async def test_initialization_success(self):
        """Test provider initialization with AWS credentials."""
        with patch('boto3.client') as mock_boto_client:
            mock_boto_client.return_value = MagicMock()
            
            provider = BedrockProvider(
                region_name="us-east-1",
                aws_access_key_id="test-key",
                aws_secret_access_key="test-secret"
            )
            
            assert provider.client is not None
            assert provider.region_name == "us-east-1"
            assert provider.is_available()
            
            # Verify boto3 client was created with correct parameters
            mock_boto_client.assert_called_once()
            call_kwargs = mock_boto_client.call_args[1]
            assert call_kwargs["region_name"] == "us-east-1"
            assert call_kwargs["aws_access_key_id"] == "test-key"
            assert call_kwargs["aws_secret_access_key"] == "test-secret"
    
    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Test provider initialization failure."""
        with patch('boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = Exception("AWS error")
            
            provider = BedrockProvider()
            
            assert provider.client is None
            assert not provider.is_available()
    
    @pytest.mark.asyncio
    async def test_model_mapping(self):
        """Test model name mapping."""
        with patch('boto3.client'):
            provider = BedrockProvider()
            
            assert provider._map_model("claude-3-sonnet") == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert provider._map_model("claude-3-haiku") == "anthropic.claude-3-haiku-20240307-v1:0"
            assert provider._map_model("claude") == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert provider._map_model("unknown-model") == "unknown-model"
    
    @pytest.mark.asyncio
    async def test_prepare_claude_request(self):
        """Test Claude request preparation."""
        with patch('boto3.client'):
            provider = BedrockProvider()
            
            request = provider._prepare_claude_request(
                prompt="Test prompt",
                temperature=0.5,
                max_tokens=1000
            )
            
            assert request["anthropic_version"] == "bedrock-2023-05-31"
            assert request["max_tokens"] == 1000
            assert request["temperature"] == 0.5
            assert len(request["messages"]) == 1
            assert request["messages"][0]["role"] == "user"
            assert request["messages"][0]["content"] == "Test prompt"
    
    @pytest.mark.asyncio
    async def test_extract_claude_response(self):
        """Test Claude response extraction."""
        with patch('boto3.client'):
            provider = BedrockProvider()
            
            response_body = {
                "content": [{"text": "Test response"}],
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 30
                },
                "stop_reason": "end_turn"
            }
            
            result = provider._extract_claude_response(response_body)
            
            assert result["content"] == "Test response"
            assert result["tokens"] == 80
            assert result["prompt_tokens"] == 50
            assert result["completion_tokens"] == 30
            assert result["finish_reason"] == "end_turn"
    
    @pytest.mark.asyncio
    async def test_generate_completion_success(self):
        """Test successful completion generation."""
        with patch('boto3.client') as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            
            # Mock Bedrock response
            mock_response = {
                'body': MagicMock()
            }
            response_body = {
                "content": [{"text": "Test response"}],
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 30
                },
                "stop_reason": "end_turn"
            }
            mock_response['body'].read.return_value = '{"content": [{"text": "Test response"}], "usage": {"input_tokens": 50, "output_tokens": 30}, "stop_reason": "end_turn"}'
            mock_client.invoke_model.return_value = mock_response
            
            provider = BedrockProvider()
            
            result = await provider.generate_completion(
                prompt="Test prompt",
                model="claude-3-sonnet",
                temperature=0.3,
                max_tokens=500,
                response_format="json"
            )
            
            assert result["content"] == "Test response"
            assert result["model"] == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert result["tokens"] == 80
            assert result["prompt_tokens"] == 50
            assert result["completion_tokens"] == 30
    
    @pytest.mark.asyncio
    async def test_generate_completion_without_client(self):
        """Test completion generation without initialized client."""
        with patch('boto3.client') as mock_boto_client:
            mock_boto_client.side_effect = Exception("AWS error")
            
            provider = BedrockProvider()
            
            with pytest.raises(ValueError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="claude-3-sonnet"
                )
            
            assert "not initialized" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_completion_throttling_error(self):
        """Test handling of throttling errors."""
        from botocore.exceptions import ClientError
        
        with patch('boto3.client') as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            
            error_response = {
                'Error': {
                    'Code': 'ThrottlingException',
                    'Message': 'Rate exceeded'
                }
            }
            mock_client.invoke_model.side_effect = ClientError(error_response, 'invoke_model')
            
            provider = BedrockProvider()
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="claude-3-sonnet"
                )
            
            assert "rate limit exceeded" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_completion_timeout_error(self):
        """Test handling of timeout errors."""
        from botocore.exceptions import ClientError
        
        with patch('boto3.client') as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            
            error_response = {
                'Error': {
                    'Code': 'ModelTimeoutException',
                    'Message': 'Model timeout'
                }
            }
            mock_client.invoke_model.side_effect = ClientError(error_response, 'invoke_model')
            
            provider = BedrockProvider()
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="claude-3-sonnet"
                )
            
            assert "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_completion_validation_error(self):
        """Test handling of validation errors."""
        from botocore.exceptions import ClientError
        
        with patch('boto3.client') as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            
            error_response = {
                'Error': {
                    'Code': 'ValidationException',
                    'Message': 'Invalid request'
                }
            }
            mock_client.invoke_model.side_effect = ClientError(error_response, 'invoke_model')
            
            provider = BedrockProvider()
            
            with pytest.raises(ValueError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="claude-3-sonnet"
                )
            
            assert "validation error" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_streaming_completion_not_implemented(self):
        """Test that streaming is not yet implemented."""
        with patch('boto3.client'):
            provider = BedrockProvider()
            
            # The method raises NotImplementedError immediately when called
            with pytest.raises(NotImplementedError) as exc_info:
                await provider.generate_streaming_completion(
                    prompt="Test prompt",
                    model="claude-3-sonnet"
                )
            
            assert "not yet supported" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_supported_models(self):
        """Test getting supported models list."""
        with patch('boto3.client'):
            provider = BedrockProvider()
            
            models = provider.get_supported_models()
            
            assert "claude-3-sonnet" in models
            assert "claude-3-haiku" in models
            assert "claude-3-opus" in models
            assert "claude" in models



class TestGoogleGenAIProvider:
    """Test suite for GoogleGenAIProvider."""
    
    @pytest.mark.asyncio
    async def test_initialization_with_api_key(self):
        """Test provider initialization with API key."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                assert provider.api_key == "test-key"
                assert provider.client is not None
                assert provider.is_available()
                
                # Verify genai.configure was called
                mock_genai.configure.assert_called_once_with(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch.dict(os.environ, {}, clear=True):
                with patch('backend.core.llm.providers.google_genai_provider.genai'):
                    provider = GoogleGenAIProvider()
                    
                    assert provider.client is None
                    assert not provider.is_available()
    
    @pytest.mark.asyncio
    async def test_initialization_genai_not_available(self):
        """Test provider initialization when genai package not available."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', False):
            provider = GoogleGenAIProvider(api_key="test-key")
            
            assert provider.client is None
            assert not provider.is_available()
    
    @pytest.mark.asyncio
    async def test_model_mapping(self):
        """Test model name mapping."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai'):
                provider = GoogleGenAIProvider(api_key="test-key")
                
                assert provider._map_model("gemini-1.5-flash") == "gemini-1.5-flash"
                assert provider._map_model("gemini-1.5-pro") == "gemini-1.5-pro"
                assert provider._map_model("gemini-flash") == "gemini-1.5-flash"
                assert provider._map_model("gemini") == "gemini-1.5-flash"
                assert provider._map_model("unknown-model") == "unknown-model"
    
    @pytest.mark.asyncio
    async def test_extract_token_count_with_metadata(self):
        """Test token count extraction with usage metadata."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai'):
                provider = GoogleGenAIProvider(api_key="test-key")
                
                # Mock response with usage metadata
                mock_response = MagicMock()
                mock_response.usage_metadata = MagicMock()
                mock_response.usage_metadata.prompt_token_count = 50
                mock_response.usage_metadata.candidates_token_count = 30
                mock_response.usage_metadata.total_token_count = 80
                
                result = provider._extract_token_count(mock_response)
                
                assert result["prompt_tokens"] == 50
                assert result["completion_tokens"] == 30
                assert result["total_tokens"] == 80
    
    @pytest.mark.asyncio
    async def test_extract_token_count_without_metadata(self):
        """Test token count extraction without usage metadata."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai'):
                provider = GoogleGenAIProvider(api_key="test-key")
                
                # Mock response without usage metadata
                mock_response = MagicMock()
                del mock_response.usage_metadata
                
                result = provider._extract_token_count(mock_response)
                
                assert result["prompt_tokens"] == 0
                assert result["completion_tokens"] == 0
                assert result["total_tokens"] == 0
    
    @pytest.mark.asyncio
    async def test_generate_completion_success(self):
        """Test successful completion generation."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                # Mock model and response
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                
                mock_response = MagicMock()
                mock_response.text = "Test response"
                mock_response.usage_metadata = MagicMock()
                mock_response.usage_metadata.prompt_token_count = 50
                mock_response.usage_metadata.candidates_token_count = 30
                mock_response.usage_metadata.total_token_count = 80
                mock_response.candidates = [MagicMock()]
                mock_response.candidates[0].finish_reason = "STOP"
                
                mock_model.generate_content.return_value = mock_response
                
                result = await provider.generate_completion(
                    prompt="Test prompt",
                    model="gemini-1.5-flash",
                    temperature=0.3,
                    max_tokens=500,
                    response_format="json"
                )
                
                assert result["content"] == "Test response"
                assert result["model"] == "gemini-1.5-flash"
                assert result["tokens"] == 80
                assert result["prompt_tokens"] == 50
                assert result["completion_tokens"] == 30
                assert "STOP" in result["finish_reason"]
    
    @pytest.mark.asyncio
    async def test_generate_completion_without_genai(self):
        """Test completion generation when genai not available."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', False):
            provider = GoogleGenAIProvider(api_key="test-key")
            
            with pytest.raises(ValueError) as exc_info:
                await provider.generate_completion(
                    prompt="Test prompt",
                    model="gemini-1.5-flash"
                )
            
            assert "not installed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_completion_without_client(self):
        """Test completion generation without initialized client."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch.dict(os.environ, {}, clear=True):
                with patch('backend.core.llm.providers.google_genai_provider.genai'):
                    provider = GoogleGenAIProvider()
                    
                    with pytest.raises(ValueError) as exc_info:
                        await provider.generate_completion(
                            prompt="Test prompt",
                            model="gemini-1.5-flash"
                        )
                    
                    assert "not initialized" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_completion_rate_limit_error(self):
        """Test handling of rate limit errors."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                mock_model.generate_content.side_effect = Exception("Rate limit exceeded")
                
                with pytest.raises(Exception) as exc_info:
                    await provider.generate_completion(
                        prompt="Test prompt",
                        model="gemini-1.5-flash"
                    )
                
                assert "rate limit exceeded" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_completion_timeout_error(self):
        """Test handling of timeout errors."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                mock_model.generate_content.side_effect = Exception("Request timeout")
                
                with pytest.raises(Exception) as exc_info:
                    await provider.generate_completion(
                        prompt="Test prompt",
                        model="gemini-1.5-flash"
                    )
                
                assert "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_completion_authentication_error(self):
        """Test handling of authentication errors."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                mock_model.generate_content.side_effect = Exception("Invalid API key")
                
                with pytest.raises(ValueError) as exc_info:
                    await provider.generate_completion(
                        prompt="Test prompt",
                        model="gemini-1.5-flash"
                    )
                
                assert "authentication error" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_generate_streaming_completion_success(self):
        """Test successful streaming completion."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai') as mock_genai:
                provider = GoogleGenAIProvider(api_key="test-key")
                
                # Mock model and streaming response
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                
                # Create mock chunks
                mock_chunks = [
                    MagicMock(text="Hello"),
                    MagicMock(text=" world"),
                    MagicMock(text="!"),
                ]
                mock_model.generate_content.return_value = iter(mock_chunks)
                
                result_chunks = []
                async for chunk in provider.generate_streaming_completion(
                    prompt="Test prompt",
                    model="gemini-1.5-flash"
                ):
                    result_chunks.append(chunk)
                
                assert result_chunks == ["Hello", " world", "!"]
    
    @pytest.mark.asyncio
    async def test_generate_streaming_completion_without_client(self):
        """Test streaming completion without initialized client."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch.dict(os.environ, {}, clear=True):
                with patch('backend.core.llm.providers.google_genai_provider.genai'):
                    provider = GoogleGenAIProvider()
                    
                    with pytest.raises(ValueError) as exc_info:
                        async for _ in provider.generate_streaming_completion(
                            prompt="Test prompt",
                            model="gemini-1.5-flash"
                        ):
                            pass
                    
                    assert "not initialized" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_supported_models(self):
        """Test getting supported models list."""
        with patch('backend.core.llm.providers.google_genai_provider.GENAI_AVAILABLE', True):
            with patch('backend.core.llm.providers.google_genai_provider.genai'):
                provider = GoogleGenAIProvider(api_key="test-key")
                
                models = provider.get_supported_models()
                
                assert "gemini-1.5-flash" in models
                assert "gemini-1.5-pro" in models
                assert "gemini-pro" in models
                assert "gemini" in models


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
