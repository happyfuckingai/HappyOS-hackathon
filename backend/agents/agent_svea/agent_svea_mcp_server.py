#!/usr/bin/env python3
"""
Agent Svea Standardized MCP Server

Isolated MCP server for Swedish ERP and compliance operations.
Implements StandardizedMCPServer interface with zero backend.* imports.

Features:
- Swedish ERP integration (ERPNext)
- BAS accounting compliance
- Skatteverket tax authority integration
- Circuit breaker resilience patterns
- Reply-to semantics for async workflows
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

# HappyOS SDK imports only - NO backend.* imports
from happyos_sdk import (
    create_mcp_client, AgentType, MCPHeaders, MCPResponse, MCPTool,
    create_service_facades, get_circuit_breaker, CircuitBreakerConfig,
    setup_logging, get_error_handler, UnifiedErrorCode
)

# Standard library and third-party imports
import httpx
from pydantic import BaseModel, Field

# Configure logging
logger = setup_logging("INFO", "json", "agent_svea", "agent_svea")


class AgentSveaServiceType(Enum):
    """Types of Agent Svea services that need circuit breaker protection."""
    ERP_INTEGRATION = "erp_integration"
    BAS_VALIDATION = "bas_validation"
    SKATTEVERKET_API = "skatteverket_api"
    DOCUMENT_PROCESSING = "document_processing"
    COMPLIANCE_CHECK = "compliance_check"
    SIE_EXPORT = "sie_export"
    INVOICE_GENERATION = "invoice_generation"


class ERPNextConfig(BaseModel):
    """Configuration for ERPNext/Agentsvea connection."""
    base_url: str = Field(..., description="ERPNext/Agentsvea base URL")
    api_key: str = Field(..., description="API key for authentication")
    api_secret: str = Field(..., description="API secret for authentication")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")


class AgentSveaMCPServer:
    """
    Standardized MCP Server for Agent Svea.
    
    Provides Swedish ERP and compliance tools via MCP protocol with
    complete isolation from backend.* imports.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Agent Svea MCP Server."""
        self.agent_id = "agent_svea"
        self.agent_type = AgentType.AGENT_SVEA
        self.config = config or {}
        
        # MCP client for agent-to-agent communication
        self.mcp_client = None
        
        # Service facades for backend access
        self.services = None
        
        # Circuit breakers for resilience
        self.circuit_breakers = {}
        
        # Error handler
        self.error_handler = get_error_handler("agent_svea", "agent_svea")
        
        # ERPNext client
        self.erp_client = None
        
        logger.info("Agent Svea MCP Server initialized")
    
    async def initialize(self) -> bool:
        """Initialize the MCP server."""
        try:
            # Create MCP client
            self.mcp_client = create_mcp_client(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                transport_type="inprocess"
            )
            
            # Initialize MCP client
            await self.mcp_client.initialize()
            
            # Create service facades
            self.services = create_service_facades(self.mcp_client.a2a_client)
            
            # Initialize circuit breakers
            await self._initialize_circuit_breakers()
            
            # Initialize ERPNext client if configured
            await self._initialize_erp_client()
            
            # Register MCP tools
            await self._register_mcp_tools()
            
            logger.info("Agent Svea MCP Server initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Agent Svea MCP Server: {e}")
            return False
    
    async def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for each service type."""
        circuit_breaker_configs = {
            AgentSveaServiceType.ERP_INTEGRATION: CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60,
                name="agent_svea_erp_integration"
            ),
            AgentSveaServiceType.BAS_VALIDATION: CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30,
                name="agent_svea_bas_validation"
            ),
            AgentSveaServiceType.SKATTEVERKET_API: CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout=120,
                name="agent_svea_skatteverket_api"
            ),
            AgentSveaServiceType.DOCUMENT_PROCESSING: CircuitBreakerConfig(
                failure_threshold=4,
                recovery_timeout=45,
                name="agent_svea_document_processing"
            ),
            AgentSveaServiceType.COMPLIANCE_CHECK: CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60,
                name="agent_svea_compliance_check"
            ),
            AgentSveaServiceType.SIE_EXPORT: CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=90,
                name="agent_svea_sie_export"
            ),
            AgentSveaServiceType.INVOICE_GENERATION: CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                name="agent_svea_invoice_generation"
            )
        }
        
        for service_type, config in circuit_breaker_configs.items():
            self.circuit_breakers[service_type] = get_circuit_breaker(
                service_name=service_type.value,
                config=config
            )
        
        logger.info(f"Initialized {len(self.circuit_breakers)} circuit breakers")
    
    async def _initialize_erp_client(self):
        """Initialize ERPNext HTTP client if configured."""
        erp_config = self.config.get("erpnext")
        if not erp_config:
            logger.warning("No ERPNext configuration provided")
            return
        
        try:
            config = ERPNextConfig(**erp_config)
            self.erp_client = httpx.AsyncClient(
                base_url=config.base_url,
                headers={
                    "Authorization": f"token {config.api_key}:{config.api_secret}",
                    "Content-Type": "application/json",
                },
                verify=config.verify_ssl,
            )
            logger.info("ERPNext client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ERPNext client: {e}")
    
    async def _register_mcp_tools(self):
        """Register MCP tools with handlers."""
        tools = [
            MCPTool(
                name="check_swedish_compliance",
                description="Validate Swedish regulatory compliance for business operations",
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_type": {"type": "string", "description": "Type of document to validate"},
                        "document_data": {"type": "object", "description": "Document data to validate"},
                        "compliance_rules": {"type": "array", "description": "Specific compliance rules to check"}
                    },
                    "required": ["document_type", "document_data"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "compliance_status": {"type": "string"},
                        "violations": {"type": "array"},
                        "recommendations": {"type": "array"}
                    }
                },
                agent_type=self.agent_type
            ),
            MCPTool(
                name="validate_bas_account",
                description="Validate BAS account structure and coding according to Swedish standards",
                input_schema={
                    "type": "object",
                    "properties": {
                        "account_number": {"type": "string", "description": "4-digit BAS account number"},
                        "account_type": {"type": "string", "description": "Expected account type"},
                        "transaction_data": {"type": "object", "description": "Transaction data for validation"}
                    },
                    "required": ["account_number"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "validation_result": {"type": "boolean"},
                        "bas_compliance": {"type": "string"},
                        "corrections": {"type": "array"}
                    }
                },
                agent_type=self.agent_type
            ),
            MCPTool(
                name="sync_erp_document",
                description="Synchronize document with ERPNext system",
                input_schema={
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "description": "ERPNext document type"},
                        "document": {"type": "object", "description": "Document data to sync"},
                        "sync_options": {"type": "object", "description": "Synchronization options"}
                    },
                    "required": ["doctype", "document"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sync_status": {"type": "string"},
                        "document_id": {"type": "string"},
                        "sync_timestamp": {"type": "string"}
                    }
                },
                agent_type=self.agent_type
            )
        ]
        
        # Register tools with handlers
        for tool in tools:
            handler = getattr(self, f"_handle_{tool.name}")
            await self.mcp_client.register_tool(tool, handler)
        
        logger.info(f"Registered {len(tools)} MCP tools")
    
    async def _handle_check_swedish_compliance(self, arguments: Dict[str, Any], headers: MCPHeaders) -> Dict[str, Any]:
        """Handle Swedish compliance checking."""
        try:
            document_type = arguments["document_type"]
            document_data = arguments["document_data"]
            compliance_rules = arguments.get("compliance_rules", [])
            
            # Execute with circuit breaker protection
            circuit_breaker = self.circuit_breakers[AgentSveaServiceType.COMPLIANCE_CHECK]
            
            async def compliance_check():
                # Perform compliance validation
                result = await self._perform_compliance_check(
                    document_type, document_data, compliance_rules, headers.trace_id
                )
                return result
            
            result = await circuit_breaker.execute(compliance_check)
            
            # Send async callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "check_swedish_compliance",
                    "status": "success",
                    "data": result,
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            return {"status": "processing", "message": "Compliance check initiated"}
            
        except Exception as e:
            error = self.error_handler.handle_mcp_error(e, {
                "trace_id": headers.trace_id,
                "tenant_id": headers.tenant_id,
                "tool_name": "check_swedish_compliance"
            })
            
            # Send error callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "check_swedish_compliance",
                    "status": "error",
                    "error": str(e),
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            raise
    
    async def _handle_validate_bas_account(self, arguments: Dict[str, Any], headers: MCPHeaders) -> Dict[str, Any]:
        """Handle BAS account validation."""
        try:
            account_number = arguments["account_number"]
            account_type = arguments.get("account_type")
            transaction_data = arguments.get("transaction_data", {})
            
            # Execute with circuit breaker protection
            circuit_breaker = self.circuit_breakers[AgentSveaServiceType.BAS_VALIDATION]
            
            async def bas_validation():
                result = await self._perform_bas_validation(
                    account_number, account_type, transaction_data, headers.trace_id
                )
                return result
            
            result = await circuit_breaker.execute(bas_validation)
            
            # Send async callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "validate_bas_account",
                    "status": "success",
                    "data": result,
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            return {"status": "processing", "message": "BAS validation initiated"}
            
        except Exception as e:
            error = self.error_handler.handle_mcp_error(e, {
                "trace_id": headers.trace_id,
                "tenant_id": headers.tenant_id,
                "tool_name": "validate_bas_account"
            })
            
            # Send error callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "validate_bas_account",
                    "status": "error",
                    "error": str(e),
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            raise
    
    async def _handle_sync_erp_document(self, arguments: Dict[str, Any], headers: MCPHeaders) -> Dict[str, Any]:
        """Handle ERPNext document synchronization."""
        try:
            doctype = arguments["doctype"]
            document = arguments["document"]
            sync_options = arguments.get("sync_options", {})
            
            # Execute with circuit breaker protection
            circuit_breaker = self.circuit_breakers[AgentSveaServiceType.ERP_INTEGRATION]
            
            async def erp_sync():
                result = await self._perform_erp_sync(
                    doctype, document, sync_options, headers.trace_id
                )
                return result
            
            result = await circuit_breaker.execute(erp_sync)
            
            # Send async callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "sync_erp_document",
                    "status": "success",
                    "data": result,
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            return {"status": "processing", "message": "ERP sync initiated"}
            
        except Exception as e:
            error = self.error_handler.handle_mcp_error(e, {
                "trace_id": headers.trace_id,
                "tenant_id": headers.tenant_id,
                "tool_name": "sync_erp_document"
            })
            
            # Send error callback
            await self.mcp_client.send_callback(
                reply_to=headers.reply_to,
                result={
                    "tool_name": "sync_erp_document",
                    "status": "error",
                    "error": str(e),
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=headers
            )
            
            raise
    
    async def _perform_compliance_check(self, document_type: str, document_data: Dict[str, Any], 
                                      compliance_rules: List[str], trace_id: str) -> Dict[str, Any]:
        """Perform Swedish compliance validation."""
        try:
            # Store compliance check request
            check_data = {
                "type": "compliance_check",
                "document_type": document_type,
                "document_data": document_data,
                "compliance_rules": compliance_rules,
                "status": "processing",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            check_id = await self.services["database"].store_data(
                data=check_data,
                data_type="compliance_check",
                trace_id=trace_id
            )
            
            # Perform basic compliance validation
            violations = []
            recommendations = []
            
            # Basic Swedish business document validation
            if document_type == "invoice":
                if not document_data.get("vat_number"):
                    violations.append("Missing VAT number (required for Swedish invoices)")
                    recommendations.append("Add valid Swedish VAT number (format: SE123456789012)")
                
                if not document_data.get("due_date"):
                    violations.append("Missing due date")
                    recommendations.append("Add payment due date")
            
            elif document_type == "accounting_entry":
                if not document_data.get("bas_account"):
                    violations.append("Missing BAS account classification")
                    recommendations.append("Classify transaction with appropriate BAS account")
            
            # Check for BAS compliance if specified
            if "bas_compliance" in compliance_rules:
                bas_account = document_data.get("bas_account")
                if bas_account:
                    bas_result = await self._validate_bas_account_internal(bas_account)
                    if not bas_result["valid"]:
                        violations.append(f"Invalid BAS account: {bas_result['error']}")
                        recommendations.append("Use valid 4-digit BAS account number")
            
            compliance_status = "compliant" if not violations else "non_compliant"
            
            result = {
                "check_id": check_id,
                "compliance_status": compliance_status,
                "violations": violations,
                "recommendations": recommendations,
                "document_type": document_type,
                "rules_checked": compliance_rules,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Update stored data with result
            await self.services["database"].update_data(
                data_id=check_id,
                updates={"result": result, "status": "completed"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            raise
    
    async def _perform_bas_validation(self, account_number: str, account_type: Optional[str], 
                                    transaction_data: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Perform BAS account validation."""
        try:
            # Store validation request
            validation_data = {
                "type": "bas_validation",
                "account_number": account_number,
                "account_type": account_type,
                "transaction_data": transaction_data,
                "status": "processing",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            validation_id = await self.services["database"].store_data(
                data=validation_data,
                data_type="bas_validation",
                trace_id=trace_id
            )
            
            # Perform BAS validation
            bas_result = await self._validate_bas_account_internal(account_number)
            
            corrections = []
            if not bas_result["valid"]:
                corrections.append({
                    "issue": bas_result["error"],
                    "suggestion": "Use valid 4-digit BAS account number",
                    "example": "1510 for bank accounts, 3001 for sales revenue"
                })
            
            # Validate account type consistency
            if account_type and bas_result["valid"]:
                expected_type = bas_result.get("account_type")
                if expected_type and expected_type != account_type:
                    corrections.append({
                        "issue": f"Account type mismatch: expected {expected_type}, got {account_type}",
                        "suggestion": f"Use account type: {expected_type}",
                        "bas_category": bas_result.get("account_category")
                    })
            
            result = {
                "validation_id": validation_id,
                "validation_result": bas_result["valid"],
                "bas_compliance": "compliant" if bas_result["valid"] and not corrections else "non_compliant",
                "corrections": corrections,
                "account_info": bas_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Update stored data with result
            await self.services["database"].update_data(
                data_id=validation_id,
                updates={"result": result, "status": "completed"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"BAS validation failed: {e}")
            raise
    
    async def _perform_erp_sync(self, doctype: str, document: Dict[str, Any], 
                              sync_options: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Perform ERPNext document synchronization."""
        try:
            # Store sync request
            sync_data = {
                "type": "erp_sync",
                "doctype": doctype,
                "document": document,
                "sync_options": sync_options,
                "status": "processing",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            sync_id = await self.services["database"].store_data(
                data=sync_data,
                data_type="erp_sync",
                trace_id=trace_id
            )
            
            # Perform ERP synchronization
            if self.erp_client:
                # Sync with actual ERPNext instance
                response = await self.erp_client.post(
                    f"/api/resource/{doctype}",
                    json=document
                )
                response.raise_for_status()
                erp_response = response.json()
                
                document_id = erp_response.get("data", {}).get("name", sync_id)
                sync_status = "success"
            else:
                # Fallback: store locally if no ERP connection
                logger.warning("No ERPNext client configured, storing document locally")
                document_id = sync_id
                sync_status = "stored_locally"
            
            result = {
                "sync_id": sync_id,
                "sync_status": sync_status,
                "document_id": document_id,
                "doctype": doctype,
                "sync_timestamp": datetime.utcnow().isoformat(),
                "erp_connected": self.erp_client is not None
            }
            
            # Update stored data with result
            await self.services["database"].update_data(
                data_id=sync_id,
                updates={"result": result, "status": "completed"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"ERP sync failed: {e}")
            raise
    
    def _validate_bas_account_internal(self, account_number: str) -> Dict[str, Any]:
        """Internal BAS account validation using local rules."""
        if not account_number or len(account_number) != 4:
            return {
                "valid": False,
                "error": "Invalid account number format",
                "expected_format": "4-digit BAS account number"
            }
        
        try:
            # Ensure it's numeric
            int(account_number)
        except ValueError:
            return {
                "valid": False,
                "error": "Account number must be numeric",
                "expected_format": "4-digit numeric BAS account number"
            }
        
        # Basic account type classification based on first digit
        first_digit = account_number[0]
        account_types = {
            "1": {"type": "assets", "name": "Tillgångar"},
            "2": {"type": "liabilities", "name": "Skulder"},
            "3": {"type": "revenue", "name": "Intäkter"},
            "4": {"type": "expenses", "name": "Kostnader"},
            "5": {"type": "expenses", "name": "Kostnader"},
            "6": {"type": "expenses", "name": "Kostnader"},
            "7": {"type": "expenses", "name": "Kostnader"},
            "8": {"type": "financial", "name": "Finansiella poster"}
        }
        
        account_info = account_types.get(first_digit, {"type": "unknown", "name": "Okänd"})
        
        return {
            "valid": True,
            "account_number": account_number,
            "account_type": account_info["type"],
            "account_category": account_info["name"],
            "validation_method": "basic_rules",
            "confidence": "medium"
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of Agent Svea services."""
        health_status = {}
        
        for service_type, circuit_breaker in self.circuit_breakers.items():
            health_status[service_type.value] = {
                "circuit_breaker_state": circuit_breaker.state.value if hasattr(circuit_breaker, 'state') else "unknown",
                "is_healthy": not getattr(circuit_breaker, 'is_open', False),
                "last_check": datetime.utcnow().isoformat()
            }
        
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "overall_health": "healthy",
            "services": health_status,
            "erp_connected": self.erp_client is not None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def shutdown(self):
        """Shutdown the MCP server."""
        try:
            if self.erp_client:
                await self.erp_client.aclose()
            
            if self.mcp_client:
                await self.mcp_client.shutdown()
            
            logger.info("Agent Svea MCP Server shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


async def main():
    """Main entry point for Agent Svea MCP Server."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Agent Svea MCP Server")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--erp-url", help="ERPNext base URL")
    parser.add_argument("--erp-key", help="ERPNext API key")
    parser.add_argument("--erp-secret", help="ERPNext API secret")
    
    args = parser.parse_args()
    
    # Build configuration
    config = {}
    
    if args.erp_url or os.getenv("ERPNEXT_URL"):
        config["erpnext"] = {
            "base_url": args.erp_url or os.getenv("ERPNEXT_URL"),
            "api_key": args.erp_key or os.getenv("ERPNEXT_API_KEY"),
            "api_secret": args.erp_secret or os.getenv("ERPNEXT_API_SECRET"),
            "verify_ssl": os.getenv("ERPNEXT_VERIFY_SSL", "true").lower() == "true"
        }
    
    # Create and run server
    server = AgentSveaMCPServer(config)
    
    try:
        if await server.initialize():
            logger.info("Agent Svea MCP Server started successfully")
            # Keep server running
            while True:
                await asyncio.sleep(1)
        else:
            logger.error("Failed to initialize Agent Svea MCP Server")
            return 1
    except KeyboardInterrupt:
        logger.info("Shutting down Agent Svea MCP Server...")
        await server.shutdown()
        return 0
    except Exception as e:
        logger.error(f"Server error: {e}")
        await server.shutdown()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))