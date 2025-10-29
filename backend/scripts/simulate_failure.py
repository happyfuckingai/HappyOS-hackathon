#!/usr/bin/env python3
"""
AWS Service Failure Simulation Script

This script simulates various AWS service failures for demonstration purposes,
allowing controlled testing of circuit breaker and fallback mechanisms.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FailureSimulator:
    """Simulates AWS service failures for demo purposes."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.simulation_active = False
        
    async def simulate_service_failure(self, service: str, severity: str = "high", duration: int = 60):
        """Simulate failure of a specific AWS service."""
        logger.info(f"🚨 Simulating {severity} failure for {service} service")
        
        failure_scenarios = {
            'opensearch': self._simulate_opensearch_failure,
            'lambda': self._simulate_lambda_failure,
            'agent_core': self._simulate_agent_core_failure,
            'elasticache': self._simulate_elasticache_failure,
            's3': self._simulate_s3_failure
        }
        
        if service not in failure_scenarios:
            raise ValueError(f"Unknown service: {service}")
        
        try:
            self.simulation_active = True
            await failure_scenarios[service](severity, duration)
        finally:
            self.simulation_active = False
            logger.info(f"✅ Failure simulation for {service} completed")
    
    async def _simulate_opensearch_failure(self, severity: str, duration: int):
        """Simulate OpenSearch service failure."""
        logger.info("📊 Starting OpenSearch failure simulation...")
        
        # Configure failure simulation
        failure_config = {
            'service': 'opensearch',
            'failure_type': 'timeout' if severity == 'high' else 'slow_response',
            'failure_rate': 1.0 if severity == 'high' else 0.7,
            'response_delay': 30000 if severity == 'high' else 5000,  # milliseconds
            'duration': duration
        }
        
        # Activate failure simulation
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/admin/simulate-failure",
                json=failure_config,
                timeout=10
            ) as response:
                if response.status == 200:
                    logger.info("✅ OpenSearch failure simulation activated")
                else:
                    logger.error(f"❌ Failed to activate simulation: {response.status}")
                    return
        
        # Monitor circuit breaker response
        await self._monitor_circuit_breaker('opensearch', duration)
        
        # Test search operations during failure
        await self._test_search_during_failure()
        
        # Deactivate simulation
        await self._deactivate_failure_simulation('opensearch')
    
    async def _simulate_lambda_failure(self, severity: str, duration: int):
        """Simulate Lambda service failure."""
        logger.info("⚡ Starting Lambda failure simulation...")
        
        failure_config = {
            'service': 'lambda',
            'failure_type': 'invocation_error' if severity == 'high' else 'cold_start_delay',
            'failure_rate': 1.0 if severity == 'high' else 0.8,
            'error_code': 'ServiceException' if severity == 'high' else 'ThrottlingException',
            'duration': duration
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/admin/simulate-failure",
                json=failure_config,
                timeout=10
            ) as response:
                if response.status == 200:
                    logger.info("✅ Lambda failure simulation activated")
                else:
                    logger.error(f"❌ Failed to activate simulation: {response.status}")
                    return
        
        await self._monitor_circuit_breaker('lambda', duration)
        await self._test_job_execution_during_failure()
        await self._deactivate_failure_simulation('lambda')
    
    async def _simulate_agent_core_failure(self, severity: str, duration: int):
        """Simulate Agent Core service failure."""
        logger.info("🧠 Starting Agent Core failure simulation...")
        
        failure_config = {
            'service': 'agent_core',
            'failure_type': 'memory_unavailable' if severity == 'high' else 'slow_memory_ops',
            'failure_rate': 1.0 if severity == 'high' else 0.6,
            'response_delay': 15000 if severity == 'high' else 3000,
            'duration': duration
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/admin/simulate-failure",
                json=failure_config,
                timeout=10
            ) as response:
                if response.status == 200:
                    logger.info("✅ Agent Core failure simulation activated")
                else:
                    logger.error(f"❌ Failed to activate simulation: {response.status}")
                    return
        
        await self._monitor_circuit_breaker('agent_core', duration)
        await self._test_memory_operations_during_failure()
        await self._deactivate_failure_simulation('agent_core')
    
    async def _simulate_elasticache_failure(self, severity: str, duration: int):
        """Simulate ElastiCache service failure."""
        logger.info("💾 Starting ElastiCache failure simulation...")
        
        failure_config = {
            'service': 'elasticache',
            'failure_type': 'connection_timeout' if severity == 'high' else 'cache_miss',
            'failure_rate': 1.0 if severity == 'high' else 0.9,
            'duration': duration
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/admin/simulate-failure",
                json=failure_config,
                timeout=10
            ) as response:
                if response.status == 200:
                    logger.info("✅ ElastiCache failure simulation activated")
                else:
                    logger.error(f"❌ Failed to activate simulation: {response.status}")
                    return
        
        await self._monitor_circuit_breaker('elasticache', duration)
        await self._deactivate_failure_simulation('elasticache')
    
    async def _simulate_s3_failure(self, severity: str, duration: int):
        """Simulate S3 service failure."""
        logger.info("📁 Starting S3 failure simulation...")
        
        failure_config = {
            'service': 's3',
            'failure_type': 'access_denied' if severity == 'high' else 'slow_upload',
            'failure_rate': 1.0 if severity == 'high' else 0.8,
            'response_delay': 20000 if severity == 'high' else 5000,
            'duration': duration
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/admin/simulate-failure",
                json=failure_config,
                timeout=10
            ) as response:
                if response.status == 200:
                    logger.info("✅ S3 failure simulation activated")
                else:
                    logger.error(f"❌ Failed to activate simulation: {response.status}")
                    return
        
        await self._monitor_circuit_breaker('s3', duration)
        await self._test_file_operations_during_failure()
        await self._deactivate_failure_simulation('s3')
    
    async def _monitor_circuit_breaker(self, service: str, duration: int):
        """Monitor circuit breaker state changes during failure."""
        logger.info(f"👁️ Monitoring circuit breaker for {service}...")
        
        start_time = time.time()
        previous_state = None
        
        while time.time() - start_time < duration:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/circuit-breakers", timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            current_state = data.get(service, {}).get('state', 'unknown')
                            
                            if current_state != previous_state:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                logger.info(f"🔄 [{timestamp}] Circuit breaker {service}: {previous_state} → {current_state}")
                                previous_state = current_state
                                
                                if current_state == 'open':
                                    logger.info(f"🚨 Circuit breaker OPENED for {service} - fallback activated")
                                elif current_state == 'half_open':
                                    logger.info(f"🔍 Circuit breaker HALF_OPEN for {service} - testing recovery")
                                elif current_state == 'closed':
                                    logger.info(f"✅ Circuit breaker CLOSED for {service} - service recovered")
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to check circuit breaker status: {e}")
            
            await asyncio.sleep(2)
    
    async def _test_search_during_failure(self):
        """Test search operations during OpenSearch failure."""
        logger.info("🔍 Testing search operations during failure...")
        
        test_queries = [
            {'query': 'infrastructure recovery', 'tenant_id': 'meetmind'},
            {'query': 'cost distribution', 'tenant_id': 'agentsvea'},
            {'query': 'financial analytics', 'tenant_id': 'feliciasfi'}
        ]
        
        for query_data in test_queries:
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/v1/{query_data['tenant_id']}/search",
                        json=query_data,
                        timeout=10
                    ) as response:
                        end_time = time.time()
                        latency = (end_time - start_time) * 1000
                        
                        if response.status == 200:
                            data = await response.json()
                            service_used = data.get('service', 'unknown')
                            logger.info(f"✅ Search successful: {latency:.0f}ms via {service_used}")
                        else:
                            logger.warning(f"⚠️ Search failed: {response.status}")
                            
            except Exception as e:
                logger.warning(f"⚠️ Search test failed: {e}")
            
            await asyncio.sleep(1)
    
    async def _test_job_execution_during_failure(self):
        """Test job execution during Lambda failure."""
        logger.info("⚡ Testing job execution during failure...")
        
        test_jobs = [
            {'job_type': 'summarization', 'tenant_id': 'meetmind', 'data': {'text': 'Test meeting content'}},
            {'job_type': 'document_processing', 'tenant_id': 'agentsvea', 'data': {'doc_id': 'test_doc'}},
            {'job_type': 'risk_analysis', 'tenant_id': 'feliciasfi', 'data': {'transaction_id': 'test_tx'}}
        ]
        
        for job_data in test_jobs:
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/v1/{job_data['tenant_id']}/jobs",
                        json=job_data,
                        timeout=15
                    ) as response:
                        end_time = time.time()
                        latency = (end_time - start_time) * 1000
                        
                        if response.status == 200:
                            data = await response.json()
                            service_used = data.get('service', 'unknown')
                            logger.info(f"✅ Job execution successful: {latency:.0f}ms via {service_used}")
                        else:
                            logger.warning(f"⚠️ Job execution failed: {response.status}")
                            
            except Exception as e:
                logger.warning(f"⚠️ Job test failed: {e}")
            
            await asyncio.sleep(1)
    
    async def _test_memory_operations_during_failure(self):
        """Test memory operations during Agent Core failure."""
        logger.info("🧠 Testing memory operations during failure...")
        
        test_operations = [
            {'user_id': 'marcus', 'key': 'test_context', 'value': {'test': 'data'}, 'tenant_id': 'meetmind'},
            {'user_id': 'admin', 'key': 'test_context', 'value': {'test': 'data'}, 'tenant_id': 'agentsvea'},
            {'user_id': 'trader', 'key': 'test_context', 'value': {'test': 'data'}, 'tenant_id': 'feliciasfi'}
        ]
        
        for op_data in test_operations:
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/v1/{op_data['tenant_id']}/memory",
                        json=op_data,
                        timeout=10
                    ) as response:
                        end_time = time.time()
                        latency = (end_time - start_time) * 1000
                        
                        if response.status == 200:
                            data = await response.json()
                            service_used = data.get('service', 'unknown')
                            logger.info(f"✅ Memory operation successful: {latency:.0f}ms via {service_used}")
                        else:
                            logger.warning(f"⚠️ Memory operation failed: {response.status}")
                            
            except Exception as e:
                logger.warning(f"⚠️ Memory test failed: {e}")
            
            await asyncio.sleep(1)
    
    async def _test_file_operations_during_failure(self):
        """Test file operations during S3 failure."""
        logger.info("📁 Testing file operations during failure...")
        
        test_files = [
            {'filename': 'test_document.txt', 'content': 'Test document content', 'tenant_id': 'meetmind'},
            {'filename': 'gov_doc.pdf', 'content': 'Government document content', 'tenant_id': 'agentsvea'},
            {'filename': 'financial_report.xlsx', 'content': 'Financial report content', 'tenant_id': 'feliciasfi'}
        ]
        
        for file_data in test_files:
            try:
                start_time = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/v1/{file_data['tenant_id']}/files",
                        json=file_data,
                        timeout=15
                    ) as response:
                        end_time = time.time()
                        latency = (end_time - start_time) * 1000
                        
                        if response.status == 200:
                            data = await response.json()
                            service_used = data.get('service', 'unknown')
                            logger.info(f"✅ File operation successful: {latency:.0f}ms via {service_used}")
                        else:
                            logger.warning(f"⚠️ File operation failed: {response.status}")
                            
            except Exception as e:
                logger.warning(f"⚠️ File test failed: {e}")
            
            await asyncio.sleep(1)
    
    async def _deactivate_failure_simulation(self, service: str):
        """Deactivate failure simulation for a service."""
        logger.info(f"🔄 Deactivating failure simulation for {service}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.base_url}/admin/simulate-failure/{service}",
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Failure simulation deactivated for {service}")
                    else:
                        logger.warning(f"⚠️ Failed to deactivate simulation: {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to deactivate simulation: {e}")
    
    async def simulate_cascade_failure(self, services: List[str], delay: int = 10):
        """Simulate cascading failure across multiple services."""
        logger.info(f"🌊 Simulating cascade failure across: {', '.join(services)}")
        
        tasks = []
        for i, service in enumerate(services):
            # Stagger the failures
            delay_time = i * delay
            task = asyncio.create_task(self._delayed_failure(service, delay_time))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        logger.info("🌊 Cascade failure simulation completed")
    
    async def _delayed_failure(self, service: str, delay: int):
        """Start failure simulation after a delay."""
        if delay > 0:
            logger.info(f"⏰ Waiting {delay}s before failing {service}...")
            await asyncio.sleep(delay)
        
        await self.simulate_service_failure(service, severity="high", duration=30)
    
    async def simulate_recovery_scenario(self, service: str):
        """Simulate a complete failure and recovery scenario."""
        logger.info(f"🔄 Starting complete failure/recovery scenario for {service}")
        
        # Phase 1: Normal operations
        logger.info("📊 Phase 1: Demonstrating normal operations...")
        await self._demonstrate_normal_operations(service)
        
        # Phase 2: Gradual degradation
        logger.info("⚠️ Phase 2: Simulating gradual degradation...")
        await self.simulate_service_failure(service, severity="medium", duration=20)
        
        # Phase 3: Complete failure
        logger.info("🚨 Phase 3: Simulating complete failure...")
        await self.simulate_service_failure(service, severity="high", duration=30)
        
        # Phase 4: Recovery
        logger.info("✅ Phase 4: Demonstrating automatic recovery...")
        await self._demonstrate_recovery(service)
        
        logger.info(f"🎯 Complete failure/recovery scenario finished for {service}")
    
    async def _demonstrate_normal_operations(self, service: str):
        """Demonstrate normal service operations."""
        operations = {
            'opensearch': self._test_search_during_failure,
            'lambda': self._test_job_execution_during_failure,
            'agent_core': self._test_memory_operations_during_failure,
            's3': self._test_file_operations_during_failure
        }
        
        if service in operations:
            logger.info(f"✅ Demonstrating normal {service} operations...")
            await operations[service]()
    
    async def _demonstrate_recovery(self, service: str):
        """Demonstrate service recovery."""
        logger.info(f"🔄 Monitoring {service} recovery...")
        
        # Wait for circuit breaker to close
        recovery_timeout = 60
        start_time = time.time()
        
        while time.time() - start_time < recovery_timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/circuit-breakers", timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            state = data.get(service, {}).get('state', 'unknown')
                            
                            if state == 'closed':
                                logger.info(f"✅ {service} fully recovered - circuit breaker closed")
                                break
                            elif state == 'half_open':
                                logger.info(f"🔍 {service} testing recovery - circuit breaker half-open")
                            
            except Exception as e:
                logger.warning(f"⚠️ Recovery monitoring failed: {e}")
            
            await asyncio.sleep(3)
        
        # Test operations after recovery
        await self._demonstrate_normal_operations(service)

def main():
    """Main function for failure simulation."""
    parser = argparse.ArgumentParser(description="Simulate AWS service failures for demo")
    parser.add_argument('--service', required=True, 
                       choices=['opensearch', 'lambda', 'agent_core', 'elasticache', 's3', 'cascade', 'recovery'],
                       help='Service to simulate failure for')
    parser.add_argument('--severity', default='high', choices=['medium', 'high'],
                       help='Failure severity level')
    parser.add_argument('--duration', type=int, default=60,
                       help='Failure duration in seconds')
    parser.add_argument('--base-url', default='http://localhost:8000',
                       help='Backend service base URL')
    
    args = parser.parse_args()
    
    simulator = FailureSimulator(args.base_url)
    
    try:
        if args.service == 'cascade':
            # Simulate cascade failure
            services = ['opensearch', 'lambda', 'agent_core']
            asyncio.run(simulator.simulate_cascade_failure(services))
        elif args.service == 'recovery':
            # Simulate complete recovery scenario
            asyncio.run(simulator.simulate_recovery_scenario('opensearch'))
        else:
            # Simulate single service failure
            asyncio.run(simulator.simulate_service_failure(
                args.service, args.severity, args.duration
            ))
        
        logger.info("🎯 Failure simulation completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Failure simulation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Failure simulation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())