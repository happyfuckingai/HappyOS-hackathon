"""
UI Resource Data Models and Validation

Comprehensive Pydantic models for UI resources with JSON schema validation,
TTL support, idempotency keys, and multi-tenant isolation.

Requirements: 2.1, 4.1
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
import jsonschema


class UIResourcePayload(BaseModel):
    """Base class for UI resource payloads"""
    pass


class CardPayload(UIResourcePayload):
    """Card UI resource payload with actions support"""
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, pattern="^(info|success|warning|error)$")
    actions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    
    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v):
        """Validate action structure"""
        if not v:
            return v
        
        for action in v:
            if not isinstance(action, dict):
                raise ValueError("Each action must be a dictionary")
            if 'label' not in action:
                raise ValueError("Each action must have a 'label' field")
            if 'type' not in action:
                raise ValueError("Each action must have a 'type' field")
            if action['type'] not in ['button', 'link', 'submit']:
                raise ValueError("Action type must be 'button', 'link', or 'submit'")
        
        return v


class ListPayload(UIResourcePayload):
    """List UI resource payload with item type support"""
    title: str = Field(..., min_length=1, max_length=200)
    items: List[str] = Field(..., min_items=0, max_items=100)
    itemType: Optional[str] = Field(default="text", pattern="^(text|link|badge)$")
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        """Validate list items"""
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All items must be strings")
            if len(item) > 500:
                raise ValueError("Item length cannot exceed 500 characters")
        return v


class FormField(BaseModel):
    """Form field definition"""
    name: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(text|email|password|number|select|textarea|checkbox|radio)$")
    required: bool = Field(default=False)
    placeholder: Optional[str] = Field(None, max_length=200)
    options: Optional[List[str]] = Field(None)
    validation: Optional[Dict[str, Any]] = Field(None)
    
    @model_validator(mode='after')
    def validate_options(self):
        """Validate options for select/radio fields"""
        if self.type in ['select', 'radio'] and not self.options:
            raise ValueError("Select and radio fields must have options")
        return self


class FormPayload(UIResourcePayload):
    """Form UI resource payload with field validation"""
    title: str = Field(..., min_length=1, max_length=200)
    fields: List[FormField] = Field(..., min_items=1, max_items=20)
    submitUrl: Optional[str] = Field(None, max_length=500)
    submitMethod: Optional[str] = Field(default="POST", pattern="^(POST|PUT|PATCH)$")
    
    @field_validator('fields')
    @classmethod
    def validate_unique_field_names(cls, v):
        """Ensure field names are unique"""
        names = [field.name for field in v]
        if len(names) != len(set(names)):
            raise ValueError("Field names must be unique")
        return v


class ChartData(BaseModel):
    """Chart data structure"""
    labels: Optional[List[str]] = Field(None, max_items=50)
    datasets: List[Dict[str, Any]] = Field(..., min_items=1, max_items=10)
    
    @field_validator('datasets')
    @classmethod
    def validate_datasets(cls, v):
        """Validate chart datasets"""
        for dataset in v:
            if not isinstance(dataset, dict):
                raise ValueError("Each dataset must be a dictionary")
            if 'data' not in dataset:
                raise ValueError("Each dataset must have a 'data' field")
            if not isinstance(dataset['data'], list):
                raise ValueError("Dataset 'data' must be a list")
            if len(dataset['data']) > 100:
                raise ValueError("Dataset cannot have more than 100 data points")
        return v


class ChartPayload(UIResourcePayload):
    """Chart UI resource payload with data validation"""
    title: str = Field(..., min_length=1, max_length=200)
    chartType: str = Field(..., pattern="^(line|bar|pie|doughnut|scatter|area)$")
    data: ChartData = Field(...)
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('options')
    @classmethod
    def validate_options(cls, v):
        """Validate chart options"""
        if not isinstance(v, dict):
            raise ValueError("Options must be a dictionary")
        return v


class UIResource(BaseModel):
    """
    Complete UI Resource model with multi-tenant isolation, versioning, and TTL support
    
    Supports all resource types: card, list, form, chart
    Includes revision management, idempotency keys, and tenant isolation
    """
    # Core identification
    id: str = Field(..., pattern=r"^mm://[a-z0-9-]+/[a-zA-Z0-9-_]+/[a-z0-9-]+/[a-zA-Z0-9-_]+$")
    tenantId: str = Field(..., pattern="^[a-z0-9-]+$")
    sessionId: str = Field(..., pattern="^[a-zA-Z0-9-_]+$")
    agentId: str = Field(..., pattern="^[a-z0-9-]+$")
    
    # Resource type and versioning
    type: str = Field(..., pattern="^(card|list|form|chart)$")
    version: str = Field(default="2025-10-21")
    revision: int = Field(default=1, ge=1)
    
    # Payload (validated based on type)
    payload: Union[CardPayload, ListPayload, FormPayload, ChartPayload] = Field(...)
    
    # Metadata
    tags: List[str] = Field(default_factory=list, max_items=10)
    ttlSeconds: Optional[int] = Field(None, ge=1, le=86400)  # Max 24 hours
    idempotencyKey: Optional[str] = Field(None, min_length=1, max_length=100)
    
    # Timestamps
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expiresAt: Optional[str] = Field(None)
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v):
        """Ensure version is supported"""
        supported_versions = ["2025-10-21"]
        if v not in supported_versions:
            raise ValueError(f"Unsupported version: {v}. Supported: {supported_versions}")
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tag format and uniqueness"""
        if not v:
            return v
        
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Tags must be unique")
        
        # Validate tag format
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")
            if len(tag) > 50:
                raise ValueError("Tag length cannot exceed 50 characters")
            if not tag.replace('-', '').replace('_', '').isalnum():
                raise ValueError("Tags can only contain alphanumeric characters, hyphens, and underscores")
        
        return v
    
    @model_validator(mode='after')
    def validate_id_format(self):
        """Validate ID matches tenant/session/agent from other fields"""
        expected_prefix = f"mm://{self.tenantId}/{self.sessionId}/{self.agentId}/"
        if not self.id.startswith(expected_prefix):
            raise ValueError(f"ID must start with {expected_prefix}")
        return self
    
    @model_validator(mode='after')
    def validate_payload_type(self):
        """Validate payload matches the declared type"""
        # Type mapping
        type_mapping = {
            'card': CardPayload,
            'list': ListPayload,
            'form': FormPayload,
            'chart': ChartPayload
        }
        
        expected_type = type_mapping.get(self.type)
        if expected_type and not isinstance(self.payload, expected_type):
            # Try to convert if it's a dict
            if isinstance(self.payload, dict):
                try:
                    self.payload = expected_type(**self.payload)
                except Exception as e:
                    raise ValueError(f"Invalid payload for type {self.type}: {e}")
            else:
                raise ValueError(f"Payload must be {expected_type.__name__} for type {self.type}")
        
        return self
    
    @model_validator(mode='after')
    def calculate_expiry(self):
        """Calculate expiry timestamp if TTL is provided"""
        if self.ttlSeconds and self.createdAt:
            try:
                created_dt = datetime.fromisoformat(self.createdAt.replace('Z', '+00:00'))
                expires_dt = created_dt + timedelta(seconds=self.ttlSeconds)
                self.expiresAt = expires_dt.isoformat()
            except Exception:
                # If parsing fails, don't set expiry
                pass
        
        return self
    
    def is_expired(self) -> bool:
        """Check if resource has expired based on TTL"""
        if not self.expiresAt:
            return False
        
        try:
            expires_dt = datetime.fromisoformat(self.expiresAt.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expires_dt
        except Exception:
            return False
    
    def time_to_expiry(self) -> Optional[int]:
        """Get seconds until expiry, None if no TTL"""
        if not self.expiresAt:
            return None
        
        try:
            expires_dt = datetime.fromisoformat(self.expiresAt.replace('Z', '+00:00'))
            delta = expires_dt - datetime.now(timezone.utc)
            return max(0, int(delta.total_seconds()))
        except Exception:
            return None


class UIResourceCreate(BaseModel):
    """Model for creating UI resources (without auto-generated fields)"""
    # Core identification
    tenantId: str = Field(..., pattern="^[a-z0-9-]+$")
    sessionId: str = Field(..., pattern="^[a-zA-Z0-9-_]+$")
    agentId: str = Field(..., pattern="^[a-z0-9-]+$")
    name: str = Field(..., pattern="^[a-zA-Z0-9-_]+$", min_length=1, max_length=100)
    
    # Resource type and versioning
    type: str = Field(..., pattern="^(card|list|form|chart)$")
    version: str = Field(default="2025-10-21")
    
    # Payload
    payload: Dict[str, Any] = Field(...)
    
    # Metadata
    tags: List[str] = Field(default_factory=list, max_items=10)
    ttlSeconds: Optional[int] = Field(None, ge=1, le=86400)
    idempotencyKey: Optional[str] = Field(None, min_length=1, max_length=100)
    
    def to_ui_resource(self) -> UIResource:
        """Convert to full UIResource with generated ID"""
        resource_id = f"mm://{self.tenantId}/{self.sessionId}/{self.agentId}/{self.name}"
        
        # Create payload object based on type
        type_mapping = {
            'card': CardPayload,
            'list': ListPayload,
            'form': FormPayload,
            'chart': ChartPayload
        }
        
        payload_class = type_mapping[self.type]
        payload_obj = payload_class(**self.payload)
        
        return UIResource(
            id=resource_id,
            tenantId=self.tenantId,
            sessionId=self.sessionId,
            agentId=self.agentId,
            type=self.type,
            version=self.version,
            payload=payload_obj,
            tags=self.tags,
            ttlSeconds=self.ttlSeconds,
            idempotencyKey=self.idempotencyKey
        )


class UIResourcePatch(BaseModel):
    """JSON Patch operations for UI Resource updates"""
    ops: List[Dict[str, Any]] = Field(..., min_items=1, max_items=20)
    
    @field_validator('ops')
    @classmethod
    def validate_patch_operations(cls, v):
        """Validate JSON Patch operations"""
        valid_ops = ['add', 'remove', 'replace', 'move', 'copy', 'test']
        
        for op in v:
            if not isinstance(op, dict):
                raise ValueError("Each operation must be a dictionary")
            
            if 'op' not in op:
                raise ValueError("Each operation must have an 'op' field")
            
            if op['op'] not in valid_ops:
                raise ValueError(f"Invalid operation: {op['op']}. Valid: {valid_ops}")
            
            if 'path' not in op:
                raise ValueError("Each operation must have a 'path' field")
            
            # Validate path format
            path = op['path']
            if not isinstance(path, str) or not path.startswith('/'):
                raise ValueError("Path must be a string starting with '/'")
            
            # Prevent modification of protected fields
            protected_paths = ['/id', '/tenantId', '/sessionId', '/agentId', '/createdAt']
            if any(path.startswith(protected) for protected in protected_paths):
                raise ValueError(f"Cannot modify protected field: {path}")
        
        return v


class UIResourceQuery(BaseModel):
    """Query parameters for filtering UI resources"""
    tenantId: Optional[str] = Field(None, pattern="^[a-z0-9-]+$")
    sessionId: Optional[str] = Field(None, pattern="^[a-zA-Z0-9-_]+$")
    agentId: Optional[str] = Field(None, pattern="^[a-z0-9-]+$")
    type: Optional[str] = Field(None, pattern="^(card|list|form|chart)$")
    tags: Optional[List[str]] = Field(None, max_items=10)
    includeExpired: bool = Field(default=False)
    limit: Optional[int] = Field(None, ge=1, le=100)
    offset: Optional[int] = Field(None, ge=0)


# JSON Schema for validation (version 2025-10-21)
UI_RESOURCE_SCHEMA_V2025_10_21 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "tenantId": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "sessionId": {"type": "string", "pattern": "^[a-zA-Z0-9-_]+$"},
        "agentId": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "id": {"type": "string", "pattern": "^mm://[a-z0-9-]+/[a-zA-Z0-9-_]+/[a-z0-9-]+/[a-zA-Z0-9-_]+$"},
        "type": {"type": "string", "enum": ["card", "list", "form", "chart"]},
        "version": {"type": "string", "const": "2025-10-21"},
        "revision": {"type": "integer", "minimum": 1},
        "payload": {"type": "object"},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "ttlSeconds": {"type": ["integer", "null"], "minimum": 1, "maximum": 86400},
        "idempotencyKey": {"type": ["string", "null"], "minLength": 1, "maxLength": 100},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": "string"},
        "expiresAt": {"type": ["string", "null"]}
    },
    "required": ["tenantId", "sessionId", "agentId", "id", "type", "version", "payload"],
    "additionalProperties": False,
    "definitions": {
        "cardPayload": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "content": {"type": ["string", "null"], "maxLength": 2000},
                "status": {"type": ["string", "null"], "enum": ["info", "success", "warning", "error", None]},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "minLength": 1},
                            "type": {"type": "string", "enum": ["button", "link", "submit"]},
                            "url": {"type": ["string", "null"]},
                            "action": {"type": ["string", "null"]}
                        },
                        "required": ["label", "type"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["title"],
            "additionalProperties": False
        },
        "listPayload": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "items": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 500},
                    "maxItems": 100
                },
                "itemType": {"type": ["string", "null"], "enum": ["text", "link", "badge", None]}
            },
            "required": ["title", "items"],
            "additionalProperties": False
        },
        "formPayload": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1, "maxLength": 100},
                            "label": {"type": "string", "minLength": 1, "maxLength": 200},
                            "type": {"type": "string", "enum": ["text", "email", "password", "number", "select", "textarea", "checkbox", "radio"]},
                            "required": {"type": "boolean"},
                            "placeholder": {"type": ["string", "null"], "maxLength": 200},
                            "options": {"type": ["array", "null"], "items": {"type": "string"}},
                            "validation": {"type": ["object", "null"]}
                        },
                        "required": ["name", "label", "type"],
                        "additionalProperties": False
                    },
                    "minItems": 1,
                    "maxItems": 20
                },
                "submitUrl": {"type": ["string", "null"], "maxLength": 500},
                "submitMethod": {"type": ["string", "null"], "enum": ["POST", "PUT", "PATCH", None]}
            },
            "required": ["title", "fields"],
            "additionalProperties": False
        },
        "chartPayload": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "chartType": {"type": "string", "enum": ["line", "bar", "pie", "doughnut", "scatter", "area"]},
                "data": {
                    "type": "object",
                    "properties": {
                        "labels": {"type": ["array", "null"], "items": {"type": "string"}, "maxItems": 50},
                        "datasets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": ["string", "null"]},
                                    "data": {"type": "array", "items": {"type": "number"}, "maxItems": 100}
                                },
                                "required": ["data"],
                                "additionalProperties": True
                            },
                            "minItems": 1,
                            "maxItems": 10
                        }
                    },
                    "required": ["datasets"],
                    "additionalProperties": False
                },
                "options": {"type": ["object", "null"]}
            },
            "required": ["title", "chartType", "data"],
            "additionalProperties": False
        }
    }
}


class UIResourceValidator:
    """JSON Schema validator for UI resources"""
    
    def __init__(self):
        self.schemas = {
            "2025-10-21": UI_RESOURCE_SCHEMA_V2025_10_21
        }
    
    def validate(self, resource_data: Dict[str, Any], version: str = "2025-10-21") -> None:
        """
        Validate UI resource against JSON schema
        
        Args:
            resource_data: Resource data to validate
            version: Schema version to use
            
        Raises:
            ValueError: If validation fails
        """
        if version not in self.schemas:
            raise ValueError(f"Unsupported schema version: {version}")
        
        schema = self.schemas[version]
        
        try:
            # First validate the overall structure (without payload validation)
            schema_without_payload = schema.copy()
            schema_without_payload["properties"] = schema["properties"].copy()
            schema_without_payload["properties"]["payload"] = {"type": "object"}
            
            jsonschema.validate(resource_data, schema_without_payload)
            
            # Then validate the payload specifically by type
            if "payload" in resource_data and "type" in resource_data:
                self.validate_payload_by_type(
                    resource_data["payload"], 
                    resource_data["type"], 
                    version
                )
                
        except jsonschema.ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message} at path {'.'.join(str(p) for p in e.absolute_path)}")
        except jsonschema.SchemaError as e:
            raise ValueError(f"Invalid schema: {e.message}")
    
    def validate_payload_by_type(self, payload: Dict[str, Any], resource_type: str, version: str = "2025-10-21") -> None:
        """
        Validate payload against type-specific schema
        
        Args:
            payload: Payload data to validate
            resource_type: Type of resource (card, list, form, chart)
            version: Schema version to use
            
        Raises:
            ValueError: If validation fails
        """
        if version not in self.schemas:
            raise ValueError(f"Unsupported schema version: {version}")
        
        schema = self.schemas[version]
        
        if resource_type not in ["card", "list", "form", "chart"]:
            raise ValueError(f"Invalid resource type: {resource_type}")
        
        # Get type-specific schema
        type_schema = schema["definitions"][f"{resource_type}Payload"]
        
        try:
            jsonschema.validate(payload, type_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Payload validation failed for {resource_type}: {e.message}")


# Global validator instance
ui_resource_validator = UIResourceValidator()