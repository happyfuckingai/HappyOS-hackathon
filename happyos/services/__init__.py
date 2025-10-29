"""
HappyOS Service Facades

Unified AWS service facades with built-in circuit breakers, retry logic,
and intelligent fallback patterns for maximum uptime.
"""

from .facades import UnifiedServiceFacades, ServiceFacade
from .unified import (
    DatabaseService,
    StorageService, 
    ComputeService,
    SearchService,
    MessagingService,
)

__all__ = [
    "UnifiedServiceFacades",
    "ServiceFacade",
    "DatabaseService",
    "StorageService",
    "ComputeService", 
    "SearchService",
    "MessagingService",
]