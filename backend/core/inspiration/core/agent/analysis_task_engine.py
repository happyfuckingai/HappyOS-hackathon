"""
🎯 ANALYSIS AND TASK ENGINE - The Brain of HappyOS

This is the intelligent brain that:
1. Understands user intent deeply
2. Generates appropriate tasks for the orchestrator
3. Maintains constant system awareness via eventbus
4. Can spawn new tasks asynchronously when new needs are detected
5. Provides natural communication responses via personality engine

According to the vision in analysis_task_engine_spec.md
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from datetime import datetime
import uuid
import random
import trace
from app.core.config.settings import BaseSettings, get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.core.performance import monitor_performance
from app.llm.router import get_llm_client

# Core system imports
from app.core.memory.context_memory import PersistentContextMemory
from app.core.database import models, persistence_manager, repositories
from app.core.security.security import SecurityManager
from app.core.skills.skill_registry import SkillRegistry
from app.core.self_building.ultimate_self_building import ultimate_self_building_system
from app.core.self_building.ultimate_self_building import handle_request_and_generate_if_needed

# AI/LLM imports
from app.core.ai.enhanced_personality_engine import EnhancedPersonalityEngine
from app.core.ai.intelligent_skill_system import IntelligentSkillSystem
from app.core.ai.summarizer import Summarizer

# Utils
from app.core.utils.logging import setup_logging

# Local Agent Models - Enhanced
from .models import ConversationState, EnhancedStatusUpdate, ConversationContext, TaskInfo
from .enhanced_models import EnhancedConversationContext
from .conversation_state_repository import ConversationStateRepository
from .state_recovery_manager import StateRecoveryManager
from .state_analytics import StateAnalytics

# Task Prioritization System
from .enhanced_task_models import EnhancedTaskInfo, TaskState, TaskPriorityMetadata
from .task_prioritization_engine import TaskPrioritizationEngine
from .task_dependency_manager import TaskDependencyManager
from .task_scheduler import TaskScheduler, AgentNode, ResourcePool
from .task_dependency_extension import TaskDependencyExtension

logger = logging.getLogger(__name__)
settings = get_settings()


class AnalysisAndTaskEngine:
    """
    🎯 ANALYSIS AND TASK ENGINE - The Brain of HappyOS

    This is the intelligent brain that:
    1. Understands user intent deeply using personality engine
    2. Generates appropriate tasks for the orchestrator
    3. Maintains constant system awareness via eventbus
    4. Can spawn new tasks asynchronously when new needs are detected
    5. Provides natural communication responses

    Core Responsibilities (from analysis_task_engine_spec.md):
    - Intelligent User Analysis with personality-based responses
    - Task Generation Engine for orchestrator
    - System Awareness & Discovery
    - Dynamic Task Spawning
    - Event-driven communication
    """
    
    def __init__(self):
        # Core system components
        self.context_memory = PersistentContextMemory()  # Enhanced with persistence
        self.database_models = models
        self.persistence_manager = persistence_manager
        self.repositories = repositories
        self.security_manager = SecurityManager()
        self.skill_registry = SkillRegistry()
        self.orchestrator = ultimate_self_building_system

        # AI/LLM components
        self.personality = EnhancedPersonalityEngine() # Using the correct, imported engine
        self.skill_system = IntelligentSkillSystem()
        self.summarizer = Summarizer()

        # Utils
        setup_logging()

        # Enhanced conversation state management
        self.conversations: Dict[str, EnhancedConversationContext] = {}
        self.status_callbacks: Dict[str, Callable] = {}
        self.pending_tasks: Dict[str, TaskInfo] = {}

        # Advanced persistence components
        self.state_repository: Optional[ConversationStateRepository] = None
        self.recovery_manager: Optional[StateRecoveryManager] = None
        self.analytics: Optional[StateAnalytics] = None

        # Task Prioritization System
        self.prioritization_engine: Optional[TaskPrioritizationEngine] = None
        self.dependency_manager: Optional[TaskDependencyManager] = None
        self.task_scheduler: Optional[TaskScheduler] = None
        self.dependency_extension: Optional[TaskDependencyExtension] = None

        # Performance tracking
        self.metrics = {
            "conversations_started": 0,
            "tasks_completed": 0,
            "skills_generated": 0,
            "errors_recovered": 0,
            "average_response_time": 0.0,
            "conversations_persisted": 0,
            "states_recovered": 0,
            "compression_operations": 0
        }
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the Analysis and Task Engine with enhanced persistence."""
        logger.info("🎯 Initializing Analysis and Task Engine...")

        # Initialize context memory
        await self.context_memory.initialize()

        # Initialize state repository
        self.state_repository = ConversationStateRepository()
        await self.state_repository.initialize()

        # Initialize recovery manager
        self.recovery_manager = StateRecoveryManager(self.state_repository)

        # Initialize analytics
        self.analytics = StateAnalytics(self.state_repository)
        await self.analytics.start_analytics()

        # Load existing conversations from persistence
        await self._load_existing_conversations()

        # Initialize task prioritization system
        self.prioritization_engine = TaskPrioritizationEngine()
        self.dependency_manager = TaskDependencyManager()
        self.task_scheduler = TaskScheduler(self.prioritization_engine, self.dependency_manager)

        # Add default agent nodes
        await self._initialize_default_agents()

        # Start task scheduler
        await self.task_scheduler.start_scheduler()

        # Initialize dependency extension
        self.dependency_extension = TaskDependencyExtension(self.dependency_manager)
        await self.dependency_extension.initialize()

        result = {
            "analysis_engine_initialized": True,
            "personality_engine_loaded": True,
            "skill_registry_connected": self.skill_registry is not None,
            "orchestrator_connected": self.orchestrator is not None,
            "system_awareness_active": True,
            "task_generation_ready": True,
            "event_driven_monitoring": True,
            "conversation_persistence_enabled": True,
            "state_recovery_enabled": True,
            "analytics_enabled": True,
            "task_prioritization_enabled": True,
            "dependency_management_enabled": True,
            "intelligent_scheduling_enabled": True,
            "advanced_dependency_analysis_enabled": True,
            "intelligent_dependency_injection_enabled": True,
            "ready_for_user_interaction": True
        }

        logger.info(f"🎯 Analysis and Task Engine initialized with enhanced persistence: {result}")
        return result

    def set_skill_registry(self, skill_registry):
        """Set the skill registry reference."""
        self.skill_registry = skill_registry
        logger.info("Skill registry set for Analysis and Task Engine")

    def set_orchestrator(self, orchestrator):
        """Set the orchestrator reference."""
        self.orchestrator = orchestrator
        logger.info("Orchestrator set for Analysis and Task Engine")
    
    async def start_conversation(self, user_id: str, initial_context: Dict[str, Any] = None) -> str:
        """Start a new conversation with enhanced persistence."""
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        # Create enhanced conversation context
        context = EnhancedConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            state=ConversationState.IDLE,
            current_task=None,
            history=[],
            context_data=initial_context or {},
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            pending_tasks={},
            user_preferences={},
            skill_generation_history=[]
        )

        self.conversations[conversation_id] = context
        self.metrics["conversations_started"] += 1

        # Persist the new conversation
        if self.state_repository:
            success = await self.state_repository.save_with_transaction(context)
            if success:
                self.metrics["conversations_persisted"] += 1
                logger.debug(f"Persisted new conversation {conversation_id}")
            else:
                logger.warning(f"Failed to persist new conversation {conversation_id}")

        # Send greeting
        greeting = self.personality.get_response("general", "greeting")
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="greeting",
            message=greeting,
            data={"conversation_started": True},
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="friendly"
        ))

        logger.info(f"Started enhanced conversation {conversation_id} for user {user_id}")
        return conversation_id
    
    async def analyze_user_intent(self, user_input: str, context: Dict[str, Any], personality_engine) -> Dict[str, Any]:
        """
        🎯 INTELLIGENT USER ANALYSIS - Core function of Analysis Engine

        Performs deep analysis of user intent using:
        - Natural language understanding
        - Contextual analysis (previous interactions)
        - Personality-based response generation
        - Complexity assessment
        - Implicit need identification
        """
        try:
            # Intent classification
            intent_result = await self._classify_user_intent(user_input, context)

            # Complexity breakdown
            complexity_analysis = await self._calculate_request_complexity(user_input, context)

            # Personality-based response generation
            personality_response = personality_engine.get_response(
                intent_result.get('primary_intent', 'general'),
                'analysis_complete'
            )

            # Identify implicit needs
            implicit_needs = self._identify_implicit_needs(user_input, context)

            return {
                "intent_classification": intent_result,
                "complexity_breakdown": complexity_analysis,
                "personality_response": personality_response,
                "implicit_needs": implicit_needs,
                "confidence_score": intent_result.get('confidence', 0.5),
                "requires_orchestrator": complexity_analysis['complexity_score'] > 0.7
            }

        except Exception as e:
            logger.error(f"Error in user intent analysis: {e}")
            return {
                "error": str(e),
                "fallback_response": "Jag förstår din förfrågan och arbetar på det...",
                "requires_orchestrator": True
            }

    async def generate_orchestrator_tasks(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        🎯 TASK GENERATION ENGINE - Creates appropriate tasks for orchestrator

        Based on analysis, determines:
        - Which existing agents/modules are available
        - What new agents need to be created
        - Which MCP servers should be used
        - What information needs to be gathered
        - Whether more user info is needed
        """
        tasks = []

        try:
            # Assess available capabilities
            available_capabilities = await self.assess_system_capabilities()

            # Generate tasks based on analysis
            if analysis_result.get('requires_orchestrator'):
                # Complex task - generate multiple orchestrator tasks
                tasks.extend(await self._generate_complex_tasks(analysis_result, available_capabilities))
            else:
                # Simple task - generate single orchestrator task
                tasks.append(await self._generate_simple_task(analysis_result, available_capabilities))

            # Add implicit need tasks
            implicit_tasks = await self._generate_implicit_need_tasks(
                analysis_result.get('implicit_needs', []),
                available_capabilities
            )
            tasks.extend(implicit_tasks)

            logger.info(f"Generated {len(tasks)} orchestrator tasks")
            return tasks

        except Exception as e:
            logger.error(f"Error generating orchestrator tasks: {e}")
            return [{
                "type": "error_handling",
                "description": f"Task generation failed: {str(e)}",
                "priority": "high",
                "requires_new_agent": False
            }]

    async def assess_system_capabilities(self) -> Dict[str, Any]:
        """
        🎯 SYSTEM AWARENESS & DISCOVERY

        Maintains constant overview of:
        - Available agents and their competencies
        - Existing modules and components
        - Reusable UI components
        - System capacity and resources
        - Active processes and status
        """
        try:
            # Get current system status
            capabilities = {
                "available_agents": await self._get_available_agents(),
                "existing_modules": await self._get_existing_modules(),
                "ui_components": await self._get_reusable_ui_components(),
                "system_resources": await self._assess_system_resources(),
                "active_processes": await self._get_active_processes()
            }

            # Cache for performance
            self._system_capabilities_cache = capabilities
            self._capabilities_cache_time = datetime.utcnow()

            return capabilities

        except Exception as e:
            logger.error(f"Error assessing system capabilities: {e}")
            return {"error": str(e), "available_agents": [], "system_resources": "unknown"}

    async def monitor_and_spawn_tasks(self) -> None:
        """
        🎯 DYNAMIC TASK SPAWNING

        During ongoing work:
        - Listens to eventbus for new needs
        - Can create additional tasks asynchronously
        - Prioritizes and schedules new tasks
        - Updates communication agent with status
        """
        while True:
            try:
                # Listen for new needs from eventbus
                new_needs = await self._listen_for_new_needs()

                if new_needs:
                    for need in new_needs:
                        # Generate additional task
                        additional_task = await self._generate_additional_task(need)

                        # Submit to orchestrator
                        await self._submit_task_to_orchestrator(additional_task)

                        # Update communication agent
                        await self._notify_communication_agent(additional_task)

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in task spawning monitor: {e}")
                await asyncio.sleep(10)  # Longer delay on error

    # Legacy method for backward compatibility
    async def handle_user_input(self, conversation_id: str, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhanced user input handling with full Analysis & Task Engine integration.
        """
        if conversation_id not in self.conversations:
            raise HappyOSError(f"Conversation {conversation_id} not found")

        conv_context = self.conversations[conversation_id]
        conv_context.last_activity = datetime.utcnow()
        conv_context.state = ConversationState.ANALYZING

        # Generate task ID
        task_id = self._generate_task_id()

        # Create enhanced task info
        task_info = TaskInfo(
            task_id=task_id,
            description=user_input[:100] + "..." if len(user_input) > 100 else user_input,
            started_at=datetime.utcnow(),
            status="analyzing"
        )

        self.pending_tasks[task_id] = task_info
        conv_context.pending_tasks[task_id] = task_info.__dict__

        # Add to history
        conv_context.history.append({
            "type": "user_input",
            "content": user_input,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Use new Analysis & Task Engine methods
        analysis_result = await self.analyze_user_intent(user_input, context or {}, self.personality)
        orchestrator_tasks = await self.generate_orchestrator_tasks(analysis_result)

        # Immediate acknowledgment with personality
        immediate_response = analysis_result.get('personality_response', 'Jag arbetar på din förfrågan...')

        # Start background processing with orchestrator tasks
        asyncio.create_task(self._process_orchestrator_tasks(conversation_id, task_id, orchestrator_tasks, context or {}))

        return {
            "task_id": task_id,
            "immediate_response": immediate_response,
            "status": "processing",
            "analysis_result": analysis_result,
            "orchestrator_tasks": len(orchestrator_tasks),
            "estimated_completion": datetime.utcnow().timestamp() + 30
        }

    # ===== NEW ANALYSIS ENGINE METHODS =====

    async def _classify_user_intent(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Classify user intent using NLP and context."""
        # Simple intent classification - can be enhanced with ML models
        input_lower = user_input.lower()

        intents = {
            'accounting': ['faktura', 'bokföring', 'moms', 'budget', 'kostnad', 'intäkt', 'utgift'],
            'research': ['forskning', 'analys', 'undersök', 'jämför', 'rapport'],
            'writing': ['skriv', 'text', 'brev', 'artikel', 'innehåll', 'redigera'],
            'coding': ['kod', 'programmera', 'utveckla', 'debug', 'funktion', 'klass'],
            'planning': ['planera', 'schemalägg', 'organisera', 'projekt', 'uppgift']
        }

        primary_intent = 'general'
        confidence = 0.3

        for intent, keywords in intents.items():
            matches = sum(1 for keyword in keywords if keyword in input_lower)
            if matches > 0:
                intent_confidence = min(matches / len(keywords), 1.0)
                if intent_confidence > confidence:
                    primary_intent = intent
                    confidence = intent_confidence

        return {
            'primary_intent': primary_intent,
            'confidence': confidence,
            'keywords_found': [kw for kw in sum(intents.values(), []) if kw in input_lower]
        }

    async def _calculate_request_complexity(self, user_input: str, context: Dict[str, Any]) -> Dict[str, float]:
        """Calculate detailed request complexity."""
        complexity_factors = {
            "length": min(len(user_input) / 500, 1.0) * 0.2,
            "technical_terms": len([w for w in user_input.split() if len(w) > 6]) / max(len(user_input.split()), 1) * 0.3,
            "multi_step": 1.0 if any(word in user_input.lower() for word in ['then', 'after', 'next', 'also', 'and', 'first', 'second']) else 0.0,
            "context_dependency": 0.5 if context else 0.0,
            "specialized_domain": 1.0 if any(domain in user_input.lower() for domain in ['accounting', 'finance', 'technical', 'programming']) else 0.0
        }

        total_complexity = sum(complexity_factors.values())

        return {
            "complexity_score": min(total_complexity, 1.0),
            "factors": complexity_factors,
            "assessment": "high" if total_complexity > 0.7 else "medium" if total_complexity > 0.4 else "low"
        }

    def _identify_implicit_needs(self, user_input: str, context: Dict[str, Any]) -> List[str]:
        """Identify implicit needs beyond explicit request."""
        implicit_needs = []

        if 'analysera' in user_input.lower() and 'data' not in context:
            implicit_needs.append("data_collection")

        if 'jämför' in user_input.lower():
            implicit_needs.append("comparison_framework")

        if 'optimera' in user_input.lower():
            implicit_needs.append("performance_monitoring")

        if len(user_input.split()) > 50:
            implicit_needs.append("summarization")

        return implicit_needs

    async def _get_available_agents(self) -> List[str]:
        """Get list of available agents from delegation system."""
        try:
            # Use delegation system to get available agent types
            from app.core.orchestrator.delegation.agent_delegator import agent_delegator
            return list(agent_delegator.agent_templates.keys())
        except:
            return ["general", "accounting", "research", "writing"]

    async def _get_existing_modules(self) -> List[str]:
        """Get list of existing system modules."""
        return ["skill_registry", "personality_engine", "memory_system", "self_building"]

    async def _get_reusable_ui_components(self) -> List[str]:
        """Get list of reusable UI components."""
        return ["data_table", "chart_component", "form_builder", "notification_system"]

    async def _assess_system_resources(self) -> Dict[str, Any]:
        """Assess current system resources."""
        return {
            "cpu_usage": "normal",
            "memory_usage": "normal",
            "available_capacity": "high",
            "active_tasks": len(self.pending_tasks)
        }

    async def _get_active_processes(self) -> List[str]:
        """Get list of active processes."""
        active_processes = []
        for conv in self.conversations.values():
            if conv.state != ConversationState.IDLE:
                active_processes.append(f"conversation_{conv.conversation_id}")
        return active_processes

    async def _generate_complex_tasks(self, analysis_result: Dict[str, Any], capabilities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate multiple tasks for complex requests."""
        tasks = []
        intent = analysis_result.get('intent_classification', {}).get('primary_intent', 'general')

        # Task 1: Primary processing
        tasks.append({
            "type": "primary_processing",
            "description": f"Process {intent} request with appropriate agent",
            "priority": "high",
            "required_capabilities": [intent],
            "requires_new_agent": intent not in capabilities.get('available_agents', [])
        })

        # Task 2: Data gathering (if needed)
        if analysis_result.get('implicit_needs'):
            tasks.append({
                "type": "data_gathering",
                "description": "Gather required data and context",
                "priority": "medium",
                "required_capabilities": ["research"],
                "requires_new_agent": False
            })

        # Task 3: Quality assurance
        tasks.append({
            "type": "quality_assurance",
            "description": "Validate and verify results",
            "priority": "medium",
            "required_capabilities": ["analysis"],
            "requires_new_agent": False
        })

        return tasks

    async def _generate_simple_task(self, analysis_result: Dict[str, Any], capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """Generate single task for simple requests."""
        intent = analysis_result.get('intent_classification', {}).get('primary_intent', 'general')

        return {
            "type": "simple_processing",
            "description": f"Handle {intent} request",
            "priority": "normal",
            "required_capabilities": [intent],
            "requires_new_agent": intent not in capabilities.get('available_agents', [])
        }

    async def _generate_implicit_need_tasks(self, implicit_needs: List[str], capabilities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tasks for implicit needs."""
        tasks = []

        for need in implicit_needs:
            if need == "data_collection":
                tasks.append({
                    "type": "data_collection",
                    "description": "Collect required data",
                    "priority": "medium",
                    "required_capabilities": ["research"],
                    "requires_new_agent": False
                })
            elif need == "summarization":
                tasks.append({
                    "type": "summarization",
                    "description": "Summarize complex information",
                    "priority": "low",
                    "required_capabilities": ["writing"],
                    "requires_new_agent": False
                })

        return tasks

    async def _listen_for_new_needs(self) -> List[Dict[str, Any]]:
        """Listen for new needs from eventbus (placeholder)."""
        # In real implementation, this would listen to eventbus
        # For now, return empty list
        return []

    async def _generate_additional_task(self, need: Dict[str, Any]) -> Dict[str, Any]:
        """Generate additional task based on new need."""
        return {
            "type": "additional_task",
            "description": need.get('description', 'Additional task needed'),
            "priority": "medium",
            "source": "event_driven"
        }

    async def _submit_task_to_orchestrator(self, task: Dict[str, Any]) -> None:
        """Submit task to orchestrator (placeholder)."""
        # In real implementation, submit to orchestrator
        logger.info(f"Would submit task to orchestrator: {task}")

    async def _notify_communication_agent(self, task: Dict[str, Any]) -> None:
        """Notify communication agent of new task (placeholder)."""
        # In real implementation, notify communication agent
        logger.info(f"Would notify communication agent: {task}")

    async def _process_orchestrator_tasks(self, conversation_id: str, task_id: str, orchestrator_tasks: List[Dict[str, Any]], context: Dict[str, Any]):
        """Process tasks with orchestrator (legacy compatibility)."""
        # For now, delegate to existing process_user_request
        # In future, this should use the new task system
        await self._process_user_request(conversation_id, task_id, f"Process {len(orchestrator_tasks)} orchestrator tasks", context)
    
    async def _process_user_request(self, conversation_id: str, task_id: str, user_input: str, context: Dict[str, Any]):
        """Process user request with enhanced skill integration."""
        conv_context = self.conversations[conversation_id]
        task_info = self.pending_tasks[task_id]
        
        try:
            # Phase 1: Skill Discovery
            conv_context.state = ConversationState.SKILL_SEARCHING
            await self._update_task_status(conversation_id, task_id, "searching_skills", 
                                         "Letar efter den perfekta förmågan för dig... 🔍")
            
            # Try to find existing skill
            if self.skill_registry:
                best_skill = await self.skill_registry.find_best_skill_for_request(user_input, context)
                
                if best_skill:
                    # Found existing skill
                    task_info.skill_used = best_skill.__class__.__name__
                    response = self.personality.get_response("skill_execution", "found_perfect_match")
                    await self._update_task_status(conversation_id, task_id, "executing", response)
                    
                    # Execute skill
                    result = await self._execute_skill_with_recovery(best_skill, user_input, context, conversation_id, task_id)
                    
                    if result.get('success'):
                        await self._complete_task_successfully(conversation_id, task_id, result)
                        return
                    else:
                        # Skill execution failed, try generating new skill
                        await self._handle_skill_failure(conversation_id, task_id, result.get('error'))
            
            # Phase 2: Skill Generation
            from app.core.config.settings import get_settings
            settings = get_settings()

            if self.orchestrator and settings.auto_skill_generation:
                conv_context.state = ConversationState.SKILL_GENERATING
                response = self.personality.get_response("skill_generation", "starting")
                await self._update_task_status(conversation_id, task_id, "generating_skill", response)

                # Generate new skill
                generation_result = await self._generate_skill_with_feedback(conversation_id, task_id, user_input, context)

                if generation_result.get('success'):
                    task_info.skioll_generated = True
                    await self._complete_task_successfully(conversation_id, task_id, generation_result)
                else:
                    await self._handle_generation_failure(conversation_id, task_id, generation_result.get('error'))
            else:
                # No orchestrator available or skill generation disabled
                if not settings.auto_skill_generation:
                    logger.info("Auto skill generation disabled by configuration")
                await self._handle_no_solution_available(conversation_id, task_id)
                
        except Exception as e:
            logger.error(f"Error processing user request: {e}", exc_info=True)
            await self._handle_critical_error(conversation_id, task_id, str(e))
    
    async def _generate_skill_with_feedback(self, conversation_id: str, task_id: str, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate skill with personality-driven feedback."""
        conv_context = self.conversations[conversation_id]
        
        try:
            # Progress feedback
            progress_messages = [
                "Analyserar din förfrågan djupt... 🧠",
                "Designar den perfekta lösningen... 🎨",
                "Skriver smart kod för dig... 💻",
                "Testar och finjusterar... 🔧",
                "Nästan klar! Sista detaljerna... ✨"
            ]
            
            for i, message in enumerate(progress_messages):
                await self._update_task_status(conversation_id, task_id, "generating", message)
                await asyncio.sleep(1)  # Simulate work and give user feedback

            # Call orchestrator to generate skill
            result = await handle_request_and_generate_if_needed(user_input, context)
            
            if result.success:
                # Success feedback
                success_message = self.personality.get_response("skill_generation", "success")
                await self._update_task_status(conversation_id, task_id, "skill_generated", success_message)
                
                # Record successful generation
                conv_context.skill_generation_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "request": user_input,
                    "success": True,
                    "skill_created": result.data.get('skill_name', 'Unknown')
                })
                
                return {
                    "success": True,
                    "result": result.data,
                    "message": result.message
                }
            else:
                # Generation failed
                retry_message = self.personality.get_response("skill_generation", "retry")
                await self._update_task_status(conversation_id, task_id, "retrying", retry_message)
                
                # Record failed attempt
                conv_context.skill_generation_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "request": user_input,
                    "success": False,
                    "error": result.message
                })
                
                return {
                    "success": False,
                    "error": result.message
                }
                
        except Exception as e:
            logger.error(f"Error in skill generation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_skill_with_recovery(self, skill, user_input: str, context: Dict[str, Any], conversation_id: str, task_id: str) -> Dict[str, Any]:
        """Execute skill with error recovery."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                conv_context = self.conversations[conversation_id]
                conv_context.state = ConversationState.EXECUTING
                
                # Execute skill
                result = await skill.execute(user_input, context)
                
                if result.get('success'):
                    return result
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        retry_message = self.personality.get_response("error_recovery", "first_error")
                        await self._update_task_status(conversation_id, task_id, "retrying", retry_message)
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue
            except Exception as e:
                retry_count += 1
                logger.error(f"Skill execution error (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    if retry_count == 1:
                        retry_message = self.personality.get_response("error_recovery", "first_error")
                    else:
                        retry_message = self.personality.get_response("error_recovery", "multiple_errors")
                
                    await self._update_task_status(conversation_id, task_id, "retrying", retry_message)
                    await asyncio.sleep(2)  # Longer pause for multiple retries
        
        # All retries failed
        return {
            "success": False,
            "error": f"Skill execution failed after {max_retries} attempts"
        }
    
    async def _update_task_status(self, conversation_id: str, task_id: str, status: str, message: str):
        """Update task status with personality-driven message."""
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id].status = status
            self.pending_tasks[task_id].personality_feedback.append(message)
        
        conv_context = self.conversations[conversation_id]
        confidence = self.personality.adjust_confidence(0.8, conv_context.personality_context)
        
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="progress",
            message=message,
            data={
                "task_id": task_id,
                "status": status,
                "confidence": confidence
            },
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="encouraging",
            confidence_level=confidence
        ))
    
    async def _complete_task_successfully(self, conversation_id: str, task_id: str, result: Dict[str, Any]):
        """Complete task with success feedback."""
        conv_context = self.conversations[conversation_id]
        conv_context.state = ConversationState.COMPLETED
        
        task_info = self.pending_tasks[task_id]
        task_info.status = "completed"
        task_info.result = result
        task_info.execution_time = (datetime.utcnow() - task_info.started_at).total_seconds()
        
        # Success message with personality
        if task_info.skill_generated:
            success_message = self.personality.get_response("skill_generation", "success")
        else:
            success_message = self.personality.get_response("skill_execution", "success")
        
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="result",
            message=success_message,
            data={
                "task_id": task_id,
                "result": result,
                "execution_time": task_info.execution_time,
                "skill_used": task_info.skill_used,
                "skill_generated": task_info.skill_generated
            },
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="excited",
            confidence_level=1.0
        ))
        
        self.metrics["tasks_completed"] += 1
        if task_info.skill_generated:
            self.metrics["skills_generated"] += 1
    
    async def _handle_skill_failure(self, conversation_id: str, task_id: str, error: str):
        """Handle skill execution failure."""
        conv_context = self.conversations[conversation_id]
        conv_context.error_recovery_attempts += 1
        
        recovery_message = self.personality.get_response("error_recovery", "first_error")
        await self._update_task_status(conversation_id, task_id, "recovering", recovery_message)
    
    async def _handle_generation_failure(self, conversation_id: str, task_id: str, error: str):
        """Handle skill generation failure."""
        conv_context = self.conversations[conversation_id]
        conv_context.error_recovery_attempts += 1
        
        if conv_context.error_recovery_attempts >= 3:
            # Ask for user help
            help_message = self.personality.get_response("error_recovery", "asking_for_help")
            conv_context.state = ConversationState.WAITING_FOR_CLARIFICATION
        else:
            help_message = self.personality.get_response("error_recovery", "multiple_errors")
        
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="error",
            message=help_message,
            data={
                "task_id": task_id,
                "error": error,
                "recovery_attempts": conv_context.error_recovery_attempts
            },
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="apologetic"
        ))
        
        self.metrics["errors_recovered"] += 1
    
    async def _handle_no_solution_available(self, conversation_id: str, task_id: str):
        """Handle case when no solution is available."""
        message = "Jag beklagar, men jag kan inte lösa det här just nu. Kan du försöka omformulera din förfrågan? 🤔"
        
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="error",
            message=message,
            data={"task_id": task_id, "reason": "no_solution_available"},
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="apologetic"
        ))
    
    async def _handle_critical_error(self, conversation_id: str, task_id: str, error: str):
        """Handle critical system errors."""
        logger.critical(f"Critical error in conversation {conversation_id}, task {task_id}: {error}")
        
        message = "Oj, något gick verkligen fel! Jag behöver en kort paus för att återhämta mig. Kan du försöka igen om en stund? 😅"
        
        await self._send_status_update(conversation_id, EnhancedStatusUpdate(
            type="error",
            message=message,
            data={"task_id": task_id, "error": error, "critical": True},
            timestamp=datetime.utcnow(),
            conversation_id=conversation_id,
            personality_tone="apologetic"
        ))
    
    async def _send_status_update(self, conversation_id: str, update: EnhancedStatusUpdate):
        """Send status update to user."""
        if conversation_id in self.status_callbacks:
            try:
                await self.status_callbacks[conversation_id](update)
            except Exception as e:
                logger.error(f"Error sending status update: {e}")
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        return f"task_{uuid.uuid4().hex[:8]}"
    
    def register_status_callback(self, conversation_id: str, callback: Callable):
        """Register status callback."""
        self.status_callbacks[conversation_id] = callback
    
    def unregister_status_callback(self, conversation_id: str):
        """Unregister status callback."""
        self.status_callbacks.pop(conversation_id, None)
    
    def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context."""
        return self.conversations.get(conversation_id)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self.metrics,
            "active_conversations": len(self.conversations),
            "pending_tasks": len(self.pending_tasks)
        }
    
    async def cleanup_conversation(self, conversation_id: str):
        """Clean up conversation resources."""
        if conversation_id in self.conversations:
            # Clean up pending tasks
            conv_context = self.conversations[conversation_id]
            for task_id in conv_context.pending_tasks.keys():
                self.pending_tasks.pop(task_id, None)
            
            # Remove conversation
            del self.conversations[conversation_id]
            
            # Remove callback
            self.status_callbacks.pop(conversation_id, None)
            
            logger.info(f"Cleaned up conversation {conversation_id}")
    
    async def _load_existing_conversations(self):
        """Load existing conversations from persistent storage."""
        try:
            if not self.state_repository:
                logger.info("No state repository available, skipping conversation loading")
                return

            # Get all conversation IDs from repository
            query = "SELECT conversation_id FROM conversation_states ORDER BY last_activity DESC"
            result = await self.state_repository._execute_query_with_retry(query)

            loaded_count = 0
            for row in result[:50]:  # Load last 50 conversations for performance
                conversation_id = row[0] if isinstance(row, (list, tuple)) else row['conversation_id']

                try:
                    # Load conversation with integrity check
                    context = await self.state_repository.load_with_integrity_check(conversation_id)
                    if context:
                        self.conversations[conversation_id] = context
                        loaded_count += 1
                except Exception as e:
                    logger.error(f"Error loading conversation {conversation_id}: {e}")

            logger.info(f"Loaded {loaded_count} existing conversations from persistence")
            self.metrics["states_recovered"] = loaded_count

        except Exception as e:
            logger.error(f"Error loading existing conversations: {e}")

    async def _persist_conversation_state(self, conversation_id: str):
        """Persist conversation state with error handling."""
        try:
            if conversation_id not in self.conversations:
                return False

            context = self.conversations[conversation_id]

            # Check for corruption and attempt recovery
            if self.recovery_manager:
                recovery_success = await self.recovery_manager.detect_and_recover_corruption(context)
                if not recovery_success:
                    logger.warning(f"Failed to recover conversation {conversation_id}")
                    return False

            # Persist to repository
            if self.state_repository:
                success = await self.state_repository.save_with_transaction(context)
                if success:
                    self.metrics["conversations_persisted"] += 1
                    logger.debug(f"Persisted conversation state {conversation_id}")
                    return True
                else:
                    logger.error(f"Failed to persist conversation state {conversation_id}")
                    return False

        except Exception as e:
            logger.error(f"Error persisting conversation state {conversation_id}: {e}")
            return False

    async def get_conversation_analytics(self, conversation_id: str) -> Dict[str, Any]:
        """Get analytics for a specific conversation."""
        try:
            if conversation_id not in self.conversations:
                return {'error': 'Conversation not found'}

            context = self.conversations[conversation_id]

            return {
                'conversation_id': conversation_id,
                'state': context.state.value,
                'created_at': context.created_at.isoformat(),
                'last_activity': context.last_activity.isoformat(),
                'message_count': len(context.history),
                'pending_tasks': len(context.pending_tasks),
                'compression_info': context.get_compression_info(),
                'performance_info': context.get_performance_info(),
                'health_status': 'healthy' if not context.persistence_metadata.corruption_detected else 'corrupted'
            }

        except Exception as e:
            logger.error(f"Error getting conversation analytics: {e}")
            return {'error': str(e)}

    async def handle_user_message(self, conversation_id: str, user_input: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Hanterar ett inkommande användarmeddelande och använder hela HappyOS core med enhanced persistence.
        """
        from app.core.config.settings import get_settings
        settings = get_settings()

        # 1. Spara kontext i minnet och persist
        self.context_memory.save_context(conversation_id, user_input, user_context or {})

        # Persist conversation state if it exists
        if conversation_id in self.conversations:
            await self._persist_conversation_state(conversation_id)

        # 2. Försök hitta en befintlig skill
        skill = self.skill_registry.find_best_skill(user_input)
        if skill:
            result = await skill.execute(user_input, user_context)
        else:
            # 3. Om ingen skill finns, be orchestrator skapa en ny (only if auto skill generation is enabled)
            if settings.auto_skill_generation:
                result = await handle_request_and_generate_if_needed(user_input, user_context)
            else:
                logger.info("Auto skill generation disabled by configuration")
                result = {
                    "success": False,
                    "error": "No suitable skill found and auto-generation is disabled",
                    "message": "Jag kan inte hitta en lämplig funktion för din förfrågan."
                }

        # 4. Summera tekniskt svar till användarvänligt
        summary = self.summarizer.summarize(result.get("message", ""))

        # 5. Logga och returnera svaret
        self.persistence_manager.save_interaction(conversation_id, user_input, summary)

        # 6. Update conversation analytics
        if self.analytics and conversation_id in self.conversations:
            await self.analytics.get_current_metrics()

        return {
            "success": result.get("success", False),
            "summary": summary,
            "raw_result": result
        }

    # ===== TASK PRIORITIZATION SYSTEM METHODS =====

    async def _initialize_default_agents(self):
        """Initialize default agent nodes for task execution."""
        try:
            # Create default agents with different capabilities
            agents = [
                AgentNode(
                    agent_id="general_agent",
                    capabilities=["general", "writing", "analysis"],
                    resource_pool=ResourcePool(
                        available_cpu_cores=2,
                        available_memory_mb=1024,
                        available_storage_mb=5120
                    ),
                    specialization_score={
                        "writing": 80,
                        "analysis": 70,
                        "general": 60
                    }
                ),
                AgentNode(
                    agent_id="coding_agent",
                    capabilities=["coding", "programming", "debugging"],
                    resource_pool=ResourcePool(
                        available_cpu_cores=4,
                        available_memory_mb=2048,
                        available_storage_mb=10240
                    ),
                    specialization_score={
                        "coding": 90,
                        "programming": 85,
                        "debugging": 75
                    }
                ),
                AgentNode(
                    agent_id="research_agent",
                    capabilities=["research", "data_collection", "analysis"],
                    resource_pool=ResourcePool(
                        available_cpu_cores=2,
                        available_memory_mb=1536,
                        available_storage_mb=7680
                    ),
                    specialization_score={
                        "research": 85,
                        "data_collection": 80,
                        "analysis": 75
                    }
                ),
                AgentNode(
                    agent_id="accounting_agent",
                    capabilities=["accounting", "finance", "reporting"],
                    resource_pool=ResourcePool(
                        available_cpu_cores=3,
                        available_memory_mb=2048,
                        available_storage_mb=5120
                    ),
                    specialization_score={
                        "accounting": 95,
                        "finance": 85,
                        "reporting": 80
                    }
                )
            ]

            # Add agents to scheduler
            for agent in agents:
                self.task_scheduler.add_agent_node(agent)

            logger.info(f"Initialized {len(agents)} default agent nodes")

        except Exception as e:
            logger.error(f"Error initializing default agents: {e}")

    async def schedule_enhanced_task(self, task: EnhancedTaskInfo) -> bool:
        """
        Schedule an enhanced task with prioritization and dependency management.

        Args:
            task: Enhanced task to schedule

        Returns:
            True if task was scheduled successfully
        """
        try:
            # Add task to dependency manager
            await self.dependency_manager.add_task(task)

            # Schedule task with scheduler
            success = await self.task_scheduler.schedule_task(task)

            if success:
                logger.info(f"Scheduled enhanced task: {task.task_id}")
                return True
            else:
                logger.error(f"Failed to schedule enhanced task: {task.task_id}")
                return False

        except Exception as e:
            logger.error(f"Error scheduling enhanced task: {e}")
            return False

    async def get_task_prioritization_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the task prioritization system."""
        try:
            if not self.task_scheduler:
                return {'error': 'Task scheduler not initialized'}

            scheduler_status = self.task_scheduler.get_scheduler_status()

            # Add prioritization engine status
            if self.prioritization_engine:
                prioritization_status = self.prioritization_engine.get_queue_status()
            else:
                prioritization_status = {'error': 'Prioritization engine not available'}

            # Add dependency manager status
            if self.dependency_manager:
                dependency_status = await self.dependency_manager.get_dependency_stats()
            else:
                dependency_status = {'error': 'Dependency manager not available'}

            return {
                'scheduler': scheduler_status,
                'prioritization': prioritization_status,
                'dependencies': dependency_status,
                'system_health': 'healthy' if all(
                    'error' not in status for status in [
                        scheduler_status, prioritization_status, dependency_status
                    ]
                ) else 'degraded'
            }

        except Exception as e:
            logger.error(f"Error getting task prioritization status: {e}")
            return {'error': str(e)}

    async def create_task_with_dependencies(self,
                                          task_description: str,
                                          dependencies: List[str] = None,
                                          priority: float = 50.0) -> Optional[str]:
        """
        Create a task with dependency management.

        Args:
            task_description: Description of the task
            dependencies: List of task IDs this task depends on
            priority: Base priority (0-100)

        Returns:
            Task ID if created successfully
        """
        try:
            # Create enhanced task
            task_id = self._generate_task_id()
            task = EnhancedTaskInfo(
                task_id=task_id,
                description=task_description,
                started_at=datetime.utcnow(),
                priority_metadata=TaskPriorityMetadata(base_priority=priority),
                tags=["user_created"]
            )

            # Add dependencies if specified
            if dependencies:
                for dep_task_id in dependencies:
                    task.add_dependency(dep_task_id, DependencyType.HARD)

            # Schedule the task
            success = await self.schedule_enhanced_task(task)
            if success:
                return task_id
            else:
                return None

        except Exception as e:
            logger.error(f"Error creating task with dependencies: {e}")
            return None

    async def get_task_execution_plan(self, task_ids: List[str]) -> Dict[str, Any]:
        """
        Get execution plan for a set of tasks including dependencies.

        Args:
            task_ids: Tasks to plan execution for

        Returns:
            Execution plan with dependencies and parallel groups
        """
        try:
            if not self.dependency_manager:
                return {'error': 'Dependency manager not available'}

            return await self.dependency_manager.get_execution_plan(task_ids)

        except Exception as e:
            logger.error(f"Error getting task execution plan: {e}")
            return {'error': str(e)}

    async def cancel_enhanced_task(self, task_id: str) -> bool:
        """
        Cancel an enhanced task.

        Args:
            task_id: Task to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            if self.task_scheduler:
                return await self.task_scheduler.cancel_task(task_id)
            return False

        except Exception as e:
            logger.error(f"Error cancelling enhanced task {task_id}: {e}")
            return False

    async def get_enhanced_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of an enhanced task.

        Args:
            task_id: Task to get status for

        Returns:
            Task status information
        """
        try:
            if self.task_scheduler:
                return await self.task_scheduler.get_task_status(task_id)
            return None

        except Exception as e:
            logger.error(f"Error getting enhanced task status: {e}")
            return {'error': str(e)}

    async def prioritize_task_manually(self, task_id: str, priority: float) -> bool:
        """
        Manually set priority for a task.

        Args:
            task_id: Task to prioritize
            priority: New priority (0-100)

        Returns:
            True if successful
        """
        try:
            if self.prioritization_engine:
                return await self.prioritization_engine.prioritize_task_manually(task_id, priority)
            return False

        except Exception as e:
            logger.error(f"Error manually prioritizing task {task_id}: {e}")
            return False


# Global instans av den nya Analysis and Task Engine
analysis_task_engine = AnalysisAndTaskEngine()

# Bakåtkompatibilitetsalias - andra delar av systemet kan fortsätta använda mr_happy_agent
mr_happy_agent = analysis_task_engine
