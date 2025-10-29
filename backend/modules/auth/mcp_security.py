"""
MCP Security Headers and Signing

Implements MCP header signing and verification using existing HMAC/Ed25519 
crypto functions. Extends existing AuthenticationManager for MCP protocol support.

Requirements: 7.1, 7.4
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Union
from uuid import uuid4

import nacl.signing
import nacl.encoding
from pydantic import BaseModel, Field

try:
    from .jwt_service import JWTService, JWTClaims
    from .mcp_tenant_isolation import MCPHeaders
except ImportError:
    # Fallback for testing
    class JWTService:
        pass
    class JWTClaims:
        pass
    class MCPHeaders:
        pass

logger = logging.getLogger(__name__)


class MCPSigningKey(BaseModel):
    """MCP signing key configuration"""
    key_id: str
    algorithm: str  # "HMAC-SHA256" or "Ed25519"
    key_material: str  # Base64 encoded key
    created_at: str
    expires_at: Optional[str] = None
    agent_id: str
    tenant_id: str


class MCPSignature(BaseModel):
    """MCP signature information"""
    algorithm: str
    key_id: str
    signature: str
    timestamp: str
    nonce: str


class MCPSecurityError(Exception):
    """MCP security related errors"""
    def __init__(self, message: str, error_code: str = "MCP_SECURITY_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class MCPSigningService:
    """Service for MCP header signing and verification"""
    
    def __init__(self):
        # In-memory key storage for demo - in production use secure key management
        self._signing_keys: Dict[str, MCPSigningKey] = {}
        self._agent_keys: Dict[str, List[str]] = {}  # agent_id -> list of key_ids
        
        # Initialize default keys for known agents
        self._initialize_default_keys()
    
    def _initialize_default_keys(self):
        """Initialize default signing keys for known agents"""
        agents = [
            ("agent_svea", "agentsvea"),
            ("felicias_finance", "feliciasfi"), 
            ("meetmind", "meetmind"),
            ("communications_agent", "shared")
        ]
        
        for agent_id, tenant_id in agents:
            # Create HMAC key
            hmac_key_id = self.create_signing_key(agent_id, tenant_id, "HMAC-SHA256")
            
            # Create Ed25519 key
            ed25519_key_id = self.create_signing_key(agent_id, tenant_id, "Ed25519")
            
            logger.info(f"Created default keys for {agent_id}: HMAC={hmac_key_id}, Ed25519={ed25519_key_id}")
    
    def create_signing_key(
        self,
        agent_id: str,
        tenant_id: str,
        algorithm: str = "HMAC-SHA256",
        expires_in_days: Optional[int] = None
    ) -> str:
        """
        Create a new signing key for an agent
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            algorithm: Signing algorithm (HMAC-SHA256 or Ed25519)
            expires_in_days: Key expiration in days
            
        Returns:
            Key ID
        """
        key_id = f"{agent_id}_{algorithm.lower().replace('-', '_')}_{int(time.time())}"
        
        # Generate key material based on algorithm
        if algorithm == "HMAC-SHA256":
            # Generate 256-bit HMAC key
            key_material = secrets.token_urlsafe(32)
        elif algorithm == "Ed25519":
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
        
        logger.info(f"Created {algorithm} signing key {key_id} for agent {agent_id}")
        return key_id
    
    def get_agent_signing_key(self, agent_id: str, algorithm: str = "HMAC-SHA256") -> Optional[MCPSigningKey]:
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
            if not key:
                continue
            
            # Check if key is expired
            if key.expires_at:
                expires_at = datetime.fromisoformat(key.expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now(timezone.utc):
                    continue
            
            # Check algorithm match
            if key.algorithm == algorithm:
                return key
        
        # Fallback to any active key
        for key_id in self._agent_keys[agent_id]:
            key = self._signing_keys.get(key_id)
            if not key:
                continue
            
            # Check if key is expired
            if key.expires_at:
                expires_at = datetime.fromisoformat(key.expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now(timezone.utc):
                    continue
            
            return key
        
        return None
    
    def sign_mcp_headers(
        self,
        headers: MCPHeaders,
        agent_id: str,
        algorithm: str = "HMAC-SHA256"
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
        if signing_key.algorithm == "HMAC-SHA256":
            signature = self._sign_hmac(signature_payload, signing_key.key_material)
        elif signing_key.algorithm == "Ed25519":
            signature = self._sign_ed25519(signature_payload, signing_key.key_material)
        else:
            raise MCPSecurityError(f"Unsupported signing algorithm: {signing_key.algorithm}")
        
        # Create signature header
        signature_header = f"{signing_key.algorithm}:{signing_key.key_id}:{signature}:{timestamp}:{nonce}"
        
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
            
            # Parse signature header
            signature_parts = headers.auth_sig.split(":")
            if len(signature_parts) != 5:
                logger.warning("Invalid signature header format")
                return False
            
            algorithm, key_id, signature, timestamp, nonce = signature_parts
            
            # Get signing key
            signing_key = self._signing_keys.get(key_id)
            if not signing_key:
                logger.warning(f"Signing key not found: {key_id}")
                return False
            
            # Check key expiration
            if signing_key.expires_at:
                expires_at = datetime.fromisoformat(signing_key.expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now(timezone.utc):
                    logger.warning(f"Signing key expired: {key_id}")
                    return False
            
            # Check signature age
            sig_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            age_seconds = (datetime.now(timezone.utc) - sig_timestamp).total_seconds()
            if age_seconds > max_age_seconds:
                logger.warning(f"Signature too old: {age_seconds}s > {max_age_seconds}s")
                return False
            
            # Verify caller matches key owner
            if headers.caller != signing_key.agent_id:
                logger.warning(f"Caller {headers.caller} does not match key owner {signing_key.agent_id}")
                return False
            
            # Create signature payload
            signature_payload = self._create_signature_payload(headers, timestamp, nonce)
            
            # Verify signature
            if algorithm == "HMAC-SHA256":
                return self._verify_hmac(signature_payload, signature, signing_key.key_material)
            elif algorithm == "Ed25519":
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
            
        except Exception as e:
            logger.debug(f"Ed25519 verification failed: {e}")
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
        new_hmac_key = self.create_signing_key(agent_id, tenant_id, "HMAC-SHA256")
        new_ed25519_key = self.create_signing_key(agent_id, tenant_id, "Ed25519")
        
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
            if key.expires_at:
                expires_at = datetime.fromisoformat(key.expires_at.replace('Z', '+00:00'))
                if expires_at < now:
                    expired_keys += 1
                else:
                    active_keys += 1
            else:
                active_keys += 1
        
        return {
            "total_keys": len(self._signing_keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "agents_with_keys": len(self._agent_keys),
            "algorithms": list(set(key.algorithm for key in self._signing_keys.values()))
        }


class MCPAuthenticationManager:
    """Extended authentication manager for MCP protocol"""
    
    def __init__(self, signing_service: MCPSigningService = None):
        self.signing_service = signing_service or MCPSigningService()
        self.jwt_service = JWTService()
    
    def create_mcp_agent_token(
        self,
        agent_id: str,
        tenant_id: str,
        session_id: str = "*",
        permissions: List[str] = None,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create JWT token for MCP agent with tenant-specific scopes
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            session_id: Session identifier
            permissions: List of permissions
            expires_in_hours: Token expiration in hours
            
        Returns:
            JWT token
        """
        if permissions is None:
            permissions = ["read", "write"]
        
        # Generate tenant-specific scopes
        scopes = []
        for permission in permissions:
            scopes.append(f"mcp:{permission}:{tenant_id}:{session_id}")
        
        # Add agent-specific scopes
        scopes.extend([
            f"agent:{agent_id}:call",
            f"agent:{agent_id}:callback"
        ])
        
        return self.jwt_service.create_access_token(
            subject=f"agent-{agent_id}",
            scopes=scopes,
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            expires_delta=timedelta(hours=expires_in_hours)
        )
    
    def validate_mcp_agent_token(self, token: str) -> Optional[JWTClaims]:
        """
        Validate MCP agent JWT token
        
        Args:
            token: JWT token to validate
            
        Returns:
            JWT claims if valid
        """
        claims = self.jwt_service.verify_token(token)
        
        if not claims:
            return None
        
        # Verify it's an agent token
        if not claims.sub.startswith("agent-"):
            logger.warning("Token is not an agent token")
            return None
        
        # Verify agent ID matches
        if claims.agentId and f"agent-{claims.agentId}" != claims.sub:
            logger.warning("Agent ID mismatch in token")
            return None
        
        return claims
    
    def authenticate_mcp_request(
        self,
        headers: MCPHeaders,
        jwt_token: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate MCP request with signature and optional JWT
        
        Args:
            headers: MCP headers with signature
            jwt_token: Optional JWT token
            
        Returns:
            Tuple of (is_authenticated, error_message)
        """
        try:
            # Verify signature
            if not self.signing_service.verify_mcp_signature(headers):
                return False, "Invalid or missing signature"
            
            # Verify JWT token if provided
            if jwt_token:
                claims = self.validate_mcp_agent_token(jwt_token)
                if not claims:
                    return False, "Invalid JWT token"
                
                # Verify agent ID matches caller
                expected_agent = claims.agentId
                if headers.caller != expected_agent:
                    return False, f"Agent ID mismatch: {headers.caller} != {expected_agent}"
                
                # Verify tenant access
                if claims.tenantId and claims.tenantId != headers.tenant_id:
                    return False, f"Tenant mismatch: {headers.tenant_id} != {claims.tenantId}"
            
            logger.debug(f"MCP request authenticated for agent {headers.caller}")
            return True, None
            
        except Exception as e:
            logger.error(f"MCP authentication error: {e}")
            return False, f"Authentication failed: {str(e)}"
    
    def create_signed_mcp_headers(
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


# Global services
mcp_signing_service = MCPSigningService()
mcp_authentication_manager = MCPAuthenticationManager(mcp_signing_service)