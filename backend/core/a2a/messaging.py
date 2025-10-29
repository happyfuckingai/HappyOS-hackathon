"""
Message Manager - Secure Message Encryption and Processing for A2A Protocol

Handles secure message creation, encryption/decryption, and routing for the
Agent-to-Agent communication protocol in HappyOS.
"""

import json
import uuid
import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

from .constants import (
    MessageType,
    MessagePriority,
    MessageHeader,
    ContentType,
    CompressionType,
    EncryptionAlgorithm,
    HashAlgorithm,
    DEFAULT_CONFIG,
    MessagePayload,
    SecurityContext,
    AgentType,
    CrossAgentWorkflowType,
    AgentCapability
)

logger = logging.getLogger(__name__)


class MessageManager:
    """
    Manages secure message creation, encryption, and processing for A2A Protocol.

    This class handles:
    - Message creation with proper headers and metadata
    - AES-256-GCM encryption/decryption
    - Message signing and verification
    - Message routing and delivery
    - Compression and serialization
    """

    def __init__(self):
        """Initialize MessageManager."""
        self.backend = default_backend()
        self._session_keys: Dict[str, bytes] = {}  # Cache for session keys
        logger.info("MessageManager initialized")

    def create_message(self,
                      sender_id: str,
                      recipient_id: str,
                      message_type: MessageType,
                      payload: MessagePayload,
                      priority: MessagePriority = MessagePriority.NORMAL,
                      ttl: int = 3600,
                      correlation_id: Optional[str] = None,
                      workflow_id: Optional[str] = None,
                      task_id: Optional[str] = None,
                      content_type: ContentType = ContentType.JSON) -> Dict[str, Any]:
        """
        Create a new message with proper headers and structure.

        Args:
            sender_id: ID of the sending agent
            recipient_id: ID of the receiving agent
            message_type: Type of message (request, response, notification)
            payload: Message payload data
            priority: Message priority level
            ttl: Time to live in seconds
            correlation_id: ID for correlating related messages
            workflow_id: Associated workflow ID
            task_id: Associated task ID
            content_type: Content type of the payload

        Returns:
            Complete message structure ready for encryption
        """
        try:
            message_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()

            # Create message headers
            headers = {
                MessageHeader.MESSAGE_ID: message_id,
                MessageHeader.SENDER_ID: sender_id,
                MessageHeader.RECIPIENT_ID: recipient_id,
                MessageHeader.TIMESTAMP: timestamp,
                MessageHeader.MESSAGE_TYPE: message_type.value,
                MessageHeader.PRIORITY: priority.value,
                MessageHeader.TTL: ttl,
                MessageHeader.CONTENT_TYPE: content_type.value
            }

            # Add optional headers
            if correlation_id:
                headers[MessageHeader.CORRELATION_ID] = correlation_id
            if workflow_id:
                headers[MessageHeader.WORKFLOW_ID] = workflow_id
            if task_id:
                headers[MessageHeader.TASK_ID] = task_id

            # Create complete message
            message = {
                "header": headers,
                "payload": payload,
                "metadata": {
                    "protocol_version": DEFAULT_CONFIG["protocol_version"],
                    "created_at": timestamp,
                    "encrypted": False,
                    "compressed": False,
                    "signed": False
                }
            }

            logger.debug(f"Created message {message_id} from {sender_id} to {recipient_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            raise

    def encrypt_message(self,
                       message: Dict[str, Any],
                       recipient_public_key: bytes,
                       sender_private_key: bytes) -> Dict[str, Any]:
        """
        Encrypt a message using AES-256-GCM with RSA key exchange.

        Args:
            message: Message to encrypt
            recipient_public_key: RSA public key of recipient for session key encryption
            sender_private_key: RSA private key of sender for signing

        Returns:
            Encrypted message with encryption metadata
        """
        try:
            # Generate session key for AES-256-GCM
            session_key = AESGCM.generate_key(bit_length=256)

            # Generate random nonce
            nonce = os.urandom(12)  # 96 bits for GCM

            # Serialize message payload for encryption
            payload_json = json.dumps(message["payload"]).encode('utf-8')
            metadata_json = json.dumps(message["metadata"]).encode('utf-8')

            # Encrypt payload and metadata separately
            aesgcm = AESGCM(session_key)

            encrypted_payload = aesgcm.encrypt(nonce, payload_json, None)
            encrypted_metadata = aesgcm.encrypt(nonce, metadata_json, None)

            # Encrypt session key with recipient's public key (RSA-OAEP)
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            encrypted_session_key = recipient_public_key.encrypt(
                session_key,
                rsa_padding.OAEP(
                    mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # Create signature of the encrypted data
            signature_data = nonce + encrypted_session_key + encrypted_payload + encrypted_metadata
            from cryptography.hazmat.primitives.asymmetric import rsa
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=self.backend
            )

            signature = private_key.sign(
                signature_data,
                rsa_padding.PSS(
                    mgf=rsa_padding.MGF1(hashes.SHA256()),
                    salt_length=rsa_padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # Create encrypted message
            encrypted_message = {
                "header": message["header"],
                "encrypted_payload": encrypted_payload.hex(),
                "encrypted_metadata": encrypted_metadata.hex(),
                "encrypted_session_key": encrypted_session_key.hex(),
                "nonce": nonce.hex(),
                "signature": signature.hex(),
                "encryption": {
                    "algorithm": EncryptionAlgorithm.AES_256_GCM.value,
                    "key_size": 256,
                    "hash_algorithm": HashAlgorithm.SHA256.value
                }
            }

            logger.debug(f"Encrypted message {message['header'][MessageHeader.MESSAGE_ID]}")
            return encrypted_message

        except Exception as e:
            logger.error(f"Message encryption failed: {e}")
            raise

    def decrypt_message(self,
                       encrypted_message: Dict[str, Any],
                       recipient_private_key: bytes,
                       sender_public_key: bytes) -> Dict[str, Any]:
        """
        Decrypt a message using AES-256-GCM.

        Args:
            encrypted_message: Encrypted message to decrypt
            recipient_private_key: RSA private key of recipient
            sender_public_key: RSA public key of sender for signature verification

        Returns:
            Decrypted message with original payload
        """
        try:
            # Extract encrypted components
            encrypted_session_key = bytes.fromhex(encrypted_message["encrypted_session_key"])
            nonce = bytes.fromhex(encrypted_message["nonce"])
            encrypted_payload = bytes.fromhex(encrypted_message["encrypted_payload"])
            encrypted_metadata = bytes.fromhex(encrypted_message["encrypted_metadata"])
            signature = bytes.fromhex(encrypted_message["signature"])

            # Decrypt session key using recipient's private key
            from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
            session_key = recipient_private_key.decrypt(
                encrypted_session_key,
                rsa_padding.OAEP(
                    mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # Verify signature before decryption
            signature_data = nonce + encrypted_session_key + encrypted_payload + encrypted_metadata
            try:
                sender_public_key.verify(
                    signature,
                    signature_data,
                    rsa_padding.PSS(
                        mgf=rsa_padding.MGF1(hashes.SHA256()),
                        salt_length=rsa_padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            except Exception as verify_error:
                raise ValueError(f"Message signature verification failed: {verify_error}")

            # Decrypt payload and metadata
            aesgcm = AESGCM(session_key)

            decrypted_payload = aesgcm.decrypt(nonce, encrypted_payload, None)
            decrypted_metadata = aesgcm.decrypt(nonce, encrypted_metadata, None)

            # Parse decrypted data
            payload = json.loads(decrypted_payload.decode('utf-8'))
            metadata = json.loads(decrypted_metadata.decode('utf-8'))

            # Reconstruct original message
            decrypted_message = {
                "header": encrypted_message["header"],
                "payload": payload,
                "metadata": metadata
            }

            logger.debug(f"Decrypted message {encrypted_message['header'][MessageHeader.MESSAGE_ID]}")
            return decrypted_message

        except Exception as e:
            logger.error(f"Message decryption failed: {e}")
            raise

    def validate_message(self, message: Dict[str, Any]) -> bool:
        """
        Validate message structure and required fields.

        Args:
            message: Message to validate

        Returns:
            True if message is valid, False otherwise
        """
        try:
            # Check required header fields
            required_headers = [
                MessageHeader.MESSAGE_ID,
                MessageHeader.SENDER_ID,
                MessageHeader.RECIPIENT_ID,
                MessageHeader.TIMESTAMP,
                MessageHeader.MESSAGE_TYPE
            ]

            headers = message.get("header", {})
            for header in required_headers:
                if header not in headers or not headers[header]:
                    logger.error(f"Missing required header: {header}")
                    return False

            # Validate message type
            valid_types = [mt.value for mt in MessageType]
            if headers[MessageHeader.MESSAGE_TYPE] not in valid_types:
                logger.error(f"Invalid message type: {headers[MessageHeader.MESSAGE_TYPE]}")
                return False

            # Validate priority
            valid_priorities = [mp.value for mp in MessagePriority]
            if headers.get(MessageHeader.PRIORITY) not in valid_priorities:
                logger.warning(f"Invalid priority, defaulting to NORMAL: {headers.get(MessageHeader.PRIORITY)}")
                headers[MessageHeader.PRIORITY] = MessagePriority.NORMAL.value

            # Check TTL
            ttl = headers.get(MessageHeader.TTL, 3600)
            if not isinstance(ttl, int) or ttl <= 0:
                logger.error(f"Invalid TTL: {ttl}")
                return False

            # Validate payload exists
            if "payload" not in message:
                logger.error("Message missing payload")
                return False

            return True

        except Exception as e:
            logger.error(f"Message validation error: {e}")
            return False

    def compress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress message payload if beneficial.

        Args:
            message: Message to compress

        Returns:
            Message with compressed payload if compression is beneficial
        """
        try:
            payload_str = json.dumps(message["payload"])
            payload_size = len(payload_str.encode('utf-8'))

            # Only compress if payload is large enough
            if payload_size > 1024:  # 1KB threshold
                import gzip

                compressed_payload = gzip.compress(payload_str.encode('utf-8'))
                compressed_size = len(compressed_payload)

                # Only use compression if it actually reduces size
                if compressed_size < payload_size:
                    message["payload"] = compressed_payload.hex()
                    message["metadata"]["compressed"] = True
                    message["metadata"]["compression_algorithm"] = CompressionType.GZIP.value
                    message["metadata"]["original_size"] = payload_size
                    message["metadata"]["compressed_size"] = compressed_size

                    logger.debug(f"Compressed message payload: {payload_size} -> {compressed_size} bytes")
                else:
                    logger.debug(f"Compression not beneficial: {payload_size} -> {compressed_size} bytes")
            else:
                logger.debug(f"Payload too small for compression: {payload_size} bytes")

            return message

        except Exception as e:
            logger.error(f"Message compression failed: {e}")
            return message

    def decompress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompress message payload if compressed.

        Args:
            message: Message to decompress

        Returns:
            Message with decompressed payload
        """
        try:
            if message.get("metadata", {}).get("compressed", False):
                import gzip

                compressed_payload = bytes.fromhex(message["payload"])
                decompressed_payload = gzip.decompress(compressed_payload)

                message["payload"] = json.loads(decompressed_payload.decode('utf-8'))
                message["metadata"]["compressed"] = False
                del message["metadata"]["compression_algorithm"]
                del message["metadata"]["original_size"]
                del message["metadata"]["compressed_size"]

                logger.debug("Decompressed message payload")

            return message

        except Exception as e:
            logger.error(f"Message decompression failed: {e}")
            return message

    def calculate_message_hash(self, message: Dict[str, Any]) -> str:
        """
        Calculate SHA-256 hash of message for integrity checking.

        Args:
            message: Message to hash

        Returns:
            Hex string of SHA-256 hash
        """
        try:
            # Create canonical representation of message
            canonical_message = {
                "header": message.get("header", {}),
                "payload": message.get("payload", {}),
                "metadata": message.get("metadata", {})
            }

            message_str = json.dumps(canonical_message, sort_keys=True)
            message_bytes = message_str.encode('utf-8')

            # Calculate hash
            digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
            digest.update(message_bytes)
            hash_bytes = digest.finalize()

            return hash_bytes.hex()

        except Exception as e:
            logger.error(f"Message hash calculation failed: {e}")
            return ""

    def create_response_message(self,
                              original_message: Dict[str, Any],
                              response_payload: MessagePayload,
                              success: bool = True,
                              error_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a response message for a given request.

        Args:
            original_message: Original request message
            response_payload: Response payload data
            success: Whether the operation was successful
            error_message: Error message if operation failed

        Returns:
            Response message
        """
        try:
            original_header = original_message["header"]

            # Create response payload
            if success:
                payload = response_payload
            else:
                payload = {
                    "success": False,
                    "error": error_message or "Unknown error",
                    "original_request_id": original_header[MessageHeader.MESSAGE_ID]
                }

            # Create response message
            response = self.create_message(
                sender_id=original_header[MessageHeader.RECIPIENT_ID],
                recipient_id=original_header[MessageHeader.SENDER_ID],
                message_type=MessageType.RESPONSE,
                payload=payload,
                priority=MessagePriority.NORMAL,
                correlation_id=original_header.get(MessageHeader.CORRELATION_ID),
                workflow_id=original_header.get(MessageHeader.WORKFLOW_ID),
                task_id=original_header.get(MessageHeader.TASK_ID)
            )

            # Add response-specific metadata
            response["metadata"]["response_to"] = original_header[MessageHeader.MESSAGE_ID]
            response["metadata"]["success"] = success

            logger.debug(f"Created response message for request {original_header[MessageHeader.MESSAGE_ID]}")
            return response

        except Exception as e:
            logger.error(f"Failed to create response message: {e}")
            raise

    def create_notification_message(self,
                                  sender_id: str,
                                  notification_type: str,
                                  notification_data: MessagePayload,
                                  priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """
        Create a notification message for broadcasting.

        Args:
            sender_id: ID of the sending agent
            notification_type: Type of notification
            notification_data: Notification payload data
            priority: Message priority level

        Returns:
            Notification message
        """
        try:
            payload = {
                "notification_type": notification_type,
                "data": notification_data,
                "timestamp": datetime.utcnow().isoformat()
            }

            message = self.create_message(
                sender_id=sender_id,
                recipient_id="*",  # Broadcast to all
                message_type=MessageType.NOTIFICATION,
                payload=payload,
                priority=priority
            )

            message["metadata"]["broadcast"] = True
            message["metadata"]["notification_category"] = notification_type

            logger.debug(f"Created notification message: {notification_type}")
            return message

        except Exception as e:
            logger.error(f"Failed to create notification message: {e}")
            raise

    async def process_message_batch(self,
                                  messages: List[Dict[str, Any]],
                                  max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """
        Process a batch of messages concurrently.

        Args:
            messages: List of messages to process
            max_concurrent: Maximum concurrent processing

        Returns:
            List of processed messages
        """
        try:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_single_message(msg: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    try:
                        # Validate message
                        if not self.validate_message(msg):
                            msg["metadata"]["validation_error"] = "Invalid message structure"
                            return msg

                        # Decompress if needed
                        msg = self.decompress_message(msg)

                        return msg

                    except Exception as e:
                        logger.error(f"Error processing message {msg.get('header', {}).get('message_id', 'unknown')}: {e}")
                        msg["metadata"]["processing_error"] = str(e)
                        return msg

            # Process messages concurrently
            tasks = [process_single_message(msg) for msg in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions that occurred
            processed_messages = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed for message {i}: {result}")
                    # Return original message with error metadata
                    original_msg = messages[i]
                    original_msg["metadata"]["batch_processing_error"] = str(result)
                    processed_messages.append(original_msg)
                else:
                    processed_messages.append(result)

            logger.info(f"Batch processed {len(messages)} messages")
            return processed_messages

        except Exception as e:
            logger.error(f"Batch message processing failed: {e}")
            return messages

    def get_message_statistics(self) -> Dict[str, Any]:
        """Get statistics about message processing."""
        return {
            "messages_created": getattr(self, '_messages_created', 0),
            "messages_encrypted": getattr(self, '_messages_encrypted', 0),
            "messages_decrypted": getattr(self, '_messages_decrypted', 0),
            "encryption_failures": getattr(self, '_encryption_failures', 0),
            "decryption_failures": getattr(self, '_decryption_failures', 0),
            "validation_failures": getattr(self, '_validation_failures', 0),
            "compression_ratio": getattr(self, '_total_compression_ratio', 0.0),
            "session_keys_cached": len(self._session_keys)
        }

    # Agent-specific message creation methods

    def create_agent_svea_message(self,
                                 sender_id: str,
                                 recipient_id: str,
                                 action: str,
                                 data: Dict[str, Any],
                                 tenant_id: str,
                                 priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """Create Agent Svea specific message."""
        message_type_mapping = {
            "bas_validation": MessageType.AGENT_SVEA_BAS_VALIDATION,
            "erp_sync": MessageType.AGENT_SVEA_ERP_SYNC,
            "skatteverket_submission": MessageType.AGENT_SVEA_SKATTEVERKET_SUBMISSION,
            "compliance_check": MessageType.AGENT_SVEA_COMPLIANCE_CHECK
        }
        
        message_type = message_type_mapping.get(action, MessageType.REQUEST)
        
        payload = {
            "agent_type": AgentType.AGENT_SVEA.value,
            "action": action,
            "data": data,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            priority=priority
        )

    def create_felicias_finance_message(self,
                                       sender_id: str,
                                       recipient_id: str,
                                       action: str,
                                       data: Dict[str, Any],
                                       tenant_id: str,
                                       priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """Create Felicia's Finance specific message."""
        message_type_mapping = {
            "crypto_trade": MessageType.FELICIAS_FINANCE_CRYPTO_TRADE,
            "portfolio_analysis": MessageType.FELICIAS_FINANCE_PORTFOLIO_ANALYSIS,
            "banking_transaction": MessageType.FELICIAS_FINANCE_BANKING_TRANSACTION,
            "risk_assessment": MessageType.FELICIAS_FINANCE_RISK_ASSESSMENT
        }
        
        message_type = message_type_mapping.get(action, MessageType.REQUEST)
        
        payload = {
            "agent_type": AgentType.FELICIAS_FINANCE.value,
            "action": action,
            "data": data,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            priority=priority
        )

    def create_meetmind_message(self,
                               sender_id: str,
                               recipient_id: str,
                               action: str,
                               data: Dict[str, Any],
                               tenant_id: str,
                               priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """Create MeetMind specific message."""
        message_type_mapping = {
            "transcript_analysis": MessageType.MEETMIND_TRANSCRIPT_ANALYSIS,
            "summary_request": MessageType.MEETMIND_SUMMARY_REQUEST,
            "insight_generation": MessageType.MEETMIND_INSIGHT_GENERATION,
            "action_item_extraction": MessageType.MEETMIND_ACTION_ITEM_EXTRACTION
        }
        
        message_type = message_type_mapping.get(action, MessageType.REQUEST)
        
        payload = {
            "agent_type": AgentType.MEETMIND.value,
            "action": action,
            "data": data,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            priority=priority
        )

    def create_cross_agent_workflow_message(self,
                                           sender_id: str,
                                           workflow_type: CrossAgentWorkflowType,
                                           workflow_data: Dict[str, Any],
                                           participating_agents: List[str],
                                           tenant_id: str,
                                           workflow_id: Optional[str] = None,
                                           priority: MessagePriority = MessagePriority.HIGH) -> Dict[str, Any]:
        """Create cross-agent workflow message."""
        workflow_id = workflow_id or str(uuid.uuid4())
        
        payload = {
            "workflow_type": workflow_type.value,
            "workflow_id": workflow_id,
            "workflow_data": workflow_data,
            "participating_agents": participating_agents,
            "tenant_id": tenant_id,
            "initiated_by": sender_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=sender_id,
            recipient_id="orchestrator",  # Send to orchestrator for coordination
            message_type=MessageType.CROSS_AGENT_WORKFLOW_START,
            payload=payload,
            priority=priority,
            workflow_id=workflow_id
        )

    def create_agent_capability_discovery_message(self,
                                                 sender_id: str,
                                                 requested_capabilities: List[AgentCapability],
                                                 tenant_id: str) -> Dict[str, Any]:
        """Create agent capability discovery message."""
        payload = {
            "action": "capability_discovery",
            "requested_capabilities": [cap.value for cap in requested_capabilities],
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=sender_id,
            recipient_id="*",  # Broadcast to all agents
            message_type=MessageType.DISCOVERY,
            payload=payload,
            priority=MessagePriority.NORMAL
        )

    def create_agent_registration_message(self,
                                        agent_id: str,
                                        agent_type: AgentType,
                                        capabilities: List[AgentCapability],
                                        endpoint: str,
                                        tenant_id: str,
                                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create agent registration message."""
        payload = {
            "agent_id": agent_id,
            "agent_type": agent_type.value,
            "capabilities": [cap.value for cap in capabilities],
            "endpoint": endpoint,
            "tenant_id": tenant_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.create_message(
            sender_id=agent_id,
            recipient_id="agent_registry",
            message_type=MessageType.REGISTRATION,
            payload=payload,
            priority=MessagePriority.HIGH
        )


# Global message manager instance
message_manager = MessageManager()