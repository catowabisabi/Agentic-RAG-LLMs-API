"""
WebSocket Chat CLI 測試工具
===========================

互動式 WebSocket 聊天測試，顯示所有思考步驟。

使用方式:
    python testing_scripts/test_ws_chat.py

功能:
- 連接到 /ws/chat 端點
- 發送聊天消息
- 實時顯示思考過程
- 顯示最終答案和來源
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("請先安裝 websockets: pip install websockets")
    sys.exit(1)

WS_URL = "ws://localhost:1130/ws/chat"


def format_step(data: dict) -> str:
    """格式化步驟輸出"""
    msg_type = data.get("type", "unknown")
    content = data.get("content", {})
    
    if msg_type == "connected":
        return f"🔗 已連接: {content.get('client_id')}"
    
    elif msg_type == "thinking":
        return f"🤔 思考中: {content.get('message', '')}"
    
    elif msg_type == "searching":
        return f"🔍 搜尋中: {content.get('message', content.get('query', ''))}"
    
    elif msg_type == "step":
        step_num = content.get("step", "?")
        thought = content.get("thought", "")[:100]
        action = content.get("action", "")
        return f"📝 步驟 {step_num}: {action}\n   💭 {thought}..."
    
    elif msg_type == "sources":
        sources = content.get("sources", [])
        if sources:
            source_list = "\n".join([f"   - {s.get('title', 'Unknown')}" for s in sources[:3]])
            return f"📚 找到 {content.get('total', len(sources))} 個來源:\n{source_list}"
        return "📚 未找到相關來源"
    
    elif msg_type == "evaluating":
        return f"🎯 評估中: {content.get('message', '')}"
    
    elif msg_type == "final_answer":
        response = content.get("response", "")
        quality = content.get("quality", {})
        stats = content.get("stats", {})
        
        lines = [
            "═" * 50,
            "✅ 最終答案:",
            "─" * 50,
            response,
            "─" * 50,
            f"📊 品質: {quality.get('confidence', 'unknown')} ({quality.get('score', 0):.2f})",
            f"⏱️ 耗時: {stats.get('duration_ms', 0)}ms",
            f"🔄 步驟: {stats.get('steps', 0)}",
            f"📁 來源: {stats.get('sources_found', 0)}",
            "═" * 50
        ]
        return "\n".join(lines)
    
    elif msg_type == "error":
        return f"❌ 錯誤: {content.get('message', content.get('error', 'Unknown'))}"
    
    elif msg_type == "cancelled":
        return "⏹️ 請求已取消"
    
    elif msg_type == "pong":
        return "🏓 Pong!"
    
    else:
        return f"📨 {msg_type}: {json.dumps(content, ensure_ascii=False)[:100]}"


async def chat_session():
    """互動式聊天會話"""
    print("╔════════════════════════════════════════════════╗")
    print("║     🤖 Agentic RAG WebSocket Chat 測試        ║")
    print("╠════════════════════════════════════════════════╣")
    print("║ 指令:                                          ║")
    print("║   /quit     - 退出                            ║")
    print("║   /simple   - 切換到簡單模式 (無 ReAct)        ║")
    print("║   /react    - 切換到 ReAct 模式               ║")
    print("║   /norag    - 禁用 RAG                        ║")
    print("║   /rag      - 啟用 RAG                        ║")
    print("╚════════════════════════════════════════════════╝")
    print()
    
    use_react = True
    use_rag = True
    
    try:
        async with websockets.connect(WS_URL, ping_interval=30) as ws:
            # 等待連接確認
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(msg)
            print(format_step(data))
            print()
            
            while True:
                # 獲取用戶輸入
                try:
                    user_input = input(f"{'[ReAct]' if use_react else '[Simple]'} {'[RAG]' if use_rag else '[NoRAG]'} 你: ").strip()
                except EOFError:
                    break
                
                if not user_input:
                    continue
                
                # 處理指令
                if user_input.lower() == "/quit":
                    print("👋 再見!")
                    break
                elif user_input.lower() == "/simple":
                    use_react = False
                    print("🔄 切換到簡單模式")
                    continue
                elif user_input.lower() == "/react":
                    use_react = True
                    print("🔄 切換到 ReAct 模式")
                    continue
                elif user_input.lower() == "/norag":
                    use_rag = False
                    print("🔄 禁用 RAG")
                    continue
                elif user_input.lower() == "/rag":
                    use_rag = True
                    print("🔄 啟用 RAG")
                    continue
                
                # 發送聊天消息
                await ws.send(json.dumps({
                    "type": "chat",
                    "content": {
                        "message": user_input,
                        "use_rag": use_rag,
                        "use_react": use_react,
                        "use_memory": True
                    }
                }))
                
                print()
                
                # 接收所有響應
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=120)
                        data = json.loads(msg)
                        
                        formatted = format_step(data)
                        print(formatted)
                        
                        msg_type = data.get("type")
                        if msg_type in ["final_answer", "error", "cancelled"]:
                            break
                            
                    except asyncio.TimeoutError:
                        print("⏰ 響應超時")
                        break
                
                print()
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 連接已關閉: {e}")
    except Exception as e:
        print(f"❌ 錯誤: {e}")


async def single_query(message: str):
    """單次查詢模式"""
    print(f"🔍 查詢: {message}")
    print()
    
    try:
        async with websockets.connect(WS_URL) as ws:
            # 等待連接
            await asyncio.wait_for(ws.recv(), timeout=10)
            
            # 發送查詢
            await ws.send(json.dumps({
                "type": "chat",
                "content": {
                    "message": message,
                    "use_rag": True,
                    "use_react": True,
                    "use_memory": True
                }
            }))
            
            # 接收響應
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=120)
                    data = json.loads(msg)
                    
                    formatted = format_step(data)
                    print(formatted)
                    
                    if data.get("type") in ["final_answer", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    print("⏰ 響應超時")
                    break
                    
    except Exception as e:
        print(f"❌ 錯誤: {e}")


def main():
    """主函數"""
    if len(sys.argv) > 1:
        # 單次查詢模式
        message = " ".join(sys.argv[1:])
        asyncio.run(single_query(message))
    else:
        # 互動模式
        asyncio.run(chat_session())


if __name__ == "__main__":
    main()
