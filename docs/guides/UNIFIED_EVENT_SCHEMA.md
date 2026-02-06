# 統一事件架構 (Unified Event Schema)

## 概述

所有 Agent/Service 發送的事件都遵循此統一結構，確保：

1. **一致性**：所有事件使用相同欄位和格式
2. **可追蹤**：每個事件有唯一 ID 和時間戳
3. **可視化**：包含 UI 渲染提示（顏色、圖標、動畫）
4. **可持久化**：自動寫入 SessionDB

---

## 事件結構

```typescript
interface UnifiedEvent {
  // 識別欄位
  event_id: string;        // 唯一事件 ID (evt_xxx)
  session_id: string;      // 會話 ID
  task_id: string;         // 任務 ID
  conversation_id?: string; // 對話 ID（可選）

  // 事件類型
  type: EventType;         // init|thinking|status|progress|stream|result|error
  stage: Stage;            // init|classifying|planning|retrieval|executing|synthesis|complete|failed

  // 詳細資訊
  agent: AgentInfo;        // Agent 資訊
  content: ContentData;    // 事件內容
  ui: UIHints;             // UI 渲染提示
  metadata: EventMetadata; // 元數據

  // 時間戳
  timestamp: string;       // ISO 8601 格式
}
```

---

## 事件類型 (EventType)

| 類型 | 說明 | 用途 |
|------|------|------|
| `init` | 初始化 | 任務開始時發送 |
| `thinking` | 思考中 | Agent 正在思考 |
| `status` | 狀態更新 | 一般狀態通知 |
| `progress` | 進度 | 多步驟任務進度 |
| `stream` | 串流 | LLM 回應片段 |
| `result` | 結果 | 最終回答 |
| `error` | 錯誤 | 處理失敗 |

---

## 處理階段 (Stage)

| 階段 | 顏色 | 圖標 | 說明 |
|------|------|------|------|
| `init` | #6b7280 | inbox | 初始化 |
| `classifying` | #8b5cf6 | tag | 分類中 |
| `planning` | #f59e0b | clipboard-list | 規劃中 |
| `retrieval` | #10b981 | search | 檢索中 |
| `executing` | #3b82f6 | cog | 執行中 |
| `synthesis` | #6366f1 | sparkles | 整合中 |
| `complete` | #22c55e | check-circle | 完成 |
| `failed` | #ef4444 | x-circle | 失敗 |

---

## 使用方式

### Python (後端)

```python
from services.unified_event_manager import get_event_manager

# 獲取事件管理器
event_manager = get_event_manager()

# 發送初始化事件
await event_manager.emit_init(
    session_id="session_123",
    task_id="task_456",
    message="收到您的訊息，正在處理..."
)

# 發送思考事件
await event_manager.emit_thinking(
    session_id="session_123",
    task_id="task_456",
    agent_name="rag_agent",
    message="正在分析問題..."
)

# 發送結果事件
await event_manager.emit_result(
    session_id="session_123",
    task_id="task_456",
    message="處理完成",
    answer="這是回答內容...",
    sources=[{"title": "來源1", "content": "..."}]
)
```

### TypeScript (前端)

```typescript
import { useUnifiedEvents } from '@/hooks/useUnifiedEvents';
import { UnifiedEvent, isTerminalEvent } from '@/types/unified-event';

function ChatComponent() {
  const {
    events,
    timeline,
    currentStage,
    isProcessing,
    latestResult
  } = useUnifiedEvents({
    sessionId: 'session_123',
    onEvent: (event) => console.log('Event:', event),
    onResult: (event) => console.log('Result:', event.content.message)
  });

  return (
    <div>
      {isProcessing && <Spinner stage={currentStage} />}
      {timeline.map(item => (
        <TimelineItem key={item.event_id} {...item} />
      ))}
      {latestResult && <Answer content={latestResult.content.answer} />}
    </div>
  );
}
```

---

## 檔案結構

```
services/
  unified_event_manager.py    # Python 事件管理器

ui/
  types/
    unified-event.ts          # TypeScript 類型定義
  hooks/
    useUnifiedEvents.ts       # React Hook
```

---

## 事件流程圖

```
用戶發送訊息
    │
    ▼
┌─────────────────────┐
│  emit_init()        │  ← "收到您的訊息..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_classifying() │  ← "正在分析問題類型..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_planning()    │  ← "正在制定計劃..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_retrieval()   │  ← "正在搜尋資料..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_thinking()    │  ← "正在思考..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_synthesis()   │  ← "正在整合資訊..."
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  emit_result()      │  ← 最終回答
└─────────────────────┘
```

---

## 最佳實踐

1. **始終包含 session_id 和 task_id**：確保 UI 可以正確過濾事件
2. **使用便捷方法**：優先使用 `emit_thinking()`, `emit_result()` 等
3. **不要在 stream 事件持久化**：設置 `persist=False`
4. **提供有意義的訊息**：使用中文，讓用戶理解正在發生什麼
