"""
GitHub Provider

GitHub repository management and automation.
Supports code operations, PRs, issues, and more.

Features:
- Repository management
- Pull request operations
- Issue tracking
- Code search
- File operations
"""

import logging
import base64
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class GitHubConfig(ProviderConfig):
    """Configuration for GitHub"""
    base_url: str = "https://api.github.com"
    default_owner: str = ""
    default_repo: str = ""


class GitHubProvider(BaseProvider):
    """
    GitHub provider for repository operations.
    
    Capabilities:
    - repos: List, create, manage repositories
    - files: Read, write, update files
    - pull_requests: Create, review, merge PRs
    - issues: Create, update, search issues
    - search: Search code, repos, users
    """
    
    def __init__(self, config: GitHubConfig = None):
        super().__init__(config or GitHubConfig())
        self.config: GitHubConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the GitHub client"""
        try:
            if not self.config.api_key:
                logger.warning("GitHub token not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("GitHub provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GitHub: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if GitHub API is available"""
        try:
            await self.ensure_initialized()
            response = await self._client.get("/user")
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return [
            "get_user", "list_repos", "get_repo",
            "get_file", "create_file", "update_file",
            "create_pr", "list_prs", "merge_pr",
            "create_issue", "list_issues", "update_issue",
            "search_code", "search_repos"
        ]
    
    def _get_repo_path(self, owner: str = None, repo: str = None) -> str:
        """Get the repo path from params or defaults"""
        owner = owner or self.config.default_owner
        repo = repo or self.config.default_repo
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified")
        return f"{owner}/{repo}"
    
    async def get_user(self) -> ProviderResult:
        """
        Get authenticated user info.
        
        Returns:
            ProviderResult with user info
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get("/user")
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="get_user",
                data={
                    "login": data.get("login"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "public_repos": data.get("public_repos"),
                    "followers": data.get("followers"),
                    "avatar_url": data.get("avatar_url")
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub get_user error: {e}")
            return self._error("get_user", str(e))
    
    async def list_repos(
        self,
        type: str = "all",  # all, owner, public, private, member
        sort: str = "updated",  # created, updated, pushed, full_name
        per_page: int = 30
    ) -> ProviderResult:
        """
        List user's repositories.
        
        Args:
            type: Type of repos to list
            sort: Sort field
            per_page: Results per page
            
        Returns:
            ProviderResult with repo list
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get(
                "/user/repos",
                params={"type": type, "sort": sort, "per_page": per_page}
            )
            response.raise_for_status()
            
            repos = response.json()
            
            return self._success(
                operation="list_repos",
                data={
                    "repos": [
                        {
                            "full_name": r.get("full_name"),
                            "description": r.get("description"),
                            "language": r.get("language"),
                            "stars": r.get("stargazers_count"),
                            "forks": r.get("forks_count"),
                            "private": r.get("private"),
                            "updated_at": r.get("updated_at")
                        }
                        for r in repos
                    ],
                    "count": len(repos)
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub list_repos error: {e}")
            return self._error("list_repos", str(e))
    
    async def get_repo(
        self,
        owner: str = None,
        repo: str = None
    ) -> ProviderResult:
        """
        Get repository information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            ProviderResult with repo info
        """
        try:
            await self.ensure_initialized()
            repo_path = self._get_repo_path(owner, repo)
            
            response = await self._client.get(f"/repos/{repo_path}")
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="get_repo",
                data={
                    "full_name": data.get("full_name"),
                    "description": data.get("description"),
                    "language": data.get("language"),
                    "default_branch": data.get("default_branch"),
                    "stars": data.get("stargazers_count"),
                    "forks": data.get("forks_count"),
                    "open_issues": data.get("open_issues_count"),
                    "topics": data.get("topics", []),
                    "private": data.get("private"),
                    "html_url": data.get("html_url")
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub get_repo error: {e}")
            return self._error("get_repo", str(e))
    
    async def get_file(
        self,
        path: str,
        owner: str = None,
        repo: str = None,
        ref: str = None  # branch, tag, or commit SHA
    ) -> ProviderResult:
        """
        Get file content from repository.
        
        Args:
            path: File path
            owner: Repository owner
            repo: Repository name
            ref: Git reference
            
        Returns:
            ProviderResult with file content
        """
        try:
            await self.ensure_initialized()
            repo_path = self._get_repo_path(owner, repo)
            
            params = {}
            if ref:
                params["ref"] = ref
            
            response = await self._client.get(
                f"/repos/{repo_path}/contents/{path}",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Decode content
            content = ""
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8")
            
            return self._success(
                operation="get_file",
                data={
                    "path": path,
                    "name": data.get("name"),
                    "sha": data.get("sha"),
                    "size": data.get("size"),
                    "content": content,
                    "html_url": data.get("html_url")
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub get_file error: {e}")
            return self._error("get_file", str(e), path=path)
    
    async def create_file(
        self,
        path: str,
        content: str,
        message: str,
        owner: str = None,
        repo: str = None,
        branch: str = None
    ) -> ProviderResult:
        """
        Create a new file in repository.
        
        Args:
            path: File path
            content: File content
            message: Commit message
            owner: Repository owner
            repo: Repository name
            branch: Target branch
            
        Returns:
            ProviderResult with commit info
        """
        try:
            await self.ensure_initialized()
            repo_path = self._get_repo_path(owner, repo)
            
            payload = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode()
            }
            
            if branch:
                payload["branch"] = branch
            
            response = await self._client.put(
                f"/repos/{repo_path}/contents/{path}",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="create_file",
                data={
                    "path": path,
                    "sha": data.get("content", {}).get("sha"),
                    "commit_sha": data.get("commit", {}).get("sha"),
                    "html_url": data.get("content", {}).get("html_url")
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub create_file error: {e}")
            return self._error("create_file", str(e), path=path)
    
    async def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        owner: str = None,
        repo: str = None,
        draft: bool = False
    ) -> ProviderResult:
        """
        Create a pull request.
        
        Args:
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            owner: Repository owner
            repo: Repository name
            draft: Create as draft PR
            
        Returns:
            ProviderResult with PR info
        """
        try:
            await self.ensure_initialized()
            repo_path = self._get_repo_path(owner, repo)
            
            payload = {
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft
            }
            
            response = await self._client.post(
                f"/repos/{repo_path}/pulls",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="create_pr",
                data={
                    "number": data.get("number"),
                    "title": data.get("title"),
                    "state": data.get("state"),
                    "html_url": data.get("html_url"),
                    "mergeable": data.get("mergeable"),
                    "draft": data.get("draft")
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub create_pr error: {e}")
            return self._error("create_pr", str(e))
    
    async def create_issue(
        self,
        title: str,
        body: str = "",
        labels: List[str] = None,
        assignees: List[str] = None,
        owner: str = None,
        repo: str = None
    ) -> ProviderResult:
        """
        Create an issue.
        
        Args:
            title: Issue title
            body: Issue description
            labels: Issue labels
            assignees: Users to assign
            owner: Repository owner
            repo: Repository name
            
        Returns:
            ProviderResult with issue info
        """
        try:
            await self.ensure_initialized()
            repo_path = self._get_repo_path(owner, repo)
            
            payload = {
                "title": title,
                "body": body
            }
            
            if labels:
                payload["labels"] = labels
            if assignees:
                payload["assignees"] = assignees
            
            response = await self._client.post(
                f"/repos/{repo_path}/issues",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="create_issue",
                data={
                    "number": data.get("number"),
                    "title": data.get("title"),
                    "state": data.get("state"),
                    "html_url": data.get("html_url"),
                    "labels": [l.get("name") for l in data.get("labels", [])]
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub create_issue error: {e}")
            return self._error("create_issue", str(e))
    
    async def search_code(
        self,
        query: str,
        language: str = None,
        per_page: int = 10
    ) -> ProviderResult:
        """
        Search code across GitHub.
        
        Args:
            query: Search query
            language: Programming language filter
            per_page: Results per page
            
        Returns:
            ProviderResult with search results
        """
        try:
            await self.ensure_initialized()
            
            q = query
            if language:
                q += f" language:{language}"
            
            response = await self._client.get(
                "/search/code",
                params={"q": q, "per_page": per_page}
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="search_code",
                data={
                    "query": query,
                    "total_count": data.get("total_count", 0),
                    "results": [
                        {
                            "name": item.get("name"),
                            "path": item.get("path"),
                            "repository": item.get("repository", {}).get("full_name"),
                            "html_url": item.get("html_url")
                        }
                        for item in data.get("items", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"GitHub search_code error: {e}")
            return self._error("search_code", str(e), query=query)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
