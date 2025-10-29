#!/usr/bin/env python3
"""
Demo Environment Setup Script
Sets up the demonstration environment for AWS Native Migration hackathon presentation.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "backend"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DemoSetup:
    """Setup demonstration environment with sample data and configurations"""
    
    def __init__(self):
        self.demo_dir = Path(__file__).parent
        self.backend_dir = self.demo_dir.parent.parent.parent / "backend"
        
    async def setup_demo_environment(self):
        """Setup complete demo environment"""
        logger.info("🚀 Setting up AWS Native Migration Demo Environment")
        
        # Create demo data
        await self._create_demo_data()
        
        # Setup AWS configurations
        await self._setup_aws_configs()
        
        # Setup custom infrastructure configs
        await self._setup_custom_configs()
        
        # Create performance test data
        await self._create_performance_data()
        
        logger.info("✅ Demo environment setup complete!")
        
    async def _create_demo_data(self):
        """Create sample data for demonstrations"""
        demo_data = {
            "meetings": [
                {
                    "id": "demo-meeting-1",
                    "title": "AWS Migration Planning",
                    "participants": ["Marcus", "Pella"],
                    "transcript": "Let's discuss our migration to AWS managed services...",
                    "summary": "Team discussed migration strategy and benefits",
                    "timestamp": "2024-10-22T10:00:00Z"
                },
                {
                    "id": "demo-meeting-2", 
                    "title": "Technical Architecture Review",
                    "participants": ["Marcus", "Development Team"],
                    "transcript": "Our custom infrastructure demonstrates deep technical knowledge...",
                    "summary": "Reviewed custom vs AWS architecture approaches",
                    "timestamp": "2024-10-22T14:00:00Z"
                }
            ],
            "agents": [
                {
                    "id": "kommunikation-agent",
                    "name": "Kommunikationsagent",
                    "type": "communication",
                    "status": "active",
                    "memory_entries": 150,
                    "interactions": 1250
                },
                {
                    "id": "summarizer-agent",
                    "name": "Summarizer Agent",
                    "type": "summarization", 
                    "status": "active",
                    "memory_entries": 89,
                    "interactions": 567
                }
            ],
            "performance_metrics": {
                "aws_services": {
                    "agent_core_latency": "45ms",
                    "opensearch_query_time": "12ms",
                    "lambda_cold_start": "850ms",
                    "lambda_warm_start": "15ms"
                },
                "custom_infrastructure": {
                    "mem0_latency": "23ms",
                    "vector_service_query": "8ms",
                    "docker_startup": "2.3s",
                    "local_processing": "5ms"
                }
            }
        }
        
        demo_data_file = self.demo_dir / "demo_data.json"
        with open(demo_data_file, 'w') as f:
            json.dump(demo_data, f, indent=2)
            
        logger.info(f"📊 Created demo data: {demo_data_file}")
        
    async def _setup_aws_configs(self):
        """Setup AWS service configurations for demo"""
        aws_config = {
            "agent_core": {
                "agent_id": "meetmind-kommunikation-demo",
                "agent_alias": "DRAFT",
                "region": "us-east-1"
            },
            "opensearch": {
                "endpoint": "https://search-meetmind-demo.us-east-1.es.amazonaws.com",
                "region": "us-east-1",
                "index_prefix": "meetmind-demo"
            },
            "lambda": {
                "function_names": {
                    "kommunikation": "meetmind-kommunikation-dev",
                    "summarizer": "meetmind-summarizer-dev"
                },
                "region": "us-east-1"
            }
        }
        
        aws_config_file = self.demo_dir / "aws_config.json"
        with open(aws_config_file, 'w') as f:
            json.dump(aws_config, f, indent=2)
            
        logger.info(f"☁️ Created AWS config: {aws_config_file}")
        
    async def _setup_custom_configs(self):
        """Setup custom infrastructure configurations"""
        custom_config = {
            "infrastructure_components": [
                {
                    "name": "Rate Limiter",
                    "file": "backend/services/infrastructure/rate_limiter.py",
                    "lines_of_code": 487,
                    "aws_equivalent": "API Gateway Throttling",
                    "features": ["Sliding window", "Circuit breaker", "Multi-level limits"]
                },
                {
                    "name": "Load Balancer", 
                    "file": "backend/services/infrastructure/load_balancer.py",
                    "lines_of_code": 823,
                    "aws_equivalent": "Application Load Balancer",
                    "features": ["Health checks", "Session affinity", "Auto-scaling integration"]
                },
                {
                    "name": "Cache Manager",
                    "file": "backend/services/infrastructure/cache_manager.py", 
                    "lines_of_code": 634,
                    "aws_equivalent": "ElastiCache + DynamoDB DAX",
                    "features": ["Multi-level caching", "Intelligent invalidation", "Compression"]
                },
                {
                    "name": "Performance Monitor",
                    "file": "backend/services/infrastructure/performance_monitor.py",
                    "lines_of_code": 445,
                    "aws_equivalent": "CloudWatch",
                    "features": ["Custom metrics", "Alerting", "Performance optimization"]
                }
            ],
            "total_lines": 2389,
            "development_time": "6 months",
            "maintenance_overhead": "20 hours/month"
        }
        
        custom_config_file = self.demo_dir / "custom_config.json"
        with open(custom_config_file, 'w') as f:
            json.dump(custom_config, f, indent=2)
            
        logger.info(f"🔧 Created custom infrastructure config: {custom_config_file}")
        
    async def _create_performance_data(self):
        """Create performance comparison data"""
        performance_data = {
            "test_scenarios": [
                {
                    "name": "Memory Operations",
                    "aws_latency": 45,
                    "custom_latency": 23,
                    "aws_throughput": 1200,
                    "custom_throughput": 1800,
                    "aws_cost_per_1k": 0.15,
                    "custom_cost_per_1k": 0.08
                },
                {
                    "name": "Vector Search",
                    "aws_latency": 12,
                    "custom_latency": 8,
                    "aws_throughput": 2500,
                    "custom_throughput": 3200,
                    "aws_cost_per_1k": 0.25,
                    "custom_cost_per_1k": 0.12
                },
                {
                    "name": "Agent Runtime",
                    "aws_latency": 850,  # Cold start
                    "custom_latency": 2300,  # Docker startup
                    "aws_throughput": 500,
                    "custom_throughput": 200,
                    "aws_cost_per_1k": 2.50,
                    "custom_cost_per_1k": 1.20
                }
            ],
            "operational_metrics": {
                "aws_services": {
                    "setup_time": "2 hours",
                    "maintenance_time": "1 hour/month", 
                    "scaling": "Automatic",
                    "monitoring": "Built-in",
                    "security": "Managed"
                },
                "custom_infrastructure": {
                    "setup_time": "6 months",
                    "maintenance_time": "20 hours/month",
                    "scaling": "Manual configuration",
                    "monitoring": "Custom implementation",
                    "security": "Custom implementation"
                }
            }
        }
        
        performance_file = self.demo_dir / "performance_data.json"
        with open(performance_file, 'w') as f:
            json.dump(performance_data, f, indent=2)
            
        logger.info(f"📈 Created performance data: {performance_file}")

if __name__ == "__main__":
    setup = DemoSetup()
    asyncio.run(setup.setup_demo_environment())