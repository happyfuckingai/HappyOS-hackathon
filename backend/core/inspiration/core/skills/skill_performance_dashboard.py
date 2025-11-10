"""
🔍 CENTRALIZED SKILL PERFORMANCE DASHBOARD

Collects, analyzes, and provides unified access to performance metrics across all skill components.
Includes performance alerting, resource usage tracking, and predictive analytics.

Components monitored:
- Skill Registry (load times, error counts, registry status)
- Skill Generator (generation metrics, timing)
- Intelligent Skill System (execution metrics, learning analytics)

Features:
- Real-time performance monitoring
- Performance degradation alerts
- Resource usage tracking (CPU/memory)
- Predictive performance forecasting
- Comprehensive metrics aggregation
"""

import asyncio
import logging
import psutil
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import threading
import time
from collections import deque, defaultdict
import warnings

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of performance metrics."""
    SUCCESS_RATE = "success_rate"
    EXECUTION_TIME = "execution_time"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    USER_SATISFACTION = "user_satisfaction"
    ADAPTATION_SCORE = "adaptation_score"


@dataclass
class PerformanceAlert:
    """Performance alert configuration."""
    metric_name: str
    threshold: float
    severity: AlertSeverity
    condition: str  # 'above', 'below', 'equals'
    description: str
    enabled: bool = True
    cooldown_minutes: int = 15  # Minimum time between alerts
    last_triggered: Optional[datetime] = None


@dataclass
class ResourceMetrics:
    """Resource usage metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    disk_usage_percent: float = 0.0
    network_connections: int = 0
    thread_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PerformancePrediction:
    """Predicted performance metrics."""
    metric_name: str
    current_value: float
    predicted_value: float
    confidence: float
    trend: str  # 'improving', 'stable', 'degrading'
    timeframe_hours: int
    prediction_timestamp: datetime = field(default_factory=datetime.utcnow)


class SkillPerformanceDashboard:
    """
    Centralized dashboard for monitoring skill performance across all components.
    """

    def __init__(self):
        # Component references (will be injected)
        self.skill_registry = None
        self.skill_generator = None
        self.intelligent_skill_system = None

        # Performance data storage
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.resource_history: deque = deque(maxlen=500)
        self.predictions: Dict[str, List[PerformancePrediction]] = defaultdict(list)

        # Alert system
        self.alerts: Dict[str, PerformanceAlert] = {}
        self.active_alerts: List[Dict[str, Any]] = []
        self.alert_handlers: List[Callable] = []

        # Monitoring configuration
        self.monitoring_enabled = True
        self.collection_interval_seconds = 30
        self.resource_monitoring_enabled = True
        self.predictive_analytics_enabled = True

        # Performance thresholds
        self._setup_default_alerts()

        # Background monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_lock = asyncio.Lock()

        logger.info("Skill Performance Dashboard initialized")

    def _setup_default_alerts(self):
        """Setup default performance alerts."""
        default_alerts = [
            PerformanceAlert(
                metric_name="skill_registry.error_rate",
                threshold=0.1,  # 10% error rate
                severity=AlertSeverity.HIGH,
                condition="above",
                description="Skill registry error rate is too high"
            ),
            PerformanceAlert(
                metric_name="intelligent_skill_system.success_rate",
                threshold=0.7,  # Below 70% success rate
                severity=AlertSeverity.MEDIUM,
                condition="below",
                description="Intelligent skill system success rate is low"
            ),
            PerformanceAlert(
                metric_name="resource.cpu_percent",
                threshold=80.0,  # CPU usage above 80%
                severity=AlertSeverity.MEDIUM,
                condition="above",
                description="High CPU usage detected"
            ),
            PerformanceAlert(
                metric_name="resource.memory_percent",
                threshold=85.0,  # Memory usage above 85%
                severity=AlertSeverity.HIGH,
                condition="above",
                description="High memory usage detected"
            ),
            PerformanceAlert(
                metric_name="skill_execution.average_time",
                threshold=10.0,  # Execution time above 10 seconds
                severity=AlertSeverity.MEDIUM,
                condition="above",
                description="Skill execution time is too high"
            )
        ]

        for alert in default_alerts:
            self.alerts[alert.metric_name] = alert

    async def initialize(self, skill_registry=None, skill_generator=None,
                        intelligent_skill_system=None):
        """Initialize dashboard with component references."""
        self.skill_registry = skill_registry
        self.skill_generator = skill_generator
        self.intelligent_skill_system = intelligent_skill_system

        logger.info("Skill Performance Dashboard initialized with components")

        # Start background monitoring if enabled
        if self.monitoring_enabled:
            await self.start_monitoring()

    async def start_monitoring(self):
        """Start background performance monitoring."""
        async with self._monitoring_lock:
            if self.monitoring_task and not self.monitoring_task.done():
                logger.warning("Monitoring already running")
                return

            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Background performance monitoring started")

    async def stop_monitoring(self):
        """Stop background performance monitoring."""
        async with self._monitoring_lock:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            logger.info("Background performance monitoring stopped")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await self._collect_metrics()
                if self.resource_monitoring_enabled:
                    await self._collect_resource_metrics()
                await self._check_alerts()
                if self.predictive_analytics_enabled:
                    await self._generate_predictions()
                await asyncio.sleep(self.collection_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.collection_interval_seconds)

    async def _collect_metrics(self):
        """Collect performance metrics from all components."""
        timestamp = datetime.utcnow()

        try:
            # Collect from Skill Registry
            if self.skill_registry:
                registry_metrics = await self._collect_skill_registry_metrics()
                for metric_name, value in registry_metrics.items():
                    self.metric_history[metric_name].append({
                        'value': value,
                        'timestamp': timestamp
                    })

            # Collect from Skill Generator
            if self.skill_generator:
                generator_metrics = await self._collect_skill_generator_metrics()
                for metric_name, value in generator_metrics.items():
                    self.metric_history[metric_name].append({
                        'value': value,
                        'timestamp': timestamp
                    })

            # Collect from Intelligent Skill System
            if self.intelligent_skill_system:
                iss_metrics = await self._collect_intelligent_skill_system_metrics()
                for metric_name, value in iss_metrics.items():
                    self.metric_history[metric_name].append({
                        'value': value,
                        'timestamp': timestamp
                    })

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def _collect_skill_registry_metrics(self) -> Dict[str, float]:
        """Collect metrics from skill registry."""
        metrics = {}

        try:
            if hasattr(self.skill_registry, 'get_registry_status'):
                status = self.skill_registry.get_registry_status()

                metrics['skill_registry.total_skills'] = status.get('total_skills', 0)
                metrics['skill_registry.total_errors'] = status.get('total_errors', 0)
                metrics['skill_registry.average_load_time'] = status.get('average_load_time', 0.0)
                metrics['skill_registry.error_rate'] = (
                    status.get('total_errors', 0) / max(status.get('total_skills', 1), 1)
                )

                # Individual skill metrics
                if hasattr(self.skill_registry, 'skills'):
                    skill_count = 0
                    total_load_time = 0.0
                    total_errors = 0

                    for skill_id, skill in self.skill_registry.skills.items():
                        if hasattr(self.skill_registry, 'get_skill_info'):
                            skill_info = self.skill_registry.get_skill_info(skill_id)
                            if skill_info:
                                load_time = skill_info.get('load_time', 0.0)
                                error_count = skill_info.get('error_count', 0)

                                total_load_time += load_time
                                total_errors += error_count
                                skill_count += 1

                    if skill_count > 0:
                        metrics['skill_registry.avg_skill_load_time'] = total_load_time / skill_count
                        metrics['skill_registry.skill_error_rate'] = total_errors / skill_count

        except Exception as e:
            logger.error(f"Error collecting skill registry metrics: {e}")

        return metrics

    async def _collect_skill_generator_metrics(self) -> Dict[str, float]:
        """Collect metrics from skill generator."""
        metrics = {}

        try:
            if hasattr(self.skill_generator, 'generation_count'):
                metrics['skill_generator.generation_count'] = self.skill_generator.generation_count

            # Add more generator metrics as they become available
            metrics['skill_generator.active'] = 1.0 if self.skill_generator else 0.0

        except Exception as e:
            logger.error(f"Error collecting skill generator metrics: {e}")

        return metrics

    async def _collect_intelligent_skill_system_metrics(self) -> Dict[str, Any]:
        """Collect metrics from intelligent skill system."""
        metrics = {}

        try:
            if hasattr(self.intelligent_skill_system, 'get_skill_statistics'):
                stats = self.intelligent_skill_system.get_skill_statistics()

                metrics['intelligent_skill_system.total_skills'] = stats.get('total_skills', 0)
                metrics['intelligent_skill_system.active_skills'] = stats.get('active_skills', 0)
                metrics['intelligent_skill_system.average_success_rate'] = stats.get('average_success_rate', 0.0)
                metrics['intelligent_skill_system.average_user_satisfaction'] = stats.get('average_user_satisfaction', 0.0)
                metrics['intelligent_skill_system.total_executions'] = stats.get('total_executions', 0)

                # Learning metrics
                learning_stats = stats.get('learning_statistics', {})
                metrics['intelligent_skill_system.total_learning_executions'] = learning_stats.get('total_executions', 0)

                # Top performing skills metrics
                top_skills = stats.get('top_performing_skills', [])
                if top_skills:
                    avg_top_score = np.mean([skill.get('overall_score', 0) for skill in top_skills])
                    metrics['intelligent_skill_system.avg_top_skill_score'] = avg_top_score

            # Individual skill execution metrics
            if hasattr(self.intelligent_skill_system, 'skills'):
                skill_execution_times = []
                skill_success_rates = []

                for skill_id, skill in self.intelligent_skill_system.skills.items():
                    if hasattr(skill, 'metrics'):
                        skill_execution_times.append(skill.metrics.average_execution_time)
                        skill_success_rates.append(skill.metrics.success_rate)

                if skill_execution_times:
                    metrics['skill_execution.average_time'] = np.mean(skill_execution_times)
                    metrics['skill_execution.median_time'] = np.median(skill_execution_times)

                if skill_success_rates:
                    metrics['skill_execution.average_success_rate'] = np.mean(skill_success_rates)

        except Exception as e:
            logger.error(f"Error collecting intelligent skill system metrics: {e}")

        return metrics

    async def _collect_resource_metrics(self):
        """Collect system resource usage metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / (1024 * 1024)

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent

            # Network connections
            network_connections = len(psutil.net_connections())

            # Thread count
            thread_count = threading.active_count()

            resource_metrics = ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_mb,
                disk_usage_percent=disk_usage_percent,
                network_connections=network_connections,
                thread_count=thread_count
            )

            self.resource_history.append(resource_metrics)

            # Store in metric history for alerting
            timestamp = datetime.utcnow()
            self.metric_history['resource.cpu_percent'].append({
                'value': cpu_percent,
                'timestamp': timestamp
            })
            self.metric_history['resource.memory_percent'].append({
                'value': memory_percent,
                'timestamp': timestamp
            })
            self.metric_history['resource.memory_mb'].append({
                'value': memory_mb,
                'timestamp': timestamp
            })

        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")

    async def _check_alerts(self):
        """Check performance alerts and trigger if necessary."""
        try:
            current_time = datetime.utcnow()

            for alert_name, alert in self.alerts.items():
                if not alert.enabled:
                    continue

                # Check cooldown period
                if alert.last_triggered:
                    time_since_last = (current_time - alert.last_triggered).total_seconds() / 60
                    if time_since_last < alert.cooldown_minutes:
                        continue

                # Get current metric value
                if alert_name in self.metric_history:
                    history = list(self.metric_history[alert_name])
                    if history:
                        current_value = history[-1]['value']

                        # Check alert condition
                        should_trigger = False

                        if alert.condition == 'above' and current_value > alert.threshold:
                            should_trigger = True
                        elif alert.condition == 'below' and current_value < alert.threshold:
                            should_trigger = True
                        elif alert.condition == 'equals' and abs(current_value - alert.threshold) < 0.01:
                            should_trigger = True

                        if should_trigger:
                            await self._trigger_alert(alert, current_value)
                            alert.last_triggered = current_time

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def _trigger_alert(self, alert: PerformanceAlert, current_value: float):
        """Trigger a performance alert."""
        try:
            alert_data = {
                'alert_name': alert.metric_name,
                'severity': alert.severity.value,
                'description': alert.description,
                'current_value': current_value,
                'threshold': alert.threshold,
                'condition': alert.condition,
                'timestamp': datetime.utcnow().isoformat()
            }

            self.active_alerts.append(alert_data)

            # Keep only recent alerts
            if len(self.active_alerts) > 100:
                self.active_alerts = self.active_alerts[-50:]

            # Call alert handlers
            for handler in self.alert_handlers:
                try:
                    await handler(alert_data)
                except Exception as e:
                    logger.error(f"Error in alert handler: {e}")

            logger.warning(f"Performance Alert Triggered: {alert.metric_name} - {alert.description}")

        except Exception as e:
            logger.error(f"Error triggering alert: {e}")

    async def _generate_predictions(self):
        """Generate predictive analytics for performance metrics."""
        try:
            for metric_name, history in self.metric_history.items():
                if len(history) < 10:  # Need minimum data points
                    continue

                await self._predict_metric_performance(metric_name, history)

        except Exception as e:
            logger.error(f"Error generating predictions: {e}")

    async def _predict_metric_performance(self, metric_name: str, history: deque):
        """Predict future performance for a specific metric."""
        try:
            # Extract values and timestamps
            values = [entry['value'] for entry in history]
            timestamps = [entry['timestamp'] for entry in history]

            if len(values) < 10:
                return

            # Simple linear regression for trend prediction
            x = np.arange(len(values))
            y = np.array(values)

            # Calculate trend
            if len(x) > 1:
                slope, intercept = np.polyfit(x, y, 1)
                trend = 'improving' if slope > 0.01 else 'degrading' if slope < -0.01 else 'stable'

                # Predict next value (1 hour ahead)
                next_value = slope * len(x) + intercept
                current_value = values[-1]

                # Calculate confidence based on data consistency
                std_dev = np.std(y)
                mean_val = np.mean(y)
                confidence = max(0.1, min(1.0, 1.0 - (std_dev / max(mean_val, 1.0))))

                prediction = PerformancePrediction(
                    metric_name=metric_name,
                    current_value=current_value,
                    predicted_value=next_value,
                    confidence=confidence,
                    trend=trend,
                    timeframe_hours=1
                )

                # Store prediction
                self.predictions[metric_name].append(prediction)

                # Keep only recent predictions
                if len(self.predictions[metric_name]) > 10:
                    self.predictions[metric_name] = self.predictions[metric_name][-5:]

        except Exception as e:
            logger.error(f"Error predicting metric {metric_name}: {e}")

    def add_alert_handler(self, handler: Callable):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)

    def remove_alert_handler(self, handler: Callable):
        """Remove an alert handler function."""
        if handler in self.alert_handlers:
            self.alert_handlers.remove(handler)

    def configure_alert(self, alert_name: str, threshold: float = None,
                       severity: AlertSeverity = None, enabled: bool = None):
        """Configure an existing alert."""
        if alert_name in self.alerts:
            alert = self.alerts[alert_name]
            if threshold is not None:
                alert.threshold = threshold
            if severity is not None:
                alert.severity = severity
            if enabled is not None:
                alert.enabled = enabled

    def add_custom_alert(self, metric_name: str, threshold: float,
                        severity: AlertSeverity, condition: str, description: str):
        """Add a custom performance alert."""
        alert = PerformanceAlert(
            metric_name=metric_name,
            threshold=threshold,
            severity=severity,
            condition=condition,
            description=description
        )
        self.alerts[metric_name] = alert

    # UNIFIED ACCESS METHODS

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current values of all tracked metrics."""
        current_metrics = {}

        for metric_name, history in self.metric_history.items():
            if history:
                current_metrics[metric_name] = history[-1]['value']

        return current_metrics

    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric."""
        if metric_name not in self.metric_history:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        history = [
            entry for entry in self.metric_history[metric_name]
            if entry['timestamp'] >= cutoff_time
        ]

        return history

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'current_metrics': self.get_current_metrics(),
            'active_alerts': self.active_alerts[-10:],  # Last 10 alerts
            'system_health': self._calculate_system_health(),
            'predictions': {}
        }

        # Add recent predictions
        for metric_name, predictions in self.predictions.items():
            if predictions:
                latest_prediction = predictions[-1]
                summary['predictions'][metric_name] = {
                    'current_value': latest_prediction.current_value,
                    'predicted_value': latest_prediction.predicted_value,
                    'confidence': latest_prediction.confidence,
                    'trend': latest_prediction.trend
                }

        return summary

    def _calculate_system_health(self) -> Dict[str, Any]:
        """Calculate overall system health score."""
        health_score = 1.0
        issues = []

        try:
            current_metrics = self.get_current_metrics()

            # Check for critical issues
            if current_metrics.get('skill_registry.error_rate', 0) > 0.2:
                health_score *= 0.7
                issues.append("High skill registry error rate")

            if current_metrics.get('resource.memory_percent', 0) > 90:
                health_score *= 0.6
                issues.append("Critical memory usage")

            if current_metrics.get('intelligent_skill_system.average_success_rate', 1.0) < 0.5:
                health_score *= 0.8
                issues.append("Low skill success rate")

            # Check for active alerts
            critical_alerts = [alert for alert in self.active_alerts
                             if alert['severity'] in ['critical', 'high']]

            if critical_alerts:
                health_score *= 0.9
                issues.append(f"{len(critical_alerts)} critical alerts active")

        except Exception as e:
            logger.error(f"Error calculating system health: {e}")
            health_score = 0.5
            issues.append("Health calculation error")

        return {
            'health_score': health_score,
            'status': 'healthy' if health_score > 0.8 else 'warning' if health_score > 0.6 else 'critical',
            'issues': issues
        }

    def get_resource_usage_report(self, hours: int = 1) -> Dict[str, Any]:
        """Get resource usage report."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        relevant_metrics = [
            metric for metric in self.resource_history
            if metric.timestamp >= cutoff_time
        ]

        if not relevant_metrics:
            return {'error': 'No resource data available'}

        cpu_usage = [m.cpu_percent for m in relevant_metrics]
        memory_usage = [m.memory_percent for m in relevant_metrics]
        memory_mb = [m.memory_mb for m in relevant_metrics]

        return {
            'period_hours': hours,
            'data_points': len(relevant_metrics),
            'cpu': {
                'average': np.mean(cpu_usage),
                'max': np.max(cpu_usage),
                'min': np.min(cpu_usage),
                'current': cpu_usage[-1] if cpu_usage else 0
            },
            'memory': {
                'average_percent': np.mean(memory_usage),
                'max_percent': np.max(memory_usage),
                'min_percent': np.min(memory_usage),
                'current_percent': memory_usage[-1] if memory_usage else 0,
                'average_mb': np.mean(memory_mb),
                'current_mb': memory_mb[-1] if memory_mb else 0
            },
            'summary': {
                'high_cpu_usage': any(cpu > 80 for cpu in cpu_usage),
                'high_memory_usage': any(mem > 85 for mem in memory_usage)
            }
        }

    def get_skill_performance_report(self, skill_id: str = None) -> Dict[str, Any]:
        """Get detailed skill performance report."""
        try:
            if skill_id and self.intelligent_skill_system:
                # Specific skill report
                if skill_id in self.intelligent_skill_system.skills:
                    skill = self.intelligent_skill_system.skills[skill_id]
                    return {
                        'skill_id': skill_id,
                        'name': skill.name,
                        'category': skill.category.value,
                        'complexity': skill.complexity.value,
                        'status': skill.status.value,
                        'metrics': {
                            'success_rate': skill.metrics.success_rate,
                            'average_execution_time': skill.metrics.average_execution_time,
                            'user_satisfaction': skill.metrics.user_satisfaction,
                            'total_executions': skill.metrics.total_executions,
                            'usage_frequency': skill.metrics.usage_frequency,
                            'error_rate': skill.metrics.error_rate,
                            'adaptation_score': skill.metrics.adaptation_score,
                            'confidence': skill.metrics.confidence
                        }
                    }
                else:
                    return {'error': f'Skill {skill_id} not found'}

            # Overall skills report
            if self.intelligent_skill_system:
                stats = self.intelligent_skill_system.get_skill_statistics()
                return stats
            else:
                return {'error': 'Intelligent skill system not available'}

        except Exception as e:
            logger.error(f"Error generating skill performance report: {e}")
            return {'error': str(e)}

    def export_metrics(self, format: str = 'json') -> str:
        """Export all metrics data."""
        try:
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'current_metrics': self.get_current_metrics(),
                'metric_history': dict(self.metric_history),
                'resource_history': [vars(m) for m in self.resource_history],
                'active_alerts': self.active_alerts,
                'predictions': {
                    metric: [vars(p) for p in predictions]
                    for metric, predictions in self.predictions.items()
                }
            }

            if format == 'json':
                return json.dumps(data, indent=2, default=str)
            else:
                return json.dumps(data, default=str)

        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return f'{{"error": "{str(e)}"}}'

    async def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old performance data."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)

            # Clean metric history
            for metric_name, history in self.metric_history.items():
                self.metric_history[metric_name] = deque(
                    [entry for entry in history if entry['timestamp'] >= cutoff_time],
                    maxlen=1000
                )

            # Clean resource history
            self.resource_history = deque(
                [metric for metric in self.resource_history if metric.timestamp >= cutoff_time],
                maxlen=500
            )

            # Clean predictions
            for metric_name, predictions in self.predictions.items():
                self.predictions[metric_name] = [
                    p for p in predictions if p.prediction_timestamp >= cutoff_time
                ]

            # Clean old alerts
            self.active_alerts = [
                alert for alert in self.active_alerts
                if (datetime.utcnow() - datetime.fromisoformat(alert['timestamp'])).days < days_to_keep
            ]

            logger.info(f"Cleaned up old performance data older than {days_to_keep} days")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")


# Global dashboard instance
_performance_dashboard: Optional[SkillPerformanceDashboard] = None


def get_skill_performance_dashboard() -> SkillPerformanceDashboard:
    """Get global skill performance dashboard instance."""
    global _performance_dashboard

    if _performance_dashboard is None:
        _performance_dashboard = SkillPerformanceDashboard()

    return _performance_dashboard


async def initialize_performance_dashboard(skill_registry=None, skill_generator=None,
                                         intelligent_skill_system=None) -> SkillPerformanceDashboard:
    """Initialize the global performance dashboard."""
    dashboard = get_skill_performance_dashboard()
    await dashboard.initialize(skill_registry, skill_generator, intelligent_skill_system)
    return dashboard


# Convenience functions for easy access
async def get_current_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics."""
    dashboard = get_skill_performance_dashboard()
    return dashboard.get_current_metrics()


async def get_performance_summary() -> Dict[str, Any]:
    """Get comprehensive performance summary."""
    dashboard = get_skill_performance_dashboard()
    return dashboard.get_performance_summary()


async def get_resource_usage_report(hours: int = 1) -> Dict[str, Any]:
    """Get resource usage report."""
    dashboard = get_skill_performance_dashboard()
    return dashboard.get_resource_usage_report(hours)


async def get_skill_performance_report(skill_id: str = None) -> Dict[str, Any]:
    """Get skill performance report."""
    dashboard = get_skill_performance_dashboard()
    return dashboard.get_skill_performance_report(skill_id)


if __name__ == "__main__":
    # Example usage
    async def main():
        dashboard = get_skill_performance_dashboard()

        # Simulate some component initialization
        class MockSkillRegistry:
            def get_registry_status(self):
                return {
                    'total_skills': 15,
                    'total_errors': 2,
                    'average_load_time': 0.5,
                    'total_metadata': 20
                }

        mock_registry = MockSkillRegistry()
        await dashboard.initialize(skill_registry=mock_registry)

        # Get summary
        summary = dashboard.get_performance_summary()
        print("Performance Summary:")
        print(json.dumps(summary, indent=2, default=str))

    asyncio.run(main())