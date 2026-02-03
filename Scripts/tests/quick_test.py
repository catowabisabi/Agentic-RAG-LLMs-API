"""快速 API 測試 - 只測試基礎端點"""
import requests
import json
import sys

BASE = "http://localhost:1130"
OUT = r"d:\codebase\Agentic-RAG-LLMs-API\API_TEST_RESULT.md"

def main():
    lines = ["# API 測試結果\n"]
    
    # 1. 根端點
    try:
        r = requests.get(f"{BASE}/", timeout=10)
        lines.append(f"## 1. 健康檢查: ✓ ({r.status_code})")
        lines.append(f"```json\n{json.dumps(r.json(), indent=2)}\n```\n")
    except Exception as e:
        lines.append(f"## 1. 健康檢查: ✗ ({e})\n")
    
    # 2. Collections
    try:
        r = requests.get(f"{BASE}/rag/collections", timeout=10)
        lines.append(f"## 2. RAG Collections: ✓ ({r.status_code})")
        lines.append(f"```json\n{json.dumps(r.json(), indent=2)}\n```\n")
    except Exception as e:
        lines.append(f"## 2. RAG Collections: ✗ ({e})\n")
    
    # 3. Databases
    try:
        r = requests.get(f"{BASE}/rag/databases", timeout=10)
        data = r.json()
        lines.append(f"## 3. 向量數據庫: ✓ ({r.status_code})")
        lines.append(f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n")
        
        # 列出有文檔的數據庫
        if "databases" in data:
            active = [d["name"] for d in data["databases"] if d.get("document_count", 0) > 0]
            lines.append(f"**有文檔的數據庫**: {active}\n")
    except Exception as e:
        lines.append(f"## 3. 向量數據庫: ✗ ({e})\n")
    
    # 4. Agents
    try:
        r = requests.get(f"{BASE}/agents/", timeout=10)
        data = r.json()
        lines.append(f"## 4. Agent 列表: ✓ ({r.status_code})")
        if "agents" in data:
            lines.append(f"**總共 {len(data['agents'])} 個 agents:**")
            for a in data["agents"]:
                lines.append(f"- {a.get('name', 'unknown')}: {a.get('role', '')}")
        lines.append("")
    except Exception as e:
        lines.append(f"## 4. Agent 列表: ✗ ({e})\n")
    
    # 寫入文件
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"結果已寫入: {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
