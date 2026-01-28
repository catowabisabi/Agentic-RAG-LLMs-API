# -*- coding: utf-8 -*-
"""
=============================================================================
遺留代碼模組 (Legacy Module)
=============================================================================

結構說明：
-----------
此目錄包含系統早期版本的遺留代碼，目前僅供參考或向後兼容使用。
新開發應使用 agents/core/ 中的現代化 BaseAgent 架構。

包含文件：
-----------
- rag_agent.py     : 舊版 RAG Agent（使用 LangGraph StateGraph）
                     現已被 agents/core/rag_agent.py 取代
- nodes.py         : 舊版節點定義（用於 LangGraph 圖）
                     現已整合到新的 Agent 架構中

遷移說明：
-----------
舊版 RAG Agent 使用 LangGraph 的 StateGraph 架構：
    - create_rag_agent() -> 返回編譯後的圖
    - agent.invoke({"query": ..., "chat_history": []})

新版 RAG Agent 使用 BaseAgent 架構：
    - RAGAgent() -> 實例化 Agent
    - await agent.process_task(TaskAssignment(...))

注意：
-----------
1. main.py 的互動模式仍使用此遺留模組
2. 未來版本可能移除此目錄
3. 新功能開發請勿依賴此模組

作者：Agentic RAG Team
版本：1.0 (Legacy)
=============================================================================
"""

from .rag_agent import RAGAgent, create_rag_agent

__all__ = ['RAGAgent', 'create_rag_agent']
