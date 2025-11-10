"""
Self-Building Orchestrator - Implementation using the shared core.

This orchestrator provides self-building capabilities by extending
the BaseOrchestratorCore with functionality focused on:
- Skill discovery and execution
- Dynamic skill generation via a self-building component
- Agent delegation
- MCP server integration
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import json
import os
import hashlib

from app.core.config.settings import get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.core.skills.skill_registry import skill_registry
from app.core.agent.analysis_task_engine import analysis_task_engine as MVP_Agent
from app.core.nlp.request_analyzer import request_analyzer, RequestType as AnalysisRequestType
from app.core.skills.base import BaseSkill
from app.core.self_building import self_builder  # Import the self-building component

# Enhanced imports for improved skill matching
try:
    from app.core.memory.memory_system import MemorySystem, MemorySystemConfig
    from app.db.metrics_collector import MetricsCollector
    from app.core.fallbacks import FallbackManager
except ImportError:
    MemorySystem = None
    MetricsCollector = None
    FallbackManager = None

# Import the shared core
from .orchestrator_core import (
    BaseOrchestratorCore,
    RequestType,
    ProcessingStrategy,
    RequestAnalysis,
    ProcessingResult
)

# Logger setup
logger = logging.getLogger(__name__)

settings = get_settings()


class BasicSelfBuildingOrchestrator(BaseOrchestratorCore):
    """
    A self-building orchestrator that provides:
    - Dynamic skill discovery and execution
    - Advanced skill generation capabilities via a dedicated self-building component
    - Agent delegation for complex tasks
    - Component discovery and management, including MCP servers
    """
    
    def __init__(self):
        super().__init__()

        # Core components for self-building functionality
        self.skill_registry = skill_registry
        self.agent = MVP_Agent
        self.self_builder = self_builder
        self.mcp_servers = {}

        # Enhanced components for improved skill matching
        self.memory_system = None
        self.metrics_collector = None
        self.fallback_manager = None

        # Configuration for the orchestrator
        self.config.update({
            "enable_self_building": True,
            "max_basic_complexity": 0.7,
            "basic_skill_timeout": 45.0,
            "mcp_settings_path": os.path.join(os.path.dirname(__file__), "..", "..", "config", "mcp_settings.json"),
            # Enhanced skill matching configuration
            "enable_enhanced_matching": True,
            "max_skill_matches": 5,
            "matching_cache_ttl": 3600,
            "performance_tracking": True,
            "contextual_matching": True,
            "fallback_enabled": True
        })

        self._load_mcp_settings()
        self._initialize_enhanced_components()

    def _initialize_enhanced_components(self):
        """Initialize enhanced components for improved skill matching."""
        try:
            # Initialize Memory System
            if MemorySystem and self.config.get("enable_enhanced_matching"):
                self.memory_system = MemorySystem(MemorySystemConfig())
                logger.info("MemorySystem initialized for BasicOrchestrator")

            # Initialize Metrics Collector
            if MetricsCollector and self.config.get("performance_tracking"):
                self.metrics_collector = MetricsCollector()
                logger.info("MetricsCollector initialized for BasicOrchestrator")

            # Initialize Fallback Manager
            if FallbackManager and self.config.get("fallback_enabled"):
                self.fallback_manager = FallbackManager()
                logger.info("FallbackManager initialized for BasicOrchestrator")

        except Exception as e:
            logger.warning(f"Error initializing enhanced components: {e}")

    def _load_mcp_settings(self):
        """Loads MCP server settings from the specified JSON file."""
        settings_path = self.config.get("mcp_settings_path")
        
        # Normalize path to be safe
        normalized_path = os.path.normpath(settings_path)

        if not os.path.exists(normalized_path):
            logger.warning(f"MCP settings file not found at '{normalized_path}'. No MCP servers will be loaded.")
            return

        try:
            with open(normalized_path, 'r') as f:
                mcp_config = json.load(f)
            
            self.mcp_servers = mcp_config.get("servers", {})
            if self.mcp_servers:
                logger.info(f"Successfully loaded {len(self.mcp_servers)} MCP servers from '{normalized_path}'.")
            else:
                logger.warning(f"No servers found in MCP settings file: '{normalized_path}'.")

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load or parse MCP settings from '{normalized_path}': {e}")
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the orchestrator with essential components.
        
        Returns:
            Dict containing initialization status and component information
        """
        logger.info("Initializing Self-Building Orchestrator...")
        
        try:
            # Initialize core components
            await request_analyzer.initialize()

            # Initialize skill registry with enhanced components
            skill_registry_result = await self.skill_registry.initialize(
                memory_system=self.memory_system,
                metrics_collector=self.metrics_collector,
                fallback_manager=self.fallback_manager
            )

            agent_result = await self.agent.initialize()
            self_builder_result = await self.self_builder.initialize()

            # Initialize enhanced components
            if self.memory_system:
                await self.memory_system.initialize()
            if self.metrics_collector:
                await self.metrics_collector.initialize()
            if self.fallback_manager:
                await self.fallback_manager.initialize()

            # Set up component relationships
            # Note: agent already has its own skill_registry instance

            result = {
                "orchestrator_initialized": True,
                "skill_registry": skill_registry_result,
                "agent": agent_result,
                "self_builder": self_builder_result,
                "mcp_servers": list(self.mcp_servers.keys()),
                "components_ready": True,
                "basic_mode": False,
                "enhanced_matching": self.memory_system is not None,
                "performance_tracking": self.metrics_collector is not None,
                "fallback_system": self.fallback_manager is not None
            }

            logger.info(f"Enhanced Self-Building Orchestrator initialized successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error initializing Self-Building Orchestrator: {e}")
            return {
                "orchestrator_initialized": False,
                "error": str(e),
                "components_ready": False,
                "basic_mode": True
            }
    
    async def _analyze_request(self, user_request: str, context: Dict[str, Any]) -> RequestAnalysis:
        """
        Request analysis using available components.
        
        Args:
            user_request: The user's request
            context: Additional context information
            
        Returns:
            RequestAnalysis with analysis results
        """
        try:
            # Use the existing request analyzer
            analysis_result = await request_analyzer.analyze_request(user_request)
            
            # Find existing skills
            existing_skills = await self._find_matching_skills(user_request, context)
            
            # Determine request type based on analysis
            if existing_skills:
                if len(existing_skills) == 1:
                    request_type = RequestType.SKILL_AVAILABLE
                else:
                    request_type = RequestType.NEEDS_SKILL_COMBINATION
            elif analysis_result.complexity > self.config["max_basic_complexity"]:
                request_type = RequestType.TOO_COMPLEX
            elif analysis_result.confidence < self.config["confidence_threshold"]:
                request_type = RequestType.UNCLEAR
            else:
                request_type = RequestType.NEEDS_NEW_SKILL
            
            # Suggest strategy based on request type
            suggested_strategy = self._suggest_strategy(request_type, existing_skills)
            
            # Find similar requests from history
            similar_requests = await self._find_similar_requests(user_request)
            
            return RequestAnalysis(
                request_type=request_type,
                complexity_score=analysis_result.complexity,
                required_capabilities=analysis_result.required_skills or [],
                suggested_strategy=suggested_strategy,
                confidence=analysis_result.confidence,
                similar_requests=similar_requests
            )
            
        except Exception as e:
            logger.error(f"Error in request analysis: {e}")
            # Fallback analysis
            return RequestAnalysis(
                request_type=RequestType.UNCLEAR,
                complexity_score=0.5,
                required_capabilities=[],
                suggested_strategy=ProcessingStrategy.SKILL_GENERATION,
                confidence=0.3,
                similar_requests=[]
            )
    
    async def _execute_strategy(self, strategy: ProcessingStrategy, user_request: str, 
                              context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute the selected strategy using available components.
        
        Args:
            strategy: The strategy to execute
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            ProcessingResult with execution results
        """
        try:
            if strategy == ProcessingStrategy.DIRECT_SKILL_EXECUTION:
                return await self._execute_direct_skill(user_request, context, analysis)
            elif strategy == ProcessingStrategy.SKILL_GENERATION:
                return await self._execute_skill_generation(user_request, context, analysis)
            elif strategy == ProcessingStrategy.AGENT_DELEGATION:
                return await self._execute_agent_delegation(user_request, context, analysis)
            elif strategy == ProcessingStrategy.HYBRID_APPROACH:
                return await self._execute_hybrid_approach(user_request, context, analysis)
            else:
                # Fallback to skill generation for unknown strategies
                return await self._execute_skill_generation(user_request, context, analysis)
                
        except Exception as e:
            logger.error(f"Error executing strategy {strategy}: {e}")
            raise
    
    async def _find_matching_skills(self, user_request: str, context: Dict[str, Any]) -> List[BaseSkill]:
        """
        Find skills that match the request using enhanced skill registry with multiple criteria.

        Args:
            user_request: The user's request
            context: Additional context information

        Returns:
            List of matching skills ordered by relevance
        """
        try:
            # Use enhanced skill matching if available
            if self.config.get("enable_enhanced_matching") and hasattr(self.skill_registry, 'find_skills_for_request'):
                matching_skills = await self.skill_registry.find_skills_for_request(
                    user_request, context, max_results=self.config.get("max_skill_matches", 5)
                )
                logger.debug(f"Enhanced matching found {len(matching_skills)} skills for request: {user_request[:50]}...")
                return matching_skills

            # Fallback to basic matching
            if hasattr(self.skill_registry, 'find_skills_for_request'):
                matching_skills = await self.skill_registry.find_skills_for_request(user_request)
                return matching_skills or []

            # Final fallback - return empty list
            logger.warning("No skill matching method available, returning empty list")
            return []

        except Exception as e:
            logger.error(f"Error finding matching skills: {e}")
            # Try fallback manager if available
            if self.fallback_manager:
                try:
                    fallback_result = await self.fallback_manager.execute_fallback(
                        "skill_matching",
                        {"user_request": user_request, "context": context}
                    )
                    if fallback_result.get('success') and fallback_result.get('skills'):
                        return [self.skill_registry.get_skill_by_id(sid) for sid in fallback_result['skills']
                               if self.skill_registry.get_skill_by_id(sid)]
                except Exception as fallback_error:
                    logger.error(f"Fallback skill matching also failed: {fallback_error}")

            return []
    
    def _suggest_strategy(self, request_type: RequestType, existing_skills: List[BaseSkill]) -> ProcessingStrategy:
        """
        Suggest processing strategy for the orchestrator.
        
        Args:
            request_type: The type of request
            existing_skills: List of existing skills that match
            
        Returns:
            ProcessingStrategy to use
        """
        if request_type == RequestType.SKILL_AVAILABLE:
            if len(existing_skills) == 1:
                return ProcessingStrategy.DIRECT_SKILL_EXECUTION
            else:
                return ProcessingStrategy.MULTI_SKILL_ORCHESTRATION
        elif request_type == RequestType.NEEDS_NEW_SKILL and self.config["enable_self_building"]:
            return ProcessingStrategy.SKILL_GENERATION
        elif request_type == RequestType.TOO_COMPLEX and self.config.get("enable_agent_delegation", True):
            return ProcessingStrategy.AGENT_DELEGATION
        else:
            return ProcessingStrategy.HYBRID_APPROACH
    
    async def _execute_direct_skill(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute request using an existing skill with enhanced matching and performance tracking.

        Args:
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results

        Returns:
            ProcessingResult with execution results
        """
        try:
            start_time = time.time()

            # Use enhanced skill matching if available
            if self.config.get("enable_enhanced_matching"):
                matched_skills = await self.skill_registry.find_skills_for_request(
                    user_request, context, max_results=1
                )
                skill = matched_skills[0] if matched_skills else None
            else:
                # Fallback to basic matching
                skill = await self.skill_registry.find_best_skill_for_request(user_request, context)

            if not skill:
                raise HappyOSError("No suitable skill found for direct execution")

            # Execute skill with timeout
            try:
                skill_start_time = time.time()
                result = await asyncio.wait_for(
                    skill.execute(user_request, context),
                    timeout=self.config["basic_skill_timeout"]
                )
                skill_execution_time = time.time() - skill_start_time

                # Track skill performance
                if self.skill_registry and hasattr(self.skill_registry, 'update_skill_performance'):
                    success = result.get('success', True) if isinstance(result, dict) else True
                    await self.skill_registry.update_skill_performance(
                        skill.__class__.__name__, success, skill_execution_time
                    )

                # Store execution in memory for learning
                if self.memory_system:
                    await self.memory_system.store_memory(
                        context.get('conversation_id', 'system'),
                        user_request,
                        {
                            "skill_used": skill.__class__.__name__,
                            "execution_time": skill_execution_time,
                            "success": result.get('success', True) if isinstance(result, dict) else True,
                            "result": result
                        }
                    )

                # Record metrics
                if self.metrics_collector:
                    await self.metrics_collector.record_metric(
                        "skill_execution",
                        {
                            "skill_name": skill.__class__.__name__,
                            "execution_time": skill_execution_time,
                            "success": result.get('success', True) if isinstance(result, dict) else True,
                            "request_length": len(user_request)
                        }
                    )

                total_execution_time = time.time() - start_time

                return ProcessingResult(
                    success=True,
                    message="Request processed successfully using existing skill",
                    data=result or {},
                    processing_type="direct_skill_execution",
                    execution_time=total_execution_time,
                    skill_used=skill.__class__.__name__,
                    performance_metrics={
                        "skill_execution_time": skill_execution_time,
                        "total_execution_time": total_execution_time,
                        "skill_confidence": 1.0,
                        "enhanced_matching_used": self.config.get("enable_enhanced_matching", False)
                    }
                )

            except asyncio.TimeoutError:
                # Track failed execution due to timeout
                if self.skill_registry and hasattr(self.skill_registry, 'update_skill_performance'):
                    await self.skill_registry.update_skill_performance(
                        skill.__class__.__name__, False, self.config["basic_skill_timeout"]
                    )
                raise HappyOSError(f"Skill execution timed out after {self.config['basic_skill_timeout']} seconds")

        except Exception as e:
            logger.error(f"Error in direct skill execution: {e}")
            raise
    
    async def _execute_skill_generation(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute request by generating a new skill using the self-building component.
        
        Args:
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            ProcessingResult with execution results
        """
        try:
            if not self.config["enable_self_building"]:
                raise HappyOSError("Self-building is disabled in the orchestrator")
            
            max_attempts = self.config.get("max_skill_generation_attempts", 3)
            
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Self-building attempt {attempt + 1}/{max_attempts}")
                    
                    # Use the self-building component
                    generation_result = await self.self_builder.build_skill(
                        user_request,
                        context=context,
                        required_capabilities=analysis.required_capabilities
                    )
                    
                    if generation_result and generation_result.get('success'):
                        skill_instance = generation_result.get('skill_instance')
                        skill_name = generation_result.get('skill_name')

                        if not skill_instance or not skill_name:
                            logger.warning(f"Self-building attempt {attempt + 1} succeeded but returned invalid result.")
                            continue

                        try:
                            # Test the newly built skill
                            test_result = await asyncio.wait_for(
                                skill_instance.execute(user_request, context),
                                timeout=self.config["basic_skill_timeout"]
                            )
                            
                            if test_result:
                                await self.skill_registry.register_skill(skill_name, skill_instance)
                                logger.info(f"Successfully built and registered new skill: {skill_name}")
                                
                                return ProcessingResult(
                                    success=True,
                                    message="Request processed successfully with a newly built skill.",
                                    data=test_result or {},
                                    processing_type="skill_generation",
                                    execution_time=0.0,
                                    new_skill_created=True,
                                    skill_used=skill_name,
                                    performance_metrics={
                                        "build_attempts": attempt + 1,
                                        "skill_build_time": generation_result.get('build_time', 0),
                                        "skill_test_success": True
                                    }
                                )
                            else:
                                logger.warning(f"Built skill '{skill_name}' failed validation on attempt {attempt + 1}.")
                        except Exception as test_error:
                            logger.error(f"Error testing built skill '{skill_name}' on attempt {attempt + 1}: {test_error}")
                            if attempt == max_attempts - 1:
                                raise
                    else:
                        error_msg = generation_result.get('error') if generation_result else "Unknown error"
                        logger.warning(f"Self-building failed on attempt {attempt + 1}: {error_msg}")
                        
                except Exception as e:
                    logger.error(f"Exception during self-building attempt {attempt + 1}: {e}")
                    if attempt == max_attempts - 1:
                        raise
            
            raise HappyOSError(f"Self-building failed after {max_attempts} attempts.")
            
        except Exception as e:
            logger.error(f"Error in self-building process: {e}")
            raise
    
    async def _execute_agent_delegation(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute request by delegating to the agent.
        
        Args:
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            ProcessingResult with execution results
        """
        try:
            # Delegate to the MVP agent
            result = await self.agent.process_request(user_request, context)
            
            return ProcessingResult(
                success=True,
                message="Request processed successfully by agent delegation",
                data=result or {},
                processing_type="agent_delegation",
                execution_time=0.0,
                agent_used=self.agent.__class__.__name__,
                performance_metrics={
                    "agent_execution_time": result.get('execution_time', 0) if isinstance(result, dict) else 0,
                    "agent_confidence": result.get('confidence', 1.0) if isinstance(result, dict) else 1.0
                }
            )
            
        except Exception as e:
            logger.error(f"Error in agent delegation: {e}")
            raise
    
    async def _execute_hybrid_approach(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute request using a hybrid approach (self-building with agent fallback).
        
        Args:
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            ProcessingResult with execution results
        """
        try:
            # Try self-building first
            try:
                return await self._execute_skill_generation(user_request, context, analysis)
            except Exception as skill_error:
                logger.warning(f"Self-building failed, trying agent delegation: {skill_error}")
                
                # Fallback to agent delegation
                try:
                    return await self._execute_agent_delegation(user_request, context, analysis)
                except Exception as agent_error:
                    logger.error(f"Agent delegation also failed: {agent_error}")
                    
                    # Final fallback - return error with suggestions
                    return ProcessingResult(
                        success=False,
                        message="All processing strategies failed. Please rephrase your request.",
                        data={
                            "skill_build_error": str(skill_error),
                            "agent_delegation_error": str(agent_error),
                            "suggestion": "Try rephrasing your request or providing more context"
                        },
                        processing_type="hybrid_approach_failed",
                        execution_time=0.0,
                        error_details={
                            "hybrid_approach": True,
                            "all_strategies_failed": True
                        }
                    )
            
        except Exception as e:
            logger.error(f"Error in hybrid approach: {e}")
            raise
    
    async def _find_similar_requests(self, user_request: str) -> List[Dict[str, Any]]:
        """
        Find similar requests from history.
        
        Args:
            user_request: The user's request
            
        Returns:
            List of similar requests
        """
        # Simple implementation - in practice, you'd use embeddings or other similarity measures
        similar = []
        request_words = set(user_request.lower().split())
        
        for result in self.processing_history[-10:]:  # Check last 10 requests
            if hasattr(result, 'data') and 'original_request' in result.data:
                other_words = set(result.data['original_request'].lower().split())
                similarity = len(request_words & other_words) / len(request_words | other_words) if (request_words | other_words) else 0
                
                if similarity > 0.3:  # 30% similarity threshold
                    similar.append({
                        'request': result.data['original_request'],
                        'similarity': similarity,
                        'success': result.success,
                        'strategy': result.strategy_used.value if result.strategy_used else None
                    })
        
        return sorted(similar, key=lambda x: x['similarity'], reverse=True)[:3]
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics.
        
        Returns:
            Dict containing statistics
        """
        return {
            **self.get_performance_stats(),
            "basic_mode": False,
            "skill_registry_ready": hasattr(self, 'skill_registry') and self.skill_registry is not None,
            "agent_ready": hasattr(self, 'agent') and self.agent is not None,
            "self_builder_ready": hasattr(self, 'self_builder') and self.self_builder is not None,
            "mcp_servers_loaded": len(self.mcp_servers)
        }
