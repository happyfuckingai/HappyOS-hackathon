import os
import sys
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, ValidationError, model_validator
from dotenv import load_dotenv
import secrets
import hashlib

# Load environment variables from .env file
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_file = os.path.join(backend_dir, '.env')
load_dotenv(env_file)

# Also try loading from current directory
load_dotenv('.env')

# External secret management support
try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False


class SecretManager:
    """Handles secure secret retrieval from various sources"""
    
    def __init__(self):
        self.aws_client = None
        self.vault_client = None
        self._init_external_clients()
    
    def _init_external_clients(self):
        """Initialize external secret management clients"""
        # AWS Secrets Manager
        if AWS_AVAILABLE and os.getenv("AWS_SECRETS_MANAGER_ENABLED", "false").lower() == "true":
            try:
                self.aws_client = boto3.client(
                    'secretsmanager',
                    region_name=os.getenv("AWS_REGION", "us-east-1")
                )
            except Exception as e:
                logging.warning(f"Failed to initialize AWS Secrets Manager: {e}")
        
        # HashiCorp Vault
        if VAULT_AVAILABLE and os.getenv("VAULT_ENABLED", "false").lower() == "true":
            try:
                vault_url = os.getenv("VAULT_URL")
                vault_token = os.getenv("VAULT_TOKEN")
                if vault_url and vault_token:
                    self.vault_client = hvac.Client(url=vault_url, token=vault_token)
            except Exception as e:
                logging.warning(f"Failed to initialize Vault client: {e}")
    
    def get_secret(self, key: str, default: str = None) -> str:
        """
        Get secret from various sources in order of preference:
        1. Environment variables
        2. AWS Secrets Manager
        3. HashiCorp Vault
        4. Default value
        """
        # First try environment variable
        env_value = os.getenv(key)
        if env_value:
            return env_value
        
        # Try AWS Secrets Manager
        if self.aws_client:
            try:
                secret_name = os.getenv(f"{key}_SECRET_NAME", key.lower().replace("_", "-"))
                response = self.aws_client.get_secret_value(SecretId=secret_name)
                return response['SecretString']
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    logging.warning(f"AWS Secrets Manager error for {key}: {e}")
            except Exception as e:
                logging.warning(f"Unexpected error retrieving {key} from AWS: {e}")
        
        # Try HashiCorp Vault
        if self.vault_client:
            try:
                vault_path = os.getenv(f"{key}_VAULT_PATH", f"secret/meetmind/{key.lower()}")
                response = self.vault_client.secrets.kv.v2.read_secret_version(path=vault_path)
                return response['data']['data'].get('value')
            except Exception as e:
                logging.warning(f"Vault error for {key}: {e}")
        
        return default
    
    def validate_secret_strength(self, secret: str, min_length: int = 32) -> List[str]:
        """Validate secret strength and return warnings"""
        warnings = []
        
        if not secret:
            warnings.append("Secret is empty")
            return warnings
        
        if len(secret) < min_length:
            warnings.append(f"Secret should be at least {min_length} characters long")
        
        # Check for common weak patterns
        if secret in ["your-secret-key", "change-me", "password", "secret"]:
            warnings.append("Secret uses a common weak value")
        
        # Check entropy (basic check)
        if len(set(secret)) < len(secret) * 0.5:
            warnings.append("Secret has low entropy (too many repeated characters)")
        
        return warnings


class Settings(BaseSettings):
    """Production-ready settings with secure secret management"""
    
    # Core Application Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8001"))
    BACKEND_DEBUG: bool = os.getenv("BACKEND_DEBUG", "true").lower() == "true"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Configuration validation settings - must be set early
    FAIL_FAST_ON_CONFIG_ERROR: bool = os.getenv("FAIL_FAST_ON_CONFIG_ERROR", "true").lower() == "true"
    VALIDATE_SECRETS_ON_STARTUP: bool = os.getenv("VALIDATE_SECRETS_ON_STARTUP", "true").lower() == "true"
    
    # External Secret Management Configuration
    AWS_SECRETS_MANAGER_ENABLED: bool = os.getenv("AWS_SECRETS_MANAGER_ENABLED", "false").lower() == "true"
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    VAULT_ENABLED: bool = os.getenv("VAULT_ENABLED", "false").lower() == "true"
    VAULT_URL: Optional[str] = os.getenv("VAULT_URL")
    VAULT_TOKEN: Optional[str] = None  # Will be set via SecretManager
    
    # AWS Configuration for DynamoDB and S3
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_DYNAMODB_TABLE_NAME: str = os.getenv("AWS_DYNAMODB_TABLE_NAME", "ui_resources")
    AWS_S3_BUCKET_NAME: Optional[str] = os.getenv("AWS_S3_BUCKET_NAME")
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", "us-east-1")
    
    # Initialize secret manager early
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._secret_manager = SecretManager()
        # Set vault token if needed
        if self.VAULT_ENABLED:
            self.VAULT_TOKEN = self._secret_manager.get_secret("VAULT_TOKEN")
    
    # Authentication Configuration - using secure secret retrieval
    SECRET_KEY: str = ""  # Will be set in model_validator
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
    
    # Rate Limiting Configuration
    AUTH_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "5"))
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("GLOBAL_RATE_LIMIT_PER_MINUTE", "100"))
    
    @model_validator(mode='after')
    def initialize_secrets_and_validate(self):
        """Initialize secret manager and validate configuration after model creation"""
        if not hasattr(self, '_secret_manager'):
            self._secret_manager = SecretManager()
        
        # Set JWT secret key using secure retrieval
        jwt_secret = self._secret_manager.get_secret("JWT_SECRET_KEY") or self._secret_manager.get_secret("SECRET_KEY")
        if not jwt_secret:
            if self.ENVIRONMENT == "production":
                raise ValueError("JWT_SECRET_KEY is required in production")
            # Generate a secure key for development
            jwt_secret = secrets.token_urlsafe(32)
            logging.warning("Generated temporary JWT secret for development. Set JWT_SECRET_KEY in production.")
        
        self.SECRET_KEY = jwt_secret
        
        # Set all other secrets using secure retrieval
        self.QDRANT_API_KEY = self._secret_manager.get_secret("QDRANT_API_KEY", "")
        self.OPENAI_API_KEY = self._secret_manager.get_secret("OPENAI_API_KEY", "")
        self.GOOGLE_AI_API_KEY = self._secret_manager.get_secret("GOOGLE_AI_API_KEY", "")
        self.ANTHROPIC_API_KEY = self._secret_manager.get_secret("ANTHROPIC_API_KEY", "")
        self.DATABRICKS_TOKEN = self._secret_manager.get_secret("DATABRICKS_TOKEN", "")
        self.LIVEKIT_API_KEY = self._secret_manager.get_secret("LIVEKIT_API_KEY", "")
        self.LIVEKIT_API_SECRET = self._secret_manager.get_secret("LIVEKIT_API_SECRET", "")
        self.SUPABASE_ANON_KEY = self._secret_manager.get_secret("SUPABASE_ANON_KEY", "")
        self.SUPABASE_SERVICE_ROLE_KEY = self._secret_manager.get_secret("SUPABASE_SERVICE_ROLE_KEY", "")
        self.REDIS_PASSWORD = self._secret_manager.get_secret("REDIS_PASSWORD", "")
        self.SENTRY_DSN = self._secret_manager.get_secret("SENTRY_DSN", "")
        
        # Validate secret strength if enabled
        if self.VALIDATE_SECRETS_ON_STARTUP:
            self._validate_secret_strength()
        
        return self
    
    def _validate_secret_strength(self):
        """Validate secret strength during initialization"""
        warnings = self._secret_manager.validate_secret_strength(self.SECRET_KEY)
        if warnings:
            for warning in warnings:
                if self.ENVIRONMENT == "production":
                    logging.error(f"JWT_SECRET_KEY validation: {warning}")
                else:
                    logging.warning(f"JWT_SECRET_KEY validation: {warning}")
            
            if self.ENVIRONMENT == "production" and self.FAIL_FAST_ON_CONFIG_ERROR:
                raise ValueError(f"JWT_SECRET_KEY validation failed: {'; '.join(warnings)}")
    
    def get_secret_manager(self) -> SecretManager:
        """Get the secret manager instance"""
        return self._secret_manager
    
    def validate_production_secrets(self) -> List[str]:
        """Validate that production secrets are properly configured"""
        errors = []
        
        # Validate JWT secret
        if hasattr(self, '_secret_manager') and self.SECRET_KEY:
            jwt_warnings = self._secret_manager.validate_secret_strength(self.SECRET_KEY)
            errors.extend([f"JWT_SECRET_KEY: {w}" for w in jwt_warnings])
        
        # Validate API keys if in production
        if self.ENVIRONMENT == "production":
            # Check if AI features are enabled
            if not self.OPENAI_API_KEY and not self.GOOGLE_AI_API_KEY and not self.ANTHROPIC_API_KEY:
                errors.append("At least one AI API key (OpenAI, Google AI, or Anthropic) is required in production")
            
            # Check LiveKit configuration
            if not all([self.LIVEKIT_URL, self.LIVEKIT_API_KEY, self.LIVEKIT_API_SECRET]):
                errors.append("LiveKit configuration is incomplete (URL, API key, and secret required)")
            
            # Check Supabase configuration if URL is provided
            if self.SUPABASE_URL and not all([self.SUPABASE_ANON_KEY, self.SUPABASE_SERVICE_ROLE_KEY]):
                errors.append("Supabase configuration is incomplete (anon key and service role key required)")
            
            # Check database configuration
            if not self.DATABASE_URL or self.DATABASE_URL == "sqlite:///./meetings.db":
                errors.append("Production database should use PostgreSQL instead of SQLite")
        
        return errors

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./meetings.db")

    # Vector Database Configuration
    QDRANT_URL: str = os.getenv("QDRANT_URL", "localhost:6333")
    QDRANT_API_KEY: str = ""  # Will be set in model_validator

    # AI/LLM API Keys - will be set securely in model_validator
    OPENAI_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Databricks Foundation Model API Configuration
    DATABRICKS_TOKEN: str = ""  # Will be set in model_validator
    DATABRICKS_HOST: str = os.getenv("DATABRICKS_HOST", "")
    DATABRICKS_MODEL_ID: str = os.getenv("DATABRICKS_MODEL_ID", "databricks-gpt-oss-20b")

    # MCP Server Configuration
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8002/sse")
    MCP_SERVER_TYPE: str = os.getenv("MCP_SERVER_TYPE", "sse")
    MCP_CONNECTION_TIMEOUT: int = int(os.getenv("MCP_CONNECTION_TIMEOUT", "30"))
    MCP_SSE_READ_TIMEOUT: int = int(os.getenv("MCP_SSE_READ_TIMEOUT", "300"))
    MCP_AUTO_RECONNECT: bool = os.getenv("MCP_AUTO_RECONNECT", "true").lower() == "true"
    MCP_MAX_RECONNECT_ATTEMPTS: int = int(os.getenv("MCP_MAX_RECONNECT_ATTEMPTS", "3"))
    MCP_RECONNECT_DELAY: float = float(os.getenv("MCP_RECONNECT_DELAY", "1.0"))

    # Backend Server Configuration
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8001"))
    BACKEND_DEBUG: bool = os.getenv("BACKEND_DEBUG", "true").lower() == "true"

    # Summarizer UI Server Configuration (Legacy - now integrated)
    SUMMARIZER_UI_HOST: str = os.getenv("SUMMARIZER_UI_HOST", "localhost")
    SUMMARIZER_UI_PORT: int = int(os.getenv("SUMMARIZER_UI_PORT", "8002"))
    SUMMARIZER_UI_DEBUG: bool = os.getenv("SUMMARIZER_UI_DEBUG", "true").lower() == "true"

    # Integrated Summarizer Service Configuration
    SUMMARIZER_ENABLED: bool = os.getenv("SUMMARIZER_ENABLED", "false").lower() == "true"
    SUMMARIZER_MAX_REQUESTS: int = int(os.getenv("SUMMARIZER_MAX_REQUESTS", "10"))
    SUMMARIZER_REQUEST_TIMEOUT: int = int(os.getenv("SUMMARIZER_REQUEST_TIMEOUT", "30"))
    SUMMARIZER_CACHING: bool = os.getenv("SUMMARIZER_CACHING", "true").lower() == "true"
    SUMMARIZER_CACHE_TTL: int = int(os.getenv("SUMMARIZER_CACHE_TTL", "300"))

    # Summarizer Database Configuration
    SUMMARIZER_DB_PATH: str = os.getenv("SUMMARIZER_DB_PATH", "data/summarizer.db")
    SUMMARIZER_DB_CONNECTION_POOL_SIZE: int = int(os.getenv("SUMMARIZER_DB_CONNECTION_POOL_SIZE", "5"))
    SUMMARIZER_DB_TIMEOUT: int = int(os.getenv("SUMMARIZER_DB_TIMEOUT", "30"))

    # Summarizer AI Configuration
    SUMMARIZER_DEFAULT_OPENAI_MODEL: str = os.getenv("SUMMARIZER_DEFAULT_OPENAI_MODEL", "gpt-3.5-turbo")
    SUMMARIZER_DEFAULT_GOOGLE_MODEL: str = os.getenv("SUMMARIZER_DEFAULT_GOOGLE_MODEL", "gemini-pro")
    SUMMARIZER_DEFAULT_ANTHROPIC_MODEL: str = os.getenv("SUMMARIZER_DEFAULT_ANTHROPIC_MODEL", "claude-3-sonnet-20240229")

    # Summarizer Vector Search Configuration
    SUMMARIZER_VECTOR_MODEL_NAME: str = os.getenv("SUMMARIZER_VECTOR_MODEL_NAME", "all-MiniLM-L6-v2")
    SUMMARIZER_VECTOR_INDEX_PATH: str = os.getenv("SUMMARIZER_VECTOR_INDEX_PATH", "data/vectors/summarizer_index.bin")
    SUMMARIZER_EMBEDDING_DIMENSION: int = int(os.getenv("SUMMARIZER_EMBEDDING_DIMENSION", "384"))
    SUMMARIZER_VECTOR_SEARCH_CACHE_SIZE: int = int(os.getenv("SUMMARIZER_VECTOR_SEARCH_CACHE_SIZE", "1000"))

    # Summarizer Processing Configuration
    SUMMARIZER_CONVERSATION_MEMORY_SIZE: int = int(os.getenv("SUMMARIZER_CONVERSATION_MEMORY_SIZE", "1000"))
    SUMMARIZER_SUMMARY_INTERVAL_SECONDS: int = int(os.getenv("SUMMARIZER_SUMMARY_INTERVAL_SECONDS", "30"))
    SUMMARIZER_MAX_SUMMARY_LENGTH: int = int(os.getenv("SUMMARIZER_MAX_SUMMARY_LENGTH", "500"))

    # Summarizer UI Configuration
    SUMMARIZER_UI_THEME: str = os.getenv("SUMMARIZER_UI_THEME", "light")
    SUMMARIZER_UI_LANGUAGE: str = os.getenv("SUMMARIZER_UI_LANGUAGE", "sv")
    SUMMARIZER_UI_NOTIFICATIONS_ENABLED: bool = os.getenv("SUMMARIZER_UI_NOTIFICATIONS_ENABLED", "true").lower() == "true"
    SUMMARIZER_UI_AUTO_REFRESH: bool = os.getenv("SUMMARIZER_UI_AUTO_REFRESH", "true").lower() == "true"

    # Summarizer Voice Commands Configuration
    SUMMARIZER_VOICE_FEEDBACK_ENABLED: bool = os.getenv("SUMMARIZER_VOICE_FEEDBACK_ENABLED", "true").lower() == "true"
    SUMMARIZER_VOICE_COMMAND_TIMEOUT: int = int(os.getenv("SUMMARIZER_VOICE_COMMAND_TIMEOUT", "10"))
    SUMMARIZER_VOICE_SIMILARITY_THRESHOLD: float = float(os.getenv("SUMMARIZER_VOICE_SIMILARITY_THRESHOLD", "0.3"))

    # Summarizer Topic Management Configuration
    SUMMARIZER_MAX_TOPIC_VERSIONS: int = int(os.getenv("SUMMARIZER_MAX_TOPIC_VERSIONS", "10"))
    SUMMARIZER_TOPIC_RELATIONSHIP_DEPTH: int = int(os.getenv("SUMMARIZER_TOPIC_RELATIONSHIP_DEPTH", "3"))
    SUMMARIZER_AUTO_TOPIC_SEGMENTATION: bool = os.getenv("SUMMARIZER_AUTO_TOPIC_SEGMENTATION", "true").lower() == "true"

    # Summarizer Search Configuration
    SUMMARIZER_DEFAULT_SEARCH_LIMIT: int = int(os.getenv("SUMMARIZER_DEFAULT_SEARCH_LIMIT", "10"))
    SUMMARIZER_SEARCH_CACHE_SIZE: int = int(os.getenv("SUMMARIZER_SEARCH_CACHE_SIZE", "100"))
    SUMMARIZER_FUZZY_SEARCH_THRESHOLD: float = float(os.getenv("SUMMARIZER_FUZZY_SEARCH_THRESHOLD", "0.6"))

    # Frontend Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # LiveKit Configuration - will be set securely in model_validator
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # Supabase Configuration - will be set securely in model_validator
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = ""
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = ""

    # Optional Services
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    REDIS_PASSWORD: str = ""  # Will be set in model_validator
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # File Storage Configuration
    FILE_STORAGE_PATH: str = os.getenv("FILE_STORAGE_PATH", "./uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

    # Monitoring Configuration
    SENTRY_DSN: Optional[str] = ""  # Will be set in model_validator
    ANALYTICS_ENABLED: bool = os.getenv("ANALYTICS_ENABLED", "false").lower() == "true"

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        extra="ignore"  # Allow extra environment variables
    )


# Global settings instance
settings = Settings()


# MCP-specific configuration class for easy access (Legacy - now using local service)
class MCPConfig:
    """MCP-specific configuration settings"""

    SERVER_URL: str = settings.MCP_SERVER_URL
    SERVER_TYPE: str = settings.MCP_SERVER_TYPE
    CONNECTION_TIMEOUT: int = settings.MCP_CONNECTION_TIMEOUT
    SSE_READ_TIMEOUT: int = settings.MCP_SSE_READ_TIMEOUT
    AUTO_RECONNECT: bool = settings.MCP_AUTO_RECONNECT
    MAX_RECONNECT_ATTEMPTS: int = settings.MCP_MAX_RECONNECT_ATTEMPTS
    RECONNECT_DELAY: float = settings.MCP_RECONNECT_DELAY

    @classmethod
    def get_connection_config(cls) -> dict:
        """Get configuration as dictionary for MCP service"""
        return {
            "server_url": cls.SERVER_URL,
            "server_type": cls.SERVER_TYPE,
            "timeout": cls.CONNECTION_TIMEOUT,
            "sse_read_timeout": cls.SSE_READ_TIMEOUT,
            "auto_reconnect": cls.AUTO_RECONNECT,
            "max_reconnect_attempts": cls.MAX_RECONNECT_ATTEMPTS,
            "reconnect_delay": cls.RECONNECT_DELAY,
            "headers": {
                "Content-Type": "application/json",
                "User-Agent": "Meetmind-Backend/1.0"
            }
        }


# Summarizer-specific configuration class for easy access
class SummarizerConfig:
    """Summarizer-specific configuration settings"""

    ENABLED: bool = settings.SUMMARIZER_ENABLED
    MAX_REQUESTS: int = settings.SUMMARIZER_MAX_REQUESTS
    REQUEST_TIMEOUT: int = settings.SUMMARIZER_REQUEST_TIMEOUT
    CACHING: bool = settings.SUMMARIZER_CACHING
    CACHE_TTL: int = settings.SUMMARIZER_CACHE_TTL

    DB_PATH: str = settings.SUMMARIZER_DB_PATH
    DB_CONNECTION_POOL_SIZE: int = settings.SUMMARIZER_DB_CONNECTION_POOL_SIZE
    DB_TIMEOUT: int = settings.SUMMARIZER_DB_TIMEOUT

    DEFAULT_OPENAI_MODEL: str = settings.SUMMARIZER_DEFAULT_OPENAI_MODEL
    DEFAULT_GOOGLE_MODEL: str = settings.SUMMARIZER_DEFAULT_GOOGLE_MODEL
    DEFAULT_ANTHROPIC_MODEL: str = settings.SUMMARIZER_DEFAULT_ANTHROPIC_MODEL

    VECTOR_MODEL_NAME: str = settings.SUMMARIZER_VECTOR_MODEL_NAME
    VECTOR_INDEX_PATH: str = settings.SUMMARIZER_VECTOR_INDEX_PATH
    EMBEDDING_DIMENSION: int = settings.SUMMARIZER_EMBEDDING_DIMENSION
    VECTOR_SEARCH_CACHE_SIZE: int = settings.SUMMARIZER_VECTOR_SEARCH_CACHE_SIZE

    CONVERSATION_MEMORY_SIZE: int = settings.SUMMARIZER_CONVERSATION_MEMORY_SIZE
    SUMMARY_INTERVAL_SECONDS: int = settings.SUMMARIZER_SUMMARY_INTERVAL_SECONDS
    MAX_SUMMARY_LENGTH: int = settings.SUMMARIZER_MAX_SUMMARY_LENGTH

    UI_THEME: str = settings.SUMMARIZER_UI_THEME
    UI_LANGUAGE: str = settings.SUMMARIZER_UI_LANGUAGE
    UI_NOTIFICATIONS_ENABLED: bool = settings.SUMMARIZER_UI_NOTIFICATIONS_ENABLED
    UI_AUTO_REFRESH: bool = settings.SUMMARIZER_UI_AUTO_REFRESH

    VOICE_FEEDBACK_ENABLED: bool = settings.SUMMARIZER_VOICE_FEEDBACK_ENABLED
    VOICE_COMMAND_TIMEOUT: int = settings.SUMMARIZER_VOICE_COMMAND_TIMEOUT
    VOICE_SIMILARITY_THRESHOLD: float = settings.SUMMARIZER_VOICE_SIMILARITY_THRESHOLD

    MAX_TOPIC_VERSIONS: int = settings.SUMMARIZER_MAX_TOPIC_VERSIONS
    TOPIC_RELATIONSHIP_DEPTH: int = settings.SUMMARIZER_TOPIC_RELATIONSHIP_DEPTH
    AUTO_TOPIC_SEGMENTATION: bool = settings.SUMMARIZER_AUTO_TOPIC_SEGMENTATION

    DEFAULT_SEARCH_LIMIT: int = settings.SUMMARIZER_DEFAULT_SEARCH_LIMIT
    SEARCH_CACHE_SIZE: int = settings.SUMMARIZER_SEARCH_CACHE_SIZE
    FUZZY_SEARCH_THRESHOLD: float = settings.SUMMARIZER_FUZZY_SEARCH_THRESHOLD

    @classmethod
    def get_service_config(cls) -> dict:
        """Get configuration as dictionary for summarizer service"""
        return {
            "enabled": cls.ENABLED,
            "max_concurrent_requests": cls.MAX_REQUESTS,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "enable_caching": cls.CACHING,
            "cache_ttl": cls.CACHE_TTL
        }

    @classmethod
    def get_database_config(cls) -> dict:
        """Get database configuration"""
        return {
            "db_path": cls.DB_PATH,
            "db_connection_pool_size": cls.DB_CONNECTION_POOL_SIZE,
            "db_timeout": cls.DB_TIMEOUT
        }

    @classmethod
    def get_ai_config(cls) -> dict:
        """Get AI provider configuration"""
        return {
            "default_openai_model": cls.DEFAULT_OPENAI_MODEL,
            "default_google_model": cls.DEFAULT_GOOGLE_MODEL,
            "default_anthropic_model": cls.DEFAULT_ANTHROPIC_MODEL
        }


class ConfigurationError(Exception):
    """Raised when configuration validation fails"""
    pass


def validate_configuration(fail_fast: bool = None) -> List[str]:
    """
    Validate the current configuration and return list of warnings/errors
    
    Args:
        fail_fast: If True, raise exception on critical errors. If None, use settings value.

    Returns:
        List[str]: List of validation messages
        
    Raises:
        ConfigurationError: If fail_fast is True and critical errors are found
    """
    warnings = []
    critical_errors = []
    
    if fail_fast is None:
        fail_fast = settings.FAIL_FAST_ON_CONFIG_ERROR

    try:
        # Check authentication configuration
        auth_errors = settings.validate_production_secrets()
        for error in auth_errors:
            if "required" in error.lower() or "empty" in error.lower():
                critical_errors.append(f"CRITICAL: {error}")
            else:
                warnings.append(error)

        # Check required services for production
        if settings.ENVIRONMENT == "production":
            # Critical checks for production
            if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key":
                critical_errors.append("CRITICAL: JWT_SECRET_KEY must be set in production")
            
            if settings.BACKEND_DEBUG:
                warnings.append("Debug mode enabled in production environment")

            if settings.BACKEND_HOST == "0.0.0.0":
                warnings.append("Binding to all interfaces in production - consider using specific host")
            
            # Check database configuration
            if not settings.DATABASE_URL or settings.DATABASE_URL == "sqlite:///./meetings.db":
                warnings.append("Using SQLite in production - consider PostgreSQL for better performance")

        # Check AI configuration
        if not settings.OPENAI_API_KEY and not settings.GOOGLE_AI_API_KEY and not settings.ANTHROPIC_API_KEY:
            if settings.ENVIRONMENT == "production":
                critical_errors.append("CRITICAL: At least one AI API key is required in production")
            else:
                warnings.append("No AI API keys configured - AI features will not work")

        # Check MCP configuration (legacy)
        if settings.MCP_SERVER_URL.startswith("http://localhost") and settings.ENVIRONMENT == "production":
            warnings.append("MCP server URL points to localhost in production environment")

        # Check Summarizer configuration
        if settings.SUMMARIZER_ENABLED:
            if not settings.OPENAI_API_KEY and not settings.GOOGLE_AI_API_KEY:
                warnings.append("Summarizer enabled but no AI API keys configured")

            if settings.SUMMARIZER_REQUEST_TIMEOUT <= 0:
                critical_errors.append("CRITICAL: Summarizer request timeout must be greater than 0")

            if settings.SUMMARIZER_CACHE_TTL <= 0:
                warnings.append("Summarizer cache TTL must be greater than 0")

        # Check external secret management configuration
        if settings.AWS_SECRETS_MANAGER_ENABLED and not AWS_AVAILABLE:
            warnings.append("AWS Secrets Manager enabled but boto3 not installed")
        
        if settings.VAULT_ENABLED and not VAULT_AVAILABLE:
            warnings.append("Vault enabled but hvac not installed")

        # Combine all messages
        all_messages = critical_errors + warnings
        
        # Fail fast if critical errors and enabled
        if critical_errors and fail_fast:
            error_msg = "Configuration validation failed with critical errors:\n" + "\n".join(critical_errors)
            raise ConfigurationError(error_msg)
        
        return all_messages
        
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        critical_error = f"CRITICAL: Configuration validation failed: {str(e)}"
        if fail_fast:
            raise ConfigurationError(critical_error)
        return [critical_error]


def validate_secrets_strength() -> Dict[str, List[str]]:
    """Validate the strength of all configured secrets"""
    secret_manager = SecretManager()
    results = {}
    
    secrets_to_check = {
        'JWT_SECRET_KEY': settings.SECRET_KEY,
        'OPENAI_API_KEY': settings.OPENAI_API_KEY,
        'GOOGLE_AI_API_KEY': settings.GOOGLE_AI_API_KEY,
        'LIVEKIT_API_SECRET': settings.LIVEKIT_API_SECRET,
        'QDRANT_API_KEY': settings.QDRANT_API_KEY,
    }
    
    for name, value in secrets_to_check.items():
        if value:
            min_length = 32 if 'SECRET_KEY' in name else 16
            results[name] = secret_manager.validate_secret_strength(value, min_length)
        else:
            results[name] = ["Secret not configured"]
    
    return results


def get_environment_info() -> dict:
    """Get environment information for debugging"""
    return {
        "environment": settings.ENVIRONMENT,
        "backend_host": settings.BACKEND_HOST,
        "backend_port": settings.BACKEND_PORT,
        "mcp_server_url": settings.MCP_SERVER_URL,
        "summarizer_ui_host": settings.SUMMARIZER_UI_HOST,
        "summarizer_ui_port": settings.SUMMARIZER_UI_PORT,
        "summarizer_enabled": settings.SUMMARIZER_ENABLED,
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_google_ai_key": bool(settings.GOOGLE_AI_API_KEY),
        "has_qdrant_config": bool(settings.QDRANT_URL != "localhost:6333" or settings.QDRANT_API_KEY),
        "log_level": settings.LOG_LEVEL
    }