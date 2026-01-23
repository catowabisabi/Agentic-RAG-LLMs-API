"""
Automation Service

Workflow automation through Zapier and GitHub.
Connect agents to external actions and triggers.

Features:
- Zapier workflow triggers
- GitHub automation
- Custom webhook triggers
- Action chaining
"""

import logging
from typing import Dict, Any, List, Optional

from mcp.providers.zapier_provider import ZapierProvider, ZapierConfig
from mcp.providers.github_provider import GitHubProvider, GitHubConfig

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Unified automation service.
    
    Provides:
    - Zapier integration for 6000+ apps
    - GitHub automation for code workflows
    - Custom webhook triggers
    """
    
    def __init__(
        self,
        zapier_api_key: str = None,
        github_token: str = None,
        github_owner: str = None,
        github_repo: str = None
    ):
        self._zapier: Optional[ZapierProvider] = None
        self._github: Optional[GitHubProvider] = None
        
        if zapier_api_key:
            config = ZapierConfig(api_key=zapier_api_key)
            self._zapier = ZapierProvider(config)
        
        if github_token:
            config = GitHubConfig(
                api_key=github_token,
                default_owner=github_owner or "",
                default_repo=github_repo or ""
            )
            self._github = GitHubProvider(config)
        
        logger.info("AutomationService initialized")
    
    async def initialize(self):
        """Initialize all providers"""
        if self._zapier:
            await self._zapier.initialize()
        if self._github:
            await self._github.initialize()
    
    # ============== Zapier Integration ==============
    
    async def list_zapier_actions(self) -> Dict[str, Any]:
        """
        List available Zapier actions.
        
        Returns:
            Available actions
        """
        if not self._zapier:
            return {"error": "Zapier not configured"}
        
        result = await self._zapier.list_actions()
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def run_zapier_action(
        self,
        action_id: str,
        instructions: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run a Zapier action.
        
        Args:
            action_id: Action ID
            instructions: Natural language instructions
            params: Additional parameters
            
        Returns:
            Action result
        """
        if not self._zapier:
            return {"error": "Zapier not configured"}
        
        result = await self._zapier.run_action(action_id, instructions, params)
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def trigger_webhook(
        self,
        webhook_url: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger a Zapier webhook.
        
        Args:
            webhook_url: Webhook URL
            data: Data to send
            
        Returns:
            Trigger result
        """
        if not self._zapier:
            return {"error": "Zapier not configured"}
        
        result = await self._zapier.trigger_webhook(webhook_url, data)
        if result.success:
            return result.data
        return {"error": result.error}
    
    # ============== GitHub Integration ==============
    
    async def get_github_user(self) -> Dict[str, Any]:
        """Get GitHub user info"""
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.get_user()
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def list_repos(self) -> Dict[str, Any]:
        """List repositories"""
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.list_repos()
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def create_issue(
        self,
        title: str,
        body: str = "",
        labels: List[str] = None,
        owner: str = None,
        repo: str = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue.
        
        Args:
            title: Issue title
            body: Issue body
            labels: Labels
            owner: Repo owner
            repo: Repo name
            
        Returns:
            Created issue
        """
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.create_issue(
            title=title,
            body=body,
            labels=labels,
            owner=owner,
            repo=repo
        )
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        owner: str = None,
        repo: str = None
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            owner: Repo owner
            repo: Repo name
            
        Returns:
            Created PR
        """
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.create_pr(
            title=title,
            body=body,
            head=head,
            base=base,
            owner=owner,
            repo=repo
        )
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        owner: str = None,
        repo: str = None,
        branch: str = None
    ) -> Dict[str, Any]:
        """
        Commit a file to repository.
        
        Args:
            path: File path
            content: File content
            message: Commit message
            owner: Repo owner
            repo: Repo name
            branch: Target branch
            
        Returns:
            Commit result
        """
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.create_file(
            path=path,
            content=content,
            message=message,
            owner=owner,
            repo=repo,
            branch=branch
        )
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def search_code(
        self,
        query: str,
        language: str = None
    ) -> Dict[str, Any]:
        """
        Search code on GitHub.
        
        Args:
            query: Search query
            language: Language filter
            
        Returns:
            Search results
        """
        if not self._github:
            return {"error": "GitHub not configured"}
        
        result = await self._github.search_code(query, language)
        if result.success:
            return result.data
        return {"error": result.error}
    
    # ============== Combined Workflows ==============
    
    async def notify_and_create_issue(
        self,
        title: str,
        body: str,
        notification_webhook: str = None,
        labels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create an issue and send notification.
        
        Args:
            title: Issue title
            body: Issue body
            notification_webhook: Zapier webhook for notification
            labels: Issue labels
            
        Returns:
            Combined result
        """
        results = {"issue": None, "notification": None}
        
        # Create GitHub issue
        if self._github:
            issue = await self.create_issue(title, body, labels)
            results["issue"] = issue
        
        # Send notification via Zapier
        if self._zapier and notification_webhook:
            notification = await self.trigger_webhook(
                notification_webhook,
                {
                    "title": title,
                    "body": body,
                    "labels": labels,
                    "issue_url": results.get("issue", {}).get("html_url")
                }
            )
            results["notification"] = notification
        
        return results
    
    async def code_review_workflow(
        self,
        code: str,
        file_path: str,
        branch: str,
        pr_title: str,
        pr_body: str = ""
    ) -> Dict[str, Any]:
        """
        Full code review workflow:
        1. Commit code to branch
        2. Create pull request
        
        Args:
            code: Code content
            file_path: File path
            branch: Branch name
            pr_title: PR title
            pr_body: PR description
            
        Returns:
            Workflow result
        """
        results = {}
        
        if not self._github:
            return {"error": "GitHub not configured"}
        
        # 1. Commit the code
        commit_result = await self.commit_file(
            path=file_path,
            content=code,
            message=f"Add {file_path}",
            branch=branch
        )
        results["commit"] = commit_result
        
        if "error" in commit_result:
            return results
        
        # 2. Create PR
        pr_result = await self.create_pull_request(
            title=pr_title,
            body=pr_body,
            head=branch,
            base="main"
        )
        results["pull_request"] = pr_result
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "zapier": self._zapier.get_status() if self._zapier else {"available": False},
            "github": self._github.get_status() if self._github else {"available": False}
        }
    
    async def close(self):
        """Close all providers"""
        if self._zapier:
            await self._zapier.close()
        if self._github:
            await self._github.close()
