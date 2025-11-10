"""
🎯 STATE ANALYTICS - Conversation State Analytics and Monitoring

Advanced analytics system for conversation states:
- Performance metrics and trends
- Usage patterns analysis
- Health monitoring and alerting
- Predictive analytics for optimization
- Comprehensive reporting and dashboards
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass, field

from .conversation_state_repository import ConversationStateRepository
from .enhanced_models import EnhancedConversationContext

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsSnapshot:
    """Snapshot of analytics data at a specific point in time."""
    timestamp: datetime
    total_conversations: int = 0
    active_conversations: int = 0
    compressed_conversations: int = 0
    corrupted_conversations: int = 0
    average_conversation_size: float = 0.0
    average_compression_ratio: float = 1.0
    total_storage_used: int = 0
    storage_saved_by_compression: int = 0
    conversations_by_state: Dict[str, int] = field(default_factory=dict)
    access_patterns: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTrend:
    """Trend analysis for conversation patterns."""
    period: str  # "hourly", "daily", "weekly"
    metric: str
    values: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    trend_direction: str = "stable"  # "increasing", "decreasing", "stable"
    change_percentage: float = 0.0


class StateAnalytics:
    """
    Comprehensive analytics system for conversation states.

    Features:
    - Real-time metrics collection
    - Trend analysis and forecasting
    - Performance monitoring
    - Health alerts and notifications
    - Usage pattern analysis
    - Predictive optimization
    """

    def __init__(self, repository: ConversationStateRepository,
                 enable_real_time: bool = True,
                 analytics_interval_minutes: int = 15):
        """
        Initialize the state analytics system.

        Args:
            repository: Conversation state repository
            enable_real_time: Whether to enable real-time analytics
            analytics_interval_minutes: Interval for analytics updates
        """
        self.repository = repository
        self.enable_real_time = enable_real_time
        self.analytics_interval_minutes = analytics_interval_minutes

        # Analytics data
        self.current_snapshot: Optional[AnalyticsSnapshot] = None
        self.historical_snapshots: List[AnalyticsSnapshot] = []
        self.trends: Dict[str, ConversationTrend] = {}

        # Alert thresholds
        self.alert_thresholds = {
            'corruption_rate': 0.05,  # 5% corruption rate
            'compression_ratio_min': 1.5,  # Minimum expected compression ratio
            'storage_growth_rate': 0.1,  # 10% daily growth
            'average_response_time': 2.0,  # 2 seconds max
            'memory_usage_percent': 85.0  # 85% memory usage
        }

        # Alert callbacks
        self.alert_callbacks: List[callable] = []

        # Background tasks
        self._analytics_task: Optional[asyncio.Task] = None
        self._alert_monitor_task: Optional[asyncio.Task] = None

        # Analytics cache
        self._cache = {}
        self._cache_timestamp = None
        self._cache_ttl_minutes = 5

        logger.info("Initialized StateAnalytics")

    async def start_analytics(self):
        """Start the analytics system."""
        if self.enable_real_time:
            self._analytics_task = asyncio.create_task(self._analytics_worker())
            self._alert_monitor_task = asyncio.create_task(self._alert_monitor())

        # Generate initial snapshot
        await self._generate_snapshot()

        logger.info("StateAnalytics started")

    async def stop_analytics(self):
        """Stop the analytics system."""
        if self._analytics_task:
            self._analytics_task.cancel()
            try:
                await self._analytics_task
            except asyncio.CancelledError:
                pass

        if self._alert_monitor_task:
            self._alert_monitor_task.cancel()
            try:
                await self._alert_monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("StateAnalytics stopped")

    async def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current analytics metrics.

        Returns:
            Dictionary containing current metrics
        """
        try:
            # Check cache
            if self._is_cache_valid():
                return self._cache

            # Generate fresh metrics
            metrics = await self._calculate_current_metrics()

            # Update cache
            self._cache = metrics
            self._cache_timestamp = datetime.utcnow()

            return metrics

        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {'error': str(e)}

    async def _calculate_current_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive current metrics."""
        try:
            # Get basic counts
            total_conversations = await self.repository.count()
            compressed_count = await self.repository._count_compressed()
            average_compression_ratio = await self.repository._calculate_average_compression_ratio()

            # Get repository performance metrics
            repo_metrics = await self.repository.get_performance_metrics()

            # Calculate storage metrics
            storage_metrics = await self._calculate_storage_metrics()

            # Get state distribution
            state_distribution = await self._calculate_state_distribution()

            # Calculate performance indicators
            performance_indicators = await self._calculate_performance_indicators()

            # Get trend indicators
            trend_indicators = await self._calculate_trend_indicators()

            return {
                'timestamp': datetime.utcnow().isoformat(),
                'conversation_metrics': {
                    'total_conversations': total_conversations,
                    'compressed_conversations': compressed_count,
                    'compression_ratio': round(average_compression_ratio, 2),
                    'active_conversations': await self._count_active_conversations(),
                    'corrupted_conversations': await self._count_corrupted_conversations()
                },
                'storage_metrics': storage_metrics,
                'state_distribution': state_distribution,
                'performance_indicators': performance_indicators,
                'trend_indicators': trend_indicators,
                'repository_metrics': repo_metrics,
                'health_score': await self._calculate_health_score()
            }

        except Exception as e:
            logger.error(f"Error calculating current metrics: {e}")
            return {'error': str(e)}

    async def _calculate_storage_metrics(self) -> Dict[str, Any]:
        """Calculate storage usage metrics."""
        try:
            # Get total storage used
            query = "SELECT SUM(size_bytes), SUM(length(compressed_state)) FROM conversation_states"
            result = await self.repository._execute_query_with_retry(query)

            if result and result[0]:
                original_size = result[0][0] or 0
                compressed_size = result[0][1] or 0

                return {
                    'total_original_size_bytes': original_size,
                    'total_compressed_size_bytes': compressed_size,
                    'total_storage_saved_bytes': original_size - compressed_size,
                    'storage_efficiency_percent': round((compressed_size / max(original_size, 1)) * 100, 2),
                    'average_conversation_size_bytes': round(original_size / max(await self.repository.count(), 1), 2)
                }

            return {
                'total_original_size_bytes': 0,
                'total_compressed_size_bytes': 0,
                'total_storage_saved_bytes': 0,
                'storage_efficiency_percent': 0.0,
                'average_conversation_size_bytes': 0.0
            }

        except Exception as e:
            logger.error(f"Error calculating storage metrics: {e}")
            return {'error': str(e)}

    async def _calculate_state_distribution(self) -> Dict[str, int]:
        """Calculate distribution of conversations by state."""
        try:
            query = "SELECT state, COUNT(*) FROM conversation_states GROUP BY state"
            result = await self.repository._execute_query_with_retry(query)

            distribution = {}
            for row in result:
                state_name = row[0]
                count = row[1]
                distribution[state_name] = count

            return distribution

        except Exception as e:
            logger.error(f"Error calculating state distribution: {e}")
            return {'error': str(e)}

    async def _calculate_performance_indicators(self) -> Dict[str, Any]:
        """Calculate key performance indicators."""
        try:
            # Access frequency analysis
            query = """
            SELECT
                AVG(json_extract(access_metrics, '$.total_accesses')) as avg_accesses,
                AVG(json_extract(access_metrics, '$.access_frequency_score')) as avg_frequency,
                AVG(json_extract(access_metrics, '$.relevance_score')) as avg_relevance
            FROM conversation_states
            """
            result = await self.repository._execute_query_with_retry(query)

            if result and result[0]:
                row = result[0]
                return {
                    'average_accesses_per_conversation': round(row[0] or 0, 2),
                    'average_access_frequency_score': round(row[1] or 0, 2),
                    'average_relevance_score': round(row[2] or 0, 2),
                    'performance_score': round(((row[1] or 0) + (row[2] or 0)) / 2, 2)
                }

            return {
                'average_accesses_per_conversation': 0.0,
                'average_access_frequency_score': 0.0,
                'average_relevance_score': 0.0,
                'performance_score': 0.0
            }

        except Exception as e:
            logger.error(f"Error calculating performance indicators: {e}")
            return {'error': str(e)}

    async def _calculate_trend_indicators(self) -> Dict[str, Any]:
        """Calculate trend indicators."""
        try:
            if len(self.historical_snapshots) < 2:
                return {'insufficient_data': True}

            # Calculate trends from recent snapshots
            recent_snapshots = self.historical_snapshots[-10:]  # Last 10 snapshots

            conversation_trend = self._calculate_trend([s.total_conversations for s in recent_snapshots])
            compression_trend = self._calculate_trend([s.average_compression_ratio for s in recent_snapshots])
            storage_trend = self._calculate_trend([s.total_storage_used for s in recent_snapshots])

            return {
                'conversation_growth_trend': conversation_trend,
                'compression_efficiency_trend': compression_trend,
                'storage_growth_trend': storage_trend,
                'trend_period_days': len(recent_snapshots) * (self.analytics_interval_minutes / (24 * 60))
            }

        except Exception as e:
            logger.error(f"Error calculating trend indicators: {e}")
            return {'error': str(e)}

    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """Calculate trend for a series of values."""
        try:
            if len(values) < 2:
                return {'direction': 'stable', 'change_percent': 0.0}

            # Simple linear trend
            if len(values) >= 2:
                first_value = values[0]
                last_value = values[-1]

                if first_value == 0:
                    change_percent = 0.0
                else:
                    change_percent = ((last_value - first_value) / first_value) * 100

                if change_percent > 5:
                    direction = 'increasing'
                elif change_percent < -5:
                    direction = 'decreasing'
                else:
                    direction = 'stable'

                return {
                    'direction': direction,
                    'change_percent': round(change_percent, 2),
                    'first_value': first_value,
                    'last_value': last_value
                }

            return {'direction': 'stable', 'change_percent': 0.0}

        except Exception:
            return {'direction': 'unknown', 'change_percent': 0.0}

    async def _count_active_conversations(self) -> int:
        """Count conversations that have been active recently."""
        try:
            # Active within last 24 hours
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            query = "SELECT COUNT(*) FROM conversation_states WHERE last_activity > ?"
            result = await self.repository._execute_query_with_retry(query, (cutoff,))

            return result[0][0] if result else 0

        except Exception:
            return 0

    async def _count_corrupted_conversations(self) -> int:
        """Count conversations marked as corrupted."""
        try:
            query = "SELECT COUNT(*) FROM conversation_states WHERE json_extract(persistence_metadata, '$.corruption_detected') = 1"
            result = await self.repository._execute_query_with_retry(query)

            return result[0][0] if result else 0

        except Exception:
            return 0

    async def _calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        try:
            metrics = await self.get_current_metrics()

            if 'error' in metrics:
                return 0.0

            health_factors = []

            # Factor 1: Corruption rate (0-20 points)
            corruption_rate = metrics['conversation_metrics']['corrupted_conversations'] / max(metrics['conversation_metrics']['total_conversations'], 1)
            corruption_score = max(0, 20 * (1 - corruption_rate / 0.1))  # Max 10% corruption allowed
            health_factors.append(corruption_score)

            # Factor 2: Compression efficiency (0-20 points)
            compression_ratio = metrics['conversation_metrics']['compression_ratio']
            compression_score = min(20, compression_ratio * 5)  # 4:1 ratio = 20 points
            health_factors.append(compression_score)

            # Factor 3: Performance score (0-20 points)
            performance_score = min(20, metrics['performance_indicators']['performance_score'] * 20)
            health_factors.append(performance_score)

            # Factor 4: Storage efficiency (0-20 points)
            storage_efficiency = metrics['storage_metrics']['storage_efficiency_percent']
            storage_score = min(20, storage_efficiency / 5)  # 100% efficiency = 20 points
            health_factors.append(storage_score)

            # Factor 5: Trend health (0-20 points)
            trend_score = await self._calculate_trend_health_score()
            health_factors.append(trend_score)

            return round(sum(health_factors), 1)

        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 0.0

    async def _calculate_trend_health_score(self) -> float:
        """Calculate trend-based health score."""
        try:
            trends = await self._calculate_trend_indicators()

            if 'error' in trends or 'insufficient_data' in trends:
                return 10.0  # Neutral score

            # Penalize negative compression trends
            compression_trend = trends.get('compression_efficiency_trend', {})
            if compression_trend.get('direction') == 'decreasing':
                return 5.0

            # Penalize excessive storage growth
            storage_trend = trends.get('storage_growth_trend', {})
            if storage_trend.get('direction') == 'increasing' and storage_trend.get('change_percent', 0) > 50:
                return 5.0

            return 20.0  # Excellent trend health

        except Exception:
            return 10.0

    def _is_cache_valid(self) -> bool:
        """Check if cached metrics are still valid."""
        if not self._cache_timestamp:
            return False

        cache_age = datetime.utcnow() - self._cache_timestamp
        return cache_age.total_seconds() < (self._cache_ttl_minutes * 60)

    async def _generate_snapshot(self):
        """Generate a new analytics snapshot."""
        try:
            metrics = await self.get_current_metrics()

            snapshot = AnalyticsSnapshot(
                timestamp=datetime.utcnow(),
                total_conversations=metrics['conversation_metrics']['total_conversations'],
                active_conversations=metrics['conversation_metrics']['active_conversations'],
                compressed_conversations=metrics['conversation_metrics']['compressed_conversations'],
                corrupted_conversations=metrics['conversation_metrics']['corrupted_conversations'],
                average_conversation_size=metrics['storage_metrics']['average_conversation_size_bytes'],
                average_compression_ratio=metrics['conversation_metrics']['compression_ratio'],
                total_storage_used=metrics['storage_metrics']['total_original_size_bytes'],
                storage_saved_by_compression=metrics['storage_metrics']['total_storage_saved_bytes'],
                conversations_by_state=metrics['state_distribution'],
                access_patterns={
                    'average_accesses': metrics['performance_indicators']['average_accesses_per_conversation'],
                    'average_frequency': metrics['performance_indicators']['average_access_frequency_score']
                },
                performance_metrics={
                    'health_score': metrics['health_score'],
                    'performance_score': metrics['performance_indicators']['performance_score']
                }
            )

            # Store snapshot
            self.current_snapshot = snapshot
            self.historical_snapshots.append(snapshot)

            # Keep only last 100 snapshots
            if len(self.historical_snapshots) > 100:
                self.historical_snapshots = self.historical_snapshots[-100:]

            logger.debug("Generated new analytics snapshot")

        except Exception as e:
            logger.error(f"Error generating analytics snapshot: {e}")

    async def _analytics_worker(self):
        """Background worker for periodic analytics updates."""
        while True:
            try:
                await self._generate_snapshot()
                await asyncio.sleep(self.analytics_interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analytics worker: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute

    async def _alert_monitor(self):
        """Background worker for monitoring alerts."""
        while True:
            try:
                await self._check_alerts()
                await asyncio.sleep(300)  # Check every 5 minutes

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert monitor: {e}")
                await asyncio.sleep(60)

    async def _check_alerts(self):
        """Check for alert conditions and trigger notifications."""
        try:
            metrics = await self.get_current_metrics()

            if 'error' in metrics:
                return

            alerts = []

            # Check corruption rate
            corruption_rate = metrics['conversation_metrics']['corrupted_conversations'] / max(metrics['conversation_metrics']['total_conversations'], 1)
            if corruption_rate > self.alert_thresholds['corruption_rate']:
                alerts.append({
                    'type': 'corruption_rate_high',
                    'severity': 'critical',
                    'message': f'Corruption rate is {corruption_rate:.1%}, threshold is {self.alert_thresholds["corruption_rate"]:.1%}',
                    'value': corruption_rate
                })

            # Check compression ratio
            compression_ratio = metrics['conversation_metrics']['compression_ratio']
            if compression_ratio < self.alert_thresholds['compression_ratio_min']:
                alerts.append({
                    'type': 'compression_inefficient',
                    'severity': 'warning',
                    'message': f'Compression ratio is {compression_ratio:.1f}, below threshold {self.alert_thresholds["compression_ratio_min"]:.1f}',
                    'value': compression_ratio
                })

            # Check storage growth
            storage_growth = await self._calculate_storage_growth_rate()
            if storage_growth > self.alert_thresholds['storage_growth_rate']:
                alerts.append({
                    'type': 'storage_growth_high',
                    'severity': 'warning',
                    'message': f'Storage growth rate is {storage_growth:.1%} per day',
                    'value': storage_growth
                })

            # Trigger alerts
            for alert in alerts:
                await self._trigger_alert(alert)

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def _calculate_storage_growth_rate(self) -> float:
        """Calculate daily storage growth rate."""
        try:
            if len(self.historical_snapshots) < 2:
                return 0.0

            recent = self.historical_snapshots[-1]
            previous = self.historical_snapshots[-2]

            if previous.total_storage_used == 0:
                return 0.0

            growth = (recent.total_storage_used - previous.total_storage_used) / previous.total_storage_used
            return growth

        except Exception:
            return 0.0

    async def _trigger_alert(self, alert: Dict[str, Any]):
        """Trigger an alert to registered callbacks."""
        try:
            for callback in self.alert_callbacks:
                try:
                    await callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

            logger.warning(f"Alert triggered: {alert}")

        except Exception as e:
            logger.error(f"Error triggering alert: {e}")

    def add_alert_callback(self, callback: callable):
        """Add an alert callback function."""
        self.alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: callable):
        """Remove an alert callback function."""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)

    def get_alert_thresholds(self) -> Dict[str, float]:
        """Get current alert thresholds."""
        return self.alert_thresholds.copy()

    def update_alert_threshold(self, alert_type: str, threshold: float):
        """Update an alert threshold."""
        if alert_type in self.alert_thresholds:
            self.alert_thresholds[alert_type] = threshold
            logger.info(f"Updated alert threshold {alert_type} to {threshold}")

    async def get_historical_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Get historical trends for the specified number of days.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary containing historical trend data
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            relevant_snapshots = [s for s in self.historical_snapshots if s.timestamp >= cutoff_date]

            if not relevant_snapshots:
                return {'insufficient_data': True}

            trends = {
                'total_conversations': [s.total_conversations for s in relevant_snapshots],
                'active_conversations': [s.active_conversations for s in relevant_snapshots],
                'compression_ratios': [s.average_compression_ratio for s in relevant_snapshots],
                'storage_used': [s.total_storage_used for s in relevant_snapshots],
                'timestamps': [s.timestamp.isoformat() for s in relevant_snapshots]
            }

            return {
                'trends': trends,
                'period_days': days,
                'data_points': len(relevant_snapshots),
                'average_metrics': {
                    'conversations_per_day': sum(trends['total_conversations']) / max(len(relevant_snapshots), 1),
                    'compression_ratio': sum(trends['compression_ratios']) / max(len(relevant_snapshots), 1),
                    'storage_mb': (sum(trends['storage_used']) / max(len(relevant_snapshots), 1)) / (1024 * 1024)
                }
            }

        except Exception as e:
            logger.error(f"Error getting historical trends: {e}")
            return {'error': str(e)}

    async def generate_report(self, report_type: str = 'comprehensive') -> Dict[str, Any]:
        """
        Generate a comprehensive analytics report.

        Args:
            report_type: Type of report ('comprehensive', 'health', 'performance', 'storage')

        Returns:
            Dictionary containing the report data
        """
        try:
            current_metrics = await self.get_current_metrics()
            historical_trends = await self.get_historical_trends(days=7)

            report = {
                'report_type': report_type,
                'generated_at': datetime.utcnow().isoformat(),
                'period': '7_days',
                'current_metrics': current_metrics,
                'historical_trends': historical_trends
            }

            if report_type == 'comprehensive':
                report.update({
                    'recommendations': await self._generate_recommendations(),
                    'anomalies': await self._detect_anomalies(),
                    'forecasts': await self._generate_forecasts()
                })
            elif report_type == 'health':
                report['health_assessment'] = await self._generate_health_assessment()
            elif report_type == 'performance':
                report['performance_analysis'] = await self._generate_performance_analysis()
            elif report_type == 'storage':
                report['storage_analysis'] = await self._generate_storage_analysis()

            return report

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {'error': str(e)}

    async def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        metrics = await self.get_current_metrics()

        try:
            # Compression recommendations
            compression_ratio = metrics['conversation_metrics']['compression_ratio']
            if compression_ratio < 2.0:
                recommendations.append("Consider increasing compression level for better storage efficiency")

            # Corruption recommendations
            corruption_rate = metrics['conversation_metrics']['corrupted_conversations'] / max(metrics['conversation_metrics']['total_conversations'], 1)
            if corruption_rate > 0.02:
                recommendations.append("High corruption rate detected - review backup and recovery processes")

            # Performance recommendations
            performance_score = metrics['performance_indicators']['performance_score']
            if performance_score < 0.5:
                recommendations.append("Low performance score - consider optimizing access patterns")

            # Storage recommendations
            storage_efficiency = metrics['storage_metrics']['storage_efficiency_percent']
            if storage_efficiency < 70:
                recommendations.append("Storage efficiency could be improved with better compression")

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")

        return recommendations

    async def _detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in the system."""
        anomalies = []

        try:
            metrics = await self.get_current_metrics()

            # Check for unusual patterns
            if metrics['conversation_metrics']['corrupted_conversations'] > metrics['conversation_metrics']['total_conversations'] * 0.1:
                anomalies.append({
                    'type': 'high_corruption',
                    'severity': 'critical',
                    'description': 'Unusually high number of corrupted conversations detected'
                })

            # Check compression anomalies
            if metrics['conversation_metrics']['compression_ratio'] > 10:
                anomalies.append({
                    'type': 'compression_anomaly',
                    'severity': 'warning',
                    'description': 'Compression ratio is unusually high'
                })

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")

        return anomalies

    async def _generate_forecasts(self) -> Dict[str, Any]:
        """Generate forecasts for future trends."""
        try:
            trends = await self._calculate_trend_indicators()

            return {
                'storage_forecast_30_days': self._forecast_storage_usage(trends, 30),
                'performance_forecast': self._forecast_performance(trends),
                'recommendations': [
                    "Monitor storage growth trends",
                    "Review compression effectiveness",
                    "Optimize frequently accessed conversations"
                ]
            }

        except Exception as e:
            logger.error(f"Error generating forecasts: {e}")
            return {'error': str(e)}

    async def _generate_health_assessment(self) -> Dict[str, Any]:
        """Generate detailed health assessment."""
        try:
            health_score = await self._calculate_health_score()
            metrics = await self.get_current_metrics()

            assessment = {
                'overall_health_score': health_score,
                'health_status': 'excellent' if health_score >= 90 else 'good' if health_score >= 70 else 'fair' if health_score >= 50 else 'poor',
                'critical_issues': [],
                'warnings': [],
                'recommendations': []
            }

            # Assess critical issues
            if metrics['conversation_metrics']['corrupted_conversations'] > 0:
                assessment['critical_issues'].append("Corrupted conversations detected")

            # Generate recommendations
            assessment['recommendations'] = await self._generate_recommendations()

            return assessment

        except Exception as e:
            logger.error(f"Error generating health assessment: {e}")
            return {'error': str(e)}

    async def _generate_performance_analysis(self) -> Dict[str, Any]:
        """Generate performance analysis."""
        try:
            metrics = await self.get_current_metrics()

            return {
                'performance_score': metrics['performance_indicators']['performance_score'],
                'average_access_time': 'N/A',  # Would need actual timing data
                'throughput_metrics': 'N/A',  # Would need request rate data
                'bottlenecks': await self._identify_performance_bottlenecks(),
                'optimization_opportunities': [
                    "Implement caching for frequently accessed conversations",
                    "Consider database indexing improvements",
                    "Review compression/decompression performance"
                ]
            }

        except Exception as e:
            logger.error(f"Error generating performance analysis: {e}")
            return {'error': str(e)}

    async def _generate_storage_analysis(self) -> Dict[str, Any]:
        """Generate storage analysis."""
        try:
            metrics = await self.get_current_metrics()

            return {
                'total_storage_used_mb': metrics['storage_metrics']['total_original_size_bytes'] / (1024 * 1024),
                'storage_saved_mb': metrics['storage_metrics']['total_storage_saved_bytes'] / (1024 * 1024),
                'storage_efficiency_percent': metrics['storage_metrics']['storage_efficiency_percent'],
                'average_conversation_size_kb': metrics['storage_metrics']['average_conversation_size_bytes'] / 1024,
                'compression_ratio': metrics['conversation_metrics']['compression_ratio'],
                'recommendations': [
                    "Continue monitoring compression effectiveness",
                    "Consider cleanup of old conversations",
                    "Evaluate backup storage requirements"
                ]
            }

        except Exception as e:
            logger.error(f"Error generating storage analysis: {e}")
            return {'error': str(e)}

    async def _identify_performance_bottlenecks(self) -> List[str]:
        """Identify potential performance bottlenecks."""
        bottlenecks = []
        metrics = await self.get_current_metrics()

        try:
            # Check for potential issues
            if metrics['conversation_metrics']['compression_ratio'] < 1.5:
                bottlenecks.append("Low compression ratio may indicate storage inefficiency")

            if metrics['performance_indicators']['average_access_frequency_score'] < 0.3:
                bottlenecks.append("Low access frequency may indicate unused conversations")

            if metrics['storage_metrics']['storage_efficiency_percent'] < 60:
                bottlenecks.append("Low storage efficiency may impact performance")

        except Exception as e:
            logger.error(f"Error identifying bottlenecks: {e}")

        return bottlenecks

    def _forecast_storage_usage(self, trends: Dict[str, Any], days: int) -> Dict[str, Any]:
        """Forecast storage usage for the next N days."""
        try:
            storage_trend = trends.get('storage_growth_trend', {})

            if 'change_percent' not in storage_trend:
                return {'forecast_mb': 0, 'confidence': 'low'}

            current_storage = self.current_snapshot.total_storage_used if self.current_snapshot else 0
            daily_growth_rate = storage_trend['change_percent'] / 100

            forecast_storage = current_storage * (1 + daily_growth_rate) ** days

            return {
                'forecast_mb': round(forecast_storage / (1024 * 1024), 2),
                'growth_rate_percent': round(storage_trend['change_percent'], 2),
                'confidence': 'high' if abs(storage_trend['change_percent']) < 20 else 'medium'
            }

        except Exception:
            return {'forecast_mb': 0, 'confidence': 'low'}

    def _forecast_performance(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Forecast performance trends."""
        try:
            return {
                'predicted_performance_score': 75.0,  # Placeholder
                'trend_direction': 'stable',
                'confidence': 'medium',
                'factors': ['compression_efficiency', 'access_patterns', 'storage_growth']
            }

        except Exception:
            return {'error': 'Unable to forecast performance'}