# Implementation Plan

## Current Status

### ✅ Completed Infrastructure Setup
- **Module Migration**: All self-building modules moved from `backend/core/inspiration/core/` to `backend/core/`
  - `self_building/` → `backend/core/self_building/` (includes discovery, registry, generators, hot_reload, intelligence, advanced)
  - `code_generation/` → `backend/core/code_generation/`
  - `component_generation/` → `backend/core/component_generation/`
  - `error_handler.py` → `backend/core/error_handler.py`
  - `skill_executor.py` → `backend/core/skill_executor.py`
- **Import Updates**: All imports updated from `app.core` to `backend.core`
- **LearningEngine**: Fully implemented with telemetry analysis, insight generation, and improvement opportunity identification (Task 4 ✅)
- **CloudWatch Streamer**: Exists and ready for integration with LearningEngine

### 🎯 Next Steps
The next task is **Task 5: Implement LLM-integrated code generator** to enable real code generation using LLM services.

After that, we'll integrate the CloudWatch streamer with LearningEngine (Task 6) to complete the telemetry pipeline.

---

## Tasks

- [x] 1. Set up self-building MCP server infrastructure
  - Create FastAPI application with MCP endpoint mounting
  - Implement Bearer token authentication middleware
  - Add health check endpoint
  - Configure CORS for cross-origin requests
  - _Requirements: 1.1, 1.2, 1.5_

- [x] 1.1 Create self-building MCP server file structure
  - Create `backend/agents/self_building/` directory
  - Create `self_building_mcp_server.py` with FastAPI app
  - Create `__init__.py` and `registry.py` files
  - Add configuration file for MCP server settings
  - _Requirements: 1.1_

- [x] 1.2 Implement MCP tool: trigger_improvement_cycle
  - Define tool function with FastMCP decorator
  - Add parameters: analysis_window_hours, max_improvements, tenant_id
  - Integrate with SBO2's autonomous_improvement_cycle method
  - Return improvement results with deployed changes
  - Add error handling and logging
  - _Requirements: 1.3, 6.1, 6.2_

- [x] 1.3 Implement MCP tool: generate_component
  - Define tool function with FastMCP decorator
  - Add parameters: component_type, requirements, context
  - Integrate with SBO2's handle_generation_candidate_request method
  - Return generated component details and registration info
  - Add validation for component requirements
  - _Requirements: 1.3, 7.1, 7.2, 7.3_

- [x] 1.4 Implement MCP tool: get_system_status
  - Define tool function with FastMCP decorator
  - Call SBO2's get_ultimate_system_status method
  - Return system health, active improvements, evolution level
  - Add caching for frequently requested status
  - _Requirements: 1.3, 8.5_

- [x] 1.5 Implement MCP tool: query_telemetry_insights
  - Define tool function with FastMCP decorator
  - Add parameters: metric_name, time_range_hours, tenant_id
  - Query LearningEngine for insights
  - Return telemetry insights and recommendations
  - Add tenant isolation validation
  - _Requirements: 1.3, 9.1_

- [x] 2. Integrate self-building agent with agent registry
  - Add registration method to AgentRegistry class
  - Define agent metadata with capabilities
  - Register MCP endpoint and health check URL
  - Add agent discovery for other agents
  - _Requirements: 1.2, 10.1_

- [x] 2.1 Update agent registry to support self-building agent
  - Modify `backend/core/registry/agents.py`
  - Add `register_self_building_agent` method
  - Define agent_info dictionary with capabilities
  - Call registration during system startup
  - _Requirements: 1.2_

- [x] 2.2 Add self-building agent startup to main.py
  - Import self-building MCP server
  - Start MCP server on port 8004 during lifespan
  - Register agent in registry after server starts
  - Add graceful shutdown handling
  - _Requirements: 1.1, 1.2_

- [x] 3. Implement CloudWatch telemetry streamer
  - Create CloudWatchTelemetryStreamer class
  - Initialize boto3 clients for CloudWatch, Logs, Events
  - Add circuit breaker protection for AWS calls
  - Implement async streaming methods
  - _Requirements: 2.1, 2.4_

- [x] 3.1 Create cloudwatch_streamer.py file
  - ✅ File exists at `backend/core/self_building/intelligence/cloudwatch_streamer.py`
  - ✅ CloudWatchTelemetryStreamer class defined
  - ✅ Initialization method with boto3 clients implemented
  - ✅ Circuit breaker instance added
  - _Requirements: 2.1_

- [x] 3.2 Implement stream_metrics method
  - Add async generator for metric streaming
  - Query CloudWatch GetMetricStatistics API
  - Filter by namespace, metric names, dimensions
  - Yield metric data points as they arrive
  - Add fallback to local metrics on circuit breaker open
  - _Requirements: 2.2, 2.4_

- [x] 3.3 Implement stream_logs method
  - Add async generator for log streaming
  - Use CloudWatch Logs Insights for querying
  - Filter by log group pattern and filter pattern
  - Parse log events and extract fields
  - Add sampling for high-volume logs
  - _Requirements: 3.1, 3.2, 3.4_

- [x] 3.4 Implement subscribe_to_events method
  - Add async generator for event streaming
  - Subscribe to EventBridge events
  - Filter by event pattern (alarms, Lambda completions)
  - Yield events as they arrive
  - Add polling fallback if EventBridge unavailable
  - _Requirements: 4.1, 4.2, 4.4_

- [x] 3.5 Implement get_alarm_state method
  - Query CloudWatch DescribeAlarms API
  - Return alarm states (OK, ALARM, INSUFFICIENT_DATA)
  - Add caching for alarm states
  - _Requirements: 4.1_

- [x] 3.6 Implement start_streaming and stop_streaming methods
  - Create background tasks for each stream
  - Feed telemetry data into LearningEngine
  - Handle graceful shutdown of streams
  - Add error recovery and reconnection logic
  - _Requirements: 2.1, 3.1, 4.1_

- [x] 4. Create enhanced LearningEngine
  - Create LearningEngine class with telemetry analysis
  - Define data models for insights and opportunities
  - Implement analysis algorithms
  - Add ML model placeholders for future enhancement
  - _Requirements: 2.2, 2.3, 6.2_

- [x] 4.1 Create learning_engine.py file
  - ✅ File created at `backend/core/self_building/intelligence/learning_engine.py`
  - ✅ TelemetryInsight and ImprovementOpportunity dataclasses defined
  - ✅ LearningEngine class with initialization implemented
  - ✅ Telemetry buffer and insights cache added
  - ✅ Exported in __init__.py
  - _Requirements: 2.2_

- [x] 4.2 Implement ingest_telemetry method
  - Add method to buffer incoming telemetry data
  - Categorize by source (metrics, logs, events)
  - Trigger analysis when buffer thresholds met
  - Add tenant isolation filtering
  - _Requirements: 2.2, 9.1_

- [x] 4.3 Implement analyze_performance_trends method
  - Calculate moving averages for metrics
  - Detect degradation using standard deviation thresholds
  - Identify anomalies using Z-score analysis
  - Generate TelemetryInsight objects for findings
  - _Requirements: 2.3, 6.2_

- [x] 4.4 Implement analyze_error_patterns method
  - Extract error messages and stack traces from logs
  - Cluster similar errors using frequency analysis
  - Identify root causes and affected components
  - Generate TelemetryInsight objects for error patterns
  - _Requirements: 3.2, 3.3_

- [x] 4.5 Implement identify_improvement_opportunities method
  - Convert telemetry insights into improvement opportunities
  - Calculate impact scores: (performance_gain × affected_users × frequency) / 100
  - Prioritize by impact score and filter by risk tolerance
  - Return sorted list of ImprovementOpportunity objects
  - _Requirements: 6.3_

- [x] 4.6 Implement get_insights_summary method
  - Aggregate insights by type and severity
  - Filter by time range and tenant_id
  - Return summary statistics
  - _Requirements: 2.2_

- [x] 5. Implement LLM-integrated code generator
  - Create LLMCodeGenerator class
  - Integrate with existing LLM service
  - Add circuit breaker protection
  - Implement prompt engineering for code generation
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 5.1 Create llm_code_generator.py file
  - Create `backend/core/self_building/generators/llm_code_generator.py`
  - Define LLMCodeGenerator class
  - Initialize with LLMService and LLMCircuitBreaker
  - _Requirements: 5.1_

- [x] 5.2 Implement generate_component_code method
  - Build comprehensive prompt with context
  - Call LLM service with circuit breaker protection
  - Parse generated code into file dictionary
  - Validate syntax and imports
  - Return code files or raise CodeGenerationError
  - _Requirements: 5.2, 5.3, 5.5_

- [x] 5.3 Implement _build_generation_prompt method
  - Include system architecture overview
  - Add existing code patterns as examples
  - Specify component requirements
  - Add telemetry insights as optimization goals
  - Include code quality standards
  - _Requirements: 5.3_

- [x] 5.4 Implement generate_improvement_code method
  - Generate code improvements for existing components
  - Use diff-based generation to minimize changes
  - Validate improvements against existing code
  - _Requirements: 5.5_

- [x] 5.5 Implement _validate_code method
  - Check syntax correctness using AST parsing
  - Verify import resolution
  - Run type checking if type hints present
  - Check for security vulnerabilities
  - Calculate code quality metrics
  - _Requirements: 5.5_

- [x] 6. Integrate CloudWatch streamer with LearningEngine
  - Connect telemetry streams to LearningEngine ingestion
  - Add event deduplication logic
  - Implement tenant-aware filtering
  - Add monitoring for stream health
  - _Requirements: 2.2, 2.5, 9.1_

- [x] 6.1 Update SBO2 initialization to start CloudWatch streaming
  - Modify `ultimate_self_building.py` initialization
  - Create CloudWatchTelemetryStreamer instance
  - Pass LearningEngine reference to streamer
  - Start streaming during system startup
  - _Requirements: 2.1_

- [x] 6.2 Implement event deduplication in streamer
  - Add event ID tracking with time windows
  - Deduplicate events within 5-minute window
  - Log deduplicated event counts
  - _Requirements: 4.5_

- [x] 6.3 Add tenant filtering to telemetry streams
  - Filter metrics by tenant_id dimension
  - Filter logs by tenant_id field
  - Filter events by tenant_id in detail
  - _Requirements: 2.5, 9.1_

- [ ] 7. Implement autonomous improvement cycle
  - Update SBO2 to use real telemetry analysis
  - Add improvement prioritization logic
  - Implement concurrent improvement execution
  - Add monitoring and rollback logic
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7.1 Update _continuous_recursive_improvement in SBO2
  - Replace mock analysis with LearningEngine calls
  - Query improvement opportunities from LearningEngine
  - Prioritize by impact score
  - Execute up to max_concurrent_improvements
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 7.2 Implement improvement execution pipeline
  - Generate code using LLMCodeGenerator
  - Validate generated code
  - Deploy to target components
  - Start monitoring period
  - _Requirements: 6.4_

- [x] 7.3 Implement improvement monitoring
  - Collect baseline metrics before deployment
  - Monitor metrics during monitoring period (1 hour)
  - Calculate degradation percentage
  - Trigger rollback if degradation > 10%
  - _Requirements: 6.5_

- [x] 7.4 Implement improvement rollback logic
  - Store previous component versions
  - Restore previous code on rollback trigger
  - Reload components using hot reload
  - Log rollback events with audit logger
  - _Requirements: 6.5_

- [x] 8. Add CloudWatch event triggers for improvement cycles
  - Subscribe to CloudWatch alarm events
  - Trigger emergency improvement cycles on critical alarms
  - Add Lambda completion event handling
  - Implement event-driven improvement initiation
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 8.1 Implement alarm event handler
  - Subscribe to alarm state change events
  - Filter for ALARM state transitions
  - Check alarm severity (HighErrorRate, HighLatency, etc.)
  - Trigger emergency improvement cycle within 30 seconds
  - _Requirements: 4.2_

- [x] 8.2 Implement Lambda completion event handler
  - Subscribe to Lambda function completion events
  - Extract execution metrics (duration, memory, errors)
  - Analyze for optimization opportunities
  - Add to improvement queue if opportunities found
  - _Requirements: 4.3_

- [x] 9. Implement multi-tenant isolation
  - Add tenant_id validation to all MCP tools
  - Filter telemetry by tenant_id
  - Scope improvements to specific tenants
  - Add system-wide improvement approval flow
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 9.1 Add tenant_id validation to MCP tools
  - Validate tenant_id parameter in all MCP tools
  - Check tenant exists in system
  - Verify requester has access to tenant
  - _Requirements: 9.1_

- [x] 9.2 Implement tenant-scoped improvement generation
  - Add tenant_id to ImprovementOpportunity
  - Filter telemetry analysis by tenant_id
  - Scope generated code to tenant namespace
  - _Requirements: 9.2_

- [x] 9.3 Implement tenant isolation validation
  - Validate generated code doesn't access other tenant data
  - Check database queries include tenant_id filter
  - Verify API calls include tenant context
  - _Requirements: 9.3_

- [x] 9.4 Implement system-wide improvement approval
  - Add approval flag to ImprovementOpportunity
  - Require meta-orchestrator approval for system-wide changes
  - Log approval decisions with audit logger
  - _Requirements: 9.4_

- [x] 10. Integrate with existing HappyOS agents
  - Add MCP client calls to existing agents
  - Implement agent-specific metric collection
  - Add agent improvement coordination
  - Test cross-agent communication
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 10.1 Add self-building agent discovery to existing agents
  - Update MeetMind, Agent Svea, Felicia's Finance agents
  - Query agent registry for self-building agent
  - Store MCP endpoint for future calls
  - _Requirements: 10.1_

- [x] 10.2 Implement agent-specific metric collection
  - Add custom metrics for each agent type
  - Collect request latency, error rates, resource usage
  - Send metrics to CloudWatch with agent_id dimension
  - _Requirements: 10.2_

- [x] 10.3 Implement agent improvement coordination
  - Add MCP call to schedule improvement deployment
  - Coordinate with agent to find low-traffic period
  - Deploy improvement during scheduled window
  - _Requirements: 10.4_

- [x] 10.4 Implement agent notification on improvements
  - Broadcast improvement deployment via MCP
  - Notify dependent agents of changes
  - Include change summary and migration guide
  - _Requirements: 10.5_

- [x] 11. Add configuration and feature flags
  - Add environment variables for self-building configuration
  - Implement feature flags in settings
  - Add runtime configuration updates
  - Document all configuration options
  - _Requirements: 1.1, 6.1_

- [x] 11.1 Add environment variables
  - Add SELF_BUILDING_MCP_PORT, SELF_BUILDING_MCP_API_KEY
  - Add CloudWatch configuration variables
  - Add improvement cycle configuration variables
  - Add LLM configuration variables (reuse existing)
  - _Requirements: 1.1_

- [x] 11.2 Add feature flags to settings.py
  - Add enable_self_building flag
  - Add enable_cloudwatch_streaming flag
  - Add enable_autonomous_improvements flag (default: False)
  - Add enable_component_generation flag
  - Add enable_improvement_rollback flag
  - _Requirements: 6.1_

- [x] 12. Add monitoring and observability
  - Implement custom metrics for self-building system
  - Create CloudWatch dashboard
  - Add alerts for critical events
  - Implement audit logging
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 12.1 Implement self-building metrics
  - Add improvement cycle metrics (started, completed, deployed, rolled_back)
  - Add code generation metrics (requests, success_rate, duration, tokens_used)
  - Add telemetry processing metrics (events_processed, insights_generated)
  - Add circuit breaker metrics (opens, closes)
  - _Requirements: 8.1_

- [x] 12.2 Create self-building CloudWatch dashboard
  - Add improvement cycle success rate widget
  - Add code generation latency distribution widget
  - Add telemetry processing throughput widget
  - Add circuit breaker state widget
  - Add evolution level progression widget
  - _Requirements: 8.2_

- [x] 12.3 Create CloudWatch alarms
  - Add alarm for high failure rate (< 70% success)
  - Add alarm for circuit breaker open (> 5 minutes)
  - Add alarm for improvement rollback
  - Add alarm for generation timeout (> 60 seconds)
  - _Requirements: 8.3_

- [x] 12.4 Implement audit logging
  - Log all improvement cycles with details
  - Log code generation requests with requester
  - Log deployment and rollback events
  - Log CloudWatch access for compliance
  - _Requirements: 9.5_

- [x] 13. Write integration tests
  - Test MCP server endpoints
  - Test CloudWatch streaming with LocalStack
  - Test LLM code generation with mocks
  - Test improvement cycle end-to-end
  - Test multi-tenant isolation
  - _Requirements: All_

- [x] 13.1 Write MCP server integration tests
  - Test trigger_improvement_cycle tool
  - Test generate_component tool
  - Test get_system_status tool
  - Test query_telemetry_insights tool
  - Test authentication and error handling
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 13.2 Write CloudWatch integration tests
  - Test metric streaming with LocalStack
  - Test log streaming with LocalStack
  - Test event subscription with LocalStack
  - Test circuit breaker failover
  - _Requirements: 2.1, 2.2, 2.4, 3.1, 4.1_

- [x] 13.3 Write LLM code generation tests
  - Test component code generation with mock LLM
  - Test improvement code generation with mock LLM
  - Test code validation logic
  - Test error handling and retries
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 13.4 Write improvement cycle end-to-end test
  - Trigger improvement cycle via MCP
  - Verify telemetry analysis
  - Verify code generation
  - Verify deployment
  - Verify monitoring and rollback logic
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13.5 Write multi-tenant isolation tests
  - Test tenant_id filtering in telemetry
  - Test tenant-scoped improvements
  - Test tenant isolation validation
  - Test system-wide improvement approval
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 14. Create documentation
  - Write MCP API documentation
  - Write CloudWatch integration guide
  - Write improvement cycle documentation
  - Write troubleshooting guide
  - _Requirements: All_

- [x] 14.1 Write MCP API documentation
  - Document all MCP tools with parameters
  - Add usage examples for each tool
  - Document authentication requirements
  - Add error codes and handling
  - _Requirements: 1.3_

- [x] 14.2 Write CloudWatch integration guide
  - Document required IAM permissions
  - Document metric namespaces and dimensions
  - Document log group patterns
  - Document event patterns
  - Add troubleshooting section
  - _Requirements: 2.1, 3.1, 4.1_

- [x] 14.3 Write improvement cycle documentation
  - Document cycle phases and timing
  - Document prioritization algorithm
  - Document monitoring and rollback logic
  - Add configuration examples
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 14.4 Write deployment guide
  - Document phased rollout strategy
  - Document feature flag usage
  - Document monitoring setup
  - Add rollback procedures
  - _Requirements: All_
