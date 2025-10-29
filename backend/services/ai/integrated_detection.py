"""
Integrated AI Detection Service

Combines all production AI detection services into a unified interface.
Provides a single entry point for topic detection, action extraction,
persona analysis, phase detection, and embedding generation.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from .production_client import ProductionAIClient, AIProvider
from ..storage.vector_service import ProductionVectorService
from .detection_service import ProductionAIDetectionService, DetectionConfig, PersonaAnalysis, MeetingPhase
from ..processing.topic_detector import TopicDetector, TopicDetectorConfig
from ..processing.action_extractor import ActionExtractor, ActionExtractorConfig
from ..processing.persona_slicer import PersonaSlicer, PersonaSlicerConfig
from ..processing.phase_detector import PhaseDetector, PhaseDetectorConfig

from backend.modules.models.transcript import TranscriptEvent, Topic, ActionItem, ConversationContext
from backend.modules.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class IntegratedDetectionConfig:
    """Configuration for integrated AI detection"""
    
    # AI client settings
    preferred_provider: Optional[AIProvider] = None
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    
    # Vector service settings
    enable_vector_storage: bool = True
    vector_collection: str = "meetmind_detection"
    
    # Detection service configs
    detection_config: DetectionConfig = None
    topic_config: TopicDetectorConfig = None
    action_config: ActionExtractorConfig = None
    persona_config: PersonaSlicerConfig = None
    phase_config: PhaseDetectorConfig = None
    
    def __post_init__(self):
        """Initialize sub-configs if not provided"""
        if self.detection_config is None:
            self.detection_config = DetectionConfig()
        if self.topic_config is None:
            self.topic_config = TopicDetectorConfig()
        if self.action_config is None:
            self.action_config = ActionExtractorConfig()
        if self.persona_config is None:
            self.persona_config = PersonaSlicerConfig()
        if self.phase_config is None:
            self.phase_config = PhaseDetectorConfig()


class IntegratedAIDetectionService:
    """
    Integrated AI detection service combining all detection capabilities.
    
    Provides a unified interface for:
    - Topic detection with semantic clustering
    - Action item extraction with structured parsing
    - Persona analysis with role identification
    - Meeting phase detection with context analysis
    - Vector embedding generation and storage
    """
    
    def __init__(self, config: IntegratedDetectionConfig = None):
        """
        Initialize integrated AI detection service
        
        Args:
            config: Service configuration
        """
        self.config = config or IntegratedDetectionConfig()
        self.settings = settings
        
        # Core services
        self.ai_client: Optional[ProductionAIClient] = None
        self.vector_service: Optional[ProductionVectorService] = None
        self.detection_service: Optional[ProductionAIDetectionService] = None
        
        # Specialized detectors
        self.topic_detector: Optional[TopicDetector] = None
        self.action_extractor: Optional[ActionExtractor] = None
        self.persona_slicer: Optional[PersonaSlicer] = None
        self.phase_detector: Optional[PhaseDetector] = None
        
        # Service state
        self.initialized = False
        
        # Statistics
        self.stats = {
            "topics_detected": 0,
            "actions_extracted": 0,
            "personas_analyzed": 0,
            "phases_detected": 0,
            "embeddings_generated": 0,
            "last_operation": None
        }
        
        logger.info("IntegratedAIDetectionService initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize all AI detection services
        
        Returns:
            True if initialization successful
        """
        if self.initialized:
            return True
        
        try:
            # Initialize AI client
            await self._init_ai_client()
            
            # Initialize vector service if enabled
            if self.config.enable_vector_storage:
                await self._init_vector_service()
            
            # Initialize detection services
            await self._init_detection_services()
            
            self.initialized = True
            logger.info("IntegratedAIDetectionService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize IntegratedAIDetectionService: {e}")
            return False
    
    async def _init_ai_client(self):
        """Initialize production AI client"""
        self.ai_client = ProductionAIClient(
            openai_api_key=self.settings.OPENAI_API_KEY,
            google_api_key=self.settings.GOOGLE_AI_API_KEY,
            bedrock_region="us-east-1"
        )
        logger.info("AI client initialized")
    
    async def _init_vector_service(self):
        """Initialize vector service"""
        self.vector_service = ProductionVectorService()
        success = await self.vector_service.initialize()
        if success:
            logger.info("Vector service initialized")
        else:
            logger.warning("Vector service initialization failed")
            self.vector_service = None
    
    async def _init_detection_services(self):
        """Initialize all detection services"""
        # Core detection service
        self.detection_service = ProductionAIDetectionService(
            self.ai_client, 
            self.config.detection_config
        )
        
        # Specialized detectors
        self.topic_detector = TopicDetector(
            self.ai_client,
            self.config.topic_config
        )
        
        self.action_extractor = ActionExtractor(
            self.ai_client,
            self.config.action_config
        )
        
        self.persona_slicer = PersonaSlicer(
            self.ai_client,
            self.config.persona_config
        )
        
        self.phase_detector = PhaseDetector(
            self.ai_client,
            self.config.phase_config
        )
        
        logger.info("All detection services initialized")
    
    async def analyze_meeting_content(self, content: str, meeting_id: str,
                                     speakers: Optional[List[str]] = None,
                                     user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive analysis of meeting content.
        
        Args:
            content: Meeting content/transcript
            meeting_id: Unique meeting identifier
            speakers: List of speaker IDs
            user_id: User ID for quota tracking
            
        Returns:
            Complete analysis results
        """
        try:
            if not self.initialized:
                raise RuntimeError("Service not initialized")
            
            results = {
                "meeting_id": meeting_id,
                "analysis_timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "speakers": speakers or []
            }
            
            # Run all analyses in parallel for efficiency
            tasks = []
            
            # Topic detection
            if self.topic_detector:
                tasks.append(self._detect_topics_task(content, user_id))
            
            # Action extraction
            if self.action_extractor:
                tasks.append(self._extract_actions_task(content, meeting_id, user_id))
            
            # Persona analysis
            if self.persona_slicer and speakers:
                tasks.append(self._analyze_personas_task(content, speakers, user_id))
            
            # Phase detection
            if self.phase_detector:
                tasks.append(self._detect_phase_task(content, user_id))
            
            # Generate embeddings
            if self.detection_service:
                tasks.append(self._generate_embeddings_task(content, user_id))
            
            # Execute all tasks
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    logger.error(f"Task {i} failed: {result}")
                    continue
                
                if isinstance(result, dict):
                    results.update(result)
            
            # Store in vector database if enabled
            if self.vector_service and "embeddings" in results:
                await self._store_in_vector_db(content, meeting_id, results)
            
            # Update statistics
            self._update_stats(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Meeting content analysis failed: {e}")
            return {
                "error": str(e),
                "meeting_id": meeting_id,
                "analysis_timestamp": datetime.now().isoformat()
            }
    
    async def _detect_topics_task(self, content: str, user_id: Optional[str]) -> Dict[str, Any]:
        """Task for topic detection"""
        try:
            topics = await self.detection_service.detect_topics_real(content, user_id)
            return {
                "topics": [
                    {
                        "name": topic.name,
                        "keywords": topic.keywords,
                        "confidence": topic.confidence,
                        "speakers": topic.speakers,
                        "sentiment": topic.sentiment,
                        "energy": topic.energy
                    }
                    for topic in topics
                ]
            }
        except Exception as e:
            logger.error(f"Topic detection task failed: {e}")
            return {"topics": []}
    
    async def _extract_actions_task(self, content: str, meeting_id: str, user_id: Optional[str]) -> Dict[str, Any]:
        """Task for action extraction"""
        try:
            actions = await self.detection_service.extract_actions_real(content, meeting_id, user_id)
            return {
                "actions": [
                    {
                        "what": action.what,
                        "owner": action.owner,
                        "when": action.when,
                        "priority": action.priority,
                        "confidence": action.confidence,
                        "status": action.status
                    }
                    for action in actions
                ]
            }
        except Exception as e:
            logger.error(f"Action extraction task failed: {e}")
            return {"actions": []}
    
    async def _analyze_personas_task(self, content: str, speakers: List[str], user_id: Optional[str]) -> Dict[str, Any]:
        """Task for persona analysis"""
        try:
            personas = await self.detection_service.analyze_personas_real(content, speakers, user_id)
            return {
                "personas": [
                    {
                        "speaker_id": persona.speaker_id,
                        "role": persona.role,
                        "engagement_level": persona.engagement_level,
                        "sentiment": persona.sentiment,
                        "key_contributions": persona.key_contributions,
                        "confidence": persona.confidence
                    }
                    for persona in personas
                ]
            }
        except Exception as e:
            logger.error(f"Persona analysis task failed: {e}")
            return {"personas": []}
    
    async def _detect_phase_task(self, content: str, user_id: Optional[str]) -> Dict[str, Any]:
        """Task for phase detection"""
        try:
            phase, confidence = await self.detection_service.detect_phase_real(content, None, user_id)
            return {
                "phase": {
                    "current_phase": phase.value,
                    "confidence": confidence
                }
            }
        except Exception as e:
            logger.error(f"Phase detection task failed: {e}")
            return {"phase": {"current_phase": "scoping", "confidence": 0.5}}
    
    async def _generate_embeddings_task(self, content: str, user_id: Optional[str]) -> Dict[str, Any]:
        """Task for embedding generation"""
        try:
            # Split content into chunks for embedding
            chunks = self._chunk_content(content, 1000)  # 1000 word chunks
            embeddings = await self.detection_service.generate_embeddings_real(chunks, user_id)
            
            return {
                "embeddings": embeddings,
                "embedding_chunks": chunks
            }
        except Exception as e:
            logger.error(f"Embedding generation task failed: {e}")
            return {"embeddings": [], "embedding_chunks": []}
    
    def _chunk_content(self, content: str, chunk_size: int) -> List[str]:
        """Split content into chunks for processing"""
        words = content.split()
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    async def _store_in_vector_db(self, content: str, meeting_id: str, results: Dict[str, Any]):
        """Store analysis results in vector database"""
        try:
            if not self.vector_service or "embeddings" not in results:
                return
            
            embeddings = results["embeddings"]
            chunks = results.get("embedding_chunks", [])
            
            # Store each chunk with its embedding
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                metadata = {
                    "meeting_id": meeting_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "topics": [topic["name"] for topic in results.get("topics", [])],
                    "actions_count": len(results.get("actions", [])),
                    "phase": results.get("phase", {}).get("current_phase", "unknown"),
                    "analysis_timestamp": results["analysis_timestamp"]
                }
                
                await self.vector_service.index_content(
                    content=chunk,
                    embedding=embedding,
                    metadata=metadata,
                    collection_name=self.config.vector_collection,
                    content_id=f"{meeting_id}_chunk_{i}"
                )
            
            logger.info(f"Stored {len(chunks)} chunks in vector database")
            
        except Exception as e:
            logger.error(f"Failed to store in vector database: {e}")
    
    def _update_stats(self, results: Dict[str, Any]):
        """Update service statistics"""
        self.stats["last_operation"] = datetime.now().isoformat()
        
        if "topics" in results:
            self.stats["topics_detected"] += len(results["topics"])
        
        if "actions" in results:
            self.stats["actions_extracted"] += len(results["actions"])
        
        if "personas" in results:
            self.stats["personas_analyzed"] += len(results["personas"])
        
        if "phase" in results:
            self.stats["phases_detected"] += 1
        
        if "embeddings" in results:
            self.stats["embeddings_generated"] += len(results["embeddings"])
    
    async def search_similar_content(self, query: str, limit: int = 10,
                                    meeting_filter: Optional[str] = None,
                                    user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar content using vector similarity
        
        Args:
            query: Search query
            limit: Maximum results
            meeting_filter: Filter by specific meeting ID
            user_id: User ID for quota tracking
            
        Returns:
            List of similar content results
        """
        try:
            if not self.vector_service or not self.detection_service:
                return []
            
            # Generate embedding for query
            query_embeddings = await self.detection_service.generate_embeddings_real([query], user_id)
            if not query_embeddings:
                return []
            
            query_embedding = query_embeddings[0]
            
            # Prepare filter conditions
            filter_conditions = {}
            if meeting_filter:
                filter_conditions["meeting_id"] = meeting_filter
            
            # Search similar content
            results = await self.vector_service.search_similar(
                query_embedding=query_embedding,
                limit=limit,
                collection_name=self.config.vector_collection,
                filter_conditions=filter_conditions if filter_conditions else None
            )
            
            # Convert to response format
            return [
                {
                    "content": result.content,
                    "similarity_score": result.similarity_score,
                    "meeting_id": result.metadata.get("meeting_id"),
                    "topics": result.metadata.get("topics", []),
                    "phase": result.metadata.get("phase"),
                    "chunk_index": result.metadata.get("chunk_index")
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Similar content search failed: {e}")
            return []
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics"""
        stats = dict(self.stats)
        
        # Add component stats
        if self.ai_client:
            ai_stats = await self.ai_client.get_usage_stats()
            stats["ai_client"] = ai_stats
        
        if self.vector_service:
            vector_stats = await self.vector_service.get_stats()
            stats["vector_service"] = vector_stats
        
        if self.detection_service:
            detection_stats = await self.detection_service.get_detection_stats()
            stats["detection_service"] = detection_stats
        
        stats.update({
            "initialized": self.initialized,
            "config": {
                "preferred_provider": self.config.preferred_provider.value if self.config.preferred_provider else None,
                "enable_caching": self.config.enable_caching,
                "enable_vector_storage": self.config.enable_vector_storage,
                "vector_collection": self.config.vector_collection
            }
        })
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health = {
            "status": "healthy",
            "initialized": self.initialized,
            "components": {}
        }
        
        try:
            # Check AI client
            if self.ai_client:
                ai_health = await self.ai_client.health_check()
                health["components"]["ai_client"] = ai_health
                if ai_health["status"] != "healthy":
                    health["status"] = "degraded"
            
            # Check vector service
            if self.vector_service:
                vector_health = await self.vector_service.health_check()
                health["components"]["vector_service"] = vector_health
                if vector_health["status"] != "healthy":
                    health["status"] = "degraded"
            
            # Check detection services
            health["components"]["detection_services"] = {
                "topic_detector": self.topic_detector is not None,
                "action_extractor": self.action_extractor is not None,
                "persona_slicer": self.persona_slicer is not None,
                "phase_detector": self.phase_detector is not None
            }
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    async def close(self):
        """Close all services and cleanup resources"""
        try:
            if self.ai_client:
                await self.ai_client.close()
            
            if self.vector_service:
                await self.vector_service.close()
            
            self.initialized = False
            logger.info("IntegratedAIDetectionService closed")
            
        except Exception as e:
            logger.error(f"Error closing IntegratedAIDetectionService: {e}")


# Global service instance
_integrated_detection_service: Optional[IntegratedAIDetectionService] = None


def get_integrated_detection_service() -> IntegratedAIDetectionService:
    """Get or create global integrated detection service instance"""
    global _integrated_detection_service
    
    if _integrated_detection_service is None:
        _integrated_detection_service = IntegratedAIDetectionService()
    
    return _integrated_detection_service


async def initialize_integrated_detection_service() -> IntegratedAIDetectionService:
    """Initialize integrated detection service"""
    service = get_integrated_detection_service()
    
    if not service.initialized:
        success = await service.initialize()
        if not success:
            raise RuntimeError("Failed to initialize integrated detection service")
    
    return service


async def shutdown_integrated_detection_service():
    """Shutdown integrated detection service"""
    global _integrated_detection_service
    
    if _integrated_detection_service:
        await _integrated_detection_service.close()
        _integrated_detection_service = None