"""
JSON Schema Validation Middleware

This middleware enforces JSON schema validation for all UI resource operations
to ensure data integrity and consistency across the MCP UI Hub platform.

Requirements: JSON schema validation enforced for all resource operations
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..modules.models.ui_resource import ui_resource_validator, UIResource, UIResourceCreate, UIResourcePatch

logger = logging.getLogger(__name__)


class JSONSchemaValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce JSON schema validation for all UI resource operations
    
    This middleware intercepts requests to UI resource endpoints and validates
    the request payload against the appropriate JSON schema before processing.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.validation_endpoints = {
            # Resource creation endpoints
            "/mcp-ui/resources": ["POST"],
            # Resource update endpoints (patch operations)
            "/mcp-ui/resources/": ["PATCH"],  # Will match /mcp-ui/resources/{resource_id}
        }
    
    async def dispatch(self, request: Request, call_next):
        """
        Intercept requests and validate JSON schema for UI resource operations
        """
        # Check if this request needs validation
        if self._should_validate_request(request):
            try:
                # Validate the request payload
                await self._validate_request_payload(request)
            except ValueError as e:
                logger.error(f"JSON schema validation failed for {request.method} {request.url.path}: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "JSON schema validation failed",
                            "details": str(e),
                            "path": str(request.url.path),
                            "method": request.method
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Validation middleware error for {request.method} {request.url.path}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": "VALIDATION_MIDDLEWARE_ERROR",
                            "message": "Internal validation error",
                            "details": str(e)
                        }
                    }
                )
        
        # Continue with the request
        response = await call_next(request)
        
        # Validate response payload for resource operations
        if self._should_validate_response(request, response):
            try:
                await self._validate_response_payload(request, response)
            except Exception as e:
                logger.error(f"Response validation failed for {request.method} {request.url.path}: {e}")
                # Don't fail the request for response validation errors, just log them
        
        return response
    
    def _should_validate_request(self, request: Request) -> bool:
        """
        Determine if the request should be validated
        """
        path = request.url.path
        method = request.method
        
        # Check exact path matches
        if path in self.validation_endpoints:
            return method in self.validation_endpoints[path]
        
        # Check pattern matches (e.g., /mcp-ui/resources/{resource_id})
        for endpoint_pattern, methods in self.validation_endpoints.items():
            if endpoint_pattern.endswith("/") and path.startswith(endpoint_pattern):
                return method in methods
        
        return False
    
    def _should_validate_response(self, request: Request, response: Response) -> bool:
        """
        Determine if the response should be validated
        """
        # Only validate successful responses (2xx status codes)
        if not (200 <= response.status_code < 300):
            return False
        
        # Only validate resource operation responses
        return self._should_validate_request(request)
    
    async def _validate_request_payload(self, request: Request) -> None:
        """
        Validate the request payload against JSON schema
        """
        path = request.url.path
        method = request.method
        
        # Read request body
        body = await request.body()
        if not body:
            return  # No body to validate
        
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in request body: {e}")
        
        # Validate based on endpoint and method
        if path == "/mcp-ui/resources" and method == "POST":
            await self._validate_resource_create_payload(payload)
        elif path.startswith("/mcp-ui/resources/") and method == "PATCH":
            await self._validate_resource_patch_payload(payload, request)
    
    async def _validate_resource_create_payload(self, payload: Dict[str, Any]) -> None:
        """
        Validate resource creation payload
        """
        try:
            # Validate using Pydantic model first
            resource_create = UIResourceCreate(**payload)
            
            # Convert to full UIResource for schema validation
            resource = resource_create.to_ui_resource()
            
            # Validate against JSON schema
            ui_resource_validator.validate(resource.model_dump(), resource.version)
            
            logger.debug("Resource creation payload validation passed")
            
        except Exception as e:
            raise ValueError(f"Resource creation validation failed: {e}")
    
    async def _validate_resource_patch_payload(self, payload: Dict[str, Any], request: Request) -> None:
        """
        Validate resource patch payload
        """
        try:
            # Validate using Pydantic model
            patch = UIResourcePatch(**payload)
            
            # Additional validation for patch operations
            self._validate_patch_operations_structure(patch.ops)
            
            logger.debug("Resource patch payload validation passed")
            
        except Exception as e:
            raise ValueError(f"Resource patch validation failed: {e}")
    
    def _validate_patch_operations_structure(self, ops: List[Dict[str, Any]]) -> None:
        """
        Validate the structure of JSON Patch operations
        """
        valid_operations = ['add', 'remove', 'replace', 'move', 'copy', 'test']
        protected_paths = ['/id', '/tenantId', '/sessionId', '/agentId', '/createdAt', '/version']
        
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                raise ValueError(f"Operation {i} must be a dictionary")
            
            if 'op' not in op:
                raise ValueError(f"Operation {i} missing 'op' field")
            
            if 'path' not in op:
                raise ValueError(f"Operation {i} missing 'path' field")
            
            if op['op'] not in valid_operations:
                raise ValueError(f"Operation {i} has invalid operation '{op['op']}'. Valid: {valid_operations}")
            
            path = op['path']
            if not isinstance(path, str) or not path.startswith('/'):
                raise ValueError(f"Operation {i} path must be a string starting with '/'")
            
            # Check for protected field modifications
            for protected_path in protected_paths:
                if path.startswith(protected_path):
                    raise ValueError(f"Operation {i} attempts to modify protected field: {path}")
    
    async def _validate_response_payload(self, request: Request, response: Response) -> None:
        """
        Validate the response payload contains valid UI resources
        """
        try:
            # This is optional validation - we don't want to break responses
            # Just log any validation issues for monitoring
            
            # Read response body (this is complex with FastAPI responses)
            # For now, we'll skip response validation to avoid complexity
            # but log that we should validate responses
            
            logger.debug(f"Response validation skipped for {request.method} {request.url.path}")
            
        except Exception as e:
            logger.warning(f"Response validation error (non-critical): {e}")


# Validation utility functions that can be used directly in routes
def validate_ui_resource_schema(resource_data: Dict[str, Any], version: str = "2025-10-21") -> None:
    """
    Utility function to validate UI resource against JSON schema
    
    Args:
        resource_data: Resource data to validate
        version: Schema version to use
        
    Raises:
        ValueError: If validation fails
    """
    try:
        ui_resource_validator.validate(resource_data, version)
    except ValueError as e:
        raise ValueError(f"JSON schema validation failed: {e}")


def validate_ui_resource_payload(payload: Dict[str, Any], resource_type: str, version: str = "2025-10-21") -> None:
    """
    Utility function to validate UI resource payload by type
    
    Args:
        payload: Payload data to validate
        resource_type: Type of resource (card, list, form, chart)
        version: Schema version to use
        
    Raises:
        ValueError: If validation fails
    """
    try:
        ui_resource_validator.validate_payload_by_type(payload, resource_type, version)
    except ValueError as e:
        raise ValueError(f"Payload validation failed for {resource_type}: {e}")


def validate_resource_create_request(request_data: Dict[str, Any]) -> UIResourceCreate:
    """
    Validate and parse resource creation request
    
    Args:
        request_data: Request payload data
        
    Returns:
        Validated UIResourceCreate instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Validate using Pydantic model
        resource_create = UIResourceCreate(**request_data)
        
        # Convert to full resource and validate schema
        resource = resource_create.to_ui_resource()
        ui_resource_validator.validate(resource.model_dump(), resource.version)
        
        return resource_create
        
    except Exception as e:
        raise ValueError(f"Resource creation request validation failed: {e}")


def validate_resource_patch_request(request_data: Dict[str, Any]) -> UIResourcePatch:
    """
    Validate and parse resource patch request
    
    Args:
        request_data: Request payload data
        
    Returns:
        Validated UIResourcePatch instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        # Validate using Pydantic model
        patch = UIResourcePatch(**request_data)
        
        # Additional validation for patch operations
        valid_operations = ['add', 'remove', 'replace', 'move', 'copy', 'test']
        protected_paths = ['/id', '/tenantId', '/sessionId', '/agentId', '/createdAt', '/version']
        
        for i, op in enumerate(patch.ops):
            if op.get('op') not in valid_operations:
                raise ValueError(f"Invalid patch operation: {op.get('op')}")
            
            path = op.get('path', '')
            for protected_path in protected_paths:
                if path.startswith(protected_path):
                    raise ValueError(f"Cannot modify protected field: {path}")
        
        return patch
        
    except Exception as e:
        raise ValueError(f"Resource patch request validation failed: {e}")