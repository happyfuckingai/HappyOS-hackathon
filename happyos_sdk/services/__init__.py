"""
HappyOS Service Facades

Provides AWS service facades with circuit breaker protection and
unified interfaces for database, storage, compute, and other services.
"""

from .facades import (
    DatabaseFacade, StorageFacade, ComputeFacade, SearchFacade,
    SecretsFacade, CacheFacade, create_service_facades
)

__all__ = [
    "DatabaseFacade",
    "StorageFacade", 
    "ComputeFacade",
    "SearchFacade",
    "SecretsFacade",
    "CacheFacade",
    "create_service_facades",
]