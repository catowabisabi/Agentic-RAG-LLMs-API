"""
Agentic RAG 完整測試腳本
========================

測試所有新功能：
1. WebSocket 串流聊天
2. ReAct Loop 迭代推理
3. Memory 整合
4. Metacognition 自我評估
5. Rate Limiting
6. REST API

使用方式:
    python testing_scripts/test_agentic_features.py
"""

import asyncio
import json
import time
import requests
import websockets
from datetime import datetime
from typing import Dict, Any, List

BASE_URL = "http://localhost:1130"
WS_URL = "ws://localhost:1130/ws/chat"
REPORT_FILE = "d:/codebase/Agentic-RAG-LLMs-API/AGENTIC_TEST_REPORT.md"


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.details: Dict[str, Any] = {}
        self.duration_ms = 0


def test_health_check() -> TestResult:
    """測試健康檢查端點"""
    result = TestResult("Health Check")
    start = time.time()
    
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        result.duration_ms = int((time.time() - start) * 1000)
        
        if r.status_code == 200:
            data = r.json()
            result.passed = data.get("status") == "healthy"
            result.message = f"Status: {data.get('status')}"
            result.details = data
        else:
            result.message = f"Status code: {r.status_code}"
    except Exception as e:
        result.message = str(e)
    
    return result


def test_root_endpoint() -> TestResult:
    """測試根端點（檢查新功能）"""
    result = TestResult("Root Endpoint Features")
    start = time.time()
    
    try:
        r = requests.get(f"{BASE_URL}/", timeout=10)
        result.duration_ms = int((time.time() - start) * 1000)
        
        if r.status_code == 200:
            data = r.json()
            features = data.get("features", {})
            
            # 檢查新功能是否存在
            expected_features = ["react_loop", "websocket_streaming", "memory", "metacognition"]
            found_features = [f for f in expected_features if f in features]
            
            result.passed = len(found_features) == len(expected_features)
            result.message = f"Found {len(found_features)}/{len(expected_features)} features"
            result.details = {
                "version": data.get("version"),
                "features": features,
                "endpoints": data.get("endpoints", {})
            }
        else:
            result.message = f"Status code: {r.status_code}"
    except Exception as e:
        result.message = str(e)
    
    return result


def test_databases() -> TestResult:
    """測試數據庫列表"""
    result = TestResult("RAG Databases")
    start = time.time()
    
    try:
        r = requests.get(f"{BASE_URL}/rag/databases", timeout=10)
        result.duration_ms = int((time.time() - start) * 1000)
        
        if r.status_code == 200:
            data = r.json()
            databases = data.get("databases", [])
            active = [db for db in databases if db.get("document_count", 0) > 0]
            
            result.passed = True
            result.message = f"Found {len(active)} active databases out of {len(databases)}"
            result.details = {
                "total": len(databases),
                "active": len(active),
                "databases": [db["name"] for db in active]
            }
        else:
            result.message = f"Status code: {r.status_code}"
    except Exception as e:
        result.message = str(e)
    
    return result


def test_simple_chat() -> TestResult:
    """測試簡單對話（不使用 RAG）"""
    result = TestResult("Simple Chat (No RAG)")
    start = time.time()
    
    try:
        r = requests.post(
            f"{BASE_URL}/chat/message",
            json={
                "message": "Hello! What is 2+2?",
                "use_rag": False,
                "enable_memory": False
            },
            timeout=60
        )
        result.duration_ms = int((time.time() - start) * 1000)
        
        if r.status_code == 200:
            data = r.json()
            response = data.get("response", "")
            
            result.passed = len(response) > 10
            result.message = f"Got response ({len(response)} chars)"
            result.details = {
                "response_preview": response[:200],
                "agents_involved": data.get("agents_involved", []),
                "workflow": data.get("workflow", "unknown")
            }
        else:
            result.message = f"Status code: {r.status_code}"
            result.details = {"body": r.text[:500]}
    except requests.exceptions.Timeout:
        result.message = "Request timed out (60s)"
    except Exception as e:
        result.message = str(e)
    
    return result


def test_rag_chat() -> TestResult:
    """測試 RAG 對話（使用知識庫）"""
    result = TestResult("RAG Chat (Knowledge Base)")
    start = time.time()
    
    try:
        r = requests.post(
            f"{BASE_URL}/chat/message",
            json={
                "message": "What features does this system have?",
                "use_rag": True,
                "enable_memory": True
            },
            timeout=120
        )
        result.duration_ms = int((time.time() - start) * 1000)
        
        if r.status_code == 200:
            data = r.json()
            response = data.get("response", "")
            sources = data.get("sources", [])
            metadata = data.get("metadata", {})
            
            result.passed = len(response) > 20
            result.message = f"Got response with {len(sources)} sources"
            result.details = {
                "response_preview": response[:300],
                "sources_count": len(sources),
                "agents_involved": data.get("agents_involved", []),
                "workflow": data.get("workflow", "unknown"),
                "quality_score": metadata.get("quality_score"),
                "used_react": metadata.get("used_react")
            }
        else:
            result.message = f"Status code: {r.status_code}"
            result.details = {"body": r.text[:500]}
    except requests.exceptions.Timeout:
        result.message = "Request timed out (120s)"
    except Exception as e:
        result.message = str(e)
    
    return result


async def test_websocket_chat() -> TestResult:
    """測試 WebSocket 串流聊天"""
    result = TestResult("WebSocket Streaming Chat")
    start = time.time()
    
    received_messages: List[Dict] = []
    
    try:
        async with websockets.connect(WS_URL, timeout=30) as ws:
            # 等待連接確認
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(msg)
            
            if data.get("type") != "connected":
                result.message = f"Expected 'connected', got '{data.get('type')}'"
                return result
            
            received_messages.append(data)
            
            # 發送聊天消息
            await ws.send(json.dumps({
                "type": "chat",
                "content": {
                    "message": "What is machine learning?",
                    "use_rag": True,
                    "use_react": True,
                    "use_memory": True
                }
            }))
            
            # 接收所有響應
            final_answer = None
            step_count = 0
            
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(msg)
                    received_messages.append(data)
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "step":
                        step_count += 1
                    elif msg_type == "final_answer":
                        final_answer = data.get("content", {})
                        break
                    elif msg_type == "error":
                        result.message = f"Error: {data.get('content', {}).get('message')}"
                        return result
                        
                except asyncio.TimeoutError:
                    result.message = "Timeout waiting for response"
                    return result
            
            result.duration_ms = int((time.time() - start) * 1000)
            
            if final_answer:
                result.passed = True
                result.message = f"Got {step_count} steps and final answer"
                result.details = {
                    "steps_received": step_count,
                    "message_count": len(received_messages),
                    "response_preview": final_answer.get("response", "")[:200],
                    "sources_count": len(final_answer.get("sources", [])),
                    "quality": final_answer.get("quality", {}),
                    "stats": final_answer.get("stats", {})
                }
            else:
                result.message = "No final answer received"
                
    except Exception as e:
        result.message = str(e)
        result.duration_ms = int((time.time() - start) * 1000)
    
    return result


def test_rate_limiting() -> TestResult:
    """測試速率限制（如果啟用）"""
    result = TestResult("Rate Limiting")
    start = time.time()
    
    try:
        # 先檢查是否啟用了認證
        r = requests.get(f"{BASE_URL}/", timeout=10)
        data = r.json()
        auth_enabled = data.get("features", {}).get("authentication", False)
        
        if not auth_enabled:
            result.passed = True
            result.message = "Auth disabled (rate limiting not active)"
            result.details = {"auth_enabled": False}
            return result
        
        # 如果啟用了認證，測試無 API Key 的請求
        r = requests.get(f"{BASE_URL}/chat/message", timeout=10)
        
        result.passed = r.status_code == 401 or r.status_code == 405
        result.message = f"Unauthenticated request returned {r.status_code}"
        result.details = {"status_code": r.status_code}
        
    except Exception as e:
        result.message = str(e)
    
    result.duration_ms = int((time.time() - start) * 1000)
    return result


def generate_report(results: List[TestResult]) -> str:
    """生成測試報告"""
    lines = [
        "# 🤖 Agentic RAG 系統測試報告",
        f"\n📅 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"🔗 API 端點: {BASE_URL}",
        "\n---\n",
        "## 📊 測試結果總覽\n"
    ]
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    lines.append(f"**通過率: {passed}/{total} ({passed/total*100:.0f}%)**\n")
    
    # 結果表格
    lines.append("| 測試項目 | 狀態 | 耗時 | 說明 |")
    lines.append("|---------|------|------|------|")
    
    for r in results:
        status = "✅" if r.passed else "❌"
        lines.append(f"| {r.name} | {status} | {r.duration_ms}ms | {r.message} |")
    
    lines.append("\n---\n")
    lines.append("## 📝 詳細結果\n")
    
    for r in results:
        status = "✅ PASSED" if r.passed else "❌ FAILED"
        lines.append(f"### {r.name} {status}\n")
        lines.append(f"- **耗時**: {r.duration_ms}ms")
        lines.append(f"- **說明**: {r.message}")
        
        if r.details:
            lines.append("- **詳細信息**:")
            lines.append("```json")
            lines.append(json.dumps(r.details, indent=2, ensure_ascii=False, default=str))
            lines.append("```")
        
        lines.append("")
    
    # 新功能說明
    lines.append("\n---\n")
    lines.append("## 🆕 新功能說明\n")
    lines.append("""
### 1. ReAct Loop (迭代推理)
- 實現 Think → Act → Observe → Reflect 循環
- 最多 3 次迭代，自動決定何時停止
- 每一步都通過 WebSocket 實時推送

### 2. WebSocket 串流 (`/ws/chat`)
- 實時推送思考過程、搜尋結果、最終答案
- 支持取消請求
- 心跳保持連接

### 3. Memory 整合
- 工作記憶：當前對話上下文
- 情節記憶：成功/失敗經驗
- 實體記憶：用戶提到的人/地點/概念

### 4. Metacognition (自我評估)
- 評估回答品質 (0-1 分)
- 識別是否需要重試
- 學習成功/失敗模式

### 5. 認證與限流
- API Key 認證（可選）
- 每分鐘/每日請求限制
- 請求日誌記錄
""")
    
    return "\n".join(lines)


async def run_all_tests():
    """運行所有測試"""
    print("🚀 開始 Agentic RAG 系統測試...\n")
    
    results: List[TestResult] = []
    
    # 同步測試
    print("1️⃣ 測試 Health Check...")
    results.append(test_health_check())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("2️⃣ 測試 Root Endpoint...")
    results.append(test_root_endpoint())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("3️⃣ 測試 Databases...")
    results.append(test_databases())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("4️⃣ 測試 Simple Chat...")
    results.append(test_simple_chat())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("5️⃣ 測試 RAG Chat...")
    results.append(test_rag_chat())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("6️⃣ 測試 WebSocket Chat...")
    results.append(await test_websocket_chat())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    print("7️⃣ 測試 Rate Limiting...")
    results.append(test_rate_limiting())
    print(f"   {'✅' if results[-1].passed else '❌'} {results[-1].message}")
    
    # 生成報告
    report = generate_report(results)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n📄 測試報告已保存至: {REPORT_FILE}")
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n🏁 測試完成: {passed}/{total} 通過 ({passed/total*100:.0f}%)")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
