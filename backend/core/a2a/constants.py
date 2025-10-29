"""
A2A Protocol Constants and Configuration

Defines the core constants, message types, and configuration parameters
for the Agent-to-Agent communication protocol in HappyOS.
"""

import os
from typing import Dict, Any
from enum import Enum

# Protocol Version
A2A_PROTOCOL_VERSION = "1.0.0"
A2A_DEFAULT_PORT = 8443
A2A_HEALTH_CHECK_INTERVAL = 30  # seconds

# Cryptographic Constants
RSA_KEY_SIZE = 2048
CERTIFICATE_VALIDITY_DAYS = 365
AES_GCM_KEY_SIZE = 256
AES_GCM_IV_SIZE = 96  # bits for GCM
HMAC_KEY_SIZE = 256

# Message Types
class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    DISCOVERY = "discovery"
    REGISTRATION = "registration"
    DEREGISTRATION = "deregistration"
    
    # Agent-specific message types
    AGENT_SVEA_BAS_VALIDATION = "agent_svea_bas_validation"
    AGENT_SVEA_ERP_SYNC = "agent_svea_erp_sync"
    AGENT_SVEA_SKATTEVERKET_SUBMISSION = "agent_svea_skatteverket_submission"
    AGENT_SVEA_COMPLIANCE_CHECK = "agent_svea_compliance_check"
    
    FELICIAS_FINANCE_CRYPTO_TRADE = "felicias_finance_crypto_trade"
    FELICIAS_FINANCE_PORTFOLIO_ANALYSIS = "felicias_finance_portfolio_analysis"
    FELICIAS_FINANCE_BANKING_TRANSACTION = "felicias_finance_banking_transaction"
    FELICIAS_FINANCE_RISK_ASSESSMENT = "felicias_finance_risk_assessment"
    
    MEETMIND_TRANSCRIPT_ANALYSIS = "meetmind_transcript_analysis"
    MEETMIND_SUMMARY_REQUEST = "meetmind_summary_request"
    MEETMIND_INSIGHT_GENERATION = "meetmind_insight_generation"
    MEETMIND_ACTION_ITEM_EXTRACTION = "meetmind_action_item_extraction"
    
    # Cross-agent workflow message types
    CROSS_AGENT_WORKFLOW_START = "cross_agent_workflow_start"
    CROSS_AGENT_WORKFLOW_STEP = "cross_agent_workflow_step"
    CROSS_AGENT_WORKFLOW_COMPLETE = "cross_agent_workflow_complete"
    CROSS_AGENT_WORKFLOW_ERROR = "cross_agent_workflow_error"
    FINANCIAL_COMPLIANCE_WORKFLOW = "financial_compliance_workflow"
    MEETING_FINANCIAL_ANALYSIS = "meeting_financial_analysis"
    COMPREHENSIVE_REPORTING = "comprehensive_reporting"

# Message Priorities
class MessagePriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

# Agent Capabilities
class AgentCapability(Enum):
    GENERAL = "general"
    ANALYSIS = "analysis"
    CODING = "coding"
    RESEARCH = "research"
    ACCOUNTING = "accounting"
    BANKING = "banking"
    CRYPTO = "crypto"
    WRITING = "writing"
    ORCHESTRATION = "orchestration"
    SELF_BUILDING = "self_building"
    MONITORING = "monitoring"
    
    # Agent-specific capabilities
    SWEDISH_ERP = "swedish_erp"
    BAS_VALIDATION = "bas_validation"
    SKATTEVERKET_INTEGRATION = "skatteverket_integration"
    SWEDISH_COMPLIANCE = "swedish_compliance"
    
    CRYPTO_TRADING = "crypto_trading"
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    FINANCIAL_ANALYSIS = "financial_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    BANKING_INTEGRATION = "banking_integration"
    
    MEETING_INTELLIGENCE = "meeting_intelligence"
    TRANSCRIPT_PROCESSING = "transcript_processing"
    INSIGHT_GENERATION = "insight_generation"
    REAL_TIME_COMMUNICATION = "real_time_communication"
    
    # Cross-agent capabilities
    WORKFLOW_ORCHESTRATION = "workflow_orchestration"
    CROSS_AGENT_COMMUNICATION = "cross_agent_communication"
    MULTI_AGENT_COORDINATION = "multi_agent_coordination"

# Transport Protocols
class TransportProtocol(Enum):
    HTTP2 = "http2"
    WEBSOCKET = "websocket"
    GRPC = "grpc"

# Authentication Methods
class AuthMethod(Enum):
    MUTUAL_TLS = "mutual_tls"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"

# Encryption Algorithms
class EncryptionAlgorithm(Enum):
    AES_256_GCM = "AES-256-GCM"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"
    RSA_OAEP = "RSA-OAEP"

# Hash Algorithms
class HashAlgorithm(Enum):
    SHA256 = "SHA-256"
    SHA384 = "SHA-384"
    SHA512 = "SHA-512"

# Default Configuration
DEFAULT_CONFIG = {
    "protocol_version": A2A_PROTOCOL_VERSION,
    "port": A2A_DEFAULT_PORT,
    "health_check_interval": A2A_HEALTH_CHECK_INTERVAL,
    "max_message_size": 10 * 1024 * 1024,  # 10MB
    "message_timeout": 30,  # seconds
    "connection_timeout": 10,  # seconds
    "max_connections": 1000,
    "enable_tls": True,
    "tls_version": "TLS_1_3",
    "enable_http2": True,
    "enable_websocket_fallback": True,
    "enable_discovery": True,
    "enable_health_monitoring": True,
    "enable_metrics_collection": True,
    "enable_message_audit": True,
    "key_rotation_interval": 90,  # days
    "certificate_rotation_threshold": 30,  # days before expiry
    "max_registration_ttl": 3600,  # seconds
    "discovery_cache_ttl": 300,  # seconds
    "heartbeat_interval": 60,  # seconds
    "failed_heartbeat_threshold": 3,
    "max_concurrent_workflows": 100,
    "workflow_timeout": 300,  # seconds
    "enable_workflow_persistence": True,
    "workflow_cleanup_interval": 86400,  # seconds (24 hours)
}

# Message Headers
class MessageHeader:
    MESSAGE_ID = "message_id"
    SENDER_ID = "sender_id"
    RECIPIENT_ID = "recipient_id"
    TIMESTAMP = "timestamp"
    MESSAGE_TYPE = "message_type"
    ENCRYPTION = "encryption"
    SIGNATURE = "signature"
    CORRELATION_ID = "correlation_id"
    WORKFLOW_ID = "workflow_id"
    TASK_ID = "task_id"
    PRIORITY = "priority"
    TTL = "ttl"
    CONTENT_TYPE = "content_type"
    COMPRESSION = "compression"

# Content Types
class ContentType:
    JSON = "application/json"
    BINARY = "application/octet-stream"
    TEXT = "text/plain"
    XML = "application/xml"
    FORM_ENCODED = "application/x-www-form-urlencoded"

# Compression Types
class CompressionType(Enum):
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    LZ4 = "lz4"

# Standard Response Codes
class ResponseCode:
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

# Agent States
class AgentState(Enum):
    REGISTERING = "registering"
    ACTIVE = "active"
    BUSY = "busy"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    ERROR = "error"

# Workflow States
class WorkflowState(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

# Cross-Agent Workflow Types
class CrossAgentWorkflowType(Enum):
    FINANCIAL_COMPLIANCE = "financial_compliance"
    COMPREHENSIVE_REPORTING = "comprehensive_reporting"
    MEETING_FINANCIAL_ANALYSIS = "meeting_financial_analysis"
    REGULATORY_VALIDATION = "regulatory_validation"
    RISK_ASSESSMENT = "risk_assessment"
    AUDIT_TRAIL_GENERATION = "audit_trail_generation"

# Agent Types for Registration
class AgentType(Enum):
    AGENT_SVEA = "agent_svea"
    FELICIAS_FINANCE = "felicias_finance"
    MEETMIND = "meetmind"
    ORCHESTRATOR = "orchestrator"
    MONITOR = "monitor"
    SELF_BUILDER = "self_builder"

# Task States
class TaskState(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

# Error Codes
class ErrorCode:
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    ENCRYPTION_FAILED = "ENCRYPTION_FAILED"
    DECRYPTION_FAILED = "DECRYPTION_FAILED"
    MESSAGE_TIMEOUT = "MESSAGE_TIMEOUT"
    INVALID_MESSAGE_FORMAT = "INVALID_MESSAGE_FORMAT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"
    TASK_EXECUTION_FAILED = "TASK_EXECUTION_FAILED"
    REGISTRATION_FAILED = "REGISTRATION_FAILED"
    DISCOVERY_FAILED = "DISCOVERY_FAILED"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    PROTOCOL_VERSION_MISMATCH = "PROTOCOL_VERSION_MISMATCH"
    CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
    CERTIFICATE_REVOKED = "CERTIFICATE_REVOKED"

# Environment Variables
ENV_CONFIG = {
    "A2A_PROTOCOL_VERSION": A2A_PROTOCOL_VERSION,
    "A2A_PORT": str(A2A_DEFAULT_PORT),
    "A2A_TLS_CERT_FILE": "A2A_TLS_CERT_FILE",
    "A2A_TLS_KEY_FILE": "A2A_TLS_KEY_FILE",
    "A2A_CA_CERT_FILE": "A2A_CA_CERT_FILE",
    "A2A_DISCOVERY_URL": "A2A_DISCOVERY_URL",
    "A2A_DISCOVERY_TOKEN": "A2A_DISCOVERY_TOKEN",
    "A2A_HEALTH_CHECK_INTERVAL": str(A2A_HEALTH_CHECK_INTERVAL),
    "A2A_MAX_MESSAGE_SIZE": str(DEFAULT_CONFIG["max_message_size"]),
    "A2A_ENABLE_TLS": "true",
    "A2A_ENABLE_HTTP2": "true",
    "A2A_ENABLE_WEBSOCKET": "true",
    "A2A_ENABLE_DISCOVERY": "true",
    "A2A_ENABLE_METRICS": "true",
    "A2A_LOG_LEVEL": "INFO",
    "A2A_STORAGE_PATH": "./data/a2a",
    "A2A_BACKUP_PATH": "./backup/a2a",
}

# Type Definitions
AgentRecord = Dict[str, Any]
ServiceRecord = Dict[str, Any]
WorkflowDefinition = Dict[str, Any]
TaskDefinition = Dict[str, Any]
MessagePayload = Dict[str, Any]
SecurityContext = Dict[str, Any]

# Utility Functions
def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value from environment or default."""
    return os.getenv(key, default)

def get_protocol_config() -> Dict[str, Any]:
    """Get complete protocol configuration."""
    config = DEFAULT_CONFIG.copy()

    # Override with environment variables
    for key, env_key in ENV_CONFIG.items():
        if key in config and env_key in os.environ:
            env_value = os.getenv(env_key)
            if isinstance(config[key], bool):
                config[key] = env_value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(config[key], int):
                try:
                    config[key] = int(env_value)
                except ValueError:
                    pass
            elif isinstance(config[key], float):
                try:
                    config[key] = float(env_value)
                except ValueError:
                    pass
            else:
                config[key] = env_value

    return config

# Protocol Metadata
PROTOCOL_METADATA = {
    "name": "A2A Protocol",
    "version": A2A_PROTOCOL_VERSION,
    "description": "Agent-to-Agent Communication Protocol for HappyOS",
    "authors": ["HappyOS Team"],
    "license": "MIT",
    "specification_url": "https://github.com/happyfuckingai/happyos/blob/main/docs/A2A_PROTOCOL.md",
    "supported_transports": [protocol.value for protocol in TransportProtocol],
    "supported_auth_methods": [method.value for method in AuthMethod],
    "supported_encryption": [alg.value for alg in EncryptionAlgorithm],
    "supported_compression": [comp.value for comp in CompressionType],
}