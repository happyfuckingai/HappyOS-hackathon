"""
Orchestrator Components Examples

This module contains practical examples of how to use the Orchestrator Components
in HappyOS including basic orchestration, ultimate orchestration, agent management,
delegation, intent handling, and MCP integration.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


# Basic Orchestrator Examples
async def basic_orchestrator_example():
    """Example of basic orchestrator usage."""

    print("=== Basic Orchestrator Example ===")

    try:
        from app.core.orchestrator.basic_orchestrator import BasicOrchestrator
        
        # Create basic orchestrator
        orchestrator = BasicOrchestrator()
        
        # Initialize orchestrator
        print("🎼 Initializing basic orchestrator...")
        
        config = {
            "max_concurrent_tasks": 5,
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "enable_logging": True
        }
        
        await orchestrator.initialize(config)
        
        print(f"✅ Orchestrator initialized with config: {config}")
        
        # Process simple requests
        print("📝 Processing orchestration requests...")
        
        requests = [
            {
                "id": "req_1",
                "type": "skill_execution", 
                "payload": {"skill": "weather_check", "location": "Stockholm"},
                "priority": "high"
            },
            {
                "id": "req_2",
                "type": "data_processing",
                "payload": {"data": "sample_dataset.csv", "operation": "analyze"},
                "priority": "medium"
            },
            {
                "id": "req_3",
                "type": "system_health",
                "payload": {"check_type": "full", "include_metrics": True},
                "priority": "low"
            }
        ]
        
        results = {}
        
        for request in requests:
            print(f"   Processing request: {request['id']}")
            
            result = await orchestrator.process_request(
                request_id=request["id"],
                request_type=request["type"],
                payload=request["payload"],
                priority=request["priority"]
            )
            
            results[request["id"]] = result
            
            print(f"     Status: {result.get('status')}")
            print(f"     Duration: {result.get('execution_time', 0):.2f}s")
            print(f"     Success: {result.get('success', False)}")
        
        # Get orchestrator metrics
        metrics = await orchestrator.get_metrics()
        
        print(f"📊 Orchestrator metrics:")
        print(f"   Requests processed: {metrics.get('total_requests', 0)}")
        print(f"   Success rate: {metrics.get('success_rate', 0):.2%}")
        print(f"   Average execution time: {metrics.get('avg_execution_time', 0):.2f}s")
        print(f"   Active tasks: {metrics.get('active_tasks', 0)}")
        
    except ImportError:
        print("🎼 Basic orchestrator not available, showing conceptual example")
        print("   Would provide:")
        print("   - Simple request routing and processing")
        print("   - Task prioritization and queuing")
        print("   - Basic error handling and retries")
        print("   - Performance metrics and monitoring")
    
    print()


async def ultimate_orchestrator_example():
    """Example of ultimate orchestrator usage."""

    print("=== Ultimate Orchestrator Example ===")

    try:
        from app.core.orchestrator.ultimate_orchestrator import UltimateOrchestrator
        
        # Create ultimate orchestrator
        ultimate_orch = UltimateOrchestrator()
        
        # Initialize with advanced configuration
        print("🚀 Initializing ultimate orchestrator...")
        
        advanced_config = {
            "ai_powered_routing": True,
            "adaptive_load_balancing": True,
            "predictive_scaling": True,
            "multi_agent_coordination": True,
            "advanced_error_recovery": True,
            "real_time_optimization": True
        }
        
        await ultimate_orch.initialize(advanced_config)
        
        print(f"✅ Ultimate orchestrator initialized with advanced features")
        
        # Process complex multi-step requests
        print("🔀 Processing complex orchestration requests...")
        
        complex_requests = [
            {
                "id": "complex_req_1",
                "type": "multi_agent_workflow",
                "description": "Analyze customer feedback and generate insights",
                "steps": [
                    {"agent": "data_collector", "task": "gather_feedback"},
                    {"agent": "sentiment_analyzer", "task": "analyze_sentiment"},
                    {"agent": "insight_generator", "task": "generate_insights"},
                    {"agent": "report_generator", "task": "create_report"}
                ],
                "dependencies": [
                    {"step": 1, "depends_on": [0]},
                    {"step": 2, "depends_on": [1]},
                    {"step": 3, "depends_on": [1, 2]}
                ]
            },
            {
                "id": "complex_req_2", 
                "type": "adaptive_skill_chain",
                "description": "Process document with optimal skill selection",
                "input": {"document": "research_paper.pdf"},
                "objectives": ["extract_text", "summarize", "identify_key_concepts", "generate_questions"],
                "optimization_target": "accuracy"
            }
        ]
        
        orchestration_results = {}
        
        for complex_req in complex_requests:
            print(f"   Processing complex request: {complex_req['id']}")
            
            result = await ultimate_orch.process_complex_request(
                request_id=complex_req["id"],
                request_data=complex_req
            )
            
            orchestration_results[complex_req["id"]] = result
            
            print(f"     Workflow status: {result.get('status')}")
            print(f"     Steps completed: {result.get('completed_steps', 0)}/{result.get('total_steps', 0)}")
            print(f"     Optimization score: {result.get('optimization_score', 0):.2%}")
            print(f"     Agents involved: {len(result.get('agents_used', []))}")
        
        # Demonstrate AI-powered routing
        print("🧠 Demonstrating AI-powered routing...")
        
        routing_scenarios = [
            {"input": "I need to analyze some data", "context": "data_science"},
            {"input": "Help me write a report", "context": "documentation"},
            {"input": "Process this image", "context": "computer_vision"}
        ]
        
        for scenario in routing_scenarios:
            routing_decision = await ultimate_orch.ai_route_request(
                user_input=scenario["input"],
                context=scenario["context"]
            )
            
            print(f"   Input: \"{scenario['input']}\"")
            print(f"     Routed to: {routing_decision.get('selected_agent')}")
            print(f"     Confidence: {routing_decision.get('confidence', 0):.2%}")
            print(f"     Reasoning: {routing_decision.get('reasoning')}")
        
        # Advanced metrics and insights
        advanced_metrics = await ultimate_orch.get_advanced_metrics()
        
        print(f"📈 Advanced orchestration metrics:")
        print(f"   AI routing accuracy: {advanced_metrics.get('ai_routing_accuracy', 0):.2%}")
        print(f"   Load balancing efficiency: {advanced_metrics.get('load_balance_efficiency', 0):.2%}")
        print(f"   Predictive scaling hits: {advanced_metrics.get('predictive_scaling_accuracy', 0):.2%}")
        print(f"   Multi-agent coordination success: {advanced_metrics.get('coordination_success_rate', 0):.2%}")
        
    except ImportError:
        print("🚀 Ultimate orchestrator not available, showing conceptual example")
        print("   Would provide:")
        print("   - AI-powered intelligent request routing")
        print("   - Complex multi-agent workflow coordination")
        print("   - Adaptive load balancing and optimization")
        print("   - Predictive scaling and resource management")
    
    print()


async def agent_manager_example():
    """Example of agent manager usage."""

    print("=== Agent Manager Example ===")

    try:
        from app.core.orchestrator.agent_manager import AgentManager
        
        # Create agent manager
        agent_manager = AgentManager()
        
        # Register agents
        print("👥 Registering and managing agents...")
        
        agents_to_register = [
            {
                "id": "agent_weather",
                "name": "Weather Agent",
                "type": "skill_agent",
                "capabilities": ["weather_data", "forecasting", "location_services"],
                "load_capacity": 10,
                "specializations": ["meteorology", "geographic_data"]
            },
            {
                "id": "agent_nlp",
                "name": "NLP Agent", 
                "type": "processing_agent",
                "capabilities": ["text_analysis", "sentiment_analysis", "language_detection"],
                "load_capacity": 15,
                "specializations": ["natural_language", "text_processing"]
            },
            {
                "id": "agent_vision",
                "name": "Vision Agent",
                "type": "ai_agent",
                "capabilities": ["image_analysis", "object_detection", "ocr"],
                "load_capacity": 8,
                "specializations": ["computer_vision", "image_processing"]
            }
        ]
        
        registered_agents = []
        
        for agent_config in agents_to_register:
            result = await agent_manager.register_agent(agent_config)
            
            if result.get('success'):
                registered_agents.append(agent_config)
                print(f"   ✅ Registered: {agent_config['name']}")
                print(f"      Capabilities: {len(agent_config['capabilities'])}")
                print(f"      Load capacity: {agent_config['load_capacity']}")
            else:
                print(f"   ❌ Failed to register: {agent_config['name']}")
        
        # Agent discovery and selection
        print("🔍 Demonstrating agent discovery...")
        
        discovery_queries = [
            {"requirement": "weather_data", "context": "location_based"},
            {"requirement": "text_analysis", "context": "sentiment_processing"},
            {"requirement": "image_analysis", "context": "document_processing"}
        ]
        
        for query in discovery_queries:
            suitable_agents = await agent_manager.discover_agents(
                requirements=[query["requirement"]],
                context=query["context"]
            )
            
            print(f"   Query: {query['requirement']} ({query['context']})")
            print(f"     Suitable agents found: {len(suitable_agents)}")
            
            for agent in suitable_agents:
                print(f"       - {agent.get('name')} (score: {agent.get('suitability_score', 0):.2f})")
        
        # Load balancing demonstration
        print("⚖️ Demonstrating load balancing...")
        
        # Simulate task assignments
        tasks = [
            {"type": "weather_query", "estimated_load": 3},
            {"type": "text_analysis", "estimated_load": 5},
            {"type": "image_processing", "estimated_load": 7},
            {"type": "sentiment_analysis", "estimated_load": 4}
        ]
        
        for task in tasks:
            assignment = await agent_manager.assign_task(
                task_type=task["type"],
                estimated_load=task["estimated_load"]
            )
            
            print(f"   Task: {task['type']} (load: {task['estimated_load']})")
            
            if assignment.get('success'):
                agent_info = assignment.get('assigned_agent', {})
                print(f"     Assigned to: {agent_info.get('name', 'Unknown')}")
                print(f"     Current load: {agent_info.get('current_load', 0)}/{agent_info.get('capacity', 0)}")
            else:
                print(f"     Assignment failed: {assignment.get('reason', 'Unknown')}")
        
        # Agent health monitoring
        health_status = await agent_manager.get_agent_health_status()
        
        print(f"🏥 Agent health monitoring:")
        print(f"   Total agents: {health_status.get('total_agents', 0)}")
        print(f"   Healthy agents: {health_status.get('healthy_agents', 0)}")
        print(f"   Average load: {health_status.get('average_load', 0):.1f}")
        print(f"   Peak capacity utilization: {health_status.get('peak_utilization', 0):.2%}")
        
    except ImportError:
        print("👥 Agent manager not available, showing conceptual example")
        print("   Would provide:")
        print("   - Agent registration and lifecycle management")
        print("   - Intelligent agent discovery and selection")
        print("   - Load balancing and capacity management")
        print("   - Agent health monitoring and optimization")
    
    print()


async def delegation_system_example():
    """Example of delegation system usage."""

    print("=== Delegation System Example ===")

    try:
        from app.core.orchestrator.delegation.delegation_manager import DelegationManager
        
        # Create delegation manager
        delegation_manager = DelegationManager()
        
        # Set up delegation scenarios
        print("📋 Setting up task delegation...")
        
        delegation_scenarios = [
            {
                "task_id": "complex_analysis",
                "description": "Comprehensive data analysis and reporting",
                "complexity": "high",
                "estimated_effort": 240,  # minutes
                "required_skills": ["data_analysis", "visualization", "reporting"],
                "deadline": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "task_id": "content_creation",
                "description": "Create marketing content for new product",
                "complexity": "medium",
                "estimated_effort": 120,
                "required_skills": ["writing", "marketing", "design"],
                "deadline": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "task_id": "system_optimization",
                "description": "Optimize system performance and resource usage",
                "complexity": "high",
                "estimated_effort": 180,
                "required_skills": ["system_admin", "performance_tuning", "monitoring"],
                "deadline": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        delegation_results = {}
        
        for scenario in delegation_scenarios:
            print(f"   Delegating task: {scenario['task_id']}")
            
            delegation_plan = await delegation_manager.create_delegation_plan(
                task=scenario,
                optimization_criteria=["skill_match", "load_balance", "deadline_priority"]
            )
            
            delegation_results[scenario["task_id"]] = delegation_plan
            
            print(f"     Delegation strategy: {delegation_plan.get('strategy')}")
            print(f"     Assigned agents: {len(delegation_plan.get('assigned_agents', []))}")
            print(f"     Estimated completion: {delegation_plan.get('estimated_completion')}")
            print(f"     Success probability: {delegation_plan.get('success_probability', 0):.2%}")
        
        # Task decomposition demonstration
        print("🧩 Demonstrating task decomposition...")
        
        complex_task = {
            "title": "End-to-end customer onboarding automation",
            "description": "Automate the complete customer onboarding process",
            "requirements": [
                "Account creation and validation",
                "Document processing and verification",
                "System setup and configuration",
                "Training material delivery",
                "Follow-up and support scheduling"
            ]
        }
        
        decomposition_result = await delegation_manager.decompose_task(complex_task)
        
        print(f"   Original task: {complex_task['title']}")
        print(f"   Decomposed into: {len(decomposition_result.get('subtasks', []))} subtasks")
        
        for i, subtask in enumerate(decomposition_result.get('subtasks', [])[:3]):  # Show first 3
            print(f"     {i+1}. {subtask.get('title')}")
            print(f"        Skills needed: {', '.join(subtask.get('required_skills', []))}")
            print(f"        Estimated duration: {subtask.get('estimated_duration', 0)} min")
        
        # Delegation monitoring
        print("📊 Monitoring delegation progress...")
        
        monitoring_data = await delegation_manager.get_delegation_status()
        
        print(f"   📈 Delegation metrics:")
        print(f"     Active delegations: {monitoring_data.get('active_delegations', 0)}")
        print(f"     Completion rate: {monitoring_data.get('completion_rate', 0):.2%}")
        print(f"     Average delegation time: {monitoring_data.get('avg_delegation_time', 0):.1f} min")
        print(f"     Skill utilization: {monitoring_data.get('skill_utilization', 0):.2%}")
        
    except ImportError:
        print("📋 Delegation system not available, showing conceptual example")
        print("   Would provide:")
        print("   - Intelligent task decomposition and delegation")
        print("   - Optimal agent assignment based on skills and load")
        print("   - Dynamic task monitoring and rebalancing")
        print("   - Performance tracking and optimization")
    
    print()


async def intent_handling_example():
    """Example of intent handling system."""

    print("=== Intent Handling Example ===")

    try:
        from app.core.orchestrator.intent.intent_classifier import IntentClassifier
        from app.core.orchestrator.intent.intent_router import IntentRouter
        
        # Create intent handling components
        intent_classifier = IntentClassifier()
        intent_router = IntentRouter()
        
        # Initialize intent system
        print("🎯 Initializing intent handling system...")
        
        intent_categories = [
            "information_request",
            "task_execution", 
            "system_control",
            "skill_management",
            "data_processing",
            "troubleshooting"
        ]
        
        await intent_classifier.initialize(intent_categories)
        await intent_router.initialize()
        
        print(f"   ✅ Intent system initialized with {len(intent_categories)} categories")
        
        # Intent classification demonstration
        print("🔍 Demonstrating intent classification...")
        
        user_inputs = [
            "What's the weather like in Stockholm today?",
            "Please analyze the sales data from last quarter",
            "Restart the monitoring service",
            "Install the new weather prediction skill",
            "Why is the system running slowly?",
            "Show me the performance metrics"
        ]
        
        classified_intents = []
        
        for user_input in user_inputs:
            classification = await intent_classifier.classify_intent(user_input)
            
            classified_intents.append({
                "input": user_input,
                "intent": classification.get('intent'),
                "confidence": classification.get('confidence', 0),
                "entities": classification.get('entities', [])
            })
            
            print(f"   Input: \"{user_input}\"")
            print(f"     Intent: {classification.get('intent')}")
            print(f"     Confidence: {classification.get('confidence', 0):.2%}")
            print(f"     Entities: {classification.get('entities', [])}")
        
        # Intent routing demonstration
        print("🚦 Demonstrating intent routing...")
        
        for classified in classified_intents:
            routing_decision = await intent_router.route_intent(
                intent=classified["intent"],
                entities=classified["entities"],
                context={"user_input": classified["input"]}
            )
            
            print(f"   Intent: {classified['intent']}")
            print(f"     Routed to: {routing_decision.get('handler')}")
            print(f"     Action: {routing_decision.get('action')}")
            print(f"     Priority: {routing_decision.get('priority')}")
        
        # Intent learning and adaptation
        print("📚 Demonstrating intent learning...")
        
        # Simulate feedback for intent improvements
        feedback_data = [
            {"input": user_inputs[0], "predicted_intent": "information_request", "actual_intent": "information_request", "satisfaction": "high"},
            {"input": user_inputs[1], "predicted_intent": "data_processing", "actual_intent": "data_processing", "satisfaction": "high"},
            {"input": user_inputs[2], "predicted_intent": "system_control", "actual_intent": "system_control", "satisfaction": "medium"}
        ]
        
        for feedback in feedback_data:
            await intent_classifier.learn_from_feedback(
                user_input=feedback["input"],
                predicted_intent=feedback["predicted_intent"],
                actual_intent=feedback["actual_intent"],
                satisfaction_level=feedback["satisfaction"]
            )
        
        # Get intent analytics
        intent_analytics = await intent_classifier.get_intent_analytics()
        
        print(f"   📊 Intent analytics:")
        print(f"     Classification accuracy: {intent_analytics.get('accuracy', 0):.2%}")
        print(f"     Most common intent: {intent_analytics.get('most_common_intent')}")
        print(f"     Learning improvement: {intent_analytics.get('learning_improvement', 0):.2%}")
        
    except ImportError:
        print("🎯 Intent handling system not available, showing conceptual example")
        print("   Would provide:")
        print("   - Intelligent user intent classification")
        print("   - Dynamic intent routing to appropriate handlers")
        print("   - Continuous learning from user feedback")
        print("   - Intent analytics and optimization")
    
    print()


async def mcp_integration_example():
    """Example of MCP integration in orchestration."""

    print("=== MCP Integration Example ===")

    try:
        from app.core.orchestrator.mcp.mcp_orchestrator import MCPOrchestrator
        
        # Create MCP orchestrator
        mcp_orchestrator = MCPOrchestrator()
        
        # Initialize MCP integration
        print("🔗 Initializing MCP integration...")
        
        mcp_config = {
            "enabled_servers": ["file_manager", "database_connector", "api_client"],
            "load_balancing": True,
            "failover_enabled": True,
            "monitoring_enabled": True
        }
        
        await mcp_orchestrator.initialize(mcp_config)
        
        print(f"   ✅ MCP integration initialized")
        print(f"   Enabled servers: {len(mcp_config['enabled_servers'])}")
        
        # MCP server discovery
        print("🔍 Discovering MCP servers...")
        
        available_servers = await mcp_orchestrator.discover_mcp_servers()
        
        print(f"   📊 MCP server discovery:")
        for server in available_servers:
            print(f"     - {server.get('name')}: {server.get('status')}")
            print(f"       Capabilities: {', '.join(server.get('capabilities', []))}")
            print(f"       Load: {server.get('current_load', 0):.1f}%")
        
        # MCP request orchestration
        print("🎼 Orchestrating MCP requests...")
        
        mcp_requests = [
            {
                "type": "file_operation",
                "operation": "read_file",
                "parameters": {"file_path": "/data/sample.txt"},
                "target_server": "file_manager"
            },
            {
                "type": "database_query",
                "operation": "select_data",
                "parameters": {"table": "users", "filter": "active=true"},
                "target_server": "database_connector"
            },
            {
                "type": "api_call",
                "operation": "get_weather",
                "parameters": {"location": "Stockholm", "units": "metric"},
                "target_server": "api_client"
            }
        ]
        
        mcp_results = []
        
        for request in mcp_requests:
            print(f"   Processing MCP request: {request['type']}")
            
            result = await mcp_orchestrator.execute_mcp_request(
                request_type=request["type"],
                operation=request["operation"],
                parameters=request["parameters"],
                preferred_server=request["target_server"]
            )
            
            mcp_results.append(result)
            
            print(f"     Status: {result.get('status')}")
            print(f"     Server used: {result.get('server_used')}")
            print(f"     Execution time: {result.get('execution_time', 0):.2f}s")
        
        # MCP load balancing demonstration
        print("⚖️ Demonstrating MCP load balancing...")
        
        # Simulate multiple concurrent requests
        concurrent_requests = [
            {"type": "file_operation", "server_preference": "auto"},
            {"type": "file_operation", "server_preference": "auto"},
            {"type": "database_query", "server_preference": "auto"},
            {"type": "api_call", "server_preference": "auto"}
        ]
        
        load_balance_results = await mcp_orchestrator.execute_concurrent_requests(
            concurrent_requests,
            load_balance=True
        )
        
        print(f"   📊 Load balancing results:")
        print(f"     Requests processed: {len(load_balance_results)}")
        
        # Group by server
        server_usage = {}
        for result in load_balance_results:
            server = result.get('server_used', 'unknown')
            server_usage[server] = server_usage.get(server, 0) + 1
        
        for server, count in server_usage.items():
            print(f"     {server}: {count} requests")
        
        # MCP monitoring and health
        mcp_health = await mcp_orchestrator.get_mcp_health_status()
        
        print(f"   🏥 MCP health status:")
        print(f"     Total servers: {mcp_health.get('total_servers', 0)}")
        print(f"     Healthy servers: {mcp_health.get('healthy_servers', 0)}")
        print(f"     Average response time: {mcp_health.get('avg_response_time', 0):.2f}s")
        print(f"     Total requests processed: {mcp_health.get('total_requests', 0)}")
        
    except ImportError:
        print("🔗 MCP integration not available, showing conceptual example")
        print("   Would provide:")
        print("   - Seamless MCP server integration and orchestration")
        print("   - Intelligent load balancing across MCP servers")
        print("   - Automatic failover and error recovery")
        print("   - Real-time monitoring and health management")
    
    print()


async def integrated_orchestration_workflow_example():
    """Example of integrated orchestration workflow."""

    print("=== Integrated Orchestration Workflow Example ===")

    print("🎼 Comprehensive orchestration workflow demonstration...")
    
    # Simulate a complete orchestration workflow
    workflow_description = "Customer service automation with multi-agent coordination"
    
    workflow_components = [
        ("🎼 Basic Orchestration", "Initialize request processing pipeline"),
        ("🚀 Ultimate Orchestration", "Apply AI-powered optimization"),
        ("👥 Agent Management", "Coordinate multiple specialized agents"),
        ("📋 Task Delegation", "Distribute work optimally"),
        ("🎯 Intent Processing", "Understand and route customer requests"),
        ("🔗 MCP Integration", "Leverage external services and data")
    ]
    
    print(f"📋 Workflow: {workflow_description}")
    print(f"🔄 Workflow components:")
    
    workflow_metrics = {}
    
    for component_name, component_description in workflow_components:
        print(f"\n{component_name}")
        print(f"   {component_description}")
        
        # Simulate processing
        await asyncio.sleep(0.3)
        
        # Mock metrics for each component
        if "Basic" in component_name:
            workflow_metrics["basic"] = {
                "requests_processed": 50,
                "success_rate": 0.94,
                "avg_response_time": 1.2
            }
            print(f"   ✅ Processed {workflow_metrics['basic']['requests_processed']} requests")
            
        elif "Ultimate" in component_name:
            workflow_metrics["ultimate"] = {
                "optimization_applied": True,
                "performance_gain": 0.35,
                "ai_routing_accuracy": 0.91
            }
            print(f"   ✅ Performance gain: {workflow_metrics['ultimate']['performance_gain']:.2%}")
            
        elif "Agent" in component_name:
            workflow_metrics["agents"] = {
                "agents_coordinated": 8,
                "load_balance_efficiency": 0.87,
                "coordination_success": 0.95
            }
            print(f"   ✅ Coordinated {workflow_metrics['agents']['agents_coordinated']} agents")
            
        elif "Delegation" in component_name:
            workflow_metrics["delegation"] = {
                "tasks_delegated": 25,
                "optimal_assignments": 0.89,
                "completion_rate": 0.92
            }
            print(f"   ✅ Delegated {workflow_metrics['delegation']['tasks_delegated']} tasks")
            
        elif "Intent" in component_name:
            workflow_metrics["intent"] = {
                "intents_classified": 50,
                "classification_accuracy": 0.93,
                "routing_success": 0.96
            }
            print(f"   ✅ Classified {workflow_metrics['intent']['intents_classified']} intents")
            
        elif "MCP" in component_name:
            workflow_metrics["mcp"] = {
                "mcp_requests": 15,
                "server_utilization": 0.78,
                "integration_success": 0.97
            }
            print(f"   ✅ Processed {workflow_metrics['mcp']['mcp_requests']} MCP requests")
    
    # Calculate overall workflow metrics
    print(f"\n📊 Integrated Workflow Results:")
    
    total_requests = workflow_metrics.get('basic', {}).get('requests_processed', 0)
    overall_success_rate = sum([
        workflow_metrics.get('basic', {}).get('success_rate', 0),
        workflow_metrics.get('delegation', {}).get('completion_rate', 0),
        workflow_metrics.get('intent', {}).get('routing_success', 0),
        workflow_metrics.get('mcp', {}).get('integration_success', 0)
    ]) / 4
    
    performance_improvement = workflow_metrics.get('ultimate', {}).get('performance_gain', 0)
    
    print(f"   Total requests processed: {total_requests}")
    print(f"   Overall success rate: {overall_success_rate:.2%}")
    print(f"   Performance improvement: {performance_improvement:.2%}")
    print(f"   Agents coordinated: {workflow_metrics.get('agents', {}).get('agents_coordinated', 0)}")
    print(f"   Tasks delegated: {workflow_metrics.get('delegation', {}).get('tasks_delegated', 0)}")
    print(f"   AI routing accuracy: {workflow_metrics.get('ultimate', {}).get('ai_routing_accuracy', 0):.2%}")
    
    print("✅ Integrated orchestration workflow completed successfully!")
    print()


async def run_all_orchestrator_examples():
    """Run all orchestrator component examples."""
    
    print("🎼 Starting Orchestrator Components Examples")
    print("=" * 50)
    
    try:
        await basic_orchestrator_example()
        await ultimate_orchestrator_example()
        await agent_manager_example()
        await delegation_system_example()
        await intent_handling_example()
        await mcp_integration_example()
        await integrated_orchestration_workflow_example()
        
        print("✅ All orchestrator components examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Orchestrator components examples failed: {e}")
        print(f"❌ Examples failed: {e}")


# Convenience functions for quick demonstrations
async def quick_orchestrator_demo():
    """Quick demonstration of orchestrator capabilities."""
    
    print("🎯 Quick Orchestrator Components Demo")
    print("-" * 40)
    
    components = [
        "🎼 Basic Orchestrator",
        "🚀 Ultimate Orchestrator", 
        "👥 Agent Manager",
        "📋 Task Delegation",
        "🎯 Intent Handling",
        "🔗 MCP Integration"
    ]
    
    print("🌟 Available orchestrator components:")
    for component in components:
        print(f"   {component}")
    
    print(f"\n📊 Demo capabilities:")
    print(f"   Components: {len(components)}")
    print(f"   Orchestration level: Advanced")
    print(f"   AI integration: Full")
    
    print("✅ Quick demo completed!")


async def setup_orchestrator_development_environment():
    """Setup orchestrator development environment."""
    
    print("🛠️ Setting up Orchestrator Development Environment")
    print("-" * 50)
    
    setup_steps = [
        ("🎼 Initialize basic orchestration", "Set up request processing"),
        ("🚀 Configure ultimate orchestrator", "Enable AI-powered features"),
        ("👥 Setup agent management", "Configure agent coordination"),
        ("📋 Enable task delegation", "Set up intelligent task distribution"),
        ("🎯 Configure intent handling", "Set up intent classification and routing"),
        ("🔗 Initialize MCP integration", "Connect external services")
    ]
    
    for step_name, description in setup_steps:
        print(f"   {step_name}: {description}")
        await asyncio.sleep(0.2)  # Simulate setup
    
    print(f"\n✅ Orchestrator development environment ready!")
    print(f"   Use individual examples to explore each component")
    print(f"   Run integrated workflow for complete orchestration automation")


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_orchestrator_examples())