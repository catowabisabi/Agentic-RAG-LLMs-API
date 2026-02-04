"""
測試重構後的 Casual Chat Agent

驗證 Service Layer 是否正常工作
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.core.casual_chat_agent import get_casual_chat_agent
from agents.shared_services.message_protocol import TaskAssignment
from services.llm_service import get_llm_service


async def test_casual_chat():
    """測試 Casual Chat Agent"""
    
    print("=" * 60)
    print("測試重構後的 Casual Chat Agent")
    print("=" * 60)
    
    # 獲取 Agent
    agent = get_casual_chat_agent()
    
    # 測試用例
    test_cases = [
        "Hello!",
        "你好",
        "你有咩功能？",
        "What can you do?"
    ]
    
    for i, message in enumerate(test_cases, 1):
        print(f"\n[Test {i}] User: {message}")
        print("-" * 60)
        
        # 創建任務
        task = TaskAssignment(
            task_id=f"test-{i}",
            task_type="casual_chat",
            description=message,
            input_data={
                "query": message,
                "chat_history": []
            }
        )
        
        # 執行任務
        result = await agent.process_task(task)
        
        # 顯示結果
        print(f"Response: {result.get('response', 'No response')}")
        
        if 'usage' in result:
            usage = result['usage']
            print(f"Tokens: {usage.get('total_tokens', 0)} (cached: {result.get('cached', False)})")
            print(f"Cost: ${usage.get('cost', 0):.6f}")
        
        if 'duration_ms' in result:
            print(f"Duration: {result['duration_ms']}ms")
    
    # 顯示總體 Token 使用統計
    print("\n" + "=" * 60)
    print("總體 Token 使用統計")
    print("=" * 60)
    
    llm_service = get_llm_service()
    stats = llm_service.get_usage_stats()
    
    total = stats.get('total', {})
    print(f"Total tokens: {total.get('total_tokens', 0)}")
    print(f"Total cost: ${total.get('cost', 0):.6f}")
    
    # 按模型統計
    print("\n按模型統計:")
    for model, usage in stats.get('by_model', {}).items():
        print(f"  {model}: {usage.get('total_tokens', 0)} tokens (${usage.get('cost', 0):.6f})")


if __name__ == "__main__":
    asyncio.run(test_casual_chat())
