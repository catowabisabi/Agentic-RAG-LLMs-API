"""
Code Execution Service

Secure code execution in isolated sandboxes.
Uses E2B for cloud-based execution.

Features:
- Python/JavaScript execution
- Multi-language support
- Package installation
- File operations
- Session management
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from mcp.providers.e2b_provider import E2BProvider, E2BConfig

logger = logging.getLogger(__name__)


class CodeExecutionService:
    """
    Service for executing code in isolated environments.
    
    Provides:
    - Code execution in multiple languages
    - Persistent sessions
    - Package management
    - File operations
    """
    
    def __init__(self, e2b_api_key: str = None):
        self._e2b: Optional[E2BProvider] = None
        
        if e2b_api_key:
            config = E2BConfig(api_key=e2b_api_key)
            self._e2b = E2BProvider(config)
        
        # Active sessions
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("CodeExecutionService initialized")
    
    async def initialize(self):
        """Initialize the service"""
        if self._e2b:
            await self._e2b.initialize()
    
    async def create_session(
        self,
        session_id: str = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Create a new code execution session.
        
        Args:
            session_id: Optional session ID
            language: Programming language
            
        Returns:
            Session info
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        template = "python" if language == "python" else "base"
        
        result = await self._e2b.create_sandbox(template=template)
        
        if result.success:
            sandbox_id = result.data.get("sandbox_id")
            sid = session_id or sandbox_id
            
            self._sessions[sid] = {
                "sandbox_id": sandbox_id,
                "language": language,
                "created_at": datetime.now().isoformat(),
                "executions": 0
            }
            
            return {
                "session_id": sid,
                "sandbox_id": sandbox_id,
                "language": language,
                "status": "active"
            }
        
        return {"error": result.error}
    
    async def execute_code(
        self,
        code: str,
        session_id: str = None,
        language: str = "python",
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute code.
        
        Args:
            code: Code to execute
            session_id: Session ID (creates new if not provided)
            language: Programming language
            timeout: Execution timeout
            
        Returns:
            Execution result
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        # Get or create session
        sandbox_id = None
        
        if session_id and session_id in self._sessions:
            sandbox_id = self._sessions[session_id]["sandbox_id"]
        else:
            # Create a new session
            session_result = await self.create_session(session_id, language)
            if "error" in session_result:
                return session_result
            sandbox_id = session_result["sandbox_id"]
            session_id = session_result["session_id"]
        
        # Execute code
        if language == "python":
            result = await self._e2b.execute_python(sandbox_id, code, timeout)
        elif language in ["javascript", "js"]:
            result = await self._e2b.execute_javascript(sandbox_id, code, timeout)
        else:
            return {"error": f"Unsupported language: {language}"}
        
        if result.success:
            # Update session stats
            if session_id in self._sessions:
                self._sessions[session_id]["executions"] += 1
            
            return {
                "session_id": session_id,
                "stdout": result.data.get("stdout", ""),
                "stderr": result.data.get("stderr", ""),
                "exit_code": result.data.get("exit_code"),
                "results": result.data.get("results", []),
                "error": result.data.get("error")
            }
        
        return {"error": result.error}
    
    async def run_command(
        self,
        command: str,
        session_id: str,
        cwd: str = None
    ) -> Dict[str, Any]:
        """
        Run a shell command in session.
        
        Args:
            command: Shell command
            session_id: Session ID
            cwd: Working directory
            
        Returns:
            Command output
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.run_command(sandbox_id, command, cwd=cwd)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def install_packages(
        self,
        packages: List[str],
        session_id: str,
        manager: str = "pip"
    ) -> Dict[str, Any]:
        """
        Install packages in a session.
        
        Args:
            packages: Package names
            session_id: Session ID
            manager: Package manager (pip, npm)
            
        Returns:
            Install result
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.install_packages(sandbox_id, packages, manager)
        
        if result.success:
            return {
                "session_id": session_id,
                "packages": packages,
                "installed": True,
                "output": result.data.get("output", "")
            }
        return {"error": result.error}
    
    async def write_file(
        self,
        path: str,
        content: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Write a file in session.
        
        Args:
            path: File path
            content: File content
            session_id: Session ID
            
        Returns:
            Write result
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.write_file(sandbox_id, path, content)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def read_file(
        self,
        path: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Read a file from session.
        
        Args:
            path: File path
            session_id: Session ID
            
        Returns:
            File content
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.read_file(sandbox_id, path)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def list_files(
        self,
        path: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        List files in a directory.
        
        Args:
            path: Directory path
            session_id: Session ID
            
        Returns:
            File list
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.list_files(sandbox_id, path)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """
        Close a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Close result
        """
        if not self._e2b:
            return {"error": "E2B not configured"}
        
        if session_id not in self._sessions:
            return {"error": f"Session {session_id} not found"}
        
        sandbox_id = self._sessions[session_id]["sandbox_id"]
        result = await self._e2b.close_sandbox(sandbox_id)
        
        if result.success:
            del self._sessions[session_id]
            return {"session_id": session_id, "closed": True}
        
        return {"error": result.error}
    
    def get_sessions(self) -> List[Dict[str, Any]]:
        """Get all active sessions"""
        return [
            {"session_id": sid, **info}
            for sid, info in self._sessions.items()
        ]
    
    async def execute_with_data_analysis(
        self,
        code: str,
        data: Dict[str, Any] = None,
        session_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute code with data pre-loaded.
        
        Useful for data analysis tasks where data
        needs to be available in the session.
        
        Args:
            code: Code to execute
            data: Data to make available as 'data' variable
            session_id: Optional session ID
            
        Returns:
            Execution result with any outputs
        """
        # Create session if needed
        if not session_id:
            session_result = await self.create_session(language="python")
            if "error" in session_result:
                return session_result
            session_id = session_result["session_id"]
        
        # Install common data analysis packages
        await self.install_packages(
            ["pandas", "numpy", "matplotlib"],
            session_id
        )
        
        # Prepare code with data
        full_code = """
import json
import pandas as pd
import numpy as np

"""
        
        if data:
            full_code += f"""
# Load data
data = json.loads('''{__import__('json').dumps(data)}''')
"""
        
        full_code += f"""
# User code
{code}
"""
        
        return await self.execute_code(full_code, session_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "e2b": self._e2b.get_status() if self._e2b else {"available": False},
            "active_sessions": len(self._sessions),
            "sessions": list(self._sessions.keys())
        }
    
    async def close(self):
        """Close all sessions and the service"""
        # Close all sessions
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)
        
        if self._e2b:
            await self._e2b.close()
