"""
Infrastructure Migration Module

Provides utilities for migrating infrastructure and data between cloud providers
while maintaining module isolation via HappyOS SDK.
"""

from .gcp_to_aws_migrator import (
    GCPToAWSMigrator,
    MigrationConfig,
    MigrationResult,
    MigrationStatus,
    MigrationStep,
    ResourceType,
    ResourceMapping,
    create_gcp_to_aws_migrator,
    create_felicia_finance_migration_config,
    get_global_migrator,
    shutdown_global_migrator
)

__all__ = [
    "GCPToAWSMigrator",
    "MigrationConfig", 
    "MigrationResult",
    "MigrationStatus",
    "MigrationStep",
    "ResourceType",
    "ResourceMapping",
    "create_gcp_to_aws_migrator",
    "create_felicia_finance_migration_config",
    "get_global_migrator",
    "shutdown_global_migrator"
]