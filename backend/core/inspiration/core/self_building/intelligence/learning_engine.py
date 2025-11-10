"""
LearningEngine for Self-Building System.

Analyzes telemetry data and generates improvement insights.
Uses ML models and heuristics to identify optimization opportunities.
"""

import asyncio
import statistics
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TelemetryInsight:
    """Represents an analyzed insight from telemetry data."""
    insight_type: str  # performance_degradation, error_pattern, optimization_opportunity
    severity: str  # low, medium, high, critical
    affected_component: str
    affected_tenants: List[str]
    metrics: Dict[str, float]
    description: str
    recommended_action: str
    confidence_score: float
    timestamp: datetime
    insight_id: str = field(default_factory=lambda: f"insight_{datetime.now().timestamp()}")


@dataclass
class ImprovementOpportunity:
    """Represents a potential system improvement."""
    opportunity_id: str
    title: str
    description: str
    impact_score: float  # 0-100
    effort_estimate: str  # low, medium, high
    affected_components: List[str]
    telemetry_evidence: List[TelemetryInsight]
    proposed_changes: Dict[str, Any]
    risk_level: str  # low, medium, high
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class LearningEngine:
    """
    Analyzes telemetry data and generates improvement insights.
    Uses ML models and heuristics to identify optimization opportunities.
    """
    
    def __init__(self):
        """Initialize the LearningEngine."""
        # Telemetry buffer organized by source
        self.telemetry_buffer: Dict[str, deque] = {
            'metrics': deque(maxlen=10000),
            'logs': deque(maxlen=5000),
            'events': deque(maxlen=1000)
        }
        
        # Insights cache
        self.insights_cache: List[TelemetryInsight] = []
        self.max_insights_cache_size = 1000
        
        # ML models placeholder
        self.ml_models: Dict[str, Any] = {}
        
        # Analysis state
        self._analysis_lock = asyncio.Lock()
        self._last_analysis_time: Dict[str, datetime] = {}
        
        # Buffer thresholds for triggering analysis
        self.buffer_thresholds = {
            'metrics': 100,  # Analyze after 100 metrics
            'logs': 50,      # Analyze after 50 logs
            'events': 10     # Analyze after 10 events
        }
        
        # Performance tracking for trend analysis
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Error pattern tracking
        self.error_patterns: Dict[str, Dict[str, Any]] = {}
        
        # Initialize ML models
        self._initialize_models()
        
        logger.info("LearningEngine initialized")
    
    def _initialize_models(self):
        """Initialize ML models for pattern recognition."""
        # Placeholder for future ML model integration
        # In production, this would load trained models for:
        # - Anomaly detection
        # - Error classification
        # - Performance prediction
        # - Root cause analysis
        
        self.ml_models = {
            'anomaly_detector': None,  # Future: Isolation Forest or similar
            'error_classifier': None,   # Future: Text classification model
            'performance_predictor': None,  # Future: Time series forecasting
            'root_cause_analyzer': None  # Future: Causal inference model
        }
        
        logger.debug("ML models initialized (placeholders)")
    
    async def ingest_telemetry(
        self,
        telemetry_data: Dict[str, Any],
        source: str  # metrics, logs, events
    ):
        """
        Ingest telemetry data for analysis.
        
        Buffers data and triggers analysis when thresholds met.
        
        Args:
            telemetry_data: Telemetry data dictionary
            source: Source type (metrics, logs, events)
        """
        if source not in self.telemetry_buffer:
            logger.warning(f"Unknown telemetry source: {source}")
            return
        
        # Add timestamp if not present
        if 'timestamp' not in telemetry_data:
            telemetry_data['timestamp'] = datetime.now().isoformat()
        
        # Buffer the data
        self.telemetry_buffer[source].append(telemetry_data)
        
        # Track metrics for trend analysis
        if source == 'metrics':
            metric_name = telemetry_data.get('metric_name', 'unknown')
            value = telemetry_data.get('value', 0)
            tenant_id = telemetry_data.get('tenant_id', 'system')
            
            # Create composite key for metric tracking
            metric_key = f"{tenant_id}:{metric_name}"
            self.metric_history[metric_key].append({
                'value': value,
                'timestamp': telemetry_data['timestamp']
            })
        
        # Track errors for pattern analysis
        if source == 'logs' and telemetry_data.get('severity') in ['ERROR', 'CRITICAL']:
            await self._track_error_pattern(telemetry_data)
        
        # Check if we should trigger analysis
        buffer_size = len(self.telemetry_buffer[source])
        threshold = self.buffer_thresholds.get(source, 100)
        
        if buffer_size >= threshold:
            # Trigger analysis asynchronously (don't block ingestion)
            asyncio.create_task(self._trigger_analysis(source))
        
        logger.debug(f"Ingested {source} telemetry, buffer size: {buffer_size}")
    
    async def _track_error_pattern(self, log_data: Dict[str, Any]):
        """
        Track error patterns for frequency analysis.
        
        Args:
            log_data: Log data containing error information
        """
        message = log_data.get('message', '')
        tenant_id = log_data.get('tenant_id', 'system')
        
        # Extract error signature (simplified)
        error_signature = self._extract_error_signature(message)
        
        pattern_key = f"{tenant_id}:{error_signature}"
        
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = {
                'signature': error_signature,
                'tenant_id': tenant_id,
                'count': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now(),
                'examples': []
            }
        
        pattern = self.error_patterns[pattern_key]
        pattern['count'] += 1
        pattern['last_seen'] = datetime.now()
        
        # Keep up to 5 examples
        if len(pattern['examples']) < 5:
            pattern['examples'].append({
                'message': message,
                'timestamp': log_data.get('timestamp'),
                'fields': log_data.get('fields', {})
            })
    
    def _extract_error_signature(self, message: str) -> str:
        """
        Extract error signature from log message.
        
        Args:
            message: Error message
            
        Returns:
            Error signature for grouping similar errors
        """
        # Simplified error signature extraction
        # In production, this would use more sophisticated NLP
        
        # Remove timestamps, IDs, and other variable parts
        import re
        
        # Remove UUIDs
        signature = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', message, flags=re.IGNORECASE)
        
        # Remove numbers
        signature = re.sub(r'\b\d+\b', 'N', signature)
        
        # Remove file paths
        signature = re.sub(r'/[\w/]+\.py', 'FILE.py', signature)
        
        # Take first 100 characters
        signature = signature[:100]
        
        return signature
    
    async def _trigger_analysis(self, source: str):
        """
        Trigger analysis for a specific telemetry source.
        
        Args:
            source: Telemetry source to analyze
        """
        async with self._analysis_lock:
            # Check if we analyzed recently (avoid too frequent analysis)
            last_analysis = self._last_analysis_time.get(source)
            if last_analysis:
                time_since_last = datetime.now() - last_analysis
                if time_since_last < timedelta(seconds=30):
                    logger.debug(f"Skipping {source} analysis, too soon since last analysis")
                    return
            
            logger.info(f"Triggering analysis for {source}")
            
            try:
                if source == 'metrics':
                    insights = await self.analyze_performance_trends(time_window_hours=1)
                elif source == 'logs':
                    insights = await self.analyze_error_patterns(time_window_hours=1)
                elif source == 'events':
                    # Events trigger immediate analysis
                    insights = await self._analyze_events()
                else:
                    insights = []
                
                # Add insights to cache
                self.insights_cache.extend(insights)
                
                # Trim cache if too large
                if len(self.insights_cache) > self.max_insights_cache_size:
                    self.insights_cache = self.insights_cache[-self.max_insights_cache_size:]
                
                self._last_analysis_time[source] = datetime.now()
                
                logger.info(f"Analysis complete for {source}, generated {len(insights)} insights")
                
            except Exception as e:
                logger.error(f"Error during {source} analysis: {e}")
    
    async def _analyze_events(self) -> List[TelemetryInsight]:
        """
        Analyze events for immediate insights.
        
        Returns:
            List of TelemetryInsight objects
        """
        insights = []
        
        # Get recent events
        events = list(self.telemetry_buffer['events'])
        
        for event_data in events:
            event_type = event_data.get('event_type', '')
            
            # Alarm events are critical
            if event_type == 'alarm':
                detail = event_data.get('detail', {})
                alarm_name = detail.get('alarmName', 'unknown')
                state = detail.get('state', 'UNKNOWN')
                
                if state == 'ALARM':
                    insight = TelemetryInsight(
                        insight_type='performance_degradation',
                        severity='critical',
                        affected_component=alarm_name,
                        affected_tenants=[event_data.get('tenant_id', 'system')],
                        metrics={'alarm_state': 1.0},
                        description=f"CloudWatch alarm {alarm_name} triggered",
                        recommended_action=f"Investigate alarm {alarm_name} and address root cause",
                        confidence_score=1.0,
                        timestamp=datetime.now()
                    )
                    insights.append(insight)
        
        return insights

    async def analyze_performance_trends(
        self,
        time_window_hours: int = 24,
        tenant_id: str = None
    ) -> List[TelemetryInsight]:
        """
        Analyze performance trends from metrics.
        
        Identifies degradation patterns, anomalies, and optimization opportunities.
        
        Args:
            time_window_hours: Hours of data to analyze
            tenant_id: Optional tenant filter
            
        Returns:
            List of TelemetryInsight objects
        """
        insights = []
        
        # Calculate time window
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        logger.info(f"Analyzing performance trends for last {time_window_hours} hours")
        
        # Analyze each metric in history
        for metric_key, history in self.metric_history.items():
            # Parse metric key
            parts = metric_key.split(':', 1)
            if len(parts) != 2:
                continue
            
            metric_tenant_id, metric_name = parts
            
            # Filter by tenant if specified
            if tenant_id and metric_tenant_id != tenant_id:
                continue
            
            # Filter by time window
            recent_data = [
                d for d in history
                if datetime.fromisoformat(d['timestamp']) > cutoff_time
            ]
            
            if len(recent_data) < 10:
                # Not enough data for analysis
                continue
            
            # Extract values
            values = [d['value'] for d in recent_data]
            
            # Calculate statistics
            try:
                mean = statistics.mean(values)
                stdev = statistics.stdev(values) if len(values) > 1 else 0
                
                # Calculate moving average for trend detection
                window_size = min(10, len(values) // 2)
                if window_size > 1:
                    recent_avg = statistics.mean(values[-window_size:])
                    older_avg = statistics.mean(values[:window_size])
                    
                    # Detect degradation (recent average worse than older average)
                    degradation_threshold = 0.2  # 20% degradation
                    
                    # For latency/duration metrics, higher is worse
                    if 'latency' in metric_name.lower() or 'duration' in metric_name.lower():
                        if recent_avg > older_avg * (1 + degradation_threshold):
                            insight = TelemetryInsight(
                                insight_type='performance_degradation',
                                severity='high',
                                affected_component=metric_name,
                                affected_tenants=[metric_tenant_id],
                                metrics={
                                    'recent_avg': recent_avg,
                                    'older_avg': older_avg,
                                    'degradation_pct': ((recent_avg - older_avg) / older_avg) * 100
                                },
                                description=f"Performance degradation detected in {metric_name}: "
                                           f"recent average {recent_avg:.2f} vs older average {older_avg:.2f}",
                                recommended_action=f"Investigate recent changes affecting {metric_name}",
                                confidence_score=0.8,
                                timestamp=datetime.now()
                            )
                            insights.append(insight)
                    
                    # For error/failure metrics, higher is worse
                    elif 'error' in metric_name.lower() or 'failure' in metric_name.lower():
                        if recent_avg > older_avg * (1 + degradation_threshold):
                            insight = TelemetryInsight(
                                insight_type='error_pattern',
                                severity='high',
                                affected_component=metric_name,
                                affected_tenants=[metric_tenant_id],
                                metrics={
                                    'recent_avg': recent_avg,
                                    'older_avg': older_avg,
                                    'increase_pct': ((recent_avg - older_avg) / older_avg) * 100
                                },
                                description=f"Error rate increase detected in {metric_name}: "
                                           f"recent average {recent_avg:.2f} vs older average {older_avg:.2f}",
                                recommended_action=f"Investigate error spike in {metric_name}",
                                confidence_score=0.85,
                                timestamp=datetime.now()
                            )
                            insights.append(insight)
                
                # Detect anomalies using Z-score
                if stdev > 0:
                    # Check last few values for anomalies
                    for i in range(max(0, len(values) - 5), len(values)):
                        z_score = abs((values[i] - mean) / stdev)
                        
                        if z_score > 3:  # 3 standard deviations
                            insight = TelemetryInsight(
                                insight_type='optimization_opportunity',
                                severity='medium',
                                affected_component=metric_name,
                                affected_tenants=[metric_tenant_id],
                                metrics={
                                    'value': values[i],
                                    'mean': mean,
                                    'stdev': stdev,
                                    'z_score': z_score
                                },
                                description=f"Anomaly detected in {metric_name}: "
                                           f"value {values[i]:.2f} is {z_score:.1f} standard deviations from mean",
                                recommended_action=f"Investigate anomalous behavior in {metric_name}",
                                confidence_score=0.7,
                                timestamp=datetime.now()
                            )
                            insights.append(insight)
                            break  # Only report one anomaly per metric
                
            except Exception as e:
                logger.error(f"Error analyzing metric {metric_key}: {e}")
                continue
        
        logger.info(f"Performance trend analysis generated {len(insights)} insights")
        return insights
    
    async def analyze_error_patterns(
        self,
        time_window_hours: int = 24,
        tenant_id: str = None
    ) -> List[TelemetryInsight]:
        """
        Analyze error patterns from logs.
        
        Identifies recurring errors, root causes, and fix opportunities.
        
        Args:
            time_window_hours: Hours of data to analyze
            tenant_id: Optional tenant filter
            
        Returns:
            List of TelemetryInsight objects
        """
        insights = []
        
        # Calculate time window
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        logger.info(f"Analyzing error patterns for last {time_window_hours} hours")
        
        # Analyze error patterns
        for pattern_key, pattern_data in self.error_patterns.items():
            # Parse pattern key
            parts = pattern_key.split(':', 1)
            if len(parts) != 2:
                continue
            
            pattern_tenant_id, signature = parts
            
            # Filter by tenant if specified
            if tenant_id and pattern_tenant_id != tenant_id:
                continue
            
            # Filter by time window
            if pattern_data['last_seen'] < cutoff_time:
                continue
            
            # Calculate frequency
            time_span = (pattern_data['last_seen'] - pattern_data['first_seen']).total_seconds()
            if time_span > 0:
                frequency = pattern_data['count'] / (time_span / 3600)  # errors per hour
            else:
                frequency = pattern_data['count']
            
            # Determine severity based on frequency and count
            if pattern_data['count'] >= 100 or frequency >= 10:
                severity = 'critical'
            elif pattern_data['count'] >= 50 or frequency >= 5:
                severity = 'high'
            elif pattern_data['count'] >= 10 or frequency >= 1:
                severity = 'medium'
            else:
                severity = 'low'
            
            # Extract affected component from examples
            affected_component = 'unknown'
            if pattern_data['examples']:
                first_example = pattern_data['examples'][0]
                fields = first_example.get('fields', {})
                affected_component = fields.get('component', fields.get('service', 'unknown'))
            
            # Create insight
            insight = TelemetryInsight(
                insight_type='error_pattern',
                severity=severity,
                affected_component=affected_component,
                affected_tenants=[pattern_tenant_id],
                metrics={
                    'error_count': pattern_data['count'],
                    'frequency_per_hour': frequency,
                    'time_span_hours': time_span / 3600
                },
                description=f"Recurring error pattern detected: {signature[:100]}... "
                           f"({pattern_data['count']} occurrences, {frequency:.1f}/hour)",
                recommended_action=f"Investigate and fix recurring error in {affected_component}",
                confidence_score=0.9 if pattern_data['count'] >= 10 else 0.7,
                timestamp=datetime.now()
            )
            insights.append(insight)
        
        logger.info(f"Error pattern analysis generated {len(insights)} insights")
        return insights
    
    async def identify_improvement_opportunities(
        self,
        insights: List[TelemetryInsight] = None,
        risk_tolerance: float = 0.5
    ) -> List[ImprovementOpportunity]:
        """
        Convert telemetry insights into actionable improvement opportunities.
        
        Prioritizes by impact score and filters by risk tolerance.
        
        Args:
            insights: List of insights to analyze (uses cache if None)
            risk_tolerance: Risk tolerance threshold (0.0-1.0)
            
        Returns:
            Sorted list of ImprovementOpportunity objects
        """
        if insights is None:
            # Use recent insights from cache
            insights = self.insights_cache[-100:]  # Last 100 insights
        
        if not insights:
            logger.debug("No insights available for improvement opportunity identification")
            return []
        
        logger.info(f"Identifying improvement opportunities from {len(insights)} insights")
        
        opportunities = []
        
        # Group insights by affected component
        component_insights: Dict[str, List[TelemetryInsight]] = defaultdict(list)
        for insight in insights:
            component_insights[insight.affected_component].append(insight)
        
        # Generate opportunities for each component
        for component, comp_insights in component_insights.items():
            # Skip if only low severity insights
            if all(i.severity == 'low' for i in comp_insights):
                continue
            
            # Calculate impact metrics
            total_insights = len(comp_insights)
            avg_severity_score = self._calculate_severity_score(comp_insights)
            affected_tenants = set()
            for insight in comp_insights:
                affected_tenants.update(insight.affected_tenants)
            
            # Estimate affected users (simplified)
            affected_users = len(affected_tenants) * 100  # Assume 100 users per tenant
            
            # Calculate performance gain estimate
            performance_gain = 0.0
            for insight in comp_insights:
                if insight.insight_type == 'performance_degradation':
                    degradation_pct = insight.metrics.get('degradation_pct', 0)
                    performance_gain += min(degradation_pct, 50)  # Cap at 50%
                elif insight.insight_type == 'error_pattern':
                    error_count = insight.metrics.get('error_count', 0)
                    performance_gain += min(error_count / 10, 30)  # Cap at 30%
            
            performance_gain = min(performance_gain, 100)  # Cap at 100%
            
            # Calculate frequency (insights per hour)
            frequency = total_insights / 24  # Assuming 24-hour window
            
            # Calculate impact score: (performance_gain × affected_users × frequency) / 100
            impact_score = (performance_gain * affected_users * frequency) / 100
            impact_score = min(impact_score, 100)  # Cap at 100
            
            # Determine effort estimate
            if total_insights <= 2:
                effort_estimate = 'low'
            elif total_insights <= 5:
                effort_estimate = 'medium'
            else:
                effort_estimate = 'high'
            
            # Determine risk level
            if avg_severity_score >= 0.8:
                risk_level = 'high'
            elif avg_severity_score >= 0.5:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            # Filter by risk tolerance
            risk_score = self._calculate_risk_score(risk_level)
            if risk_score > risk_tolerance:
                logger.debug(f"Skipping opportunity for {component} due to risk tolerance")
                continue
            
            # Generate proposed changes
            proposed_changes = self._generate_proposed_changes(component, comp_insights)
            
            # Create opportunity
            opportunity = ImprovementOpportunity(
                opportunity_id=f"opp_{component}_{datetime.now().timestamp()}",
                title=f"Optimize {component}",
                description=self._generate_opportunity_description(component, comp_insights),
                impact_score=impact_score,
                effort_estimate=effort_estimate,
                affected_components=[component],
                telemetry_evidence=comp_insights,
                proposed_changes=proposed_changes,
                risk_level=risk_level,
                tenant_id=list(affected_tenants)[0] if len(affected_tenants) == 1 else None
            )
            opportunities.append(opportunity)
        
        # Sort by impact score (descending)
        opportunities.sort(key=lambda o: o.impact_score, reverse=True)
        
        logger.info(f"Identified {len(opportunities)} improvement opportunities")
        return opportunities
    
    def _calculate_severity_score(self, insights: List[TelemetryInsight]) -> float:
        """
        Calculate average severity score for insights.
        
        Args:
            insights: List of insights
            
        Returns:
            Average severity score (0.0-1.0)
        """
        severity_map = {
            'low': 0.25,
            'medium': 0.5,
            'high': 0.75,
            'critical': 1.0
        }
        
        scores = [severity_map.get(i.severity, 0.5) for i in insights]
        return statistics.mean(scores) if scores else 0.5
    
    def _calculate_risk_score(self, risk_level: str) -> float:
        """
        Calculate risk score from risk level.
        
        Args:
            risk_level: Risk level string
            
        Returns:
            Risk score (0.0-1.0)
        """
        risk_map = {
            'low': 0.2,
            'medium': 0.5,
            'high': 0.8
        }
        return risk_map.get(risk_level, 0.5)
    
    def _generate_proposed_changes(
        self,
        component: str,
        insights: List[TelemetryInsight]
    ) -> Dict[str, Any]:
        """
        Generate proposed changes based on insights.
        
        Args:
            component: Component name
            insights: List of insights for component
            
        Returns:
            Dictionary of proposed changes
        """
        changes = {
            'component': component,
            'change_type': 'optimization',
            'targets': []
        }
        
        for insight in insights:
            if insight.insight_type == 'performance_degradation':
                changes['targets'].append({
                    'type': 'performance',
                    'action': 'optimize_latency',
                    'description': insight.recommended_action
                })
            elif insight.insight_type == 'error_pattern':
                changes['targets'].append({
                    'type': 'reliability',
                    'action': 'fix_error',
                    'description': insight.recommended_action
                })
            elif insight.insight_type == 'optimization_opportunity':
                changes['targets'].append({
                    'type': 'optimization',
                    'action': 'improve_efficiency',
                    'description': insight.recommended_action
                })
        
        return changes
    
    def _generate_opportunity_description(
        self,
        component: str,
        insights: List[TelemetryInsight]
    ) -> str:
        """
        Generate human-readable description for opportunity.
        
        Args:
            component: Component name
            insights: List of insights
            
        Returns:
            Description string
        """
        insight_types = set(i.insight_type for i in insights)
        severities = [i.severity for i in insights]
        max_severity = max(severities, key=lambda s: ['low', 'medium', 'high', 'critical'].index(s))
        
        description = f"Component {component} shows {len(insights)} issues with {max_severity} severity. "
        
        if 'performance_degradation' in insight_types:
            description += "Performance degradation detected. "
        if 'error_pattern' in insight_types:
            description += "Recurring error patterns identified. "
        if 'optimization_opportunity' in insight_types:
            description += "Optimization opportunities available. "
        
        return description.strip()
    
    async def get_insights_summary(
        self,
        time_range_hours: int = 1,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        Get summary of recent insights.
        
        Aggregates insights by type and severity.
        
        Args:
            time_range_hours: Time range for summary
            tenant_id: Optional tenant filter
            
        Returns:
            Summary statistics dictionary
        """
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
        
        # Filter insights by time and tenant
        filtered_insights = [
            i for i in self.insights_cache
            if i.timestamp > cutoff_time and (tenant_id is None or tenant_id in i.affected_tenants)
        ]
        
        # Aggregate by type
        by_type = defaultdict(int)
        for insight in filtered_insights:
            by_type[insight.insight_type] += 1
        
        # Aggregate by severity
        by_severity = defaultdict(int)
        for insight in filtered_insights:
            by_severity[insight.severity] += 1
        
        # Aggregate by component
        by_component = defaultdict(int)
        for insight in filtered_insights:
            by_component[insight.affected_component] += 1
        
        # Get top components
        top_components = sorted(by_component.items(), key=lambda x: x[1], reverse=True)[:5]
        
        summary = {
            'total_insights': len(filtered_insights),
            'time_range_hours': time_range_hours,
            'tenant_id': tenant_id,
            'by_type': dict(by_type),
            'by_severity': dict(by_severity),
            'top_components': [{'component': c, 'count': count} for c, count in top_components],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Generated insights summary: {summary['total_insights']} insights")
        return summary
    
    def get_buffer_status(self) -> Dict[str, Any]:
        """
        Get current buffer status.
        
        Returns:
            Dictionary with buffer status information
        """
        return {
            'metrics_buffer_size': len(self.telemetry_buffer['metrics']),
            'logs_buffer_size': len(self.telemetry_buffer['logs']),
            'events_buffer_size': len(self.telemetry_buffer['events']),
            'insights_cache_size': len(self.insights_cache),
            'metric_history_keys': len(self.metric_history),
            'error_patterns_tracked': len(self.error_patterns),
            'last_analysis_times': {
                source: time.isoformat() if time else None
                for source, time in self._last_analysis_time.items()
            }
        }
