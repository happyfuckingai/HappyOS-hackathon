"""
Monitor LLM Service Deployment

This script monitors the LLM service deployment in real-time, tracking:
- Request latency
- Error rates
- Circuit breaker state
- Cost per hour
- Cache hit rate

Usage:
    python monitor_llm_deployment.py --environment prod --region us-east-1 --duration 24
"""

import argparse
import boto3
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict


class LLMDeploymentMonitor:
    """Monitor LLM service deployment metrics."""
    
    def __init__(self, environment: str, region: str):
        """Initialize monitor."""
        self.environment = environment
        self.region = region
        
        # AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        
        # Resource names
        self.table_name = f"happyos-llm-usage-{environment}"
        self.log_group_name = f"/aws/happyos/llm-service-{environment}"
        
        print(f"📊 LLM Deployment Monitor")
        print(f"   Environment: {environment}")
        print(f"   Region: {region}")
        print()
    
    def monitor(self, duration_hours: int = 24, interval_minutes: int = 5):
        """
        Monitor deployment for specified duration.
        
        Args:
            duration_hours: How long to monitor (hours)
            interval_minutes: Check interval (minutes)
        """
        print(f"🔍 Monitoring for {duration_hours} hours (checking every {interval_minutes} minutes)")
        print("=" * 80)
        print()
        
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)
        check_count = 0
        
        try:
            while datetime.utcnow() < end_time:
                check_count += 1
                elapsed = datetime.utcnow() - start_time
                
                print(f"\n{'=' * 80}")
                print(f"Check #{check_count} - Elapsed: {elapsed}")
                print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"{'=' * 80}\n")
                
                # Collect metrics
                metrics = self.collect_metrics()
                
                # Display metrics
                self.display_metrics(metrics)
                
                # Check for issues
                issues = self.check_for_issues(metrics)
                if issues:
                    self.display_issues(issues)
                
                # Wait for next check
                if datetime.utcnow() < end_time:
                    wait_seconds = interval_minutes * 60
                    print(f"\n⏳ Next check in {interval_minutes} minutes...")
                    time.sleep(wait_seconds)
                    
        except KeyboardInterrupt:
            print("\n\n⚠️  Monitoring interrupted by user")
            print(f"   Completed {check_count} checks")
        
        print("\n✅ Monitoring completed")
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from DynamoDB and CloudWatch."""
        metrics = {
            'timestamp': datetime.utcnow(),
            'requests': self.get_request_metrics(),
            'latency': self.get_latency_metrics(),
            'errors': self.get_error_metrics(),
            'cost': self.get_cost_metrics(),
            'cache': self.get_cache_metrics(),
            'circuit_breaker': self.get_circuit_breaker_state(),
            'agents': self.get_agent_metrics()
        }
        
        return metrics
    
    def get_request_metrics(self) -> Dict[str, Any]:
        """Get request count metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            # Scan DynamoDB for recent requests
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                },
                Select='COUNT'
            )
            
            total_requests = response['Count']
            
            return {
                'total_last_hour': total_requests,
                'rate_per_minute': round(total_requests / 60, 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_latency_metrics(self) -> Dict[str, Any]:
        """Get latency metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                }
            )
            
            latencies = []
            for item in response.get('Items', []):
                if 'latency_ms' in item:
                    latencies.append(int(item['latency_ms']['N']))
            
            if not latencies:
                return {'no_data': True}
            
            latencies.sort()
            count = len(latencies)
            
            return {
                'min': latencies[0],
                'max': latencies[-1],
                'avg': round(sum(latencies) / count, 2),
                'p50': latencies[count // 2],
                'p95': latencies[int(count * 0.95)],
                'p99': latencies[int(count * 0.99)]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """Get error rate metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                }
            )
            
            total = 0
            errors = 0
            
            for item in response.get('Items', []):
                total += 1
                if 'success' in item and not item['success']['BOOL']:
                    errors += 1
            
            error_rate = (errors / total * 100) if total > 0 else 0
            
            return {
                'total_requests': total,
                'error_count': errors,
                'error_rate_percent': round(error_rate, 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_cost_metrics(self) -> Dict[str, Any]:
        """Get cost metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                }
            )
            
            total_cost = 0.0
            total_tokens = 0
            
            for item in response.get('Items', []):
                if 'estimated_cost' in item:
                    total_cost += float(item['estimated_cost']['N'])
                if 'tokens_used' in item:
                    total_tokens += int(item['tokens_used']['N'])
            
            # Extrapolate to daily cost
            daily_cost = total_cost * 24
            
            return {
                'cost_last_hour': round(total_cost, 4),
                'estimated_daily_cost': round(daily_cost, 2),
                'tokens_last_hour': total_tokens
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache hit rate metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                }
            )
            
            total = 0
            cached = 0
            
            for item in response.get('Items', []):
                total += 1
                if 'cached' in item and item['cached']['BOOL']:
                    cached += 1
            
            hit_rate = (cached / total * 100) if total > 0 else 0
            
            return {
                'total_requests': total,
                'cache_hits': cached,
                'cache_misses': total - cached,
                'hit_rate_percent': round(hit_rate, 2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Get circuit breaker state from logs."""
        try:
            # Query CloudWatch logs for circuit breaker events
            start_time = int((datetime.utcnow() - timedelta(minutes=5)).timestamp() * 1000)
            end_time = int(datetime.utcnow().timestamp() * 1000)
            
            response = self.logs.filter_log_events(
                logGroupName=self.log_group_name,
                startTime=start_time,
                endTime=end_time,
                filterPattern='circuit breaker'
            )
            
            # Parse events
            open_events = 0
            closed_events = 0
            
            for event in response.get('events', []):
                message = event['message'].lower()
                if 'circuit breaker open' in message or 'circuit breaker opened' in message:
                    open_events += 1
                elif 'circuit breaker closed' in message:
                    closed_events += 1
            
            # Determine current state
            if open_events > closed_events:
                state = 'OPEN'
            elif closed_events > 0:
                state = 'CLOSED'
            else:
                state = 'UNKNOWN'
            
            return {
                'state': state,
                'open_events_last_5min': open_events,
                'closed_events_last_5min': closed_events
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get per-agent metrics."""
        try:
            # Query last hour of data
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='#ts >= :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': {'S': start_time.isoformat()}
                }
            )
            
            agent_stats = defaultdict(lambda: {'requests': 0, 'tokens': 0, 'cost': 0.0})
            
            for item in response.get('Items', []):
                if 'agent_id' in item:
                    agent_id = item['agent_id']['S']
                    agent_stats[agent_id]['requests'] += 1
                    
                    if 'tokens_used' in item:
                        agent_stats[agent_id]['tokens'] += int(item['tokens_used']['N'])
                    
                    if 'estimated_cost' in item:
                        agent_stats[agent_id]['cost'] += float(item['estimated_cost']['N'])
            
            # Convert to regular dict and round costs
            result = {}
            for agent_id, stats in agent_stats.items():
                result[agent_id] = {
                    'requests': stats['requests'],
                    'tokens': stats['tokens'],
                    'cost': round(stats['cost'], 4)
                }
            
            return result
            
        except Exception as e:
            return {'error': str(e)}
    
    def display_metrics(self, metrics: Dict[str, Any]):
        """Display collected metrics."""
        # Requests
        print("📊 REQUEST METRICS (Last Hour)")
        if 'error' in metrics['requests']:
            print(f"   ❌ Error: {metrics['requests']['error']}")
        else:
            print(f"   Total Requests: {metrics['requests']['total_last_hour']}")
            print(f"   Rate: {metrics['requests']['rate_per_minute']} req/min")
        
        # Latency
        print("\n⏱️  LATENCY METRICS (Last Hour)")
        if 'error' in metrics['latency']:
            print(f"   ❌ Error: {metrics['latency']['error']}")
        elif 'no_data' in metrics['latency']:
            print(f"   ℹ️  No data available")
        else:
            print(f"   Min: {metrics['latency']['min']}ms")
            print(f"   Avg: {metrics['latency']['avg']}ms")
            print(f"   P50: {metrics['latency']['p50']}ms")
            print(f"   P95: {metrics['latency']['p95']}ms")
            print(f"   P99: {metrics['latency']['p99']}ms")
            print(f"   Max: {metrics['latency']['max']}ms")
        
        # Errors
        print("\n❌ ERROR METRICS (Last Hour)")
        if 'error' in metrics['errors']:
            print(f"   ❌ Error: {metrics['errors']['error']}")
        else:
            print(f"   Total Requests: {metrics['errors']['total_requests']}")
            print(f"   Errors: {metrics['errors']['error_count']}")
            print(f"   Error Rate: {metrics['errors']['error_rate_percent']}%")
        
        # Cost
        print("\n💰 COST METRICS")
        if 'error' in metrics['cost']:
            print(f"   ❌ Error: {metrics['cost']['error']}")
        else:
            print(f"   Last Hour: ${metrics['cost']['cost_last_hour']}")
            print(f"   Estimated Daily: ${metrics['cost']['estimated_daily_cost']}")
            print(f"   Tokens (Last Hour): {metrics['cost']['tokens_last_hour']:,}")
        
        # Cache
        print("\n🔄 CACHE METRICS (Last Hour)")
        if 'error' in metrics['cache']:
            print(f"   ❌ Error: {metrics['cache']['error']}")
        else:
            print(f"   Total Requests: {metrics['cache']['total_requests']}")
            print(f"   Cache Hits: {metrics['cache']['cache_hits']}")
            print(f"   Cache Misses: {metrics['cache']['cache_misses']}")
            print(f"   Hit Rate: {metrics['cache']['hit_rate_percent']}%")
        
        # Circuit Breaker
        print("\n🔌 CIRCUIT BREAKER STATE")
        if 'error' in metrics['circuit_breaker']:
            print(f"   ❌ Error: {metrics['circuit_breaker']['error']}")
        else:
            state = metrics['circuit_breaker']['state']
            if state == 'OPEN':
                print(f"   ⚠️  State: {state} (ALERT!)")
            else:
                print(f"   ✓ State: {state}")
            print(f"   Open Events (5min): {metrics['circuit_breaker']['open_events_last_5min']}")
            print(f"   Closed Events (5min): {metrics['circuit_breaker']['closed_events_last_5min']}")
        
        # Agent Breakdown
        print("\n🤖 AGENT METRICS (Last Hour)")
        if 'error' in metrics['agents']:
            print(f"   ❌ Error: {metrics['agents']['error']}")
        elif not metrics['agents']:
            print(f"   ℹ️  No agent data available")
        else:
            for agent_id, stats in sorted(metrics['agents'].items()):
                print(f"   {agent_id}:")
                print(f"      Requests: {stats['requests']}")
                print(f"      Tokens: {stats['tokens']:,}")
                print(f"      Cost: ${stats['cost']}")
    
    def check_for_issues(self, metrics: Dict[str, Any]) -> List[str]:
        """Check metrics for potential issues."""
        issues = []
        
        # Check error rate
        if 'error_rate_percent' in metrics['errors']:
            if metrics['errors']['error_rate_percent'] > 5:
                issues.append(f"High error rate: {metrics['errors']['error_rate_percent']}% (threshold: 5%)")
        
        # Check latency
        if 'p95' in metrics['latency']:
            if metrics['latency']['p95'] > 5000:
                issues.append(f"High P95 latency: {metrics['latency']['p95']}ms (threshold: 5000ms)")
        
        # Check cost
        if 'estimated_daily_cost' in metrics['cost']:
            if metrics['cost']['estimated_daily_cost'] > 100:
                issues.append(f"High daily cost: ${metrics['cost']['estimated_daily_cost']} (threshold: $100)")
        
        # Check cache hit rate
        if 'hit_rate_percent' in metrics['cache']:
            if metrics['cache']['hit_rate_percent'] < 20:
                issues.append(f"Low cache hit rate: {metrics['cache']['hit_rate_percent']}% (threshold: 20%)")
        
        # Check circuit breaker
        if 'state' in metrics['circuit_breaker']:
            if metrics['circuit_breaker']['state'] == 'OPEN':
                issues.append("Circuit breaker is OPEN - service degraded")
        
        return issues
    
    def display_issues(self, issues: List[str]):
        """Display detected issues."""
        print("\n⚠️  ISSUES DETECTED:")
        for issue in issues:
            print(f"   - {issue}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Monitor LLM Service Deployment'
    )
    parser.add_argument(
        '--environment',
        choices=['dev', 'staging', 'prod'],
        required=True,
        help='Deployment environment'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=24,
        help='Monitoring duration in hours (default: 24)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Check interval in minutes (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = LLMDeploymentMonitor(
        environment=args.environment,
        region=args.region
    )
    
    # Start monitoring
    monitor.monitor(
        duration_hours=args.duration,
        interval_minutes=args.interval
    )


if __name__ == '__main__':
    main()
