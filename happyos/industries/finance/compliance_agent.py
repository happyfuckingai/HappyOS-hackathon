"""
Financial Compliance Agent

FINRA/SEC compliant AI agent for financial services with built-in
regulatory compliance checking, audit trails, and risk assessment.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime, timedelta

from ...agents.templates import IndustryTemplate, TemplateConfig, ComplianceLevel
from ...agents.base import AgentConfig
from ...config import Config
from ...exceptions import ValidationError, ComplianceError


class FinancialRegulation(Enum):
    """Supported financial regulations."""
    FINRA_3310 = "FINRA_3310"  # Anti-Money Laundering
    FINRA_2111 = "FINRA_2111"  # Suitability
    SEC_15C3_3 = "SEC_15c3_3"  # Customer Protection Rule
    SOX_404 = "SOX_404"        # Sarbanes-Oxley
    DODD_FRANK = "DODD_FRANK"  # Dodd-Frank Act
    MiFID_II = "MiFID_II"      # Markets in Financial Instruments Directive


@dataclass
class RiskLimits:
    """Risk management limits for financial operations."""
    
    max_position_size: float = 1000000.0  # Maximum position size
    var_limit: float = 50000.0            # Value at Risk limit
    concentration_limit: float = 0.1      # Maximum concentration (10%)
    leverage_limit: float = 3.0           # Maximum leverage ratio
    
    # Time-based limits
    daily_trading_limit: float = 5000000.0
    monthly_exposure_limit: float = 50000000.0


@dataclass
class FinanceConfig(TemplateConfig):
    """Configuration for financial services agents."""
    
    industry: str = "finance"
    compliance_level: ComplianceLevel = ComplianceLevel.REGULATORY
    
    # Financial regulations
    required_regulations: List[FinancialRegulation] = field(
        default_factory=lambda: [
            FinancialRegulation.FINRA_3310,
            FinancialRegulation.SEC_15C3_3
        ]
    )
    
    # Risk management
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    
    # Audit settings
    audit_retention_days: int = 2555  # 7 years for FINRA
    real_time_monitoring: bool = True
    
    # Integration settings
    market_data_sources: List[str] = field(default_factory=list)
    trading_systems: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate finance configuration."""
        super().__post_init__()
        
        # Ensure regulatory compliance requirements
        if self.compliance_level == ComplianceLevel.REGULATORY:
            required_standards = [
                "audit_logging",
                "data_encryption", 
                "real_time_monitoring",
                "risk_management"
            ]
            
            for standard in required_standards:
                if standard not in self.required_standards:
                    self.required_standards.append(standard)


class ComplianceAgent(IndustryTemplate):
    """FINRA/SEC compliant financial services agent.
    
    Provides comprehensive compliance checking for financial operations
    including AML, suitability analysis, and regulatory reporting.
    
    Features:
    - Real-time compliance monitoring
    - FINRA/SEC rule enforcement
    - Automated risk assessment
    - Comprehensive audit trails
    - Regulatory reporting
    
    Example:
        >>> config = FinanceConfig(
        ...     required_regulations=[FinancialRegulation.FINRA_3310],
        ...     risk_limits=RiskLimits(var_limit=25000)
        ... )
        >>> agent = ComplianceAgent(agent_config, sdk_config, config)
        >>> 
        >>> @agent.tool("check_transaction")
        >>> async def check_transaction(transaction: dict) -> dict:
        ...     result = await agent.check_compliance(transaction, "FINRA_3310")
        ...     return {"compliant": result.compliant, "risk_score": result.risk_score}
    """
    
    industry = "finance"
    template_version = "1.0.0"
    required_standards = [
        "FINRA_3310",
        "FINRA_2111", 
        "SEC_15c3_3",
        "SOX_404"
    ]
    
    def __init__(
        self,
        agent_config: AgentConfig,
        sdk_config: Config,
        finance_config: FinanceConfig
    ):
        """Initialize compliance agent.
        
        Args:
            agent_config: Base agent configuration
            sdk_config: SDK configuration
            finance_config: Finance-specific configuration
        """
        super().__init__(agent_config, sdk_config, finance_config)
        self.finance_config = finance_config
        
        # Initialize compliance engines
        self._compliance_engines = {
            regulation.value: self._create_compliance_engine(regulation)
            for regulation in finance_config.required_regulations
        }
        
        # Risk monitoring
        self._risk_monitor = RiskMonitor(finance_config.risk_limits)
        
        # Transaction cache for pattern analysis
        self._transaction_history: List[Dict[str, Any]] = []
        self._max_history_size = 10000
    
    async def _perform_compliance_check(
        self, 
        data: Dict[str, Any], 
        standard: str
    ) -> Dict[str, Any]:
        """Perform financial compliance check.
        
        Args:
            data: Transaction or operation data
            standard: Compliance standard (e.g., "FINRA_3310")
            
        Returns:
            Compliance check result
        """
        if standard not in self._compliance_engines:
            raise ValidationError(f"Unsupported compliance standard: {standard}")
        
        engine = self._compliance_engines[standard]
        
        # Perform compliance check
        result = await engine.check_compliance(data)
        
        # Add to transaction history for pattern analysis
        self._add_to_history(data, standard, result)
        
        # Perform risk assessment
        risk_assessment = await self._risk_monitor.assess_risk(data, result)
        result.update(risk_assessment)
        
        return result
    
    async def check_aml_compliance(
        self, 
        transaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check Anti-Money Laundering compliance (FINRA 3310).
        
        Args:
            transaction: Transaction data
            
        Returns:
            AML compliance result
        """
        return await self.check_compliance(transaction, "FINRA_3310")
    
    async def check_suitability(
        self,
        customer: Dict[str, Any],
        investment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check investment suitability (FINRA 2111).
        
        Args:
            customer: Customer profile data
            investment: Investment details
            
        Returns:
            Suitability analysis result
        """
        data = {
            "customer": customer,
            "investment": investment,
            "check_type": "suitability"
        }
        
        return await self.check_compliance(data, "FINRA_2111")
    
    async def assess_portfolio_risk(
        self,
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess portfolio risk and compliance.
        
        Args:
            portfolio: Portfolio data
            
        Returns:
            Risk assessment result
        """
        # Check against risk limits
        risk_result = await self._risk_monitor.assess_portfolio_risk(portfolio)
        
        # Check regulatory compliance
        compliance_results = {}
        for regulation in self.finance_config.required_regulations:
            if regulation in [FinancialRegulation.SEC_15C3_3]:
                compliance_results[regulation.value] = await self.check_compliance(
                    portfolio, regulation.value
                )
        
        return {
            "risk_assessment": risk_result,
            "compliance_checks": compliance_results,
            "overall_score": self._calculate_overall_score(risk_result, compliance_results)
        }
    
    async def generate_regulatory_report(
        self,
        report_type: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Generate regulatory compliance report.
        
        Args:
            report_type: Type of report (e.g., "FINRA_annual", "SEC_quarterly")
            period_start: Report period start
            period_end: Report period end
            
        Returns:
            Regulatory report
        """
        # Filter audit trail by period
        period_transactions = [
            entry for entry in self._audit_trail
            if period_start <= datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")) <= period_end
        ]
        
        # Generate report based on type
        if report_type == "FINRA_annual":
            return await self._generate_finra_annual_report(period_transactions)
        elif report_type == "SEC_quarterly":
            return await self._generate_sec_quarterly_report(period_transactions)
        else:
            return await self.generate_audit_report(
                period_start.isoformat(),
                period_end.isoformat()
            )
    
    def _create_compliance_engine(self, regulation: FinancialRegulation):
        """Create compliance engine for specific regulation."""
        if regulation == FinancialRegulation.FINRA_3310:
            return AMLComplianceEngine()
        elif regulation == FinancialRegulation.FINRA_2111:
            return SuitabilityEngine()
        elif regulation == FinancialRegulation.SEC_15C3_3:
            return CustomerProtectionEngine()
        else:
            return GenericComplianceEngine(regulation)
    
    def _add_to_history(
        self,
        data: Dict[str, Any],
        standard: str,
        result: Dict[str, Any]
    ) -> None:
        """Add transaction to history for pattern analysis."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "data_hash": self._hash_data(data),
            "standard": standard,
            "compliant": result.get("compliant", False),
            "risk_score": result.get("risk_score", 0.0)
        }
        
        self._transaction_history.append(entry)
        
        # Maintain history size limit
        if len(self._transaction_history) > self._max_history_size:
            self._transaction_history.pop(0)
    
    def _calculate_overall_score(
        self,
        risk_result: Dict[str, Any],
        compliance_results: Dict[str, Any]
    ) -> float:
        """Calculate overall compliance and risk score."""
        risk_score = risk_result.get("risk_score", 0.0)
        
        compliance_scores = [
            result.get("compliance_score", 0.0)
            for result in compliance_results.values()
        ]
        
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 1.0
        
        # Weighted average (70% compliance, 30% risk)
        return (avg_compliance * 0.7) + ((1.0 - risk_score) * 0.3)
    
    async def _generate_finra_annual_report(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate FINRA annual compliance report."""
        return {
            "report_type": "FINRA_annual",
            "period_transactions": len(transactions),
            "compliance_rate": self._calculate_compliance_rate(transactions),
            "aml_violations": len([t for t in transactions if not t.get("compliant", True)]),
            "risk_incidents": len([t for t in transactions if t.get("risk_score", 0) > 0.8]),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _generate_sec_quarterly_report(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate SEC quarterly compliance report."""
        return {
            "report_type": "SEC_quarterly",
            "period_transactions": len(transactions),
            "customer_protection_compliance": self._calculate_compliance_rate(transactions),
            "risk_assessment_summary": await self._risk_monitor.get_period_summary(),
            "generated_at": datetime.utcnow().isoformat()
        }


class RiskMonitor:
    """Risk monitoring and assessment for financial operations."""
    
    def __init__(self, risk_limits: RiskLimits):
        """Initialize risk monitor.
        
        Args:
            risk_limits: Risk limit configuration
        """
        self.risk_limits = risk_limits
        self.daily_exposure = 0.0
        self.monthly_exposure = 0.0
        self.last_reset = datetime.utcnow()
    
    async def assess_risk(
        self,
        data: Dict[str, Any],
        compliance_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess risk for transaction or operation.
        
        Args:
            data: Transaction data
            compliance_result: Compliance check result
            
        Returns:
            Risk assessment result
        """
        risk_score = 0.0
        risk_factors = []
        
        # Check position size
        position_size = data.get("amount", 0.0)
        if position_size > self.risk_limits.max_position_size:
            risk_score += 0.3
            risk_factors.append("position_size_exceeded")
        
        # Check compliance violations
        if not compliance_result.get("compliant", True):
            risk_score += 0.4
            risk_factors.append("compliance_violation")
        
        # Check daily limits
        if self.daily_exposure + position_size > self.risk_limits.daily_trading_limit:
            risk_score += 0.2
            risk_factors.append("daily_limit_approached")
        
        # Update exposure tracking
        self.daily_exposure += position_size
        
        return {
            "risk_score": min(risk_score, 1.0),
            "risk_factors": risk_factors,
            "within_limits": risk_score < 0.5
        }
    
    async def assess_portfolio_risk(
        self,
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess overall portfolio risk."""
        total_value = portfolio.get("total_value", 0.0)
        positions = portfolio.get("positions", [])
        
        # Calculate concentration risk
        concentration_risk = self._calculate_concentration_risk(positions, total_value)
        
        # Calculate VaR
        var_estimate = self._calculate_var(positions)
        
        # Overall risk score
        risk_score = max(concentration_risk, var_estimate / self.risk_limits.var_limit)
        
        return {
            "risk_score": min(risk_score, 1.0),
            "concentration_risk": concentration_risk,
            "var_estimate": var_estimate,
            "var_limit": self.risk_limits.var_limit,
            "within_limits": var_estimate <= self.risk_limits.var_limit
        }
    
    def _calculate_concentration_risk(
        self,
        positions: List[Dict[str, Any]],
        total_value: float
    ) -> float:
        """Calculate portfolio concentration risk."""
        if not positions or total_value == 0:
            return 0.0
        
        max_concentration = max(
            pos.get("value", 0.0) / total_value
            for pos in positions
        )
        
        return max(0.0, (max_concentration - self.risk_limits.concentration_limit) * 2)
    
    def _calculate_var(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate Value at Risk estimate."""
        # Simplified VaR calculation
        total_risk = sum(
            pos.get("value", 0.0) * pos.get("volatility", 0.1)
            for pos in positions
        )
        
        return total_risk * 1.65  # 95% confidence level
    
    async def get_period_summary(self) -> Dict[str, Any]:
        """Get risk monitoring summary for reporting period."""
        return {
            "daily_exposure": self.daily_exposure,
            "monthly_exposure": self.monthly_exposure,
            "daily_limit_utilization": self.daily_exposure / self.risk_limits.daily_trading_limit,
            "monthly_limit_utilization": self.monthly_exposure / self.risk_limits.monthly_exposure_limit
        }


# Compliance engines for different regulations
class AMLComplianceEngine:
    """Anti-Money Laundering compliance engine (FINRA 3310)."""
    
    async def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check AML compliance."""
        # Simplified AML check
        amount = data.get("amount", 0.0)
        customer_risk = data.get("customer_risk_score", 0.0)
        
        # High-risk indicators
        risk_score = 0.0
        violations = []
        
        # Large transaction check
        if amount > 10000:
            risk_score += 0.3
            violations.append("large_transaction")
        
        # High-risk customer
        if customer_risk > 0.7:
            risk_score += 0.4
            violations.append("high_risk_customer")
        
        # Unusual pattern (simplified)
        if data.get("unusual_pattern", False):
            risk_score += 0.5
            violations.append("unusual_pattern")
        
        return {
            "compliant": risk_score < 0.5,
            "risk_score": min(risk_score, 1.0),
            "violations": violations,
            "compliance_score": 1.0 - risk_score
        }


class SuitabilityEngine:
    """Investment suitability engine (FINRA 2111)."""
    
    async def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check suitability compliance."""
        customer = data.get("customer", {})
        investment = data.get("investment", {})
        
        # Suitability factors
        risk_tolerance = customer.get("risk_tolerance", "moderate")
        investment_risk = investment.get("risk_level", "moderate")
        
        # Simple suitability check
        suitable = self._check_suitability(risk_tolerance, investment_risk)
        
        return {
            "compliant": suitable,
            "risk_score": 0.0 if suitable else 0.8,
            "violations": [] if suitable else ["unsuitable_investment"],
            "compliance_score": 1.0 if suitable else 0.2
        }
    
    def _check_suitability(self, customer_risk: str, investment_risk: str) -> bool:
        """Check if investment is suitable for customer."""
        risk_levels = {"conservative": 1, "moderate": 2, "aggressive": 3}
        
        customer_level = risk_levels.get(customer_risk, 2)
        investment_level = risk_levels.get(investment_risk, 2)
        
        return investment_level <= customer_level


class CustomerProtectionEngine:
    """Customer protection engine (SEC 15c3-3)."""
    
    async def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check customer protection compliance."""
        # Simplified customer protection check
        segregated_funds = data.get("segregated_funds", True)
        proper_custody = data.get("proper_custody", True)
        
        compliant = segregated_funds and proper_custody
        violations = []
        
        if not segregated_funds:
            violations.append("funds_not_segregated")
        if not proper_custody:
            violations.append("improper_custody")
        
        return {
            "compliant": compliant,
            "risk_score": 0.0 if compliant else 0.9,
            "violations": violations,
            "compliance_score": 1.0 if compliant else 0.1
        }


class GenericComplianceEngine:
    """Generic compliance engine for other regulations."""
    
    def __init__(self, regulation: FinancialRegulation):
        """Initialize generic engine.
        
        Args:
            regulation: Financial regulation to check
        """
        self.regulation = regulation
    
    async def check_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generic compliance check."""
        # Placeholder implementation
        return {
            "compliant": True,
            "risk_score": 0.0,
            "violations": [],
            "compliance_score": 1.0,
            "regulation": self.regulation.value
        }