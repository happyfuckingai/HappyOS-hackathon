"""
AgentManager - Hanterar agentinstanser och agentrelaterad logik för UltimateSelfBuildingOrchestrator.
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self, mr_happy_agent, skill_registry):
        self.mr_happy_agent = mr_happy_agent
        self.skill_registry = skill_registry
        self.orchestrator = None

    async def initialize(self):
        """Initiera agent och koppla ihop med skill registry och orchestrator."""
        result = {}
        if hasattr(self.mr_happy_agent, 'initialize'):
            result['mr_happy_agent'] = await self.mr_happy_agent.initialize()
        if hasattr(self.mr_happy_agent, 'set_skill_registry'):
            self.mr_happy_agent.set_skill_registry(self.skill_registry)
        if self.orchestrator and hasattr(self.mr_happy_agent, 'set_orchestrator'):
            self.mr_happy_agent.set_orchestrator(self.orchestrator)
        return result

    def set_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator
        if hasattr(self.mr_happy_agent, 'set_orchestrator'):
            self.mr_happy_agent.set_orchestrator(orchestrator)

    def get_agent(self):
        return self.mr_happy_agent

    def get_skill_registry(self):
        return self.skill_registry

    # Lägg till fler agentrelaterade metoder här vid behov
