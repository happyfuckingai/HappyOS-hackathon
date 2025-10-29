"""Version information for HappyOS SDK."""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)

# Build metadata
__build__ = "enterprise"
__author__ = "HappyOS Team"
__email__ = "sdk@happyos.com"
__license__ = "MIT"
__copyright__ = "Copyright 2024 HappyOS"

def get_version() -> str:
    """Get the current version string."""
    return __version__

def get_version_info() -> tuple:
    """Get version as tuple for programmatic comparison."""
    return __version_info__