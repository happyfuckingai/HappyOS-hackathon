"""
Message Signing and Verification

Cryptographic signing and verification for MCP messages using
HMAC-SHA256 and Ed25519 signatures for enterprise security.
"""

import hashlib
import hmac
import json
import base64
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta

from ..exceptions import AuthenticationError, ValidationError
from ..communication.mcp.protocol import MCPMessage


@dataclass
class MessageSignature:
    """Message signature with metadata."""
    
    signature: str
    algorithm: str
    timestamp: str
    key_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        result = {
            "signature": self.signature,
            "algorithm": self.algorithm,
            "timestamp": self.timestamp
        }
        
        if self.key_id:
            result["key_id"] = self.key_id
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "MessageSignature":
        """Create from dictionary."""
        return cls(
            signature=data["signature"],
            algorithm=data["algorithm"],
            timestamp=data["timestamp"],
            key_id=data.get("key_id")
        )


class MCPMessageSigner:
    """MCP message signer using HMAC-SHA256.
    
    Provides cryptographic signing and verification of MCP messages
    for authentication and integrity protection.
    """
    
    def __init__(self, signing_key: str, key_id: Optional[str] = None):
        """Initialize message signer.
        
        Args:
            signing_key: Secret key for signing (base64 encoded)
            key_id: Optional key identifier
        """
        if not signing_key:
            raise ValidationError("Signing key is required")
        
        try:
            self.signing_key = base64.b64decode(signing_key)
        except Exception:
            # If not base64, use as-is
            self.signing_key = signing_key.encode('utf-8')
        
        self.key_id = key_id
        self.algorithm = "HMAC-SHA256"
    
    async def sign_message(self, message: MCPMessage) -> str:
        """Sign an MCP message.
        
        Args:
            message: Message to sign
            
        Returns:
            Base64-encoded signature
            
        Raises:
            AuthenticationError: If signing fails
        """
        try:
            # Create canonical message representation
            canonical_message = self._create_canonical_message(message)
            
            # Create HMAC signature
            signature_bytes = hmac.new(
                self.signing_key,
                canonical_message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Encode signature
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            
            # Create signature object
            signature_obj = MessageSignature(
                signature=signature_b64,
                algorithm=self.algorithm,
                timestamp=datetime.utcnow().isoformat(),
                key_id=self.key_id
            )
            
            # Return as JSON string
            return json.dumps(signature_obj.to_dict())
            
        except Exception as e:
            raise AuthenticationError(f"Message signing failed: {e}")
    
    async def verify_message(
        self, 
        message: MCPMessage, 
        signature_data: str,
        max_age_minutes: int = 5
    ) -> bool:
        """Verify message signature.
        
        Args:
            message: Message to verify
            signature_data: Signature data (JSON string)
            max_age_minutes: Maximum signature age in minutes
            
        Returns:
            True if signature is valid
        """
        try:
            # Parse signature
            signature_dict = json.loads(signature_data)
            signature_obj = MessageSignature.from_dict(signature_dict)
            
            # Check signature age
            if not self._check_signature_age(signature_obj.timestamp, max_age_minutes):
                return False
            
            # Check algorithm
            if signature_obj.algorithm != self.algorithm:
                return False
            
            # Check key ID if provided
            if self.key_id and signature_obj.key_id != self.key_id:
                return False
            
            # Create canonical message
            canonical_message = self._create_canonical_message(message)
            
            # Compute expected signature
            expected_signature_bytes = hmac.new(
                self.signing_key,
                canonical_message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            expected_signature_b64 = base64.b64encode(expected_signature_bytes).decode('utf-8')
            
            # Compare signatures using constant-time comparison
            return hmac.compare_digest(
                signature_obj.signature,
                expected_signature_b64
            )
            
        except Exception:
            return False
    
    def _create_canonical_message(self, message: MCPMessage) -> str:
        """Create canonical string representation of message.
        
        Args:
            message: Message to canonicalize
            
        Returns:
            Canonical string representation
        """
        # Create ordered dictionary for consistent serialization
        canonical_data = {
            "type": message.message_type.value,
            "headers": {
                "tenant-id": message.headers.tenant_id,
                "trace-id": message.headers.trace_id,
                "conversation-id": message.headers.conversation_id,
                "reply-to": message.headers.reply_to,
                "caller": message.headers.caller,
                "timestamp": message.headers.timestamp
            },
            "payload": message.payload
        }
        
        # Serialize with sorted keys for consistency
        return json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
    
    def _check_signature_age(self, timestamp_str: str, max_age_minutes: int) -> bool:
        """Check if signature is within acceptable age.
        
        Args:
            timestamp_str: ISO timestamp string
            max_age_minutes: Maximum age in minutes
            
        Returns:
            True if signature is not too old
        """
        try:
            signature_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            current_time = datetime.utcnow()
            
            # Handle timezone-naive timestamps
            if signature_time.tzinfo is None:
                signature_time = signature_time.replace(tzinfo=None)
                current_time = current_time.replace(tzinfo=None)
            
            age = current_time - signature_time
            max_age = timedelta(minutes=max_age_minutes)
            
            return age <= max_age
            
        except Exception:
            return False


class Ed25519MessageSigner:
    """Ed25519 message signer for high-security environments.
    
    Provides Ed25519 digital signatures for MCP messages when
    HMAC is not sufficient for security requirements.
    """
    
    def __init__(self, private_key: str, public_key: str, key_id: Optional[str] = None):
        """Initialize Ed25519 signer.
        
        Args:
            private_key: Ed25519 private key (base64 encoded)
            public_key: Ed25519 public key (base64 encoded)
            key_id: Optional key identifier
        """
        try:
            import nacl.signing
            import nacl.encoding
        except ImportError:
            raise ValidationError(
                "PyNaCl library required for Ed25519 signing. "
                "Install with: pip install pynacl"
            )
        
        try:
            self.private_key = nacl.signing.SigningKey(
                private_key,
                encoder=nacl.encoding.Base64Encoder
            )
            self.public_key = nacl.signing.VerifyKey(
                public_key,
                encoder=nacl.encoding.Base64Encoder
            )
        except Exception as e:
            raise ValidationError(f"Invalid Ed25519 keys: {e}")
        
        self.key_id = key_id
        self.algorithm = "Ed25519"
    
    async def sign_message(self, message: MCPMessage) -> str:
        """Sign message with Ed25519.
        
        Args:
            message: Message to sign
            
        Returns:
            Signature data as JSON string
        """
        try:
            import nacl.encoding
            
            # Create canonical message
            canonical_message = self._create_canonical_message(message)
            
            # Sign message
            signed = self.private_key.sign(
                canonical_message.encode('utf-8'),
                encoder=nacl.encoding.Base64Encoder
            )
            
            # Extract signature
            signature_b64 = signed.signature.decode('utf-8')
            
            # Create signature object
            signature_obj = MessageSignature(
                signature=signature_b64,
                algorithm=self.algorithm,
                timestamp=datetime.utcnow().isoformat(),
                key_id=self.key_id
            )
            
            return json.dumps(signature_obj.to_dict())
            
        except Exception as e:
            raise AuthenticationError(f"Ed25519 signing failed: {e}")
    
    async def verify_message(
        self, 
        message: MCPMessage, 
        signature_data: str,
        max_age_minutes: int = 5
    ) -> bool:
        """Verify Ed25519 signature.
        
        Args:
            message: Message to verify
            signature_data: Signature data
            max_age_minutes: Maximum signature age
            
        Returns:
            True if signature is valid
        """
        try:
            import nacl.encoding
            import nacl.exceptions
            
            # Parse signature
            signature_dict = json.loads(signature_data)
            signature_obj = MessageSignature.from_dict(signature_dict)
            
            # Check signature age and algorithm
            if (signature_obj.algorithm != self.algorithm or
                not self._check_signature_age(signature_obj.timestamp, max_age_minutes)):
                return False
            
            # Create canonical message
            canonical_message = self._create_canonical_message(message)
            
            # Verify signature
            self.public_key.verify(
                canonical_message.encode('utf-8'),
                signature_obj.signature,
                encoder=nacl.encoding.Base64Encoder
            )
            
            return True
            
        except (nacl.exceptions.BadSignatureError, Exception):
            return False
    
    def _create_canonical_message(self, message: MCPMessage) -> str:
        """Create canonical message representation."""
        # Same implementation as HMAC signer
        canonical_data = {
            "type": message.message_type.value,
            "headers": {
                "tenant-id": message.headers.tenant_id,
                "trace-id": message.headers.trace_id,
                "conversation-id": message.headers.conversation_id,
                "reply-to": message.headers.reply_to,
                "caller": message.headers.caller,
                "timestamp": message.headers.timestamp
            },
            "payload": message.payload
        }
        
        return json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
    
    def _check_signature_age(self, timestamp_str: str, max_age_minutes: int) -> bool:
        """Check signature age."""
        # Same implementation as HMAC signer
        try:
            signature_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            current_time = datetime.utcnow()
            
            if signature_time.tzinfo is None:
                signature_time = signature_time.replace(tzinfo=None)
                current_time = current_time.replace(tzinfo=None)
            
            age = current_time - signature_time
            max_age = timedelta(minutes=max_age_minutes)
            
            return age <= max_age
            
        except Exception:
            return False