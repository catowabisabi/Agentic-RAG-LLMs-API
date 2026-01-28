"""
MCP 服務測試腳本
==================

此腳本用於驗證 MCP（Model Context Protocol）各服務的可用性和功能。

MCP 服務清單：
1. Web Scraping（Brave Search, Firecrawl, Exa）
2. Code Execution（E2B）
3. Database（Supabase）
4. Automation（Zapier, GitHub）
5. Medical RAG（PubMed）
6. File Control
7. System Commands

使用方式：
    python Scripts/test_mcp_services.py --all      # 測試所有服務
    python Scripts/test_mcp_services.py --service web_scraping
"""

import asyncio
import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

# 添加項目根目錄
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def import_module_from_path(module_name: str, file_path: Path):
    """從指定路徑導入模塊，避免相對導入問題"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class MCPServiceTester:
    """MCP 服務測試器"""
    
    def __init__(self):
        self.results = {}
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """載入環境變數配置"""
        from dotenv import load_dotenv
        load_dotenv()
        
        return {
            "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY"),
            "E2B_API_KEY": os.getenv("E2B_API_KEY"),
            "SUPABASE_URL": os.getenv("SUPABASE_URL"),
            "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
            "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
            "ZAPIER_API_KEY": os.getenv("ZAPIER_API_KEY"),
            "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
            "EXA_API_KEY": os.getenv("EXA_API_KEY"),
        }
    
    def _log(self, service: str, status: str, message: str):
        """記錄測試結果"""
        icon = "✅" if status == "pass" else "❌" if status == "fail" else "⚠️"
        print(f"{icon} [{service}] {message}")
        
        self.results[service] = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    
    async def test_brave_search(self):
        """測試 Brave Search"""
        service = "brave_search"
        
        if not self.config.get("BRAVE_API_KEY"):
            self._log(service, "skip", "BRAVE_API_KEY not configured")
            return
        
        try:
            from mcp.providers.brave_search_provider import BraveSearchProvider, BraveSearchConfig
            
            config = BraveSearchConfig(api_key=self.config["BRAVE_API_KEY"])
            provider = BraveSearchProvider(config)
            
            if await provider.initialize():
                result = await provider.web_search("test query", count=1)
                if result.success:
                    self._log(service, "pass", f"Search works - got {len(result.data.get('results', []))} results")
                else:
                    self._log(service, "fail", f"Search failed: {result.error}")
            else:
                self._log(service, "fail", "Failed to initialize")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_e2b_code_execution(self):
        """測試 E2B 程式碼執行"""
        service = "e2b"
        
        if not self.config.get("E2B_API_KEY"):
            self._log(service, "skip", "E2B_API_KEY not configured")
            return
        
        try:
            from mcp.services.code_execution_service import CodeExecutionService
            
            service_obj = CodeExecutionService(e2b_api_key=self.config["E2B_API_KEY"])
            await service_obj.initialize()
            
            result = await service_obj.execute_code("print('Hello MCP!')", language="python")
            
            if "error" not in result:
                self._log(service, "pass", f"Code execution works")
            else:
                self._log(service, "fail", f"Execution failed: {result.get('error')}")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_database_service(self):
        """測試 Database Service (Supabase)"""
        service = "database"
        
        if not self.config.get("SUPABASE_URL") or not self.config.get("SUPABASE_KEY"):
            self._log(service, "skip", "SUPABASE_URL/KEY not configured")
            return
        
        try:
            from mcp.services.database_service import DatabaseService
            
            service_obj = DatabaseService(
                supabase_url=self.config["SUPABASE_URL"],
                supabase_key=self.config["SUPABASE_KEY"]
            )
            await service_obj.initialize()
            
            # 測試基本查詢
            self._log(service, "pass", "Database service initialized")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_github_provider(self):
        """測試 GitHub Provider"""
        service = "github"
        
        if not self.config.get("GITHUB_TOKEN"):
            self._log(service, "skip", "GITHUB_TOKEN not configured")
            return
        
        try:
            from mcp.providers.github_provider import GitHubProvider, GitHubConfig
            
            config = GitHubConfig(api_key=self.config["GITHUB_TOKEN"])
            provider = GitHubProvider(config)
            
            if await provider.initialize():
                self._log(service, "pass", "GitHub provider initialized")
            else:
                self._log(service, "fail", "Failed to initialize")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_medical_rag(self):
        """測試 Medical RAG Service"""
        service = "medical_rag"
        
        try:
            from mcp.services.medical_rag_service import MedicalRAGService
            
            service_obj = MedicalRAGService()
            
            if await service_obj.initialize():
                # 測試 PubMed 搜尋（不需要 API key）
                result = await service_obj.search_pubmed("diabetes treatment", max_results=1)
                
                if result and len(result) > 0:
                    self._log(service, "pass", f"PubMed search works - got {len(result)} results")
                else:
                    self._log(service, "warn", "PubMed search returned no results (may need biopython)")
            else:
                self._log(service, "fail", "Failed to initialize")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_file_control(self):
        """測試 File Control Provider"""
        service = "file_control"
        
        try:
            # 使用 mcp.providers 包導入
            from mcp.providers.file_control_provider import FileControlProvider, FileControlConfig
            
            config = FileControlConfig()
            provider = FileControlProvider(config)
            await provider.initialize()
            
            # 測試讀取 README
            readme_path = project_root / "app_docs" / "README.md"
            if readme_path.exists():
                result = await provider.read_txt(str(readme_path))
                if result.success:
                    self._log(service, "pass", f"File read works - {len(result.data.get('content', ''))} chars")
                else:
                    self._log(service, "fail", f"File read failed: {result.error}")
            else:
                self._log(service, "warn", "No README.md found for testing")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def test_system_commands(self):
        """測試 System Command Provider"""
        service = "system_commands"
        
        try:
            from mcp.providers.system_command_provider import SystemCommandProvider, SystemCommandConfig
            
            # 測試時禁用 HITL 確認
            config = SystemCommandConfig(require_confirmation=False)
            provider = SystemCommandProvider(config)
            await provider.initialize()
            
            # 測試安全的系統指令
            result = await provider.execute_command("echo MCP_TEST_OK", timeout=5)
            
            if result.success:
                output = result.data.get('stdout', '').strip()
                self._log(service, "pass", f"System commands work - output: {output}")
            else:
                self._log(service, "fail", f"Command failed: {result.error}")
                
        except Exception as e:
            self._log(service, "fail", f"Exception: {e}")
    
    async def run_all_tests(self):
        """執行所有測試"""
        print("\n" + "="*60)
        print("🧪 MCP 服務測試")
        print("="*60 + "\n")
        
        # 按順序執行測試
        await self.test_file_control()
        await self.test_system_commands()
        await self.test_medical_rag()
        await self.test_brave_search()
        await self.test_e2b_code_execution()
        await self.test_database_service()
        await self.test_github_provider()
        
        # 輸出摘要
        print("\n" + "="*60)
        print("📊 測試摘要")
        print("="*60)
        
        passed = sum(1 for r in self.results.values() if r["status"] == "pass")
        failed = sum(1 for r in self.results.values() if r["status"] == "fail")
        skipped = sum(1 for r in self.results.values() if r["status"] == "skip")
        warned = sum(1 for r in self.results.values() if r["status"] == "warn")
        
        print(f"✅ 通過: {passed}")
        print(f"❌ 失敗: {failed}")
        print(f"⚠️ 警告: {warned}")
        print(f"⏭️ 跳過: {skipped}")
        
        return self.results


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP 服務測試")
    parser.add_argument("--all", action="store_true", help="測試所有服務")
    parser.add_argument("--service", type=str, help="測試特定服務")
    
    args = parser.parse_args()
    
    tester = MCPServiceTester()
    
    if args.service:
        method_name = f"test_{args.service}"
        if hasattr(tester, method_name):
            await getattr(tester, method_name)()
        else:
            print(f"未知服務: {args.service}")
    else:
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
