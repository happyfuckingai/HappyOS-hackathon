"""
LLM cost calculator for tracking and estimating costs across different providers.

This module provides cost calculation based on token usage and model pricing.
Pricing is based on public pricing as of 2024 and should be updated regularly.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelPricing:
    """Pricing information for a specific model."""
    input_cost_per_1k: float  # Cost per 1000 input tokens
    output_cost_per_1k: float  # Cost per 1000 output tokens
    provider: str
    model_name: str


class LLMCostCalculator:
    """
    Calculator for LLM costs across different providers and models.
    
    Pricing is approximate and based on public pricing information.
    Actual costs may vary based on volume discounts and regional pricing.
    """
    
    # Pricing data (USD per 1000 tokens)
    PRICING_TABLE: Dict[str, ModelPricing] = {
        # OpenAI GPT-4 models
        "gpt-4": ModelPricing(
            input_cost_per_1k=0.03,
            output_cost_per_1k=0.06,
            provider="openai",
            model_name="gpt-4"
        ),
        "gpt-4-turbo": ModelPricing(
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.03,
            provider="openai",
            model_name="gpt-4-turbo"
        ),
        "gpt-4-turbo-preview": ModelPricing(
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.03,
            provider="openai",
            model_name="gpt-4-turbo-preview"
        ),
        
        # OpenAI GPT-3.5 models
        "gpt-3.5-turbo": ModelPricing(
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0015,
            provider="openai",
            model_name="gpt-3.5-turbo"
        ),
        
        # AWS Bedrock Claude models
        "anthropic.claude-3-sonnet-20240229-v1:0": ModelPricing(
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            provider="bedrock",
            model_name="claude-3-sonnet"
        ),
        "anthropic.claude-3-haiku-20240307-v1:0": ModelPricing(
            input_cost_per_1k=0.00025,
            output_cost_per_1k=0.00125,
            provider="bedrock",
            model_name="claude-3-haiku"
        ),
        "anthropic.claude-3-opus-20240229-v1:0": ModelPricing(
            input_cost_per_1k=0.015,
            output_cost_per_1k=0.075,
            provider="bedrock",
            model_name="claude-3-opus"
        ),
        "anthropic.claude-3-5-sonnet-20240620-v1:0": ModelPricing(
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            provider="bedrock",
            model_name="claude-3.5-sonnet"
        ),
        "anthropic.claude-v2": ModelPricing(
            input_cost_per_1k=0.008,
            output_cost_per_1k=0.024,
            provider="bedrock",
            model_name="claude-2"
        ),
        "anthropic.claude-v2:1": ModelPricing(
            input_cost_per_1k=0.008,
            output_cost_per_1k=0.024,
            provider="bedrock",
            model_name="claude-2.1"
        ),
        
        # Google GenAI models
        "gemini-1.5-flash": ModelPricing(
            input_cost_per_1k=0.00035,
            output_cost_per_1k=0.00105,
            provider="google",
            model_name="gemini-1.5-flash"
        ),
        "gemini-1.5-pro": ModelPricing(
            input_cost_per_1k=0.0035,
            output_cost_per_1k=0.0105,
            provider="google",
            model_name="gemini-1.5-pro"
        ),
        "gemini-pro": ModelPricing(
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0015,
            provider="google",
            model_name="gemini-pro"
        ),
    }
    
    # Simplified model name mappings
    MODEL_ALIASES = {
        "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
        "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        "claude-3.5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "claude-2": "anthropic.claude-v2",
        "claude-2.1": "anthropic.claude-v2:1",
        "claude": "anthropic.claude-3-sonnet-20240229-v1:0",
    }
    
    @classmethod
    def calculate_cost(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        Calculate cost for an LLM request.
        
        Args:
            model: Model identifier
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens
            
        Returns:
            Estimated cost in USD
        """
        # Resolve model alias
        resolved_model = cls.MODEL_ALIASES.get(model, model)
        
        # Get pricing info
        pricing = cls.PRICING_TABLE.get(resolved_model)
        
        if not pricing:
            # Unknown model, use default GPT-4 pricing as fallback
            pricing = cls.PRICING_TABLE["gpt-4"]
        
        # Calculate cost
        input_cost = (prompt_tokens / 1000.0) * pricing.input_cost_per_1k
        output_cost = (completion_tokens / 1000.0) * pricing.output_cost_per_1k
        
        total_cost = input_cost + output_cost
        
        return round(total_cost, 6)  # Round to 6 decimal places
    
    @classmethod
    def calculate_cost_from_total_tokens(
        cls,
        model: str,
        total_tokens: int,
        input_ratio: float = 0.5
    ) -> float:
        """
        Calculate cost when only total tokens are known.
        
        Assumes a ratio between input and output tokens.
        
        Args:
            model: Model identifier
            total_tokens: Total token count
            input_ratio: Ratio of input tokens to total (default: 0.5)
            
        Returns:
            Estimated cost in USD
        """
        prompt_tokens = int(total_tokens * input_ratio)
        completion_tokens = total_tokens - prompt_tokens
        
        return cls.calculate_cost(model, prompt_tokens, completion_tokens)
    
    @classmethod
    def get_model_pricing(cls, model: str) -> Optional[ModelPricing]:
        """
        Get pricing information for a model.
        
        Args:
            model: Model identifier
            
        Returns:
            ModelPricing object or None if not found
        """
        resolved_model = cls.MODEL_ALIASES.get(model, model)
        return cls.PRICING_TABLE.get(resolved_model)
    
    @classmethod
    def estimate_monthly_cost(
        cls,
        model: str,
        requests_per_day: int,
        avg_prompt_tokens: int,
        avg_completion_tokens: int
    ) -> Dict[str, float]:
        """
        Estimate monthly cost based on usage patterns.
        
        Args:
            model: Model identifier
            requests_per_day: Average requests per day
            avg_prompt_tokens: Average prompt tokens per request
            avg_completion_tokens: Average completion tokens per request
            
        Returns:
            Dict with daily, weekly, and monthly cost estimates
        """
        cost_per_request = cls.calculate_cost(
            model, avg_prompt_tokens, avg_completion_tokens
        )
        
        daily_cost = cost_per_request * requests_per_day
        weekly_cost = daily_cost * 7
        monthly_cost = daily_cost * 30
        
        return {
            "cost_per_request": round(cost_per_request, 6),
            "daily_cost": round(daily_cost, 2),
            "weekly_cost": round(weekly_cost, 2),
            "monthly_cost": round(monthly_cost, 2),
            "model": model,
            "requests_per_day": requests_per_day
        }
    
    @classmethod
    def compare_model_costs(
        cls,
        models: list,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Dict[str, float]:
        """
        Compare costs across different models for the same request.
        
        Args:
            models: List of model identifiers
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Dict mapping model names to costs
        """
        costs = {}
        
        for model in models:
            cost = cls.calculate_cost(model, prompt_tokens, completion_tokens)
            costs[model] = cost
        
        return costs
    
    @classmethod
    def get_cheapest_model(
        cls,
        models: list,
        prompt_tokens: int,
        completion_tokens: int
    ) -> tuple:
        """
        Find the cheapest model for a given request.
        
        Args:
            models: List of model identifiers
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Tuple of (model_name, cost)
        """
        costs = cls.compare_model_costs(models, prompt_tokens, completion_tokens)
        
        if not costs:
            return None, 0.0
        
        cheapest_model = min(costs.items(), key=lambda x: x[1])
        return cheapest_model



@dataclass
class CostEntry:
    """Single cost entry for tracking."""
    timestamp: datetime
    agent_id: str
    model: str
    provider: str
    cost: float
    prompt_tokens: int
    completion_tokens: int


@dataclass
class DailyCostSummary:
    """Summary of costs for a specific day."""
    date: str  # YYYY-MM-DD format
    total_cost: float
    total_requests: int
    total_tokens: int
    cost_by_agent: Dict[str, float] = field(default_factory=dict)
    cost_by_model: Dict[str, float] = field(default_factory=dict)
    cost_by_provider: Dict[str, float] = field(default_factory=dict)


class CostTracker:
    """
    Tracks LLM costs over time with daily aggregation and budget alerts.
    
    This class maintains an in-memory history of costs and provides
    aggregation and alerting functionality.
    """
    
    def __init__(self, daily_budget: Optional[float] = None):
        """
        Initialize cost tracker.
        
        Args:
            daily_budget: Optional daily budget limit in USD
        """
        self.daily_budget = daily_budget
        self.cost_history: List[CostEntry] = []
        self.logger = logger
        
        # Cache for daily summaries
        self._daily_summaries: Dict[str, DailyCostSummary] = {}
    
    def record_cost(
        self,
        agent_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Record a cost entry and return the calculated cost.
        
        Args:
            agent_id: Agent making the request
            model: Model used
            provider: Provider used
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Calculated cost in USD
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Calculate cost
        cost = LLMCostCalculator.calculate_cost(
            model, prompt_tokens, completion_tokens
        )
        
        # Create entry
        entry = CostEntry(
            timestamp=timestamp,
            agent_id=agent_id,
            model=model,
            provider=provider,
            cost=cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        
        # Add to history
        self.cost_history.append(entry)
        
        # Invalidate cache for this day
        date_key = timestamp.strftime("%Y-%m-%d")
        if date_key in self._daily_summaries:
            del self._daily_summaries[date_key]
        
        # Check budget alert
        if self.daily_budget:
            self._check_budget_alert(date_key)
        
        return cost
    
    def get_daily_summary(self, date: Optional[datetime] = None) -> DailyCostSummary:
        """
        Get cost summary for a specific day.
        
        Args:
            date: Date to get summary for (defaults to today)
            
        Returns:
            DailyCostSummary for the specified date
        """
        if date is None:
            date = datetime.utcnow()
        
        date_key = date.strftime("%Y-%m-%d")
        
        # Check cache
        if date_key in self._daily_summaries:
            return self._daily_summaries[date_key]
        
        # Calculate summary
        summary = self._calculate_daily_summary(date)
        
        # Cache it
        self._daily_summaries[date_key] = summary
        
        return summary
    
    def _calculate_daily_summary(self, date: datetime) -> DailyCostSummary:
        """Calculate daily summary from cost history."""
        date_key = date.strftime("%Y-%m-%d")
        
        # Filter entries for this day
        day_start = datetime(date.year, date.month, date.day)
        day_end = day_start + timedelta(days=1)
        
        day_entries = [
            entry for entry in self.cost_history
            if day_start <= entry.timestamp < day_end
        ]
        
        # Aggregate
        total_cost = sum(entry.cost for entry in day_entries)
        total_tokens = sum(
            entry.prompt_tokens + entry.completion_tokens
            for entry in day_entries
        )
        
        # By agent
        cost_by_agent = defaultdict(float)
        for entry in day_entries:
            cost_by_agent[entry.agent_id] += entry.cost
        
        # By model
        cost_by_model = defaultdict(float)
        for entry in day_entries:
            cost_by_model[entry.model] += entry.cost
        
        # By provider
        cost_by_provider = defaultdict(float)
        for entry in day_entries:
            cost_by_provider[entry.provider] += entry.cost
        
        return DailyCostSummary(
            date=date_key,
            total_cost=round(total_cost, 2),
            total_requests=len(day_entries),
            total_tokens=total_tokens,
            cost_by_agent=dict(cost_by_agent),
            cost_by_model=dict(cost_by_model),
            cost_by_provider=dict(cost_by_provider)
        )
    
    def get_cost_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[DailyCostSummary]:
        """
        Get cost summaries for a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of DailyCostSummary objects
        """
        summaries = []
        current_date = start_date
        
        while current_date <= end_date:
            summary = self.get_daily_summary(current_date)
            summaries.append(summary)
            current_date += timedelta(days=1)
        
        return summaries
    
    def get_weekly_summary(self, date: Optional[datetime] = None) -> Dict[str, any]:
        """
        Get cost summary for the week containing the specified date.
        
        Args:
            date: Date in the week (defaults to today)
            
        Returns:
            Dict with weekly summary
        """
        if date is None:
            date = datetime.utcnow()
        
        # Get start of week (Monday)
        days_since_monday = date.weekday()
        week_start = date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        # Get daily summaries
        daily_summaries = self.get_cost_range(week_start, week_end)
        
        # Aggregate
        total_cost = sum(s.total_cost for s in daily_summaries)
        total_requests = sum(s.total_requests for s in daily_summaries)
        total_tokens = sum(s.total_tokens for s in daily_summaries)
        
        return {
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d"),
            "total_cost": round(total_cost, 2),
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "daily_summaries": daily_summaries
        }
    
    def get_monthly_summary(self, date: Optional[datetime] = None) -> Dict[str, any]:
        """
        Get cost summary for the month containing the specified date.
        
        Args:
            date: Date in the month (defaults to today)
            
        Returns:
            Dict with monthly summary
        """
        if date is None:
            date = datetime.utcnow()
        
        # Get start and end of month
        month_start = datetime(date.year, date.month, 1)
        
        # Calculate last day of month
        if date.month == 12:
            month_end = datetime(date.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(date.year, date.month + 1, 1) - timedelta(days=1)
        
        # Get daily summaries
        daily_summaries = self.get_cost_range(month_start, month_end)
        
        # Aggregate
        total_cost = sum(s.total_cost for s in daily_summaries)
        total_requests = sum(s.total_requests for s in daily_summaries)
        total_tokens = sum(s.total_tokens for s in daily_summaries)
        
        return {
            "month": date.strftime("%Y-%m"),
            "month_start": month_start.strftime("%Y-%m-%d"),
            "month_end": month_end.strftime("%Y-%m-%d"),
            "total_cost": round(total_cost, 2),
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "daily_summaries": daily_summaries
        }
    
    def _check_budget_alert(self, date_key: str) -> None:
        """
        Check if daily budget has been exceeded and log alert.
        
        Args:
            date_key: Date key in YYYY-MM-DD format
        """
        if not self.daily_budget:
            return
        
        summary = self.get_daily_summary(
            datetime.strptime(date_key, "%Y-%m-%d")
        )
        
        if summary.total_cost >= self.daily_budget:
            self.logger.warning(
                f"Daily budget exceeded! "
                f"Date: {date_key}, "
                f"Cost: ${summary.total_cost:.2f}, "
                f"Budget: ${self.daily_budget:.2f}"
            )
    
    def check_budget_threshold(
        self,
        threshold_percent: float = 80.0,
        date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Check if cost is approaching budget threshold.
        
        Args:
            threshold_percent: Percentage of budget to alert at (default: 80%)
            date: Date to check (defaults to today)
            
        Returns:
            Dict with threshold check results
        """
        if not self.daily_budget:
            return {
                "budget_set": False,
                "message": "No daily budget configured"
            }
        
        summary = self.get_daily_summary(date)
        threshold_amount = self.daily_budget * (threshold_percent / 100.0)
        
        is_over_threshold = summary.total_cost >= threshold_amount
        is_over_budget = summary.total_cost >= self.daily_budget
        
        percent_used = (summary.total_cost / self.daily_budget) * 100.0
        
        return {
            "budget_set": True,
            "daily_budget": self.daily_budget,
            "current_cost": summary.total_cost,
            "threshold_amount": round(threshold_amount, 2),
            "threshold_percent": threshold_percent,
            "is_over_threshold": is_over_threshold,
            "is_over_budget": is_over_budget,
            "percent_used": round(percent_used, 1),
            "remaining_budget": round(self.daily_budget - summary.total_cost, 2)
        }
    
    def set_daily_budget(self, budget: float) -> None:
        """
        Set or update the daily budget.
        
        Args:
            budget: Daily budget in USD
        """
        self.daily_budget = budget
        self.logger.info(f"Daily budget set to ${budget:.2f}")
    
    def clear_old_history(self, days_to_keep: int = 30) -> int:
        """
        Clear cost history older than specified days.
        
        Args:
            days_to_keep: Number of days of history to keep
            
        Returns:
            Number of entries removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        original_count = len(self.cost_history)
        self.cost_history = [
            entry for entry in self.cost_history
            if entry.timestamp >= cutoff_date
        ]
        
        removed_count = original_count - len(self.cost_history)
        
        # Clear cache
        self._daily_summaries.clear()
        
        if removed_count > 0:
            self.logger.info(
                f"Cleared {removed_count} old cost entries "
                f"(keeping last {days_to_keep} days)"
            )
        
        return removed_count


# Global cost tracker instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker(daily_budget: Optional[float] = None) -> CostTracker:
    """
    Get or create the global cost tracker instance.
    
    Args:
        daily_budget: Optional daily budget limit in USD
        
    Returns:
        CostTracker instance
    """
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker(daily_budget=daily_budget)
    elif daily_budget is not None and _cost_tracker.daily_budget != daily_budget:
        _cost_tracker.set_daily_budget(daily_budget)
    return _cost_tracker
