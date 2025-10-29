"""
Identity Manager - Cryptographic Identity Management for A2A Protocol

Manages RSA key pairs and X.509 certificates for secure agent authentication
and communication in the HappyOS A2A Protocol implementation.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption
)
from cryptography.hazmat.backends import default_backend

from .constants import (
    RSA_KEY_SIZE,
    CERTIFICATE_VALIDITY_DAYS,
    DEFAULT_CONFIG,
    AgentRecord,
    ENV_CONFIG
)

logger = logging.getLogger(__name__)


class IdentityManager:
    """
    Manages agent identities and cryptographic credentials for A2A Protocol.

    This class handles:
    - RSA-2048 key pair generation and management
    - X.509 certificate creation and validation
    - Certificate storage and retrieval
    - Key rotation and certificate renewal
    """

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize IdentityManager with storage configuration."""
        self.storage_path = storage_path or get_config_value(
            ENV_CONFIG["A2A_STORAGE_PATH"],
            "./data/a2a/identities"
        )
        self.key_size = RSA_KEY_SIZE
        self.cert_validity = CERTIFICATE_VALIDITY_DAYS

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        # In-memory cache for loaded identities
        self._identity_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"IdentityManager initialized with storage path: {self.storage_path}")

    def generate_agent_identity(self, agent_id: str, common_name: Optional[str] = None,
                              organization: str = "HappyOS") -> Dict[str, Any]:
        """
        Generate a new RSA key pair and X.509 certificate for an agent.

        Args:
            agent_id: Unique identifier for the agent
            common_name: Human-readable name for the certificate
            organization: Organization name for the certificate

        Returns:
            Dictionary containing private key, certificate, and metadata
        """
        try:
            logger.info(f"Generating identity for agent: {agent_id}")

            # Generate RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.key_size,
                backend=default_backend()
            )

            public_key = private_key.public_key()

            # Create certificate subject and issuer
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, common_name or agent_id),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "A2A Protocol"),
            ])

            # Create certificate
            certificate = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                public_key
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=self.cert_validity)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress("127.0.0.1"),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256(), default_backend())

            # Create identity record
            identity_data = {
                "agent_id": agent_id,
                "common_name": common_name or agent_id,
                "organization": organization,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=self.cert_validity)).isoformat(),
                "key_size": self.key_size,
                "certificate_fingerprint": self._calculate_fingerprint(certificate),
                "status": "active"
            }

            # Serialize keys and certificate
            private_pem = private_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=NoEncryption()
            )

            public_pem = public_key.public_bytes(
                encoding=Encoding.PEM,
                format=PublicFormat.SubjectPublicKeyInfo
            )

            certificate_pem = certificate.public_bytes(Encoding.PEM)

            # Store identity
            identity_record = {
                "identity_data": identity_data,
                "private_key_pem": private_pem.decode('utf-8'),
                "public_key_pem": public_pem.decode('utf-8'),
                "certificate_pem": certificate_pem.decode('utf-8'),
                "private_key": private_key,
                "public_key": public_key,
                "certificate": certificate
            }

            # Save to disk
            self._save_identity(agent_id, identity_record)

            # Cache in memory
            self._identity_cache[agent_id] = identity_record

            logger.info(f"Successfully generated identity for agent: {agent_id}")
            return identity_record

        except Exception as e:
            logger.error(f"Failed to generate identity for agent {agent_id}: {e}")
            raise

    def load_agent_identity(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Load an existing agent identity from storage.

        Args:
            agent_id: Agent identifier to load

        Returns:
            Identity record if found, None otherwise
        """
        try:
            # Check cache first
            if agent_id in self._identity_cache:
                cached_identity = self._identity_cache[agent_id]
                # Validate certificate is not expired
                if self._is_certificate_valid(cached_identity["certificate"]):
                    return cached_identity
                else:
                    logger.warning(f"Cached certificate for agent {agent_id} is expired")
                    del self._identity_cache[agent_id]

            # Load from disk
            identity_path = os.path.join(self.storage_path, f"{agent_id}.json")
            if not os.path.exists(identity_path):
                logger.warning(f"No identity file found for agent: {agent_id}")
                return None

            with open(identity_path, 'r') as f:
                identity_data = json.load(f)

            # Load cryptographic objects
            private_key = load_pem_private_key(
                identity_data["private_key_pem"].encode('utf-8'),
                password=None,
                backend=default_backend()
            )

            public_key = load_pem_public_key(
                identity_data["public_key_pem"].encode('utf-8'),
                backend=default_backend()
            )

            certificate = x509.load_pem_x509_certificate(
                identity_data["certificate_pem"].encode('utf-8'),
                default_backend()
            )

            # Validate certificate
            if not self._is_certificate_valid(certificate):
                logger.error(f"Certificate for agent {agent_id} is expired or invalid")
                return None

            # Create identity record
            identity_record = {
                "identity_data": identity_data["identity_data"],
                "private_key_pem": identity_data["private_key_pem"],
                "public_key_pem": identity_data["public_key_pem"],
                "certificate_pem": identity_data["certificate_pem"],
                "private_key": private_key,
                "public_key": public_key,
                "certificate": certificate
            }

            # Cache for future use
            self._identity_cache[agent_id] = identity_record

            logger.info(f"Successfully loaded identity for agent: {agent_id}")
            return identity_record

        except Exception as e:
            logger.error(f"Failed to load identity for agent {agent_id}: {e}")
            return None

    def validate_agent_certificate(self, agent_id: str, certificate_pem: str) -> bool:
        """
        Validate an agent's certificate.

        Args:
            agent_id: Agent identifier
            certificate_pem: PEM-encoded certificate to validate

        Returns:
            True if certificate is valid, False otherwise
        """
        try:
            certificate = x509.load_pem_x509_certificate(
                certificate_pem.encode('utf-8'),
                default_backend()
            )

            # Check if certificate is for the correct agent
            common_name = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            if common_name != agent_id:
                logger.warning(f"Certificate CN ({common_name}) doesn't match agent ID ({agent_id})")
                return False

            # Check expiration
            if not self._is_certificate_valid(certificate):
                logger.warning(f"Certificate for agent {agent_id} is expired")
                return False

            # Check if certificate is in our trust store
            if not self._is_certificate_trusted(certificate):
                logger.warning(f"Certificate for agent {agent_id} is not trusted")
                return False

            return True

        except Exception as e:
            logger.error(f"Certificate validation failed for agent {agent_id}: {e}")
            return False

    def sign_data(self, agent_id: str, data: bytes) -> bytes:
        """
        Sign data using the agent's private key.

        Args:
            agent_id: Agent identifier
            data: Data to sign

        Returns:
            RSA signature of the data
        """
        try:
            identity = self.load_agent_identity(agent_id)
            if not identity:
                raise ValueError(f"No identity found for agent: {agent_id}")

            private_key = identity["private_key"]
            signature = private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            return signature

        except Exception as e:
            logger.error(f"Failed to sign data for agent {agent_id}: {e}")
            raise

    def verify_signature(self, agent_id: str, data: bytes, signature: bytes) -> bool:
        """
        Verify a signature using the agent's public key.

        Args:
            agent_id: Agent identifier
            data: Original data that was signed
            signature: Signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            identity = self.load_agent_identity(agent_id)
            if not identity:
                logger.error(f"No identity found for agent: {agent_id}")
                return False

            public_key = identity["public_key"]

            try:
                public_key.verify(
                    signature,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True

            except Exception as verify_error:
                logger.warning(f"Signature verification failed for agent {agent_id}: {verify_error}")
                return False

        except Exception as e:
            logger.error(f"Error verifying signature for agent {agent_id}: {e}")
            return False

    def rotate_agent_certificate(self, agent_id: str) -> bool:
        """
        Rotate an agent's certificate (generate new key pair and certificate).

        Args:
            agent_id: Agent identifier

        Returns:
            True if rotation successful, False otherwise
        """
        try:
            logger.info(f"Rotating certificate for agent: {agent_id}")

            # Generate new identity
            new_identity = self.generate_agent_identity(
                agent_id,
                common_name=f"{agent_id}_rotated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            )

            # Mark old identity as rotated
            old_identity_path = os.path.join(self.storage_path, f"{agent_id}.json")
            if os.path.exists(old_identity_path):
                with open(old_identity_path, 'r') as f:
                    old_data = json.load(f)

                old_data["identity_data"]["status"] = "rotated"
                old_data["identity_data"]["rotated_at"] = datetime.utcnow().isoformat()
                old_data["identity_data"]["rotation_reason"] = "scheduled_rotation"

                with open(old_identity_path, 'w') as f:
                    json.dump(old_data, f, indent=2)

            # Save new identity as current
            self._save_identity(agent_id, new_identity)

            # Update cache
            self._identity_cache[agent_id] = new_identity

            logger.info(f"Successfully rotated certificate for agent: {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Certificate rotation failed for agent {agent_id}: {e}")
            return False

    def get_certificate_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an agent's certificate.

        Args:
            agent_id: Agent identifier

        Returns:
            Certificate information or None if not found
        """
        try:
            identity = self.load_agent_identity(agent_id)
            if not identity:
                return None

            certificate = identity["certificate"]
            return {
                "agent_id": agent_id,
                "subject": certificate.subject.rfc4514_string(),
                "issuer": certificate.issuer.rfc4514_string(),
                "serial_number": str(certificate.serial_number),
                "not_valid_before": certificate.not_valid_before.isoformat(),
                "not_valid_after": certificate.not_valid_after.isoformat(),
                "fingerprint": self._calculate_fingerprint(certificate),
                "public_key_algorithm": certificate.public_key().public_key_bytes(
                    Encoding.DER, PublicFormat.SubjectPublicKeyInfo
                ).hex(),
                "is_expired": datetime.utcnow() > certificate.not_valid_after,
                "days_until_expiry": (certificate.not_valid_after - datetime.utcnow()).days,
                "signature_algorithm": certificate.signature_algorithm_oid._name
            }

        except Exception as e:
            logger.error(f"Failed to get certificate info for agent {agent_id}: {e}")
            return None

    def list_agent_identities(self) -> Dict[str, Dict[str, Any]]:
        """
        List all agent identities in storage.

        Returns:
            Dictionary mapping agent_id to certificate info
        """
        try:
            identities = {}

            if not os.path.exists(self.storage_path):
                return identities

            for filename in os.listdir(self.storage_path):
                if filename.endswith('.json'):
                    agent_id = filename[:-5]  # Remove .json extension
                    cert_info = self.get_certificate_info(agent_id)
                    if cert_info:
                        identities[agent_id] = cert_info

            return identities

        except Exception as e:
            logger.error(f"Failed to list agent identities: {e}")
            return {}

    def cleanup_expired_identities(self) -> int:
        """
        Remove expired identities from storage.

        Returns:
            Number of identities removed
        """
        try:
            removed_count = 0
            current_time = datetime.utcnow()

            if not os.path.exists(self.storage_path):
                return removed_count

            for filename in os.listdir(self.storage_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.storage_path, filename)
                    agent_id = filename[:-5]

                    try:
                        with open(filepath, 'r') as f:
                            identity_data = json.load(f)

                        expires_at = datetime.fromisoformat(identity_data["identity_data"]["expires_at"])
                        if current_time > expires_at:
                            # Remove expired identity file
                            os.remove(filepath)

                            # Remove from cache if present
                            self._identity_cache.pop(agent_id, None)

                            removed_count += 1
                            logger.info(f"Removed expired identity for agent: {agent_id}")

                    except Exception as e:
                        logger.error(f"Error processing identity file {filename}: {e}")

            logger.info(f"Cleaned up {removed_count} expired identities")
            return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired identities: {e}")
            return 0

    def _save_identity(self, agent_id: str, identity_record: Dict[str, Any]) -> None:
        """Save identity record to disk storage."""
        try:
            filepath = os.path.join(self.storage_path, f"{agent_id}.json")

            # Prepare data for JSON serialization
            save_data = {
                "identity_data": identity_record["identity_data"],
                "private_key_pem": identity_record["private_key_pem"],
                "public_key_pem": identity_record["public_key_pem"],
                "certificate_pem": identity_record["certificate_pem"]
            }

            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)

            logger.debug(f"Saved identity for agent: {agent_id}")

        except Exception as e:
            logger.error(f"Failed to save identity for agent {agent_id}: {e}")
            raise

    def _calculate_fingerprint(self, certificate: x509.Certificate) -> str:
        """Calculate SHA-256 fingerprint of certificate."""
        try:
            fingerprint = certificate.fingerprint(hashes.SHA256())
            return fingerprint.hex()
        except Exception as e:
            logger.error(f"Failed to calculate certificate fingerprint: {e}")
            return ""

    def _is_certificate_valid(self, certificate: x509.Certificate) -> bool:
        """Check if certificate is valid (not expired, properly signed)."""
        try:
            current_time = datetime.utcnow()

            # Check expiration
            if current_time < certificate.not_valid_before:
                return False

            if current_time > certificate.not_valid_after:
                return False

            # Additional validation can be added here
            # (e.g., certificate chain validation, revocation checks)

            return True

        except Exception as e:
            logger.error(f"Certificate validation error: {e}")
            return False

    def _is_certificate_trusted(self, certificate: x509.Certificate) -> bool:
        """
        Check if certificate is trusted (basic implementation).
        In production, this should validate against a trust store.
        """
        try:
            # For now, we trust all certificates we issued
            # In production, implement proper trust store validation
            return True
        except Exception as e:
            logger.error(f"Certificate trust validation error: {e}")
            return False

    def get_identity_statistics(self) -> Dict[str, Any]:
        """Get statistics about managed identities."""
        try:
            identities = self.list_agent_identities()

            total_identities = len(identities)
            active_identities = sum(1 for info in identities.values() if not info["is_expired"])
            expired_identities = total_identities - active_identities

            # Find soon-to-expire certificates (within 30 days)
            current_time = datetime.utcnow()
            soon_to_expire = 0

            for info in identities.values():
                expiry_date = datetime.fromisoformat(info["not_valid_after"])
                if 0 < (expiry_date - current_time).days <= 30:
                    soon_to_expire += 1

            return {
                "total_identities": total_identities,
                "active_identities": active_identities,
                "expired_identities": expired_identities,
                "soon_to_expire": soon_to_expire,
                "storage_path": self.storage_path,
                "cache_size": len(self._identity_cache),
                "rsa_key_size": self.key_size,
                "default_validity_days": self.cert_validity
            }

        except Exception as e:
            logger.error(f"Failed to get identity statistics: {e}")
            return {
                "error": str(e),
                "storage_path": self.storage_path
            }


# Utility function to get config values
def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value from environment variables."""
    import os
    return os.getenv(key, default)