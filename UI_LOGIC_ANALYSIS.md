# UI 邏輯與問題診斷清單

## 📋 當前問題總結

### 用戶反映的問題：
1. ✅ **已修復**: 不會再卡住（async 轉換完成）
2. ❌ **未解決**: Chat 頁面發問後離開，回來看不到回應
3. ❌ **未解決**: 看不到 running 的 agent
4. ❌ **未解決**: WebSocket 沒反應

---

## 🔍 問題根因分析

### 問題 1: Chat 頁面離開後看不到回應

**當前行為：**
- ChatPage 使用 `async_mode: true` 發送任務
- 任務在後台運行，前端輪詢 (polling) 每 2 秒檢查狀態
- **關鍵問題**: 當用戶離開 Chat 頁面時，`while` 輪詢循環仍在 `sendMessage` 函數中運行
- 但是當用戶離開頁面，React 組件可能被卸載，狀態更新無效

**程式碼位置：**
- `ui/components/ChatPage.tsx:448-530`
- Async 模式下的 polling loop

**根因：**
```tsx
// 問題：這個 while loop 綁定在 sendMessage 函數內
while (attempts < maxAttempts) {
  await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  attempts++;
  
  const statusResponse = await chatAPI.getTaskStatus(task_id);
  // ... 更新狀態
  setSessions(prev => ...) // ❌ 如果用戶離開頁面，這個不會顯示
}
```

**正確做法應該是：**
- 輪詢應該在 `useEffect` 中獨立運行
- 使用 `localStorage` 中的 `PENDING_TASK_KEY` 來恢復未完成的任務
- 當用戶回到頁面時，檢測到有 pending task，自動恢復輪詢

---

### 問題 2: 看不到 running 的 agent

**當前行為：**
- WebSocket 連接建立，但 agent 狀態沒有顯示

**可能原因：**

#### A. 後端沒有發送 agent 狀態更新
**檢查點：**
1. EventBus 是否正確廣播事件？
   - 位置: `services/event_bus.py:150-250`
   - 檢查: `broadcast_loop()` 是否運行
   
2. BaseAgent 是否正確更新狀態？
   - 位置: `agents/shared_services/base_agent.py`
   - 檢查: `_update_state()` 是否調用 `event_bus.emit_event()`

3. Manager Agent 處理任務時是否發送狀態？
   - 位置: `agents/core/manager_agent.py`
   - 檢查: 是否調用 `self._update_state(AgentState.WORKING)`

#### B. WebSocket 沒有正確轉發事件
**檢查點：**
1. WebSocketManager 的 broadcast 功能
   - 位置: `agents/shared_services/websocket_manager.py:130-150`
   - 檢查: `broadcast_to_clients()` 是否被 EventBus 調用

2. WebSocket 連接是否建立？
   - 檢查瀏覽器 Console: `[Chat] WebSocket connected`
   - 檢查後端日誌: `Client connected: client_xxx`

#### C. 前端沒有正確處理 WebSocket 消息
**檢查點：**
1. ChatPage WebSocket onmessage handler
   - 位置: `ui/components/ChatPage.tsx:120-180`
   - 檢查: 是否正確解析 `agent_status_changed` 事件

2. DashboardPage WebSocket handler
   - 位置: `ui/components/DashboardPage.tsx:85-105`
   - 檢查: 是否更新 `agentStatuses` state

---

### 問題 3: WebSocket 沒反應

**診斷步驟：**

#### Step 1: 確認 WebSocket 連接建立
```javascript
// 打開瀏覽器 Console，查看：
[Chat] WebSocket connected  // ✅ 應該看到這個
[Dashboard] WebSocket connected  // ✅ 應該看到這個
```

#### Step 2: 確認後端發送事件
```python
# 查看 API 服務日誌，應該看到：
services.event_bus - INFO - Event emitted: agent_status_changed
agents.shared_services.websocket_manager - INFO - Broadcasting to 1 clients
```

#### Step 3: 確認前端收到消息
```javascript
// 在 ChatPage.tsx ws.onmessage 中添加 console.log
ws.onmessage = (event) => {
  console.log('[WS] Received:', event.data);  // 🔍 應該看到心跳和狀態更新
}
```

---

## 🛠️ 修復方案

### 方案 1: 修復 Chat 頁面輪詢問題

**目標**: 即使用戶離開頁面，回來後也能看到結果

**修改位置**: `ui/components/ChatPage.tsx`

**實現：**
1. 將輪詢邏輯從 `sendMessage` 函數中分離
2. 創建 `useEffect` hook 專門處理 pending task 輪詢
3. 使用 `localStorage` 的 `PENDING_TASK_KEY` 作為輪詢觸發器

**偽代碼：**
```tsx
// 新增一個 useEffect 專門處理輪詢
useEffect(() => {
  const pollPendingTask = async () => {
    const pendingTaskStr = localStorage.getItem(PENDING_TASK_KEY);
    if (!pendingTaskStr) return;
    
    const pendingTask: PendingTask = JSON.parse(pendingTaskStr);
    
    // 開始輪詢
    const interval = setInterval(async () => {
      const status = await chatAPI.getTaskStatus(pendingTask.taskId);
      
      if (status.status === 'completed') {
        // 獲取結果並更新 sessions
        const result = await chatAPI.getTaskResult(pendingTask.taskId);
        setSessions(...);
        localStorage.removeItem(PENDING_TASK_KEY);
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  };
  
  pollPendingTask();
}, []); // 頁面加載時執行
```

---

### 方案 2: 修復 Agent 狀態顯示

**目標**: 實時看到哪些 agent 正在運行

**檢查清單：**

#### A. 確認後端正確發送狀態
1. 在 `base_agent.py` 的 `_update_state()` 中確認：
```python
async def _update_state(self, new_state: AgentState, message: str = None):
    self.state = new_state
    # 🔍 確認這行存在
    await event_bus.emit_agent_status_changed(...)
    logger.info(f"Agent {self.agent_name} state: {new_state}")
```

2. 在 `manager_agent.py` 的 `process_task()` 中確認：
```python
async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
    # 🔍 確認在處理任務時更新狀態
    await self._update_state(AgentState.WORKING, f"Processing {task.task_type}")
    # ... 處理邏輯
    await self._update_state(AgentState.IDLE)
```

#### B. 確認 WebSocket 正確轉發
1. 檢查 `websocket_manager.py` 的 `broadcast_to_clients()`:
```python
async def broadcast_to_clients(self, event: Dict[str, Any]):
    """Called by EventBus to broadcast events"""
    # 🔍 這個函數應該被調用
    logger.info(f"Broadcasting to {len(self.client_connections)} clients: {event.get('event_type')}")
    
    for connection in self.client_connections.values():
        await connection.send_json(event)
```

#### C. 確認前端正確顯示
1. ChatPage 的 agent 狀態面板應該顯示：
```tsx
{/* 🔍 確認這個區域有渲染 */}
{hasWorkingAgents && (
  <div className="mb-4 p-4 bg-blue-50 rounded-lg">
    <div className="flex items-center gap-2 mb-2">
      <Activity className="w-5 h-5 text-blue-600 animate-pulse" />
      <span className="font-semibold text-blue-900">Active Agents</span>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {Object.values(agentStatuses)
        .filter(a => ['working', 'thinking', ...].includes(a.state?.toLowerCase()))
        .map(agent => (
          <div key={agent.name} ...>
            {agent.name}: {agent.state}
          </div>
        ))}
    </div>
  </div>
)}
```

---

### 方案 3: 增強 WebSocket 可靠性

**目標**: 確保 WebSocket 消息正確接收和處理

**實現：**
1. 添加 WebSocket 心跳檢測
2. 添加重連機制（已有，但需確認工作）
3. 添加消息確認機制

**修改位置**: `ui/components/ChatPage.tsx` 和 `DashboardPage.tsx`

---

## 📊 診斷工具

### 前端檢查命令（瀏覽器 Console）

```javascript
// 1. 檢查 WebSocket 狀態
console.log('WS State:', wsRef.current?.readyState); // 1 = OPEN

// 2. 檢查 Agent 狀態
console.log('Agent Statuses:', agentStatuses);

// 3. 檢查 Pending Task
console.log('Pending:', localStorage.getItem('agentic-rag-pending-task'));

// 4. 監聽 WebSocket 消息
const ws = new WebSocket('ws://localhost:1130/ws');
ws.onmessage = (e) => console.log('WS:', JSON.parse(e.data));
```

### 後端檢查（API 日誌）

應該看到以下日誌：
```
services.event_bus - INFO - EventBus broadcast loop started
agents.shared_services.websocket_manager - INFO - Client connected: client_xxx
services.event_bus - INFO - Event emitted: agent_status_changed (agent: manager_agent, state: working)
agents.shared_services.websocket_manager - INFO - Broadcasting event to 1 clients
```

---

## 🎯 優先修復順序

1. **高優先級**: 修復 Chat 頁面輪詢問題
   - 影響: 用戶體驗最差
   - 複雜度: 中等
   - 預估時間: 30 分鐘

2. **高優先級**: 確認 Agent 狀態事件是否發送
   - 影響: Dashboard 和 Chat 頁面都依賴這個
   - 複雜度: 低（主要是診斷）
   - 預估時間: 15 分鐘

3. **中優先級**: 增強 WebSocket 可靠性
   - 影響: 整體系統穩定性
   - 複雜度: 中等
   - 預估時間: 45 分鐘

---

## 🔧 建議的測試流程

### 測試 1: WebSocket 連接
1. 開啟 Chat 頁面
2. 打開瀏覽器 Console
3. 確認看到 `[Chat] WebSocket connected`
4. 檢查 API 日誌確認 `Client connected`

### 測試 2: Agent 狀態更新
1. 在 Chat 頁面發送問題
2. 立即切換到 Dashboard 頁面
3. Dashboard 應該顯示 agent 狀態變化
4. 檢查 Console 是否收到 `agent_status_changed` 事件

### 測試 3: 離開頁面後恢復
1. 在 Chat 頁面發送問題（Background Mode）
2. 立即離開到其他頁面（如 Dashboard）
3. 等待 10 秒
4. 回到 Chat 頁面
5. 應該看到回應已經出現

---

## 📝 代碼審查發現

### 發現 1: Polling 綁定在函數內
**位置**: `ChatPage.tsx:448-530`
**問題**: `while` loop 在 `sendMessage` 函數內，用戶離開頁面後無法繼續更新 UI
**影響**: 高

### 發現 2: WebSocket 重連延遲太長
**位置**: `ChatPage.tsx:168`
```tsx
ws.onclose = () => {
  setTimeout(connectWs, 3000); // ❌ 3秒太長
}
```
**建議**: 改為 1000ms 或實現指數退避

### 發現 3: 缺少 Agent 狀態的初始請求
**問題**: WebSocket 連接後，前端沒有主動請求當前所有 agent 的狀態
**建議**: 連接後發送 `{type: "status"}` 消息

### 發現 4: EventBus 心跳可能沒有包含完整狀態
**位置**: `services/event_bus.py`
**需確認**: 心跳事件是否包含所有 agent 的當前狀態

---

## ✅ 下一步行動

1. **立即執行**:
   - [ ] 在瀏覽器 Console 檢查 WebSocket 連接
   - [ ] 在 API 日誌檢查 EventBus 是否廣播事件
   - [ ] 測試發送消息時是否有 agent 狀態變化

2. **短期修復**:
   - [ ] 將 Chat 頁面的輪詢邏輯移到獨立的 useEffect
   - [ ] 添加前端調試日誌確認 WebSocket 消息
   - [ ] 確認 Manager Agent 正確更新狀態

3. **長期改進**:
   - [ ] 實現 Server-Sent Events (SSE) 作為 WebSocket 備份
   - [ ] 添加任務完成通知
   - [ ] 實現任務歷史查詢
