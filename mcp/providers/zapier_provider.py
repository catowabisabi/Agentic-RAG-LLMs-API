"""
Zapier Provider

Connect to 6000+ apps through Zapier.
Trigger automated workflows from agent actions.

Features:
- Trigger Zaps via webhooks
- Natural language actions (NLA)
- Action execution
- Workflow automation
"""

import logging
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class ZapierConfig(ProviderConfig):
    """Configuration for Zapier"""
    base_url: str = "https://nla.zapier.com/api/v1"
    webhook_base_url: str = "https://hooks.zapier.com/hooks/catch"


class ZapierProvider(BaseProvider):
    """
    Zapier provider for workflow automation.
    
    Capabilities:
    - list_actions: List available actions
    - run_action: Execute a Zapier action
    - trigger_webhook: Trigger a Zap webhook
    """
    
    def __init__(self, config: ZapierConfig = None):
        super().__init__(config or ZapierConfig())
        self.config: ZapierConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
        self._webhook_client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the Zapier client"""
        try:
            if not self.config.api_key:
                logger.warning("Zapier API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout
            )
            
            self._webhook_client = httpx.AsyncClient(
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("Zapier provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Zapier: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Zapier API is available"""
        try:
            await self.ensure_initialized()
            response = await self._client.get("/exposed/")
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.error(f"Zapier health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return ["list_actions", "run_action", "trigger_webhook", "search_actions"]
    
    async def list_actions(self) -> ProviderResult:
        """
        List all available Zapier actions.
        
        Returns:
            ProviderResult with available actions
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get("/exposed/")
            response.raise_for_status()
            
            data = response.json()
            
            actions = []
            for action in data.get("results", []):
                actions.append({
                    "id": action.get("id"),
                    "operation_id": action.get("operation_id"),
                    "description": action.get("description"),
                    "params": action.get("params", {})
                })
            
            return self._success(
                operation="list_actions",
                data={
                    "actions": actions,
                    "count": len(actions)
                }
            )
            
        except Exception as e:
            logger.error(f"Zapier list_actions error: {e}")
            return self._error("list_actions", str(e))
    
    async def run_action(
        self,
        action_id: str,
        instructions: str,
        params: Dict[str, Any] = None,
        preview_only: bool = False
    ) -> ProviderResult:
        """
        Run a Zapier action using Natural Language Actions.
        
        Args:
            action_id: Action ID (from list_actions)
            instructions: Natural language instructions
            params: Additional parameters
            preview_only: If True, preview without executing
            
        Returns:
            ProviderResult with action result
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "instructions": instructions,
                "preview_only": preview_only
            }
            
            if params:
                payload.update(params)
            
            response = await self._client.post(
                f"/exposed/{action_id}/execute/",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="run_action",
                data={
                    "action_id": action_id,
                    "status": data.get("status"),
                    "result": data.get("result"),
                    "result_str": data.get("result_str"),
                    "preview": data.get("preview") if preview_only else None
                }
            )
            
        except Exception as e:
            logger.error(f"Zapier run_action error: {e}")
            return self._error("run_action", str(e), action_id=action_id)
    
    async def trigger_webhook(
        self,
        webhook_url: str,
        data: Dict[str, Any]
    ) -> ProviderResult:
        """
        Trigger a Zapier webhook.
        
        Args:
            webhook_url: Full webhook URL or just the path
            data: Data to send
            
        Returns:
            ProviderResult
        """
        try:
            await self.ensure_initialized()
            
            # Ensure full URL
            if not webhook_url.startswith("http"):
                webhook_url = f"{self.config.webhook_base_url}/{webhook_url}"
            
            response = await self._webhook_client.post(
                webhook_url,
                json=data
            )
            response.raise_for_status()
            
            return self._success(
                operation="trigger_webhook",
                data={
                    "webhook_url": webhook_url,
                    "triggered": True,
                    "response": response.text
                }
            )
            
        except Exception as e:
            logger.error(f"Zapier trigger_webhook error: {e}")
            return self._error("trigger_webhook", str(e), webhook_url=webhook_url)
    
    async def search_actions(
        self,
        query: str
    ) -> ProviderResult:
        """
        Search for actions by keyword.
        
        Args:
            query: Search query
            
        Returns:
            ProviderResult with matching actions
        """
        try:
            await self.ensure_initialized()
            
            # Get all actions and filter
            all_actions = await self.list_actions()
            
            if not all_actions.success:
                return all_actions
            
            query_lower = query.lower()
            matching = [
                a for a in all_actions.data.get("actions", [])
                if query_lower in a.get("description", "").lower()
            ]
            
            return self._success(
                operation="search_actions",
                data={
                    "query": query,
                    "actions": matching,
                    "count": len(matching)
                }
            )
            
        except Exception as e:
            logger.error(f"Zapier search_actions error: {e}")
            return self._error("search_actions", str(e), query=query)
    
    async def close(self):
        """Close HTTP clients"""
        if self._client:
            await self._client.aclose()
        if self._webhook_client:
            await self._webhook_client.aclose()
