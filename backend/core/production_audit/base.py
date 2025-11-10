"""Base class for audit modules."""

from abc import ABC, abstractmethod
from typing import Optional

from .models import AuditResult


class AuditModule(ABC):
    """Base class for all audit modules.
    
    Each audit module is responsible for evaluating a specific category
    of production readiness (e.g., LLM integration, infrastructure resilience).
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        """Initialize audit module.
        
        Args:
            workspace_root: Root directory of the workspace to audit.
                          Defaults to current directory if not provided.
        """
        self.workspace_root = workspace_root or "."
    
    @abstractmethod
    async def audit(self) -> AuditResult:
        """Perform audit and return results.
        
        This method should:
        1. Execute all checks for this category
        2. Calculate scores for each check
        3. Identify gaps based on check results
        4. Generate recommendations
        5. Return complete AuditResult
        
        Returns:
            AuditResult with scores, checks, gaps, and recommendations.
        """
        pass
    
    @abstractmethod
    def get_category_name(self) -> str:
        """Get audit category name.
        
        Returns:
            Human-readable category name (e.g., "LLM Integration").
        """
        pass
    
    @abstractmethod
    def get_weight(self) -> float:
        """Get category weight for overall score calculation.
        
        Returns:
            Weight between 0.0 and 1.0. All weights should sum to 1.0.
        """
        pass
    
    def _calculate_category_score(self, checks: list) -> float:
        """Calculate overall score for this category based on check results.
        
        Args:
            checks: List of CheckResult objects.
            
        Returns:
            Score between 0 and 100.
        """
        if not checks:
            return 0.0
        
        total_score = sum(check.score for check in checks)
        return total_score / len(checks)
