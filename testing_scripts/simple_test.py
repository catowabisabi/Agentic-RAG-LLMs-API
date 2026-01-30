"""
簡化版測試腳本 - 結果直接寫入文件
"""
import requests
import json

OUTPUT_FILE = r"d:\codebase\Agentic-RAG-LLMs-API\RESULT.md"
BASE_URL = "http://localhost:1130"

results = []

def log(msg):
    results.append(msg)
    print(msg)

def test(name, method, url, data=None):
    log(f"\n## {name}")
    log(f"- 端點: {method} {url}")
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        else:
            r = requests.post(url, json=data, timeout=60)
        
        log(f"- 狀態碼: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            log(f"- 結果: ```json\n{json.dumps(result, ensure_ascii=False, indent=2)[:1500]}\n```")
            return True, result
        else:
            log(f"- 錯誤: {r.text[:500]}")
            return False, None
    except Exception as e:
        log(f"- 異常: {e}")
        return False, None

# 開始測試
log("# RAG API 自動測試結果\n")

test("健康檢查", "GET", f"{BASE_URL}/")
test("RAG Collections", "GET", f"{BASE_URL}/rag/collections")
ok, db_data = test("向量數據庫列表", "GET", f"{BASE_URL}/rag/databases")
test("Agent 列表", "GET", f"{BASE_URL}/agents")

# 找到有文檔的數據庫
available_dbs = []
if ok and db_data and "databases" in db_data:
    available_dbs = [db["name"] for db in db_data["databases"] if db.get("document_count", 0) > 0]
    log(f"\n**可用知識庫**: {available_dbs}")

# 測試 Chat
test("簡單對話", "POST", f"{BASE_URL}/chat", {
    "message": "你好，你是誰？",
    "use_rag": False,
    "enable_memory": False
})

if available_dbs:
    test("RAG 查詢", "POST", f"{BASE_URL}/rag/query", {
        "query": "main topic",
        "collection": available_dbs[0],
        "top_k": 3
    })

test("RAG 增強對話", "POST", f"{BASE_URL}/chat", {
    "message": "請搜索知識庫，告訴我這個系統有什麼功能?",
    "use_rag": True,
    "enable_memory": False
})

# 寫入文件
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print(f"\n\n測試完成！結果已保存到 {OUTPUT_FILE}")
