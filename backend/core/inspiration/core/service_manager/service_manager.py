"""
Service Manager for HappyOS
Async service management with health checks, monitoring, and graceful shutdown.
"""
import asyncio
import signal
import time
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import psutil
import aiohttp
from pathlib import Path

from app.core.config.settings import get_config, ServiceConfig
from app.core.logging.logger import get_logger, log_service_event


class ServiceStatus(Enum):
    """Service status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServiceInstance:
    """Represents a running service instance."""
    config: ServiceConfig
    process: Optional[psutil.Process] = None
    status: ServiceStatus = ServiceStatus.STOPPED
    start_time: Optional[float] = None
    last_health_check: Optional[float] = None
    health_check_failures: int = 0
    restart_count: int = 0
    logger: Any = field(init=False)

    def __post_init__(self):
        self.logger = get_logger(f"service.{self.config.name}")


class ServiceManager:
    """Manages HappyOS services with async support."""

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger("service_manager")
        self.services: Dict[str, ServiceInstance] = {}
        self._shutdown_requested = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._startup_complete = False

        # Setup signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self._shutdown_requested = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Handle SIGUSR1 for service status
        def status_handler(signum, frame):
            self._log_service_status()

        signal.signal(signal.SIGUSR1, status_handler)

    async def initialize(self) -> None:
        """Initialize the service manager."""
        self.logger.info("Initializing HappyOS Service Manager")

        # Create service instances
        for service_config in self.config.get_service_configs():
            self.services[service_config.name] = ServiceInstance(service_config)

        # Create necessary directories
        self._create_directories()

        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info(f"Service Manager initialized with {len(self.services)} services")

    async def start_services(self) -> bool:
        """Start all configured services."""
        self.logger.info("Starting HappyOS services")

        success_count = 0
        total_services = len(self.services)

        for service_name, service_instance in self.services.items():
            if await self._start_service(service_instance):
                success_count += 1
                log_service_event(service_name, "start", "success")
            else:
                log_service_event(service_name, "start", "failed")
                # Continue with other services even if one fails
                continue

        self._startup_complete = success_count == total_services

        if self._startup_complete:
            self.logger.info(f"All {total_services} services started successfully")
        else:
            self.logger.warning(f"Started {success_count}/{total_services} services successfully")

        return self._startup_complete

    async def _start_service(self, service_instance: ServiceInstance) -> bool:
        """Start a single service."""
        service_instance.status = ServiceStatus.STARTING
        service_instance.logger.info(f"Starting service {service_instance.config.name}")

        try:
            # Create environment for the subprocess
            env = self._create_service_environment(service_instance.config)

            # Get the appropriate Python executable for this service
            venv_path = self._get_virtual_environment_path()
            python_executable = self._get_python_executable(venv_path)

            # Prepare the command, using virtual environment Python when appropriate
            command = service_instance.config.command.copy()

            # If the command starts with python3 or python, replace it with the virtual environment Python
            if command and command[0] in ['python3', 'python']:
                command[0] = python_executable

            # Define proper preexec_fn for POSIX systems
            def setup_child_process():
                """Setup child process environment."""
                import os
                import signal
                # Start new process group to prevent signal propagation
                os.setpgrp()
                # Reset signal handlers to defaults
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                signal.signal(signal.SIGHUP, signal.SIG_DFL)

            # Start the process
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env,
                cwd=self.config.base_path,
                preexec_fn=None if psutil.WINDOWS else setup_child_process,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wrap in psutil Process for better management
            psutil_process = psutil.Process(process.pid)
            service_instance.process = psutil_process
            service_instance.start_time = time.time()
            service_instance.status = ServiceStatus.RUNNING

            # Start monitoring the process output
            asyncio.create_task(self._monitor_process_output(service_instance, process))

            service_instance.logger.info(f"Service {service_instance.config.name} started with PID {process.pid}")
            return True

        except Exception as e:
            service_instance.status = ServiceStatus.FAILED
            service_instance.logger.error(f"Failed to start service {service_instance.config.name}: {e}")
            return False

    def _create_service_environment(self, service_config: ServiceConfig) -> Dict[str, str]:
        """Create environment variables for service."""
        env = dict(self.config.__dict__.get('__environ__', {}))

        # Add service-specific environment variables
        env.update(service_config.environment)

        # Detect and configure virtual environment
        venv_path = self._get_virtual_environment_path()
        python_executable = self._get_python_executable(venv_path)

        # Set PYTHONPATH to include both the happyos directory, base path, and virtual environment site-packages
        # This ensures subprocesses can import both app.* and any local modules
        happyos_root = Path(self.config.base_path).parent
        existing_pythonpath = env.get('PYTHONPATH', '')

        # Build PYTHONPATH with proper priority: venv site-packages first, then project paths
        pythonpath_parts = []

        if venv_path:
            # Add virtual environment site-packages to PYTHONPATH
            venv_site_packages = venv_path / "lib" / "python3.10" / "site-packages"
            if venv_site_packages.exists():
                pythonpath_parts.append(str(venv_site_packages))

            # Also add the bin directory to PATH so subprocesses can find executables
            venv_bin = venv_path / "bin"
            if venv_bin.exists():
                existing_path = env.get('PATH', '')
                env['PATH'] = f"{venv_bin}:{existing_path}" if existing_path else str(venv_bin)

        # Add project directories
        pythonpath_parts.extend([self.config.base_path, str(happyos_root)])

        # Add existing PYTHONPATH if present
        if existing_pythonpath:
            pythonpath_parts.append(existing_pythonpath)

        pythonpath = ':'.join(pythonpath_parts)

        env.update({
            'HAPPYOS_BASE_PATH': self.config.base_path,
            'HAPPYOS_LOGS_DIR': self.config.logs_directory,
            'HAPPYOS_DATA_DIR': self.config.data_directory,
            'PYTHONPATH': pythonpath,
            'VIRTUAL_ENV': str(venv_path) if venv_path else '',
            'PYTHONEXECUTABLE': python_executable
        })

        return env

    def _get_virtual_environment_path(self) -> Optional[Path]:
        """Detect the virtual environment path."""
        # Check for VIRTUAL_ENV environment variable first
        venv_env = os.environ.get('VIRTUAL_ENV')
        if venv_env:
            venv_path = Path(venv_env)
            if venv_path.exists():
                return venv_path

        # Check for common virtual environment locations relative to project root
        project_root = Path(self.config.base_path).parent

        # Common virtual environment directory names
        venv_names = ['.venv', 'venv', 'virtualenv', 'env']

        for venv_name in venv_names:
            venv_path = project_root / venv_name
            if venv_path.exists() and venv_path.is_dir():
                # Verify it's actually a virtual environment by checking for activation script
                if (venv_path / 'bin' / 'activate').exists() or (venv_path / 'Scripts' / 'activate.bat').exists():
                    return venv_path

        return None

    def _get_python_executable(self, venv_path: Optional[Path] = None) -> str:
        """Get the appropriate Python executable for subprocesses."""
        if venv_path:
            # Use virtual environment Python
            venv_python = venv_path / "bin" / "python3"
            if venv_python.exists():
                return str(venv_python)
            # Fallback to python
            venv_python_fallback = venv_path / "bin" / "python"
            if venv_python_fallback.exists():
                return str(venv_python_fallback)

        # Fallback to system Python
        return "python3"

    async def _monitor_process_output(self, service_instance: ServiceInstance, process: asyncio.subprocess.Process) -> None:
        """Monitor process stdout and stderr."""
        try:
            async for line in process.stdout:
                service_instance.logger.debug(f"[STDOUT] {line.decode().strip()}")

            async for line in process.stderr:
                service_instance.logger.warning(f"[STDERR] {line.decode().strip()}")

        except Exception as e:
            service_instance.logger.error(f"Error monitoring process output: {e}")

    async def _health_check_loop(self) -> None:
        """Continuous health check loop."""
        while not self._shutdown_requested:
            await asyncio.sleep(self.config.system_check_interval)

            if self._shutdown_requested:
                break

            await self._perform_health_checks()

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all running services."""
        for service_name, service_instance in self.services.items():
            if service_instance.status == ServiceStatus.RUNNING and service_instance.config.health_check_url:
                await self._check_service_health(service_instance)

    async def _check_service_health(self, service_instance: ServiceInstance) -> None:
        """Check health of a single service."""
        try:
            timeout = aiohttp.ClientTimeout(total=service_instance.config.health_check_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(service_instance.config.health_check_url) as response:
                    if response.status == 200:
                        service_instance.last_health_check = time.time()
                        service_instance.health_check_failures = 0
                        if service_instance.status != ServiceStatus.RUNNING:
                            service_instance.status = ServiceStatus.RUNNING
                            service_instance.logger.info("Service health restored")
                    else:
                        await self._handle_health_check_failure(service_instance, f"HTTP {response.status}")

        except Exception as e:
            await self._handle_health_check_failure(service_instance, str(e))

    async def _handle_health_check_failure(self, service_instance: ServiceInstance, error: str) -> None:
        """Handle health check failure."""
        service_instance.health_check_failures += 1
        service_instance.logger.warning(f"Health check failed: {error} (failure #{service_instance.health_check_failures})")

        if service_instance.health_check_failures >= 3:
            service_instance.status = ServiceStatus.UNHEALTHY
            service_instance.logger.error("Service marked as unhealthy due to repeated health check failures")

            # Attempt restart if enabled
            if self.config.enable_auto_recovery:
                await self._restart_service(service_instance)

    async def _restart_service(self, service_instance: ServiceInstance) -> None:
        """Restart a failed service."""
        if service_instance.restart_count >= service_instance.config.max_retries:
            service_instance.logger.error("Max restart attempts reached, giving up")
            service_instance.status = ServiceStatus.FAILED
            return

        service_instance.restart_count += 1
        service_instance.logger.info(f"Attempting to restart service (attempt #{service_instance.restart_count})")

        # Stop the current process
        await self._stop_service_process(service_instance)

        # Wait before restarting
        await asyncio.sleep(service_instance.config.restart_delay)

        # Start again
        if await self._start_service(service_instance):
            service_instance.logger.info("Service restarted successfully")
            log_service_event(service_instance.config.name, "restart", "success")
        else:
            service_instance.logger.error("Failed to restart service")
            log_service_event(service_instance.config.name, "restart", "failed")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop."""
        while not self._shutdown_requested:
            await asyncio.sleep(10)  # Monitor every 10 seconds

            if self._shutdown_requested:
                break

            await self._perform_system_monitoring()

    async def _perform_system_monitoring(self) -> None:
        """Perform system monitoring and metrics collection."""
        if not self.config.monitoring.enabled:
            return

        try:
            # Monitor system resources
            system_metrics = self._collect_system_metrics()

            # Monitor service resources
            service_metrics = {}
            for service_name, service_instance in self.services.items():
                if service_instance.process and service_instance.process.is_running():
                    service_metrics[service_name] = self._collect_process_metrics(service_instance.process)

            # Log metrics
            self.logger.debug("System metrics collected", system_metrics=system_metrics, service_metrics=service_metrics)

        except Exception as e:
            self.logger.error(f"Error during system monitoring: {e}")

    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'timestamp': time.time()
        }

    def _collect_process_metrics(self, process: psutil.Process) -> Dict[str, Any]:
        """Collect metrics for a specific process."""
        try:
            return {
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'num_threads': process.num_threads(),
                'status': process.status(),
                'create_time': process.create_time()
            }
        except psutil.NoSuchProcess:
            return {'error': 'Process not found'}
        except Exception as e:
            return {'error': str(e)}

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        self.logger.info("Initiating graceful shutdown of all services")

        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()

        # Stop all services
        stop_tasks = []
        for service_instance in self.services.values():
            stop_tasks.append(self._stop_service(service_instance))

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Cleanup processes
        await self._cleanup_processes()

        self.logger.info("Service Manager shutdown complete")

    async def _stop_service(self, service_instance: ServiceInstance) -> None:
        """Stop a single service."""
        if service_instance.status in [ServiceStatus.STOPPING, ServiceStatus.STOPPED]:
            return

        service_instance.status = ServiceStatus.STOPPING
        service_instance.logger.info(f"Stopping service {service_instance.config.name}")

        try:
            if service_instance.process:
                await self._stop_service_process(service_instance)

            service_instance.status = ServiceStatus.STOPPED
            service_instance.logger.info(f"Service {service_instance.config.name} stopped successfully")
            log_service_event(service_instance.config.name, "stop", "success")

        except Exception as e:
            service_instance.logger.error(f"Error stopping service {service_instance.config.name}: {e}")
            log_service_event(service_instance.config.name, "stop", "failed")

    async def _stop_service_process(self, service_instance: ServiceInstance) -> None:
        """Stop a service process with graceful termination."""
        if not service_instance.process:
            return

        try:
            # First try graceful termination
            service_instance.process.terminate()

            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(service_instance.process.wait, timeout=10),
                    timeout=10
                )
            except asyncio.TimeoutError:
                # Force kill if graceful shutdown fails
                service_instance.logger.warning("Graceful shutdown timeout, force killing process")
                service_instance.process.kill()
                await asyncio.to_thread(service_instance.process.wait)

        except psutil.NoSuchProcess:
            pass  # Process already dead
        except Exception as e:
            service_instance.logger.error(f"Error stopping process: {e}")

    async def _cleanup_processes(self) -> None:
        """Cleanup any remaining processes."""
        try:
            if hasattr(self, '_main_process'):
                main_process = psutil.Process(self._main_process)
                for child in main_process.children(recursive=True):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass

                # Wait for termination
                gone, alive = psutil.wait_procs(main_process.children(recursive=True), timeout=5)

                # Kill any remaining processes
                for p in alive:
                    try:
                        p.kill()
                    except psutil.NoSuchProcess:
                        pass

        except Exception as e:
            self.logger.error(f"Error during process cleanup: {e}")

    def _create_directories(self) -> None:
        """Create necessary directories."""
        directories = [
            self.config.logs_directory,
            self.config.data_directory,
            Path(self.config.logs_directory) / "services"
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def _log_service_status(self) -> None:
        """Log current status of all services."""
        status_summary = {service_name: service_instance.status.value
                         for service_name, service_instance in self.services.items()}

        self.logger.info("Service status summary", **status_summary)

    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Get status of a specific service."""
        service_instance = self.services.get(service_name)
        return service_instance.status if service_instance else None

    def is_healthy(self) -> bool:
        """Check if the service manager is in a healthy state."""
        if not self._startup_complete:
            return False

        # Check if all critical services are running
        critical_services = [s for s in self.services.values()
                           if s.status not in [ServiceStatus.RUNNING, ServiceStatus.STARTING]]

        return len(critical_services) == 0

    async def wait_for_startup(self, timeout: float = 60.0) -> bool:
        """Wait for all services to start up."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._startup_complete and self.is_healthy():
                return True
            await asyncio.sleep(1)

        return False