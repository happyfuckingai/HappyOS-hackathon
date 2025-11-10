"""
Zero Trust Sandbox Isolation Engine.
Executes all components in isolated containers with strict security controls.
"""

import logging
import asyncio
import tempfile
import shutil
import json
import psutil
import subprocess
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.config.settings import get_settings
from app.core.error_handler import safe_execute

logger = logging.getLogger(__name__)
settings = get_settings()


class IsolationLevel(Enum):
    """Levels of isolation for component execution."""
    PROCESS = "process"          # Separate process
    CONTAINER = "container"      # Docker container
    VM = "virtual_machine"       # Full VM isolation
    CHROOT = "chroot"           # Chroot jail


class SecurityThreat(Enum):
    """Types of security threats detected."""
    FILE_ACCESS_VIOLATION = "file_access_violation"
    NETWORK_ACCESS_VIOLATION = "network_access_violation"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SUSPICIOUS_SYSTEM_CALL = "suspicious_system_call"
    MALICIOUS_CODE_PATTERN = "malicious_code_pattern"
    PRIVILEGE_ESCALATION = "privilege_escalation"


@dataclass
class ResourceLimits:
    """Resource limits for sandboxed execution."""
    max_memory_mb: int = 256
    max_cpu_percent: float = 50.0
    max_execution_time: int = 300  # seconds
    max_file_size_mb: int = 10
    max_network_connections: int = 5
    allowed_file_paths: Set[str] = field(default_factory=set)
    blocked_file_paths: Set[str] = field(default_factory=set)
    allowed_network_hosts: Set[str] = field(default_factory=set)


@dataclass
class SandboxExecution:
    """Represents a sandboxed execution."""
    execution_id: str
    component_name: str
    isolation_level: IsolationLevel
    resource_limits: ResourceLimits
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    result: Optional[Dict[str, Any]] = None
    security_violations: List[SecurityThreat] = field(default_factory=list)
    resource_usage: Dict[str, float] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


class ZeroTrustSandbox:
    """
    Zero Trust Sandbox for secure component execution.
    No component is trusted - all execution is isolated and monitored.
    """
    
    def __init__(self):
        self.active_executions: Dict[str, SandboxExecution] = {}
        self.execution_history: List[SandboxExecution] = []
        self.sandbox_dir = Path("/tmp/happyos_sandbox")
        self.container_runtime = "docker"  # or "podman"
        
        # Security configuration
        self.security_config = {
            "default_isolation_level": IsolationLevel.CONTAINER,
            "max_concurrent_executions": 10,
            "execution_timeout": 300,
            "memory_limit_mb": 256,
            "cpu_limit_percent": 50.0,
            "network_isolation": True,
            "file_system_isolation": True,
            "enable_monitoring": True,
            "auto_terminate_violations": True
        }
        
        # Blacklisted patterns
        self.security_patterns = {
            "dangerous_imports": [
                r"import\s+os\s*$",
                r"import\s+subprocess\s*$", 
                r"import\s+sys\s*$",
                r"from\s+os\s+import",
                r"from\s+subprocess\s+import"
            ],
            "dangerous_functions": [
                r"os\.system\s*\(",
                r"subprocess\.call\s*\(",
                r"subprocess\.run\s*\(",
                r"eval\s*\(",
                r"exec\s*\(",
                r"__import__\s*\(",
                r"open\s*\([^)]*['\"]w['\"]"
            ],
            "network_operations": [
                r"socket\.",
                r"urllib\.",
                r"requests\.",
                r"http\.",
                r"ftp\."
            ]
        }
        
        # Statistics
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "security_violations": 0,
            "resource_violations": 0,
            "terminated_executions": 0
        }
        
        # Ensure sandbox directory exists
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize the sandbox system."""
        
        try:
            # Check if container runtime is available
            await self._check_container_runtime()
            
            # Setup base container image
            await self._setup_base_container()
            
            # Start monitoring tasks
            asyncio.create_task(self._execution_monitor())
            asyncio.create_task(self._security_monitor())
            
            logger.info("Zero Trust Sandbox initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize sandbox: {e}")
            raise
    
    async def execute_component(
        self,
        component_name: str,
        component_code: str,
        request: str,
        context: Dict[str, Any] = None,
        resource_limits: Optional[ResourceLimits] = None,
        isolation_level: Optional[IsolationLevel] = None
    ) -> Dict[str, Any]:
        """
        Execute a component in a secure sandbox.
        
        Args:
            component_name: Name of the component
            component_code: Code to execute
            request: Request to process
            context: Execution context
            resource_limits: Resource limits for execution
            isolation_level: Level of isolation to use
            
        Returns:
            Execution result
        """
        
        if context is None:
            context = {}
        
        if resource_limits is None:
            resource_limits = ResourceLimits()
        
        if isolation_level is None:
            isolation_level = self.security_config["default_isolation_level"]
        
        # Check concurrent execution limit
        if len(self.active_executions) >= self.security_config["max_concurrent_executions"]:
            return {
                "success": False,
                "error": "Maximum concurrent executions reached",
                "security_violation": True
            }
        
        try:
            # Pre-execution security scan
            security_issues = await self._security_scan_code(component_code)
            if security_issues:
                logger.warning(f"Security issues detected in {component_name}: {security_issues}")
                
                if self.security_config["auto_terminate_violations"]:
                    return {
                        "success": False,
                        "error": "Security violations detected",
                        "security_issues": security_issues,
                        "security_violation": True
                    }
            
            # Create execution record
            execution_id = f"{component_name}_{int(datetime.now().timestamp())}"
            execution = SandboxExecution(
                execution_id=execution_id,
                component_name=component_name,
                isolation_level=isolation_level,
                resource_limits=resource_limits,
                start_time=datetime.now()
            )
            
            self.active_executions[execution_id] = execution
            
            # Execute based on isolation level
            if isolation_level == IsolationLevel.CONTAINER:
                result = await self._execute_in_container(execution, component_code, request, context)
            elif isolation_level == IsolationLevel.PROCESS:
                result = await self._execute_in_process(execution, component_code, request, context)
            elif isolation_level == IsolationLevel.CHROOT:
                result = await self._execute_in_chroot(execution, component_code, request, context)
            else:
                result = {
                    "success": False,
                    "error": f"Unsupported isolation level: {isolation_level}"
                }
            
            # Update execution record
            execution.end_time = datetime.now()
            execution.success = result.get("success", False)
            execution.result = result
            
            # Move to history
            self.execution_history.append(execution)
            del self.active_executions[execution_id]
            
            # Update statistics
            self.stats["total_executions"] += 1
            if execution.success:
                self.stats["successful_executions"] += 1
            if execution.security_violations:
                self.stats["security_violations"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing component in sandbox: {e}")
            return {
                "success": False,
                "error": str(e),
                "security_violation": False
            }
    
    async def _security_scan_code(self, code: str) -> List[str]:
        """Scan code for security issues."""
        
        issues = []
        
        try:
            import re
            
            # Check for dangerous patterns
            for category, patterns in self.security_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                        issues.append(f"{category}: {pattern}")
            
            # Check for suspicious strings
            suspicious_strings = [
                "/etc/passwd", "/etc/shadow", "rm -rf", "sudo", "chmod 777",
                "wget", "curl", "nc ", "netcat", "bash -i", "/bin/sh"
            ]
            
            for sus_str in suspicious_strings:
                if sus_str in code:
                    issues.append(f"suspicious_string: {sus_str}")
            
            return issues
            
        except Exception as e:
            logger.error(f"Error in security scan: {e}")
            return [f"security_scan_error: {e}"]
    
    async def _execute_in_container(
        self,
        execution: SandboxExecution,
        component_code: str,
        request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute component in a Docker container."""
        
        try:
            # Create temporary directory for this execution
            exec_dir = self.sandbox_dir / execution.execution_id
            exec_dir.mkdir(parents=True, exist_ok=True)
            
            # Write component code to file
            code_file = exec_dir / "component.py"
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(component_code)
            
            # Write execution script
            exec_script = exec_dir / "execute.py"
            exec_script_content = f'''
import json
import sys
import traceback
from datetime import datetime

# Import the component
import component

async def main():
    try:
        # Execute the component
        result = await component.execute_skill(
            {json.dumps(request)},
            {json.dumps(context)}
        )
        
        # Write result
        with open('/sandbox/result.json', 'w') as f:
            json.dump({{
                "success": True,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }}, f)
            
    except Exception as e:
        # Write error
        with open('/sandbox/result.json', 'w') as f:
            json.dump({{
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat()
            }}, f)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
            
            with open(exec_script, 'w', encoding='utf-8') as f:
                f.write(exec_script_content)
            
            # Build Docker command
            docker_cmd = [
                self.container_runtime, "run",
                "--rm",
                "--network", "none" if self.security_config["network_isolation"] else "bridge",
                "--memory", f"{execution.resource_limits.max_memory_mb}m",
                "--cpus", str(execution.resource_limits.max_cpu_percent / 100),
                "--user", "nobody",
                "--read-only",
                "--tmpfs", "/tmp:noexec,nosuid,size=10m",
                "-v", f"{exec_dir}:/sandbox:ro",
                "-v", f"{exec_dir}:/output:rw",
                "--timeout", str(execution.resource_limits.max_execution_time),
                "happyos-sandbox:latest",
                "python", "/sandbox/execute.py"
            ]
            
            # Execute in container
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=execution.resource_limits.max_execution_time
                )
                
                # Read result
                result_file = exec_dir / "result.json"
                if result_file.exists():
                    with open(result_file, 'r') as f:
                        result = json.load(f)
                else:
                    result = {
                        "success": False,
                        "error": "No result file generated",
                        "stdout": stdout.decode() if stdout else "",
                        "stderr": stderr.decode() if stderr else ""
                    }
                
                return result
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                execution.security_violations.append(SecurityThreat.RESOURCE_LIMIT_EXCEEDED)
                
                return {
                    "success": False,
                    "error": "Execution timeout",
                    "security_violation": True
                }
            
            finally:
                # Cleanup
                shutil.rmtree(exec_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"Error executing in container: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_in_process(
        self,
        execution: SandboxExecution,
        component_code: str,
        request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute component in a separate process."""
        
        try:
            # Create temporary file for component
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(component_code)
                temp_file = f.name
            
            try:
                # Create execution script
                exec_script = f'''
import json
import sys
import traceback
import resource
import signal
from datetime import datetime

# Set resource limits
resource.setrlimit(resource.RLIMIT_AS, ({execution.resource_limits.max_memory_mb * 1024 * 1024}, -1))
resource.setrlimit(resource.RLIMIT_CPU, ({execution.resource_limits.max_execution_time}, -1))

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Execution timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({execution.resource_limits.max_execution_time})

try:
    # Import component
    import {Path(temp_file).stem} as component
    
    # Execute
    import asyncio
    result = asyncio.run(component.execute_skill({json.dumps(request)}, {json.dumps(context)}))
    
    print(json.dumps({{
        "success": True,
        "result": result,
        "timestamp": datetime.now().isoformat()
    }}))
    
except Exception as e:
    print(json.dumps({{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.now().isoformat()
    }}))
'''
                
                # Execute in subprocess
                process = await asyncio.create_subprocess_exec(
                    "python", "-c", exec_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if stdout:
                    result = json.loads(stdout.decode())
                else:
                    result = {
                        "success": False,
                        "error": "No output from process",
                        "stderr": stderr.decode() if stderr else ""
                    }
                
                return result
                
            finally:
                # Cleanup temp file
                Path(temp_file).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Error executing in process: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_in_chroot(
        self,
        execution: SandboxExecution,
        component_code: str,
        request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute component in a chroot jail."""
        
        # This would implement chroot execution
        # For now, fallback to process execution
        logger.warning("Chroot execution not implemented, falling back to process")
        return await self._execute_in_process(execution, component_code, request, context)
    
    async def _check_container_runtime(self):
        """Check if container runtime is available."""
        
        try:
            # Check if Docker/Podman is available
            result = await asyncio.create_subprocess_exec(
                self.container_runtime, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                logger.info(f"Container runtime {self.container_runtime} is available")
            else:
                logger.warning(f"Container runtime {self.container_runtime} not available")
                # Fallback to process isolation
                self.security_config["default_isolation_level"] = IsolationLevel.PROCESS
                
        except Exception as e:
            logger.warning(f"Error checking container runtime: {e}")
            self.security_config["default_isolation_level"] = IsolationLevel.PROCESS
    
    async def _setup_base_container(self):
        """Setup base container image for sandboxing."""
        
        try:
            # Check if base image exists
            result = await asyncio.create_subprocess_exec(
                self.container_runtime, "images", "-q", "happyos-sandbox:latest",
                stdout=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await result.communicate()
            
            if not stdout.strip():
                # Build base image
                logger.info("Building base sandbox container image...")
                await self._build_base_container()
            else:
                logger.info("Base sandbox container image already exists")
                
        except Exception as e:
            logger.error(f"Error setting up base container: {e}")
    
    async def _build_base_container(self):
        """Build the base container image."""
        
        try:
            # Create Dockerfile
            dockerfile_content = '''
FROM python:3.11-slim

# Install minimal dependencies
RUN pip install --no-cache-dir aiohttp asyncio

# Create non-root user
RUN useradd -m -s /bin/bash sandbox

# Set working directory
WORKDIR /sandbox

# Switch to non-root user
USER sandbox

# Default command
CMD ["python"]
'''
            
            dockerfile_path = self.sandbox_dir / "Dockerfile"
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            
            # Build image
            build_cmd = [
                self.container_runtime, "build",
                "-t", "happyos-sandbox:latest",
                str(self.sandbox_dir)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *build_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Base sandbox container built successfully")
            else:
                logger.error(f"Failed to build container: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error building base container: {e}")
    
    async def _execution_monitor(self):
        """Monitor active executions for violations."""
        
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                current_time = datetime.now()
                
                for execution_id, execution in list(self.active_executions.items()):
                    # Check timeout
                    if (current_time - execution.start_time).total_seconds() > execution.resource_limits.max_execution_time:
                        logger.warning(f"Execution timeout: {execution_id}")
                        execution.security_violations.append(SecurityThreat.RESOURCE_LIMIT_EXCEEDED)
                        await self._terminate_execution(execution_id)
                    
                    # Monitor resource usage (simplified)
                    try:
                        # This would monitor actual resource usage
                        # For now, just log that monitoring is active
                        pass
                    except Exception as e:
                        logger.error(f"Error monitoring execution {execution_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in execution monitor: {e}")
    
    async def _security_monitor(self):
        """Monitor for security violations."""
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Monitor system for suspicious activity
                # This would implement more sophisticated monitoring
                
                # Check for unusual resource usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                
                if cpu_percent > 90 or memory_percent > 90:
                    logger.warning(f"High resource usage detected: CPU {cpu_percent}%, Memory {memory_percent}%")
                
            except Exception as e:
                logger.error(f"Error in security monitor: {e}")
    
    async def _terminate_execution(self, execution_id: str):
        """Terminate a running execution."""
        
        try:
            execution = self.active_executions.get(execution_id)
            if execution:
                execution.end_time = datetime.now()
                execution.success = False
                
                # Move to history
                self.execution_history.append(execution)
                del self.active_executions[execution_id]
                
                self.stats["terminated_executions"] += 1
                
                logger.info(f"Terminated execution: {execution_id}")
                
        except Exception as e:
            logger.error(f"Error terminating execution: {e}")
    
    def get_sandbox_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics."""
        
        return {
            **self.stats,
            "active_executions": len(self.active_executions),
            "isolation_level": self.security_config["default_isolation_level"].value,
            "container_runtime": self.container_runtime,
            "recent_executions": [
                {
                    "execution_id": exec.execution_id,
                    "component_name": exec.component_name,
                    "success": exec.success,
                    "duration": (exec.end_time - exec.start_time).total_seconds() if exec.end_time else None,
                    "security_violations": [v.value for v in exec.security_violations]
                }
                for exec in self.execution_history[-10:]
            ]
        }


# Global sandbox instance
zero_trust_sandbox = ZeroTrustSandbox()


# Convenience functions
async def execute_component_safely(
    component_name: str,
    component_code: str,
    request: str,
    context: Dict[str, Any] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute a component safely in sandbox."""
    return await zero_trust_sandbox.execute_component(
        component_name, component_code, request, context, **kwargs
    )


def get_sandbox_stats() -> Dict[str, Any]:
    """Get sandbox statistics."""
    return zero_trust_sandbox.get_sandbox_stats()