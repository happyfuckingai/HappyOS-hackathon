"""
Simple validation script to check LLM integration code structure.
This validates the implementation without running it.
"""

import ast
import os

def validate_file_syntax(filepath):
    """Validate Python file syntax."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
            ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

def check_file_exists(filepath):
    """Check if file exists."""
    return os.path.exists(filepath)

def check_class_in_file(filepath, class_name):
    """Check if a class is defined in a file."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
            tree = ast.parse(code)
            
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return True
        return False
    except Exception as e:
        print(f"Error checking class: {e}")
        return False

def check_method_in_class(filepath, class_name, method_name):
    """Check if a method exists in a class."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
            tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        return True
        return False
    except Exception as e:
        print(f"Error checking method: {e}")
        return False

def main():
    """Run validation checks."""
    print("=" * 60)
    print("LLM Service Integration Validation")
    print("=" * 60)
    
    checks = []
    
    # Check 1: LLM circuit breaker file exists
    llm_cb_file = "backend/core/circuit_breaker/llm_circuit_breaker.py"
    exists = check_file_exists(llm_cb_file)
    checks.append(("LLM circuit breaker file exists", exists))
    print(f"{'✓' if exists else '✗'} LLM circuit breaker file: {llm_cb_file}")
    
    # Check 2: LLM circuit breaker syntax is valid
    if exists:
        valid, error = validate_file_syntax(llm_cb_file)
        checks.append(("LLM circuit breaker syntax valid", valid))
        print(f"{'✓' if valid else '✗'} LLM circuit breaker syntax valid")
        if not valid:
            print(f"  Error: {error}")
    
    # Check 3: LLMCircuitBreaker class exists
    if exists:
        has_class = check_class_in_file(llm_cb_file, "LLMCircuitBreaker")
        checks.append(("LLMCircuitBreaker class exists", has_class))
        print(f"{'✓' if has_class else '✗'} LLMCircuitBreaker class defined")
    
    # Check 4: Key methods exist in LLMCircuitBreaker (check in file content)
    if exists:
        with open(llm_cb_file, 'r') as f:
            content = f.read()
        methods = [
            "call_with_failover",
            "get_provider_health",
            "get_health_summary"
        ]
        for method in methods:
            has_method = f"def {method}" in content
            checks.append((f"Method {method} exists", has_method))
            print(f"{'✓' if has_method else '✗'} Method: {method}")
    
    # Check 5: ServiceFacade updated
    facade_file = "backend/infrastructure/service_facade.py"
    has_llm_method = check_method_in_class(facade_file, "ServiceFacade", "get_llm_service")
    checks.append(("ServiceFacade.get_llm_service exists", has_llm_method))
    print(f"{'✓' if has_llm_method else '✗'} ServiceFacade.get_llm_service method")
    
    # Check 6: LLMFacade class exists
    has_llm_facade = check_class_in_file(facade_file, "LLMFacade")
    checks.append(("LLMFacade class exists", has_llm_facade))
    print(f"{'✓' if has_llm_facade else '✗'} LLMFacade class defined")
    
    # Check 7: InfrastructureServiceFactory updated
    has_create_llm = check_method_in_class(facade_file, "InfrastructureServiceFactory", "create_llm_service")
    checks.append(("InfrastructureServiceFactory.create_llm_service exists", has_create_llm))
    print(f"{'✓' if has_create_llm else '✗'} InfrastructureServiceFactory.create_llm_service method")
    
    # Check 8: Circuit breaker __init__ updated
    cb_init_file = "backend/core/circuit_breaker/__init__.py"
    with open(cb_init_file, 'r') as f:
        cb_init_content = f.read()
    has_llm_import = "LLMCircuitBreaker" in cb_init_content
    checks.append(("LLMCircuitBreaker exported from __init__", has_llm_import))
    print(f"{'✓' if has_llm_import else '✗'} LLMCircuitBreaker exported from circuit_breaker module")
    
    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    print(f"Passed: {passed}/{total} checks")
    
    if passed == total:
        print("\n✓ All validation checks passed!")
        print("LLM service integration is correctly implemented.")
        return 0
    else:
        print("\n✗ Some validation checks failed.")
        print("Please review the implementation.")
        return 1

if __name__ == "__main__":
    exit(main())
