"""
Example integration showing unified error handling and logging across MCP and A2A protocols.

This example demonstrates how the HappyOS SDK provides consistent observability
patterns for both MCP agent communication and Backend Core A2A service calls.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any

# Import HappyOS SDK components
from happyos_sdk.error_handling import UnifiedErrorCode, get_error_handler
from happyos_sdk.logging import get_logger, create_log_context
from happyos_sdk.unified_observability import get_observability_manager, ObservabilityContext


class ExampleMCPClient:
    """Example MCP client showing unified observability integration."""
    
    def __init__(self, agent_type: str = "example_agent"):
        self.agent_type = agent_type
        self.error_handler = get_error_handler("mcp_client", agent_type)
        self.logger = get_logger(component="mcp_client", agent_type=agent_type)
        self.observability = get_observability_manager("mcp_client", agent_type)
    
    async def call_tool_with_observability(self,
                                         target_agent: str,
                                         tool_name: str,
                                         arguments: Dict[str, Any],
                                         trace_id: str = None,
                                         conversation_id: str = None,
                                         tenant_id: str = None) -> Dict[str, Any]:
        """
        Example MCP tool call with full observability integration.
        
        This demonstrates how MCP calls are instrumented with:
        - Unified error handling
        - Structured logging with trace correlation
        - Metrics collection
        - Audit logging
        """
        trace_id = trace_id or str(uuid.uuid4())
        conversation_id = conversation_id or str(uuid.uuid4())
        tenant_id = tenant_id or "example_tenant"
        
        # Create observability context
        context = ObservabilityContext(
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            agent_type=self.agent_type,
            component="mcp_client",
            operation="tool_call",
            protocol="mcp",
            target_agent=target_agent,
            tool_name=tool_name
        )
        
        # Simulate MCP tool call with observability
        async def mcp_tool_call():
            # Log the start of the operation
            self.logger.info(
                f"Starting MCP tool call: {tool_name} -> {target_agent}",
                context=context.to_log_context(),
                target_agent=target_agent,
                tool_name=tool_name,
                arguments=arguments
            )
            
            # Simulate some processing time
            await asyncio.sleep(0.1)
            
            # Simulate different outcomes based on tool name
            if tool_name == "failing_tool":
                raise TimeoutError("Tool execution timed out")
            elif tool_name == "compliance_tool" and arguments.get("invalid_data"):
                raise ValueError("Compliance validation failed")
            
            # Successful response
            return {
                "status": "success",
                "result": f"Tool {tool_name} executed successfully",
                "data": {"processed_args": arguments}
            }
        
        try:
            # Execute with full observability
            result = await self.observability.execute_with_observability(
                mcp_tool_call,
                context,
                f"mcp_tool_call_{tool_name}"
            )
            
            # Log successful completion
            await self.observability.log_mcp_operation(
                operation_type="tool_call",
                target_agent=target_agent,
                tool_name=tool_name,
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                success=True,
                duration_ms=100.0  # Would be calculated in real implementation
            )
            
            return result
            
        except Exception as e:
            # Handle error with unified error handling
            if "timeout" in str(e).lower():
                unified_error = self.error_handler.handle_tool_error(e, tool_name, context.to_dict())
            elif "compliance" in str(e).lower():
                unified_error = self.error_handler.handle_compliance_error(e, "data_validation", context.to_dict())
            else:
                unified_error = self.error_handler.handle_mcp_error(e, context.to_dict())
            
            # Log the error
            self.error_handler.log_error(unified_error)
            
            # Log failed MCP operation
            await self.observability.log_mcp_operation(
                operation_type="tool_call",
                target_agent=target_agent,
                tool_name=tool_name,
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                success=False,
                error=e
            )
            
            # Return error response in MCP format
            return unified_error.to_mcp_response()


class ExampleServiceFacade:
    """Example service facade showing unified observability integration."""
    
    def __init__(self, service_name: str = "example_service"):
        self.service_name = service_name
        self.error_handler = get_error_handler("service_facade")
        self.logger = get_logger(component="service_facade")
        self.observability = get_observability_manager("service_facade")
    
    async def store_data_with_observability(self,
                                          data: Dict[str, Any],
                                          trace_id: str = None,
                                          tenant_id: str = None) -> Dict[str, Any]:
        """
        Example A2A service call with full observability integration.
        
        This demonstrates how A2A service calls are instrumented with:
        - Unified error handling
        - Structured logging with trace correlation
        - Circuit breaker integration
        - Metrics collection
        """
        trace_id = trace_id or str(uuid.uuid4())
        tenant_id = tenant_id or "example_tenant"
        
        # Create observability context
        context = ObservabilityContext(
            trace_id=trace_id,
            tenant_id=tenant_id,
            component="service_facade",
            operation="store_data",
            protocol="a2a",
            service_name=self.service_name,
            action="store_data"
        )
        
        # Simulate A2A service call with observability
        async def a2a_service_call():
            # Log the start of the operation
            self.logger.info(
                f"Starting A2A service call: store_data -> {self.service_name}",
                context=context.to_log_context(),
                service_name=self.service_name,
                data_size=len(str(data))
            )
            
            # Simulate some processing time
            await asyncio.sleep(0.05)
            
            # Simulate different outcomes based on data
            if data.get("simulate_error") == "service_unavailable":
                from happyos_sdk.exceptions import ServiceUnavailableError
                raise ServiceUnavailableError(f"{self.service_name} is temporarily unavailable")
            elif data.get("simulate_error") == "validation_error":
                raise ValueError("Invalid data format provided")
            
            # Successful response
            data_id = str(uuid.uuid4())
            return {
                "success": True,
                "data_id": data_id,
                "stored_at": datetime.utcnow().isoformat()
            }
        
        try:
            # Execute with full observability
            result = await self.observability.execute_with_observability(
                a2a_service_call,
                context,
                f"a2a_store_data_{self.service_name}"
            )
            
            # Log successful completion
            await self.observability.log_a2a_operation(
                operation_type="service_call",
                service_name=self.service_name,
                action="store_data",
                trace_id=trace_id,
                tenant_id=tenant_id,
                success=True,
                duration_ms=50.0  # Would be calculated in real implementation
            )
            
            return result
            
        except Exception as e:
            # Handle error with unified error handling
            if "unavailable" in str(e).lower():
                unified_error = self.error_handler.handle_a2a_error(e, self.service_name, context.to_dict())
            elif "validation" in str(e).lower():
                unified_error = self.error_handler.handle_validation_error(e, "data", context.to_dict())
            else:
                unified_error = self.error_handler.handle_a2a_error(e, self.service_name, context.to_dict())
            
            # Log the error
            self.error_handler.log_error(unified_error)
            
            # Log failed A2A operation
            await self.observability.log_a2a_operation(
                operation_type="service_call",
                service_name=self.service_name,
                action="store_data",
                trace_id=trace_id,
                tenant_id=tenant_id,
                success=False,
                error=e
            )
            
            # Return error response
            return {
                "success": False,
                "error": unified_error.to_dict()
            }


async def demonstrate_unified_observability():
    """
    Demonstrate unified observability across MCP and A2A protocols.
    
    This example shows how the same observability patterns work consistently
    across both MCP agent communication and Backend Core A2A service calls.
    """
    print("🔍 HappyOS SDK Unified Observability Demonstration")
    print("=" * 60)
    
    # Create example clients
    mcp_client = ExampleMCPClient("demo_agent")
    service_facade = ExampleServiceFacade("database")
    
    # Generate trace ID for correlation across operations
    trace_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    tenant_id = "demo_tenant"
    
    print(f"📋 Trace ID: {trace_id}")
    print(f"💬 Conversation ID: {conversation_id}")
    print(f"🏢 Tenant ID: {tenant_id}")
    print()
    
    # Demonstrate successful MCP tool call
    print("✅ Testing successful MCP tool call...")
    mcp_result = await mcp_client.call_tool_with_observability(
        target_agent="agent_svea",
        tool_name="check_compliance",
        arguments={"document_type": "invoice", "amount": 1000},
        trace_id=trace_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id
    )
    print(f"   Result: {mcp_result['status']}")
    print()
    
    # Demonstrate successful A2A service call
    print("✅ Testing successful A2A service call...")
    a2a_result = await service_facade.store_data_with_observability(
        data={"type": "compliance_result", "status": "passed"},
        trace_id=trace_id,
        tenant_id=tenant_id
    )
    print(f"   Result: {'Success' if a2a_result['success'] else 'Failed'}")
    print(f"   Data ID: {a2a_result.get('data_id', 'N/A')}")
    print()
    
    # Demonstrate MCP tool timeout error
    print("❌ Testing MCP tool timeout error...")
    mcp_error_result = await mcp_client.call_tool_with_observability(
        target_agent="agent_svea",
        tool_name="failing_tool",
        arguments={"test": "timeout"},
        trace_id=trace_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id
    )
    print(f"   Status: {mcp_error_result['status']}")
    print(f"   Error Code: {mcp_error_result['error_code']}")
    print(f"   Recoverable: {mcp_error_result['recoverable']}")
    print()
    
    # Demonstrate A2A service unavailable error
    print("❌ Testing A2A service unavailable error...")
    a2a_error_result = await service_facade.store_data_with_observability(
        data={"simulate_error": "service_unavailable"},
        trace_id=trace_id,
        tenant_id=tenant_id
    )
    print(f"   Success: {a2a_error_result['success']}")
    if not a2a_error_result['success']:
        error_info = a2a_error_result['error']
        print(f"   Error Code: {error_info['error_code']}")
        print(f"   Recoverable: {error_info['recoverable']}")
        print(f"   Retry After: {error_info.get('retry_after', 'N/A')} seconds")
    print()
    
    # Demonstrate compliance error
    print("❌ Testing compliance validation error...")
    compliance_error_result = await mcp_client.call_tool_with_observability(
        target_agent="agent_svea",
        tool_name="compliance_tool",
        arguments={"invalid_data": True},
        trace_id=trace_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id
    )
    print(f"   Status: {compliance_error_result['status']}")
    print(f"   Error Code: {compliance_error_result['error_code']}")
    print(f"   Recoverable: {compliance_error_result['recoverable']}")
    print()
    
    print("🎉 Unified observability demonstration completed!")
    print()
    print("Key Features Demonstrated:")
    print("• Consistent error codes across MCP and A2A protocols")
    print("• Unified logging with trace correlation")
    print("• Standardized error recovery patterns")
    print("• Protocol-specific metrics collection")
    print("• Integrated audit logging")
    print("• Circuit breaker integration")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_unified_observability())