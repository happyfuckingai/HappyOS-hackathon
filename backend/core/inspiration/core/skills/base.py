"""
Base class for all skills.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseSkill(ABC):
    """
    Abstract base class for all skills.
    """
    @abstractmethod
    async def execute(self, user_request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill.
        """
        pass
