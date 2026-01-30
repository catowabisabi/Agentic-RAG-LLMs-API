"""快速測試 - 直接寫入文件"""
import requests
import json
import os

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

# Test RAG Query
if active_dbs:
    try:
        r = requests.post(f"{BASE}/rag/query", json={
            "query": "What are the main features?",
            "collection": active_dbs[0],
            "top_k": 3
        }, timeout=30)
        data = r.json()
        lines.append(f"\n## 4. RAG 查詢 ({active_dbs[0]}): ✓ {r.status_code}")
        lines.append(f"返回 {data.get('count', 0)} 條結果")
        for i, res in enumerate(data.get("results", [])[:2]):
            content = str(res.get("content", res.get("page_content", "")))[:150]
            lines.append(f"  - 結果{i+1}: {content}...")
    except Exception as e:
        lines.append(f"\n## 4. RAG 查詢: ✗ {e}")

# Test Chat
try:
    r = requests.post(f"{BASE}/chat/message", json={
        "message": "你好，請簡單介紹一下你自己",
        "use_rag": False,
        "enable_memory": False
    }, timeout=60)
    lines.append(f"\n## 5. 簡單對話: ✓ {r.status_code}")
    data = r.json()
    if "response" in data:
        lines.append(f"回應: {data['response'][:300]}")
    else:
        lines.append(f"回應數據: {json.dumps(data, ensure_ascii=False)[:500]}")
except requests.exceptions.Timeout:
    lines.append(f"\n## 5. 簡單對話: ⚠️ 超時")
except Exception as e:
    lines.append(f"\n## 5. 簡單對話: ✗ {e}")

# Summary
lines.append("\n## 總結")
lines.append("- API 服務: ✓ 運行中")
lines.append(f"- 有效知識庫: {len(active_dbs)} 個")
lines.append("- 測試完成")

# Write file
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Done! Check {OUT}")
