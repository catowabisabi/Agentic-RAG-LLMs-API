import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import json
import asyncio
import websockets
from datetime import datetime

class ChatClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RAG Chatbot Test Client")
        self.root.geometry("500x600")
        
        # 狀態變數
        self.ws = None
        self.is_connected = False
        self.loop = None
        self.thread = None
        
        self.create_widgets()
        
        # 啟動 WebSocket 連線執行緒
        self.start_ws_thread()

    def create_widgets(self):
        # 1. 頂部狀態列
        self.status_frame = tk.Frame(self.root, bg="#f0f0f0", pady=5)
        self.status_frame.pack(fill=tk.X)
        
        self.status_indicator = tk.Label(
            self.status_frame, 
            text="🔴 Disconnected", 
            fg="red", 
            bg="#f0f0f0",
            font=("Arial", 10, "bold")
        )
        self.status_indicator.pack(side=tk.LEFT, padx=10)
        
        self.reconnect_btn = tk.Button(
            self.status_frame,
            text="Reconnect",
            command=self.reconnect,
            state=tk.DISABLED
        )
        self.reconnect_btn.pack(side=tk.RIGHT, padx=10)

        # 2. 聊天記錄顯示區
        self.chat_display = scrolledtext.ScrolledText(
            self.root, 
            wrap=tk.WORD, 
            state='disabled',
            font=("Consolas", 10)
        )
        self.chat_display.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        self.chat_display.tag_config("user", foreground="blue")
        self.chat_display.tag_config("bot", foreground="green")
        self.chat_display.tag_config("system", foreground="gray", font=("Arial", 8, "italic"))
        self.chat_display.tag_config("error", foreground="red")

        # 3. 輸入區
        self.input_frame = tk.Frame(self.root, pady=10)
        self.input_frame.pack(fill=tk.X, padx=10)
        
        self.msg_entry = tk.Entry(self.input_frame, font=("Arial", 12))
        self.msg_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.msg_entry.bind("<Return>", lambda event: self.send_message())
        
        self.send_btn = tk.Button(
            self.input_frame, 
            text="Send", 
            command=self.send_message,
            bg="#007acc",
            fg="white",
            font=("Arial", 10, "bold"),
            width=8
        )
        self.send_btn.pack(side=tk.RIGHT)

    def log(self, text, tag="system"):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"{text}\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    def update_status(self, status):
        if status == "connected":
            self.status_indicator.config(text="🟢 Connected", fg="green")
            self.send_btn.config(state=tk.NORMAL)
            self.reconnect_btn.config(state=tk.DISABLED)
            self.is_connected = True
        elif status == "connecting":
            self.status_indicator.config(text="🟡 Connecting...", fg="orange")
            self.send_btn.config(state=tk.DISABLED)
            self.reconnect_btn.config(state=tk.DISABLED)
            self.is_connected = False
        else:
            self.status_indicator.config(text="🔴 Disconnected", fg="red")
            self.send_btn.config(state=tk.DISABLED)
            self.reconnect_btn.config(state=tk.NORMAL)
            self.is_connected = False

    def start_ws_thread(self):
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()

    def run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_ws())

    async def connect_ws(self):
        uri = "ws://localhost:8000/ws/chat"
        self.root.after(0, self.update_status, "connecting")
        self.root.after(0, self.log, f"Attempting to connect to {uri}...")

        try:
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                self.root.after(0, self.update_status, "connected")
                self.root.after(0, self.log, "Successfully connected!")
                
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        self.handle_incoming_message(data)
                    except websockets.exceptions.ConnectionClosed:
                        self.root.after(0, self.log, "Connection closed by server", "error")
                        break
        except Exception as e:
            self.root.after(0, self.log, f"Connection error: {e}", "error")
        finally:
            self.root.after(0, self.update_status, "disconnected")
            self.ws = None

    def handle_incoming_message(self, data):
        msg_type = data.get("type")
        content = data.get("content")
        
        if msg_type == "complete":
            self.root.after(0, self.log, f"Bot: {content}", "bot")
        elif msg_type == "status":
            self.root.after(0, self.log, f"System: {content}", "system")
        elif msg_type == "error":
            self.root.after(0, self.log, f"Error: {content}", "error")

    def send_message(self):
        if not self.is_connected or not self.ws:
            return
            
        text = self.msg_entry.get().strip()
        if not text:
            return
            
        self.msg_entry.delete(0, tk.END)
        self.log(f"You: {text}", "user")
        
        # 建構 JSON 訊息
        msg_data = {
            "type": "chat_message",
            "content": text,
            "timestamp": datetime.now().isoformat()
        }
        
        # 透過 asyncio loop 發送 (因為 ws 是 async 的)
        asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(msg_data)), self.loop)

    def reconnect(self):
        if not self.thread or not self.thread.is_alive():
            self.start_ws_thread()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClientGUI(root)
    root.mainloop()
