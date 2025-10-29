"""
HappyOS Industry-Specific Templates

Pre-built agent templates for regulated industries with built-in
compliance, security, and domain-specific functionality.
"""

# Import industry modules when available
try:
    from . import finance
except ImportError:
    finance = None

try:
    from . import healthcare
except ImportError:
    healthcare = None

try:
    from . import manufacturing
except ImportError:
    manufacturing = None

__all__ = []

# Add available industries to __all__
if finance:
    __all__.append("finance")
if healthcare:
    __all__.append("healthcare")
if manufacturing:
    __all__.append("manufacturing")