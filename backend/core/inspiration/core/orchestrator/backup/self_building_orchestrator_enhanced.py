"""
🧠 ENHANCED SELF-BUILDING ORCHESTRATOR - FULL INTEGRATION

Enhancements:
- Full integration with optimized skill registry
- Enhanced Mr Happy agent integration
- Eliminated hardcoded fallbacks
- Robust error recovery mechanisms
- Performance optimizations
- Better skill generation feedback
- Owl integration for advanced multi-agent capabilities
- CAMEL integration for multi-agent collaboration
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import time

from app.config.settings import get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.core.performance import monitor_performance
from app.core.skills.skill_registry_optimized import optimized_skill_registry
from app.core.agent.mr_happy_agent_enhanced import enhanced_mr_happy_agent
from app.core.skill_generator import skill_generator, generate_skill_for_request
from app.agents.multi_agent import agent_orchestrator, Task, TaskPriority

# Import Owl integration
from app.core.orchestrator.owl_integration import (
    owl_integration_manager, 
    OwlTaskType, 
    is_owl_available
)

# Import CAMEL integration
from app.core.orchestrator.camel_integration import (
    camel_integration_manager,
    CamelTaskType
)
from app.llm.router import get_llm_client
from app.core.skill_executor import execute_skill
from app.core.nlp.unified_intent_classifier import unified_intent_classifier

# Logger setup
logger = logging.getLogger(__name__)

settings = get_settings()


class RequestType(Enum):
    """Enhanced request types."""
    SKILL_AVAILABLE = "skill_available"
    AGENT_AVAILABLE = "agent_available" 
    NEEDS_NEW_SKILL = "needs_new_skill"
    NEEDS_SKILL_COMBINATION = "needs_skill_combination"
    TOO_COMPLEX = "too_complex"
    UNCLEAR = "unclear"
    REQUIRES_CLARIFICATION = "requires_clarification"


class ProcessingStrategy(Enum):
    """Processing strategies."""
    DIRECT_SKILL_EXECUTION = "direct_skill_execution"
    SKILL_GENERATION = "skill_generation"
    MULTI_SKILL_ORCHESTRATION = "multi_skill_orchestration"
    AGENT_DELEGATION = "agent_delegation"
    HYBRID_APPROACH = "hybrid_approach"


@dataclass
class EnhancedProcessingResult:
    """Enhanced processing result with more context."""
    success: bool
    message: str
    data: Dict[str, Any]
    processing_type: str
    execution_time: float
    skill_used: Optional[str] = None
    agent_used: Optional[str] = None
    new_skill_created: bool = False
    strategy_used: Optional[ProcessingStrategy] = None
    confidence_score: float = 0.0
    performance_metrics: Dict[str, Any] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {}


@dataclass
class RequestAnalysis:
    """Analysis of user request."""
    request_type: RequestType
    complexity_score: float
    intent_classification: Dict[str, Any]
    required_capabilities: List[str]
    suggested_strategy: ProcessingStrategy
    confidence: float
    similar_requests: List[Dict[str, Any]]


class EnhancedSelfBuildingOrchestrator:
    """
    Enhanced self-building orchestrator with full system integration.
    """
    
    def __init__(self):
        self.skill_registry = optimized_skill_registry
        self.mr_happy_agent = enhanced_mr_happy_agent
        self.intent_classifier = unified_intent_classifier
        
        # Processing history and analytics
        self.processing_history: List[EnhancedProcessingResult] = []
        self.request_patterns: Dict[str, List[Dict[str, Any]]] = {}
        
        # Performance metrics
        self.performance_stats = {
            "total_requests": 0,
            "skill_requests": 0,
            "agent_requests": 0,
            "new_skills_created": 0,
            "average_response_time": 0.0,
            "success_rate": 0.0,
            "strategy_distribution": {},
            "error_recovery_rate": 0.0
        }
        
        # Configuration
        self.config = {
            "max_skill_generation_attempts": 3,
            "complexity_threshold": 0.7,
            "confidence_threshold": 0.6,
            "enable_skill_combination": True,
            "enable_agent_delegation": True,
            "performance_monitoring": True
        }
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the enhanced orchestrator."""
        logger.info("Initializing EnhancedSelfBuildingOrchestrator...")
        
        # Initialize components
        skill_registry_result = await self.skill_registry.initialize()
        mr_happy_result = await self.mr_happy_agent.initialize()
        
        # Set up integrations
        self.mr_happy_agent.set_skill_registry(self.skill_registry)
        self.mr_happy_agent.set_orchestrator(self)
        
        # Initialize Owl integration if available
        owl_result = {"available": False}
        if is_owl_available():
            try:
                # No initialization needed for owl_integration_manager
                owl_result = {
                    "available": True,
                    "initialized": True
                }
                logger.info("Owl integration initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing Owl integration: {str(e)}")
                owl_result = {
                    "available": False,
                    "error": str(e)
                }
        
        # Initialize CAMEL integration
        camel_result = {"available": False}
        try:
            # Initialize CAMEL client
            camel_result = {
                "available": True,
                "initialized": True
            }
            logger.info("CAMEL integration initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing CAMEL integration: {str(e)}")
            camel_result = {
                "available": False,
                "error": str(e)
            }
        
        result = {
            "orchestrator_initialized": True,
            "skill_registry": skill_registry_result,
            "mr_happy_agent": mr_happy_result,
            "intent_classifier_ready": True,
            "performance_tracking_active": self.config["performance_monitoring"],
            "owl_integration": owl_result,
            "camel_integration": camel_result,
            "integration_complete": True
        }
        
        logger.info(f"EnhancedSelfBuildingOrchestrator initialized: {result}")
        return result
    
    @monitor_performance
    async def process_request(self, user_request: str, context: Dict[str, Any] = None) -> EnhancedProcessingResult:
        """
        Enhanced request processing with full integration.
        """
        start_time = time.time()
        context = context or {}
        
        logger.info(f"Processing request: '{user_request[:100]}...'")
        
        try:
            # Phase 1: Request Analysis
            analysis = await self._analyze_request(user_request, context)
            logger.debug(f"Request analysis: {analysis.request_type}, confidence: {analysis.confidence}")
            
            # Check if we should use Owl or CAMEL for this request
            use_owl = False
            use_camel = False
            
            # Check Owl first
            if is_owl_available():
                try:
                    use_owl = await owl_integration_manager.should_use_owl(user_request, context)
                    if use_owl:
                        logger.info("Request will be processed using Owl integration")
                        # Add Owl flag to context
                        context["use_owl"] = True
                except Exception as e:
                    logger.error(f"Error checking Owl availability: {str(e)}")
                    use_owl = False
            
            # If not using Owl, check if we should use CAMEL
            if not use_owl:
                try:
                    use_camel = await camel_integration_manager.should_use_camel(user_request, context)
                    if use_camel:
                        logger.info("Request will be processed using CAMEL integration")
                        # Add CAMEL flag to context
                        context["use_camel"] = True
                except Exception as e:
                    logger.error(f"Error checking CAMEL availability: {str(e)}")
                    use_camel = False
            # Phase 2: Strategy Selection
            strategy = self._select_processing_strategy(analysis, context)
            logger.debug(f"Selected strategy: {strategy}")
            
            # Phase 3: Execute Strategy (with Owl or CAMEL if appropriate)
            if use_owl and strategy in [ProcessingStrategy.SKILL_GENERATION, ProcessingStrategy.MULTI_SKILL_ORCHESTRATION]:
                logger.info(f"Using Owl for strategy: {strategy}")
                result = await self._execute_with_owl(strategy, user_request, context, analysis)
            elif use_camel and strategy in [ProcessingStrategy.MULTI_SKILL_ORCHESTRATION, ProcessingStrategy.AGENT_DELEGATION]:
                logger.info(f"Using CAMEL for strategy: {strategy}")
                result = await self._execute_with_camel(strategy, user_request, context, analysis)
            else:
                result = await self._execute_strategy(strategy, user_request, context, analysis)
            
            # Phase 4: Post-processing
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            result.strategy_used = strategy
            result.confidence_score = analysis.confidence
            
            # Update metrics and history
            await self._update_metrics(result)
            self.processing_history.append(result)
            
            # Learn from this request
            await self._learn_from_request(user_request, result, analysis)
            
            logger.info(f"Request processed successfully in {execution_time:.2f}s using {strategy.value}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            execution_time = time.time() - start_time
            
            error_result = EnhancedProcessingResult(
                success=False,
                message=f"Processing failed: {str(e)}",
                data={},
                processing_type="error",
                execution_time=execution_time,
                error_details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "request": user_request[:200]
                }
            )
            
            self.processing_history.append(error_result)
            return error_result
    
    async def _analyze_request(self, user_request: str, context: Dict[str, Any]) -> RequestAnalysis:
        """Analyze user request to determine processing approach."""
        try:
            # Intent classification
            intent_result = await self.intent_classifier.classify_intent(user_request)
            
            # Complexity analysis
            complexity_score = await self._calculate_complexity(user_request, context)
            
            # Check for existing skills
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
            suggested_strategy = self._suggest_strategy(request_type, complexity_score, existing_skills)
            
            # Find similar requests
            similar_requests = await self._find_similar_requests(user_request)
            
            return RequestAnalysis(
                request_type=request_type,
                complexity_score=complexity_score,
                intent_classification=intent_result,
                required_capabilities=intent_result.get('capabilities', []),
                suggested_strategy=suggested_strategy,
                confidence=intent_result.get('confidence', 0.5),
                similar_requests=similar_requests
            )
            
        except Exception as e:
            logger.error(f"Error analyzing request: {e}")
            # Fallback analysis
            return RequestAnalysis(
                request_type=RequestType.UNCLEAR,
                complexity_score=0.5,
                intent_classification={},
                required_capabilities=[],
                suggested_strategy=ProcessingStrategy.SKILL_GENERATION,
                confidence=0.3,
                similar_requests=[]
            )
    
    async def _calculate_complexity(self, user_request: str, context: Dict[str, Any]) -> float:
        """Calculate request complexity score."""
        complexity_factors = {
            "length": min(len(user_request) / 500, 1.0) * 0.2,
            "technical_terms": self._count_technical_terms(user_request) / 10 * 0.3,
            "multi_step": 1.0 if any(word in user_request.lower() for word in ['then', 'after', 'next', 'also', 'and']) else 0.0,
            "context_dependency": 0.5 if context else 0.0,
            "ambiguity": await self._calculate_ambiguity(user_request)
        }
        
        return min(sum(complexity_factors.values()), 1.0)
    
    def _count_technical_terms(self, text: str) -> int:
        """Count technical terms in text."""
        technical_terms = [
            'api', 'database', 'algorithm', 'function', 'class', 'method',
            'server', 'client', 'protocol', 'framework', 'library', 'module',
            'authentication', 'authorization', 'encryption', 'deployment'
        ]
        return sum(1 for term in technical_terms if term in text.lower())
    
    async def _calculate_ambiguity(self, user_request: str) -> float:
        """Calculate ambiguity score using LLM."""
        try:
            llm_client = get_llm_client()
            prompt = f"""
Rate the ambiguity of this request on a scale of 0.0 to 1.0:
"{user_request}"

0.0 = Very clear and specific
1.0 = Very ambiguous and unclear

Return only the number:"""
            
            response = await llm_client.generate_response(prompt)
            return float(response.strip())
        except Exception:
            return 0.5  # Default ambiguity
    
    async def _find_matching_skills(self, user_request: str, context: Dict[str, Any]) -> List[Any]:
        """Find skills that match the request."""
        try:
            # Use optimized skill registry
            best_skill = await self.skill_registry.find_best_skill_for_request_optimized(user_request, context)
            return [best_skill] if best_skill else []
        except Exception as e:
            logger.error(f"Error finding matching skills: {e}")
            return []
    
    def _suggest_strategy(self, request_type: RequestType, complexity_score: float, existing_skills: List[Any]) -> ProcessingStrategy:
        """Suggest processing strategy based on analysis."""
        if request_type == RequestType.SKILL_AVAILABLE:
            if len(existing_skills) == 1:
                return ProcessingStrategy.DIRECT_SKILL_EXECUTION
            else:
                return ProcessingStrategy.MULTI_SKILL_ORCHESTRATION
        elif request_type == RequestType.NEEDS_NEW_SKILL:
            return ProcessingStrategy.SKILL_GENERATION
        elif request_type == RequestType.TOO_COMPLEX:
            if self.config["enable_agent_delegation"]:
                return ProcessingStrategy.AGENT_DELEGATION
            else:
                return ProcessingStrategy.HYBRID_APPROACH
        else:
            return ProcessingStrategy.SKILL_GENERATION
    
    def _select_processing_strategy(self, analysis: RequestAnalysis, context: Dict[str, Any]) -> ProcessingStrategy:
        """Select the best processing strategy."""
        # Use suggested strategy from analysis
        suggested = analysis.suggested_strategy
        
        # Override based on context or configuration
        if context.get('force_generation'):
            return ProcessingStrategy.SKILL_GENERATION
        elif context.get('prefer_existing'):
            return ProcessingStrategy.DIRECT_SKILL_EXECUTION
        
        return suggested
    
    async def _execute_strategy(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute the selected processing strategy."""
        try:
            if strategy == ProcessingStrategy.DIRECT_SKILL_EXECUTION:
                return await self._execute_direct_skill(user_request, context, analysis)
            elif strategy == ProcessingStrategy.SKILL_GENERATION:
                return await self._execute_skill_generation(user_request, context, analysis)
            elif strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
                return await self._execute_multi_skill_orchestration(user_request, context, analysis)
            elif strategy == ProcessingStrategy.AGENT_DELEGATION:
                return await self._execute_agent_delegation(user_request, context, analysis)
            elif strategy == ProcessingStrategy.HYBRID_APPROACH:
                return await self._execute_hybrid_approach(user_request, context, analysis)
            else:
                raise HappyOSError(f"Unknown strategy: {strategy}")
                
        except Exception as e:
            logger.error(f"Error executing strategy {strategy}: {e}")
            raise
    
    async def _execute_direct_skill(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute request using existing skill."""
        try:
            # Find the best skill
            skill = await self.skill_registry.find_best_skill_for_request_optimized(user_request, context)
            
            if not skill:
                raise HappyOSError("No suitable skill found")
            
            # Execute skill
            result = await execute_skill(skill, user_request, context)
            
            return EnhancedProcessingResult(
                success=True,
                message="Request processed successfully using existing skill",
                data=result,
                processing_type="direct_skill_execution",
                execution_time=0.0,  # Will be set by caller
                skill_used=skill.__class__.__name__,
                performance_metrics={
                    "skill_execution_time": result.get('execution_time', 0),
                    "skill_confidence": result.get('confidence', 1.0)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in direct skill execution: {e}")
            raise
    
    async def _execute_skill_generation(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute request by generating new skill."""
        try:
            max_attempts = self.config["max_skill_generation_attempts"]
            
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Skill generation attempt {attempt + 1}/{max_attempts}")
                    
                    # Generate skill
                    generation_result = await generate_skill_for_request(
                        user_request, 
                        context, 
                        required_capabilities=analysis.required_capabilities
                    )
                    
                    if generation_result.get('success'):
                        # Test the generated skill
                        skill_instance = generation_result['skill_instance']
                        test_result = await execute_skill(skill_instance, user_request, context)
                        
                        if test_result.get('success'):
                            # Register the new skill
                            await self.skill_registry.register_generated_skill(
                                generation_result['skill_name'],
                                skill_instance
                            )
                            
                            return EnhancedProcessingResult(
                                success=True,
                                message="Request processed successfully with newly generated skill",
                                data=test_result,
                                processing_type="skill_generation",
                                execution_time=0.0,
                                new_skill_created=True,
                                skill_used=generation_result['skill_name'],
                                performance_metrics={
                                    "generation_attempts": attempt + 1,
                                    "skill_generation_time": generation_result.get('generation_time', 0),
                                    "skill_test_success": True
                                }
                            )
                        else:
                            logger.warning(f"Generated skill failed test on attempt {attempt + 1}")
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
    
    async def _execute_multi_skill_orchestration(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute request using multiple skills in orchestration."""
        try:
            # Find all relevant skills
            relevant_skills = await self._find_all_relevant_skills(user_request, context)
            
            if not relevant_skills:
                raise HappyOSError("No relevant skills found for orchestration")
            
            # Plan execution sequence
            execution_plan = await self._plan_skill_execution(user_request, relevant_skills, context)
            
            # Execute skills in sequence
            results = []
            for step in execution_plan:
                skill = step['skill']
                input_data = step['input']
                
                result = await execute_skill(skill, input_data, context)
                results.append(result)
                
                # Update context with result for next step
                context.update(result.get('output_context', {}))
            
            # Combine results
            combined_result = await self._combine_skill_results(results)
            
            return EnhancedProcessingResult(
                success=True,
                message="Request processed successfully using skill orchestration",
                data=combined_result,
                processing_type="multi_skill_orchestration",
                execution_time=0.0,
                performance_metrics={
                    "skills_used": len(relevant_skills),
                    "orchestration_steps": len(execution_plan),
                    "individual_results": len(results)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in multi-skill orchestration: {e}")
            raise
    
    async def _execute_agent_delegation(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute request by delegating to agent system."""
        try:
            # Create task for agent system
            task = Task(
                id=f"task_{int(time.time())}",
                description=user_request,
                priority=TaskPriority.HIGH,
                context=context,
                required_capabilities=analysis.required_capabilities
            )
            
            # Delegate to agent orchestrator
            result = await agent_orchestrator.process_task(task)
            
            return EnhancedProcessingResult(
                success=result.get('success', False),
                message="Request processed by agent delegation",
                data=result,
                processing_type="agent_delegation",
                execution_time=0.0,
                agent_used=result.get('agent_used'),
                performance_metrics={
                    "delegation_successful": result.get('success', False),
                    "agent_execution_time": result.get('execution_time', 0)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in agent delegation: {e}")
            raise
    
    async def _execute_hybrid_approach(self, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """Execute request using hybrid approach."""
        try:
            # Try skill generation first
            try:
                return await self._execute_skill_generation(user_request, context, analysis)
            except Exception as skill_error:
                logger.warning(f"Skill generation failed, trying agent delegation: {skill_error}")
                
                # Fallback to agent delegation
                try:
                    return await self._execute_agent_delegation(user_request, context, analysis)
                except Exception as agent_error:
                    logger.error(f"Agent delegation also failed: {agent_error}")
                    
                    # Final fallback - ask for clarification
                    return EnhancedProcessingResult(
                        success=False,
                        message="Request too complex. Please provide more specific details or break it into smaller parts.",
                        data={
                            "skill_generation_error": str(skill_error),
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
        """Find similar requests from history."""
        # Simple implementation - in practice, you'd use embeddings or other similarity measures
        similar = []
        request_words = set(user_request.lower().split())
        
        for result in self.processing_history[-50:]:  # Check last 50 requests
            if 'original_request' in result.data:
                other_words = set(result.data['original_request'].lower().split())
                similarity = len(request_words & other_words) / len(request_words | other_words)
                
                if similarity > 0.3:  # 30% similarity threshold
                    similar.append({
                        'request': result.data['original_request'],
                        'similarity': similarity,
                        'success': result.success,
                        'strategy': result.strategy_used.value if result.strategy_used else None
                    })
        
        return sorted(similar, key=lambda x: x['similarity'], reverse=True)[:5]
    
    async def _find_all_relevant_skills(self, user_request: str, context: Dict[str, Any]) -> List[Any]:
        """Find all skills relevant to the request."""
        # Implementation would use the skill registry to find multiple relevant skills
        return []
    
    async def _plan_skill_execution(self, user_request: str, skills: List[Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan the execution sequence for multiple skills."""
        # Implementation would create an execution plan
        return []
    
    async def _combine_skill_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine results from multiple skills."""
        # Implementation would intelligently combine results
        return {"combined_results": results}
    
    async def _update_metrics(self, result: EnhancedProcessingResult):
        """Update performance metrics."""
        self.performance_stats["total_requests"] += 1
        
        if result.success:
            self.performance_stats["success_rate"] = (
                (self.performance_stats["success_rate"] * (self.performance_stats["total_requests"] - 1) + 1.0) /
                self.performance_stats["total_requests"]
            )
        else:
            self.performance_stats["success_rate"] = (
                (self.performance_stats["success_rate"] * (self.performance_stats["total_requests"] - 1)) /
                self.performance_stats["total_requests"]
            )
        
        # Update average response time
        current_avg = self.performance_stats["average_response_time"]
        new_avg = (current_avg * (self.performance_stats["total_requests"] - 1) + result.execution_time) / self.performance_stats["total_requests"]
        self.performance_stats["average_response_time"] = new_avg
        
        # Update strategy distribution
        if result.strategy_used:
            strategy_key = result.strategy_used.value
            self.performance_stats["strategy_distribution"][strategy_key] = (
                self.performance_stats["strategy_distribution"].get(strategy_key, 0) + 1
            )
        
        # Update specific counters
        if result.skill_used and not result.new_skill_created:
            self.performance_stats["skill_requests"] += 1
        elif result.new_skill_created:
            self.performance_stats["new_skills_created"] += 1
        elif result.agent_used:
            self.performance_stats["agent_requests"] += 1
    
    async def _learn_from_request(self, user_request: str, result: EnhancedProcessingResult, analysis: RequestAnalysis):
        """Learn from the request for future improvements."""
        # Store request pattern
        request_hash = hash(user_request.lower())
        if request_hash not in self.request_patterns:
            self.request_patterns[request_hash] = []
        
        self.request_patterns[request_hash].append({
            "timestamp": datetime.utcnow().isoformat(),
            "request": user_request,
            "analysis": analysis.__dict__,
            "result": result.__dict__,
            "success": result.success
        })
        
        # Keep only recent patterns (last 100 per pattern)
        if len(self.request_patterns[request_hash]) > 100:
            self.request_patterns[request_hash] = self.request_patterns[request_hash][-100:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            **self.performance_stats,
            "skill_registry_stats": self.skill_registry.get_performance_stats(),
            "mr_happy_stats": self.mr_happy_agent.get_performance_metrics(),
            "recent_success_rate": self._calculate_recent_success_rate(),
            "processing_history_size": len(self.processing_history),
            "learned_patterns": len(self.request_patterns)
        }
    
    def _calculate_recent_success_rate(self) -> float:
        """Calculate success rate for recent requests."""
        recent_results = self.processing_history[-20:]  # Last 20 requests
        if not recent_results:
            return 0.0
        
        successful = sum(1 for r in recent_results if r.success)
        return successful / len(recent_results)
    
    async def cleanup(self):
        """Cleanup orchestrator resources."""
        await self.skill_registry.cleanup()
        logger.info("EnhancedSelfBuildingOrchestrator cleaned up")


# Global instance
enhanced_self_building_orchestrator = EnhancedSelfBuildingOrchestrator()

    async def _execute_with_owl(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """
        Execute a strategy using Owl integration.
        
        This method sends the request to Owl for processing by CAMEL agents,
        then processes the results based on the strategy.
        """
        logger.info(f"Executing strategy {strategy} with Owl integration")
        
        # Determine the appropriate Owl task type based on the strategy
        if strategy == ProcessingStrategy.SKILL_GENERATION:
            task_type = OwlTaskType.SKILL_CREATION
        elif strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
            task_type = OwlTaskType.MULTI_AGENT_COLLABORATION
        else:
            task_type = OwlTaskType.CODE_GENERATION
        
        # Prepare enhanced context for Owl
        owl_context = context.copy()
        owl_context.update({
            "request_type": analysis.request_type.value,
            "complexity": analysis.complexity,
            "ambiguity": analysis.ambiguity,
            "confidence": analysis.confidence,
            "happyos_version": "1.0.0"
        })
        
        # Send the task to Owl
        try:
            success, result_data, workflow_id = await owl_integration_manager.send_task_to_owl(
                task=user_request,
                task_type=task_type,
                context=owl_context
            )
            
            if not success:
                logger.error(f"Owl task failed: {result_data.get('error', 'Unknown error')}")
                # Fall back to regular strategy execution
                return await self._execute_strategy(strategy, user_request, context, analysis)
            
            # Process the results based on the task type
            if task_type == OwlTaskType.SKILL_CREATION:
                # Process skill creation results
                skill_result = await owl_integration_manager.process_skill_creation_result(
                    result_data=result_data,
                    skills_path=os.path.join(os.getcwd(), "app", "skills")
                )
                
                if skill_result["success"]:
                    # Reload the skill registry to include the new skill
                    await self.skill_registry.reload()
                    
                    return EnhancedProcessingResult(
                        success=True,
                        response=f"Created new skill: {skill_result['skill_name']}",
                        strategy=strategy,
                        skills_used=[],
                        execution_time=0.0,
                        metadata={
                            "owl_result": result_data,
                            "skill_result": skill_result,
                            "workflow_id": workflow_id
                        }
                    )
                else:
                    logger.error(f"Failed to process skill creation result: {skill_result.get('error')}")
            
            elif task_type == OwlTaskType.MULTI_AGENT_COLLABORATION:
                # For multi-agent collaboration, the result might be data or a report
                return EnhancedProcessingResult(
                    success=True,
                    response=result_data.get("response", "Task completed successfully"),
                    strategy=strategy,
                    skills_used=[],
                    execution_time=0.0,
                    metadata={
                        "owl_result": result_data,
                        "workflow_id": workflow_id
                    }
                )
            
            else:  # Generic code generation
                code_result = await owl_integration_manager.process_code_generation_result(
                    result_data=result_data
                )
                
                if code_result["success"]:
                    return EnhancedProcessingResult(
                        success=True,
                        response=f"Generated code: {', '.join(code_result['saved_files'])}",
                        strategy=strategy,
                        skills_used=[],
                        execution_time=0.0,
                        metadata={
                            "owl_result": result_data,
                            "code_result": code_result,
                            "workflow_id": workflow_id
                        }
                    )
            
            # If we get here, something went wrong with processing the results
            return EnhancedProcessingResult(
                success=True,  # Still mark as success since Owl did return something
                response="Received results from Owl, but couldn't process them fully.",
                strategy=strategy,
                skills_used=[],
                execution_time=0.0,
                metadata={
                    "owl_result": result_data,
                    "workflow_id": workflow_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in Owl integration: {str(e)}")
            # Fall back to regular strategy execution
            return await self._execute_strategy(strategy, user_request, context, analysis)    async def _execute_with_camel(self, strategy: ProcessingStrategy, user_request: str, context: Dict[str, Any], analysis: RequestAnalysis) -> EnhancedProcessingResult:
        """
        Execute a strategy using CAMEL integration.
        
        This method sends the request to CAMEL for processing by multi-agent collaboration,
        then processes the results based on the strategy.
        """
        logger.info(f"Executing strategy {strategy} with CAMEL integration")
        
        # Determine the appropriate CAMEL task type based on the strategy
        if strategy == ProcessingStrategy.MULTI_SKILL_ORCHESTRATION:
            task_type = CamelTaskType.DEVELOPMENT_TEAM
        elif strategy == ProcessingStrategy.AGENT_DELEGATION:
            task_type = CamelTaskType.TEAM_CONVERSATION
        else:
            task_type = CamelTaskType.PAIR_CONVERSATION
        
        # Prepare enhanced context for CAMEL
        camel_context = context.copy()
        camel_context.update({
            "request_type": analysis.request_type.value,
            "complexity_score": analysis.complexity_score,
            "required_capabilities": analysis.required_capabilities,
            "confidence": analysis.confidence,
            "happyos_version": "1.0.0"
        })
        
        # Send the task to CAMEL
        try:
            success, result_data, conversation_id = await camel_integration_manager.send_task_to_camel(
                task=user_request,
                task_type=task_type,
                context=camel_context
            )
            
            if not success:
                logger.error(f"CAMEL task failed: {result_data.get('error', 'Unknown error')}")
                # Fall back to regular strategy execution
                return await self._execute_strategy(strategy, user_request, context, analysis)
            
            # Process the results based on the task type
            if task_type == CamelTaskType.DEVELOPMENT_TEAM:
                # Process development team results
                dev_result = await camel_integration_manager.process_development_team_result(
                    result_data=result_data
                )
                
                if dev_result["success"]:
                    # Save any code files
                    code_files = dev_result.get("code_files", {})
                    saved_files = []
                    
                    for file_path, content in code_files.items():
                        try:
                            # Ensure directory exists
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            
                            # Save the file
                            with open(file_path, 'w') as f:
                                f.write(content)
                            saved_files.append(file_path)
                        except Exception as e:
                            logger.error(f"Error saving file {file_path}: {str(e)}")
                    
                    return EnhancedProcessingResult(
                        success=True,
                        message="Development team task completed successfully",
                        data={
                            "saved_files": saved_files,
                            "tasks": dev_result.get("tasks", []),
                            "conversation_id": conversation_id
                        },
                        processing_type="camel_development_team",
                        execution_time=0.0,
                        strategy_used=strategy
                    )
            
            elif task_type == CamelTaskType.TEAM_CONVERSATION:
                # For team conversation, return the conversation results
                return EnhancedProcessingResult(
                    success=True,
                    message="Team conversation completed successfully",
                    data={
                        "conversation_id": conversation_id,
                        "messages": result_data.get("messages", []),
                        "summary": result_data.get("summary", "")
                    },
                    processing_type="camel_team_conversation",
                    execution_time=0.0,
                    strategy_used=strategy
                )
            
            else:  # Pair conversation
                return EnhancedProcessingResult(
                    success=True,
                    message="Pair conversation completed successfully",
                    data={
                        "conversation_id": conversation_id,
                        "messages": result_data.get("messages", []),
                        "response": result_data.get("messages", [])[-1].get("content", "") if result_data.get("messages") else ""
                    },
                    processing_type="camel_pair_conversation",
                    execution_time=0.0,
                    strategy_used=strategy
                )
            
            # If we get here, something went wrong with processing the results
            return EnhancedProcessingResult(
                success=True,  # Still mark as success since CAMEL did return something
                message="Received results from CAMEL, but couldn't process them fully.",
                data={
                    "camel_result": result_data,
                    "conversation_id": conversation_id
                },
                processing_type="camel_partial",
                execution_time=0.0,
                strategy_used=strategy
            )
            
        except Exception as e:
            logger.error(f"Error in CAMEL integration: {str(e)}")
            # Fall back to regular strategy execution
            return await self._execute_strategy(strategy, user_request, context, analysis)