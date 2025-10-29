# A2A Protocol - Secure Agent-to-Agent Communication for HappyOS

The **A2A Protocol** (Agent-to-Agent Protocol) provides a comprehensive framework for secure, scalable, and intelligent communication between autonomous agents in HappyOS. This implementation is based on the Felicia's Finance A2A Protocol specification and adapted for HappyOS's "Replicator" architecture.

## 🎯 Overview

The A2A Protocol enables HappyOS agents to:
- **Communicate securely** using RSA-2048 encryption and X.509 certificates
- **Discover each other** through capability-based service discovery
- **Orchestrate workflows** across multiple specialized agents
- **Self-heal and monitor** system health and performance
- **Scale dynamically** with automatic agent creation and management

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Agent Svea    │───▶│  A2A Protocol    │───▶│  Specialized    │
│  (Interface)    │    │  Manager         │    │  Agents         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
        │ Identity Mgr │ │ Message Mgr │ │ Transport  │
        │ (RSA/X.509)  │ │ (AES-GCM)   │ │ Layer      │
        └──────────────┘ └─────────────┘ └────────────┘
        ┌──────────────┐ ┌──────────────┐ ┌────────────┐
        │ Discovery    │ │ Auth Manager │ │ Workflow   │
        │ Service      │ │ (JWT/OAuth)  │ │ Orchestr.  │
        └──────────────┘ └──────────────┘ └────────────┘
```

## 🚀 Key Features

### 🔐 Security First
- **RSA-2048 key pairs** for agent identity
- **X.509 certificates** for mutual authentication
- **AES-256-GCM encryption** for message confidentiality
- **JWT tokens** for stateless authorization
- **Mutual TLS** for transport security

### 🤖 Agent Management
- **Dynamic agent creation** using Self-Builder patterns
- **Specialized agent types** (Architect, Product Manager, QA, etc.)
- **Capability-based discovery** and routing
- **Health monitoring** and automatic recovery
- **Performance tracking** and optimization

### 🔄 Workflow Orchestration
- **Multi-agent workflows** with dependency management
- **Task prioritization** and scheduling
- **Event-driven communication** between agents
- **Automatic failover** and error recovery

## 📦 Installation & Setup

### 1. Initialize A2A Protocol Manager

```python
from app.a2a_protocol.core.orchestrator import a2a_protocol_manager

# Initialize the protocol manager
success = await a2a_protocol_manager.initialize()
if success:
    print("A2A Protocol initialized successfully!")
```

### 2. Create Agent Identity

```python
from app.a2a_protocol.core.identity import identity_manager

# Generate identity for your agent
identity = identity_manager.generate_agent_identity(
    agent_id="my_agent",
    common_name="My HappyOS Agent",
    organization="HappyOS"
)
print(f"Generated certificate with fingerprint: {identity['certificate_fingerprint']}")
```

### 3. Register Agent Capabilities

```python
from app.a2a_protocol.core.discovery import discovery_service
from app.a2a_protocol.core.constants import AgentCapability

# Register agent with capabilities
await discovery_service.register_agent(
    agent_id="my_agent",
    capabilities=[AgentCapability.GENERAL, AgentCapability.ANALYSIS],
    metadata={"version": "1.0", "domain": "general"}
)
```

## 💻 Usage Examples

### Basic Agent Communication

```python
# Create and send a message
from_agent = "my_agent"
to_agent = "analysis_agent"
action = "analyze_data"
parameters = {"data": "some data to analyze"}

result = await a2a_protocol_manager.send_message(
    from_agent, to_agent, action, parameters
)

if result["success"]:
    print(f"Analysis result: {result['response']}")
else:
    print(f"Error: {result['error']}")
```

### Agent Discovery

```python
# Find agents with specific capabilities
agents = await discovery_service.discover_agents(
    capability=AgentCapability.ANALYSIS,
    min_agents=1
)

for agent in agents:
    print(f"Found analysis agent: {agent['agent_id']}")
```

### Workflow Creation and Execution

```python
# Create a multi-step workflow
workflow_id = await a2a_protocol_manager.create_workflow(
    "Data Processing Pipeline",
    "Process and analyze financial data",
    [
        {
            "type": "agent_task",
            "agent_id": "data_collector",
            "action": "collect_data",
            "parameters": {"source": "api"}
        },
        {
            "type": "agent_task",
            "agent_id": "analyzer",
            "action": "analyze_data",
            "parameters": {"algorithm": "ml"}
        },
        {
            "type": "agent_task",
            "agent_id": "reporter",
            "action": "generate_report",
            "parameters": {"format": "pdf"}
        }
    ]
)

# Execute the workflow
result = await a2a_protocol_manager.execute_workflow(workflow_id)
print(f"Workflow completed: {result['success']}")
```

### Specialized Agent Types

#### Architect Agent

```python
# Create an architect agent for technical design
architect = await a2a_protocol_manager.create_agent(
    "architect",
    "technical_architect",
    [AgentCapability.ORCHESTRATION, AgentCapability.CODING],
    description="Technical architect for system design"
)

# Request technical design
design_result = await a2a_protocol_manager.send_message(
    "user_interface",
    "technical_architect",
    "design_system",
    {"requirements": "Build a financial analysis system"}
)
```

#### Self-Building Agent

```python
# Create a self-building agent for dynamic agent creation
builder = await a2a_protocol_manager.create_agent(
    "self_builder",
    "dynamic_builder",
    [AgentCapability.SELF_BUILDING, AgentCapability.CODING],
    description="Dynamic agent creation and deployment"
)

# Generate a new specialized agent
new_agent = await a2a_protocol_manager.send_message(
    "user_interface",
    "dynamic_builder",
    "generate_agent",
    {
        "agent_type": "crypto_analyzer",
        "capabilities": ["crypto", "analysis"],
        "domain": "cryptocurrency"
    }
)
```

#### Monitoring Agent

```python
# Create a monitoring agent for health tracking
monitor = await a2a_protocol_manager.create_agent(
    "monitor",
    "health_monitor",
    [AgentCapability.MONITORING, AgentCapability.ANALYSIS],
    description="System health and performance monitoring"
)

# Get system health report
health_report = await a2a_protocol_manager.send_message(
    "user_interface",
    "health_monitor",
    "get_health_report",
    {"include_details": True}
)
```

## 🔧 Configuration

### Environment Variables

```bash
# Basic Configuration
export A2A_PROTOCOL_VERSION="1.0.0"
export A2A_PORT="8443"
export A2A_TLS_CERT_FILE="/path/to/cert.pem"
export A2A_TLS_KEY_FILE="/path/to/key.pem"
export A2A_STORAGE_PATH="./data/a2a"

# Security Configuration
export A2A_ENABLE_TLS="true"
export A2A_ENABLE_HTTP2="true"
export A2A_ENABLE_DISCOVERY="true"
export A2A_DISCOVERY_URL="https://discovery.happyos.local"

# Performance Configuration
export A2A_MAX_MESSAGE_SIZE="10485760"  # 10MB
export A2A_MESSAGE_TIMEOUT="30"
export A2A_MAX_CONNECTIONS="1000"
```

### Programmatic Configuration

```python
from app.a2a_protocol.core.orchestrator import A2AProtocolManager
from app.a2a_protocol.core.transport import TransportConfig

# Configure transport layer
transport_config = TransportConfig(
    host="0.0.0.0",
    port=8443,
    enable_tls=True,
    cert_file="/path/to/server.crt",
    key_file="/path/to/server.key",
    enable_http2=True,
    enable_websocket_fallback=True
)

# Create protocol manager with custom config
config = {
    "max_workflows": 100,
    "enable_health_monitoring": True,
    "enable_metrics_collection": True
}

protocol_manager = A2AProtocolManager(config=config)
await protocol_manager.initialize()
```

## 🔍 API Reference

### A2AProtocolManager

Main coordinator for the A2A Protocol system.

#### Methods

- `initialize()` - Initialize the protocol manager
- `shutdown()` - Shutdown the protocol manager gracefully
- `create_agent(agent_type, agent_id, capabilities, **kwargs)` - Create a new agent
- `send_message(from_agent, to_agent, action, parameters)` - Send message between agents
- `broadcast_message(from_agent, action, parameters, capability_filter)` - Broadcast to multiple agents
- `create_workflow(name, description, steps)` - Create a workflow
- `execute_workflow(workflow_id)` - Execute a workflow
- `get_system_status()` - Get comprehensive system status
- `health_check()` - Perform health check

### IdentityManager

Manages cryptographic identities for agents.

#### Key Features

- RSA-2048 key pair generation
- X.509 certificate management
- Certificate rotation and renewal
- Identity persistence and caching

### MessageManager

Handles secure message processing.

#### Features

- AES-256-GCM message encryption
- Message compression and validation
- Batch message processing
- Response correlation

### DiscoveryService

Provides agent discovery and service registry.

#### Capabilities

- Agent registration and discovery
- Capability-based agent finding
- Health monitoring and cleanup
- External registry integration

### TransportLayer

Manages secure communication transport.

#### Protocols

- HTTP/2 primary protocol
- WebSocket fallback
- TLS 1.3 encryption
- Connection pooling and health monitoring

## 🧪 Testing

### Basic Protocol Test

```python
import asyncio
from app.a2a_protocol.core.orchestrator import a2a_protocol_manager

async def test_a2a_protocol():
    # Initialize system
    success = await a2a_protocol_manager.initialize()
    assert success, "A2A Protocol initialization failed"

    # Create test agents
    agent1 = await a2a_protocol_manager.create_agent(
        "base", "test_agent_1",
        [AgentCapability.GENERAL],
        description="Test agent 1"
    )

    agent2 = await a2a_protocol_manager.create_agent(
        "base", "test_agent_2",
        [AgentCapability.ANALYSIS],
        description="Test agent 2"
    )

    # Test message sending
    result = await a2a_protocol_manager.send_message(
        "test_agent_1", "test_agent_2",
        "test_action", {"data": "hello"}
    )

    assert result["success"], f"Message send failed: {result['error']}"

    # Get system status
    status = await a2a_protocol_manager.get_system_status()
    print(f"System status: {status}")

    # Shutdown
    await a2a_protocol_manager.shutdown()

# Run test
asyncio.run(test_a2a_protocol())
```

### Load Testing

```python
import asyncio
import time

async def load_test():
    # Initialize system
    await a2a_protocol_manager.initialize()

    # Create multiple agents
    agents = []
    for i in range(10):
        agent = await a2a_protocol_manager.create_agent(
            "base", f"load_agent_{i}",
            [AgentCapability.GENERAL],
            description=f"Load test agent {i}"
        )
        agents.append(agent)

    # Send concurrent messages
    start_time = time.time()

    tasks = []
    for i in range(100):
        from_agent = f"load_agent_{i % 10}"
        to_agent = f"load_agent_{(i + 1) % 10}"

        task = a2a_protocol_manager.send_message(
            from_agent, to_agent,
            "load_test", {"message_id": i}
        )
        tasks.append(task)

    # Wait for all messages to complete
    results = await asyncio.gather(*tasks)

    end_time = time.time()
    successful_messages = sum(1 for r in results if r["success"])

    print(f"Load test completed in {end_time - start_time".2f"}s")
    print(f"Successful messages: {successful_messages}/{len(results)}")

    await a2a_protocol_manager.shutdown()

# Run load test
asyncio.run(load_test())
```

## 🔒 Security Considerations

### Production Deployment

1. **Certificate Management**
   ```bash
   # Generate proper certificates for production
   openssl req -x509 -newkey rsa:2048 -keyout a2a-key.pem -out a2a-cert.pem -days 365 -nodes
   ```

2. **Secure Configuration**
   ```python
   # Use strong secrets in production
   import secrets
   jwt_secret = secrets.token_hex(32)

   # Configure proper TLS
   transport_config = TransportConfig(
       enable_tls=True,
       cert_file="/etc/ssl/certs/a2a-server.crt",
       key_file="/etc/ssl/private/a2a-server.key",
       ca_cert_file="/etc/ssl/certs/ca.crt"
   )
   ```

3. **Network Security**
   - Use proper firewall rules
   - Implement rate limiting
   - Monitor for suspicious activity
   - Regular security audits

### Best Practices

- **Key Rotation**: Rotate agent certificates regularly (90-day intervals)
- **Access Control**: Implement capability-based authorization
- **Audit Logging**: Log all authentication and authorization events
- **Network Segmentation**: Separate A2A traffic from user traffic
- **Monitoring**: Monitor for security events and anomalies

## 📊 Monitoring & Observability

### Health Checks

```python
# Get comprehensive health status
health = await a2a_protocol_manager.health_check()
print(f"Overall status: {health['overall_status']}")

# Check individual components
for component, status in health['components'].items():
    print(f"{component}: {status}")
```

### Performance Metrics

```python
# Get system status with performance metrics
status = await a2a_protocol_manager.get_system_status()

# Agent performance
for agent_id, agent_info in status['agents']['details'].items():
    perf_stats = agent_info.get('performance_stats', {})
    print(f"Agent {agent_id}: {perf_stats['messages_processed']} messages processed")

# Transport statistics
transport_stats = status['services']['transport_layer']
print(f"Messages sent: {transport_stats['transport_stats']['messages_sent']}")
```

### Logging

The A2A Protocol uses structured logging with the following levels:
- **DEBUG**: Detailed operation information
- **INFO**: General operational messages
- **WARNING**: Warning conditions
- **ERROR**: Error conditions
- **CRITICAL**: Critical errors requiring immediate attention

## 🚨 Troubleshooting

### Common Issues

#### 1. Certificate Errors
```
Error: Certificate verification failed
Solution: Ensure all agents use certificates signed by the same CA
```

#### 2. Connection Timeouts
```
Error: Message timeout after 30s
Solution: Check network connectivity and agent availability
```

#### 3. Discovery Failures
```
Error: Agent not found in registry
Solution: Verify agent registration and discovery service health
```

#### 4. Authentication Failures
```
Error: Token validation failed
Solution: Check JWT secret configuration and token expiration
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging

# Enable debug logging
logging.getLogger('app.a2a_protocol').setLevel(logging.DEBUG)

# Initialize with debug output
await a2a_protocol_manager.initialize()
```

## 🤝 Integration with HappyOS

### Existing Component Integration

The A2A Protocol integrates seamlessly with existing HappyOS components:

```python
# Integration with Analysis & Task Engine
from app.core.agent.analysis_task_engine import analysis_task_engine

# Register A2A message handlers
await a2a_client.register_message_handler(
    "analyze_request",
    analysis_task_engine.analyze_user_intent
)

# Integration with Ultimate Orchestrator
from app.core.orchestrator.ultimate_orchestrator import ultimate_orchestrator

# Use A2A for inter-agent communication
result = await a2a_protocol_manager.send_message(
    "analysis_engine", "ultimate_orchestrator",
    "process_task", {"task_data": task_info}
)
```

### Agent Svea Integration

```python
# Agent Svea uses A2A Protocol for communication
class AgentSvea:
    def __init__(self):
        self.a2a_client = A2AClient(
            "agent_svea",
            [AgentCapability.GENERAL, AgentCapability.ORCHESTRATION]
        )

    async def process_user_request(self, user_input: str):
        # Analyze request using A2A
        analysis_result = await self.a2a_client.send_message(
            "analysis_agent", "analyze_intent",
            {"user_input": user_input}
        )

        # Create workflow if needed
        if analysis_result["requires_workflow"]:
            workflow_id = await self.a2a_client.create_workflow(
                "User Request Processing",
                f"Process user request: {user_input[:50]}",
                analysis_result["workflow_steps"]
            )

        return analysis_result
```

## 🔮 Future Enhancements

### Planned Features

- **Multi-Party Communication**: Group messaging and consensus protocols
- **Advanced Workflow Engine**: Visual workflow designer and complex orchestration
- **Machine Learning Integration**: AI-powered agent optimization
- **Blockchain Integration**: Decentralized identity and consensus
- **Edge Computing Support**: Distributed agent deployment
- **Advanced Monitoring**: Predictive analytics and anomaly detection

### Extension Points

The A2A Protocol is designed for extensibility:

```python
# Custom transport protocol
class CustomTransport(TransportLayer):
    async def send_custom_message(self, message):
        # Implement custom transport logic
        pass

# Custom agent type
class CustomAgent(A2AAgent):
    async def process_message(self, message):
        # Implement custom agent logic
        pass

# Custom authentication method
class CustomAuth(AuthenticationManager):
    def validate_custom_token(self, token):
        # Implement custom validation
        pass
```

## 📚 Additional Resources

- [A2A Protocol Specification](../../docs/A2A_PROTOCOL.md)
- [HappyOS Architecture Documentation](../../docs/architecture/)
- [Integration Examples](../../examples/)
- [API Reference](https://happyos-a2a-api.readthedocs.io/)

## 🆘 Support

For issues, questions, or contributions:

1. Check the [troubleshooting guide](#troubleshooting)
2. Review the [integration examples](../../examples/)
3. Open an issue in the HappyOS repository
4. Contact the HappyOS development team

---

**HappyOS A2A Protocol v1.0.0** - Secure, Scalable, Intelligent Agent Communication 🚀