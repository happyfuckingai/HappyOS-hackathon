"""
HappyOS SDK Version Management

Semantic versioning for the HappyOS SDK following enterprise standards.
"""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)

# Version components
MAJOR = 1
MINOR = 0
PATCH = 0

# Build metadata
BUILD_DATE = "2024-10-29"
BUILD_COMMIT = "initial"

def get_version() -> str:
    """Get the current SDK version."""
    return __version__

def get_version_info() -> tuple:
    """Get version as tuple (major, minor, patch)."""
    return __version_info__