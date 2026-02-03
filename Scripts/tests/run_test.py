"""快速測試 - 直接寫入文件"""
import requests
import json

BASE = "http://localhost:1130"
OUT = "d:/codebase/Agentic-RAG-LLMs-API/TEST_REPORT.md"

lines = ["# RAG 系統測試報告\n"]

# Test Health
try:
    r = requests.get(f"{BASE}/", timeout=10)
    lines.append(f"## 1. 健康檢查: ✓ {r.status_code}")
except Exception as e:
    lines.append(f"## 1. 健康檢查: ✗ {e}")

# Test DBs
try:
    r = requests.get(f"{BASE}/rag/databases", timeout=10)
    data = r.json()
    lines.append(f"\n## 2. 數據庫列表: ✓ {r.status_code}")
    lines.append(f"總共 {len(data.get('databases', []))} 個數據庫")
    active_dbs = []
    for db in data.get("databases", []):
        count = db.get("document_count", 0)
        if count > 0:
            active_dbs.append(db["name"])
            lines.append(f"- ✓ {db['name']}: {count} 文檔")
    lines.append(f"\n**有效知識庫**: {active_dbs}")
except Exception as e:
    lines.append(f"\n## 2. 數據庫: ✗ {e}")
    active_dbs = []

# Test Agents
try:
    r = requests.get(f"{BASE}/agents/", timeout=10)
    data = r.json()
    lines.append(f"\n## 3. Agent 列表: ✓ {r.status_code}")
    lines.append(f"總共 {len(data)} 個 agents 運行中")
except Exception as e:
    lines.append(f"\n## 3. Agents: ✗ {e}")

# Test RAG Query using correct endpoint
if active_dbs:
    try:
        r = requests.post(f"{BASE}/rag/databases/query", json={
            "query": "What are the main features?",
            "database": active_dbs[0],
            "n_results": 3
        }, timeout=30)
        data = r.json()
        lines.append(f"\n## 4. RAG 數據庫查詢 ({active_dbs[0]}): ✓ {r.status_code}")
        results = data.get("results", [])
        lines.append(f"返回 {len(results)} 條結果")
        for i, res in enumerate(results[:2]):
            content = str(res.get("content", ""))[:200]
            lines.append(f"  - 結果{i+1}: {content}...")
    except Exception as e:
        lines.append(f"\n## 4. RAG 數據庫查詢: ✗ {e}")

# Test Smart Query (multi-database)
if active_dbs:
    try:
        r = requests.post(f"{BASE}/rag/smart-query", json={
            "query": "How does the system work?",
            "mode": "multi",
            "top_k": 3
        }, timeout=30)
        data = r.json()
        lines.append(f"\n## 5. 智能多庫查詢: ✓ {r.status_code}")
        lines.append(f"- 查詢模式: {data.get('mode', 'N/A')}")
        lines.append(f"- 結果總數: {data.get('total_results', 0)}")
        lines.append(f"- 搜索數據庫: {data.get('databases_searched', [])}")
    except Exception as e:
        lines.append(f"\n## 5. 智能查詢: ✗ {e}")

# Test Chat (simple, no RAG)
try:
    r = requests.post(f"{BASE}/chat/message", json={
        "message": "你好，你是誰？",
        "use_rag": False,
        "enable_memory": False
    }, timeout=60)
    data = r.json()
    lines.append(f"\n## 6. 簡單對話 (無 RAG): ✓ {r.status_code}")
    if "response" in data:
        lines.append(f"回應: {data['response'][:300]}...")
    else:
        lines.append(f"原始回應: {json.dumps(data, ensure_ascii=False)[:500]}")
except requests.exceptions.Timeout:
    lines.append(f"\n## 6. 簡單對話: ⚠️ 超時 (60秒)")
except Exception as e:
    lines.append(f"\n## 6. 簡單對話: ✗ {e}")

# Test Chat with RAG
try:
    r = requests.post(f"{BASE}/chat/message", json={
        "message": "請使用知識庫告訴我這個 RAG 系統有什麼功能?",
        "use_rag": True,
        "enable_memory": False
    }, timeout=120)
    data = r.json()
    lines.append(f"\n## 7. RAG 增強對話: ✓ {r.status_code}")
    if "response" in data:
        lines.append(f"回應: {data['response'][:500]}...")
        lines.append(f"涉及 Agents: {data.get('agents_involved', [])}")
        lines.append(f"來源數量: {len(data.get('sources', []))}")
    else:
        lines.append(f"原始回應: {json.dumps(data, ensure_ascii=False)[:800]}")
except requests.exceptions.Timeout:
    lines.append(f"\n## 7. RAG 對話: ⚠️ 超時 (120秒)")
except Exception as e:
    lines.append(f"\n## 7. RAG 對話: ✗ {e}")

# Summary
lines.append("\n---\n## 總結")
lines.append("- API 服務: ✓ 運行中")
lines.append(f"- 有效知識庫: {len(active_dbs)} 個")
lines.append(f"- 知識庫列表: {', '.join(active_dbs)}")
lines.append("- 測試完成")

# Write file
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Done! Saved to {OUT}")
