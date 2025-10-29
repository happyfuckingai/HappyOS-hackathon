"""
Base Agent Classes

Provides foundational classes for building HappyOS agents with enterprise
patterns including security, observability, and resilience.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from uuid import uuid4

try:
    from ..exceptions import HappyOSSDKError
except ImportError:
    from happyos_sdk.exceptions import HappyOSSDKError

try:
    from ..observability.logging import get_logger
except ImportError:
    # Fallback to standard logging
    import logging
    def get_logger(name):
        return logging.getLogger(name)

try:
    from ..observability.metrics import MetricsCollector
except ImportError:
    # Simple metrics collector fallback
    class MetricsCollector:
        def increment(self, metric): pass

try:
    from ..resilience.circuit_breaker import CircuitBreaker
except ImportError:
    # Simple circuit breaker fallback
    class CircuitBreaker:
        def __init__(self, *args, **kwargs): pass
        async def call(self, func, *args, **kwargs):
            return await func(*args, **kwargs)


@dataclass
class AgentConfig:
    """Configuration for agent instances."""
    
    agent_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "HappyOS Agent"
    description: str = "A HappyOS AI Agent"
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    
    # Performance settings
    max_concurrent_tasks: int = 10
    task_timeout: int = 300  # 5 minutes
    
    # Observability
    enable_metrics: bool = True
    enable_tracing: bool = True
    
    # Custom configuration
    custom: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all HappyOS agents.
    
    Provides common functionality including configuration management,
    logging, metrics, and task execution patterns.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize base agent."""
        self.config = config
        self.logger = get_logger(f"agent.{config.name}")
        self.metrics = MetricsCollector() if config.enable_metrics else None
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """Check if agent is currently running."""
        return self._running
    
    async def start(self) -> None:
        """Start the agent."""
        if self._running:
            raise HappyOSSDKError("Agent is already running")
        
        self.logger.info(f"Starting agent {self.config.name}")
        await self._initialize()
        self._running = True
        
        if self.metrics:
            self.metrics.increment("agent.started")
    
    async def stop(self) -> None:
        """Stop the agent gracefully."""
        if not self._running:
            return
        
        self.logger.info(f"Stopping agent {self.config.name}")
        self._running = False
        await self._cleanup()
        
        if self.metrics:
            self.metrics.increment("agent.stopped")
    
    @abstractmethod
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single task. Must be implemented by concrete agents."""
        pass
    
    async def _initialize(self) -> None:
        """Initialize agent-specific resources. Override in subclasses."""
        pass
    
    async def _cleanup(self) -> None:
        """Clean up agent-specific resources. Override in subclasses."""
        pass
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get agent health status."""
        return {
            "agent_id": self.config.agent_id,
            "name": self.config.name,
            "version": self.config.version,
            "running": self._running,
            "capabilities": self.config.capabilities,
        }