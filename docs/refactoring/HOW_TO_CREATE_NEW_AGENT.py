"""
如何建立新的 Agent - 完整指南

使用新的 Service Layer，建立新 Agent 變得非常簡單！
只需 3 個步驟，大約 30 分鐘即可完成。
"""

# ============================================================================
# 步驟 1: 創建 Prompt 配置文件 (5 分鐘)
# ============================================================================

# 在 config/prompts/ 目錄下創建 YAML 文件
# 例如: config/prompts/my_new_agent.yaml

"""
agent_name: my_new_agent

system_prompt: |
  You are a specialized agent for [describe your agent's purpose].
  
  Your responsibilities:
  - [Responsibility 1]
  - [Responsibility 2]
  - [Responsibility 3]
  
  When handling tasks:
  1. [Step 1]
  2. [Step 2]
  3. [Step 3]

temperature: 0.7
max_tokens: 2000

metadata:
  description: Brief description of what this agent does
  role: Agent Role Name
"""

# ============================================================================
# 步驟 2: 創建 Agent 類 (20 分鐘)
# ============================================================================

from typing import Dict, Any
import logging
from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment

logger = logging.getLogger(__name__)


class MyNewAgent(BaseAgent):
    """
    [描述你的 Agent]
    
    使用 Service Layer:
    - self.llm_service: 統一的 LLM 調用
    - self.rag_service: 統一的 RAG 查詢
    - self.broadcast: 統一的 WebSocket 廣播
    - self.prompt_manager: Prompt 模板管理
    """
    
    def __init__(self, agent_name: str = "my_new_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="My Role",
            agent_description="What this agent does"
        )
        
        # 加載 Prompt 模板
        self.prompt_template = self.prompt_manager.get_prompt("my_new_agent")
        
        logger.info(f"MyNewAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        處理任務
        
        Args:
            task: TaskAssignment 包含任務信息
            
        Returns:
            Dict 包含 response 和其他元數據
        """
        task_id = task.task_id
        query = task.input_data.get("query", task.description)
        
        # Step 1: 廣播開始狀態
        await self.broadcast.agent_status(
            self.agent_name,
            "started",
            task_id,
            {"query": query[:100]}
        )
        
        try:
            # Step 2: 使用 LLM Service 生成響應
            response = await self.llm_service.generate(
                prompt=query,
                system_message=self.prompt_template.system_prompt,
                temperature=self.prompt_template.temperature,
                max_tokens=self.prompt_template.max_tokens,
                session_id=task_id
            )
            
            # Step 3: 廣播完成狀態
            await self.broadcast.agent_status(
                self.agent_name,
                "completed",
                task_id,
                {
                    "response_preview": response.content[:200],
                    "tokens_used": response.usage.total_tokens
                }
            )
            
            # Step 4: 返回結果
            return {
                "response": response.content,
                "agents_involved": [self.agent_name],
                "usage": response.usage.model_dump()
            }
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error: {e}")
            
            await self.broadcast.error(
                self.agent_name,
                str(e),
                task_id
            )
            
            return {
                "response": "抱歉，處理時發生錯誤。",
                "error": str(e),
                "agents_involved": [self.agent_name]
            }


# ============================================================================
# 步驟 3: 註冊 Agent (5 分鐘)
# ============================================================================

# 在 main.py 的 create_agents() 函數中添加你的 Agent：

"""
async def create_agents():
    registry = AgentRegistry()
    
    # ... 現有的 Agent ...
    
    # 添加你的新 Agent
    from agents.my_module.my_new_agent import MyNewAgent
    my_new_agent = MyNewAgent()
    await my_new_agent.start()
    
    logger.info("所有 Agent 已啟動")
"""

# ============================================================================
# 進階用法: 使用 RAG Service
# ============================================================================

class AdvancedAgent(BaseAgent):
    """帶 RAG 功能的進階 Agent"""
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        task_id = task.task_id
        query = task.input_data.get("query", task.description)
        use_rag = task.input_data.get("use_rag", False)
        
        # 初始化
        context = ""
        sources = []
        
        # 如果需要 RAG，查詢知識庫
        if use_rag:
            await self.broadcast.agent_status(
                self.agent_name,
                "searching",
                task_id,
                {"message": "Searching knowledge bases..."}
            )
            
            # 使用 RAG Service 查詢
            from services.rag_service import RAGStrategy
            
            rag_result = await self.rag_service.query(
                query=query,
                strategy=RAGStrategy.AUTO,  # 自動選擇最佳策略
                top_k=5,
                threshold=0.3
            )
            
            context = rag_result.context
            sources = [s.model_dump() for s in rag_result.sources]
            
            # 廣播找到的來源
            await self.broadcast.rag_sources(sources, task_id)
        
        # 構建完整的 Prompt
        full_prompt = query
        if context:
            full_prompt = f"Context:\n{context}\n\nQuestion: {query}"
        
        # 使用 LLM 生成響應
        response = await self.llm_service.generate(
            prompt=full_prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=0.7,
            session_id=task_id
        )
        
        return {
            "response": response.content,
            "sources": sources,
            "agents_involved": [self.agent_name],
            "usage": response.usage.model_dump()
        }


# ============================================================================
# 測試你的 Agent
# ============================================================================

"""
# 創建測試腳本: testing_scripts/test_my_agent.py

import asyncio
from agents.my_module.my_new_agent import MyNewAgent
from agents.shared_services.message_protocol import TaskAssignment

async def test():
    agent = MyNewAgent()
    
    task = TaskAssignment(
        task_id="test-1",
        task_type="test",
        description="Test query",
        input_data={"query": "Test query"}
    )
    
    result = await agent.process_task(task)
    print(f"Response: {result['response']}")

asyncio.run(test())
"""

# ============================================================================
# 完整範例: 創建一個「程式碼審查 Agent」
# ============================================================================

class CodeReviewAgent(BaseAgent):
    """
    程式碼審查 Agent
    
    專門審查程式碼品質、安全性、性能問題
    """
    
    def __init__(self):
        super().__init__(
            agent_name="code_review_agent",
            agent_role="Code Review Specialist",
            agent_description="Reviews code for quality, security, and performance"
        )
        
        self.prompt_template = self.prompt_manager.get_prompt("code_review_agent")
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        task_id = task.task_id
        code = task.input_data.get("code", "")
        language = task.input_data.get("language", "python")
        
        if not code:
            return {
                "response": "請提供需要審查的程式碼。",
                "error": "No code provided"
            }
        
        # 廣播: 開始審查
        await self.broadcast.agent_status(
            self.agent_name,
            "reviewing",
            task_id,
            {"language": language, "code_length": len(code)}
        )
        
        # 構建審查 Prompt
        review_prompt = f"""
請審查以下 {language} 程式碼:

```{language}
{code}
```

請檢查:
1. 程式碼品質 (可讀性、維護性)
2. 潛在的 Bug
3. 安全性問題
4. 性能問題
5. 最佳實踐建議
"""
        
        # 使用 LLM Service
        response = await self.llm_service.generate(
            prompt=review_prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=0.2,  # 較低的溫度，更客觀的審查
            session_id=task_id
        )
        
        # 廣播: 完成
        await self.broadcast.agent_status(
            self.agent_name,
            "completed",
            task_id,
            {"issues_found": "See response"}
        )
        
        return {
            "response": response.content,
            "language": language,
            "code_length": len(code),
            "agents_involved": [self.agent_name],
            "usage": response.usage.model_dump()
        }


# 對應的 Prompt 配置: config/prompts/code_review_agent.yaml
"""
agent_name: code_review_agent

system_prompt: |
  You are a Code Review Specialist with expertise in multiple programming languages.
  
  Your responsibilities:
  - Review code for quality, security, and performance
  - Identify potential bugs and issues
  - Suggest improvements and best practices
  - Explain issues clearly and constructively
  
  When reviewing code:
  1. Analyze code structure and organization
  2. Check for common security vulnerabilities
  3. Identify performance bottlenecks
  4. Suggest specific improvements
  5. Be constructive and helpful
  
  Output format:
  - Summary: Overall assessment
  - Issues: List of problems found (severity: high/medium/low)
  - Suggestions: Specific recommendations
  - Good practices: What's done well

temperature: 0.2
max_tokens: 3000

metadata:
  description: Reviews code for quality, security, and performance
  role: Code Review Specialist
"""

# ============================================================================
# 總結
# ============================================================================

"""
建立新 Agent 只需 3 步驟:

1. 創建 Prompt 配置文件 (YAML)
2. 創建 Agent 類 (繼承 BaseAgent)
3. 註冊到系統 (main.py)

優點:
✅ 自動 Token 追蹤 (llm_service)
✅ 自動快取 (減少 API 調用)
✅ 統一的廣播機制 (broadcast)
✅ Prompt 外部化 (易於調整)
✅ 支援 RAG (rag_service)
✅ 完整的錯誤處理

估計時間:
- 簡單 Agent: 30 分鐘
- 帶 RAG 的 Agent: 45 分鐘
- 複雜 Agent: 1-2 小時
"""
