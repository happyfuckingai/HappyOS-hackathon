"""
Repository exceptions
"""


class UIResourceRepositoryError(Exception):
    """Base exception for repository operations"""
    pass


class ResourceNotFoundError(UIResourceRepositoryError):
    """Raised when a resource is not found"""
    pass


class ResourceConflictError(UIResourceRepositoryError):
    """Raised when there's a conflict (e.g., revision mismatch)"""
    pass


class TenantIsolationError(UIResourceRepositoryError):
    """Raised when tenant isolation is violated"""
    pass