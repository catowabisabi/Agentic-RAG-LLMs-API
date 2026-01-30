"""
RAG API 自動測試腳本
測試 RAG 智能體系統的完整功能
"""

import requests
import json
import time
from typing import Dict, Any, List

BASE_URL = "http://localhost:1130"


def test_endpoint(name: str, method: str, url: str, data: Dict = None) -> Dict[str, Any]:
    """測試一個 endpoint"""
    print(f"\n{'='*60}")
    print(f"測試: {name}")
    print(f"端點: {method} {url}")
    print("-"*60)
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=60)
        else:
            return {"success": False, "error": f"Unknown method: {method}"}
        
        print(f"狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"結果: {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}")
            return {"success": True, "data": result}
        else:
            print(f"錯誤: {response.text}")
            return {"success": False, "error": response.text}
            
    except requests.exceptions.Timeout:
        print("請求超時")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print(f"異常: {str(e)}")
        return {"success": False, "error": str(e)}


def main():
    print("="*60)
    print("RAG 智能體系統自動化測試")
    print("="*60)
    
    results = []
    
    # 1. 健康檢查
    result = test_endpoint(
        "健康檢查",
        "GET",
        f"{BASE_URL}/"
    )
    results.append(("健康檢查", result["success"]))
    
    # 2. 列出 RAG Collections
    result = test_endpoint(
        "RAG Collections 列表",
        "GET",
        f"{BASE_URL}/rag/collections"
    )
    results.append(("RAG Collections", result["success"]))
    
    # 3. 列出數據庫
    result = test_endpoint(
        "向量數據庫列表",
        "GET",
        f"{BASE_URL}/rag/databases"
    )
    results.append(("向量數據庫", result["success"]))
    
    available_dbs = []
    if result["success"] and "databases" in result.get("data", {}):
        available_dbs = [db["name"] for db in result["data"]["databases"] if db.get("document_count", 0) > 0]
        print(f"\n可用知識庫: {available_dbs}")
    
    # 4. 測試 Agent 列表
    result = test_endpoint(
        "Agent 列表",
        "GET",
        f"{BASE_URL}/agents"
    )
    results.append(("Agent列表", result["success"]))
    
    # 5. 測試簡單 Chat (不使用 RAG)
    result = test_endpoint(
        "簡單聊天 (無RAG)",
        "POST",
        f"{BASE_URL}/chat",
        {
            "message": "你好，請簡單介紹一下你自己",
            "use_rag": False,
            "enable_memory": False
        }
    )
    results.append(("簡單聊天", result["success"]))
    
    # 6. 測試 RAG 查詢 (如果有知識庫)
    if available_dbs:
        result = test_endpoint(
            "RAG 查詢",
            "POST",
            f"{BASE_URL}/rag/query",
            {
                "query": "What is the main topic of the documents?",
                "collection": available_dbs[0],
                "top_k": 3
            }
        )
        results.append(("RAG查詢", result["success"]))
    
    # 7. 測試帶 RAG 的聊天
    result = test_endpoint(
        "RAG 增強聊天",
        "POST",
        f"{BASE_URL}/chat",
        {
            "message": "請使用知識庫回答：這個系統有什麼功能？",
            "use_rag": True,
            "enable_memory": False
        }
    )
    results.append(("RAG聊天", result["success"]))
    
    # 8. 測試智能路由
    result = test_endpoint(
        "智能 RAG 路由",
        "POST",
        f"{BASE_URL}/rag/smart-query",
        {
            "query": "Explain the main features",
            "mode": "auto",
            "top_k": 5
        }
    )
    results.append(("智能路由", result["success"]))
    
    # 打印摘要
    print("\n" + "="*60)
    print("測試結果摘要")
    print("="*60)
    
    passed = 0
    failed = 0
    for name, success in results:
        status = "✓ 通過" if success else "✗ 失敗"
        print(f"  {name}: {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-"*60)
    print(f"總計: {len(results)} 測試 | 通過: {passed} | 失敗: {failed}")
    print("="*60)
    
    return passed, failed


if __name__ == "__main__":
    main()
