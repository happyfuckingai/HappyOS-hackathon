"""
Test runner for AWS LLM adapter integration tests.

This runner directly imports the necessary modules to avoid
dependency issues with the full package imports.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Set environment variable to skip tests if AWS is not configured
if not os.getenv("AWS_REGION"):
    print("AWS_REGION not set. Setting SKIP_AWS_INTEGRATION_TESTS=1")
    os.environ["SKIP_AWS_INTEGRATION_TESTS"] = "1"

if not os.getenv("OPENAI_API_KEY"):
    print("OPENAI_API_KEY not set. Some tests may be skipped.")

# Now run the tests
import pytest

if __name__ == "__main__":
    # Run with verbose output
    exit_code = pytest.main([
        "backend/tests/test_aws_llm_adapter_integration.py",
        "-v",
        "-s",
        "--tb=short",
        "-x"  # Stop on first failure
    ])
    
    sys.exit(exit_code)
