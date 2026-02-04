# Manager Agent 整合計劃

## 目標
合併 `manager_agent.py` (1721 行) 和 `manager_agent_v2.py` (687 行) 成為單一、強大的 Manager Agent。

## 版本對比

### manager_agent.py (舊版)
**優勢：**
- ✅ 完整的查詢分類系統 (QueryClassification)
- ✅ EventBus 整合
- ✅ 中斷命令處理 (InterruptCommand)
- ✅ 系統健康監控
- ✅ 詳細的錯誤處理
- ✅ 代理狀態追蹤

**缺點：**
- ❌ 硬編碼 LLM 初始化
- ❌ 沒有 Metacognition
- ❌ 缺少 Self-Correction
- ❌ 沒有 PEV 驗證
- ❌ 較少的智能決策能力

### manager_agent_v2.py (Agentic 版)
**優勢：**
- ✅ Metacognition 引擎整合
- ✅ 智能策略選擇 (direct/RAG/ReAct)
- ✅ PEV 驗證流程
- ✅ Self-Correction 能力
- ✅ Planning-Driven 架構
- ✅ ReAct 循環整合

**缺點：**
- ❌ 功能較少（僅核心功能）
- ❌ 較少的錯誤處理
- ❌ 沒有系統監控功能

## 整合策略

### 階段 1: 創建統一版本 (unified_manager_agent.py)
**保留所有優勢：**
1. **基礎架構** - 來自 v1
   - QueryClassification
   - EventBus 整合
   - 中斷命令處理
   - 系統健康監控

2. **Agentic 能力** - 來自 v2
   - Metacognition 引擎
   - 智能策略選擇
   - PEV 驗證
   - Self-Correction

3. **Service Layer 重構**
   - 使用 llm_service 替代硬編碼 ChatOpenAI
   - 使用 rag_service 處理 RAG 查詢
   - 使用 prompt_manager 管理提示詞

### 階段 2: 測試與驗證
1. 單元測試所有核心功能
2. 整合測試與其他 Agent 的交互
3. 性能測試確保沒有退化

### 階段 3: 逐步遷移
1. 保留舊版本作為備份
2. 更新所有引用指向新版本
3. 監控生產環境表現

## 預期收益

### 代碼簡化
- **當前：** 1721 + 687 = 2408 行
- **預期：** ~1200 行（減少 50%）
- **減少原因：**
  - 消除重複代碼
  - Service Layer 減少樣板代碼
  - 統一的錯誤處理

### 功能增強
- ✅ 完整的 Agentic 能力
- ✅ 完整的系統監控
- ✅ 更好的錯誤處理
- ✅ 自動 Token 追蹤
- ✅ 外部化提示詞配置

### 維護性
- 單一事實來源
- 更容易測試
- 更清晰的代碼結構
- 更好的文檔

## 實施步驟

### 步驟 1: 創建新文件
```bash
agents/core/unified_manager_agent.py
```

### 步驟 2: 實現核心類
```python
class UnifiedManagerAgent(BaseAgent):
    """統一的 Manager Agent - 整合所有最佳功能"""
    
    def __init__(self):
        # 使用 Service Layer
        super().__init__(...)
        
        # 加載配置
        self.prompt_template = self.prompt_manager.get_prompt("manager_agent")
        
        # 初始化 Agentic 組件
        from agents.core.metacognition.metacognition_engine import MetacognitionEngine
        self.metacognition = MetacognitionEngine()
        
        # 事件總線（如果可用）
        if HAS_EVENT_BUS:
            self.event_bus = event_bus
```

### 步驟 3: 遷移核心方法
**從 v1 保留：**
- `_classify_query()` - 查詢分類
- `_handle_interrupt()` - 中斷處理
- `_monitor_system()` - 系統監控
- `_handle_escalation()` - 升級處理

**從 v2 保留：**
- `_select_strategy()` - 智能策略選擇
- `_execute_with_metacognition()` - Metacognition 執行
- `_verify_with_pev()` - PEV 驗證
- `_self_correct()` - 自我修正

**新增統一方法：**
- `process_task()` - 統一任務處理入口
- `_execute_strategy()` - 執行選定策略
- `_handle_failure()` - 統一錯誤處理

### 步驟 4: 更新 Agent Registry
```python
# agents/shared_services/agent_registry.py
from agents.core.unified_manager_agent import UnifiedManagerAgent

# 替換舊的 manager_agent import
```

### 步驟 5: 測試
```bash
# 運行測試
python testing_scripts/test_unified_manager.py
```

## 時間估計
- **步驟 1-2:** 2-3 小時（創建基礎結構）
- **步驟 3:** 3-4 小時（遷移方法）
- **步驟 4:** 30 分鐘（更新引用）
- **步驟 5:** 2-3 小時（測試和調試）

**總計：** 8-11 小時

## 風險管理
- ✅ 保留原文件作為備份
- ✅ 逐步遷移，不一次性替換
- ✅ 詳細的測試覆蓋
- ✅ 回滾計劃（如果出現問題）

## 下一步行動
1. ✅ 創建此計劃文檔
2. ⏳ 開始實施統一版本
3. ⏳ 測試與驗證
4. ⏳ 部署到生產環境
