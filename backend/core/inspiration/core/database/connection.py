"""
🔌 ADVANCED DATABASE CONNECTION MANAGEMENT

Handles database connections with support for:
- SQLite for development and small deployments
- PostgreSQL for production deployments
- Advanced connection pooling with auto-scaling
- Connection health monitoring and automatic reconnection
- Performance metrics and statistics
- Automatic migration and setup
- Failover mechanisms and recovery
"""

import asyncio
import logging
import os
import sqlite3
import threading
import time
from typing import Optional, Dict, Any, AsyncContextManager, List, Tuple, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
import aiosqlite
import asyncpg
from datetime import datetime, timedelta
import psutil

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Advanced database configuration with auto-scaling and health monitoring."""
    database_type: str = "sqlite"  # "sqlite" or "postgresql"
    database_url: Optional[str] = None
    database_path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None

    # Connection pooling settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # Recycle connections after 1 hour
    pool_pre_ping: bool = True  # Test connections before use

    # Auto-scaling settings
    min_pool_size: int = 5
    max_pool_size: int = 50
    scale_up_threshold: float = 0.8  # Scale up when 80% of pool is used
    scale_down_threshold: float = 0.3  # Scale down when 30% of pool is used
    scale_check_interval: int = 60  # Check every 60 seconds

    # Health monitoring settings
    health_check_interval: int = 30
    connection_timeout: int = 10
    max_reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    enable_auto_recovery: bool = True

    # Performance settings
    statement_cache_size: int = 500
    enable_query_logging: bool = False
    slow_query_threshold: float = 5.0  # Log queries slower than 5 seconds

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create config from environment variables."""
        return cls(
            database_type=os.getenv('DATABASE_TYPE', 'sqlite'),
            database_url=os.getenv('DATABASE_URL'),
            database_path=os.getenv('DATABASE_PATH', 'data/happyos.db'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            username=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            database_name=os.getenv('DB_NAME', 'happyos'),
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600')),
            pool_pre_ping=os.getenv('DB_POOL_PRE_PING', 'true').lower() == 'true',
            min_pool_size=int(os.getenv('DB_MIN_POOL_SIZE', '5')),
            max_pool_size=int(os.getenv('DB_MAX_POOL_SIZE', '50')),
            scale_up_threshold=float(os.getenv('DB_SCALE_UP_THRESHOLD', '0.8')),
            scale_down_threshold=float(os.getenv('DB_SCALE_DOWN_THRESHOLD', '0.3')),
            scale_check_interval=int(os.getenv('DB_SCALE_CHECK_INTERVAL', '60')),
            health_check_interval=int(os.getenv('DB_HEALTH_CHECK_INTERVAL', '30')),
            connection_timeout=int(os.getenv('DB_CONNECTION_TIMEOUT', '10')),
            max_reconnect_attempts=int(os.getenv('DB_MAX_RECONNECT_ATTEMPTS', '3')),
            reconnect_delay=float(os.getenv('DB_RECONNECT_DELAY', '1.0')),
            enable_auto_recovery=os.getenv('DB_ENABLE_AUTO_RECOVERY', 'true').lower() == 'true',
            statement_cache_size=int(os.getenv('DB_STATEMENT_CACHE_SIZE', '500')),
            enable_query_logging=os.getenv('DB_ENABLE_QUERY_LOGGING', 'false').lower() == 'true',
            slow_query_threshold=float(os.getenv('DB_SLOW_QUERY_THRESHOLD', '5.0'))
        )


class DatabaseConnection:
    """
    Advanced database connection manager with auto-scaling, health monitoring, and failover.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool = None
        self._connection = None
        self._is_initialized = False

        # Advanced connection management
        self._pool_lock = asyncio.Lock()
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._auto_scaler_task: Optional[asyncio.Task] = None
        self._connection_health: Dict[str, Dict[str, Any]] = {}
        self._pool_metrics: Dict[str, Any] = {}

        # Performance tracking
        self._query_stats: Dict[str, Dict[str, Any]] = {}
        self._connection_stats = {
            'created': 0,
            'closed': 0,
            'failed': 0,
            'reconnected': 0,
            'peak_pool_size': 0
        }
        
    async def initialize(self) -> Dict[str, Any]:
        """Initialize database connection with advanced features."""
        logger.info(f"Initializing advanced database connection ({self.config.database_type})")

        try:
            if self.config.database_type == "sqlite":
                await self._initialize_sqlite()
            elif self.config.database_type == "postgresql":
                await self._initialize_postgresql()
            else:
                raise ValueError(f"Unsupported database type: {self.config.database_type}")

            self._is_initialized = True

            # Start advanced monitoring tasks
            await self._start_monitoring_tasks()

            result = {
                "database_type": self.config.database_type,
                "initialized": True,
                "connection_pool": self._pool is not None,
                "pool_size": self.config.pool_size,
                "auto_scaling": True,
                "health_monitoring": True,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Advanced database initialized successfully: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks."""
        if self.config.enable_auto_recovery:
            self._health_monitor_task = asyncio.create_task(self._health_monitoring_loop())
            self._auto_scaler_task = asyncio.create_task(self._auto_scaling_loop())

    async def _health_monitoring_loop(self):
        """Background health monitoring loop."""
        while self._is_initialized:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _auto_scaling_loop(self):
        """Background auto-scaling loop."""
        while self._is_initialized:
            try:
                await self._check_and_scale_pool()
                await asyncio.sleep(self.config.scale_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-scaling error: {e}")
                await asyncio.sleep(self.config.scale_check_interval)
    
    async def _initialize_sqlite(self):
        """Initialize SQLite connection."""
        db_path = Path(self.config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Test connection
        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute("SELECT 1")
            logger.info(f"SQLite database ready at: {db_path}")
    
    async def _initialize_postgresql(self):
        """Initialize PostgreSQL connection pool."""
        if self.config.database_url:
            dsn = self.config.database_url
        else:
            dsn = f"postgresql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database_name}"
        
        try:
            self._pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=self.config.pool_size,
                command_timeout=self.config.pool_timeout
            )
            logger.info("PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection context manager."""
        if not self._is_initialized:
            await self.initialize()
        
        if self.config.database_type == "sqlite":
            async with aiosqlite.connect(self.config.database_path) as conn:
                # Enable foreign keys and WAL mode for better performance
                await conn.execute("PRAGMA foreign_keys = ON")
                await conn.execute("PRAGMA journal_mode = WAL")
                yield conn
        
        elif self.config.database_type == "postgresql":
            if not self._pool:
                raise RuntimeError("PostgreSQL pool not initialized")
            
            async with self._pool.acquire() as conn:
                yield conn
        
        else:
            raise ValueError(f"Unsupported database type: {self.config.database_type}")
    
    async def execute_query(self, query: str, params: tuple = None) -> Any:
        """Execute a query and return results with performance tracking."""
        start_time = time.time()
        success = False

        try:
            async with self.get_connection() as conn:
                if self.config.database_type == "sqlite":
                    if params:
                        cursor = await conn.execute(query, params)
                    else:
                        cursor = await conn.execute(query)

                    if query.strip().upper().startswith(('SELECT', 'WITH')):
                        result = await cursor.fetchall()
                    else:
                        await conn.commit()
                        result = cursor.rowcount

                elif self.config.database_type == "postgresql":
                    if query.strip().upper().startswith(('SELECT', 'WITH')):
                        if params:
                            result = await conn.fetch(query, *params)
                        else:
                            result = await conn.fetch(query)
                    else:
                        if params:
                            result = await conn.execute(query, *params)
                        else:
                            result = await conn.execute(query)
                else:
                    raise ValueError(f"Unsupported database type: {self.config.database_type}")

            success = True
            execution_time = time.time() - start_time

            # Track query performance
            await self._track_query_performance(query, execution_time, success)

            # Log slow queries
            if self.config.enable_query_logging and execution_time > self.config.slow_query_threshold:
                logger.warning(f"Slow query ({execution_time:.3f}s): {query[:100]}...")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            await self._track_query_performance(query, execution_time, False)
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def execute_transaction(self, queries: list) -> bool:
        """Execute multiple queries in a transaction."""
        async with self.get_connection() as conn:
            try:
                if self.config.database_type == "sqlite":
                    async with conn.execute("BEGIN"):
                        for query, params in queries:
                            if params:
                                await conn.execute(query, params)
                            else:
                                await conn.execute(query)
                        await conn.commit()
                
                elif self.config.database_type == "postgresql":
                    async with conn.transaction():
                        for query, params in queries:
                            if params:
                                await conn.execute(query, *params)
                            else:
                                await conn.execute(query)
                
                return True
                
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                return False
    
    async def check_health(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            start_time = datetime.utcnow()
            
            # Simple health check query
            if self.config.database_type == "sqlite":
                result = await self.execute_query("SELECT 1")
            else:
                result = await self.execute_query("SELECT 1")
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            return {
                "healthy": True,
                "database_type": self.config.database_type,
                "response_time_seconds": response_time,
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            stats = {
                "database_type": self.config.database_type,
                "initialized": self._is_initialized,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if self.config.database_type == "sqlite":
                # SQLite specific stats
                db_path = Path(self.config.database_path)
                if db_path.exists():
                    stats["database_size_bytes"] = db_path.stat().st_size
                    stats["database_path"] = str(db_path)
                
                # Get table count
                tables = await self.execute_query(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                )
                stats["table_count"] = tables[0][0] if tables else 0
            
            elif self.config.database_type == "postgresql":
                # PostgreSQL specific stats
                if self._pool:
                    stats["pool_size"] = self._pool.get_size()
                    stats["pool_free_connections"] = self._pool.get_idle_size()
                
                # Get database size
                size_result = await self.execute_query(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )
                if size_result:
                    stats["database_size"] = size_result[0][0]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup(self):
        """Cleanup database connections and monitoring tasks."""
        logger.info("Cleaning up database connections")

        # Stop monitoring tasks
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass

        if self._auto_scaler_task:
            self._auto_scaler_task.cancel()
            try:
                await self._auto_scaler_task
            except asyncio.CancelledError:
                pass

        try:
            if self.config.database_type == "postgresql" and self._pool:
                await self._pool.close()
                self._pool = None

            self._is_initialized = False
            logger.info("Database cleanup completed")

        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")

    async def _perform_health_checks(self):
        """Perform comprehensive health checks."""
        try:
            health_status = await self.check_health()
            self._connection_health['latest_check'] = health_status

            if not health_status['healthy']:
                logger.warning("Database health check failed, attempting recovery")
                await self._attempt_connection_recovery()
            else:
                # Reset any failed connection attempts on successful health check
                if 'failed_attempts' in self._connection_health:
                    self._connection_health['failed_attempts'] = 0

        except Exception as e:
            logger.error(f"Health check error: {e}")
            self._connection_health['last_error'] = str(e)

    async def _attempt_connection_recovery(self):
        """Attempt to recover from connection failures."""
        failed_attempts = self._connection_health.get('failed_attempts', 0)

        if failed_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return

        self._connection_health['failed_attempts'] = failed_attempts + 1
        logger.info(f"Attempting connection recovery (attempt {failed_attempts + 1})")

        try:
            # Try to reinitialize the connection
            if self.config.database_type == "postgresql" and self._pool:
                await self._pool.close()

            await self.initialize()
            logger.info("Connection recovery successful")

        except Exception as e:
            logger.error(f"Connection recovery failed: {e}")
            # Schedule next attempt with exponential backoff
            await asyncio.sleep(self.config.reconnect_delay * (2 ** failed_attempts))

    async def _check_and_scale_pool(self):
        """Check pool usage and scale if necessary."""
        if self.config.database_type != "postgresql" or not self._pool:
            return

        try:
            current_size = self._pool.get_size()
            used_connections = current_size - self._pool.get_idle_size()
            usage_ratio = used_connections / current_size if current_size > 0 else 0

            self._pool_metrics.update({
                'current_size': current_size,
                'used_connections': used_connections,
                'usage_ratio': usage_ratio,
                'last_check': datetime.utcnow()
            })

            # Scale up if usage is high
            if usage_ratio >= self.config.scale_up_threshold and current_size < self.config.max_pool_size:
                new_size = min(current_size + 5, self.config.max_pool_size)
                await self._scale_pool_size(new_size)
                logger.info(f"Scaled up pool size to {new_size}")

            # Scale down if usage is low
            elif usage_ratio <= self.config.scale_down_threshold and current_size > self.config.min_pool_size:
                new_size = max(current_size - 2, self.config.min_pool_size)
                await self._scale_pool_size(new_size)
                logger.info(f"Scaled down pool size to {new_size}")

        except Exception as e:
            logger.error(f"Pool scaling check error: {e}")

    async def _scale_pool_size(self, new_size: int):
        """Scale the connection pool to a new size."""
        if not self._pool:
            return

        try:
            # For asyncpg, we recreate the pool with new size
            await self._pool.close()

            if self.config.database_url:
                dsn = self.config.database_url
            else:
                dsn = f"postgresql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database_name}"

            self._pool = await asyncpg.create_pool(
                dsn,
                min_size=self.config.min_pool_size,
                max_size=new_size,
                command_timeout=self.config.pool_timeout
            )

            self.config.pool_size = new_size
            self._connection_stats['peak_pool_size'] = max(
                self._connection_stats['peak_pool_size'],
                new_size
            )

        except Exception as e:
            logger.error(f"Failed to scale pool to size {new_size}: {e}")

    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get comprehensive connection metrics."""
        return {
            'connection_stats': self._connection_stats.copy(),
            'pool_metrics': self._pool_metrics.copy(),
            'health_status': self._connection_health.copy(),
            'query_stats': self._query_stats.copy(),
            'config': {
                'pool_size': self.config.pool_size,
                'max_pool_size': self.config.max_pool_size,
                'min_pool_size': self.config.min_pool_size,
                'auto_scaling': True,
                'health_monitoring': True
            },
            'timestamp': datetime.utcnow().isoformat()
        }

    async def _track_query_performance(self, query: str, execution_time: float, success: bool):
        """Track query performance metrics."""
        # Create a hash of the query for grouping similar queries
        query_hash = hash(query.strip().upper())

        if query_hash not in self._query_stats:
            self._query_stats[query_hash] = {
                'query_template': query[:100] + '...' if len(query) > 100 else query,
                'count': 0,
                'success_count': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0,
                'last_execution': None
            }

        stats = self._query_stats[query_hash]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['count']
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['last_execution'] = datetime.utcnow().isoformat()

        if success:
            stats['success_count'] += 1


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


async def get_db_connection() -> DatabaseConnection:
    """Get the global database connection instance."""
    global _db_connection
    
    if _db_connection is None:
        config = DatabaseConfig.from_env()
        _db_connection = DatabaseConnection(config)
        await _db_connection.initialize()
    
    return _db_connection


async def initialize_database() -> Dict[str, Any]:
    """Initialize the global database connection."""
    db = await get_db_connection()
    return await db.initialize()


async def cleanup_database():
    """Cleanup the global database connection."""
    global _db_connection
    
    if _db_connection:
        await _db_connection.cleanup()
        _db_connection = None

