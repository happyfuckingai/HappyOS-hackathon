"""
Message signing for HappyOS SDK.

Stub implementation for testing purposes.
"""

from typing import Dict, Any, Optional


class MCPMessageSigner:
    """MCP message signer."""
    
    def __init__(self, signing_key: Optional[str] = None):
        self.signing_key = signing_key
    
    async def sign_message(self, message: Dict[str, Any]) -> str:
        """Sign a message."""
        return "test_signature"
    
    async def verify_signature(self, message: Dict[str, Any], signature: str) -> bool:
        """Verify a message signature."""
        return True


class MessageSigner:
    """General message signer."""
    
    def __init__(self, signing_key: Optional[str] = None):
        self.signing_key = signing_key
    
    async def sign(self, data: bytes) -> str:
        """Sign data."""
        return "test_signature"
    
    async def verify(self, data: bytes, signature: str) -> bool:
        """Verify signature."""
        return True


class SignatureVerifier:
    """Signature verifier."""
    
    def __init__(self, public_key: Optional[str] = None):
        self.public_key = public_key
    
    async def verify(self, data: bytes, signature: str) -> bool:
        """Verify signature."""
        return True