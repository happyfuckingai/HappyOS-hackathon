"""
Authentication Manager - Authentication and Authorization for A2A Protocol

Handles JWT tokens, OAuth2 flows, and authorization for secure agent
communication in the HappyOS A2A Protocol implementation.
"""

import jwt
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .constants import (
    DEFAULT_CONFIG,
    AuthMethod,
    ErrorCode
)

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """
    Manages authentication and authorization for A2A Protocol.

    Handles JWT token generation/validation, OAuth2 flows, and
    capability-based authorization for secure agent communication.
    """

    def __init__(self,
                 jwt_secret: Optional[str] = None,
                 token_expiry: int = 3600):
        """
        Initialize AuthenticationManager.

        Args:
            jwt_secret: Secret key for JWT signing
            token_expiry: Token expiry time in seconds
        """
        self.jwt_secret = jwt_secret or "default-secret-change-in-production"
        self.token_expiry = token_expiry

        # Token cache for performance
        self._token_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("AuthenticationManager initialized")

    def generate_token(self,
                      agent_id: str,
                      capabilities: List[str],
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a JWT token for an agent.

        Args:
            agent_id: Agent identifier
            capabilities: List of agent capabilities
            metadata: Additional metadata to include in token

        Returns:
            JWT token string
        """
        try:
            now = int(time.time())

            payload = {
                "agent_id": agent_id,
                "capabilities": capabilities,
                "metadata": metadata or {},
                "iat": now,  # Issued at
                "exp": now + self.token_expiry,  # Expires at
                "iss": "happyos-a2a",  # Issuer
                "aud": "a2a-protocol",  # Audience
                "type": "agent_token"
            }

            token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")

            # Cache token info
            self._token_cache[token] = {
                "agent_id": agent_id,
                "capabilities": capabilities,
                "created_at": now,
                "expires_at": now + self.token_expiry
            }

            logger.debug(f"Generated JWT token for agent: {agent_id}")
            return token

        except Exception as e:
            logger.error(f"Token generation failed for agent {agent_id}: {e}")
            raise

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token.

        Args:
            token: JWT token to validate

        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Check cache first
            if token in self._token_cache:
                cached_info = self._token_cache[token]
                if cached_info["expires_at"] > int(time.time()):
                    return cached_info
                else:
                    # Token expired, remove from cache
                    del self._token_cache[token]

            # Validate token
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])

            # Verify token structure
            required_fields = ["agent_id", "capabilities", "exp", "iat"]
            for field in required_fields:
                if field not in payload:
                    logger.warning(f"Token missing required field: {field}")
                    return None

            # Check expiration
            if payload["exp"] < int(time.time()):
                logger.warning("Token has expired")
                return None

            # Cache valid token
            self._token_cache[token] = {
                "agent_id": payload["agent_id"],
                "capabilities": payload["capabilities"],
                "created_at": payload["iat"],
                "expires_at": payload["exp"]
            }

            logger.debug(f"Validated token for agent: {payload['agent_id']}")
            return {
                "agent_id": payload["agent_id"],
                "capabilities": payload["capabilities"],
                "metadata": payload.get("metadata", {}),
                "expires_at": payload["exp"]
            }

        except jwt.ExpiredSignatureError:
            logger.warning("Token signature has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def authorize_request(self,
                         token: str,
                         required_capability: str,
                         resource: Optional[str] = None) -> bool:
        """
        Authorize a request based on token capabilities.

        Args:
            token: JWT token
            required_capability: Required capability for the operation
            resource: Optional resource identifier

        Returns:
            True if authorized, False otherwise
        """
        try:
            token_info = self.validate_token(token)
            if not token_info:
                return False

            capabilities = token_info["capabilities"]

            # Check if agent has required capability
            if required_capability not in capabilities:
                logger.warning(f"Agent {token_info['agent_id']} lacks required capability: {required_capability}")
                return False

            # Additional authorization logic can be added here
            # (e.g., resource-specific permissions, time-based access, etc.)

            logger.debug(f"Authorized agent {token_info['agent_id']} for capability: {required_capability}")
            return True

        except Exception as e:
            logger.error(f"Authorization check failed: {e}")
            return False

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a JWT token.

        Args:
            token: Token to revoke

        Returns:
            True if revoked successfully, False otherwise
        """
        try:
            if token in self._token_cache:
                del self._token_cache[token]
                logger.debug("Token revoked from cache")
                return True
            else:
                logger.warning("Token not found in cache for revocation")
                return False

        except Exception as e:
            logger.error(f"Token revocation failed: {e}")
            return False

    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from cache.

        Returns:
            Number of tokens removed
        """
        try:
            current_time = int(time.time())
            expired_tokens = []

            for token, info in self._token_cache.items():
                if info["expires_at"] <= current_time:
                    expired_tokens.append(token)

            # Remove expired tokens
            for token in expired_tokens:
                del self._token_cache[token]

            if expired_tokens:
                logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")

            return len(expired_tokens)

        except Exception as e:
            logger.error(f"Token cleanup failed: {e}")
            return 0

    def get_authentication_stats(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        try:
            current_time = int(time.time())
            active_tokens = 0
            expired_tokens = 0

            for info in self._token_cache.values():
                if info["expires_at"] > current_time:
                    active_tokens += 1
                else:
                    expired_tokens += 1

            return {
                "cached_tokens": len(self._token_cache),
                "active_tokens": active_tokens,
                "expired_tokens": expired_tokens,
                "token_expiry_seconds": self.token_expiry,
                "cleanup_performed": expired_tokens > 0
            }

        except Exception as e:
            logger.error(f"Failed to get authentication stats: {e}")
            return {"error": str(e)}


# Global authentication manager instance
authentication_manager = AuthenticationManager()


class OAuth2Manager:
    """
    Manages OAuth2 authentication flows for A2A Protocol.

    Handles OAuth2 authorization code flows, token refresh,
    and integration with external identity providers.
    """

    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 authorization_base_url: str,
                 token_url: str):
        """
        Initialize OAuth2Manager.

        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            authorization_base_url: Base URL for authorization
            token_url: Token endpoint URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_base_url = authorization_base_url
        self.token_url = token_url

        logger.info("OAuth2Manager initialized")

    async def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth2 authorization URL."""
        # Implementation would integrate with actual OAuth2 provider
        return f"{self.authorization_base_url}/authorize?client_id={self.client_id}&redirect_uri={redirect_uri}&state={state}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        # Implementation would make actual HTTP request to token endpoint
        return {
            "access_token": "oauth2_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "oauth2_refresh_token"
        }


# Example usage and integration functions
async def example_authentication_flow():
    """Example of A2A authentication flow."""

    # Create authentication manager
    auth_manager = AuthenticationManager(jwt_secret="example-secret")

    # Generate token for agent
    token = auth_manager.generate_token(
        "example_agent",
        ["general", "analysis"],
        {"version": "1.0", "domain": "test"}
    )

    # Validate token
    token_info = auth_manager.validate_token(token)
    if token_info:
        print(f"Token valid for agent: {token_info['agent_id']}")

        # Check authorization
        authorized = auth_manager.authorize_request(token, "analysis")
        print(f"Agent authorized for analysis: {authorized}")
    else:
        print("Token validation failed")

    return auth_manager


# Integration with existing HappyOS components
def integrate_a2a_auth_with_happyos():
    """Integration points for A2A authentication with HappyOS."""

    # This would integrate the A2A authentication with HappyOS's existing
    # authentication and authorization systems

    integration_points = {
        "user_authentication": "Integrate JWT tokens with user sessions",
        "agent_authorization": "Use capability-based authorization for agents",
        "skill_permissions": "Map agent capabilities to skill permissions",
        "api_security": "Secure API endpoints with A2A authentication",
        "inter_agent_auth": "Authenticate all inter-agent communication"
    }

    return integration_points