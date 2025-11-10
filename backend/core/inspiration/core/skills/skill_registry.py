"""
🔄 SKILL REGISTRY & LOADER - DYNAMISK HANTERING AV FÄRDIGHETER

Vad gör den här filen?
- Hanterar registrering och laddning av alla skills i systemet
- Automatisk upptäckt av nya skills utan restart
- Hot-reload funktionalitet för utveckling
- Capability signature och intent-baserad auto-discovery

Varför behövs detta?
- Gör systemet dynamiskt och utökningsbart
- Möjliggör self-building skill pipeline
- Automatisk integration av nya skills
- Robust felhantering vid skill-laddning
"""

import asyncio
import importlib
import inspect
import logging
import os
import sys
import traceback
import json
import hashlib
from typing import Dict, Any, List, Optional, Set, Callable
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from abc import ABC, abstractmethod
import importlib.util
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import functools
import time

try:
    from app.core.config.settings import get_settings
except ImportError:
    def get_settings():
        class Settings:
            DEBUG = True
            orchestrator = type('OrchestratorSettings', (), {'skill_selection_top_k': 5})()
        return Settings()

from app.core.utils.error_handler import safe_execute, HappyOSError

try:
    from app.core.performance import monitor_performance
except ImportError:
    def monitor_performance(func):
        return func

try:
    from app.skills.base import Skill, BaseSkill
except ImportError:
    class Skill:
        pass
    class BaseSkill:
        pass

try:
    from app.llm.router import get_llm_client
except ImportError:
    def get_llm_client(model_type=None):
        return None

# Enhanced imports for improved skill matching
try:
    from app.core.memory.memory_system import MemorySystem, MemorySystemConfig
    from app.db.repository_base import Repository
    from app.db.metrics_collector import MetricsCollector
    from app.core.fallbacks import FallbackManager
except ImportError:
    MemorySystem = None
    Repository = None
    MetricsCollector = None
    FallbackManager = None

import numpy as np
import random

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SkillCapability:
    """Beskriver vad en skill kan göra."""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkillMetadata:
    """Metadata för en skill."""
    skill_id: str
    name: str
    description: str
    version: str
    author: str
    capabilities: List[SkillCapability]
    intents: List[str]
    file_path: str
    module_path: str
    last_modified: datetime
    file_hash: str
    dependencies: Optional[List[str]] = None
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['capabilities'] = [cap.to_dict() for cap in self.capabilities]
        data['last_modified'] = self.last_modified.isoformat()
        return data


@dataclass
class SkillMatchResult:
    """Result of skill matching for a request."""
    skill_id: str
    skill_name: str
    confidence_score: float
    match_reasons: List[str] = field(default_factory=list)
    performance_score: float = 0.0
    historical_success_rate: float = 0.0
    contextual_relevance: float = 0.0
    execution_time_estimate: float = 0.0
    capabilities_matched: List[str] = field(default_factory=list)
    intents_matched: List[str] = field(default_factory=list)

    def total_score(self) -> float:
        """Calculate total weighted score."""
        weights = {
            'confidence': 0.3,
            'performance': 0.25,
            'historical': 0.2,
            'contextual': 0.15,
            'capabilities': 0.1
        }

        capability_bonus = min(len(self.capabilities_matched) * 0.05, 0.1)
        intent_bonus = min(len(self.intents_matched) * 0.03, 0.05)

        return (
            self.confidence_score * weights['confidence'] +
            self.performance_score * weights['performance'] +
            self.historical_success_rate * weights['historical'] +
            self.contextual_relevance * weights['contextual'] +
            capability_bonus +
            intent_bonus
        )


@dataclass
class SkillMatchingCacheEntry:
    """Cache entry for skill matching results."""
    request_hash: str
    request_text: str
    matched_skills: List[str]
    timestamp: datetime
    context_hash: str
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """Check if cache entry is expired."""
        return (datetime.utcnow() - self.timestamp).total_seconds() > max_age_seconds


class SkillFileWatcher(FileSystemEventHandler):
    """Övervakar ändringar i skill-filer för hot-reload."""
    
    def __init__(self, registry: 'SkillRegistry'):
        self.registry = registry
        self.debounce_time = 1.0  # Sekunder att vänta innan reload
        self.pending_reloads: Dict[str, float] = {}
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if event.src_path.endswith('.py'):
            current_time = datetime.utcnow().timestamp()
            self.pending_reloads[event.src_path] = current_time
            asyncio.create_task(self._debounced_reload(event.src_path, current_time))
    
    async def _debounced_reload(self, file_path: str, trigger_time: float):
        await asyncio.sleep(self.debounce_time)
        if self.pending_reloads.get(file_path) == trigger_time:
            try:
                await self.registry.reload_skill_from_file(file_path)
                del self.pending_reloads[file_path]
            except Exception as e:
                logger.error(f"Fel vid hot-reload av {file_path}: {str(e)}")


class SkillRegistry:
    """
    Enhanced central register för alla skills i systemet med avancerad matching.
    Integrerar IntelligentMemory, Database metrics, och smart caching.
    """

    def __init__(self):
        # Core skill storage
        self.skills: Dict[str, Skill] = {}
        self.metadata: Dict[str, SkillMetadata] = {}
        self.capabilities: Dict[str, List[str]] = {}
        self.intents: Dict[str, List[str]] = {}
        self.file_watcher: Optional[Observer] = None
        self.skills_directory = Path("app/skills")
        self.loaded_modules: Set[str] = set()
        self.embedding_client = None
        self.load_times: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = {}

        # Enhanced skill matching components
        self.memory_system: Optional[MemorySystem] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.skill_cache: Optional[Repository] = None
        self.fallback_manager: Optional[FallbackManager] = None

        # Smart caching system
        self.matching_cache: Dict[str, SkillMatchingCacheEntry] = {}
        self.cache_max_size = 1000
        self.cache_ttl_seconds = 3600  # 1 hour

        # Performance tracking
        self.skill_performance_history: Dict[str, List[Dict[str, Any]]] = {}
        self.skill_success_rates: Dict[str, float] = {}
        self.skill_execution_times: Dict[str, float] = {}

        # Matching configuration
        self.confidence_threshold = 0.3
        self.max_matches_returned = 5
        self.enable_historical_learning = True
        self.enable_contextual_matching = True
        self.enable_performance_weighting = True
    
    async def initialize(self, memory_system: Optional[MemorySystem] = None,
                        metrics_collector: Optional[MetricsCollector] = None,
                        skill_cache: Optional[Repository] = None,
                        fallback_manager: Optional[FallbackManager] = None) -> Dict[str, Any]:
        """
        Initialize SkillRegistry with enhanced components for improved skill matching.

        Args:
            memory_system: IntelligentMemory system for contextual scoring
            metrics_collector: Database metrics collector for performance tracking
            skill_cache: Repository for smart caching
            fallback_manager: Fallback system for robust error handling

        Returns:
            Initialization status
        """
        logger.info("Initialiserar Enhanced SkillRegistry...")
        try:
            # Initialize core embedding client
            self.embedding_client = get_llm_client("hybrid")
            if self.embedding_client:
                logger.info("Embedding client (OpenAI) initialized successfully.")
            else:
                logger.warning("Could not initialize OpenAI embedding client. Embedding features will be disabled.")
                self.embedding_client = None

            # Initialize enhanced components
            self.memory_system = memory_system
            self.metrics_collector = metrics_collector
            self.skill_cache = skill_cache
            self.fallback_manager = fallback_manager

            # Initialize memory system if not provided
            if not self.memory_system and MemorySystem:
                self.memory_system = MemorySystem(MemorySystemConfig())
                await self.memory_system.initialize()
                logger.info("MemorySystem initialized for SkillRegistry")

            # Initialize metrics collector if not provided
            if not self.metrics_collector and MetricsCollector:
                self.metrics_collector = MetricsCollector()
                await self.metrics_collector.initialize()
                logger.info("MetricsCollector initialized for SkillRegistry")

            # Initialize skill cache if not provided
            if not self.skill_cache and Repository:
                self.skill_cache = Repository("skill_cache")
                logger.info("Skill cache repository initialized")

            # Initialize fallback manager if not provided
            if not self.fallback_manager and FallbackManager:
                self.fallback_manager = FallbackManager()
                logger.info("FallbackManager initialized for SkillRegistry")

            # Load skill performance data from database
            await self._load_performance_data()

            # Discover and load skills
            discovered = await self.discover_skills()
            loaded = await self.load_all_skills()
            await self.start_file_watcher()

            # Initialize cache cleanup task
            asyncio.create_task(self._periodic_cache_cleanup())

            result = {
                "discovered": len(discovered),
                "loaded": len(loaded),
                "capabilities": len(self.capabilities),
                "intents": len(self.intents),
                "errors": sum(self.error_counts.values()),
                "memory_system": self.memory_system is not None,
                "metrics_collector": self.metrics_collector is not None,
                "skill_cache": self.skill_cache is not None,
                "fallback_manager": self.fallback_manager is not None,
                "cache_size": len(self.matching_cache)
            }
            logger.info(f"Enhanced SkillRegistry initialiserad: {result}")
            return result

        except Exception as e:
            error_msg = f"Failed to initialize Enhanced SkillRegistry: {e}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "discovered": 0,
                "loaded": 0,
                "capabilities": 0,
                "intents": 0,
                "memory_system": False,
                "metrics_collector": False,
                "skill_cache": False,
                "fallback_manager": False
            }
    
    async def discover_skills(self) -> List[str]:
        discovered_skills = []
        if not self.skills_directory.exists():
            logger.warning(f"Skills directory inte funnet: {self.skills_directory}")
            return discovered_skills
        
        for skill_file in self.skills_directory.rglob("*.py"):
            if skill_file.name.startswith("__") or skill_file.name == "base.py":
                continue
            try:
                skill_id = self._get_skill_id_from_path(skill_file)
                metadata = await self._extract_skill_metadata(skill_file)
                if metadata:
                    self.metadata[skill_id] = metadata
                    discovered_skills.append(skill_id)
                    logger.debug(f"Upptäckte skill: {skill_id}")
            except Exception as e:
                logger.error(f"Fel vid upptäckt av skill {skill_file}: {str(e)}")
                self.error_counts[str(skill_file)] = self.error_counts.get(str(skill_file), 0) + 1
        logger.info(f"Upptäckte {len(discovered_skills)} skills")
        return discovered_skills
    
    async def load_skill(self, skill_id: str) -> bool:
        if skill_id not in self.metadata:
            logger.error(f"Skill {skill_id} inte upptäckt")
            return False
        metadata = self.metadata[skill_id]
        try:
            start_time = datetime.utcnow()
            skill_instance = await self._load_skill_module(metadata)
            if skill_instance:
                self.skills[skill_id] = skill_instance
                await self._register_capabilities(skill_id, skill_instance)
                await self._register_intents(skill_id, skill_instance)
                load_time = (datetime.utcnow() - start_time).total_seconds()
                self.load_times[skill_id] = load_time
                logger.info(f"Laddade skill {skill_id} på {load_time:.2f}s")
                return True
        except Exception as e:
            logger.error(f"Fel vid laddning av skill {skill_id}: {str(e)}")
            logger.debug(traceback.format_exc())
            self.error_counts[skill_id] = self.error_counts.get(skill_id, 0) + 1
        return False
    
    async def load_all_skills(self) -> List[str]:
        loaded_skills = []
        for skill_id in self.metadata.keys():
            if await self.load_skill(skill_id):
                loaded_skills.append(skill_id)
        logger.info(f"Laddade {len(loaded_skills)}/{len(self.metadata)} skills")
        return loaded_skills
    
    async def reload_skill(self, skill_id: str) -> bool:
        if skill_id not in self.metadata: return False
        try:
            await self.unload_skill(skill_id)
            metadata = self.metadata[skill_id]
            updated_metadata = await self._extract_skill_metadata(Path(metadata.file_path))
            if updated_metadata:
                self.metadata[skill_id] = updated_metadata
                if await self.load_skill(skill_id):
                    logger.info(f"Hot-reloadade skill {skill_id}")
                    return True
        except Exception as e:
            logger.error(f"Fel vid reload av skill {skill_id}: {str(e)}")
        return False
    
    async def reload_skill_from_file(self, file_path: str) -> bool:
        skill_id = self._get_skill_id_from_path(Path(file_path))
        return await self.reload_skill(skill_id)
    
    async def unload_skill(self, skill_id: str) -> bool:
        try:
            if skill_id in self.skills: del self.skills[skill_id]
            for cap_skills in self.capabilities.values():
                if skill_id in cap_skills: cap_skills.remove(skill_id)
            for intent_skills in self.intents.values():
                if skill_id in intent_skills: intent_skills.remove(skill_id)
            metadata = self.metadata.get(skill_id)
            if metadata and metadata.module_path in sys.modules:
                try:
                    del sys.modules[metadata.module_path]
                    self.loaded_modules.discard(metadata.module_path)
                except: pass
            logger.info(f"Laddade ur skill {skill_id}")
            return True
        except Exception as e:
            logger.error(f"Fel vid urladdning av skill {skill_id}: {str(e)}")
            return False
    
    def get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id)
    
    def get_skills_by_capability(self, capability: str) -> List[Skill]:
        skill_ids = self.capabilities.get(capability, [])
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]
    
    def get_skills_by_intent(self, intent: str) -> List[Skill]:
        skill_ids = self.intents.get(intent, [])
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]
    
    async def find_best_skill_for_request(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> Optional[Skill]:
        logger.debug(f"Finding best skill for request: '{user_request}'")
        if not self.metadata: return None
        candidate_skills_metadata: List[SkillMetadata] = []
        if self.embedding_client:
            try:
                user_request_embedding = await self.embedding_client.generate_embedding(user_request)
                skill_similarities = [(sid, self._cosine_similarity(user_request_embedding, meta.embedding), meta)
                                      for sid, meta in self.metadata.items() if sid in self.skills and meta.embedding]
                skill_similarities.sort(key=lambda x: x[1], reverse=True)
                top_k = settings.orchestrator.skill_selection_top_k
                if not skill_similarities: logger.warning("No skills with embeddings for similarity.")
                elif len(skill_similarities) < top_k: candidate_skills_metadata = [m for _, _, m in skill_similarities]
                else: candidate_skills_metadata = [m for _, _, m in skill_similarities[:top_k]]
                logger.info(f"Selected top {len(candidate_skills_metadata)} skills via embeddings: {[m.skill_id for m in candidate_skills_metadata]}")
            except Exception as e:
                logger.error(f"Embedding pre-filtering error: {e}", exc_info=True)
                candidate_skills_metadata = [m for sid, m in self.metadata.items() if sid in self.skills]
        else:
            logger.info("Embedding client NA. Using all loaded skills for LLM selection.")
            candidate_skills_metadata = [m for sid, m in self.metadata.items() if sid in self.skills]

        if not candidate_skills_metadata: return None
        available_skills_info = [
            f"- Skill ID: {m.skill_id}\n  Name: {m.name}\n  Description: {m.description}\n  Capabilities: {', '.join(c.name for c in m.capabilities)}\n  Intents: {', '.join(m.intents)}"
            for m in candidate_skills_metadata
        ]
        if not available_skills_info: return None
        skills_list_str = "\n\n".join(available_skills_info)
        prompt = f"""
User request: "{user_request}"

Available skills:
{skills_list_str}

Based on the user request and the available skills, which skill is the most suitable?
Consider the skill descriptions and capabilities.
Return ONLY the Skill ID (e.g., 'your_skill_id_here' or 'another_skill_id').
If no skill is clearly suitable, return 'None'.
Selected Skill ID:"""
        try:
            llm_client = get_llm_client()
            if not llm_client:
                logger.error("Reasoning LLM client NA for skill selection.")
                if candidate_skills_metadata and self.embedding_client and candidate_skills_metadata[0].embedding:
                    return self.skills.get(candidate_skills_metadata[0].skill_id)
                return None
            response = await llm_client.generate(messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=60)
            chosen_skill_id_str = response.get("content", "").strip().replace("'", "").replace("\"", "")
            if chosen_skill_id_str.startswith("Skill ID:"): chosen_skill_id_str = chosen_skill_id_str.replace("Skill ID:", "").strip()
            logger.info(f"LLM chose skill ID: '{chosen_skill_id_str}' for request: '{user_request}' from {len(available_skills_info)} candidates.")
            if chosen_skill_id_str and chosen_skill_id_str != 'None' and chosen_skill_id_str in self.skills:
                if chosen_skill_id_str in [m.skill_id for m in candidate_skills_metadata]:
                    return self.skills[chosen_skill_id_str]
                else:
                    logger.warning(f"LLM chose skill '{chosen_skill_id_str}' not in candidate list.")
                    if candidate_skills_metadata and self.embedding_client and candidate_skills_metadata[0].embedding:
                        return self.skills.get(candidate_skills_metadata[0].skill_id)
                    return None
            else:
                logger.warning(f"LLM chose invalid/no skill ID: '{chosen_skill_id_str}'.")
                if candidate_skills_metadata and self.embedding_client and candidate_skills_metadata[0].embedding:
                    return self.skills.get(candidate_skills_metadata[0].skill_id)
                return None
        except Exception as e:
            logger.error(f"LLM skill selection error: {str(e)}", exc_info=True)
            if candidate_skills_metadata and self.embedding_client and candidate_skills_metadata[0].embedding:
                return self.skills.get(candidate_skills_metadata[0].skill_id)
            return None

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2: return 0.0
        vec1_np, vec2_np = np.array(vec1), np.array(vec2)
        if vec1_np.shape != vec2_np.shape:
            logger.warning(f"Embeddings shape mismatch: {vec1_np.shape} vs {vec2_np.shape}")
            return 0.0
        norm_v1, norm_v2 = np.linalg.norm(vec1_np), np.linalg.norm(vec2_np)
        if norm_v1 == 0 or norm_v2 == 0: return 0.0
        return float(np.dot(vec1_np, vec2_np) / (norm_v1 * norm_v2))

    async def start_file_watcher(self):
        try:
            if self.file_watcher: self.file_watcher.stop()
            self.file_watcher = Observer()
            handler = SkillFileWatcher(self)
            self.file_watcher.schedule(handler, str(self.skills_directory), recursive=True)
            self.file_watcher.start()
            logger.info("File watcher startad för hot-reload")
        except Exception as e:
            logger.error(f"Kunde inte starta file watcher: {str(e)}")
    
    async def stop_file_watcher(self):
        if self.file_watcher:
            self.file_watcher.stop()
            self.file_watcher.join()
            self.file_watcher = None
            logger.info("File watcher stoppad")
    
    def get_registry_status(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self.skills), "total_metadata": len(self.metadata),
            "capabilities": len(self.capabilities), "intents": len(self.intents),
            "loaded_modules": len(self.loaded_modules),
            "average_load_time": sum(self.load_times.values()) / len(self.load_times) if self.load_times else 0,
            "total_errors": sum(self.error_counts.values()),
            "file_watcher_active": self.file_watcher is not None and self.file_watcher.is_alive()
        }
    
    def get_skill_info(self, skill_id: str) -> Optional[Dict[str, Any]]:
        if skill_id not in self.metadata: return None
        metadata, is_loaded = self.metadata[skill_id], skill_id in self.skills
        info = metadata.to_dict()
        info.update({"is_loaded": is_loaded, "load_time": self.load_times.get(skill_id, 0), "error_count": self.error_counts.get(skill_id, 0)})
        return info
    
    def _get_skill_id_from_path(self, file_path: Path) -> str:
        relative_path = file_path.relative_to(self.skills_directory)
        return str(relative_path.with_suffix('')).replace(os.sep, '_')
    
    async def _extract_skill_metadata(self, file_path: Path) -> Optional[SkillMetadata]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            file_hash = hashlib.md5(content.encode()).hexdigest()
            last_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
            skill_id = self._get_skill_id_from_path(file_path)
            module_path = f"app.skills.{skill_id.replace('_', '.')}"
            spec = importlib.util.spec_from_file_location(module_path, file_path)
            if not spec or not spec.loader: return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            skill_classes = [obj for _, obj in inspect.getmembers(module) if inspect.isclass(obj) and issubclass(obj, Skill) and obj != Skill and not inspect.isabstract(obj)]
            if not skill_classes: return None
            skill_class = skill_classes[0]
            capabilities, intents = [], []
            if hasattr(skill_class, 'get_capabilities'):
                try:
                    caps = skill_class().get_capabilities()
                    for cap in caps:
                        if isinstance(cap, dict): capabilities.append(SkillCapability(**cap))
                except: pass
            if hasattr(skill_class, 'get_intents'):
                try: intents = skill_class().get_intents()
                except: pass
            raw_metadata = SkillMetadata(skill_id=skill_id, name=skill_class.__name__, description=skill_class.__doc__ or "Ingen beskrivning", version="1.0.0", author="HappyOS", capabilities=capabilities, intents=intents, file_path=str(file_path), module_path=module_path, last_modified=last_modified, file_hash=file_hash)
            if self.embedding_client:
                try:
                    text_to_embed = f"{raw_metadata.name} - {raw_metadata.description}. Capabilities: {', '.join(c.name for c in raw_metadata.capabilities)}. Intents: {', '.join(raw_metadata.intents)}"
                    raw_metadata.embedding = await self.embedding_client.generate_embedding(text_to_embed)
                    logger.debug(f"Generated embedding for skill {skill_id}")
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for skill {skill_id}: {e}")
                    raw_metadata.embedding = None
            return raw_metadata
        except Exception as e:
            logger.error(f"Fel vid extrahering av metadata från {file_path}: {str(e)}")
            return None
    
    async def _load_skill_module(self, metadata: SkillMetadata) -> Optional[Skill]:
        try:
            if metadata.module_path in sys.modules: module = importlib.reload(sys.modules[metadata.module_path])
            else: module = importlib.import_module(metadata.module_path)
            self.loaded_modules.add(metadata.module_path)
            for _, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Skill) and obj != Skill and not inspect.isabstract(obj):
                    return obj()
            logger.error(f"Ingen skill-klass hittad i {metadata.module_path}")
            return None
        except Exception as e:
            logger.error(f"Fel vid laddning av modul {metadata.module_path}: {str(e)}")
            return None
    
    async def _register_capabilities(self, skill_id: str, skill: Skill):
        try:
            if hasattr(skill, 'get_capabilities'):
                for cap_data in skill.get_capabilities():
                    cap_name = cap_data.get('name') if isinstance(cap_data, dict) else str(cap_data)
                    if cap_name not in self.capabilities: self.capabilities[cap_name] = []
                    if skill_id not in self.capabilities[cap_name]: self.capabilities[cap_name].append(skill_id)
        except Exception as e: logger.error(f"Fel vid registrering av capabilities för {skill_id}: {str(e)}")
    
    async def _register_intents(self, skill_id: str, skill: Skill):
        try:
            if hasattr(skill, 'get_intents'):
                for intent in skill.get_intents():
                    if intent not in self.intents: self.intents[intent] = []
                    if skill_id not in self.intents[intent]: self.intents[intent].append(skill_id)
        except Exception as e: logger.error(f"Fel vid registrering av intents för {skill_id}: {str(e)}")

    # ==================== ENHANCED SKILL MATCHING METHODS ====================

    async def find_skills_for_request(self, user_request: str, context: Optional[Dict[str, Any]] = None,
                                     max_results: int = None) -> List[BaseSkill]:
        """
        Enhanced skill matching using hybrid algorithm with multiple criteria.

        Args:
            user_request: The user's request text
            context: Additional context information
            max_results: Maximum number of skills to return

        Returns:
            List of matched skills ordered by relevance
        """
        try:
            if max_results is None:
                max_results = self.max_matches_returned

            start_time = time.time()

            # Check cache first
            cache_key = self._generate_cache_key(user_request, context)
            if cache_key in self.matching_cache:
                cache_entry = self.matching_cache[cache_key]
                if not cache_entry.is_expired(self.cache_ttl_seconds):
                    logger.debug(f"Cache hit for request: {user_request[:50]}...")
                    cached_skills = [self.skills[sid] for sid in cache_entry.matched_skills if sid in self.skills]
                    if cached_skills:
                        return cached_skills[:max_results]

            # Perform hybrid matching
            match_results = await self._perform_hybrid_matching(user_request, context)

            # Filter and sort results
            matched_skills = []
            for result in sorted(match_results, key=lambda x: x.total_score(), reverse=True):
                if result.skill_id in self.skills and result.total_score() >= self.confidence_threshold:
                    matched_skills.append(self.skills[result.skill_id])
                    if len(matched_skills) >= max_results:
                        break

            # Update cache
            if matched_skills:
                await self._update_matching_cache(cache_key, user_request, context,
                                                [skill.__class__.__name__ for skill in matched_skills])

            # Track performance metrics
            execution_time = time.time() - start_time
            await self._track_matching_performance(user_request, len(matched_skills), execution_time)

            logger.info(f"Found {len(matched_skills)} skills for request in {execution_time:.3f}s")
            return matched_skills

        except Exception as e:
            logger.error(f"Error in find_skills_for_request: {e}")
            # Fallback to basic matching
            return await self._fallback_skill_matching(user_request, context, max_results)

    async def _perform_hybrid_matching(self, user_request: str, context: Optional[Dict[str, Any]]) -> List[SkillMatchResult]:
        """
        Perform hybrid skill matching combining multiple algorithms and data sources.
        """
        match_results = []

        # 1. Embedding-based similarity matching
        embedding_matches = await self._embedding_similarity_matching(user_request)

        # 2. Intent and capability matching
        intent_matches = self._intent_capability_matching(user_request)

        # 3. Contextual matching from memory
        contextual_matches = await self._contextual_memory_matching(user_request, context)

        # 4. Performance-based matching
        performance_matches = await self._performance_based_matching(user_request)

        # 5. Historical pattern matching
        historical_matches = await self._historical_pattern_matching(user_request)

        # Combine and score all matching results
        all_skill_ids = set()
        for matches in [embedding_matches, intent_matches, contextual_matches,
                       performance_matches, historical_matches]:
            all_skill_ids.update(match.skill_id for match in matches)

        for skill_id in all_skill_ids:
            if skill_id not in self.metadata:
                continue

            metadata = self.metadata[skill_id]
            combined_result = SkillMatchResult(
                skill_id=skill_id,
                skill_name=metadata.name,
                confidence_score=0.0,
                performance_score=0.0,
                historical_success_rate=0.0,
                contextual_relevance=0.0
            )

            # Aggregate scores from different matching methods
            for match_list in [embedding_matches, intent_matches, contextual_matches,
                             performance_matches, historical_matches]:
                for match in match_list:
                    if match.skill_id == skill_id:
                        combined_result.confidence_score = max(combined_result.confidence_score, match.confidence_score)
                        combined_result.performance_score = max(combined_result.performance_score, getattr(match, 'performance_score', 0.0))
                        combined_result.historical_success_rate = max(combined_result.historical_success_rate, getattr(match, 'historical_success_rate', 0.0))
                        combined_result.contextual_relevance = max(combined_result.contextual_relevance, getattr(match, 'contextual_relevance', 0.0))
                        combined_result.match_reasons.extend(match.match_reasons)
                        combined_result.capabilities_matched.extend(getattr(match, 'capabilities_matched', []))
                        combined_result.intents_matched.extend(getattr(match, 'intents_matched', []))

            # Add performance data from database
            if self.enable_performance_weighting:
                combined_result.performance_score = self.skill_success_rates.get(skill_id, 0.5)
                combined_result.execution_time_estimate = self.skill_execution_times.get(skill_id, 1.0)

            match_results.append(combined_result)

        return match_results

    async def _embedding_similarity_matching(self, user_request: str) -> List[SkillMatchResult]:
        """Perform embedding-based similarity matching."""
        results = []

        if not self.embedding_client:
            return results

        try:
            user_embedding = await self.embedding_client.generate_embedding(user_request)

            for skill_id, metadata in self.metadata.items():
                if skill_id not in self.skills or not metadata.embedding:
                    continue

                similarity = self._cosine_similarity(user_embedding, metadata.embedding)

                if similarity > 0.3:  # Minimum similarity threshold
                    results.append(SkillMatchResult(
                        skill_id=skill_id,
                        skill_name=metadata.name,
                        confidence_score=similarity,
                        match_reasons=[f"Embedding similarity: {similarity:.3f}"]
                    ))

        except Exception as e:
            logger.warning(f"Error in embedding similarity matching: {e}")

        return results

    def _intent_capability_matching(self, user_request: str) -> List[SkillMatchResult]:
        """Perform intent and capability based matching."""
        results = []
        request_words = set(user_request.lower().split())

        for skill_id, metadata in self.metadata.items():
            if skill_id not in self.skills:
                continue

            match_reasons = []
            confidence_score = 0.0
            matched_intents = []
            matched_capabilities = []

            # Check intent matching
            for intent in metadata.intents:
                intent_words = set(intent.lower().split())
                overlap = len(request_words & intent_words)
                if overlap > 0:
                    similarity = overlap / len(request_words | intent_words)
                    confidence_score += similarity * 0.6
                    matched_intents.append(intent)
                    match_reasons.append(f"Intent match: {intent}")

            # Check capability matching
            for cap in metadata.capabilities:
                cap_words = set(cap.name.lower().split())
                overlap = len(request_words & cap_words)
                if overlap > 0:
                    similarity = overlap / len(request_words | cap_words)
                    confidence_score += similarity * 0.4
                    matched_capabilities.append(cap.name)
                    match_reasons.append(f"Capability match: {cap.name}")

            if confidence_score > 0.1:
                results.append(SkillMatchResult(
                    skill_id=skill_id,
                    skill_name=metadata.name,
                    confidence_score=min(confidence_score, 1.0),
                    match_reasons=match_reasons,
                    intents_matched=matched_intents,
                    capabilities_matched=matched_capabilities
                ))

        return results

    async def _contextual_memory_matching(self, user_request: str, context: Optional[Dict[str, Any]]) -> List[SkillMatchResult]:
        """Perform contextual matching using IntelligentMemory."""
        results = []

        if not self.memory_system or not self.enable_contextual_matching:
            return results

        try:
            # Query memory for similar requests
            conversation_id = context.get('conversation_id', 'system') if context else 'system'
            memory_results = await self.memory_system.retrieve_memory(conversation_id, user_request)

            # Analyze historical patterns
            skill_usage_patterns = {}
            for result in memory_results.results:
                content = result.get('content', '')
                if isinstance(content, dict):
                    # Look for skill usage in historical data
                    used_skill = content.get('skill_used') or content.get('executed_skill')
                    if used_skill:
                        if used_skill not in skill_usage_patterns:
                            skill_usage_patterns[used_skill] = []
                        skill_usage_patterns[used_skill].append(result.get('relevance_score', 0.5))

            # Create match results based on historical usage
            for skill_name, scores in skill_usage_patterns.items():
                # Find skill by name
                for skill_id, metadata in self.metadata.items():
                    if metadata.name == skill_name and skill_id in self.skills:
                        avg_score = sum(scores) / len(scores) if scores else 0.5
                        results.append(SkillMatchResult(
                            skill_id=skill_id,
                            skill_name=skill_name,
                            confidence_score=avg_score,
                            contextual_relevance=avg_score,
                            match_reasons=[f"Historical usage pattern (avg score: {avg_score:.3f})"]
                        ))
                        break

        except Exception as e:
            logger.warning(f"Error in contextual memory matching: {e}")

        return results

    async def _performance_based_matching(self, user_request: str) -> List[SkillMatchResult]:
        """Perform performance-based matching using database metrics."""
        results = []

        if not self.enable_performance_weighting:
            return results

        try:
            # Get performance metrics for all skills
            for skill_id, metadata in self.metadata.items():
                if skill_id not in self.skills:
                    continue

                success_rate = self.skill_success_rates.get(skill_id, 0.5)
                avg_execution_time = self.skill_execution_times.get(skill_id, 1.0)

                # Calculate performance score (higher success rate and lower execution time is better)
                performance_score = success_rate * (1.0 / max(avg_execution_time, 0.1))

                if performance_score > 0.1:
                    results.append(SkillMatchResult(
                        skill_id=skill_id,
                        skill_name=metadata.name,
                        confidence_score=performance_score,
                        performance_score=performance_score,
                        match_reasons=[f"Performance score: {performance_score:.3f} (success: {success_rate:.2f}, time: {avg_execution_time:.2f}s)"]
                    ))

        except Exception as e:
            logger.warning(f"Error in performance-based matching: {e}")

        return results

    async def _historical_pattern_matching(self, user_request: str) -> List[SkillMatchResult]:
        """Perform historical pattern matching."""
        results = []

        if not self.enable_historical_learning or not self.memory_system:
            return results

        try:
            # Query for similar historical requests
            system_memory = await self.memory_system.retrieve_memory("system", user_request)

            # Analyze patterns in historical successful executions
            for result in system_memory.results:
                content = result.get('content', {})
                if isinstance(content, dict) and content.get('success') and content.get('skill_used'):
                    skill_name = content['skill_used']
                    relevance = result.get('relevance_score', 0.5)

                    # Find matching skill
                    for skill_id, metadata in self.metadata.items():
                        if metadata.name == skill_name and skill_id in self.skills:
                            results.append(SkillMatchResult(
                                skill_id=skill_id,
                                skill_name=skill_name,
                                confidence_score=relevance,
                                historical_success_rate=relevance,
                                match_reasons=[f"Historical success pattern (relevance: {relevance:.3f})"]
                            ))
                            break

        except Exception as e:
            logger.warning(f"Error in historical pattern matching: {e}")

        return results

    async def _fallback_skill_matching(self, user_request: str, context: Optional[Dict[str, Any]],
                                     max_results: int) -> List[BaseSkill]:
        """Fallback skill matching when enhanced matching fails."""
        try:
            logger.warning("Using fallback skill matching")

            # Use the fallback manager if available
            if self.fallback_manager:
                fallback_result = await self.fallback_manager.execute_fallback(
                    "skill_matching",
                    {"user_request": user_request, "context": context}
                )
                if fallback_result.get('success') and fallback_result.get('skills'):
                    return [self.skills[sid] for sid in fallback_result['skills'] if sid in self.skills]

            # Basic fallback: return all available skills up to max_results
            available_skills = [skill for skill in self.skills.values() if skill is not None]
            return available_skills[:max_results] if available_skills else []

        except Exception as e:
            logger.error(f"Error in fallback skill matching: {e}")
            return []

    def _generate_cache_key(self, user_request: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for request and context."""
        request_hash = hashlib.md5(user_request.encode()).hexdigest()
        context_hash = hashlib.md5(str(sorted(context.items())).encode()).hexdigest() if context else ""
        return f"{request_hash}_{context_hash}"

    async def _update_matching_cache(self, cache_key: str, user_request: str,
                                   context: Optional[Dict[str, Any]], matched_skill_names: List[str]):
        """Update the matching cache with new results."""
        try:
            cache_entry = SkillMatchingCacheEntry(
                request_hash=cache_key,
                request_text=user_request,
                matched_skills=matched_skill_names,
                timestamp=datetime.utcnow(),
                context_hash=hashlib.md5(str(context).encode()).hexdigest() if context else "",
                performance_metrics={"match_count": len(matched_skill_names)}
            )

            self.matching_cache[cache_key] = cache_entry

            # Clean up old cache entries if we exceed max size
            if len(self.matching_cache) > self.cache_max_size:
                await self._cleanup_matching_cache()

        except Exception as e:
            logger.warning(f"Error updating matching cache: {e}")

    async def _cleanup_matching_cache(self):
        """Clean up expired cache entries."""
        try:
            current_time = datetime.utcnow()
            expired_keys = []

            for key, entry in self.matching_cache.items():
                if entry.is_expired(self.cache_ttl_seconds):
                    expired_keys.append(key)

            for key in expired_keys:
                del self.matching_cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        except Exception as e:
            logger.warning(f"Error cleaning up matching cache: {e}")

    async def _periodic_cache_cleanup(self):
        """Periodic task to clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                await self._cleanup_matching_cache()
            except Exception as e:
                logger.warning(f"Error in periodic cache cleanup: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _track_matching_performance(self, user_request: str, match_count: int, execution_time: float):
        """Track performance metrics for skill matching."""
        try:
            if self.metrics_collector:
                await self.metrics_collector.record_metric(
                    "skill_matching_performance",
                    {
                        "request_length": len(user_request),
                        "match_count": match_count,
                        "execution_time": execution_time,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Error tracking matching performance: {e}")

    async def _load_performance_data(self):
        """Load skill performance data from database."""
        try:
            if not self.metrics_collector:
                return

            # Load success rates
            success_metrics = await self.metrics_collector.get_metrics("skill_success_rate")
            for metric in success_metrics:
                skill_id = metric.get('skill_id')
                success_rate = metric.get('value', 0.5)
                self.skill_success_rates[skill_id] = success_rate

            # Load execution times
            execution_metrics = await self.metrics_collector.get_metrics("skill_execution_time")
            for metric in execution_metrics:
                skill_id = metric.get('skill_id')
                exec_time = metric.get('value', 1.0)
                self.skill_execution_times[skill_id] = exec_time

            logger.info(f"Loaded performance data for {len(self.skill_success_rates)} skills")

        except Exception as e:
            logger.warning(f"Error loading performance data: {e}")

    async def update_skill_performance(self, skill_id: str, success: bool, execution_time: float):
        """Update performance metrics for a skill."""
        try:
            if skill_id not in self.skill_performance_history:
                self.skill_performance_history[skill_id] = []

            # Record the performance
            self.skill_performance_history[skill_id].append({
                "timestamp": datetime.utcnow(),
                "success": success,
                "execution_time": execution_time
            })

            # Keep only last 100 entries per skill
            if len(self.skill_performance_history[skill_id]) > 100:
                self.skill_performance_history[skill_id] = self.skill_performance_history[skill_id][-100:]

            # Update success rate
            recent_performance = self.skill_performance_history[skill_id][-20:]  # Last 20 executions
            success_rate = sum(1 for p in recent_performance if p['success']) / len(recent_performance)
            self.skill_success_rates[skill_id] = success_rate

            # Update average execution time
            avg_exec_time = sum(p['execution_time'] for p in recent_performance) / len(recent_performance)
            self.skill_execution_times[skill_id] = avg_exec_time

            # Store in database if available
            if self.metrics_collector:
                await self.metrics_collector.record_metric(
                    "skill_success_rate",
                    {"skill_id": skill_id, "value": success_rate}
                )
                await self.metrics_collector.record_metric(
                    "skill_execution_time",
                    {"skill_id": skill_id, "value": avg_exec_time}
                )

            logger.debug(f"Updated performance for skill {skill_id}: success_rate={success_rate:.3f}, avg_time={avg_exec_time:.3f}s")

        except Exception as e:
            logger.warning(f"Error updating skill performance for {skill_id}: {e}")

skill_registry = SkillRegistry()

@safe_execute(fallback_response={"error": "Skill registry inte tillgängligt"})
async def initialize_skill_registry() -> Dict[str, Any]:
    return await skill_registry.initialize()

__all__ = [
    'SkillCapability',
    'SkillMetadata', 
    'SkillRegistry',
    'skill_registry',
    'initialize_skill_registry'
]
