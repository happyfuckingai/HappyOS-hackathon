"""
Financial Services Industry Templates

FINRA/SEC compliant AI agents for financial services with built-in
regulatory compliance, risk management, and audit capabilities.
"""

from .compliance_agent import ComplianceAgent, FinanceConfig
from .trading_agent import TradingAgent, TradingConfig
from .risk_agent import RiskAnalysisAgent, RiskConfig

__all__ = [
    "ComplianceAgent",
    "FinanceConfig",
    "TradingAgent", 
    "TradingConfig",
    "RiskAnalysisAgent",
    "RiskConfig",
]