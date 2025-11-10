"""
🤖 HAPPYOS MCP ADAPTER FÖR WINDOWS AI STUDIO

Denna modul skapar en MCP (Model Control Protocol) server som kopplar samman
HappyOS agent-system med Windows AI Studio's visuella verktyg.

Funktioner:
- Exponerar HappyOS-agenter som MCP-verktyg
- Tillhandahåller visuella templates för varje agenttyp
- Möjliggör realtids-testning och debugging
- Integrerar med Windows AI Studio's Agent Builder

Författare: HappyOS AI Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from app.config.settings import get_settings
from app.core.error_handler import error_handler, HappyOSError
from app.agents.multi_agent import agent_orchestrator, AgentCapability, Task, TaskPriority
from app.core.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class MCPTool:
    """Representerar ett MCP-verktyg."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable


@dataclass
class MCPToolResult:
    """Resultat från ett MCP-verktyg."""
    success: bool
    content: List[Dict[str, Any]]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentTemplate:
    """Template för visuell agent-representation."""
    name: str
    type: str
    description: str
    visual: Dict[str, Any]
    capabilities: List[str]
    default_inputs: Dict[str, Any]
    test_scenarios: List[Dict[str, Any]]
    performance_metrics: Optional[Dict[str, Any]] = None


class HappyOSMCPAdapter:
    """
    MCP Adapter för HappyOS - kopplar samman agent-systemet med Windows AI Studio.

    Denna adapter:
    1. Upptäcker automatiskt alla tillgängliga HappyOS-agenter
    2. Skapar MCP-verktyg för varje agent
    3. Tillhandahåller visuella templates
    4. Hanterar verktygs-exekvering och felhantering
    """

    def __init__(self):
        self.agent_orchestrator = agent_orchestrator
        self.available_tools: Dict[str, MCPTool] = {}
        self.agent_templates: Dict[str, AgentTemplate] = {}
        self.session_manager = MCPSessionManager()
        self._initialized = False

    async def initialize(self):
        """Initiera MCP adaptern."""
        if self._initialized:
            return

        logger.info("Initializing HappyOS MCP Adapter...")

        try:
            # Registrera alla agent-verktyg
            await self._register_agent_tools()

            # Registrera system-verktyg
            await self._register_system_tools()

            # Skapa visuella templates
            await self._create_agent_templates()

            self._initialized = True
            logger.info(f"HappyOS MCP Adapter initialized with {len(self.available_tools)} tools")

        except Exception as e:
            logger.error(f"Failed to initialize MCP Adapter: {str(e)}")
            raise HappyOSError(f"MCP Adapter initialization failed: {str(e)}")

    async def _register_agent_tools(self):
        """Registrera MCP-verktyg för varje HappyOS-agent."""
        for agent_name, agent in self.agent_orchestrator.agents.items():
            tool_name = f"happyos_agent_{agent_name}"

            tool = MCPTool(
                name=tool_name,
                description=f"Execute tasks with HappyOS {agent_name} agent. Capabilities: {', '.join([cap.value for cap in agent.capabilities])}",
                input_schema=self._create_agent_input_schema(agent),
                handler=self._create_agent_handler(agent_name)
            )

            self.available_tools[tool_name] = tool
            logger.debug(f"Registered MCP tool: {tool_name}")

    async def _register_system_tools(self):
        """Registrera system-specifika MCP-verktyg."""
        system_tools = [
            MCPTool(
                name="happyos_system_get_agents",
                description="Get list of all available HappyOS agents with their capabilities",
                input_schema={"type": "object", "properties": {}},
                handler=self._handle_get_agents
            ),
            MCPTool(
                name="happyos_system_get_agent_status",
                description="Get detailed status of a specific agent",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_name": {"type": "string", "description": "Name of the agent"}
                    },
                    "required": ["agent_name"]
                },
                handler=self._handle_get_agent_status
            ),
            MCPTool(
                name="happyos_system_run_bulk_test",
                description="Run bulk tests across multiple agents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "test_cases": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "agent_name": {"type": "string"},
                                    "task_description": {"type": "string"},
                                    "context": {"type": "object"}
                                }
                            }
                        }
                    },
                    "required": ["test_cases"]
                },
                handler=self._handle_bulk_test
            )
        ]

        for tool in system_tools:
            self.available_tools[tool.name] = tool
            logger.debug(f"Registered system MCP tool: {tool.name}")

    def _create_agent_input_schema(self, agent) -> Dict[str, Any]:
        """Skapa input-schema för agent baserat på dess capabilities."""
        schema = {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "The task to be executed by the agent"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for the task",
                    "additionalProperties": True
                },
                "priority": {
                    "type": "string",
                    "enum": ["LOW", "NORMAL", "HIGH", "URGENT"],
                    "default": "NORMAL",
                    "description": "Task priority level"
                }
            },
            "required": ["task_description"]
        }

        # Lägg till capability-specifika fält
        if AgentCapability.RESEARCH in agent.capabilities:
            schema["properties"]["research_depth"] = {
                "type": "string",
                "enum": ["basic", "detailed", "comprehensive"],
                "default": "detailed",
                "description": "Depth of research analysis"
            }

        if AgentCapability.WRITING in agent.capabilities:
            schema["properties"]["writing_tone"] = {
                "type": "string",
                "enum": ["professional", "casual", "academic", "creative"],
                "default": "professional",
                "description": "Writing tone and style"
            }

        return schema

    def _create_agent_handler(self, agent_name: str) -> Callable:
        """Skapa handler-funktion för agent-verktyg."""
        async def handler(parameters: Dict[str, Any]) -> MCPToolResult:
            return await self._execute_agent_tool(agent_name, parameters)

        return handler

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> MCPToolResult:
        """Huvudfunktion för att exekvera MCP-verktyg."""
        if tool_name not in self.available_tools:
            return MCPToolResult(
                success=False,
                content=[],
                error=f"Unknown tool: {tool_name}"
            )

        tool = self.available_tools[tool_name]

        try:
            logger.info(f"Executing MCP tool: {tool_name}")
            start_time = time.time()

            result = await tool.handler(parameters)

            execution_time = time.time() - start_time
            logger.info(f"MCP tool {tool_name} executed in {execution_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"MCP tool execution failed: {str(e)}")
            return MCPToolResult(
                success=False,
                content=[],
                error=str(e)
            )

    async def _execute_agent_tool(self, agent_name: str, params: Dict[str, Any]) -> MCPToolResult:
        """Exekvera agent-specifika verktyg."""
        agent = self.agent_orchestrator.agents.get(agent_name.lower())

        if not agent:
            return MCPToolResult(
                success=False,
                content=[],
                error=f"Agent {agent_name} not found"
            )

        # Skapa task från parameters
        task_id = f"mcp_{agent_name}_{datetime.now().timestamp()}"
        task = Task(
            task_id=task_id,
            description=params["task_description"],
            task_type=self._infer_task_type(params, agent),
            priority=TaskPriority[params.get("priority", "NORMAL")],
            context=params.get("context", {})
        )

        # Exekvera task genom agent
        start_time = time.time()

        try:
            result = await agent.process_task(task)
            execution_time = time.time() - start_time

            # Formatera resultat för MCP
            content = []

            if result.get("success"):
                content.append({
                    "type": "text",
                    "text": result.get("data", {}).get("llm_response", "Task completed successfully")
                })

                # Lägg till metadata
                content.append({
                    "type": "text",
                    "text": f"Execution time: {execution_time:.2f}s | Task ID: {task_id}"
                })
            else:
                content.append({
                    "type": "text",
                    "text": f"Task failed: {result.get('error', 'Unknown error')}"
                })

            return MCPToolResult(
                success=result.get("success", False),
                content=content,
                metadata={
                    "agent": agent_name,
                    "execution_time": execution_time,
                    "task_id": task_id,
                    "priority": params.get("priority", "NORMAL")
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Agent tool execution failed: {str(e)}")

            return MCPToolResult(
                success=False,
                content=[{
                    "type": "text",
                    "text": f"Task execution failed: {str(e)}"
                }],
                error=str(e),
                metadata={
                    "agent": agent_name,
                    "execution_time": execution_time,
                    "task_id": task_id
                }
            )

    async def _handle_get_agents(self, parameters: Dict[str, Any]) -> MCPToolResult:
        """Hantera get_agents systemverktyg."""
        agents_info = []

        for agent_name, agent in self.agent_orchestrator.agents.items():
            agent_info = {
                "name": agent_name,
                "displayName": agent.name,
                "capabilities": [cap.value for cap in agent.capabilities],
                "model": agent.model,
                "status": agent.get_status(),
                "template": self.agent_templates.get(agent_name, {})
            }
            agents_info.append(agent_info)

        return MCPToolResult(
            success=True,
            content=[{
                "type": "json",
                "data": agents_info
            }],
            metadata={"total_agents": len(agents_info)}
        )

    async def _handle_get_agent_status(self, parameters: Dict[str, Any]) -> MCPToolResult:
        """Hantera get_agent_status systemverktyg."""
        agent_name = parameters.get("agent_name", "").lower()
        agent = self.agent_orchestrator.agents.get(agent_name)

        if not agent:
            return MCPToolResult(
                success=False,
                content=[],
                error=f"Agent {agent_name} not found"
            )

        status = agent.get_status()

        return MCPToolResult(
            success=True,
            content=[{
                "type": "json",
                "data": status
            }],
            metadata={"agent_name": agent_name}
        )

    async def _handle_bulk_test(self, parameters: Dict[str, Any]) -> MCPToolResult:
        """Hantera bulk test systemverktyg."""
        test_cases = parameters.get("test_cases", [])
        results = []

        for i, test_case in enumerate(test_cases):
            agent_name = test_case.get("agent_name", "").lower()
            task_desc = test_case.get("task_description", "")
            context = test_case.get("context", {})

            agent = self.agent_orchestrator.agents.get(agent_name)
            if not agent:
                results.append({
                    "test_case": i + 1,
                    "agent": agent_name,
                    "success": False,
                    "error": f"Agent {agent_name} not found"
                })
                continue

            # Kör test
            task = Task(
                task_id=f"bulk_test_{i}_{datetime.now().timestamp()}",
                description=task_desc,
                task_type="test",
                context=context
            )

            try:
                result = await agent.process_task(task)
                results.append({
                    "test_case": i + 1,
                    "agent": agent_name,
                    "success": result.get("success", False),
                    "response": result.get("data", {}).get("llm_response", ""),
                    "execution_time": result.get("execution_time", 0)
                })
            except Exception as e:
                results.append({
                    "test_case": i + 1,
                    "agent": agent_name,
                    "success": False,
                    "error": str(e)
                })

        return MCPToolResult(
            success=True,
            content=[{
                "type": "json",
                "data": results
            }],
            metadata={
                "total_tests": len(test_cases),
                "successful_tests": len([r for r in results if r.get("success")])
            }
        )

    def _infer_task_type(self, params: Dict[str, Any], agent) -> str:
        """Härleda uppgiftstyp från parametrar och agent-kapabiliteter."""
        task_desc = params.get("task_description", "").lower()

        # Research tasks
        if AgentCapability.RESEARCH in agent.capabilities and any(word in task_desc for word in ['research', 'analyze', 'study', 'investigate']):
            return "research"

        # Writing tasks
        if AgentCapability.WRITING in agent.capabilities and any(word in task_desc for word in ['write', 'create', 'compose', 'draft']):
            return "writing"

        # CAMEL tasks
        if AgentCapability.CAMEL_WORKFLOW in agent.capabilities and any(word in task_desc for word in ['plan', 'coordinate', 'workflow', 'complex']):
            return "camel"

        return "general"

    async def _create_agent_templates(self):
        """Skapa visuella templates för varje agenttyp."""
        templates = {
            "ResearchAgent": AgentTemplate(
                name="Research Agent",
                type="ResearchAgent",
                description="Expert agent for research, data analysis, and information gathering. Specializes in comprehensive analysis and evidence-based reporting.",
                visual={
                    "icon": "🔍",
                    "color": "#4A90E2",
                    "shape": "hexagon",
                    "size": "large",
                    "category": "Analysis"
                },
                capabilities=["RESEARCH", "ANALYSIS", "WRITING"],
                default_inputs={
                    "research_depth": "detailed",
                    "output_format": "comprehensive_report",
                    "sources_required": 3,
                    "include_visualizations": True
                },
                test_scenarios=[
                    {
                        "name": "Market Analysis",
                        "input": "Analyze the AI market trends and predict growth for 2025-2030",
                        "expectedOutput": "Detailed market analysis with data, trends, predictions, and visualizations"
                    },
                    {
                        "name": "Technical Research",
                        "input": "Research the latest developments in quantum computing hardware",
                        "expectedOutput": "Technical report on quantum computing advancements with citations and technical details"
                    }
                ],
                performance_metrics={
                    "expectedResponseTime": "30-120 seconds",
                    "accuracyThreshold": "85%",
                    "completenessScore": "90%"
                }
            ),

            "WritingAgent": AgentTemplate(
                name="Writing Agent",
                type="WritingAgent",
                description="Creative writing specialist for content generation, copywriting, and communication. Adapts tone and style based on audience and purpose.",
                visual={
                    "icon": "✍️",
                    "color": "#7ED321",
                    "shape": "rectangle",
                    "size": "medium",
                    "category": "Content"
                },
                capabilities=["WRITING", "TRANSLATION"],
                default_inputs={
                    "tone": "professional",
                    "audience": "general",
                    "length": "medium",
                    "include_call_to_action": True
                },
                test_scenarios=[
                    {
                        "name": "Product Description",
                        "input": "Write a compelling product description for HappyOS AI system",
                        "expectedOutput": "Engaging marketing copy highlighting key features and benefits"
                    },
                    {
                        "name": "Technical Documentation",
                        "input": "Create API documentation for the agent orchestration endpoint",
                        "expectedOutput": "Clear, comprehensive API documentation with examples and use cases"
                    }
                ],
                performance_metrics={
                    "expectedResponseTime": "15-60 seconds",
                    "readabilityScore": "70+",
                    "engagementPotential": "80%"
                }
            ),

            "CAMELAgent": AgentTemplate(
                name="CAMEL Workflow Agent",
                type="CAMELAgent",
                description="Multi-agent orchestration specialist for complex, multi-step tasks. Breaks down complex problems and coordinates multiple agents for optimal results.",
                visual={
                    "icon": "🤝",
                    "color": "#F5A623",
                    "shape": "diamond",
                    "size": "large",
                    "category": "Orchestration"
                },
                capabilities=["CAMEL_WORKFLOW", "PLANNING", "CODING"],
                default_inputs={
                    "max_subtasks": 4,
                    "coordination_strategy": "parallel",
                    "quality_threshold": "high",
                    "deadline_sensitivity": "medium"
                },
                test_scenarios=[
                    {
                        "name": "Product Launch Strategy",
                        "input": "Develop a comprehensive product launch strategy for HappyOS including marketing, technical setup, and user onboarding",
                        "expectedOutput": "Complete launch plan with multiple coordinated components"
                    },
                    {
                        "name": "System Integration",
                        "input": "Integrate multiple AI services (OpenAI, Anthropic, local models) into a unified orchestration system",
                        "expectedOutput": "Detailed integration plan with step-by-step implementation and testing procedures"
                    }
                ],
                performance_metrics={
                    "expectedResponseTime": "60-300 seconds",
                    "coordinationEfficiency": "85%",
                    "taskCompletionRate": "95%"
                }
            )
        }

        # Lägg till templates baserat på tillgängliga agenter
        for agent_name in self.agent_orchestrator.agents.keys():
            if agent_name in templates:
                self.agent_templates[agent_name] = templates[agent_name]
            else:
                # Skapa generisk template för okända agenter
                self.agent_templates[agent_name] = AgentTemplate(
                    name=agent_name,
                    type=agent_name,
                    description=f"Custom HappyOS agent: {agent_name}",
                    visual={
                        "icon": "🤖",
                        "color": "#BD10E0",
                        "shape": "circle",
                        "size": "medium",
                        "category": "Custom"
                    },
                    capabilities=["GENERAL"],
                    default_inputs={},
                    test_scenarios=[]
                )

        logger.info(f"Created {len(self.agent_templates)} agent templates")

    def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """Returnera alla tillgängliga MCP-verktyg."""
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            for name, tool in self.available_tools.items()
        }

    def get_agent_templates(self) -> Dict[str, Dict[str, Any]]:
        """Returnera alla agent-templates."""
        return {
            name: asdict(template)
            for name, template in self.agent_templates.items()
        }


class MCPSessionManager:
    """Hanterar MCP-sessioner och tillstånd."""

    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 3600  # 1 timme

    def create_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """Skapa en ny session."""
        self.active_sessions[session_id] = {
            "created": datetime.now(),
            "metadata": metadata or {},
            "tool_calls": []
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Hämta session-information."""
        return self.active_sessions.get(session_id)

    def update_session(self, session_id: str, tool_call: Dict[str, Any]):
        """Uppdatera session med verktygsanrop."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["tool_calls"].append(tool_call)
            self.active_sessions[session_id]["last_activity"] = datetime.now()

    def cleanup_expired_sessions(self):
        """Rensa utgångna sessioner."""
        current_time = datetime.now()
        expired = [
            session_id for session_id, session in self.active_sessions.items()
            if (current_time - session["created"]).total_seconds() > self.session_timeout
        ]

        for session_id in expired:
            del self.active_sessions[session_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired MCP sessions")


# Global MCP adapter-instans
mcp_adapter = HappyOSMCPAdapter()


async def initialize_mcp_adapter():
    """Initiera den globala MCP adaptern."""
    await mcp_adapter.initialize()


@error_handler(default_return=MCPToolResult(success=False, content=[], error="MCP operation failed"))
async def execute_mcp_tool(tool_name: str, parameters: Dict[str, Any]) -> MCPToolResult:
    """
    Exekvera ett MCP-verktyg genom HappyOS adaptern.

    Args:
        tool_name: Namn på verktyget att exekvera
        parameters: Parametrar för verktyget

    Returns:
        Resultat från verktygs-exekvering
    """
    return await mcp_adapter.execute_tool(tool_name, parameters)


# Exportera viktiga komponenter
__all__ = [
    'HappyOSMCPAdapter',
    'MCPTool',
    'MCPToolResult',
    'AgentTemplate',
    'MCPSessionManager',
    'mcp_adapter',
    'initialize_mcp_adapter',
    'execute_mcp_tool'
]