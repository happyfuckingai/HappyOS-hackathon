"""
Summarizer Client Module

Klient för kommunikation med summarizer-agenten via MCP-protokoll.
Centraliserar all summarizer-relaterad kommunikation från andra delar av systemet.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from uuid import uuid4

import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SummarizerClient:
    """
    Klient för kommunikation med summarizer-ui-agenten via MCP.

    Centraliserar all logik för att anropa summarizer-agenten och hanterar
    olika typer av summarizer-operationer.
    """

    def __init__(self, mcp_integration=None):
        """
        Initiera SummarizerClient.

        Args:
            mcp_integration: MCPToolsIntegration instans för kommunikation
        """
        self.mcp_integration = mcp_integration
        self.logger = logging.getLogger(__name__)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._redis_client: Optional[redis.Redis] = None
        self._base_url = os.getenv("MEETMIND_MCP_URL", "http://localhost:8150")
        self._api_key = os.getenv("MCP_API_KEY")
        self._redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    def set_mcp_integration(self, mcp_integration):
        """Sätt MCP-integration för kommunikation med summarizer-agenten"""
        self.mcp_integration = mcp_integration

    async def summarize_conversation_async(self, transcript: str,
                                         style: str = "detailed",
                                         include_visuals: bool = True) -> str:
        """
        Sammanfatta en konversation via summarizer-agenten.

        Args:
            transcript: Konversationstext att sammanfatta
            style: Summeringsstil ('detailed', 'brief', 'bullet_points')
            include_visuals: Om visuella element ska inkluderas

        Returns:
            Sammanfattad text eller felmeddelande
        """
        if not self.mcp_integration:
            return "Summeringsagenten är inte tillgänglig för tillfället."

        try:
            # Anropa summarizer-ui-servern via MCP
            result = await self.mcp_integration.call_tool(
                "summarize_conversation",
                {
                    "transcript": transcript,
                    "style": style,
                    "include_visuals": include_visuals
                }
            )

            # Returnera UI-renderad summering för frontend
            if result and result.content:
                return f"Summering genererad: {result.content[0].text[:200]}..."
            else:
                return "Ingen summering kunde genereras."

        except Exception as e:
            self.logger.error(f"Summeringsagent-kommunikation misslyckades: {e}")
            return "Tekniskt fel vid kommunikation med summeringsagenten."

    def summarize_conversation(self, transcript: str,
                             style: str = "detailed",
                             include_visuals: bool = True) -> str:
        """
        Synkron wrapper för att sammanfatta konversation.

        Args:
            transcript: Konversationstext att sammanfatta
            style: Summeringsstil
            include_visuals: Om visuella element ska inkluderas

        Returns:
            Sammanfattad text eller felmeddelande
        """
        try:
            asyncio.get_running_loop()
            return "Summering begärd. Bearbetar i bakgrunden..."
        except RuntimeError:
            return asyncio.run(self.summarize_conversation_async(
                transcript, style, include_visuals
            ))

    async def stream_transcript_chunk_async(
        self,
        meeting_id: str,
        content: str,
        *,
        speaker: Optional[str] = None,
        is_final: bool = False,
        sequence: Optional[int] = None,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Stream a transcript chunk to the Meetmind MCP server for meeting memory storage.

        Args:
            meeting_id: The meeting identifier (maps to LiveKit room or tenant session)
            content: Transcript text chunk
            speaker: Optional speaker label/participant identity
            is_final: Flag marking transcript stability
            sequence: Monotonic sequence number to preserve ordering downstream
            start_time_ms: Start timestamp of the chunk in milliseconds
            end_time_ms: End timestamp of the chunk in milliseconds
            confidence: Confidence score between 0 and 1 (if provided by STT)
            metadata: Arbitrary metadata to persist with the chunk

        Returns:
            Parsed JSON response from MCP server
        """
        if not meeting_id:
            raise ValueError("meeting_id is required to stream transcript chunks")
        if not content:
            raise ValueError("content must contain transcript text")

        client = await self._get_http_client()
        payload: Dict[str, Any] = {
            "content": content,
            "speaker": speaker,
            "is_final": is_final,
            "sequence": sequence,
            "start_time_ms": start_time_ms,
            "end_time_ms": end_time_ms,
            "confidence": confidence,
            "metadata": metadata or {},
        }

        if "chunk_id" not in payload["metadata"]:
            payload["metadata"]["chunk_id"] = uuid4().hex

        response = await client.post(
            f"/meetmind/meetings/{meeting_id}/transcripts",
            json=payload,
            headers=self._build_auth_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    async def get_conversation_context_async(self, meeting_id: str, persona: str) -> Dict[str, Any]:
        """
        Fetch conversation context and summary for a given persona.

        Reads from Redis cache populated by SummarizerIngestWorker.
        Used by agent to read state without direct transcript access.

        Args:
            meeting_id: Meeting identifier
            persona: Persona to retrieve context for ("PO", "Eng", "CS", "Exec")

        Returns:
            ConversationContext object as dict

        Raises:
            ValueError: If meeting_id or persona is invalid
            RuntimeError: If Redis connection fails
        """
        if not meeting_id:
            raise ValueError("meeting_id is required")
        if persona not in ["PO", "Eng", "CS", "Exec"]:
            raise ValueError(f"Invalid persona: {persona}. Must be one of: PO, Eng, CS, Exec")

        try:
            redis_client = await self._get_redis_client()
            cache_key = f"meetmind:cache:{meeting_id}:{persona}:context"

            cached_data = await redis_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
            else:
                # Return empty context if no data available yet
                return {
                    "meeting_id": meeting_id,
                    "persona": persona,
                    "summary": "No conversation context available yet.",
                    "topics": [],
                    "actions": [],
                    "risks": [],
                    "phase": "scoping",
                    "energy_level": "medium",
                    "updated_at": int(asyncio.get_event_loop().time() * 1000),
                    "confidence_score": 0.0
                }

        except Exception as e:
            self.logger.error(f"Failed to get conversation context for {meeting_id}/{persona}: {e}")
            raise RuntimeError(f"Failed to retrieve conversation context: {e}")

    async def get_visuals_async(self, meeting_id: str) -> list:
        """
        Fetch latest visuals for a meeting (phase bars, topic cards, highlights, action widgets).

        Reads from Redis cache populated by SummarizerIngestWorker.
        Used by agent overlay and frontend.

        Args:
            meeting_id: Meeting identifier

        Returns:
            Array of Visual objects

        Raises:
            ValueError: If meeting_id is invalid
            RuntimeError: If Redis connection fails
        """
        if not meeting_id:
            raise ValueError("meeting_id is required")

        try:
            redis_client = await self._get_redis_client()
            cache_key = f"meetmind:cache:{meeting_id}:visuals"

            cached_data = await redis_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
            else:
                # Return empty visuals if no data available yet
                return []

        except Exception as e:
            self.logger.error(f"Failed to get visuals for {meeting_id}: {e}")
            raise RuntimeError(f"Failed to retrieve visuals: {e}")

    async def publish_agent_artifact(self, meeting_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish a structured agent artifact (e.g., web search result, document summary)
        so the summarizer worker can convert it to MCP UI components.

        Args:
            meeting_id: Active meeting identifier
            artifact: Dict with artifact metadata (title, abstract, source, url, etc.)

        Returns:
            Dict with success flag and artifact_id
        """
        if not meeting_id:
            raise ValueError("meeting_id is required")
        if not artifact or not isinstance(artifact, dict):
            raise ValueError("artifact payload must be a non-empty dict")

        try:
            redis_client = await self._get_redis_client()
            artifact_id = artifact.get("artifact_id") or f"artifact-{uuid4().hex[:8]}"

            payload = {
                "artifact_id": artifact_id,
                "meeting_id": meeting_id,
                "title": artifact.get("title"),
                "abstract": artifact.get("abstract"),
                "summary": artifact.get("summary"),
                "source": artifact.get("source"),
                "url": artifact.get("url"),
                "artifacts": artifact.get("artifacts", []),
                "persona_filter": artifact.get("persona_filter"),
                "kind": artifact.get("kind", "agent_artifact"),
                "timestamp_ms": int(asyncio.get_event_loop().time() * 1000),
                "metadata": artifact.get("metadata", {}),
                "received_at": artifact.get("received_at"),
            }

            import json

            queue_key = f"meetmind:queue:{meeting_id}:agent-artifacts"
            await redis_client.rpush(queue_key, json.dumps(payload))
            await redis_client.ltrim(queue_key, -200, -1)

            # Emit debug event for observability
            channel = f"meetmind:{meeting_id}:events"
            await redis_client.publish(
                channel,
                json.dumps(
                    {
                        "event_type": "agent_artifact",
                        "data": payload,
                        "published_at": int(asyncio.get_event_loop().time() * 1000),
                    }
                ),
            )

            self.logger.info("Published agent artifact %s to meeting %s", artifact_id, meeting_id)
            return {"success": True, "artifact_id": artifact_id}

        except Exception as e:
            self.logger.error(f"Failed to publish agent artifact for {meeting_id}: {e}")
            raise RuntimeError(f"Failed to publish agent artifact: {e}")

    async def tag_event(self, meeting_id: str, kind: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent-triggered event tagging (decision, highlight, risk flag).

        Publishes to Redis channel for SummarizerIngestWorker to process.
        Summarizer re-aggregates and publishes via Redis.

        Args:
            meeting_id: Meeting identifier
            kind: Type of event ("decision", "highlight", "risk_flag", "checkpoint")
            meta: Event metadata (text, reason, severity, etc.)

        Returns:
            Success response with event_id

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If Redis connection fails
        """
        if not meeting_id:
            raise ValueError("meeting_id is required")
        if kind not in ["decision", "highlight", "risk_flag", "checkpoint"]:
            raise ValueError(f"Invalid kind: {kind}. Must be one of: decision, highlight, risk_flag, checkpoint")
        if meta is None:
            raise TypeError("meta is required and cannot be None")

        try:
            redis_client = await self._get_redis_client()
            event_id = f"evt-{uuid4().hex[:8]}"

            event_data = {
                "event_id": event_id,
                "meeting_id": meeting_id,
                "kind": kind,
                "meta": meta,
                "timestamp_ms": int(asyncio.get_event_loop().time() * 1000),
                "source": "agent"
            }

            # Publish to events channel
            channel = f"meetmind:{meeting_id}:events"
            import json
            await redis_client.publish(channel, json.dumps(event_data))

            self.logger.info(f"Tagged event {event_id} of kind {kind} for meeting {meeting_id}")

            return {
                "success": True,
                "event_id": event_id,
                "message": "Event tagged and published"
            }

        except Exception as e:
            self.logger.error(f"Failed to tag event for {meeting_id}: {e}")
            raise RuntimeError(f"Failed to tag event: {e}")

    async def aclose(self) -> None:
        """Close any underlying HTTP and Redis resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._redis_client:
            await self._redis_client.aclose()
            self._redis_client = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client and not self._http_client.is_closed:
            return self._http_client

        self._http_client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        return self._http_client

    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client for reading summarizer data"""
        if self._redis_client and not self._redis_client.connection:
            try:
                await self._redis_client.ping()
                return self._redis_client
            except Exception:
                pass

        self._redis_client = redis.Redis.from_url(self._redis_url)
        return self._redis_client

    async def get_conversation_context_mcp_async(self,
                                           include_topics: bool = True,
                                           include_phase: bool = True,
                                           include_memory: bool = True) -> str:
        """
        Hämta aktuell kontext och analys av konversationen.

        Args:
            include_topics: Om identifierade ämnen ska inkluderas
            include_phase: Om konversationsfas ska inkluderas
            include_memory: Om konversationsminne ska inkluderas

        Returns:
            Kontextinformation eller felmeddelande
        """
        if not self.mcp_integration:
            return "Summeringsagenten är inte tillgänglig för tillfället."

        try:
            result = await self.mcp_integration.call_tool(
                "get_conversation_context",
                {
                    "include_topics": include_topics,
                    "include_phase": include_phase,
                    "include_memory": include_memory
                }
            )

            if result and result.content:
                return result.content[0].text
            else:
                return "Ingen kontextinformation kunde hämtas."

        except Exception as e:
            self.logger.error(f"Kontexthämtning misslyckades: {e}")
            return "Tekniskt fel vid hämtning av kontext."

    async def start_live_summarization_async(self,
                                           conversation_id: str,
                                           update_interval: int = 30,
                                           style: str = "detailed") -> str:
        """
        Starta live-summering som uppdateras automatiskt.

        Args:
            conversation_id: Unik ID för konversationen
            update_interval: Sekunder mellan uppdateringar
            style: Summeringsstil för live-uppdateringar

        Returns:
            Statusmeddelande
        """
        if not self.mcp_integration:
            return "Summeringsagenten är inte tillgänglig för tillfället."

        try:
            result = await self.mcp_integration.call_tool(
                "start_live_summarization",
                {
                    "conversation_id": conversation_id,
                    "update_interval": update_interval,
                    "style": style
                }
            )

            if result and result.content:
                return result.content[0].text
            else:
                return "Live-summering kunde inte startas."

        except Exception as e:
            self.logger.error(f"Start av live-summering misslyckades: {e}")
            return "Tekniskt fel vid start av live-summering."

    async def stop_live_summarization_async(self, conversation_id: str) -> str:
        """
        Stoppa live-summering för en konversation.

        Args:
            conversation_id: ID för konversationen att stoppa

        Returns:
            Statusmeddelande
        """
        if not self.mcp_integration:
            return "Summeringsagenten är inte tillgänglig för tillfället."

        try:
            result = await self.mcp_integration.call_tool(
                "stop_live_summarization",
                {
                    "conversation_id": conversation_id
                }
            )

            if result and result.content:
                return result.content[0].text
            else:
                return "Live-summering kunde inte stoppas."

        except Exception as e:
            self.logger.error(f"Stopp av live-summering misslyckades: {e}")
            return "Tekniskt fel vid stopp av live-summering."

    # ======================================================================
    # NEW MCP ENDPOINT WRAPPERS FOR ARCHITECTURAL BOUNDARY ENFORCEMENT
    # ======================================================================
    
    async def register_a2a_agent_async(
        self,
        agent_id: str,
        capabilities: List[str],
        status: str = "active"
    ) -> Dict[str, Any]:
        """
        Register A2A agent via MCP integration.
        
        Provides clean interface for backend services to register as A2A agents
        without directly importing from summarizer modules.
        
        Args:
            agent_id: Unique identifier for the agent
            capabilities: List of agent capabilities
            status: Agent status (default: "active")
            
        Returns:
            Registration result
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.register_a2a_agent(
            agent_id=agent_id,
            capabilities=capabilities,
            status=status
        )
    
    async def send_a2a_message_async(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Send A2A message via MCP integration.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            
        Returns:
            Message send result
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.send_a2a_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            priority=priority
        )
    
    async def call_bedrock_summarize_async(
        self,
        transcript: str,
        meeting_id: str,
        style: str = "detailed"
    ) -> str:
        """
        Generate summary using Bedrock via MCP integration.
        
        Args:
            transcript: Text to summarize
            meeting_id: Meeting identifier
            style: Summary style
            
        Returns:
            Generated summary text
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.call_bedrock_summarize(
            transcript=transcript,
            meeting_id=meeting_id,
            style=style
        )
    
    async def coordinate_agents_async(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Coordinate agents via MCP integration.
        
        Args:
            task: Task definition with coordination parameters
            
        Returns:
            Coordination result
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.coordinate_agents(task)
    
    async def get_a2a_agent_status_async(self, agent_id: str) -> Dict[str, Any]:
        """
        Get A2A agent status via MCP integration.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent status information
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.get_a2a_agent_status(agent_id)
    
    async def unregister_a2a_agent_async(self, agent_id: str) -> Dict[str, Any]:
        """
        Unregister A2A agent via MCP integration.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Unregistration result
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.unregister_a2a_agent(agent_id)
    
    async def broadcast_a2a_message_async(
        self,
        from_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        capability_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Broadcast A2A message via MCP integration.
        
        Args:
            from_agent: Sender agent ID
            message_type: Type of message
            payload: Message payload
            capability_filter: Optional capability filter
            
        Returns:
            Broadcast result
        """
        if not self.mcp_integration:
            raise RuntimeError("MCP integration not available")
        
        return await self.mcp_integration.broadcast_a2a_message(
            from_agent=from_agent,
            message_type=message_type,
            payload=payload,
            capability_filter=capability_filter
        )
    
    def get_mcp_health_status(self) -> Dict[str, Any]:
        """
        Get MCP integration health status.
        
        Returns:
            Health status including circuit breaker state
        """
        if not self.mcp_integration:
            return {"status": "unavailable", "error": "MCP integration not initialized"}
        
        return self.mcp_integration.get_health_status()
