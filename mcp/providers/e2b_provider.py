"""
E2B Provider

Cloud code execution sandbox.
Allows agents to safely execute code in isolated environments.

Features:
- Python/JavaScript execution
- File system access
- Package installation
- Persistent sessions
"""

import logging
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class E2BConfig(ProviderConfig):
    """Configuration for E2B"""
    base_url: str = "https://api.e2b.dev"
    default_template: str = "base"  # base, python, nodejs, etc.
    session_timeout: int = 300  # 5 minutes


class E2BProvider(BaseProvider):
    """
    E2B provider for cloud code execution.
    
    Capabilities:
    - create_sandbox: Create a new sandbox
    - execute_code: Run code in sandbox
    - run_command: Run shell command
    - file_operations: Read/write files
    - install_packages: Install Python/Node packages
    """
    
    def __init__(self, config: E2BConfig = None):
        super().__init__(config or E2BConfig())
        self.config: E2BConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
        self._active_sandboxes: Dict[str, str] = {}  # sandbox_id -> template
    
    async def initialize(self) -> bool:
        """Initialize the E2B client"""
        try:
            if not self.config.api_key:
                logger.warning("E2B API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"X-API-Key": self.config.api_key},
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("E2B provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize E2B: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if E2B API is available"""
        try:
            await self.ensure_initialized()
            response = await self._client.get("/health")
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.error(f"E2B health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return [
            "create_sandbox", "close_sandbox", "list_sandboxes",
            "execute_python", "execute_javascript", "run_command",
            "write_file", "read_file", "list_files",
            "install_packages"
        ]
    
    async def create_sandbox(
        self,
        template: str = None,
        metadata: Dict[str, Any] = None
    ) -> ProviderResult:
        """
        Create a new code execution sandbox.
        
        Args:
            template: Sandbox template (base, python, nodejs)
            metadata: Additional metadata
            
        Returns:
            ProviderResult with sandbox info
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "template": template or self.config.default_template
            }
            
            if metadata:
                payload["metadata"] = metadata
            
            response = await self._client.post("/sandboxes", json=payload)
            response.raise_for_status()
            
            data = response.json()
            sandbox_id = data.get("sandboxId")
            
            if sandbox_id:
                self._active_sandboxes[sandbox_id] = payload["template"]
            
            return self._success(
                operation="create_sandbox",
                data={
                    "sandbox_id": sandbox_id,
                    "template": payload["template"],
                    "client_id": data.get("clientId"),
                    "started_at": data.get("startedAt")
                }
            )
            
        except Exception as e:
            logger.error(f"E2B create_sandbox error: {e}")
            return self._error("create_sandbox", str(e))
    
    async def close_sandbox(self, sandbox_id: str) -> ProviderResult:
        """
        Close a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            
        Returns:
            ProviderResult
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.delete(f"/sandboxes/{sandbox_id}")
            response.raise_for_status()
            
            self._active_sandboxes.pop(sandbox_id, None)
            
            return self._success(
                operation="close_sandbox",
                data={"sandbox_id": sandbox_id, "closed": True}
            )
            
        except Exception as e:
            logger.error(f"E2B close_sandbox error: {e}")
            return self._error("close_sandbox", str(e), sandbox_id=sandbox_id)
    
    async def execute_python(
        self,
        sandbox_id: str,
        code: str,
        timeout: int = 30
    ) -> ProviderResult:
        """
        Execute Python code in sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            code: Python code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            ProviderResult with execution result
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "code": code,
                "timeout": timeout
            }
            
            response = await self._client.post(
                f"/sandboxes/{sandbox_id}/code/execute",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="execute_python",
                data={
                    "sandbox_id": sandbox_id,
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exitCode"),
                    "results": data.get("results", []),
                    "error": data.get("error")
                }
            )
            
        except Exception as e:
            logger.error(f"E2B execute_python error: {e}")
            return self._error("execute_python", str(e), sandbox_id=sandbox_id)
    
    async def execute_javascript(
        self,
        sandbox_id: str,
        code: str,
        timeout: int = 30
    ) -> ProviderResult:
        """
        Execute JavaScript code in sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            code: JavaScript code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            ProviderResult with execution result
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "code": code,
                "language": "javascript",
                "timeout": timeout
            }
            
            response = await self._client.post(
                f"/sandboxes/{sandbox_id}/code/execute",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="execute_javascript",
                data={
                    "sandbox_id": sandbox_id,
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exitCode"),
                    "results": data.get("results", [])
                }
            )
            
        except Exception as e:
            logger.error(f"E2B execute_javascript error: {e}")
            return self._error("execute_javascript", str(e), sandbox_id=sandbox_id)
    
    async def run_command(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 30,
        cwd: str = None
    ) -> ProviderResult:
        """
        Run a shell command in sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            command: Shell command
            timeout: Execution timeout
            cwd: Working directory
            
        Returns:
            ProviderResult with command output
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "cmd": command,
                "timeout": timeout
            }
            
            if cwd:
                payload["cwd"] = cwd
            
            response = await self._client.post(
                f"/sandboxes/{sandbox_id}/commands",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="run_command",
                data={
                    "sandbox_id": sandbox_id,
                    "command": command,
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exitCode")
                }
            )
            
        except Exception as e:
            logger.error(f"E2B run_command error: {e}")
            return self._error("run_command", str(e), sandbox_id=sandbox_id)
    
    async def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str
    ) -> ProviderResult:
        """
        Write a file in sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            path: File path
            content: File content
            
        Returns:
            ProviderResult
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "path": path,
                "content": content
            }
            
            response = await self._client.post(
                f"/sandboxes/{sandbox_id}/files",
                json=payload
            )
            response.raise_for_status()
            
            return self._success(
                operation="write_file",
                data={
                    "sandbox_id": sandbox_id,
                    "path": path,
                    "written": True
                }
            )
            
        except Exception as e:
            logger.error(f"E2B write_file error: {e}")
            return self._error("write_file", str(e), sandbox_id=sandbox_id)
    
    async def read_file(
        self,
        sandbox_id: str,
        path: str
    ) -> ProviderResult:
        """
        Read a file from sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            path: File path
            
        Returns:
            ProviderResult with file content
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get(
                f"/sandboxes/{sandbox_id}/files",
                params={"path": path}
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="read_file",
                data={
                    "sandbox_id": sandbox_id,
                    "path": path,
                    "content": data.get("content", "")
                }
            )
            
        except Exception as e:
            logger.error(f"E2B read_file error: {e}")
            return self._error("read_file", str(e), sandbox_id=sandbox_id)
    
    async def list_files(
        self,
        sandbox_id: str,
        path: str = "/"
    ) -> ProviderResult:
        """
        List files in a directory.
        
        Args:
            sandbox_id: Sandbox ID
            path: Directory path
            
        Returns:
            ProviderResult with file list
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get(
                f"/sandboxes/{sandbox_id}/files/list",
                params={"path": path}
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="list_files",
                data={
                    "sandbox_id": sandbox_id,
                    "path": path,
                    "files": data.get("files", [])
                }
            )
            
        except Exception as e:
            logger.error(f"E2B list_files error: {e}")
            return self._error("list_files", str(e), sandbox_id=sandbox_id)
    
    async def install_packages(
        self,
        sandbox_id: str,
        packages: List[str],
        manager: str = "pip"  # pip, npm, yarn
    ) -> ProviderResult:
        """
        Install packages in sandbox.
        
        Args:
            sandbox_id: Sandbox ID
            packages: List of packages
            manager: Package manager (pip, npm, yarn)
            
        Returns:
            ProviderResult with install output
        """
        try:
            await self.ensure_initialized()
            
            if manager == "pip":
                command = f"pip install {' '.join(packages)}"
            elif manager == "npm":
                command = f"npm install {' '.join(packages)}"
            elif manager == "yarn":
                command = f"yarn add {' '.join(packages)}"
            else:
                return self._error("install_packages", f"Unknown manager: {manager}")
            
            result = await self.run_command(sandbox_id, command, timeout=120)
            
            if result.success:
                return self._success(
                    operation="install_packages",
                    data={
                        "sandbox_id": sandbox_id,
                        "packages": packages,
                        "manager": manager,
                        "output": result.data.get("stdout", "")
                    }
                )
            else:
                return result
            
        except Exception as e:
            logger.error(f"E2B install_packages error: {e}")
            return self._error("install_packages", str(e), sandbox_id=sandbox_id)
    
    async def close(self):
        """Close all sandboxes and HTTP client"""
        # Close all active sandboxes
        for sandbox_id in list(self._active_sandboxes.keys()):
            try:
                await self.close_sandbox(sandbox_id)
            except Exception as e:
                logger.error(f"Error closing sandbox {sandbox_id}: {e}")
        
        if self._client:
            await self._client.aclose()
