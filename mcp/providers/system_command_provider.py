"""
System Command MCP Provider

Handles local terminal/CMD command execution with security controls.
Implements whitelist/blacklist for safe command execution.
"""

import os
import subprocess
import asyncio
import logging
import shlex
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class SystemCommandConfig(ProviderConfig):
    """Configuration for system command provider"""
    # Security settings
    enable_execution: bool = True
    require_confirmation: bool = True  # HITL by default
    allowed_commands: List[str] = [
        "echo", "ls", "dir", "pwd", "cd", "cat", "head", "tail", "grep",
        "find", "wc", "date", "whoami", "hostname", "ping", "curl", "wget",
        "python", "pip", "node", "npm", "git", "docker"
    ]
    blocked_commands: List[str] = [
        "rm -rf /", "rm -rf *", "del /s", "format", "mkfs",
        "dd if=", "shutdown", "reboot", "halt", "poweroff",
        ":(){:|:&};:", "fork bomb"  # Fork bomb pattern
    ]
    blocked_patterns: List[str] = [
        "rm -rf", "del /f /s", "format c:", ">(", "sudo rm",
        "chmod 777 /", "chown -R", "passwd", "mkpasswd"
    ]
    # Execution settings
    max_execution_time: int = 30  # seconds
    max_output_size: int = 100000  # characters
    working_directory: Optional[str] = None
    shell: str = "powershell" if os.name == "nt" else "bash"


class SystemCommandProvider(BaseProvider):
    """
    MCP Provider for executing local system commands.
    
    ⚠️ Security Warning:
    This provider allows execution of system commands.
    Always use with HITL confirmation in production.
    
    Capabilities:
    - Execute shell commands
    - Run Python scripts
    - Process management
    - Environment variable access
    """
    
    def __init__(self, config: SystemCommandConfig = None):
        super().__init__(config or SystemCommandConfig())
        self.config: SystemCommandConfig = self.config
        self._command_history: List[Dict] = []
        
    async def initialize(self) -> bool:
        """Initialize the system command provider"""
        try:
            if not self.config.enable_execution:
                logger.warning("SystemCommandProvider: Execution disabled by config")
            
            self._initialized = True
            logger.info("SystemCommandProvider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SystemCommandProvider: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if provider is healthy"""
        try:
            # Try a simple command
            result = subprocess.run(
                ["echo", "health_check"] if os.name != "nt" else ["cmd", "/c", "echo health_check"],
                capture_output=True,
                timeout=5
            )
            self._is_healthy = result.returncode == 0
        except Exception:
            self._is_healthy = False
        
        self._last_health_check = datetime.now()
        return self._is_healthy
    
    def get_capabilities(self) -> List[str]:
        """List available operations"""
        if self.config.enable_execution:
            return [
                "execute_command",
                "run_python",
                "run_script",
                "get_environment",
                "list_processes",
                "get_system_info"
            ]
        return ["get_environment", "get_system_info"]
    
    def _is_command_safe(self, command: str) -> tuple[bool, str]:
        """Check if a command is safe to execute"""
        command_lower = command.lower()
        
        # Check blocked commands
        for blocked in self.config.blocked_commands:
            if blocked.lower() in command_lower:
                return False, f"Blocked command detected: {blocked}"
        
        # Check blocked patterns
        for pattern in self.config.blocked_patterns:
            if pattern.lower() in command_lower:
                return False, f"Blocked pattern detected: {pattern}"
        
        # Check if base command is allowed
        parts = command.split()
        if parts:
            base_cmd = parts[0].lower()
            # Extract just the command name (not path)
            base_cmd = os.path.basename(base_cmd)
            
            # Remove common extensions
            for ext in ['.exe', '.bat', '.cmd', '.sh', '.ps1']:
                if base_cmd.endswith(ext):
                    base_cmd = base_cmd[:-len(ext)]
            
            if base_cmd not in [c.lower() for c in self.config.allowed_commands]:
                return False, f"Command '{base_cmd}' not in allowed list"
        
        return True, "OK"
    
    async def execute_command(
        self, 
        command: str, 
        working_dir: str = None,
        timeout: int = None,
        confirm: bool = None
    ) -> ProviderResult:
        """Execute a shell command"""
        if not self.config.enable_execution:
            return ProviderResult(
                success=False,
                error="Command execution is disabled",
                provider=self.provider_name,
                operation="execute_command"
            )
        
        # Safety check
        is_safe, reason = self._is_command_safe(command)
        if not is_safe:
            return ProviderResult(
                success=False,
                error=f"Security check failed: {reason}",
                provider=self.provider_name,
                operation="execute_command"
            )
        
        # HITL confirmation check
        should_confirm = confirm if confirm is not None else self.config.require_confirmation
        if should_confirm:
            logger.info(f"[HITL] Command pending confirmation: {command}")
            return ProviderResult(
                success=False,
                error="HITL_REQUIRED",
                data={
                    "action": "execute_command",
                    "command": command,
                    "working_dir": working_dir or self.config.working_directory,
                    "message": "Human confirmation required before execution"
                },
                provider=self.provider_name,
                operation="execute_command"
            )
        
        try:
            timeout = timeout or self.config.max_execution_time
            working_dir = working_dir or self.config.working_directory or os.getcwd()
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ProviderResult(
                    success=False,
                    error=f"Command timed out after {timeout} seconds",
                    provider=self.provider_name,
                    operation="execute_command"
                )
            
            stdout_str = stdout.decode('utf-8', errors='replace')[:self.config.max_output_size]
            stderr_str = stderr.decode('utf-8', errors='replace')[:self.config.max_output_size]
            
            # Log to history
            self._command_history.append({
                "command": command,
                "return_code": process.returncode,
                "timestamp": datetime.now().isoformat()
            })
            
            return ProviderResult(
                success=process.returncode == 0,
                data={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "return_code": process.returncode,
                    "command": command,
                    "working_dir": working_dir
                },
                provider=self.provider_name,
                operation="execute_command"
            )
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="execute_command"
            )
    
    async def run_python(
        self, 
        code: str, 
        timeout: int = None,
        confirm: bool = None
    ) -> ProviderResult:
        """Execute Python code snippet"""
        if not self.config.enable_execution:
            return ProviderResult(
                success=False,
                error="Python execution is disabled",
                provider=self.provider_name,
                operation="run_python"
            )
        
        # HITL confirmation check
        should_confirm = confirm if confirm is not None else self.config.require_confirmation
        if should_confirm:
            return ProviderResult(
                success=False,
                error="HITL_REQUIRED",
                data={
                    "action": "run_python",
                    "code_preview": code[:500],
                    "message": "Human confirmation required before execution"
                },
                provider=self.provider_name,
                operation="run_python"
            )
        
        try:
            import tempfile
            
            timeout = timeout or self.config.max_execution_time
            
            # Write code to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Execute Python script
                process = await asyncio.create_subprocess_exec(
                    'python', temp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return ProviderResult(
                    success=process.returncode == 0,
                    data={
                        "stdout": stdout.decode('utf-8', errors='replace'),
                        "stderr": stderr.decode('utf-8', errors='replace'),
                        "return_code": process.returncode
                    },
                    provider=self.provider_name,
                    operation="run_python"
                )
                
            finally:
                # Cleanup temp file
                os.unlink(temp_path)
                
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="run_python"
            )
    
    async def run_script(
        self, 
        script_path: str, 
        args: List[str] = None,
        timeout: int = None,
        confirm: bool = None
    ) -> ProviderResult:
        """Execute a script file"""
        if not self.config.enable_execution:
            return ProviderResult(
                success=False,
                error="Script execution is disabled",
                provider=self.provider_name,
                operation="run_script"
            )
        
        if not os.path.exists(script_path):
            return ProviderResult(
                success=False,
                error=f"Script not found: {script_path}",
                provider=self.provider_name,
                operation="run_script"
            )
        
        # HITL confirmation
        should_confirm = confirm if confirm is not None else self.config.require_confirmation
        if should_confirm:
            return ProviderResult(
                success=False,
                error="HITL_REQUIRED",
                data={
                    "action": "run_script",
                    "script_path": script_path,
                    "args": args,
                    "message": "Human confirmation required"
                },
                provider=self.provider_name,
                operation="run_script"
            )
        
        try:
            timeout = timeout or self.config.max_execution_time
            cmd = [script_path] + (args or [])
            
            # Determine interpreter based on extension
            ext = os.path.splitext(script_path)[1].lower()
            if ext == '.py':
                cmd = ['python'] + cmd
            elif ext == '.js':
                cmd = ['node'] + cmd
            elif ext in ['.sh', '.bash']:
                cmd = ['bash'] + cmd
            elif ext == '.ps1':
                cmd = ['powershell', '-File'] + cmd
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return ProviderResult(
                success=process.returncode == 0,
                data={
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "return_code": process.returncode,
                    "script": script_path
                },
                provider=self.provider_name,
                operation="run_script"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="run_script"
            )
    
    async def get_environment(self, var_name: str = None) -> ProviderResult:
        """Get environment variables"""
        try:
            if var_name:
                value = os.environ.get(var_name)
                if value is None:
                    return ProviderResult(
                        success=False,
                        error=f"Environment variable '{var_name}' not found",
                        provider=self.provider_name,
                        operation="get_environment"
                    )
                return ProviderResult(
                    success=True,
                    data={"name": var_name, "value": value},
                    provider=self.provider_name,
                    operation="get_environment"
                )
            else:
                # Return all (filtered for security)
                safe_vars = {}
                sensitive_patterns = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIAL']
                
                for key, value in os.environ.items():
                    is_sensitive = any(p in key.upper() for p in sensitive_patterns)
                    safe_vars[key] = "***REDACTED***" if is_sensitive else value
                
                return ProviderResult(
                    success=True,
                    data={"variables": safe_vars, "count": len(safe_vars)},
                    provider=self.provider_name,
                    operation="get_environment"
                )
                
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="get_environment"
            )
    
    async def get_system_info(self) -> ProviderResult:
        """Get system information"""
        try:
            import platform
            
            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "cwd": os.getcwd()
            }
            
            return ProviderResult(
                success=True,
                data=info,
                provider=self.provider_name,
                operation="get_system_info"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="get_system_info"
            )
    
    async def list_processes(self, filter_name: str = None) -> ProviderResult:
        """List running processes"""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    if filter_name and filter_name.lower() not in info['name'].lower():
                        continue
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu_percent": info['cpu_percent'],
                        "memory_percent": round(info['memory_percent'], 2)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return ProviderResult(
                success=True,
                data={"processes": processes[:100], "count": len(processes)},
                provider=self.provider_name,
                operation="list_processes"
            )
            
        except ImportError:
            return ProviderResult(
                success=False,
                error="psutil not installed. Run: pip install psutil",
                provider=self.provider_name,
                operation="list_processes"
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="list_processes"
            )


# Singleton instance
system_command_provider = SystemCommandProvider()
