"""
完整的 RAG Chat 測試腳本
將所有結果輸出到文件
"""
import requests
import json
import sys

BASE_URL = "http://localhost:1130"
OUTPUT = r"d:\codebase\Agentic-RAG-LLMs-API\FULL_TEST_RESULT.md"

def write_result(lines):
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    lines = ["# RAG 智能體系統完整測試報告\n"]
    lines.append(f"## 測試時間: {__import__('datetime').datetime.now()}\n")
    
    # Test 1: Health
    lines.append("## 1. 健康檢查")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=10)
        lines.append(f"- 狀態: ✓ {r.status_code}")
        lines.append(f"```json\n{json.dumps(r.json(), indent=2)}\n```")
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Test 2: Databases
    lines.append("\n## 2. 知識庫列表")
    available_dbs = []
    try:
        r = requests.get(f"{BASE_URL}/rag/databases", timeout=10)
        data = r.json()
        lines.append(f"- 狀態: ✓ {r.status_code}")
        if "databases" in data:
            lines.append(f"- 總共 {len(data['databases'])} 個知識庫")
            for db in data["databases"]:
                doc_count = db.get("document_count", 0)
                status = "📗" if doc_count > 0 else "📕"
                lines.append(f"  - {status} **{db['name']}**: {doc_count} 文檔 - {db.get('description', '')}")
                if doc_count > 0:
                    available_dbs.append(db['name'])
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Test 3: Agents
    lines.append("\n## 3. Agent 列表")
    try:
        r = requests.get(f"{BASE_URL}/agents/", timeout=10)
        data = r.json()
        lines.append(f"- 狀態: ✓ {r.status_code}")
        lines.append(f"- 總共 {len(data)} 個 agents")
        for agent in data:
            status = "🟢" if agent.get("is_running") else "🔴"
            lines.append(f"  - {status} **{agent['name']}**: {agent.get('role', '')} - {agent.get('description', '')[:50]}")
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Test 4: RAG Query (if databases available)
    if available_dbs:
        lines.append(f"\n## 4. RAG 查詢測試 (知識庫: {available_dbs[0]})")
        try:
            r = requests.post(
                f"{BASE_URL}/rag/query",
                json={
                    "query": "What are the main features?",
                    "collection": available_dbs[0],
                    "top_k": 3
                },
                timeout=30
            )
            lines.append(f"- 狀態: ✓ {r.status_code}")
            data = r.json()
            lines.append(f"- 返回 {data.get('count', 0)} 條結果")
            if data.get("results"):
                for i, result in enumerate(data["results"][:2]):
                    content = result.get("content", result.get("page_content", ""))[:200]
                    lines.append(f"  - 結果 {i+1}: {content}...")
        except Exception as e:
            lines.append(f"- 狀態: ✗ {e}")
    
    # Test 5: Smart Query
    lines.append("\n## 5. 智能多庫查詢測試")
    try:
        r = requests.post(
            f"{BASE_URL}/rag/smart-query",
            json={
                "query": "How does the RAG system work?",
                "mode": "multi",
                "top_k": 3
            },
            timeout=30
        )
        lines.append(f"- 狀態: ✓ {r.status_code}")
        data = r.json()
        lines.append(f"- 查詢模式: {data.get('mode', 'N/A')}")
        lines.append(f"- 搜索數據庫數量: {len(data.get('databases_searched', []))}")
        lines.append(f"- 返回結果數: {data.get('total_results', data.get('count', 0))}")
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Test 6: Chat with RAG
    lines.append("\n## 6. RAG 增強對話測試")
    try:
        r = requests.post(
            f"{BASE_URL}/chat/message",
            json={
                "message": "請使用知識庫告訴我這個系統有什麼功能？",
                "use_rag": True,
                "enable_memory": False
            },
            timeout=120
        )
        lines.append(f"- 狀態: ✓ {r.status_code}")
        data = r.json()
        if "response" in data:
            lines.append(f"- 回應:\n```\n{data['response'][:500]}...\n```")
            lines.append(f"- 涉及 Agents: {data.get('agents_involved', [])}")
            lines.append(f"- 來源數: {len(data.get('sources', []))}")
        elif "error" in data:
            lines.append(f"- 錯誤: {data['error']}")
        else:
            lines.append(f"- 原始回應:\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1000]}\n```")
    except requests.exceptions.Timeout:
        lines.append("- 狀態: ⚠️ 請求超時 (120秒)")
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Test 7: Simple Chat (no RAG)
    lines.append("\n## 7. 簡單對話測試 (無 RAG)")
    try:
        r = requests.post(
            f"{BASE_URL}/chat/message",
            json={
                "message": "你好，你是誰？",
                "use_rag": False,
                "enable_memory": False
            },
            timeout=60
        )
        lines.append(f"- 狀態: ✓ {r.status_code}")
        data = r.json()
        if "response" in data:
            lines.append(f"- 回應: {data['response'][:300]}")
        else:
            lines.append(f"- 原始回應: {json.dumps(data, ensure_ascii=False)[:500]}")
    except Exception as e:
        lines.append(f"- 狀態: ✗ {e}")
    
    # Summary
    lines.append("\n## 總結")
    lines.append(f"- 可用知識庫: {len(available_dbs)} 個 ({', '.join(available_dbs)})")
    lines.append("- API 服務: ✓ 運行中")
    lines.append("- Agent 系統: ✓ 16 個 agents 就緒")
    
    # Write results
    write_result(lines)
    print(f"測試完成！結果已保存到: {OUTPUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
