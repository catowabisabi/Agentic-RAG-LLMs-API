# Casual Chat Escalation Bug Fix

## 問題描述

當用戶詢問系統功能時（例如："我想知道你有什麼功能"），系統會錯誤地返回 JSON 格式的 escalation 響應給用戶，而不是正常的文字回答。

### 錯誤響應示例
```json{
  "status": "escalate",
  "reason": "The message '我想知道你有什麼功能' translates to 'I want to know what functions you have,' which indicates a request for information rather than casual conversation.",
  "original_query": "我想知道你有什麼功能",
  "agents_involved": ["casual_chat_agent"],
  "workflow": "casual_chat_escalation"
}
```

## 根本原因

### 調用鏈分析

1. **Entry Classifier** 將問題分類為 "casual chat"
2. **ChatService.process_message()** 調用 `_process_casual_chat()`
3. **ChatService._process_casual_chat()** 調用 `casual_chat_agent.process_task()`
4. **CasualChatAgent** 判斷這不是閒聊，返回 `{"status": "escalate", ...}`
5. **問題：** `_process_casual_chat()` 沒有檢查 escalate 狀態
6. **結果：** 使用 `result.get("response", str(result))` fallback 到 `str(result)`
7. **錯誤：** 整個 dict 被轉換為字符串返回給用戶

### 對比：Manager Agent 的正確處理

在 `manager_agent.py` 的 `_handle_casual_chat()` 方法中，有正確的 escalation 處理：

```python
# Check for Escalation (if Casual Chat declined to answer)
if result.get("status") == "escalate":
    reason = result.get("reason", "Unknown")
    logger.info(f"[Manager] Casual Chat escalated query: {reason}. Rerouting to Simple RAG.")
    
    # Re-route to general knowledge
    return await self._handle_general_knowledge(task)
```

但是當從 ChatService 層直接調用時，繞過了這個檢查。

## 修復方案

### 1. 在 ChatService._process_casual_chat() 中添加 escalation 檢查

```python
async def _process_casual_chat(self, ...) -> Union[Tuple[str, List[str], List[Dict]], Tuple[str, List[str]]]:
    """處理休閒聊天"""
    # ...existing code...
    
    result = await casual_agent.process_task(task)
    
    # ✅ NEW: Check if casual chat agent escalated the query
    if result.get("status") == "escalate":
        reason = result.get("reason", "Query requires factual information")
        logger.info(f"[ChatService] Casual chat escalated: {reason}. Rerouting to manager agent.")
        
        # Emit rerouting event
        await self.event_manager.emit(...)
        
        # Re-route to manager agent
        response_text, agents_involved, sources = await self._process_manager_agent(
            message=message,
            chat_history=chat_history,
            user_context=user_context,
            use_rag=True,  # Enable RAG for escalated queries
            context={},
            task_uid=task_uid,
            conversation_id=conversation_id,
            classification=None,
            stream_callback=None
        )
        
        # Return with sources (3-tuple)
        return response_text, agents_involved, sources
    
    # Normal casual chat (2-tuple)
    response_text = result.get("response", str(result))
    return response_text, result.get("agents_involved", ["casual_chat_agent"])
```

### 2. 更新返回值類型

因為 escalation 時會返回 sources，所以返回值類型需要支持兩種格式：

```python
# Type annotation
async def _process_casual_chat(...) -> Union[Tuple[str, List[str], List[Dict]], Tuple[str, List[str]]]:
```

### 3. 更新調用處的解包邏輯

在 `process_message()` 中：

```python
if classification.is_casual:
    # Route to Casual Chat Agent
    # Note: May escalate internally and return sources
    result = await self._process_casual_chat(...)
    
    # Handle tuple unpacking (may be 2 or 3 elements due to escalation)
    if len(result) == 3:
        response_text, agents_involved, sources = result
    else:
        response_text, agents_involved = result
```

## 修復後的流程

### 正常閒聊（無 escalation）
```
User: "你好"
  ↓
Entry Classifier: casual=True
  ↓
ChatService._process_casual_chat()
  ↓
CasualChatAgent.process_task()
  ↓
返回: {"response": "你好！有什麼可以幫到你？", ...}
  ↓
用戶收到: "你好！有什麼可以幫到你？"
```

### 需要 Escalation 的情況
```
User: "我想知道你有什麼功能"
  ↓
Entry Classifier: casual=True
  ↓
ChatService._process_casual_chat()
  ↓
CasualChatAgent.process_task()
  ↓
返回: {"status": "escalate", "reason": "...", ...}
  ↓
✅ 檢測到 escalate 狀態
  ↓
發送重新路由事件
  ↓
調用 _process_manager_agent() 並啟用 RAG
  ↓
ManagerAgent → GeneralKnowledge 或 RAG
  ↓
返回正常文字回答
  ↓
用戶收到: "我可以幫你：回答問題、搜索知識庫、規劃分析、翻譯、總結文件，同埋記住你嘅偏好。有咩需要？"
```

## 修改的文件

- ✅ [services/chat_service.py](../services/chat_service.py)
  - 添加 `Union` 導入
  - 修改 `_process_casual_chat()` 添加 escalation 檢查
  - 更新返回值類型註解
  - 修改 `process_message()` 中的解包邏輯

## 測試驗證

### 測試用例

1. **正常閒聊** - 應該快速回應
   ```
   - "你好"
   - "How are you?"
   - "謝謝"
   ```

2. **需要 Escalation 的問題**
   ```
   - "我想知道你有什麼功能"
   - "What can you do?"
   - "你可以幫我做什麼"
   ```

3. **技術問題** - 應該直接路由到 Manager
   ```
   - "如何使用 Python 創建 API"
   - "解釋量子計算"
   ```

### 預期行為

- ✅ 正常閒聊：快速回應，無 RAG 調用
- ✅ 需要 Escalation：顯示重新路由訊息，然後給出詳細回答
- ✅ 技術問題：直接路由到 Manager Agent
- ✅ 不再返回 JSON 字符串給用戶

## 相關 Issues

- COT (Chain of Thought) 中斷問題
- Casual Chat Agent escalation 邏輯
- ChatService 與 ManagerAgent 的路由一致性

## 總結

這個修復確保了當 CasualChatAgent 判斷無法處理某個問題時，系統會優雅地重新路由到 ManagerAgent，而不是將內部狀態返回給用戶。同時保持了快速響應閒聊的優勢，只在必要時才啟用完整的 RAG 處理流程。
