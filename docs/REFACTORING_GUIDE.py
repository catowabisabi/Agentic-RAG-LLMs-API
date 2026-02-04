"""
示例：如何使用新的 Service Layer 重構 Agent

這個文件展示了如何將現有的 Agent 改造為使用新的 Service Layer。

重構前後對比：
==============

【重構前】 - 每個 Agent 都有自己的 LLM 初始化
--------------------------------------------
class ThinkingAgent(BaseAgent):
    def __init__(self):
        super().__init__(...)
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        self.system_prompt = "You are a thinking agent..."  # 硬編碼
    
    async def process_task(self, task):
        prompt = f"{self.system_prompt}\n\n{task.description}"
        result = await self.llm.ainvoke(prompt)
        return {"response": result.content}


【重構後】 - 使用 Service Layer
--------------------------------------------
class ThinkingAgent(BaseAgent):
    def __init__(self):
        super().__init__(...)
        # llm_service, rag_service, broadcast, prompt_manager
        # 已經通過 BaseAgent 自動注入了！
        
        # 從 Prompt Manager 加載 System Prompt
        self.prompt_template = self.prompt_manager.get_prompt("thinking_agent")
    
    async def process_task(self, task):
        # 使用 LLM Service 生成響應（自動追蹤 Token）
        response = await self.llm_service.generate(
            prompt=task.description,
            system_message=self.prompt_template.system_prompt,
            temperature=self.prompt_template.temperature,
            session_id=task.task_id
        )
        
        # 使用 Broadcast Service 發送狀態
        await self.broadcast.agent_status(
            self.agent_name,
            "completed",
            task.task_id,
            {"response_preview": response.content[:100]}
        )
        
        return {"response": response.content}


重構步驟：
==========

Step 1: 移除舊的 LLM 初始化
---------------------------
❌ 刪除：
    self.config = Config()
    self.llm = ChatOpenAI(...)

✅ 改為：
    # BaseAgent 已經自動注入了 self.llm_service


Step 2: 移除硬編碼的 System Prompt
----------------------------------
❌ 刪除：
    self.system_prompt = "You are..."

✅ 改為：
    self.prompt_template = self.prompt_manager.get_prompt("agent_name")


Step 3: 替換 LLM 調用
---------------------
❌ 舊代碼：
    result = await self.llm.ainvoke(messages)
    content = result.content

✅ 新代碼：
    response = await self.llm_service.generate(
        prompt="...",
        temperature=0.7,
        session_id=task.task_id
    )
    content = response.content
    # 自動追蹤了 Token 使用！


Step 4: 替換 RAG 調用
---------------------
❌ 舊代碼：
    retriever = DocumentRetriever(collection_name="default")
    results = retriever.retrieve(query, top_k=5)

✅ 新代碼：
    result = await self.rag_service.query(
        query=query,
        strategy=RAGStrategy.AUTO,
        top_k=5
    )
    context = result.context
    sources = result.sources


Step 5: 替換 WebSocket 廣播
---------------------------
❌ 舊代碼：
    await self.ws_manager.broadcast_agent_activity({
        "type": "agent_status",
        "agent": self.agent_name,
        "content": {...},
        "timestamp": datetime.now().isoformat()
    })

✅ 新代碼：
    await self.broadcast.agent_status(
        self.agent_name,
        "working",
        task.task_id,
        {...}
    )


完整重構示例：
==============
"""

from typing import Dict, Any
from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment
from services.rag_service import RAGStrategy


class RefactoredThinkingAgent(BaseAgent):
    """
    重構後的 Thinking Agent
    
    使用新的 Service Layer：
    - llm_service: 統一的 LLM 調用
    - rag_service: 統一的 RAG 查詢
    - broadcast: 統一的 WebSocket 廣播
    - prompt_manager: Prompt 模板管理
    """
    
    def __init__(self):
        super().__init__(
            agent_name="thinking_agent_refactored",
            agent_role="Thinking Specialist",
            agent_description="Deep reasoning with new Service Layer"
        )
        
        # 加載 Prompt 模板
        self.prompt_template = self.prompt_manager.get_prompt("thinking_agent")
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """處理任務"""
        query = task.input_data.get("query", task.description)
        use_rag = task.input_data.get("use_rag", False)
        
        # Step 1: 廣播開始狀態
        await self.broadcast.agent_status(
            self.agent_name,
            "started",
            task.task_id,
            {"query": query[:100]}
        )
        
        # Step 2: 如果需要 RAG，先查詢知識庫
        context = ""
        sources = []
        
        if use_rag:
            await self.broadcast.agent_status(
                self.agent_name,
                "searching",
                task.task_id,
                {"message": "Searching knowledge bases..."}
            )
            
            rag_result = await self.rag_service.query(
                query=query,
                strategy=RAGStrategy.AUTO,
                top_k=5,
                threshold=0.3
            )
            
            context = rag_result.context
            sources = [s.model_dump() for s in rag_result.sources]
            
            # 廣播找到的來源
            await self.broadcast.rag_sources(sources, task.task_id)
        
        # Step 3: 使用 LLM 生成響應
        await self.broadcast.agent_status(
            self.agent_name,
            "thinking",
            task.task_id,
            {"message": "Analyzing and reasoning..."}
        )
        
        # 構建完整的 Prompt
        full_prompt = query
        if context:
            full_prompt = f"Context:\n{context}\n\nQuestion: {query}"
        
        # 調用 LLM Service
        response = await self.llm_service.generate(
            prompt=full_prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=self.prompt_template.temperature,
            max_tokens=self.prompt_template.max_tokens,
            session_id=task.task_id
        )
        
        # Step 4: 廣播完成狀態
        await self.broadcast.agent_status(
            self.agent_name,
            "completed",
            task.task_id,
            {
                "response_preview": response.content[:200],
                "tokens_used": response.usage.total_tokens,
                "cost": response.usage.cost
            }
        )
        
        # Step 5: 返回結果
        return {
            "response": response.content,
            "sources": sources,
            "usage": response.usage.model_dump(),
            "agents_involved": [self.agent_name]
        }


# 使用 Token 統計
async def example_get_token_usage():
    """示例：如何獲取 Token 使用統計"""
    from services.llm_service import get_llm_service
    
    llm_service = get_llm_service()
    
    # 獲取總體統計
    total_stats = llm_service.get_usage_stats()
    print(f"Total tokens used: {total_stats['total']['total_tokens']}")
    print(f"Total cost: ${total_stats['total']['cost']:.4f}")
    
    # 獲取特定 Session 的統計
    session_stats = llm_service.get_usage_stats(session_id="task-123")
    print(f"Session tokens: {session_stats['session']['total_tokens']}")


# 使用 RAG 快取
async def example_rag_with_cache():
    """示例：使用 RAG 快取"""
    from services.rag_service import get_rag_service
    
    rag_service = get_rag_service()
    
    # 第一次查詢（會實際查詢數據庫）
    result1 = await rag_service.query("What is RAG?", use_cache=True)
    print(f"Cached: {result1.cached}")  # False
    
    # 第二次相同查詢（會從快取返回）
    result2 = await rag_service.query("What is RAG?", use_cache=True)
    print(f"Cached: {result2.cached}")  # True
    
    # 清空快取
    rag_service.clear_cache()


# 使用 Prompt 模板
async def example_prompt_templates():
    """示例：使用 Prompt 模板"""
    from services.prompt_manager import get_prompt_manager
    
    pm = get_prompt_manager()
    
    # 獲取模板
    template = pm.get_prompt("casual_chat_agent")
    
    # 渲染模板（替換變量）
    rendered = pm.render(template, {
        "user_name": "Alice",
        "topic": "Python programming"
    })
    
    print(rendered)
    
    # 列出所有可用的模板
    all_prompts = pm.list_prompts()
    print(f"Available prompts: {all_prompts}")


"""
重構清單：
=========

需要重構的 Agent：
✅ casual_chat_agent.py
✅ rag_agent.py
✅ thinking_agent.py
✅ manager_agent.py
✅ planning_agent.py
✅ memory_agent.py
✅ validation_agent.py
✅ calculation_agent.py
✅ translate_agent.py
✅ summarize_agent.py
✅ data_agent.py
✅ tool_agent.py

重構優先級：
1. 核心 Agent (Manager, RAG, Thinking) - 高
2. 輔助 Agent (Calculation, Translate, etc.) - 中
3. 特殊 Agent (Memory, Validation) - 低

每個 Agent 大約需要：15-30 分鐘重構時間
"""
