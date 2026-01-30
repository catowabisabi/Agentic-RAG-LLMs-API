# RAG 系統測試報告

## 1. 健康檢查: ✗ HTTPConnectionPool(host='localhost', port=1130): Max retries exceeded with url: / (Caused by NewConnectionError("HTTPConnection(host='localhost', port=1130): Failed to establish a new connection: [WinError 10061] 無法連線，因為目標電腦拒絕連線。"))

## 2. 數據庫: ✗ HTTPConnectionPool(host='localhost', port=1130): Max retries exceeded with url: /rag/databases (Caused by NewConnectionError("HTTPConnection(host='localhost', port=1130): Failed to establish a new connection: [WinError 10061] 無法連線，因為目標電腦拒絕連線。"))

## 3. Agents: ✗ HTTPConnectionPool(host='localhost', port=1130): Max retries exceeded with url: /agents/ (Caused by NewConnectionError("HTTPConnection(host='localhost', port=1130): Failed to establish a new connection: [WinError 10061] 無法連線，因為目標電腦拒絕連線。"))

## 6. 簡單對話: ✗ HTTPConnectionPool(host='localhost', port=1130): Max retries exceeded with url: /chat/message (Caused by NewConnectionError("HTTPConnection(host='localhost', port=1130): Failed to establish a new connection: [WinError 10061] 無法連線，因為目標電腦拒絕連線。"))

## 7. RAG 對話: ✗ HTTPConnectionPool(host='localhost', port=1130): Max retries exceeded with url: /chat/message (Caused by NewConnectionError("HTTPConnection(host='localhost', port=1130): Failed to establish a new connection: [WinError 10061] 無法連線，因為目標電腦拒絕連線。"))

---
## 總結
- API 服務: ✓ 運行中
- 有效知識庫: 0 個
- 知識庫列表: 
- 測試完成