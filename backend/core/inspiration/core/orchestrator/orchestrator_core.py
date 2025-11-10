"""
Base Orchestrator Core - Shared foundation for all orchestrator implementations.

This module provides the common functionality that can be shared between
different orchestrator types, including basic request processing,
component management, and core orchestration logic.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from app.core.config.settings import get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.core.performance import monitor_performance

# Logger setup
logger = logging.getLogger(__name__)

settings = get_settings()


class RequestType(Enum):
    """Base request types for orchestrator processing."""
    SKILL_AVAILABLE = "skill_available"
    AGENT_AVAILABLE = "agent_available" 
    NEEDS_NEW_SKILL = "needs_new_skill"
    NEEDS_SKILL_COMBINATION = "needs_skill_combination"
    TOO_COMPLEX = "too_complex"
    UNCLEAR = "unclear"
    REQUIRES_CLARIFICATION = "requires_clarification"


class ProcessingStrategy(Enum):
    """Base processing strategies."""
    DIRECT_SKILL_EXECUTION = "direct_skill_execution"
    SKILL_GENERATION = "skill_generation"
    MULTI_SKILL_ORCHESTRATION = "multi_skill_orchestration"
    AGENT_DELEGATION = "agent_delegation"
    HYBRID_APPROACH = "hybrid_approach"


@dataclass
class ProcessingResult:
    """Base processing result with essential information."""
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
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class RequestAnalysis:
    """Base analysis of user request."""
    request_type: RequestType
    complexity_score: float
    required_capabilities: List[str]
    suggested_strategy: ProcessingStrategy
    confidence: float
    similar_requests: List[Dict[str, Any]]


class BaseOrchestratorCore(ABC):
    """
    Base orchestrator core providing shared functionality for all orchestrator implementations.
    
    This abstract base class defines the common interface and shared functionality
    that can be used by both basic and advanced orchestrator implementations.
    """
    
    def __init__(self):
        # Core components that all orchestrators share
        self.processing_history: List[ProcessingResult] = []
        self.request_patterns: Dict[str, List[Dict[str, Any]]] = {}
        
        # Basic performance metrics
        self.performance_stats = {
            "total_requests": 0,
            "skill_requests": 0,
            "agent_requests": 0,
            "new_skills_created": 0,
            "average_response_time": 0.0,
            "success_rate": 0.0,
            "strategy_distribution": {},
        }
        
        # Basic configuration
        self.config = {
            "max_skill_generation_attempts": 3,
            "complexity_threshold": 0.7,
            "confidence_threshold": 0.6,
            "enable_skill_combination": True,
            "enable_agent_delegation": True,
            "performance_monitoring": True
        }
    
    @abstractmethod
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the orchestrator. Must be implemented by subclasses.
        
        Returns:
            Dict containing initialization results
        """
        pass
    
    @abstractmethod
    async def _analyze_request(self, user_request: str, context: Dict[str, Any]) -> RequestAnalysis:
        """
        Analyze user request to determine processing approach. Must be implemented by subclasses.
        
        Args:
            user_request: The user's request
            context: Additional context information
            
        Returns:
            RequestAnalysis with analysis results
        """
        pass
    
    @abstractmethod
    async def _execute_strategy(self, strategy: ProcessingStrategy, user_request: str, 
                              context: Dict[str, Any], analysis: RequestAnalysis) -> ProcessingResult:
        """
        Execute the selected processing strategy. Must be implemented by subclasses.
        
        Args:
            strategy: The strategy to execute
            user_request: The user's request
            context: Additional context information
            analysis: Request analysis results
            
        Returns:
            ProcessingResult with execution results
        """
        pass
    
    @monitor_performance()
    async def process_request(self, user_request: str, context: Dict[str, Any] = None) -> ProcessingResult:
        """
        Process a user request using the orchestrator.
        
        This is the main entry point that orchestrates the request processing flow.
        
        Args:
            user_request: The user's request to process
            context: Optional context information
            
        Returns:
            ProcessingResult with the results of processing
        """
        start_time = time.time()
        context = context or {}
        
        logger.info(f"Processing request: '{user_request[:100]}...'")
        
        try:
            # Phase 1: Request Analysis
            analysis = await self._analyze_request(user_request, context)
            logger.debug(f"Request analysis: {analysis.request_type}, confidence: {analysis.confidence}")
            
            # Phase 2: Strategy Selection
            strategy = self._select_processing_strategy(analysis, context)
            logger.debug(f"Selected strategy: {strategy}")
            
            # Phase 3: Execute Strategy
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
            
            error_result = ProcessingResult(
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
    
    def _select_processing_strategy(self, analysis: RequestAnalysis, context: Dict[str, Any]) -> ProcessingStrategy:
        """
        Select the best processing strategy based on analysis and context.
        
        Args:
            analysis: Request analysis results
            context: Additional context information
            
        Returns:
            ProcessingStrategy to use
        """
        # Use suggested strategy from analysis
        suggested = analysis.suggested_strategy
        
        # Override based on context or configuration
        if context.get('force_generation'):
            return ProcessingStrategy.SKILL_GENERATION
        elif context.get('prefer_existing'):
            return ProcessingStrategy.DIRECT_SKILL_EXECUTION
        
        return suggested
    
    async def _update_metrics(self, result: ProcessingResult):
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
    
    async def _learn_from_request(self, user_request: str, result: ProcessingResult, analysis: RequestAnalysis):
        """
        Learn from the request for future improvements.
        
        Args:
            user_request: The original user request
            result: The processing result
            analysis: The request analysis
        """
        # Store request pattern
        request_hash = hash(user_request.lower())
        if request_hash not in self.request_patterns:
            self.request_patterns[request_hash] = []
        
        self.request_patterns[request_hash].append({
            "timestamp": time.time(),
            "request": user_request,
            "analysis": {
                "request_type": analysis.request_type.value,
                "complexity_score": analysis.complexity_score,
                "confidence": analysis.confidence
            },
            "result": {
                "success": result.success,
                "strategy_used": result.strategy_used.value if result.strategy_used else None
            },
            "success": result.success
        })
        
        # Keep only recent patterns (last 100 per pattern)
        if len(self.request_patterns[request_hash]) > 100:
            self.request_patterns[request_hash] = self.request_patterns[request_hash][-100:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic performance statistics."""
        return {
            **self.performance_stats,
            "processing_history_size": len(self.processing_history),
            "learned_patterns": len(self.request_patterns)
        }
    
    async def cleanup(self):
        """Cleanup orchestrator resources."""
        logger.info("BaseOrchestratorCore cleaned up")
