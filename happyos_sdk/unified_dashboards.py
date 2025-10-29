"""
Unified Dashboards and Alerting for HappyOS SDK

Provides standardized dashboard creation and alerting configuration
that works consistently across all HappyOS agent systems.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .logging import get_logger
from .metrics_collection import StandardizedMetrics

# Try to import backend observability for CloudWatch integration
try:
    from backend.modules.observability.cloudwatch import get_cloudwatch_monitor
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class DashboardWidget:
    """Configuration for a dashboard widget."""
    
    widget_type: str  # "metric", "log", "alarm"
    title: str
    x: int
    y: int
    width: int
    height: int
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch dashboard widget format."""
        return {
            "type": self.widget_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "properties": self.properties
        }


@dataclass
class AlertRule:
    """Configuration for an alert rule."""
    
    name: str
    metric_name: str
    threshold: float
    comparison_operator: str  # "GreaterThanThreshold", "LessThanThreshold"
    evaluation_periods: int
    period_seconds: int = 300
    statistic: str = "Average"  # "Average", "Sum", "Maximum", "Minimum"
    dimensions: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    actions_enabled: bool = True
    
    def to_cloudwatch_format(self, namespace: str) -> Dict[str, Any]:
        """Convert to CloudWatch alarm format."""
        alarm_config = {
            "AlarmName": self.name,
            "ComparisonOperator": self.comparison_operator,
            "EvaluationPeriods": self.evaluation_periods,
            "MetricName": self.metric_name,
            "Namespace": namespace,
            "Period": self.period_seconds,
            "Statistic": self.statistic,
            "Threshold": self.threshold,
            "ActionsEnabled": self.actions_enabled,
            "AlarmDescription": self.description or f"Alert for {self.metric_name}"
        }
        
        if self.dimensions:
            alarm_config["Dimensions"] = [
                {"Name": key, "Value": value}
                for key, value in self.dimensions.items()
            ]
        
        return alarm_config


class UnifiedDashboardManager:
    """Manages unified dashboards and alerting across all HappyOS agents."""
    
    def __init__(self, namespace: str = "HappyOS/Agents"):
        """
        Initialize dashboard manager.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self.cloudwatch = None
        
        if CLOUDWATCH_AVAILABLE:
            try:
                self.cloudwatch = get_cloudwatch_monitor()
                logger.info("CloudWatch dashboard integration enabled")
            except Exception as e:
                logger.warning(f"CloudWatch dashboards not available: {e}")
        
        # Standard dashboard configurations
        self.standard_dashboards = self._create_standard_dashboards()
        self.standard_alerts = self._create_standard_alerts()
        
        logger.info("Unified dashboard manager initialized")
    
    def _create_standard_dashboards(self) -> Dict[str, List[DashboardWidget]]:
        """Create standard dashboard configurations for all agents."""
        
        # System Overview Dashboard
        system_overview = [
            # Agent Health Status Row
            DashboardWidget(
                widget_type="metric",
                title="Agent Health Status",
                x=0, y=0, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "HealthStatus", "AgentType", "agent_svea"],
                        [self.namespace, "HealthStatus", "AgentType", "felicias_finance"],
                        [self.namespace, "HealthStatus", "AgentType", "meetmind"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Agent Health Status (0=unhealthy, 1=degraded, 2=healthy)",
                    "yAxis": {"left": {"min": 0, "max": 2}}
                }
            ),
            
            # MCP Call Success Rate Row
            DashboardWidget(
                widget_type="metric",
                title="MCP Call Success Rate",
                x=0, y=6, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallSuccess", "AgentType", "agent_svea"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "felicias_finance"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "meetmind"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "MCP Call Success Count"
                }
            ),
            
            # Response Time Row
            DashboardWidget(
                widget_type="metric",
                title="Agent Response Times",
                x=0, y=12, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "AgentResponseTime", "AgentType", "agent_svea"],
                        [self.namespace, "AgentResponseTime", "AgentType", "felicias_finance"],
                        [self.namespace, "AgentResponseTime", "AgentType", "meetmind"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Average Response Time (ms)",
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "SLA Target (5s)",
                                "value": 5000
                            }
                        ]
                    }
                }
            ),
            
            # Error Rate Row
            DashboardWidget(
                widget_type="metric",
                title="Error Rates",
                x=0, y=18, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallError", "AgentType", "agent_svea"],
                        [self.namespace, "MCPCallError", "AgentType", "felicias_finance"],
                        [self.namespace, "MCPCallError", "AgentType", "meetmind"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "Error Count",
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "SLA Target (1% error rate)",
                                "value": 10  # Assuming 1000 calls per period
                            }
                        ]
                    }
                }
            )
        ]
        
        # Agent Svea Specific Dashboard
        agent_svea_dashboard = [
            # Swedish ERP Operations
            DashboardWidget(
                widget_type="metric",
                title="Swedish ERP Operations",
                x=0, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallSuccess", "AgentType", "agent_svea", "ToolName", "check_swedish_compliance"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "agent_svea", "ToolName", "validate_bas_account"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "agent_svea", "ToolName", "sync_erp_document"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "ERP Tool Usage"
                }
            ),
            
            # Compliance Check Performance
            DashboardWidget(
                widget_type="metric",
                title="Compliance Check Performance",
                x=6, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallDuration", "AgentType", "agent_svea", "ToolName", "check_swedish_compliance"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Compliance Check Duration (ms)"
                }
            ),
            
            # Circuit Breaker Status
            DashboardWidget(
                widget_type="metric",
                title="Circuit Breaker Status",
                x=0, y=6, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "CircuitBreakerState", "AgentType", "agent_svea", "ServiceName", "erp_service"],
                        [self.namespace, "CircuitBreakerState", "AgentType", "agent_svea", "ServiceName", "compliance_service"]
                    ],
                    "period": 300,
                    "stat": "Maximum",
                    "region": "us-east-1",
                    "title": "Circuit Breaker States (0=closed, 1=open, 2=half-open)"
                }
            )
        ]
        
        # Felicia's Finance Specific Dashboard
        felicias_finance_dashboard = [
            # Financial Operations
            DashboardWidget(
                widget_type="metric",
                title="Financial Operations",
                x=0, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallSuccess", "AgentType", "felicias_finance", "ToolName", "analyze_financial_risk"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "felicias_finance", "ToolName", "execute_crypto_trade"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "felicias_finance", "ToolName", "process_banking_transaction"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "Financial Tool Usage"
                }
            ),
            
            # Trading Performance
            DashboardWidget(
                widget_type="metric",
                title="Trading Performance",
                x=6, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallDuration", "AgentType", "felicias_finance", "ToolName", "execute_crypto_trade"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Crypto Trade Execution Time (ms)"
                }
            ),
            
            # AWS Migration Status
            DashboardWidget(
                widget_type="metric",
                title="AWS Service Health",
                x=0, y=6, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "CircuitBreakerState", "AgentType", "felicias_finance", "ServiceName", "aws_lambda"],
                        [self.namespace, "CircuitBreakerState", "AgentType", "felicias_finance", "ServiceName", "aws_dynamodb"],
                        [self.namespace, "CircuitBreakerState", "AgentType", "felicias_finance", "ServiceName", "aws_s3"]
                    ],
                    "period": 300,
                    "stat": "Maximum",
                    "region": "us-east-1",
                    "title": "AWS Service Circuit Breakers"
                }
            )
        ]
        
        # MeetMind Specific Dashboard
        meetmind_dashboard = [
            # Meeting Intelligence Operations
            DashboardWidget(
                widget_type="metric",
                title="Meeting Intelligence",
                x=0, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "MCPCallSuccess", "AgentType", "meetmind", "ToolName", "generate_meeting_summary"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "meetmind", "ToolName", "extract_financial_topics"],
                        [self.namespace, "MCPCallSuccess", "AgentType", "meetmind", "ToolName", "ingest_result"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "Meeting Tool Usage"
                }
            ),
            
            # Fan-in Logic Performance
            DashboardWidget(
                widget_type="metric",
                title="Fan-in Results Collection",
                x=6, y=0, width=6, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "FanInResults", "SourceAgent", "agent_svea"],
                        [self.namespace, "FanInResults", "SourceAgent", "felicias_finance"]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "Results Collected from Agents"
                }
            ),
            
            # Cross-Agent Workflows
            DashboardWidget(
                widget_type="metric",
                title="Cross-Agent Workflows",
                x=0, y=6, width=12, height=6,
                properties={
                    "metrics": [
                        [self.namespace, "WorkflowDuration", "WorkflowType", "compliance_analysis"],
                        [self.namespace, "WorkflowDuration", "WorkflowType", "financial_analysis"],
                        [self.namespace, "WorkflowDuration", "WorkflowType", "meeting_intelligence"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Workflow Duration (ms)"
                }
            )
        ]
        
        return {
            "system_overview": system_overview,
            "agent_svea": agent_svea_dashboard,
            "felicias_finance": felicias_finance_dashboard,
            "meetmind": meetmind_dashboard
        }
    
    def _create_standard_alerts(self) -> List[AlertRule]:
        """Create standard alert rules for all agents."""
        
        alerts = []
        
        # System-wide alerts
        for agent_type in ["agent_svea", "felicias_finance", "meetmind"]:
            # High response time alert (SLA breach)
            alerts.append(AlertRule(
                name=f"HappyOS-{agent_type}-HighResponseTime",
                metric_name="AgentResponseTime",
                threshold=5000.0,  # 5 seconds
                comparison_operator="GreaterThanThreshold",
                evaluation_periods=2,
                period_seconds=300,
                statistic="Average",
                dimensions={"AgentType": agent_type},
                description=f"High response time detected for {agent_type} (SLA breach)"
            ))
            
            # High error rate alert
            alerts.append(AlertRule(
                name=f"HappyOS-{agent_type}-HighErrorRate",
                metric_name="MCPCallError",
                threshold=10.0,  # More than 10 errors per 5 minutes
                comparison_operator="GreaterThanThreshold",
                evaluation_periods=2,
                period_seconds=300,
                statistic="Sum",
                dimensions={"AgentType": agent_type},
                description=f"High error rate detected for {agent_type}"
            ))
            
            # Agent unhealthy alert
            alerts.append(AlertRule(
                name=f"HappyOS-{agent_type}-Unhealthy",
                metric_name="HealthStatus",
                threshold=1.0,  # Less than degraded (unhealthy = 0)
                comparison_operator="LessThanThreshold",
                evaluation_periods=1,
                period_seconds=300,
                statistic="Average",
                dimensions={"AgentType": agent_type},
                description=f"Agent {agent_type} is unhealthy"
            ))
            
            # Circuit breaker open alert
            alerts.append(AlertRule(
                name=f"HappyOS-{agent_type}-CircuitBreakerOpen",
                metric_name="CircuitBreakerState",
                threshold=0.5,  # Greater than closed (open = 1)
                comparison_operator="GreaterThanThreshold",
                evaluation_periods=1,
                period_seconds=300,
                statistic="Maximum",
                dimensions={"AgentType": agent_type},
                description=f"Circuit breaker opened for {agent_type}"
            ))
        
        # Isolation violation alert (critical)
        alerts.append(AlertRule(
            name="HappyOS-IsolationViolation-Critical",
            metric_name="IsolationViolations",
            threshold=0.0,  # Any violation is critical
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            period_seconds=300,
            statistic="Sum",
            description="Backend.* import isolation violation detected"
        ))
        
        # Cross-agent workflow failure alert
        alerts.append(AlertRule(
            name="HappyOS-WorkflowFailure",
            metric_name="WorkflowSteps",
            threshold=5.0,  # More than 5 failed workflow steps
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=2,
            period_seconds=300,
            statistic="Sum",
            dimensions={"Status": "error"},
            description="High number of workflow step failures"
        ))
        
        # Fan-in logic failure alert (MeetMind specific)
        alerts.append(AlertRule(
            name="HappyOS-FanInFailure",
            metric_name="FanInResults",
            threshold=2.0,  # More than 2 failed fan-in operations
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=2,
            period_seconds=300,
            statistic="Sum",
            dimensions={"Status": "error"},
            description="Fan-in result collection failures in MeetMind"
        ))
        
        return alerts
    
    async def create_dashboard(self, dashboard_name: str, 
                             dashboard_type: str = "system_overview") -> bool:
        """Create a unified dashboard in CloudWatch."""
        if not self.cloudwatch:
            logger.warning("CloudWatch not available - cannot create dashboard")
            return False
        
        try:
            # Get dashboard configuration
            widgets = self.standard_dashboards.get(dashboard_type, [])
            if not widgets:
                logger.error(f"Unknown dashboard type: {dashboard_type}")
                return False
            
            # Convert widgets to CloudWatch format
            dashboard_body = {
                "widgets": [widget.to_cloudwatch_format() for widget in widgets]
            }
            
            # Create dashboard
            await self.cloudwatch.client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            logger.info(f"Created dashboard: {dashboard_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create dashboard {dashboard_name}: {e}")
            return False
    
    async def create_all_standard_dashboards(self) -> Dict[str, bool]:
        """Create all standard dashboards."""
        results = {}
        
        dashboard_configs = [
            ("HappyOS-System-Overview", "system_overview"),
            ("HappyOS-Agent-Svea", "agent_svea"),
            ("HappyOS-Felicias-Finance", "felicias_finance"),
            ("HappyOS-MeetMind", "meetmind")
        ]
        
        for dashboard_name, dashboard_type in dashboard_configs:
            success = await self.create_dashboard(dashboard_name, dashboard_type)
            results[dashboard_name] = success
        
        return results
    
    async def create_alert_rules(self) -> Dict[str, bool]:
        """Create all standard alert rules."""
        if not self.cloudwatch:
            logger.warning("CloudWatch not available - cannot create alerts")
            return {}
        
        results = {}
        
        for alert_rule in self.standard_alerts:
            try:
                # Create CloudWatch alarm
                alarm_config = alert_rule.to_cloudwatch_format(self.namespace)
                
                await self.cloudwatch.client.put_metric_alarm(**alarm_config)
                
                logger.info(f"Created alert rule: {alert_rule.name}")
                results[alert_rule.name] = True
                
            except Exception as e:
                logger.error(f"Failed to create alert rule {alert_rule.name}: {e}")
                results[alert_rule.name] = False
        
        return results
    
    async def setup_unified_monitoring(self) -> Dict[str, Any]:
        """Setup complete unified monitoring (dashboards + alerts)."""
        logger.info("Setting up unified monitoring for HappyOS agents")
        
        # Create dashboards
        dashboard_results = await self.create_all_standard_dashboards()
        
        # Create alert rules
        alert_results = await self.create_alert_rules()
        
        # Summary
        setup_summary = {
            "dashboards": {
                "created": len([r for r in dashboard_results.values() if r]),
                "failed": len([r for r in dashboard_results.values() if not r]),
                "details": dashboard_results
            },
            "alerts": {
                "created": len([r for r in alert_results.values() if r]),
                "failed": len([r for r in alert_results.values() if not r]),
                "details": alert_results
            },
            "overall_success": (
                all(dashboard_results.values()) and 
                all(alert_results.values())
            )
        }
        
        logger.info(f"Unified monitoring setup completed: {setup_summary}")
        return setup_summary
    
    def get_dashboard_url(self, dashboard_name: str, region: str = "us-east-1") -> str:
        """Get CloudWatch dashboard URL."""
        return (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#dashboards:name={dashboard_name}"
        )
    
    def get_alert_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Get all alert thresholds for documentation."""
        thresholds = {}
        
        for alert in self.standard_alerts:
            thresholds[alert.name] = {
                "metric": alert.metric_name,
                "threshold": alert.threshold,
                "operator": alert.comparison_operator,
                "evaluation_periods": alert.evaluation_periods,
                "description": alert.description
            }
        
        return thresholds


# Global dashboard manager instance
_dashboard_manager: Optional[UnifiedDashboardManager] = None


def get_dashboard_manager(namespace: str = "HappyOS/Agents") -> UnifiedDashboardManager:
    """Get or create unified dashboard manager."""
    global _dashboard_manager
    if _dashboard_manager is None:
        _dashboard_manager = UnifiedDashboardManager(namespace)
    return _dashboard_manager