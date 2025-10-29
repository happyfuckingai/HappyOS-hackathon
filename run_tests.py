#!/usr/bin/env python3
"""
HappyOS SDK Test Runner

Comprehensive test runner for the HappyOS SDK with different test categories
and reporting options.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return the result."""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="HappyOS SDK Test Runner")
    
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "performance", "all"],
        default="all",
        help="Type of tests to run"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests"
    )
    
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        help="Run tests in parallel (requires pytest-xdist)"
    )
    
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML test report"
    )
    
    parser.add_argument(
        "--junit-xml",
        help="Generate JUnit XML report file"
    )
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("happyos").exists():
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test type markers
    if args.type == "unit":
        cmd.extend(["-m", "unit"])
    elif args.type == "integration":
        cmd.extend(["-m", "integration"])
    elif args.type == "performance":
        cmd.extend(["-m", "performance"])
    elif args.type == "all":
        pass  # Run all tests
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend([
            "--cov=happyos",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Skip slow tests if requested
    if args.fast:
        cmd.extend(["-m", "not slow"])
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])
    
    # Add HTML report
    if args.html_report:
        cmd.extend(["--html=test_report.html", "--self-contained-html"])
    
    # Add JUnit XML report
    if args.junit_xml:
        cmd.extend(["--junit-xml", args.junit_xml])
    
    # Add test directory
    cmd.append("tests/")
    
    # Run the tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if success:
        print("\n✅ All tests passed!")
        
        if args.coverage:
            print("\n📊 Coverage report generated:")
            print("  - HTML: htmlcov/index.html")
            print("  - XML: coverage.xml")
        
        if args.html_report:
            print("\n📋 HTML test report: test_report.html")
        
        if args.junit_xml:
            print(f"\n📄 JUnit XML report: {args.junit_xml}")
    
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


def run_specific_tests():
    """Run specific test categories with predefined configurations."""
    
    print("HappyOS SDK Test Suite")
    print("=" * 50)
    
    # Unit tests (fast)
    print("\n1. Running Unit Tests...")
    unit_success = run_command([
        "python", "-m", "pytest",
        "-m", "unit",
        "-v",
        "--tb=short",
        "tests/"
    ], "Unit Tests")
    
    # Integration tests
    print("\n2. Running Integration Tests...")
    integration_success = run_command([
        "python", "-m", "pytest",
        "-m", "integration",
        "-v",
        "--tb=short",
        "tests/"
    ], "Integration Tests")
    
    # Performance tests (if requested)
    print("\n3. Running Performance Tests...")
    perf_success = run_command([
        "python", "-m", "pytest",
        "-m", "performance",
        "-v",
        "--tb=short",
        "tests/"
    ], "Performance Tests")
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"Unit Tests:        {'✅ PASSED' if unit_success else '❌ FAILED'}")
    print(f"Integration Tests: {'✅ PASSED' if integration_success else '❌ FAILED'}")
    print(f"Performance Tests: {'✅ PASSED' if perf_success else '❌ FAILED'}")
    
    overall_success = unit_success and integration_success and perf_success
    
    if overall_success:
        print("\n🎉 All test suites passed!")
        return True
    else:
        print("\n💥 Some test suites failed!")
        return False


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments, run the comprehensive test suite
        success = run_specific_tests()
        sys.exit(0 if success else 1)
    else:
        # Arguments provided, use the argument parser
        main()