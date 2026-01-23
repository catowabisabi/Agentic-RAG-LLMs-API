import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置 Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG-API")

app = FastAPI(title="RAG Chatbot API")

# 允許 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 訊息結構設計 (Message Structure) ===

class ChatMessage(BaseModel):
    """使用者傳送的訊息結構"""
    type: str = "chat_message"  # 訊息類型: chat_message, ping, etc.
    content: str                # 訊息內容
    timestamp: Optional[str] = None

class ChatResponse(BaseModel):
    """伺服器回傳的訊息結構"""
    type: str                  # 類型: response_chunk, complete, error, status
    content: str               # 內容或 Token
    status: str = "processing" # 狀態: processing, done, failed
    timestamp: str

# === WebSocket 端點 ===

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")
    
    try:
        # 發送連接成功訊息
        await websocket.send_json({
            "type": "status",
            "content": "Connected to RAG Chatbot API",
            "status": "connected",
            "timestamp": datetime.now().isoformat()
        })

        while True:
            # 1. 接收訊息
            data = await websocket.receive_text()
            logger.info(f"Received raw data: {data}")
            
            try:
                # 解析 JSON
                message_data = json.loads(data)
                user_msg = ChatMessage(**message_data)
                
                logger.info(f"Parsed Message: {user_msg.content}")

                # TODO: 這裡未來會接 LangGraph Agent
                # 目前為 Echo 模式
                
                # 2. 模擬處理中 (可選)
                await websocket.send_json({
                    "type": "status",
                    "content": "Thinking...",
                    "status": "processing",
                    "timestamp": datetime.now().isoformat()
                })

                # 3. 回傳主要內容 (Echo)
                response_content = f"Server received: {user_msg.content}"
                
                response = ChatResponse(
                    type="complete",
                    content=response_content,
                    status="done",
                    timestamp=datetime.now().isoformat()
                )
                
                await websocket.send_json(response.dict())
                logger.info(f"Sent response: {response_content}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON")
                await websocket.send_json({
                    "type": "error", 
                    "content": "Invalid JSON format", 
                    "status": "failed",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error", 
                    "content": str(e), 
                    "status": "failed",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
