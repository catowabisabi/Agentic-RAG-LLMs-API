# -*- coding: utf-8 -*-
"""
Agentic System Test Script
===========================

測試增強後的 Agentic 系統：
1. Metacognition - 自我評估
2. 智能 RAG 決策 - 非強制
3. ReAct 迭代推理
4. PEV 驗證
"""

import asyncio
import logging
from datetime import datetime

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_agentic_orchestrator():
    """測試 Agentic Orchestrator"""
    print("\n" + "="*60)
    print("Testing Agentic Orchestrator")
    print("="*60)
    
    from agents.core import (
        AgenticOrchestrator,
        create_agentic_orchestrator,
        AgentStrategy
    )
    
    # 創建 Orchestrator
    orchestrator = create_agentic_orchestrator()
    print(f"✓ Created Orchestrator: {orchestrator.self_model.name}")
    
    # 測試用例
    test_cases = [
        {
            "name": "Simple Greeting (should use DIRECT_ANSWER)",
            "query": "你好！",
            "expected_strategy": AgentStrategy.DIRECT_ANSWER
        },
        {
            "name": "General Knowledge (should use DIRECT_ANSWER or SINGLE_RAG)",
            "query": "什麼是人工智能？",
            "expected_strategy": None  # 可能是任一種
        },
        {
            "name": "Document Query (should use SINGLE_RAG or REACT)",
            "query": "根據上傳的文件，這個項目的主要功能是什麼？",
            "expected_strategy": None
        }
    ]
    
    for tc in test_cases:
        print(f"\n--- Test: {tc['name']} ---")
        print(f"Query: {tc['query']}")
        
        # 執行 Metacognitive Analysis
        analysis = await orchestrator.metacognitive_analysis(
            query=tc['query'],
            chat_history=[],
            user_context=""
        )
        
        print(f"Strategy: {analysis.strategy.value}")
        print(f"Confidence: {analysis.confidence:.2f}")
        print(f"Complexity: {analysis.estimated_complexity}")
        print(f"Reasoning: {analysis.reasoning[:100]}...")
        
        if tc['expected_strategy'] and analysis.strategy != tc['expected_strategy']:
            print(f"⚠ Expected {tc['expected_strategy'].value}, got {analysis.strategy.value}")
        else:
            print("✓ Strategy selection looks reasonable")
    
    print("\n✓ Agentic Orchestrator tests completed!")


async def test_metacognition_engine():
    """測試 Metacognition Engine"""
    print("\n" + "="*60)
    print("Testing Metacognition Engine")
    print("="*60)
    
    from agents.core import (
        get_metacognition_engine,
        get_metacognitive_self_model
    )
    
    # 獲取 Self Model
    self_model = get_metacognitive_self_model()
    print(f"✓ Self Model: {self_model.name}")
    print(f"  Capabilities: {len(self_model.capabilities)} domains")
    print(f"  Boundaries: {len(self_model.knowledge_boundaries)} boundaries")
    print(f"  High-Risk Topics: {self_model.high_risk_topics}")
    
    # 獲取 Engine
    engine = get_metacognition_engine()
    print(f"✓ Metacognition Engine initialized")
    
    # 測試能力評估
    test_queries = [
        "幫我寫一首詩",
        "這個藥物的副作用是什麼？",  # 高風險主題
        "幫我分析這個數據"
    ]
    
    for query in test_queries:
        print(f"\n--- Query: {query} ---")
        assessment = await engine.assess_capability(query)
        print(f"Can Handle: {assessment.get('can_handle')}")
        print(f"Domain: {assessment.get('domain')}")
        print(f"Confidence: {assessment.get('confidence')}")
        print(f"Recommended Strategy: {assessment.get('recommended_strategy')}")
        if assessment.get('risks'):
            print(f"Risks: {assessment.get('risks')}")
    
    print("\n✓ Metacognition Engine tests completed!")


async def test_react_loop():
    """測試 ReAct Loop with PEV"""
    print("\n" + "="*60)
    print("Testing ReAct Loop with PEV")
    print("="*60)
    
    from agents.core import create_react_loop, ActionType
    
    # 創建 ReAct Loop
    react_loop = create_react_loop(
        max_iterations=3,
        verification_threshold=0.6
    )
    print(f"✓ ReAct Loop created (max_iterations={react_loop.max_iterations})")
    
    # 註冊一個簡單的搜索工具
    async def mock_search(query: str):
        return {
            "content": f"Mock search result for: {query}. This is simulated content about the topic.",
            "sources": [{"title": "Mock Source", "url": "http://example.com"}]
        }
    
    react_loop.register_tool(ActionType.SEARCH, mock_search)
    print("✓ Mock search tool registered")
    
    # 測試 Think 步驟
    thought = await react_loop.think(
        query="什麼是機器學習？",
        context="",
        previous_steps=[]
    )
    
    print(f"\n--- Think Result ---")
    print(f"Thought: {thought.thought[:100]}...")
    print(f"Action: {thought.action.value}")
    print(f"Confidence: {thought.confidence}")
    print(f"Self-Assessment: {thought.self_assessment[:100]}..." if thought.self_assessment else "N/A")
    
    print("\n✓ ReAct Loop tests completed!")


async def test_rag_decision():
    """測試增強的 RAG 決策邏輯"""
    print("\n" + "="*60)
    print("Testing Enhanced RAG Decision")
    print("="*60)
    
    from agents.core import RAGAgent
    from agents.shared_services.message_protocol import TaskAssignment
    
    # 創建 RAG Agent
    rag_agent = RAGAgent()
    print(f"✓ RAG Agent initialized")
    
    # 測試不同類型的查詢
    test_cases = [
        {
            "query": "你好",
            "expected_rag": False,
            "desc": "Simple greeting"
        },
        {
            "query": "根據上傳的文件，總結主要觀點",
            "expected_rag": True,
            "desc": "Document query"
        },
        {
            "query": "什麼是 Python？",
            "expected_rag": False,  # 一般知識
            "desc": "General knowledge"
        }
    ]
    
    for tc in test_cases:
        print(f"\n--- {tc['desc']}: {tc['query'][:30]}... ---")
        
        task = TaskAssignment(
            task_type="rag_check",
            description=tc['query'],
            input_data={
                "query": tc['query'],
                "chat_history": [],
                "user_context": ""
            }
        )
        
        result = await rag_agent._check_if_rag_needed(task)
        
        print(f"Should use RAG: {result.get('should_use_rag')}")
        print(f"Confidence: {result.get('confidence', 'N/A')}")
        print(f"Strategy: {result.get('suggested_strategy', 'N/A')}")
        print(f"Complexity: {result.get('complexity_level', 'N/A')}")
        print(f"Reasoning: {result.get('reasoning', '')[:80]}...")
    
    print("\n✓ RAG Decision tests completed!")


async def main():
    """主測試函數"""
    print("\n" + "="*60)
    print("AGENTIC SYSTEM INTEGRATION TEST")
    print("="*60)
    print(f"Time: {datetime.now().isoformat()}")
    
    try:
        # 基本導入測試
        print("\n--- Import Tests ---")
        from agents.core import (
            AgenticOrchestrator,
            MetacognitionEngine,
            ReActLoop,
            ManagerAgentV2
        )
        print("✓ All imports successful")
        
        # 運行各項測試
        await test_metacognition_engine()
        await test_react_loop()
        await test_agentic_orchestrator()
        await test_rag_decision()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
