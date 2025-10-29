#!/usr/bin/env python3
"""
Migration Test Runner

Script to run comprehensive migration validation tests and generate reports.
"""

import asyncio
import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

# Import test modules
from backend.infrastructure.migration.test_migration_validation import (
    TestMigrationDataIntegrity,
    TestInfrastructureConversionDeployment,
    TestModuleIsolationValidation,
    TestCrossModuleWorkflows,
    TestFinancialDataMigration,
    TestComprehensiveValidationSuite,
    TestEndToEndMigrationValidation
)

# Import migration components
from backend.infrastructure.migration.gcp_to_aws_migrator import (
    GCPToAWSMigrator, create_felicia_finance_migration_config
)
from backend.infrastructure.migration.financial_data_migrator import (
    FinancialDataMigrator, create_felicia_finance_datasets
)
from backend.infrastructure.migration.migration_validator import (
    MigrationValidator
)

logger = logging.getLogger(__name__)


class MigrationTestRunner:
    """Migration test runner and report generator."""
    
    def __init__(self, tenant_id: str = "test_tenant"):
        self.tenant_id = tenant_id
        self.test_results: List[Dict[str, Any]] = []
        self.start_time = datetime.utcnow()
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all migration validation tests."""
        logger.info("Starting comprehensive migration validation tests")
        
        test_suites = [
            ("Data Migration Integrity", self.run_data_integrity_tests),
            ("Infrastructure Conversion", self.run_infrastructure_tests),
            ("Module Isolation", self.run_module_isolation_tests),
            ("Cross-Module Workflows", self.run_workflow_tests),
            ("Financial Data Migration", self.run_financial_migration_tests),
            ("Comprehensive Validation", self.run_comprehensive_tests),
            ("End-to-End Integration", self.run_e2e_tests)
        ]
        
        overall_results = {
            "test_run_id": f"migration_test_{int(self.start_time.timestamp())}",
            "start_time": self.start_time.isoformat(),
            "tenant_id": self.tenant_id,
            "suite_results": [],
            "overall_success": True,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0
        }
        
        for suite_name, test_func in test_suites:
            try:
                logger.info(f"Running test suite: {suite_name}")
                suite_result = await test_func()
                suite_result["suite_name"] = suite_name
                overall_results["suite_results"].append(suite_result)
                
                overall_results["total_tests"] += suite_result.get("total_tests", 0)
                overall_results["passed_tests"] += suite_result.get("passed_tests", 0)
                overall_results["failed_tests"] += suite_result.get("failed_tests", 0)
                
                if not suite_result.get("success", False):
                    overall_results["overall_success"] = False
                    
            except Exception as e:
                logger.error(f"Test suite {suite_name} failed with error: {e}")
                overall_results["suite_results"].append({
                    "suite_name": suite_name,
                    "success": False,
                    "error": str(e),
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 1
                })
                overall_results["overall_success"] = False
                overall_results["failed_tests"] += 1
        
        overall_results["end_time"] = datetime.utcnow().isoformat()
        overall_results["duration_seconds"] = (datetime.utcnow() - self.start_time).total_seconds()
        
        return overall_results
    
    async def run_data_integrity_tests(self) -> Dict[str, Any]:
        """Run data migration integrity tests."""
        test_class = TestMigrationDataIntegrity()
        
        # Create test validator
        validator = MigrationValidator("test_validator", self.tenant_id)
        validator.a2a_client = MockA2AClient()
        validator.database = MockDatabaseFacade()
        validator.storage = MockStorageFacade()
        validator.search = MockSearchFacade()
        validator.is_initialized = True
        
        # Sample metadata
        metadata = {
            "migration_id": "test_migration_001",
            "source_record_count": 1000,
            "target_record_count": 998,
            "source_checksums": ["abc123", "def456", "ghi789"],
            "target_checksums": ["abc123", "def456", "ghi789"],
            "migration_timestamp": datetime.utcnow().isoformat()
        }
        
        tests = [
            ("validate_data_migration_integrity_success", 
             test_class.test_validate_data_migration_integrity_success(validator, metadata)),
            ("validate_data_migration_integrity_failure",
             test_class.test_validate_data_migration_integrity_failure(validator)),
            ("validate_record_counts",
             test_class.test_validate_record_counts(validator)),
            ("validate_record_counts_failure",
             test_class.test_validate_record_counts_failure(validator))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_infrastructure_tests(self) -> Dict[str, Any]:
        """Run infrastructure conversion and deployment tests."""
        test_class = TestInfrastructureConversionDeployment()
        
        # Create test converter
        converter = MockInfrastructureConverter(self.tenant_id)
        
        # Sample Terraform config
        tf_config = {
            "resource": {
                "google_cloud_run_service": {
                    "crypto_service": {
                        "name": "crypto-trading-service",
                        "location": "us-central1"
                    }
                }
            }
        }
        
        tests = [
            ("convert_terraform_to_cdk_success",
             test_class.test_convert_terraform_to_cdk_success(converter, tf_config)),
            ("convert_cloud_run_to_lambda",
             test_class.test_convert_cloud_run_to_lambda(converter))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_module_isolation_tests(self) -> Dict[str, Any]:
        """Run module isolation validation tests."""
        test_class = TestModuleIsolationValidation()
        
        # Create test validator
        validator = MigrationValidator("test_validator", self.tenant_id)
        validator.a2a_client = MockA2AClient()
        validator.database = MockDatabaseFacade()
        validator.storage = MockStorageFacade()
        validator.search = MockSearchFacade()
        validator.is_initialized = True
        
        tests = [
            ("validate_module_isolation_success",
             test_class.test_validate_module_isolation_success(validator)),
            ("import_isolation_validation",
             test_class.test_import_isolation_validation(validator)),
            ("a2a_communication_isolation",
             test_class.test_a2a_communication_isolation(validator)),
            ("database_isolation",
             test_class.test_database_isolation(validator))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_workflow_tests(self) -> Dict[str, Any]:
        """Run cross-module workflow tests."""
        test_class = TestCrossModuleWorkflows()
        
        # Create test validator
        validator = MigrationValidator("test_validator", self.tenant_id)
        validator.a2a_client = MockA2AClient()
        validator.database = MockDatabaseFacade()
        validator.storage = MockStorageFacade()
        validator.search = MockSearchFacade()
        validator.is_initialized = True
        
        tests = [
            ("cross_module_workflows_success",
             test_class.test_cross_module_workflows_success(validator)),
            ("financial_compliance_workflow",
             test_class.test_financial_compliance_workflow(validator)),
            ("financial_reporting_workflow",
             test_class.test_financial_reporting_workflow(validator)),
            ("meeting_financial_analysis_workflow",
             test_class.test_meeting_financial_analysis_workflow(validator))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_financial_migration_tests(self) -> Dict[str, Any]:
        """Run financial data migration tests."""
        test_class = TestFinancialDataMigration()
        
        # Create test financial migrator
        migrator = FinancialDataMigrator("test_financial_migrator", self.tenant_id)
        migrator.a2a_client = MockA2AClient()
        migrator.database = MockDatabaseFacade()
        migrator.storage = MockStorageFacade()
        migrator.search = MockSearchFacade()
        migrator.is_initialized = True
        migrator.circuit_breakers = {
            "bigquery_extraction": MockCircuitBreaker(),
            "opensearch_indexing": MockCircuitBreaker(),
            "dynamodb_storage": MockCircuitBreaker(),
            "s3_transfer": MockCircuitBreaker()
        }
        
        tests = [
            ("migrate_trading_analytics_success",
             test_class.test_migrate_trading_analytics_success(migrator)),
            ("migrate_portfolio_data_success",
             test_class.test_migrate_portfolio_data_success(migrator)),
            ("validate_migration_integrity",
             test_class.test_validate_migration_integrity(migrator))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive validation suite tests."""
        test_class = TestComprehensiveValidationSuite()
        
        # Create test validator
        validator = MigrationValidator("test_validator", self.tenant_id)
        validator.a2a_client = MockA2AClient()
        validator.database = MockDatabaseFacade()
        validator.storage = MockStorageFacade()
        validator.search = MockSearchFacade()
        validator.is_initialized = True
        
        tests = [
            ("comprehensive_validation_suite_success",
             test_class.test_comprehensive_validation_suite_success(validator))
        ]
        
        return await self._run_test_suite(tests)
    
    async def run_e2e_tests(self) -> Dict[str, Any]:
        """Run end-to-end integration tests."""
        test_class = TestEndToEndMigrationValidation()
        
        # Create migration components
        components = {
            "migrator": MockGCPToAWSMigrator(self.tenant_id),
            "financial_migrator": MockFinancialDataMigrator(self.tenant_id),
            "validator": MockMigrationValidator(self.tenant_id)
        }
        
        tests = [
            ("end_to_end_migration_workflow",
             test_class.test_end_to_end_migration_workflow(components))
        ]
        
        return await self._run_test_suite(tests)
    
    async def _run_test_suite(self, tests: List[tuple]) -> Dict[str, Any]:
        """Run a suite of tests and return results."""
        suite_result = {
            "success": True,
            "total_tests": len(tests),
            "passed_tests": 0,
            "failed_tests": 0,
            "test_results": []
        }
        
        for test_name, test_coro in tests:
            try:
                await test_coro
                suite_result["passed_tests"] += 1
                suite_result["test_results"].append({
                    "test_name": test_name,
                    "success": True,
                    "message": "Test passed"
                })
                logger.info(f"✓ {test_name} passed")
                
            except Exception as e:
                suite_result["failed_tests"] += 1
                suite_result["success"] = False
                suite_result["test_results"].append({
                    "test_name": test_name,
                    "success": False,
                    "error": str(e)
                })
                logger.error(f"✗ {test_name} failed: {e}")
        
        return suite_result
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate test report."""
        report = []
        report.append("=" * 80)
        report.append("MIGRATION VALIDATION TEST REPORT")
        report.append("=" * 80)
        report.append(f"Test Run ID: {results['test_run_id']}")
        report.append(f"Start Time: {results['start_time']}")
        report.append(f"End Time: {results['end_time']}")
        report.append(f"Duration: {results['duration_seconds']:.2f} seconds")
        report.append(f"Tenant ID: {results['tenant_id']}")
        report.append("")
        
        # Overall summary
        report.append("OVERALL SUMMARY")
        report.append("-" * 40)
        report.append(f"Overall Success: {'✓ PASS' if results['overall_success'] else '✗ FAIL'}")
        report.append(f"Total Tests: {results['total_tests']}")
        report.append(f"Passed Tests: {results['passed_tests']}")
        report.append(f"Failed Tests: {results['failed_tests']}")
        report.append(f"Success Rate: {(results['passed_tests'] / results['total_tests'] * 100):.1f}%")
        report.append("")
        
        # Suite details
        report.append("TEST SUITE DETAILS")
        report.append("-" * 40)
        
        for suite in results['suite_results']:
            status = "✓ PASS" if suite.get('success', False) else "✗ FAIL"
            report.append(f"{suite['suite_name']}: {status}")
            report.append(f"  Tests: {suite.get('passed_tests', 0)}/{suite.get('total_tests', 0)}")
            
            if 'error' in suite:
                report.append(f"  Error: {suite['error']}")
            
            report.append("")
        
        return "\n".join(report)
    
    def save_report(self, results: Dict[str, Any], output_dir: str = "test_reports"):
        """Save test report to file."""
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        # Save JSON results
        json_file = Path(output_dir) / f"migration_test_results_{results['test_run_id']}.json"
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save text report
        report_text = self.generate_report(results)
        report_file = Path(output_dir) / f"migration_test_report_{results['test_run_id']}.txt"
        with open(report_file, 'w') as f:
            f.write(report_text)
        
        logger.info(f"Test results saved to {json_file}")
        logger.info(f"Test report saved to {report_file}")


# Mock classes for testing
class MockA2AClient:
    async def send_request(self, recipient_id, action, data, timeout=30):
        return {"success": True, "response_time": 0.1, "data": []}

class MockDatabaseFacade:
    async def store_data(self, data, table_name=None, partition_key=None, sort_key=None):
        return {"success": True}
    
    async def query_data(self, query):
        return {"success": True, "data": [{"tenant_id": "test_tenant"}]}

class MockStorageFacade:
    async def upload_file(self, bucket_name, key, data, metadata=None):
        return {"success": True}
    
    async def list_objects(self, bucket_name, prefix=""):
        return {"success": True, "objects": [{"key": f"{prefix}test_object"}]}

class MockSearchFacade:
    async def create_index(self, index_name, mapping, settings):
        return {"success": True}
    
    async def bulk_index(self, index_name, documents):
        return {"success": True}
    
    async def search(self, index_name, query, size=10):
        return {
            "success": True,
            "hits": [
                {"_source": {"trade_id": "trade_001", "tenant_id": "test_tenant"}},
                {"_source": {"trade_id": "trade_002", "tenant_id": "test_tenant"}}
            ]
        }

class MockCircuitBreaker:
    async def execute(self, func):
        return await func()

class MockInfrastructureConverter:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

class MockGCPToAWSMigrator:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

class MockFinancialDataMigrator:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

class MockMigrationValidator:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


async def main():
    """Main test runner function."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test runner
    runner = MigrationTestRunner("test_tenant")
    
    try:
        # Run all tests
        results = await runner.run_all_tests()
        
        # Generate and save report
        print(runner.generate_report(results))
        runner.save_report(results)
        
        # Exit with appropriate code
        sys.exit(0 if results['overall_success'] else 1)
        
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())