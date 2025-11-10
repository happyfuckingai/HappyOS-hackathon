"""
🔄 DATABASE MIGRATIONS - SCHEMA MANAGEMENT

Handles database schema creation, updates, and migrations:
- Initial schema setup
- Version management
- Schema updates and rollbacks
- Data migrations
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from .connection import DatabaseConnection
from .models import SQLITE_SCHEMA, SQLITE_INDEXES

logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """
    Database migration manager for HappyOS.
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.current_version = "1.0.0"
        
        # Migration definitions
        self.migrations = {
            "1.0.0": {
                "description": "Initial schema setup",
                "up": self._migration_1_0_0_up,
                "down": self._migration_1_0_0_down
            }
        }
    
    async def initialize_schema(self) -> Dict[str, Any]:
        """Initialize database schema."""
        logger.info("Initializing database schema...")
        
        try:
            # Create migration tracking table first
            await self._create_migration_table()
            
            # Check current schema version
            current_version = await self._get_current_version()
            
            if current_version is None:
                # Fresh installation
                logger.info("Fresh database installation detected")
                await self._run_migration("1.0.0", direction="up")
                await self._set_version("1.0.0")
                
                result = {
                    "schema_initialized": True,
                    "version": "1.0.0",
                    "migration_type": "fresh_install",
                    "tables_created": len(SQLITE_SCHEMA),
                    "indexes_created": len(SQLITE_INDEXES)
                }
            else:
                # Existing installation
                logger.info(f"Existing database found (version: {current_version})")
                
                # Check if migration is needed
                if current_version != self.current_version:
                    logger.info(f"Migration needed: {current_version} -> {self.current_version}")
                    await self._migrate_to_version(self.current_version)
                
                result = {
                    "schema_initialized": True,
                    "version": current_version,
                    "migration_type": "existing_database",
                    "migration_needed": current_version != self.current_version
                }
            
            # Verify schema integrity
            integrity_check = await self._verify_schema_integrity()
            result.update(integrity_check)
            
            logger.info(f"Schema initialization completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise
    
    async def _create_migration_table(self):
        """Create migration tracking table."""
        migration_table_sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at TEXT NOT NULL,
                applied_by TEXT DEFAULT 'system'
            )
        """
        
        await self.db.execute_query(migration_table_sql)
        logger.debug("Migration tracking table created")
    
    async def _get_current_version(self) -> Optional[str]:
        """Get current schema version."""
        try:
            result = await self.db.execute_query(
                "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
            )
            return result[0][0] if result else None
        except Exception:
            return None
    
    async def _set_version(self, version: str, description: str = None):
        """Set current schema version."""
        await self.db.execute_query(
            "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
            (version, description or f"Migration to {version}", datetime.utcnow().isoformat())
        )
        logger.info(f"Schema version set to: {version}")
    
    async def _run_migration(self, version: str, direction: str = "up"):
        """Run a specific migration."""
        if version not in self.migrations:
            raise ValueError(f"Migration {version} not found")
        
        migration = self.migrations[version]
        logger.info(f"Running migration {version} ({direction}): {migration['description']}")
        
        try:
            if direction == "up":
                await migration["up"]()
            elif direction == "down":
                await migration["down"]()
            else:
                raise ValueError(f"Invalid migration direction: {direction}")
            
            logger.info(f"Migration {version} ({direction}) completed successfully")
            
        except Exception as e:
            logger.error(f"Migration {version} ({direction}) failed: {e}")
            raise
    
    async def _migrate_to_version(self, target_version: str):
        """Migrate to a specific version."""
        current_version = await self._get_current_version()
        
        if current_version == target_version:
            logger.info(f"Already at target version: {target_version}")
            return
        
        # For now, we only support forward migration to 1.0.0
        if target_version == "1.0.0" and current_version is None:
            await self._run_migration("1.0.0", "up")
            await self._set_version("1.0.0")
        else:
            logger.warning(f"Migration from {current_version} to {target_version} not implemented")
    
    async def _migration_1_0_0_up(self):
        """Migration 1.0.0 - Initial schema setup."""
        logger.info("Creating initial database schema...")
        
        # Create all tables
        for table_name, table_sql in SQLITE_SCHEMA.items():
            logger.debug(f"Creating table: {table_name}")
            await self.db.execute_query(table_sql)
        
        # Create indexes
        for index_sql in SQLITE_INDEXES:
            logger.debug(f"Creating index: {index_sql}")
            await self.db.execute_query(index_sql)
        
        # Insert default configuration
        await self._insert_default_config()
        
        logger.info("Initial schema setup completed")
    
    async def _migration_1_0_0_down(self):
        """Migration 1.0.0 rollback - Drop all tables."""
        logger.warning("Rolling back initial schema (dropping all tables)")
        
        tables = list(SQLITE_SCHEMA.keys())
        tables.reverse()  # Drop in reverse order to handle foreign keys
        
        for table_name in tables:
            await self.db.execute_query(f"DROP TABLE IF EXISTS {table_name}")
            logger.debug(f"Dropped table: {table_name}")
    
    async def _insert_default_config(self):
        """Insert default system configuration."""
        default_configs = [
            ("skill_cache_ttl_hours", "24", "integer", "Skill cache TTL in hours"),
            ("max_conversation_history", "1000", "integer", "Maximum messages per conversation"),
            ("default_language", "en", "string", "Default system language"),
            ("enable_analytics", "true", "boolean", "Enable usage analytics"),
            ("max_skill_generation_attempts", "3", "integer", "Maximum skill generation retry attempts"),
            ("similarity_threshold", "0.7", "float", "Skill similarity matching threshold"),
            ("performance_monitoring", "true", "boolean", "Enable performance monitoring"),
            ("auto_cleanup_days", "30", "integer", "Auto cleanup old data after N days"),
            ("max_concurrent_requests", "10", "integer", "Maximum concurrent request processing"),
            ("enable_personality_learning", "true", "boolean", "Enable personality adaptation learning")
        ]
        
        for config_key, config_value, config_type, description in default_configs:
            await self.db.execute_query(
                """INSERT OR IGNORE INTO system_config 
                   (config_key, config_value, config_type, description, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (config_key, config_value, config_type, description, 
                 datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
        
        logger.info("Default configuration inserted")
    
    async def _verify_schema_integrity(self) -> Dict[str, Any]:
        """Verify database schema integrity."""
        logger.info("Verifying schema integrity...")
        
        try:
            integrity_results = {
                "tables_exist": True,
                "indexes_exist": True,
                "foreign_keys_valid": True,
                "config_populated": True,
                "issues": []
            }
            
            # Check if all tables exist
            for table_name in SQLITE_SCHEMA.keys():
                result = await self.db.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not result:
                    integrity_results["tables_exist"] = False
                    integrity_results["issues"].append(f"Missing table: {table_name}")
            
            # Check if indexes exist
            for index_sql in SQLITE_INDEXES:
                # Extract index name from SQL
                index_name = index_sql.split("CREATE INDEX IF NOT EXISTS ")[1].split(" ON ")[0]
                result = await self.db.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                )
                if not result:
                    integrity_results["indexes_exist"] = False
                    integrity_results["issues"].append(f"Missing index: {index_name}")
            
            # Check if default config exists
            config_count = await self.db.execute_query(
                "SELECT COUNT(*) FROM system_config"
            )
            if not config_count or config_count[0][0] == 0:
                integrity_results["config_populated"] = False
                integrity_results["issues"].append("No system configuration found")
            
            # Overall integrity status
            integrity_results["overall_status"] = (
                integrity_results["tables_exist"] and 
                integrity_results["indexes_exist"] and 
                integrity_results["config_populated"]
            )
            
            if integrity_results["overall_status"]:
                logger.info("Schema integrity verification passed")
            else:
                logger.warning(f"Schema integrity issues found: {integrity_results['issues']}")
            
            return integrity_results
            
        except Exception as e:
            logger.error(f"Schema integrity verification failed: {e}")
            return {
                "overall_status": False,
                "error": str(e),
                "issues": [f"Verification failed: {str(e)}"]
            }
    
    async def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get migration history."""
        try:
            result = await self.db.execute_query(
                "SELECT version, description, applied_at, applied_by FROM schema_migrations ORDER BY applied_at"
            )
            
            return [
                {
                    "version": row[0],
                    "description": row[1],
                    "applied_at": row[2],
                    "applied_by": row[3]
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []
    
    async def backup_schema(self) -> Dict[str, Any]:
        """Create a schema backup."""
        try:
            backup_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "version": await self._get_current_version(),
                "tables": {},
                "indexes": []
            }
            
            # Get table schemas
            for table_name in SQLITE_SCHEMA.keys():
                result = await self.db.execute_query(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if result:
                    backup_data["tables"][table_name] = result[0][0]
            
            # Get index schemas
            result = await self.db.execute_query(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            )
            backup_data["indexes"] = [row[0] for row in result]
            
            logger.info("Schema backup created successfully")
            return backup_data
            
        except Exception as e:
            logger.error(f"Schema backup failed: {e}")
            raise
    
    async def cleanup_old_migrations(self, keep_count: int = 10):
        """Clean up old migration records."""
        try:
            # Keep only the most recent N migration records
            await self.db.execute_query(
                """DELETE FROM schema_migrations 
                   WHERE version NOT IN (
                       SELECT version FROM schema_migrations 
                       ORDER BY applied_at DESC LIMIT ?
                   )""",
                (keep_count,)
            )
            
            logger.info(f"Cleaned up old migration records (kept {keep_count} most recent)")
            
        except Exception as e:
            logger.error(f"Migration cleanup failed: {e}")
            raise

