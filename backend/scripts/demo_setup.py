#!/usr/bin/env python3
"""
Happy OS Demo Setup Script

This script prepares the complete demo environment for hackathon presentation,
including AWS services, local agent services, demo data, and monitoring.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import boto3
from botocore.exceptions import ClientError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DemoSetup:
    """Comprehensive demo environment setup and validation."""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.demo_data_path = Path(__file__).parent / "demo_data"
        self.aws_clients = {}
        self.setup_status = {}
        
    async def setup_complete_demo(self):
        """Setup complete demo environment."""
        logger.info("🚀 Starting Happy OS Demo Setup")
        
        try:
            # Phase 1: Environment validation
            await self._validate_environment()
            
            # Phase 2: AWS services setup
            await self._setup_aws_services()
            
            # Phase 3: Local agent services
            await self._setup_local_agent_services()
            
            # Phase 4: Demo data preparation
            await self._prepare_demo_data()
            
            # Phase 5: Monitoring setup
            await self._setup_monitoring()
            
            # Phase 6: System validation
            await self._validate_complete_system()
            
            logger.info("✅ Demo setup completed successfully!")
            await self._print_demo_summary()
            
        except Exception as e:
            logger.error(f"❌ Demo setup failed: {e}")
            await self._cleanup_partial_setup()
            raise
    
    async def _validate_environment(self):
        """Validate environment prerequisites."""
        logger.info("🔍 Validating environment prerequisites...")
        
        # Check Python version
        if sys.version_info < (3, 9):
            raise RuntimeError("Python 3.9+ required")
        
        # Check required environment variables
        required_vars = [
            'AWS_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.warning(f"Missing AWS credentials: {missing_vars}")
            logger.info("Using local services only for demo")
        
        # Check backend service
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health", timeout=5) as response:
                    if response.status == 200:
                        logger.info("✅ Backend service is running")
                    else:
                        raise RuntimeError("Backend service not responding correctly")
        except Exception as e:
            logger.error(f"❌ Backend service check failed: {e}")
            logger.info("Please start backend service: python backend/main.py")
            raise
        
        self.setup_status['environment'] = True
    
    async def _setup_aws_services(self):
        """Setup and validate AWS services."""
        logger.info("☁️ Setting up AWS services...")
        
        if not all(os.getenv(var) for var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']):
            logger.info("⚠️ AWS credentials not available, skipping AWS setup")
            self.setup_status['aws_services'] = False
            return
        
        try:
            # Initialize AWS clients
            self.aws_clients = {
                'opensearch': boto3.client('opensearch'),
                'lambda': boto3.client('lambda'),
                'secretsmanager': boto3.client('secretsmanager'),
                's3': boto3.client('s3')
            }
            
            # Check AWS service availability
            aws_status = {}
            
            # Check OpenSearch
            try:
                domains = self.aws_clients['opensearch'].list_domain_names()
                aws_status['opensearch'] = len(domains['DomainNames']) > 0
                logger.info(f"✅ OpenSearch: {len(domains['DomainNames'])} domains available")
            except Exception as e:
                logger.warning(f"⚠️ OpenSearch not available: {e}")
                aws_status['opensearch'] = False
            
            # Check Lambda
            try:
                functions = self.aws_clients['lambda'].list_functions(MaxItems=1)
                aws_status['lambda'] = True
                logger.info("✅ Lambda service available")
            except Exception as e:
                logger.warning(f"⚠️ Lambda not available: {e}")
                aws_status['lambda'] = False
            
            # Setup demo AWS resources if available
            if any(aws_status.values()):
                await self._create_demo_aws_resources()
            
            self.setup_status['aws_services'] = any(aws_status.values())
            
        except Exception as e:
            logger.warning(f"⚠️ AWS setup failed: {e}")
            self.setup_status['aws_services'] = False
    
    async def _create_demo_aws_resources(self):
        """Create demo-specific AWS resources."""
        logger.info("🏗️ Creating demo AWS resources...")
        
        # Create demo S3 bucket for file storage demo
        try:
            bucket_name = f"infrastructure-recovery-demo-{int(time.time())}"
            self.aws_clients['s3'].create_bucket(Bucket=bucket_name)
            
            # Store demo files
            demo_files = [
                ("demo_document.txt", "This is a demo document for Infrastructure Recovery"),
                ("meeting_transcript.json", json.dumps({
                    "meeting_id": "demo_001",
                    "participants": ["Marcus", "Pella", "Team"],
                    "topic": "Infrastructure Recovery Demo",
                    "transcript": "Discussion about resilient AI infrastructure..."
                }))
            ]
            
            for filename, content in demo_files:
                self.aws_clients['s3'].put_object(
                    Bucket=bucket_name,
                    Key=filename,
                    Body=content.encode('utf-8')
                )
            
            logger.info(f"✅ Created demo S3 bucket: {bucket_name}")
            
        except Exception as e:
            logger.warning(f"⚠️ S3 demo setup failed: {e}")
    
    async def _setup_local_agent_services(self):
        """Setup and validate local agent services."""
        logger.info("🏠 Setting up Happy OS local agent services...")
        
        local_agent_services = {
            'agent_memory_core': 8001,
            'agent_search_engine': 8002, 
            'agent_task_runner': 8003,
            'agent_file_system': 8004
        }
        
        service_status = {}
        
        for service_name, port in local_agent_services.items():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://localhost:{port}/health", timeout=2) as response:
                        if response.status == 200:
                            service_status[service_name] = True
                            logger.info(f"✅ {service_name} running on port {port}")
                        else:
                            service_status[service_name] = False
                            logger.warning(f"⚠️ {service_name} not responding correctly")
            except Exception:
                service_status[service_name] = False
                logger.warning(f"⚠️ {service_name} not running on port {port}")
        
        # Start missing services
        missing_services = [name for name, status in service_status.items() if not status]
        if missing_services:
            logger.info(f"🔧 Starting missing services: {missing_services}")
            await self._start_local_services(missing_services)
        
        self.setup_status['local_agent_services'] = len(service_status) > 0
    
    async def _start_local_services(self, services: List[str]):
        """Start local agent services."""
        import subprocess
        
        service_commands = {
            'agent_memory_core': 'python backend/infrastructure/local/services/memory_service.py',
            'agent_search_engine': 'python backend/infrastructure/local/services/search_service.py',
            'agent_task_runner': 'python backend/infrastructure/local/services/job_runner.py',
            'agent_file_system': 'python backend/infrastructure/local/services/file_store.py'
        }
        
        for service in services:
            if service in service_commands:
                try:
                    subprocess.Popen(
                        service_commands[service].split(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logger.info(f"🚀 Started {service}")
                    await asyncio.sleep(2)  # Give service time to start
                except Exception as e:
                    logger.warning(f"⚠️ Failed to start {service}: {e}")
    
    async def _prepare_demo_data(self):
        """Prepare comprehensive demo data."""
        logger.info("📊 Preparing demo data...")
        
        # Create demo data directory
        self.demo_data_path.mkdir(exist_ok=True)
        
        # Demo tenant configurations
        demo_tenants = {
            'meetmind': {
                'domain': 'meetmind.se',
                'users': ['marcus', 'pella'],
                'meetings': [
                    {
                        'id': 'demo_meeting_001',
                        'title': 'Infrastructure Recovery Demo',
                        'participants': ['Marcus', 'Pella', 'Team'],
                        'transcript': 'Discussion about building resilient AI infrastructure with intelligent fallback systems...'
                    }
                ]
            },
            'agentsvea': {
                'domain': 'agentsvea.se', 
                'users': ['admin', 'analyst'],
                'documents': [
                    {
                        'id': 'gov_doc_001',
                        'title': 'Government Cost Distribution Framework',
                        'content': 'Guidelines for distributing costs across government departments...'
                    }
                ]
            },
            'feliciasfi': {
                'domain': 'feliciasfi.com',
                'users': ['trader', 'analyst'],
                'transactions': [
                    {
                        'id': 'tx_001',
                        'type': 'equity_trade',
                        'amount': 10000,
                        'risk_score': 0.23
                    }
                ]
            }
        }
        
        # Store demo data
        for tenant_id, tenant_data in demo_tenants.items():
            await self._setup_tenant_demo_data(tenant_id, tenant_data)
        
        self.setup_status['demo_data'] = True
    
    async def _setup_tenant_demo_data(self, tenant_id: str, tenant_data: Dict):
        """Setup demo data for a specific tenant."""
        logger.info(f"📋 Setting up demo data for {tenant_id}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Setup tenant configuration
                async with session.post(
                    f"{self.base_url}/api/v1/admin/tenants/{tenant_id}/setup",
                    json=tenant_data,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ {tenant_id} tenant configured")
                    else:
                        logger.warning(f"⚠️ {tenant_id} setup failed: {response.status}")
                
                # Setup user contexts
                for user in tenant_data.get('users', []):
                    user_context = {
                        'user_id': user,
                        'preferences': {'technical_level': 'advanced' if user == 'marcus' else 'business'},
                        'history': f'Demo user for {tenant_id} tenant'
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/v1/{tenant_id}/memory",
                        json={
                            'user_id': user,
                            'key': 'user_context',
                            'value': user_context
                        },
                        timeout=5
                    ) as response:
                        if response.status == 200:
                            logger.info(f"✅ {user} context stored for {tenant_id}")
                
                # Setup domain-specific data
                if 'meetings' in tenant_data:
                    for meeting in tenant_data['meetings']:
                        async with session.post(
                            f"{self.base_url}/api/v1/{tenant_id}/search/index",
                            json={
                                'document': meeting,
                                'doc_type': 'meeting'
                            },
                            timeout=5
                        ) as response:
                            if response.status == 200:
                                logger.info(f"✅ Meeting {meeting['id']} indexed for {tenant_id}")
                
        except Exception as e:
            logger.warning(f"⚠️ Demo data setup failed for {tenant_id}: {e}")
    
    async def _setup_monitoring(self):
        """Setup monitoring and dashboard."""
        logger.info("📊 Setting up monitoring dashboard...")
        
        try:
            # Verify monitoring endpoints
            monitoring_endpoints = [
                '/health',
                '/circuit-breakers', 
                '/metrics',
                '/api/v1/admin/system-status'
            ]
            
            async with aiohttp.ClientSession() as session:
                for endpoint in monitoring_endpoints:
                    try:
                        async with session.get(f"{self.base_url}{endpoint}", timeout=5) as response:
                            if response.status == 200:
                                logger.info(f"✅ Monitoring endpoint {endpoint} available")
                            else:
                                logger.warning(f"⚠️ Monitoring endpoint {endpoint} returned {response.status}")
                    except Exception as e:
                        logger.warning(f"⚠️ Monitoring endpoint {endpoint} failed: {e}")
            
            self.setup_status['monitoring'] = True
            
        except Exception as e:
            logger.warning(f"⚠️ Monitoring setup failed: {e}")
            self.setup_status['monitoring'] = False
    
    async def _validate_complete_system(self):
        """Validate complete system functionality."""
        logger.info("🔍 Validating complete system functionality...")
        
        validation_tests = [
            self._test_multi_tenant_operations,
            self._test_circuit_breaker_functionality,
            self._test_a2a_communication,
            self._test_fallback_services
        ]
        
        validation_results = {}
        
        for test in validation_tests:
            try:
                result = await test()
                validation_results[test.__name__] = result
                if result:
                    logger.info(f"✅ {test.__name__} passed")
                else:
                    logger.warning(f"⚠️ {test.__name__} failed")
            except Exception as e:
                logger.warning(f"⚠️ {test.__name__} error: {e}")
                validation_results[test.__name__] = False
        
        self.setup_status['system_validation'] = any(validation_results.values())
    
    async def _test_multi_tenant_operations(self) -> bool:
        """Test multi-tenant operations."""
        try:
            async with aiohttp.ClientSession() as session:
                # Test MeetMind tenant
                async with session.post(
                    f"{self.base_url}/api/v1/meetmind/memory",
                    json={'user_id': 'marcus', 'key': 'test', 'value': 'demo_value'},
                    timeout=5
                ) as response:
                    meetmind_ok = response.status == 200
                
                # Test Agent Svea tenant
                async with session.post(
                    f"{self.base_url}/api/v1/agentsvea/search",
                    json={'query': 'test query', 'tenant_id': 'agentsvea'},
                    timeout=5
                ) as response:
                    agentsvea_ok = response.status == 200
                
                return meetmind_ok and agentsvea_ok
        except:
            return False
    
    async def _test_circuit_breaker_functionality(self) -> bool:
        """Test circuit breaker functionality."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/circuit-breakers", timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return isinstance(data, dict) and len(data) > 0
            return False
        except:
            return False
    
    async def _test_a2a_communication(self) -> bool:
        """Test A2A communication."""
        try:
            async with aiohttp.ClientSession() as session:
                message = {
                    'sender_agent': 'demo_sender',
                    'recipient_agent': 'demo_recipient',
                    'tenant_id': 'meetmind',
                    'message_type': 'test',
                    'payload': {'test': 'data'}
                }
                
                async with session.post(
                    f"{self.base_url}/api/v1/a2a/send",
                    json=message,
                    timeout=5
                ) as response:
                    return response.status == 200
        except:
            return False
    
    async def _test_fallback_services(self) -> bool:
        """Test fallback services availability."""
        fallback_ports = [8001, 8002, 8003, 8004]
        working_services = 0
        
        for port in fallback_ports:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://localhost:{port}/health", timeout=2) as response:
                        if response.status == 200:
                            working_services += 1
            except:
                pass
        
        return working_services >= 2  # At least 2 fallback services working
    
    async def _print_demo_summary(self):
        """Print comprehensive demo setup summary."""
        print("\n" + "="*60)
        print("🎯 HAPPY OS DEMO READY")
        print("="*60)
        
        print("\n📊 SETUP STATUS:")
        for component, status in self.setup_status.items():
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {component.replace('_', ' ').title()}: {'Ready' if status else 'Failed'}")
        
        print("\n🌐 DEMO ENDPOINTS:")
        print(f"  • Backend API: {self.base_url}")
        print(f"  • Health Check: {self.base_url}/health")
        print(f"  • Circuit Breakers: {self.base_url}/circuit-breakers")
        print(f"  • System Metrics: {self.base_url}/metrics")
        
        print("\n🤖 HAPPY OS AGENT ENVIRONMENTS:")
        print("  • MeetMind (meetmind.se) - Meeting summarization agents")
        print("  • Agent Svea (agentsvea.se) - Government document agents")
        print("  • Felicia's Finance (feliciasfi.com) - Financial analytics agents")
        
        print("\n🔧 HAPPY OS LOCAL AGENT SERVICES:")
        print("  • Agent Memory Core: http://localhost:8001")
        print("  • Agent Search Engine: http://localhost:8002")
        print("  • Agent Task Runner: http://localhost:8003")
        print("  • Agent File System: http://localhost:8004")
        
        print("\n🎬 DEMO COMMANDS:")
        print("  # Test multi-agent operations")
        print(f"  curl -X POST {self.base_url}/api/v1/meetmind/memory \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -d '{\"user_id\": \"marcus\", \"key\": \"demo\", \"value\": \"test\"}'")
        
        print("\n  # Simulate AWS failure")
        print("  python backend/scripts/simulate_failure.py --service opensearch")
        
        print("\n  # Check Happy OS resilient infrastructure status")
        print(f"  curl {self.base_url}/circuit-breakers")
        
        print("\n🚀 READY FOR DEMO!")
        print("="*60)
    
    async def _cleanup_partial_setup(self):
        """Cleanup partial setup on failure."""
        logger.info("🧹 Cleaning up partial setup...")
        # Add cleanup logic here if needed
        pass

async def main():
    """Main demo setup function."""
    setup = DemoSetup()
    
    try:
        await setup.setup_complete_demo()
        return 0
    except KeyboardInterrupt:
        logger.info("Demo setup interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Demo setup failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)