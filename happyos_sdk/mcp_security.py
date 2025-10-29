"""
HappyOS SDK - Unified MCP Security

Standardized MCP header signing and validation for all HappyOS agents.
Provides consistent authentication across Agent Svea, Felicia's Finance, and MeetMind
using HMAC/Ed25519 signatures with tenant isolation.

Requirements: 5.1, 5.3, 5.4
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Union
from uuid import uuid4
from dataclasses import dataclass
from enum import Enum

import nacl.signing
import nacl.encoding
from nacl.exceptions import BadSignatureError

from .exceptions import A2AError, AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class SigningAlgorithm(Enum):
    """Supported signing algorithms"""
    HMAC_SHA256 = "HMAC-SHA256"
    ED25519 = "Ed25519"


@dataclass
class MCPHeaders:
    """Standardized MCP headers across all agent systems"""
    tenant_id: str
    trace_id: str
    conversation_id: str
    caller: str
    reply_to: Optional[str] = None
    auth_sig: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for HTTP headers"""
        headers = {
            "X-MCP-Tenant-ID": self.tenant_id,
            "X-MCP-Trace-ID": self.trace_id,
            "X-MCP-Conversation-ID": self.conversation_id,
            "X-MCP-Caller": self.caller,
            "X-MCP-Timestamp": self.timestamp
        }
        
        if self.reply_to:
            headers["X-MCP-Reply-To"] = self.reply_to
        if self.auth_sig:
            headers["X-MCP-Auth-Sig"] = self.auth_sig
            
        return headers
    
    @classmethod
    def from_dict(cls, headers: Dict[str, str]) -> "MCPHeaders":
        """Create MCPHeaders from HTTP headers dictionary"""
        return cls(
            tenant_id=headers.get("X-MCP-Tenant-ID", ""),
            trace_id=headers.get("X-MCP-Trace-ID", ""),
            conversation_id=headers.get("X-MCP-Conversation-ID", ""),
            caller=headers.get("X-MCP-Caller", ""),
            reply_to=headers.get("X-MCP-Reply-To"),
            auth_sig=headers.get("X-MCP-Auth-Sig"),
            timestamp=headers.get("X-MCP-Timestamp")
        )


@dataclass
class MCPSigningKey:
    """MCP signing key configuration"""
    key_id: str
    algorithm: SigningAlgorithm
    key_material: str  # Base64 encoded key
    created_at: str
    agent_id: str
    tenant_id: str
    expires_at: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if key is expired"""
        if not self.expires_at:
            return False
        
        expires_at = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expires_at


class MCPSecurityError(A2AError):
    """MCP security related errors"""
    def __init__(self, message: str, error_code: str = "MCP_SECURITY_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class MCPSigningService:
    """Unified MCP signing service for all HappyOS agents"""
    
    def __init__(self):
        # In-memory key storage for demo - in production use secure key management
        self._signing_keys: Dict[str, MCPSigningKey] = {}
        self._agent_keys: Dict[str, List[str]] = {}  # agent_id -> list of key_ids
        
        # Initialize default keys for all agents
        self._initialize_agent_keys()
    
    def _initialize_agent_keys(self):
        """Initialize signing keys for all HappyOS agents"""
        agents = [
            ("agent_svea", "agentsvea"),
            ("felicias_finance", "feliciasfi"), 
            ("meetmind", "meetmind"),
            ("communications_agent", "shared")
        ]
        
        for agent_id, tenant_id in agents:
            # Create HMAC key (primary)
            hmac_key_id = self.create_signing_key(
                agent_id=agent_id,
                tenant_id=tenant_id,
                algorithm=SigningAlgorithm.HMAC_SHA256
            )
            
            # Create Ed25519 key (backup)
            ed25519_key_id = self.create_signing_key(
                agent_id=agent_id,
                tenant_id=tenant_id,
                algorithm=SigningAlgorithm.ED25519
            )
            
            logger.info(f"Initialized keys for {agent_id}: HMAC={hmac_key_id}, Ed25519={ed25519_key_id}")
    
    def create_signing_key(
        self,
        agent_id: str,
        tenant_id: str,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256,
        expires_in_days: Optional[int] = None
    ) -> str:
        """
        Create a new signing key for an agent
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            algorithm: Signing algorithm
            expires_in_days: Key expiration in days
            
        Returns:
            Key ID
        """
        key_id = f"{agent_id}_{algorithm.value.lower().replace('-', '_')}_{int(time.time())}"
        
        # Generate key material based on algorithm
        if algorithm == SigningAlgorithm.HMAC_SHA256:
            # Generate 256-bit HMAC key
            key_material = secrets.token_urlsafe(32)
        elif algorithm == SigningAlgorithm.ED25519:
            # Generate Ed25519 key pair
            signing_key = nacl.signing.SigningKey.generate()
            key_material = signing_key.encode(encoder=nacl.encoding.Base64Encoder).decode()
        else:
            raise MCPSecurityError(f"Unsupported algorithm: {algorithm}")
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
        
        # Create key record
        signing_key = MCPSigningKey(
            key_id=key_id,
            algorithm=algorithm,
            key_material=key_material,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at,
            agent_id=agent_id,
            tenant_id=tenant_id
        )
        
        # Store key
        self._signing_keys[key_id] = signing_key
        
        # Update agent key mapping
        if agent_id not in self._agent_keys:
            self._agent_keys[agent_id] = []
        self._agent_keys[agent_id].append(key_id)
        
        logger.debug(f"Created {algorithm.value} signing key {key_id} for agent {agent_id}")
        return key_id
    
    def get_agent_signing_key(
        self, 
        agent_id: str, 
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256
    ) -> Optional[MCPSigningKey]:
        """
        Get active signing key for an agent
        
        Args:
            agent_id: Agent identifier
            algorithm: Preferred algorithm
            
        Returns:
            Signing key if found
        """
        if agent_id not in self._agent_keys:
            return None
        
        # Find active key with preferred algorithm
        for key_id in self._agent_keys[agent_id]:
            key = self._signing_keys.get(key_id)
            if not key or key.is_expired():
                continue
            
            if key.algorithm == algorithm:
                return key
        
        # Fallback to any active key
        for key_id in self._agent_keys[agent_id]:
            key = self._signing_keys.get(key_id)
            if key and not key.is_expired():
                return key
        
        return None
    
    def sign_mcp_headers(
        self,
        headers: MCPHeaders,
        agent_id: str,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256
    ) -> MCPHeaders:
        """
        Sign MCP headers with agent's signing key
        
        Args:
            headers: MCP headers to sign
            agent_id: Agent identifier
            algorithm: Signing algorithm
            
        Returns:
            Headers with signature
        """
        # Get signing key
        signing_key = self.get_agent_signing_key(agent_id, algorithm)
        if not signing_key:
            raise MCPSecurityError(f"No signing key found for agent {agent_id}")
        
        # Add timestamp and nonce
        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_urlsafe(16)
        
        # Create signature payload
        signature_payload = self._create_signature_payload(headers, timestamp, nonce)
        
        # Generate signature
        if signing_key.algorithm == SigningAlgorithm.HMAC_SHA256:
            signature = self._sign_hmac(signature_payload, signing_key.key_material)
        elif signing_key.algorithm == SigningAlgorithm.ED25519:
            signature = self._sign_ed25519(signature_payload, signing_key.key_material)
        else:
            raise MCPSecurityError(f"Unsupported signing algorithm: {signing_key.algorithm}")
        
        # Create signature header (use | as delimiter to avoid conflicts with timestamp colons)
        signature_header = f"{signing_key.algorithm.value}|{signing_key.key_id}|{signature}|{timestamp}|{nonce}"
        
        # Return headers with signature
        headers.auth_sig = signature_header
        headers.timestamp = timestamp
        
        logger.debug(f"Signed MCP headers for agent {agent_id} with key {signing_key.key_id}")
        return headers
    
    def verify_mcp_signature(
        self,
        headers: MCPHeaders,
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verify MCP header signature
        
        Args:
            headers: MCP headers with signature
            max_age_seconds: Maximum age of signature in seconds
            
        Returns:
            True if signature is valid
        """
        try:
            if not headers.auth_sig:
                logger.warning("No signature found in MCP headers")
                return False
            
            # Parse signature header (using | as delimiter)
            signature_parts = headers.auth_sig.split("|")
            if len(signature_parts) != 5:
                logger.warning(f"Invalid signature header format: expected 5 parts, got {len(signature_parts)} in '{headers.auth_sig}'")
                return False
            
            algorithm_str, key_id, signature, timestamp, nonce = signature_parts
            
            # Parse algorithm
            try:
                algorithm = SigningAlgorithm(algorithm_str)
            except ValueError:
                logger.warning(f"Unknown signing algorithm: {algorithm_str}")
                return False
            
            # Get signing key
            signing_key = self._signing_keys.get(key_id)
            if not signing_key:
                logger.warning(f"Signing key not found: {key_id}")
                return False
            
            # Check key expiration
            if signing_key.is_expired():
                logger.warning(f"Signing key expired: {key_id}")
                return False
            
            # Check signature age
            try:
                sig_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                age_seconds = (datetime.now(timezone.utc) - sig_timestamp).total_seconds()
                if age_seconds > max_age_seconds:
                    logger.warning(f"Signature too old: {age_seconds}s > {max_age_seconds}s")
                    return False
            except ValueError as e:
                logger.warning(f"Invalid timestamp format: {timestamp} - {e}")
                return False
            
            # Verify caller matches key owner
            if headers.caller != signing_key.agent_id:
                logger.warning(f"Caller {headers.caller} does not match key owner {signing_key.agent_id}")
                return False
            
            # Create signature payload
            signature_payload = self._create_signature_payload(headers, timestamp, nonce)
            
            # Verify signature
            if algorithm == SigningAlgorithm.HMAC_SHA256:
                return self._verify_hmac(signature_payload, signature, signing_key.key_material)
            elif algorithm == SigningAlgorithm.ED25519:
                return self._verify_ed25519(signature_payload, signature, signing_key.key_material)
            else:
                logger.warning(f"Unsupported verification algorithm: {algorithm}")
                return False
                
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def _create_signature_payload(self, headers: MCPHeaders, timestamp: str, nonce: str) -> str:
        """Create canonical signature payload from headers"""
        # Create canonical string for signing
        canonical_parts = [
            headers.tenant_id,
            headers.trace_id,
            headers.conversation_id,
            headers.caller,
            headers.reply_to or "",
            timestamp,
            nonce
        ]
        
        return "|".join(canonical_parts)
    
    def _sign_hmac(self, payload: str, key_material: str) -> str:
        """Sign payload with HMAC-SHA256"""
        key_bytes = key_material.encode('utf-8')
        payload_bytes = payload.encode('utf-8')
        signature = hmac.new(key_bytes, payload_bytes, hashlib.sha256).hexdigest()
        return signature
    
    def _verify_hmac(self, payload: str, signature: str, key_material: str) -> bool:
        """Verify HMAC-SHA256 signature"""
        expected_signature = self._sign_hmac(payload, key_material)
        return hmac.compare_digest(signature, expected_signature)
    
    def _sign_ed25519(self, payload: str, key_material: str) -> str:
        """Sign payload with Ed25519"""
        try:
            # Decode signing key
            signing_key = nacl.signing.SigningKey(
                key_material.encode(), 
                encoder=nacl.encoding.Base64Encoder
            )
            
            # Sign payload
            signed = signing_key.sign(payload.encode('utf-8'))
            signature = signed.signature.hex()
            
            return signature
            
        except Exception as e:
            logger.error(f"Ed25519 signing error: {e}")
            raise MCPSecurityError(f"Ed25519 signing failed: {str(e)}")
    
    def _verify_ed25519(self, payload: str, signature: str, key_material: str) -> bool:
        """Verify Ed25519 signature"""
        try:
            # Decode signing key to get verify key
            signing_key = nacl.signing.SigningKey(
                key_material.encode(), 
                encoder=nacl.encoding.Base64Encoder
            )
            verify_key = signing_key.verify_key
            
            # Verify signature
            signature_bytes = bytes.fromhex(signature)
            verify_key.verify(payload.encode('utf-8'), signature_bytes)
            
            return True
            
        except (BadSignatureError, ValueError) as e:
            logger.debug(f"Ed25519 verification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Ed25519 verification error: {e}")
            return False
    
    def rotate_agent_keys(self, agent_id: str) -> Dict[str, str]:
        """
        Rotate signing keys for an agent
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary with new key IDs
        """
        if agent_id not in self._agent_keys:
            raise MCPSecurityError(f"No keys found for agent: {agent_id}")
        
        # Get agent's current tenant
        old_keys = self._agent_keys[agent_id]
        if not old_keys:
            raise MCPSecurityError(f"No active keys for agent: {agent_id}")
        
        old_key = self._signing_keys[old_keys[0]]
        tenant_id = old_key.tenant_id
        
        # Create new keys
        new_hmac_key = self.create_signing_key(
            agent_id, tenant_id, SigningAlgorithm.HMAC_SHA256
        )
        new_ed25519_key = self.create_signing_key(
            agent_id, tenant_id, SigningAlgorithm.ED25519
        )
        
        # Mark old keys as expired (in production, would have grace period)
        for key_id in old_keys:
            if key_id in self._signing_keys:
                self._signing_keys[key_id].expires_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Rotated keys for agent {agent_id}")
        
        return {
            "hmac_key_id": new_hmac_key,
            "ed25519_key_id": new_ed25519_key
        }
    
    def get_key_stats(self) -> Dict:
        """Get signing key statistics"""
        now = datetime.now(timezone.utc)
        active_keys = 0
        expired_keys = 0
        
        for key in self._signing_keys.values():
            if key.is_expired():
                expired_keys += 1
            else:
                active_keys += 1
        
        return {
            "total_keys": len(self._signing_keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "agents_with_keys": len(self._agent_keys),
            "algorithms": list(set(key.algorithm.value for key in self._signing_keys.values()))
        }


class MCPAuthenticationService:
    """Unified MCP authentication service for all HappyOS agents"""
    
    def __init__(self, signing_service: MCPSigningService = None):
        self.signing_service = signing_service or MCPSigningService()
    
    def create_signed_headers(
        self,
        tenant_id: str,
        caller: str,
        trace_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> MCPHeaders:
        """
        Create signed MCP headers for outgoing requests
        
        Args:
            tenant_id: Tenant identifier
            caller: Calling agent identifier
            trace_id: Optional trace ID
            conversation_id: Optional conversation ID
            reply_to: Optional reply-to endpoint
            
        Returns:
            Signed MCP headers
        """
        # Create headers
        headers = MCPHeaders(
            tenant_id=tenant_id,
            trace_id=trace_id or str(uuid4()),
            conversation_id=conversation_id or str(uuid4()),
            caller=caller,
            reply_to=reply_to
        )
        
        # Sign headers
        signed_headers = self.signing_service.sign_mcp_headers(headers, caller)
        
        return signed_headers
    
    def authenticate_request(
        self,
        headers: MCPHeaders,
        target_agent: str = None,
        tool_name: str = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate MCP request with signature verification
        
        Args:
            headers: MCP headers with signature
            target_agent: Target agent identifier
            tool_name: Tool being called
            
        Returns:
            Tuple of (is_authenticated, error_message)
        """
        try:
            # Verify signature
            if not self.signing_service.verify_mcp_signature(headers):
                return False, "Invalid or missing signature"
            
            # Additional validation can be added here
            # - Check if caller is authorized for target_agent
            # - Check if caller has permission for tool_name
            # - Rate limiting checks
            
            logger.debug(f"MCP request authenticated: {headers.caller} -> {target_agent}.{tool_name}")
            return True, None
            
        except Exception as e:
            logger.error(f"MCP authentication error: {e}")
            return False, f"Authentication failed: {str(e)}"
    
    def validate_tenant_access(
        self,
        headers: MCPHeaders,
        required_tenant: str
    ) -> bool:
        """
        Validate tenant access in MCP headers
        
        Args:
            headers: MCP headers
            required_tenant: Required tenant ID
            
        Returns:
            True if access is valid
        """
        if headers.tenant_id != required_tenant:
            logger.warning(
                f"Tenant mismatch: {headers.tenant_id} != {required_tenant} "
                f"for caller {headers.caller}"
            )
            return False
        
        return True


# Global services for HappyOS SDK
mcp_signing_service = MCPSigningService()
mcp_authentication_service = MCPAuthenticationService(mcp_signing_service)


def create_signed_mcp_headers(
    tenant_id: str,
    caller: str,
    trace_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    reply_to: Optional[str] = None
) -> MCPHeaders:
    """
    Convenience function to create signed MCP headers
    
    Args:
        tenant_id: Tenant identifier
        caller: Calling agent identifier
        trace_id: Optional trace ID
        conversation_id: Optional conversation ID
        reply_to: Optional reply-to endpoint
        
    Returns:
        Signed MCP headers
    """
    return mcp_authentication_service.create_signed_headers(
        tenant_id=tenant_id,
        caller=caller,
        trace_id=trace_id,
        conversation_id=conversation_id,
        reply_to=reply_to
    )


def verify_mcp_headers(headers: MCPHeaders) -> bool:
    """
    Convenience function to verify MCP headers
    
    Args:
        headers: MCP headers to verify
        
    Returns:
        True if headers are valid
    """
    return mcp_signing_service.verify_mcp_signature(headers)