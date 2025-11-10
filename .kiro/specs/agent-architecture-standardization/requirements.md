# Requirements Document

## Introduction

This specification defines the standardization of the HappyOS agent architecture to ensure all agents (Agent Svea, Felicia's Finance, and MeetMind) follow a consistent pattern for initialization, service access, circuit breakers, A2A communication, and self-building integration. The goal is to create a base class (BaseMCPServer) that encapsulates common functionality while allowing agents to focus solely on their domain-specific business logic.

## Glossary

- **BaseMCPServer**: Base class that all HappyOS MCP agents inherit from, providing standardized initialization and service access patterns
- **MCP (Model Context Protocol)**: Protocol for agent-to-agent communication in the HappyOS system
- **A2A (Agent-to-Agent)**: Communication protocol for inter-agent messaging
- **Service Facade**: Abstraction layer providing unified access to backend services (database, storage, compute, cache, search, LLM)
- **Circuit Breaker**: Resilience pattern that prevents cascading failures by detecting and handling service failures
- **Self-Building Integration**: System capability allowing agents to discover and interact with the self-building agent for autonomous improvements
- **HappyOS SDK**: Software development kit providing standardized interfaces for agent development
- **Agent Svea**: Swedish compliance and ERP integration agent
- **Felicia's Finance**: Financial services and cryptocurrency trading agent
- **MeetMind**: Meeting intelligence and summarization agent
- **Domain-Specific Logic**: Business logic unique to each agent's specialized function

## Requirements

### Requirement 1: Base Class Architecture

**User Story:** As a system architect, I want a standardized base class for all MCP agents, so that common functionality is centralized and agents maintain consistent behavior.

#### Acceptance Criteria

1. WHEN THE BaseMCPServer class is created, THE System SHALL provide a base class in `backend/agents/shared/base_mcp_server.py`
2. WHEN an agent inherits from BaseMCPServer, THE System SHALL provide standardized initialization methods for MCP client, A2A client, service facades, circuit breakers, and self-building integration
3. WHEN BaseMCPServer initializes, THE System SHALL create service facades for database, storage, compute, cache, search, and LLM services
4. WHEN BaseMCPServer initializes circuit breakers, THE System SHALL configure circuit breakers for all service types with appropriate failure thresholds and recovery timeouts
5. WHEN BaseMCPServer provides health status, THE System SHALL return standardized health information including circuit breaker states, service availability, and self-building agent status

### Requirement 2: Service Access Standardization

**User Story:** As an agent developer, I want all agents to access backend services through the same service facade pattern, so that service integration is consistent and maintainable.

#### Acceptance Criteria

1. WHEN an agent needs database access, THE System SHALL provide access through `self.services["database"]` facade
2. WHEN an agent needs storage access, THE System SHALL provide access through `self.services["storage"]` facade
3. WHEN an agent needs compute access, THE System SHALL provide access through `self.services["compute"]` facade
4. WHEN an agent needs cache access, THE System SHALL provide access through `self.services["cache"]` facade
5. WHEN an agent needs search access, THE System SHALL provide access through `self.services["search"]` facade
6. WHEN an agent needs LLM access, THE System SHALL provide access through `self.services["llm"]` facade
7. WHEN service facades are created, THE System SHALL use only HappyOS SDK imports without any direct `backend.*` imports

### Requirement 3: Circuit Breaker Standardization

**User Story:** As a reliability engineer, I want all agents to implement circuit breakers consistently, so that service failures are handled gracefully and system resilience is maintained.

#### Acceptance Criteria

1. WHEN BaseMCPServer initializes, THE System SHALL create circuit breakers for each service type (database, storage, compute, cache, search, LLM)
2. WHEN a circuit breaker is configured, THE System SHALL set appropriate failure thresholds between 2 and 5 failures
3. WHEN a circuit breaker is configured, THE System SHALL set recovery timeout between 30 and 120 seconds based on service criticality
4. WHEN an agent calls a protected service, THE System SHALL execute the call through the appropriate circuit breaker
5. WHEN a circuit breaker opens due to failures, THE System SHALL prevent further calls and return failure responses immediately

### Requirement 4: MeetMind Refactoring

**User Story:** As a system architect, I want MeetMind to use the same standardized patterns as Agent Svea and Felicia's Finance, so that all agents have consistent architecture.

#### Acceptance Criteria

1. WHEN MeetMind is refactored, THE System SHALL inherit from BaseMCPServer class
2. WHEN MeetMind accesses LLM services, THE System SHALL use `self.services["llm"]` instead of direct BedrockMeetingClient
3. WHEN MeetMind accesses database services, THE System SHALL use `self.services["database"]` instead of direct MeetingMemoryService
4. WHEN MeetMind initializes, THE System SHALL use the standardized initialization process from BaseMCPServer
5. WHEN MeetMind implements tools, THE System SHALL maintain all existing meeting intelligence functionality (summarization, action items, persona views)

### Requirement 5: A2A Communication Standardization

**User Story:** As an agent developer, I want standardized A2A communication patterns, so that agents can communicate reliably and consistently.

#### Acceptance Criteria

1. WHEN BaseMCPServer initializes, THE System SHALL create an A2A client for inter-agent communication
2. WHEN an agent sends an A2A message, THE System SHALL use the standardized MCP client interface
3. WHEN an agent receives an A2A message, THE System SHALL handle it through registered message handlers
4. WHEN an agent uses reply-to semantics, THE System SHALL send async callbacks through the MCP client
5. WHEN A2A communication fails, THE System SHALL handle errors through the circuit breaker pattern

### Requirement 6: Self-Building Integration Standardization

**User Story:** As a system operator, I want all agents to integrate with the self-building agent consistently, so that autonomous improvements work uniformly across the system.

#### Acceptance Criteria

1. WHEN BaseMCPServer initializes, THE System SHALL discover the self-building agent through SelfBuildingAgentDiscovery
2. WHEN BaseMCPServer initializes, THE System SHALL create an AgentMetricsCollector for metrics collection
3. WHEN an agent reports health status, THE System SHALL include self-building agent discovery status
4. WHEN an agent collects metrics, THE System SHALL use the standardized metrics collector
5. WHEN self-building integration fails, THE System SHALL log warnings without preventing agent initialization

### Requirement 7: Domain-Specific Logic Isolation

**User Story:** As an agent developer, I want domain-specific logic clearly separated from infrastructure code, so that business logic is easy to understand and modify.

#### Acceptance Criteria

1. WHEN Agent Svea implements tools, THE System SHALL contain only Swedish compliance logic (BAS validation, ERPNext sync, GDPR compliance)
2. WHEN Felicia's Finance implements tools, THE System SHALL contain only financial services logic (crypto trading, portfolio optimization, risk assessment)
3. WHEN MeetMind implements tools, THE System SHALL contain only meeting intelligence logic (summarization, action items, persona views)
4. WHEN agents are refactored, THE System SHALL move domain-specific logic to `services/` subdirectories
5. WHEN agents inherit from BaseMCPServer, THE System SHALL eliminate all duplicated infrastructure code

### Requirement 8: Import Strategy Standardization

**User Story:** As a system architect, I want all agents to use only HappyOS SDK imports, so that agents are properly isolated from backend implementation details.

#### Acceptance Criteria

1. WHEN an agent imports dependencies, THE System SHALL use only `happyos_sdk` imports for infrastructure services
2. WHEN an agent needs MCP functionality, THE System SHALL import from `happyos_sdk` (create_mcp_client, MCPHeaders, MCPResponse, MCPTool)
3. WHEN an agent needs A2A functionality, THE System SHALL import from `happyos_sdk` (create_a2a_client, A2AClient)
4. WHEN an agent needs service facades, THE System SHALL import from `happyos_sdk` (create_service_facades, DatabaseFacade, StorageFacade, ComputeFacade)
5. WHEN an agent needs circuit breakers, THE System SHALL import from `happyos_sdk` (get_circuit_breaker, CircuitBreakerConfig)
6. WHEN agents are refactored, THE System SHALL remove all direct `backend.*` imports

### Requirement 9: Registry Integration Standardization

**User Story:** As a system operator, I want consistent agent registry integration, so that agent discovery and health checks work uniformly.

#### Acceptance Criteria

1. WHEN BaseMCPServer initializes, THE System SHALL register the agent with the agent registry
2. WHEN an agent provides capabilities, THE System SHALL register capabilities through the standardized registry interface
3. WHEN the registry queries agent health, THE System SHALL return standardized health status from BaseMCPServer
4. WHEN an agent updates its status, THE System SHALL use the standardized registry update methods
5. WHEN registry integration fails, THE System SHALL log errors without preventing agent operation

### Requirement 10: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive tests for the standardized architecture, so that refactoring maintains system reliability.

#### Acceptance Criteria

1. WHEN BaseMCPServer is tested, THE System SHALL verify initialization of all components (MCP client, A2A client, service facades, circuit breakers)
2. WHEN service facades are tested, THE System SHALL verify access to all service types (database, storage, compute, cache, search, LLM)
3. WHEN circuit breakers are tested, THE System SHALL verify failure detection and recovery behavior
4. WHEN agents are tested individually, THE System SHALL verify all domain-specific functionality remains intact
5. WHEN A2A communication is tested, THE System SHALL verify message sending and receiving between agents
