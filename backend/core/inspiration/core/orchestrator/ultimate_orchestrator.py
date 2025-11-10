"""
Ultimate Self-Building Orchestrator - Advanced implementation using the shared core.

This orchestrator provides advanced self-building capabilities by extending
the BaseOrchestratorCore with sophisticated functionality including:
- Advanced skill discovery and orchestration
- Enhanced skill generation with multiple attempts
- Multi-agent delegation with Owl and CAMEL integration
- Advanced request analysis and strategy selection
- Performance optimization and learning capabilities
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from dataclasses import dataclass
import uuid

from app.core.config.settings import get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.core.performance import monitor_performance
from app.core.agent.analysis_task_engine import analysis_task_engine as enhanced_mr_happy_agent
from app.core.nlp.unified_intent_classifier import unified_intent_classifier
from app.core.skills.skill_registry_optimized import optimized_skill_registry
from app.core.skills.skill_generator import generate_skill_for_request
from app.core.skills.base import BaseSkill

# Enhanced system components
from app.core.memory.memory_system import MemorySystem, MemorySystemConfig
from app.core.database.connection import get_db_connection

# Import A2A Protocol integration (replaces CAMEL/OWL)
try:
    from app.a2a_protocol.core.orchestrator import A2AProtocolManager
    from app.a2a_protocol.core.agent_factory import create_agent, get_agent_by_role, create_agent_team
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    A2AProtocolManager = None
    create_agent = None
    get_agent_by_role = None
    create_agent_team = None

from app.llm.router import get_llm_client

# Remove old CAMEL/OWL imports - replaced by A2A Protocol

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


@dataclass
class EnhancedRequestAnalysis(RequestAnalysis):
    """Enhanced analysis with more detailed information."""
    intent_classification: Dict[str, Any]
    complexity_breakdown: Dict[str, float]
    ambiguity_score: float
    multi_step_indicators: List[str]


@dataclass
class UltimateProcessingResult(ProcessingResult):
    """Enhanced processing result with more context."""
    confidence_score: float = 0.0
    performance_metrics: Dict[str, Any] = None
    error_details: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {}
        if self.metadata is None:
            self.metadata = {}


class UltimateSelfBuildingOrchestrator(BaseOrchestratorCore):
    """
    Ultimate self-building orchestrator with full system integration.
    
    This orchestrator provides:
    - Full integration with optimized skill registry
    - Enhanced Mr Happy agent integration
    - Robust error recovery mechanisms
    - Performance optimizations
    - Better skill generation feedback
    - Owl integration for advanced multi-agent capabilities
    - CAMEL integration for multi-agent collaboration
    """
    
    def __init__(self):
        super().__init__()

        # Core components for advanced functionality
        self.skill_registry = optimized_skill_registry
        self.mr_happy_agent = enhanced_mr_happy_agent
        self.intent_classifier = unified_intent_classifier

        # Enhanced system clients for advanced integration (A2A replaces CAMEL/OWL)
        self.a2a_protocol_manager = A2AProtocolManager() if A2A_AVAILABLE else None

        # Remove old CAMEL/OWL clients
        # self.owl_client = OwlClient() if OWL_AVAILABLE else None
        # self.camel_client = camel_client if CAMEL_AVAILABLE else None
        # self.owl_network_client = OwlNetworkClient() if OWL_AVAILABLE else None
        # self.camel_network_client = CamelNetworkClient() if CAMEL_AVAILABLE else None

        # Agent delegation and multi-agent systems
        from app.core.orchestrator.delegation.agent_delegator import agent_delegator
        from app.agents.multi_agent import agent_orchestrator
        self.agent_delegator = agent_delegator
        self.multi_agent_orchestrator = agent_orchestrator

        # Advanced memory and database systems
        self.memory_system = None
        self.db_connection = None
        self.intelligent_memory = None  # Direct access for compatibility
        
        # Advanced configuration
        self.config.update({
            "max_skill_generation_attempts": 5,  # More attempts than basic
            "complexity_threshold": 0.8,  # Higher threshold for advanced processing
            "confidence_threshold": 0.7,  # Higher confidence requirement
            "enable_skill_combination": True,
            "enable_agent_delegation": True,
            "enable_owl_integration": False,  # Replaced by A2A
            "enable_camel_integration": False,  # Replaced by A2A
            "enable_a2a_integration": A2A_AVAILABLE,
            "performance_monitoring": True,
            "advanced_skill_timeout": 60.0,
            "enable_multi_step_processing": True,
            "enable_context_aware_processing": True
        })
        
        # Advanced performance metrics
        self.performance_stats.update({
            "owl_requests": 0,
            "camel_requests": 0,
            "multi_skill_orchestrations": 0,
            "hybrid_approach_success": 0,
            "error_recovery_rate": 0.0
        })
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the ultimate orchestrator with all components.
        
        Returns:
            Dict containing initialization status and component information
        """
        logger.info("Initializing UltimateSelfBuildingOrchestrator...")
        
        try:
            # Initialize core components
            skill_registry_result = await self.skill_registry.initialize()
            mr_happy_result = await self.mr_happy_agent.initialize()

            # Initialize intent classifier
            await self.intent_classifier.initialize()

            # Set up component relationships
            self.mr_happy_agent.set_skill_registry(self.skill_registry)
            self.mr_happy_agent.set_orchestrator(self)
            
            # Initialize A2A Protocol integration (replaces CAMEL/OWL)
            a2a_result = {"available": False}
            if A2A_AVAILABLE and self.a2a_protocol_manager:
                try:
                    # Initialize A2A protocol manager
                    await self.a2a_protocol_manager.initialize()

                    a2a_result = {
                        "available": True,
                        "protocol_manager_initialized": True,
                        "agent_factory_available": bool(create_agent and get_agent_by_role),
                        "agent_team_creation_available": bool(create_agent_team)
                    }
                    logger.info("A2A Protocol integration initialized successfully")
                except Exception as e:
                    logger.error(f"Error initializing A2A Protocol integration: {str(e)}")
                    a2a_result = {
                        "available": False,
                        "error": str(e)
                    }

            # Initialize advanced memory system
            memory_result = {"available": False}
            try:
                self.memory_system = MemorySystem(MemorySystemConfig())
                memory_init_result = await self.memory_system.initialize()
                memory_result = {
                    "available": True,
                    "initialized": True,
                    "components": memory_init_result.get("components_active", 0),
                    "intelligent_memory": memory_init_result.get("intelligent_memory", False),
                    "persistent_memory": memory_init_result.get("persistent_memory", False),
                    "memory_optimizer": memory_init_result.get("memory_optimizer", False),
                    "summarized_memory": memory_init_result.get("summarized_memory", False)
                }
                logger.info("Advanced MemorySystem initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing advanced MemorySystem: {str(e)}")
                memory_result = {
                    "available": False,
                    "error": str(e)
                }

            # Initialize advanced database connection
            database_result = {"available": False}
            try:
                self.db_connection = await get_db_connection()
                db_init_result = await self.db_connection.initialize()
                database_result = {
                    "available": True,
                    "initialized": True,
                    "database_type": db_init_result.get("database_type"),
                    "pool_size": db_init_result.get("pool_size"),
                    "auto_scaling": db_init_result.get("auto_scaling", False),
                    "health_monitoring": db_init_result.get("health_monitoring", False)
                }
                logger.info("Advanced DatabaseConnection initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing advanced DatabaseConnection: {str(e)}")
                database_result = {
                    "available": False,
                    "error": str(e)
                }
            result = {
                "orchestrator_initialized": True,
                "skill_registry": skill_registry_result,
                "mr_happy_agent": mr_happy_result,
                "intent_classifier_ready": True,
                "performance_tracking_active": self.config["performance_monitoring"],
                "a2a_integration": a2a_result,
                "integration_complete": True,
                "advanced_mode": True,
                "memory_system": memory_result,
                "database_connection": database_result
            }
            
            logger.info(f"UltimateSelfBuildingOrchestrator initialized successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error initializing UltimateSelfBuildingOrchestrator: {e}")
            return {
                "orchestrator_initialized": False,
                "error": str(e),
                "components_ready": False,
                "advanced_mode": True
            }
    
    async def _coordinate_all_systems(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """
        Coordinate all advanced systems for optimal request processing.
        This method ensures intelligent memory usage, database performance tracking,
        and unified system coordination.
        """
        try:
            coordination_result = {
                "memory_integration": False,
                "database_tracking": False,
                "system_coordination": True,
                "performance_optimization": False,
                "context_enrichment": False
            }

            # Extract conversation ID for memory integration
            conversation_id = context.get('conversation_id', f"conv_{datetime.utcnow().timestamp()}")

            # Step 1: Memory Integration - Retrieve relevant context
            if self.memory_system and analysis.complexity_score > 0.3:
                try:
                    memory_entries = await self.memory_system.retrieve_memory(
                        conversation_id=conversation_id,
                        query=user_request,
                        context=context
                    )

                    if memory_entries.results:
                        # Enrich context with relevant memory
                        context['memory_context'] = memory_entries.results[:3]  # Top 3 relevant memories
                        context['memory_source'] = memory_entries.source
                        coordination_result["memory_integration"] = True
                        coordination_result["context_enrichment"] = True

                        logger.info(f"Integrated {len(memory_entries.results)} memory entries from {memory_entries.source}")

                except Exception as e:
                    logger.warning(f"Memory integration failed: {e}")

            # Step 2: Performance Tracking - Start database tracking
            if self.db_connection:
                try:
                    # Track this orchestrator request
                    await self.db_connection._track_query_performance(
                        query=f"ultimate_orchestrator_request_{conversation_id}",
                        execution_time=0.0,  # Will be updated at completion
                        success=True
                    )
                    coordination_result["database_tracking"] = True
                    logger.info("Database performance tracking initialized")

                except Exception as e:
                    logger.warning(f"Database tracking failed: {e}")

            # Step 3: System Coordination - Optimize based on analysis
            coordination_decisions = self._optimize_system_coordination(analysis, context)

            # Step 4: Performance Optimization - Apply optimizations
            if coordination_decisions.get("performance_optimization_needed", False):
                await self._apply_performance_optimizations(analysis, context)
                coordination_result["performance_optimization"] = True

            coordination_result.update({
                "coordination_decisions": coordination_decisions,
                "conversation_id": conversation_id,
                "system_load": await self._assess_system_load(),
                "optimization_applied": coordination_result["performance_optimization"]
            })

            logger.info(f"System coordination completed: {coordination_result}")
            return coordination_result

        except Exception as e:
            logger.error(f"Error in system coordination: {e}")
            return {
                "system_coordination": False,
                "error": str(e),
                "fallback_mode": True
            }

    def _optimize_system_coordination(self, analysis: EnhancedRequestAnalysis, context: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize system coordination based on analysis."""
        decisions = {
            "performance_optimization_needed": False,
            "memory_preloading": False,
            "database_connection_pooling": True,
            "parallel_processing": False,
            "caching_strategy": "standard"
        }

        # High complexity requests need performance optimization
        if analysis.complexity_score > 0.8:
            decisions["performance_optimization_needed"] = True
            decisions["parallel_processing"] = True

        # Multi-step requests benefit from memory preloading
        if len(analysis.multi_step_indicators) > 1:
            decisions["memory_preloading"] = True

        # Low ambiguity requests can use aggressive caching
        if analysis.ambiguity_score < 0.3:
            decisions["caching_strategy"] = "aggressive"

        return decisions

    async def _apply_performance_optimizations(self, analysis: EnhancedRequestAnalysis, context: Dict[str, Any]):
        """Apply performance optimizations based on analysis."""
        try:
            # Memory optimization
            if self.memory_system:
                await self.memory_system.optimize_memory()

            # Database optimization
            if self.db_connection:
                # Trigger connection pool optimization
                pass  # Database auto-scaling is handled internally

            logger.info("Performance optimizations applied")

        except Exception as e:
            logger.warning(f"Performance optimization failed: {e}")

    async def _assess_system_load(self) -> Dict[str, Any]:
        """Assess current system load."""
        load_info = {
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
            "database_connections": 0,
            "active_tasks": 0
        }

        try:
            # Get memory system stats
            if self.memory_system:
                memory_stats = self.memory_system.get_system_stats()
                load_info["memory_system_active"] = memory_stats.get("system_status") == "initialized"

            # Get database connection metrics
            if self.db_connection:
                db_metrics = self.db_connection.get_connection_metrics()
                load_info["database_connections"] = db_metrics.get("pool_metrics", {}).get("current_size", 0)

            # Get agent system load
            if hasattr(self, 'multi_agent_orchestrator'):
                agent_status = self.multi_agent_orchestrator.get_system_status()
                load_info["active_tasks"] = agent_status.get("active_tasks", 0)

        except Exception as e:
            logger.warning(f"System load assessment failed: {e}")

        return load_info

    async def _analyze_request(self, user_request: str, context: Dict[str, Any]) -> EnhancedRequestAnalysis:
        """
        Advanced request analysis using multiple components.
        
        Args:
            user_request: The user's request
            context: Additional context information
            
        Returns:
            EnhancedRequestAnalysis with detailed analysis results
        """
        try:
            # System coordination first
            coordination_result = await self._coordinate_all_systems(user_request, context, None)  # Pre-coordination

            # Intent classification
            intent_result = await self.intent_classifier.classify_intent(user_request)
            
            # Complexity analysis
            complexity_breakdown = await self._calculate_complexity_detailed(user_request, context)
            complexity_score = sum(complexity_breakdown.values())
            
            # Ambiguity analysis
            ambiguity_score = await self._calculate_ambiguity(user_request)
            
            # Find existing skills
            existing_skills = await self._find_matching_skills(user_request, context)
            
            # Determine request type
            if existing_skills:
                if len(existing_skills) == 1:
                    request_type = RequestType.SKILL_AVAILABLE
                else:
                    request_type = RequestType.NEEDS_SKILL_COMBINATION
            elif complexity_score > self.config["complexity_threshold"]:
                request_type = RequestType.TOO_COMPLEX
            elif intent_result.get('confidence', 0) < self.config["confidence_threshold"]:
                request_type = RequestType.UNCLEAR
            else:
                request_type = RequestType.NEEDS_NEW_SKILL
            
            # Suggest strategy
            suggested_strategy = self._suggest_advanced_strategy(request_type, complexity_score, existing_skills)
            
            # Find similar requests
            similar_requests = await self._find_similar_requests(user_request)
            
            # Multi-step indicators
            multi_step_indicators = self._find_multi_step_indicators(user_request)
            
            return EnhancedRequestAnalysis(
                request_type=request_type,
                complexity_score=min(complexity_score, 1.0),
                required_capabilities=intent_result.get('capabilities', []),
                suggested_strategy=suggested_strategy,
                confidence=intent_result.get('confidence', 0.5),
                similar_requests=similar_requests,
                intent_classification=intent_result,
                complexity_breakdown=complexity_breakdown,
                ambiguity_score=ambiguity_score,
                multi_step_indicators=multi_step_indicators
            )
            
        except Exception as e:
            logger.error(f"Error in advanced request analysis: {e}")
            # Fallback analysis
            return EnhancedRequestAnalysis(
                request_type=RequestType.UNCLEAR,
                complexity_score=0.5,
                required_capabilities=[],
                suggested_strategy=ProcessingStrategy.SKILL_GENERATION,
                confidence=0.3,
                similar_requests=[],
                intent_classification={},
                complexity_breakdown={"fallback": 0.5},
                ambiguity_score=0.5,
                multi_step_indicators=[]
            )
    
    async def _calculate_complexity_detailed(self, user_request: str, context: Dict[str, Any]) -> Dict[str, float]:
        """Calculate detailed request complexity score."""
        complexity_factors = {
            "length": min(len(user_request) / 1000, 1.0) * 0.2,
            "technical_terms": self._count_technical_terms(user_request) / 20 * 0.3,
            "multi_step": 1.0 if any(word in user_request.lower() for word in ['then', 'after', 'next', 'also', 'and', 'first', 'second', 'finally']) else 0.0,
            "context_dependency": 0.5 if context else 0.0,
            "nested_operations": 1.0 if any(word in user_request.lower() for word in ['within', 'inside', 'nested', 'hierarchical']) else 0.0,
            "conditional_logic": 1.0 if any(word in user_request.lower() for word in ['if', 'when', 'unless', 'provided that']) else 0.0
        }
        
        return complexity_factors
    
    def _count_technical_terms(self, text: str) -> int:
        """Count technical terms in text."""
        technical_terms = [
            'api', 'database', 'algorithm', 'function', 'class', 'method',
            'server', 'client', 'protocol', 'framework', 'library', 'module',
            'authentication', 'authorization', 'encryption', 'deployment',
            'orchestration', 'microservice', 'container', 'kubernetes',
            'machine learning', 'artificial intelligence', 'neural network',
            'blockchain', 'distributed system', 'concurrency', 'parallel processing'
        ]
        return sum(1 for term in technical_terms if term in text.lower())
    
    async def _calculate_ambiguity(self, user_request: str) -> float:
        """Calculate ambiguity score using LLM."""
        try:
            # In a real implementation, this would use an LLM to rate ambiguity
            # For now, we'll use a simple heuristic
            question_words = ['what', 'how', 'why', 'when', 'where', 'which', 'who']
            has_question_words = any(word in user_request.lower().split() for word in question_words)
            has_vague_terms = any(word in user_request.lower() for word in ['something', 'thing', 'stuff', 'etc', 'and so on'])
            
            ambiguity_score = 0.0
            if has_question_words:
                ambiguity_score += 0.3
            if has_vague_terms:
                ambiguity_score += 0.4
            if len(user_request.split()) < 5:  # Very short requests are often ambiguous
                ambiguity_score += 0.3
                
            return min(ambiguity_score, 1.0)
        except Exception:
            return 0.5  # Default ambiguity
    
    def _find_multi_step_indicators(self, user_request: str) -> List[str]:
        """Find indicators of multi-step processing."""
        indicators = []
        multi_step_words = ['then', 'after', 'next', 'also', 'and', 'first', 'second', 'finally', 'step by step']
        
        for word in multi_step_words:
            if word in user_request.lower():
                indicators.append(word)
                
        return indicators
    
    async def _execute_strategy(self, strategy: ProcessingStrategy, user_request: str, 
                              context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """
        Execute the selected strategy using advanced components.
        
        Args:
            strategy: The strategy to execute
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            UltimateProcessingResult with execution results
        """
        try:
            # Enhanced system decision making for Owl/CAMEL usage
            use_a2a = False

            # Check A2A Protocol integration (replaces OWL/CAMEL)
            if (self.config["enable_a2a_integration"] and
                A2A_AVAILABLE and self.a2a_protocol_manager and 
                strategy in [ProcessingStrategy.MULTI_SKILL_ORCHESTRATION, ProcessingStrategy.AGENT_DELEGATION]):
                try:
                    use_a2a = await self._should_use_a2a(user_request, context, analysis)
                    if use_a2a:
                        logger.info("Request will be processed using A2A Protocol integration")
                        context["use_a2a"] = True
                        context["a2a_protocol_manager"] = self.a2a_protocol_manager
                        context["agent_factory"] = {"create_agent": create_agent, "get_agent_by_role": get_agent_by_role}
                        self.performance_stats["a2a_requests"] += 1
                except Exception as e:
                    logger.error(f"Error checking A2A Protocol: {str(e)}")
                    use_a2a = False
                except Exception as e:
                    logger.error(f"Error checking CAMEL with enhanced client: {str(e)}")
                    use_camel = False
            
            # Execute with A2A Protocol (replaces CAMEL/OWL)
            if A2A_AVAILABLE and self.a2a_protocol_manager and strategy in [ProcessingStrategy.MULTI_SKILL_ORCHESTRATION, ProcessingStrategy.AGENT_DELEGATION]:
                logger.info(f"Using A2A Protocol for strategy: {strategy}")
                result = await self._execute_with_a2a(strategy, user_request, context, analysis)
            else:
                # Execute with standard components
                if strategy == ProcessingStrategy.DIRECT_SKILL_EXECUTION:
                    result = await self._execute_direct_skill(user_request, context, analysis)
                elif strategy == ProcessingStrategy.SKILL_GENERATION:
                    result = await self._execute_skill_generation(user_request, context, analysis)
                elif strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
                    result = await self._execute_multi_skill_orchestration(user_request, context, analysis)
                elif strategy == ProcessingStrategy.AGENT_DELEGATION:
                    result = await self._execute_agent_delegation(user_request, context, analysis)
                elif strategy == ProcessingStrategy.HYBRID_APPROACH:
                    result = await self._execute_hybrid_approach(user_request, context, analysis)
                else:
                    # Fallback to skill generation for unknown strategies
                    result = await self._execute_skill_generation(user_request, context, analysis)
            
            # Ensure we return the correct result type
            if not isinstance(result, UltimateProcessingResult):
                # Convert ProcessingResult to UltimateProcessingResult
                result = UltimateProcessingResult(
                    success=result.success,
                    message=result.message,
                    data=result.data,
                    processing_type=result.processing_type,
                    execution_time=result.execution_time,
                    skill_used=result.skill_used,
                    agent_used=result.agent_used,
                    new_skill_created=result.new_skill_created,
                    strategy_used=result.strategy_used,
                    confidence_score=analysis.confidence if hasattr(analysis, 'confidence') else 0.5,
                    performance_metrics=getattr(result, 'performance_metrics', {}),
                    error_details=getattr(result, 'error_details', None),
                    metadata={}
                )
            
            # Store result in memory system for future learning
            if result.success and self.memory_system:
                try:
                    conversation_id = context.get('conversation_id', f"conv_{datetime.utcnow().timestamp()}")
                    await self.memory_system.store_memory(
                        conversation_id=conversation_id,
                        user_input=user_request,
                        context_data={
                            "strategy_used": strategy.value,
                            "result": result.data,
                            "success": result.success,
                            "processing_time": result.execution_time,
                            "confidence": analysis.confidence if hasattr(analysis, 'confidence') else 0.5
                        }
                    )
                    logger.info(f"Stored execution result in memory system for conversation {conversation_id}")
                except Exception as e:
                    logger.warning(f"Failed to store result in memory: {e}")

            return result

        except Exception as e:
            logger.error(f"Error executing strategy {strategy}: {e}")
            raise
    
    async def _execute_direct_skill(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """Execute request using existing skill."""
        try:
            # Find the best skill
            skill = await self.skill_registry.find_best_skill_for_request_optimized(user_request, context)
            
            if not skill:
                raise HappyOSError("No suitable skill found for direct execution")
            
            # Execute skill with timeout
            try:
                result = await asyncio.wait_for(
                    skill.execute(user_request, context),
                    timeout=self.config["advanced_skill_timeout"]
                )
                
                return UltimateProcessingResult(
                    success=True,
                    message="Request processed successfully using existing skill",
                    data=result or {},
                    processing_type="direct_skill_execution",
                    execution_time=0.0,  # Will be set by caller
                    skill_used=skill.__class__.__name__,
                    confidence_score=analysis.confidence,
                    performance_metrics={
                        "skill_execution_time": result.get('execution_time', 0) if isinstance(result, dict) else 0,
                        "skill_confidence": 1.0
                    },
                    metadata={
                        "skill_type": type(skill).__name__,
                        "skill_complexity": getattr(skill, 'complexity', 'unknown')
                    }
                )
                
            except asyncio.TimeoutError:
                raise HappyOSError(f"Skill execution timed out after {self.config['advanced_skill_timeout']} seconds")
                
        except Exception as e:
            logger.error(f"Error in direct skill execution: {e}")
            raise
    
    async def _execute_skill_generation(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """Execute request by generating new skill."""
        try:
            max_attempts = self.config["max_skill_generation_attempts"]
            
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Advanced skill generation attempt {attempt + 1}/{max_attempts}")
                    
                    # Generate skill with enhanced parameters
                    generation_result = await generate_skill_for_request(
                        user_request, 
                        context, 
                        required_capabilities=analysis.required_capabilities,
                        complexity_level=analysis.complexity_score,
                        intent_classification=analysis.intent_classification
                    )
                    
                    if generation_result.get('success'):
                        # Test the generated skill
                        skill_instance = generation_result['skill_instance']
                        
                        try:
                            test_result = await asyncio.wait_for(
                                skill_instance.execute(user_request, context),
                                timeout=self.config["advanced_skill_timeout"]
                            )
                            
                            if test_result:
                                # Register the new skill
                                await self.skill_registry.register_generated_skill(
                                    generation_result['skill_name'],
                                    skill_instance
                                )
                                
                                return UltimateProcessingResult(
                                    success=True,
                                    message="Request processed successfully with newly generated skill",
                                    data=test_result or {},
                                    processing_type="skill_generation",
                                    execution_time=0.0,
                                    new_skill_created=True,
                                    skill_used=generation_result['skill_name'],
                                    confidence_score=analysis.confidence,
                                    performance_metrics={
                                        "generation_attempts": attempt + 1,
                                        "skill_generation_time": generation_result.get('generation_time', 0),
                                        "skill_test_success": True,
                                        "complexity_handled": analysis.complexity_score
                                    },
                                    metadata={
                                        "generated_skill_type": type(skill_instance).__name__,
                                        "generation_method": generation_result.get('method', 'unknown'),
                                        "capabilities_covered": analysis.required_capabilities
                                    }
                                )
                            else:
                                logger.warning(f"Generated skill failed test on attempt {attempt + 1}")
                        except Exception as test_error:
                            logger.error(f"Error testing generated skill on attempt {attempt + 1}: {test_error}")
                            if attempt == max_attempts - 1:
                                raise
                    else:
                        logger.warning(f"Skill generation failed on attempt {attempt + 1}: {generation_result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"Error in skill generation attempt {attempt + 1}: {e}")
                    if attempt == max_attempts - 1:
                        raise
            
            # All attempts failed
            raise HappyOSError(f"Skill generation failed after {max_attempts} attempts")
            
        except Exception as e:
            logger.error(f"Error in skill generation: {e}")
            raise
    
    async def _execute_multi_step_orchestration(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """
        Execute request using advanced multi-step processing orchestration.

        This method intelligently breaks down complex requests into multiple steps
        and orchestrates their execution using various system components.
        """
        try:
            logger.info(f"Starting multi-step orchestration for: {user_request[:50]}...")

            # Step 1: Analyze request for multi-step decomposition
            steps = await self._decompose_request_into_steps(user_request, analysis)

            if not steps or len(steps) <= 1:
                logger.info("Request doesn't require multi-step processing, falling back to single execution")
                return await self._execute_direct_skill(user_request, context, analysis)

            logger.info(f"Decomposed request into {len(steps)} steps")

            # Step 2: Plan execution order and dependencies
            execution_plan = await self._plan_multi_step_execution(steps, context, analysis)

            # Step 3: Execute steps with intelligent orchestration
            step_results = []
            accumulated_context = context.copy()

            for step_info in execution_plan:
                step_number = step_info['step']
                step_request = step_info['request']
                step_agent = step_info['agent']
                step_dependencies = step_info['dependencies']

                logger.info(f"Executing step {step_number}: {step_request[:30]}... with agent {step_agent}")

                # Wait for dependencies if any
                if step_dependencies:
                    await self._wait_for_step_dependencies(step_dependencies, step_results)

                # Execute step using appropriate agent/system
                step_result = await self._execute_step_with_agent(
                    step_request, accumulated_context, analysis, step_agent
                )

                step_results.append({
                    'step': step_number,
                    'request': step_request,
                    'agent': step_agent,
                    'result': step_result,
                    'success': step_result.get('success', False)
                })

                # Update accumulated context with step result
                accumulated_context.update(step_result.get('output_context', {}))

                # Check if we should continue with remaining steps
                if not step_result.get('success', False):
                    logger.warning(f"Step {step_number} failed, evaluating continuation strategy")
                    should_continue = await self._evaluate_step_failure_continuation(
                        step_number, step_result, execution_plan
                    )
                    if not should_continue:
                        break

            # Step 4: Synthesize results from all steps
            final_result = await self._synthesize_multi_step_results(step_results, analysis)

            return UltimateProcessingResult(
                success=final_result.get('overall_success', False),
                message=final_result.get('message', 'Multi-step orchestration completed'),
                data={
                    'step_results': step_results,
                    'final_synthesis': final_result,
                    'total_steps': len(steps),
                    'successful_steps': sum(1 for r in step_results if r['success'])
                },
                processing_type="multi_step_orchestration",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                performance_metrics={
                    'steps_executed': len(step_results),
                    'successful_steps': sum(1 for r in step_results if r['success']),
                    'failed_steps': sum(1 for r in step_results if not r['success']),
                    'orchestration_complexity': len(steps)
                },
                metadata={
                    'multi_step_orchestration': True,
                    'execution_plan': execution_plan,
                    'enhanced_integration': True
                }
            )

        except Exception as e:
            logger.error(f"Error in multi-step orchestration: {e}")
            raise

    async def _decompose_request_into_steps(self, user_request: str, analysis: EnhancedRequestAnalysis) -> List[Dict[str, Any]]:
        """Decompose a complex request into manageable steps."""
        try:
            # Use LLM to intelligently decompose the request
            llm_client = get_llm_client()
            if not llm_client:
                return []

            decomposition_prompt = f"""
            Analyze this user request and break it down into 2-4 logical, sequential steps.
            Each step should be:
            1. Specific and actionable
            2. Independent where possible
            3. Clear in its objective
            4. Appropriately sized (not too big, not too small)

            User Request: "{user_request}"

            Context Information:
            - Complexity Score: {analysis.complexity_score}
            - Multi-step Indicators: {analysis.multi_step_indicators}
            - Required Capabilities: {analysis.required_capabilities}

            Return a JSON array of steps, where each step has:
            - "description": Clear description of what this step should accomplish
            - "agent_type": Best agent type for this step ("research", "coding", "writing", "analysis", "general")
            - "dependencies": Array of step numbers this step depends on (empty for first step)
            - "estimated_complexity": 1-5 scale

            JSON Output:
            """

            messages = [{"role": "user", "content": decomposition_prompt}]

            response = await llm_client.generate(messages, temperature=0.3, max_tokens=1000)

            if response and response.get("content"):
                steps_text = response["content"].strip()

                # Try to parse JSON
                try:
                    steps = json.loads(steps_text)
                    if isinstance(steps, list):
                        return steps
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse decomposition JSON: {steps_text}")

            # Fallback: simple keyword-based decomposition
            return await self._fallback_request_decomposition(user_request, analysis)

        except Exception as e:
            logger.error(f"Error decomposing request: {e}")
            return []

    async def _fallback_request_decomposition(self, user_request: str, analysis: EnhancedRequestAnalysis) -> List[Dict[str, Any]]:
        """Fallback method for request decomposition using heuristics."""
        steps = []
        words = user_request.lower().split()

        # Check for common multi-step patterns
        if 'first' in words or 'then' in words or 'after' in words or 'next' in words:
            # Try to split by conjunctions
            sentences = user_request.split('.')
            for i, sentence in enumerate(sentences):
                if sentence.strip():
                    steps.append({
                        "description": sentence.strip(),
                        "agent_type": "general",
                        "dependencies": [i] if i > 0 else [],
                        "estimated_complexity": 2
                    })
        else:
            # Single comprehensive step
            steps.append({
                "description": user_request,
                "agent_type": "general",
                "dependencies": [],
                "estimated_complexity": 3
            })

        return steps

    async def _plan_multi_step_execution(self, steps: List[Dict[str, Any]], context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> List[Dict[str, Any]]:
        """Plan the execution order and parallelization of steps."""
        execution_plan = []

        for i, step in enumerate(steps):
            execution_plan.append({
                'step': i + 1,
                'request': step['description'],
                'agent': step['agent_type'],
                'dependencies': step.get('dependencies', []),
                'estimated_complexity': step.get('estimated_complexity', 2),
                'can_parallelize': len(step.get('dependencies', [])) == 0  # No dependencies = can run in parallel
            })

        # Sort by dependencies and complexity for optimal execution
        execution_plan.sort(key=lambda x: (len(x['dependencies']), x['estimated_complexity']))

        return execution_plan

    async def _execute_step_with_agent(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis, agent_type: str) -> Dict[str, Any]:
        """Execute a single step using the appropriate agent."""
        try:
            # Map agent types to execution methods
            agent_method_map = {
                'research': self._execute_research_step,
                'coding': self._execute_coding_step,
                'writing': self._execute_writing_step,
                'analysis': self._execute_analysis_step,
                'general': self._execute_general_step
            }

            execution_method = agent_method_map.get(agent_type, self._execute_general_step)

            return await execution_method(step_request, context, analysis)

        except Exception as e:
            logger.error(f"Error executing step with agent {agent_type}: {e}")
            return {
                'success': False,
                'error': str(e),
                'step_request': step_request,
                'agent_type': agent_type
            }

    async def _execute_research_step(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Execute a research-focused step."""
        # Use the research agent from multi_agent system
        if hasattr(self.multi_agent_orchestrator, 'agents') and 'ResearchAgent' in [agent.name for agent in self.multi_agent_orchestrator.agents.values()]:
            research_agent = self.multi_agent_orchestrator.agents['researchagent']
            from app.agents.multi_agent import Task
            task = Task(
                task_id=f"research_step_{uuid.uuid4().hex[:8]}",
                description=step_request,
                task_type="research",
                context=context
            )
            return await research_agent.process_task(task)
        else:
            # Fallback to skill-based execution
            return await self._execute_general_step(step_request, context, analysis)

    async def _execute_coding_step(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Execute a coding-focused step."""
        # Use OWL for coding tasks if available
        if self.config["enable_owl_integration"] and self.owl_client:
            # Create a coding-specific context
            coding_context = context.copy()
            coding_context['coding_task'] = True
            coding_context['language'] = self._detect_programming_language(step_request)

            owl_response = await self.owl_client.send_task_to_owl(
                task=step_request,
                context=coding_context,
                agent_type="coding"
            )

            return {
                'success': owl_response.success,
                'result': owl_response.data if owl_response.success else None,
                'error': owl_response.message if not owl_response.success else None,
                'agent_used': 'owl_coding',
                'output_context': {'coding_result': owl_response.data} if owl_response.success else {}
            }
        else:
            return await self._execute_general_step(step_request, context, analysis)

    async def _execute_writing_step(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Execute a writing-focused step."""
        # Use writing agent if available
        if hasattr(self.multi_agent_orchestrator, 'agents') and 'WritingAgent' in [agent.name for agent in self.multi_agent_orchestrator.agents.values()]:
            writing_agent = self.multi_agent_orchestrator.agents['writingagent']
            from app.agents.multi_agent import Task
            task = Task(
                task_id=f"writing_step_{uuid.uuid4().hex[:8]}",
                description=step_request,
                task_type="writing",
                context=context
            )
            return await writing_agent.process_task(task)
        else:
            return await self._execute_general_step(step_request, context, analysis)

    async def _execute_analysis_step(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Execute an analysis-focused step."""
        # Use enhanced analysis capabilities
        return await self._execute_general_step(step_request, context, analysis)

    async def _execute_general_step(self, step_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Execute a general step using available capabilities."""
        try:
            # Try to find an appropriate skill first
            skill = await self.skill_registry.find_best_skill_for_request_optimized(step_request, context)

            if skill:
                result = await skill.execute(step_request, context)
                return {
                    'success': True,
                    'result': result,
                    'agent_used': f'skill_{skill.__class__.__name__}',
                    'output_context': result.get('output_context', {})
                }
            else:
                # Fallback to skill generation
                generation_result = await self._execute_skill_generation(step_request, context, analysis)
                return {
                    'success': generation_result.success,
                    'result': generation_result.data,
                    'agent_used': 'skill_generation',
                    'error': generation_result.message if not generation_result.success else None,
                    'output_context': {}
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'agent_used': 'general_fallback'
            }

    def _detect_programming_language(self, request: str) -> str:
        """Detect programming language from request."""
        languages = ['python', 'javascript', 'java', 'cpp', 'c++', 'typescript', 'go', 'rust', 'php']
        request_lower = request.lower()

        for lang in languages:
            if lang in request_lower:
                return lang

        return 'python'  # Default

    async def _wait_for_step_dependencies(self, dependencies: List[int], step_results: List[Dict[str, Any]]):
        """Wait for dependent steps to complete."""
        for dep_step in dependencies:
            if dep_step <= len(step_results):
                # Dependency already completed
                continue
            else:
                # Wait a bit for dependency to complete (in real implementation, this would be more sophisticated)
                await asyncio.sleep(0.1)

    async def _evaluate_step_failure_continuation(self, failed_step: int, step_result: Dict[str, Any], execution_plan: List[Dict[str, Any]]) -> bool:
        """Evaluate whether to continue execution after a step failure."""
        # Simple heuristic: continue if less than 50% of steps have failed
        failed_count = sum(1 for result in step_results if not result.get('success', False))
        total_steps = len(execution_plan)

        # Continue if failure rate is less than 50%
        return (failed_count / total_steps) < 0.5

    async def _synthesize_multi_step_results(self, step_results: List[Dict[str, Any]], analysis: EnhancedRequestAnalysis) -> Dict[str, Any]:
        """Synthesize results from all executed steps."""
        try:
            successful_steps = [r for r in step_results if r['success']]
            failed_steps = [r for r in step_results if not r['success']]

            overall_success = len(successful_steps) > len(failed_steps)

            synthesis = {
                'overall_success': overall_success,
                'total_steps': len(step_results),
                'successful_steps': len(successful_steps),
                'failed_steps': len(failed_steps),
                'success_rate': len(successful_steps) / len(step_results) if step_results else 0,
                'message': f"Completed {len(successful_steps)}/{len(step_results)} steps successfully"
            }

            if successful_steps:
                # Combine outputs from successful steps
                combined_output = []
                for step in successful_steps:
                    result = step['result']
                    if isinstance(result, dict) and 'result' in result:
                        combined_output.append(str(result['result']))
                    else:
                        combined_output.append(str(result))

                synthesis['combined_output'] = '\n\n'.join(combined_output)

            if failed_steps:
                synthesis['failed_step_details'] = [
                    {'step': s['step'], 'error': s['result'].get('error', 'Unknown error')}
                    for s in failed_steps
                ]

            return synthesis

        except Exception as e:
            logger.error(f"Error synthesizing multi-step results: {e}")
            return {
                'overall_success': False,
                'error': str(e),
                'message': 'Failed to synthesize step results'
            }

    async def _execute_multi_skill_orchestration(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """Execute request using multiple skills in orchestration."""
        try:
            # Find all relevant skills
            relevant_skills = await self._find_all_relevant_skills(user_request, context)
            
            if not relevant_skills:
                raise HappyOSError("No relevant skills found for orchestration")
            
            self.performance_stats["multi_skill_orchestrations"] += 1
            
            # Plan execution sequence
            execution_plan = await self._plan_skill_execution(user_request, relevant_skills, context)
            
            # Execute skills in sequence
            results = []
            for step in execution_plan:
                skill = step['skill']
                input_data = step['input']
                
                result = await skill.execute(input_data, context)
                results.append(result)
                
                # Update context with result for next step
                context.update(result.get('output_context', {}))
            
            # Combine results
            combined_result = await self._combine_skill_results(results)
            
            return UltimateProcessingResult(
                success=True,
                message="Request processed successfully using skill orchestration",
                data=combined_result,
                processing_type="multi_skill_orchestration",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                performance_metrics={
                    "skills_used": len(relevant_skills),
                    "orchestration_steps": len(execution_plan),
                    "individual_results": len(results),
                    "orchestration_complexity": len(execution_plan) / len(relevant_skills)
                },
                metadata={
                    "skills_orchestrated": [skill.__class__.__name__ for skill in relevant_skills],
                    "execution_plan_length": len(execution_plan)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in multi-skill orchestration: {e}")
            raise
    
    async def _execute_agent_delegation(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """Execute request by delegating to enhanced agent system."""
        try:
            logger.info(f"Enhanced agent delegation requested for: {user_request[:50]}...")

            # Use agent delegator to find best agent type
            best_agent_type = await self.agent_delegator.find_best_agent_type(user_request, context)

            if not best_agent_type:
                logger.warning("No suitable agent type found for delegation, using general")
                best_agent_type = self.agent_delegator._get_agent_templates().get('general', {}).get('template', 'general')

            # Delegate to agent using enhanced delegator
            delegation_result = await self.agent_delegator.delegate_to_agent(
                agent_type=best_agent_type,
                request=user_request,
                context=context
            )

            if delegation_result.success:
                return UltimateProcessingResult(
                    success=True,
                    message=f"Request processed successfully by {best_agent_type.value} agent",
                    data=delegation_result.response,
                    processing_type="enhanced_agent_delegation",
                    execution_time=delegation_result.execution_time,
                    agent_used=delegation_result.agent_name,
                    confidence_score=analysis.confidence,
                    performance_metrics={
                        "delegation_successful": True,
                        "agent_execution_time": delegation_result.execution_time,
                        "capabilities_matched": len(analysis.required_capabilities),
                        "agents_used_count": len(delegation_result.agents_used),
                        "camel_conversation_id": delegation_result.camel_conversation_id
                    },
                    metadata={
                        "agent_type": best_agent_type.value if hasattr(best_agent_type, 'value') else str(best_agent_type),
                        "delegation_method": "enhanced_agent_delegator",
                        "agents_used": delegation_result.agents_used,
                        "camel_conversation_id": delegation_result.camel_conversation_id,
                        "enhanced_integration": True
                    }
                )
            else:
                logger.warning(f"Agent delegation failed: {delegation_result.error}")
                # Fallback to multi-agent orchestrator
                return await self._fallback_agent_delegation(user_request, context, analysis, delegation_result.error)

        except Exception as e:
            logger.error(f"Error in enhanced agent delegation: {e}")
            return await self._fallback_agent_delegation(user_request, context, analysis, str(e))

    async def _fallback_agent_delegation(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis, error_msg: str) -> UltimateProcessingResult:
        """Fallback agent delegation using multi-agent orchestrator."""
        try:
            logger.info("Using fallback multi-agent orchestrator for delegation")

            # Use multi-agent orchestrator as fallback
            result = await self.multi_agent_orchestrator.process_request(user_request, context)

            return UltimateProcessingResult(
                success=result.get('success', False),
                message=result.get('message', 'Fallback delegation completed'),
                data=result,
                processing_type="fallback_multi_agent_delegation",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                performance_metrics={
                    "fallback_used": True,
                    "original_error": error_msg,
                    "multi_agent_success": result.get('success', False)
                },
                metadata={
                    "fallback_reason": error_msg,
                    "multi_agent_orchestrator_used": True,
                    "enhanced_integration": True
                }
            )

        except Exception as fallback_error:
            logger.error(f"Fallback delegation also failed: {fallback_error}")

            return UltimateProcessingResult(
                success=False,
                message="All agent delegation methods failed",
                data={
                    "original_error": error_msg,
                    "fallback_error": str(fallback_error),
                    "suggestion": "Try rephrasing your request or breaking it into smaller parts"
                },
                processing_type="agent_delegation_failed",
                execution_time=0.0,
                confidence_score=0.1,
                error_details={
                    "agent_delegation_failed": True,
                    "all_methods_failed": True,
                    "original_error": error_msg,
                    "fallback_error": str(fallback_error)
                }
            )
    
    async def _execute_hybrid_approach(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """Execute request using hybrid approach."""
        try:
            # Try skill generation first
            try:
                result = await self._execute_skill_generation(user_request, context, analysis)
                self.performance_stats["hybrid_approach_success"] += 1
                return result
            except Exception as skill_error:
                logger.warning(f"Skill generation failed, trying agent delegation: {skill_error}")
                
                # Fallback to agent delegation
                try:
                    result = await self._execute_agent_delegation(user_request, context, analysis)
                    self.performance_stats["hybrid_approach_success"] += 1
                    return result
                except Exception as agent_error:
                    logger.error(f"Agent delegation also failed: {agent_error}")
                    
                    # Final fallback - return error with suggestions
                    return UltimateProcessingResult(
                        success=False,
                        message="Request too complex. Please provide more specific details or break it into smaller parts.",
                        data={
                            "skill_generation_error": str(skill_error),
                            "agent_delegation_error": str(agent_error),
                            "suggestion": "Try rephrasing your request or providing more context"
                        },
                        processing_type="hybrid_approach_failed",
                        execution_time=0.0,
                        confidence_score=0.1,
                        error_details={
                            "hybrid_approach": True,
                            "all_strategies_failed": True,
                            "skill_error": str(skill_error),
                            "agent_error": str(agent_error)
                        }
                    )
            
        except Exception as e:
            logger.error(f"Error in hybrid approach: {e}")
            raise
    
    async def _execute_with_a2a(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """
        Execute using A2A Protocol for multi-agent coordination.

        Replaces CAMEL/OWL functionality with A2A-based agent orchestration.
        """
        try:
            start_time = time.time()

            # Create agent team using A2A
            if strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
                # Create team for complex multi-step tasks
                agent_team = await create_agent_team(
                    team_name=f"a2a_team_{uuid.uuid4().hex[:8]}",
                    roles=["coordinator", "research", "coding", "writing"]
                )
            elif strategy == ProcessingStrategy.AGENT_DELEGATION:
                # Create specialized agents for delegation
                agent_team = await create_agent_team(
                    team_name=f"delegation_team_{uuid.uuid4().hex[:8]}",
                    roles=["coordinator", "specialist"]
                )
            else:
                # Default team
                agent_team = await create_agent_team(
                    team_name=f"default_team_{uuid.uuid4().hex[:8]}",
                    roles=["coordinator"]
                )

            # Execute through A2A protocol manager
            workflow_result = await self.a2a_protocol_manager.execute_workflow(
                workflow_type="multi_agent_task",
                user_request=user_request,
                context=context,
                agent_team=agent_team,
                analysis=analysis
            )

            execution_time = time.time() - start_time

            return UltimateProcessingResult(
                success=workflow_result.get("success", False),
                result=workflow_result.get("result", {}),
                execution_time=execution_time,
                strategy=strategy,
                confidence_score=workflow_result.get("confidence", 0.8),
                metadata={
                    "a2a_agents_used": len(agent_team),
                    "workflow_type": "multi_agent_task",
                    "execution_details": workflow_result
                }
            )

        except Exception as e:
            logger.error(f"Error in A2A execution: {str(e)}")
            return UltimateProcessingResult(
                success=False,
                result={"error": str(e)},
                execution_time=time.time() - start_time,
                strategy=strategy,
                error_details={"a2a_error": str(e)}
            )
        """
        Execute a strategy using enhanced Owl integration with OwlClient.
        """
        if not OWL_AVAILABLE or not self.owl_client:
            logger.warning("Owl integration not available, falling back to regular execution")
            return await self._execute_strategy(strategy, user_request, context, analysis)

        logger.info(f"Executing strategy {strategy} with enhanced Owl integration")

        # Determine agent type based on strategy using enhanced logic
        agent_type = self._determine_owl_agent_type(strategy, user_request, analysis)

        # Prepare enhanced context for Owl with network client information
        owl_context = context.copy()
        owl_context.update({
            "request_type": analysis.request_type.value,
            "complexity": analysis.complexity_score,
            "ambiguity": analysis.ambiguity_score,
            "confidence": analysis.confidence,
            "multi_step_indicators": analysis.multi_step_indicators,
            "required_capabilities": analysis.required_capabilities,
            "happyos_version": "1.0.0",
            "network_client_available": bool(self.owl_network_client)
        })

        # Use OwlClient directly for enhanced control
        try:
            owl_response = await self.owl_client.send_task_to_owl(
                task=user_request,
                context=owl_context,
                agent_type=agent_type
            )

            if not owl_response.success:
                logger.error(f"Enhanced Owl task failed: {owl_response.message}")
                return await self._execute_strategy(strategy, user_request, context, analysis)

            # Process results with enhanced error handling
            result_data = owl_response.data
            workflow_id = result_data.get('workflow_id')

            # Enhanced result processing based on agent type
            if agent_type == "camel_chat":
                return await self._process_owl_skill_creation_result(result_data, analysis, workflow_id)
            elif agent_type == "multi_agent":
                return await self._process_owl_multi_agent_result(result_data, analysis, workflow_id)
            else:
                return await self._process_owl_generic_result(result_data, analysis, workflow_id, agent_type)

        except Exception as e:
            logger.error(f"Error in enhanced Owl integration: {str(e)}")
            return await self._execute_strategy(strategy, user_request, context, analysis)
    
    async def _execute_with_camel(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """
        Execute a strategy using enhanced CAMEL integration.
        """
        logger.info(f"Executing strategy {strategy} with enhanced CAMEL integration")

        # Use the A2A Protocol execution method
        return await self._execute_with_a2a(strategy, user_request, context, analysis)
    
    async def _should_use_a2a(self, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> bool:
        """Decision making for when to use A2A Protocol integration."""
        try:
            # Use A2A for complex multi-agent requests
            if (analysis.complexity_score > 0.7 or
                len(analysis.multi_step_indicators) > 2 or
                analysis.ambiguity_score > 0.6):

                # Check if we can create appropriate agents
                if create_agent and get_agent_by_role:
                    return True

            # Use A2A for team-based tasks
            team_keywords = ['team', 'collaborate', 'together', 'multiple', 'group', 'coordinate', 'agents']
            if any(word in user_request.lower() for word in team_keywords):
                return True

            return False

        except Exception as e:
            logger.error(f"Error in A2A decision making: {e}")
            return False

    def _suggest_advanced_strategy(self, request_type: RequestType, complexity_score: float, existing_skills: List[BaseSkill]) -> ProcessingStrategy:
        """Suggest advanced processing strategy with intelligent decision making."""
        try:
            # Enhanced strategy selection based on multiple factors
            strategy_score = self._calculate_strategy_scores(request_type, complexity_score, existing_skills)

            # Select strategy with highest score
            best_strategy = max(strategy_score.items(), key=lambda x: x[1])[0]

            logger.info(f"Selected advanced strategy: {best_strategy.value} with score {strategy_score[best_strategy]:.2f}")
            return best_strategy

        except Exception as e:
            logger.error(f"Error in advanced strategy suggestion: {e}")
            # Fallback to basic strategy selection
            return self._fallback_strategy_selection(request_type, existing_skills)

    def _calculate_strategy_scores(self, request_type: RequestType, complexity_score: float, existing_skills: List[BaseSkill]) -> Dict[ProcessingStrategy, float]:
        """Calculate scores for different processing strategies."""
        scores = {}

        # Base scores for each strategy
        base_scores = {
            ProcessingStrategy.DIRECT_SKILL_EXECUTION: 0.0,
            ProcessingStrategy.SKILL_GENERATION: 0.0,
            ProcessingStrategy.MULTI_SKILL_ORCHESTRATION: 0.0,
            ProcessingStrategy.AGENT_DELEGATION: 0.0,
            ProcessingStrategy.HYBRID_APPROACH: 0.0
        }

        # Adjust scores based on request type
        if request_type == RequestType.SKILL_AVAILABLE:
            if len(existing_skills) == 1:
                base_scores[ProcessingStrategy.DIRECT_SKILL_EXECUTION] += 0.8
            else:
                base_scores[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] += 0.7
                base_scores[ProcessingStrategy.DIRECT_SKILL_EXECUTION] += 0.3

        elif request_type == RequestType.NEEDS_SKILL_COMBINATION:
            base_scores[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] += 0.9

        elif request_type == RequestType.NEEDS_NEW_SKILL:
            base_scores[ProcessingStrategy.SKILL_GENERATION] += 0.8

        elif request_type == RequestType.TOO_COMPLEX:
            if self.config["enable_agent_delegation"] and self.agent_delegator:
                base_scores[ProcessingStrategy.AGENT_DELEGATION] += 0.7
            base_scores[ProcessingStrategy.HYBRID_APPROACH] += 0.6

        elif request_type == RequestType.UNCLEAR:
            base_scores[ProcessingStrategy.HYBRID_APPROACH] += 0.8

        # Adjust based on complexity
        if complexity_score > 0.8:
            base_scores[ProcessingStrategy.AGENT_DELEGATION] += 0.3
            base_scores[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] += 0.2

        elif complexity_score > 0.6:
            base_scores[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] += 0.3
            base_scores[ProcessingStrategy.SKILL_GENERATION] += 0.2

        # Adjust based on system availability
        if self.config["enable_a2a_integration"] and A2A_AVAILABLE and self.a2a_protocol_manager:
            base_scores[ProcessingStrategy.AGENT_DELEGATION] += 0.25  # A2A good for agent delegation
            base_scores[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] += 0.2  # A2A good for orchestration

        # Adjust based on performance history
        performance_bonus = self._calculate_performance_bonus()
        for strategy in base_scores:
            base_scores[strategy] += performance_bonus.get(strategy, 0)

        return base_scores

    def _calculate_performance_bonus(self) -> Dict[ProcessingStrategy, float]:
        """Calculate performance bonuses based on historical success rates."""
        bonuses = {}

        try:
            # Analyze recent performance stats
            stats = self.performance_stats

            # Bonus for strategies that have been successful recently
            if stats.get("hybrid_approach_success", 0) > 0:
                bonuses[ProcessingStrategy.HYBRID_APPROACH] = 0.1

            if stats.get("multi_skill_orchestrations", 0) > 0:
                bonuses[ProcessingStrategy.MULTI_SKILL_ORCHESTRATION] = 0.1

            if stats.get("owl_requests", 0) > 0:
                bonuses[ProcessingStrategy.SKILL_GENERATION] = 0.05  # OWL often used for skill generation

            if stats.get("camel_requests", 0) > 0:
                bonuses[ProcessingStrategy.AGENT_DELEGATION] = 0.05  # CAMEL often used for agent delegation

        except Exception as e:
            logger.warning(f"Error calculating performance bonus: {e}")

        return bonuses

    def _fallback_strategy_selection(self, request_type: RequestType, existing_skills: List[BaseSkill]) -> ProcessingStrategy:
        """Fallback strategy selection when advanced calculation fails."""
        if request_type == RequestType.SKILL_AVAILABLE:
            if len(existing_skills) == 1:
                return ProcessingStrategy.DIRECT_SKILL_EXECUTION
            else:
                return ProcessingStrategy.MULTI_SKILL_ORCHESTRATION
        elif request_type == RequestType.NEEDS_SKILL_COMBINATION:
            return ProcessingStrategy.MULTI_SKILL_ORCHESTRATION
        elif request_type == RequestType.NEEDS_NEW_SKILL:
            return ProcessingStrategy.SKILL_GENERATION
        elif request_type == RequestType.TOO_COMPLEX:
            return ProcessingStrategy.AGENT_DELEGATION
        elif request_type == RequestType.UNCLEAR:
            return ProcessingStrategy.HYBRID_APPROACH
        else:
            return ProcessingStrategy.SKILL_GENERATION
    
    async def _find_matching_skills(self, user_request: str, context: Dict[str, Any]) -> List[BaseSkill]:
        """Find skills that match the request using optimized skill registry."""
        try:
            # Use the optimized skill registry to find matching skills
            matching_skills = await self.skill_registry.find_skills_for_request_optimized(user_request, context)
            return matching_skills or []
        except Exception as e:
            logger.error(f"Error finding matching skills: {e}")
            return []
    
    async def _find_all_relevant_skills(self, user_request: str, context: Dict[str, Any]) -> List[BaseSkill]:
        """Find all skills relevant to the request."""
        try:
            # Use the skill registry to find all relevant skills
            relevant_skills = await self.skill_registry.find_all_relevant_skills(user_request, context)
            return relevant_skills or []
        except Exception as e:
            logger.error(f"Error finding all relevant skills: {e}")
            return []
    
    async def _plan_skill_execution(self, user_request: str, skills: List[BaseSkill], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan the execution sequence for multiple skills."""
        # Simple sequential execution plan
        execution_plan = []
        for i, skill in enumerate(skills):
            execution_plan.append({
                "step": i + 1,
                "skill": skill,
                "input": user_request if i == 0 else f"Previous result: {execution_plan[-1]['result'] if execution_plan else 'N/A'}",
                "dependencies": [] if i == 0 else [i]
            })
        return execution_plan
    
    async def _combine_skill_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine results from multiple skills."""
        combined = {
            "individual_results": results,
            "total_results": len(results),
            "success_count": sum(1 for r in results if r.get('success', False)),
            "combined_output": " ".join(str(r.get('output', r.get('message', ''))) for r in results if r.get('success', False))
        }
        return combined
    
    def get_advanced_stats(self) -> Dict[str, Any]:
        """Get advanced orchestrator statistics."""
        return {
            **self.get_performance_stats(),
            "advanced_mode": True,
            "a2a_integration_available": A2A_AVAILABLE,
            "skill_registry_optimized": True,
            "enhanced_agent_available": True,
            "advanced_metrics": {
                "a2a_requests": self.performance_stats.get("a2a_requests", 0),
                "multi_skill_orchestrations": self.performance_stats.get("multi_skill_orchestrations", 0),
                "hybrid_approach_success": self.performance_stats.get("hybrid_approach_success", 0)
            }
        }

    def _determine_owl_agent_type(self, strategy: ProcessingStrategy, user_request: str, analysis: EnhancedRequestAnalysis) -> str:
        """Determine the appropriate Owl agent type based on strategy and analysis."""
        if strategy == ProcessingStrategy.SKILL_GENERATION:
            return "camel_chat"  # For skill creation
        elif strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
            return "multi_agent"  # For collaboration
        elif analysis.complexity_score > 0.8:
            return "multi_agent"  # Complex tasks need multiple agents
        else:
            return "general"  # Default agent type

    async def _process_owl_skill_creation_result(self, result_data: Dict[str, Any], analysis: EnhancedRequestAnalysis, workflow_id: Optional[str]) -> UltimateProcessingResult:
        """Process Owl skill creation results."""
        try:
            # Extract generated code/files from Owl response
            generated_code = result_data.get('generated_code', {})
            skill_name = result_data.get('skill_name', f"owl_generated_skill_{workflow_id}")

            if generated_code:
                # Register the new skill in the registry
                skill_instance = await self.skill_registry.create_skill_from_code(
                    skill_name,
                    generated_code,
                    analysis.required_capabilities
                )

                if skill_instance:
                    await self.skill_registry.register_generated_skill(skill_name, skill_instance)

                    return UltimateProcessingResult(
                        success=True,
                        message=f"Successfully created skill: {skill_name}",
                        data={"skill_name": skill_name, "generated_code": generated_code},
                        processing_type="enhanced_owl_skill_creation",
                        execution_time=0.0,
                        new_skill_created=True,
                        skill_used=skill_name,
                        confidence_score=analysis.confidence,
                        performance_metrics={
                            "owl_processing_time": result_data.get('processing_time', 0),
                            "workflow_id": workflow_id,
                            "code_lines_generated": len(str(generated_code))
                        },
                        metadata={
                            "owl_result": result_data,
                            "workflow_id": workflow_id,
                            "enhanced_integration": True
                        }
                    )

            # Fallback for cases where skill creation didn't work as expected
            return UltimateProcessingResult(
                success=True,
                message="Owl processed request successfully",
                data=result_data,
                processing_type="enhanced_owl_general",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                metadata={
                    "owl_result": result_data,
                    "workflow_id": workflow_id
                }
            )

        except Exception as e:
            logger.error(f"Error processing Owl skill creation result: {e}")
            return UltimateProcessingResult(
                success=False,
                message=f"Error processing Owl result: {str(e)}",
                data={"error": str(e), "owl_result": result_data},
                processing_type="owl_error",
                execution_time=0.0,
                confidence_score=0.1,
                error_details={"processing_error": str(e)}
            )

    async def _process_owl_multi_agent_result(self, result_data: Dict[str, Any], analysis: EnhancedRequestAnalysis, workflow_id: Optional[str]) -> UltimateProcessingResult:
        """Process Owl multi-agent collaboration results."""
        try:
            agent_logs = result_data.get('agent_logs', [])
            response = result_data.get('response', 'Multi-agent task completed')

            return UltimateProcessingResult(
                success=True,
                message=response,
                data={
                    "agent_logs": agent_logs,
                    "conversation_summary": result_data.get('summary', ''),
                    "agents_used": result_data.get('agents_used', [])
                },
                processing_type="enhanced_owl_multi_agent",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                performance_metrics={
                    "owl_processing_time": result_data.get('processing_time', 0),
                    "workflow_id": workflow_id,
                    "agents_involved": len(result_data.get('agents_used', [])),
                    "conversation_turns": len(agent_logs)
                },
                metadata={
                    "owl_result": result_data,
                    "workflow_id": workflow_id,
                    "enhanced_integration": True,
                    "agent_collaboration": True
                }
            )

        except Exception as e:
            logger.error(f"Error processing Owl multi-agent result: {e}")
            return UltimateProcessingResult(
                success=False,
                message=f"Error processing multi-agent result: {str(e)}",
                data={"error": str(e), "owl_result": result_data},
                processing_type="owl_error",
                execution_time=0.0,
                confidence_score=0.1,
                error_details={"processing_error": str(e)}
            )

    async def _process_owl_generic_result(self, result_data: Dict[str, Any], analysis: EnhancedRequestAnalysis, workflow_id: Optional[str], agent_type: str) -> UltimateProcessingResult:
        """Process generic Owl results."""
        return UltimateProcessingResult(
            success=True,
            message=result_data.get("response", "Owl task completed successfully"),
            data=result_data,
            processing_type=f"enhanced_owl_{agent_type}",
            execution_time=0.0,
            confidence_score=analysis.confidence,
            performance_metrics={
                "owl_processing_time": result_data.get('processing_time', 0),
                "workflow_id": workflow_id,
                "agent_type": agent_type
            },
            metadata={
                "owl_result": result_data,
                "workflow_id": workflow_id,
                "enhanced_integration": True
            }
        )

    async def _execute_with_a2a(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: EnhancedRequestAnalysis) -> UltimateProcessingResult:
        """
        Execute a strategy using A2A Protocol integration.
        """
        if not A2A_AVAILABLE or not self.a2a_protocol_manager:
            logger.warning("A2A Protocol integration not available, falling back to regular execution")
            return await self._execute_strategy(strategy, user_request, context, analysis)

        logger.info(f"Executing strategy {strategy} with A2A Protocol integration")

        # Determine agent roles based on strategy and analysis
        agent_roles = self._determine_a2a_agent_roles(strategy, user_request, analysis)

        # Prepare context for A2A
        a2a_context = context.copy()
        a2a_context.update({
            "request_type": analysis.request_type.value,
            "complexity_score": analysis.complexity_score,
            "ambiguity_score": analysis.ambiguity_score,
            "confidence": analysis.confidence,
            "multi_step_indicators": analysis.multi_step_indicators,
            "required_capabilities": analysis.required_capabilities,
            "happyos_version": "1.0.0",
            "happyos_version": "1.0.0",
            "agent_factory_available": bool(create_agent and get_agent_by_role)
        })

        # Use A2A Protocol Manager for agent coordination
        try:
            # Create agent team using A2A factory
            agent_team = await create_agent_team(
                team_name=f"a2a_team_{uuid.uuid4().hex[:8]}",
                agent_roles=agent_roles,
                task_description=user_request,
                context=a2a_context
            )

            # Execute task through A2A protocol
            success, result_data, session_id = await self.a2a_protocol_manager.execute_multi_agent_task(
                task=user_request,
                agent_team=agent_team,
                context=a2a_context,
                max_turns=5 if analysis.complexity_score > 0.7 else 3
            )

            if not success:
                logger.error(f"A2A Protocol task failed: {result_data.get('error', 'Unknown error')}")
                return await self._execute_strategy(strategy, user_request, context, analysis)

            # Process results with A2A error handling
            return await self._process_a2a_result(result_data, analysis, session_id, agent_roles)

        except Exception as e:
            logger.error(f"Error in A2A Protocol integration: {str(e)}")
            return await self._execute_strategy(strategy, user_request, context, analysis)

    def _determine_a2a_agent_roles(self, strategy: ProcessingStrategy, user_request: str, analysis: EnhancedRequestAnalysis) -> List[str]:
        """Determine the appropriate A2A agent roles based on strategy and analysis."""
        roles = []

        if strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
            roles = ["analyst", "programmer", "writer"]
        elif strategy == ProcessingStrategy.AGENT_DELEGATION:
            roles = ["general", "specialist"]
        elif analysis.complexity_score > 0.8:
            roles = ["analyst", "programmer"]
        elif analysis.ambiguity_score > 0.6:
            roles = ["analyst", "general"]
        else:
            roles = ["general"]

        return roles

    async def _process_a2a_result(self, result_data: Dict[str, Any], analysis: EnhancedRequestAnalysis, session_id: Optional[str], agent_roles: List[str]) -> UltimateProcessingResult:
        """Process A2A Protocol results."""
        try:
            messages = result_data.get('messages', [])
            summary = result_data.get('summary', 'Task completed')
            outcome = result_data.get('outcome', {})

            return UltimateProcessingResult(
                success=True,
                message=summary,
                data={
                    "conversation": result_data.get('conversation', {}),
                    "messages": messages,
                    "outcome": outcome,
                    "agent_roles_used": agent_roles
                },
                processing_type="a2a_multi_agent",
                execution_time=0.0,
                confidence_score=analysis.confidence,
                performance_metrics={
                    "a2a_processing_time": result_data.get('processing_time', 0),
                    "session_id": session_id,
                    "agent_roles_count": len(agent_roles),
                    "conversation_turns": len(messages)
                },
                metadata={
                    "a2a_result": result_data,
                    "session_id": session_id,
                    "enhanced_integration": True,
                    "agent_roles": agent_roles
                }
            )

        except Exception as e:
            logger.error(f"Error processing A2A result: {e}")
            return UltimateProcessingResult(
                success=False,
                message=f"Error processing A2A result: {str(e)}",
                data={"error": str(e), "a2a_result": result_data},
                processing_type="a2a_error",
                execution_time=0.0,
                confidence_score=0.1,
                error_details={"processing_error": str(e)}
            )
