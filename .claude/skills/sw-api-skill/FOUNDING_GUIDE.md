# SolidWorks API Founding Database 使用指南

## 概述

`founding.db` 是一個學習數據庫系統，記錄 SolidWorks API 使用過程中發現的錯誤和解決方案，幫助避免重複錯誤並積累修正經驗。

## 核心理念

**Agent + Skill + Learning** 架構：
- **Skill**: 從 SolidWorks API 文檔提取數據
- **Agent**: 生成代碼並修正錯誤
- **Learning**: 記錄修正過程供未來參考

## 快速開始

### 1. 搜索已知解決方案

在開始修正API錯誤前，先搜索是否有相似的解決方案：

```bash
# 搜索特定API函數的錯誤記錄
python scripts/founding_manager.py search --api-function "SetUserPreferenceInteger"

# 搜索特定錯誤類型
python scripts/founding_manager.py search --error-type "UNDEFINED_CONSTANT"

# 按標籤搜索
python scripts/founding_manager.py search --tags "units,constants" --severity high
```

### 2. 記錄新發現

當發現並修正新的API錯誤時，使用 Python 代碼記錄：

```python
from founding_manager import FoundingManager

manager = FoundingManager()

finding_id = manager.add_finding(
    error_type="UNDEFINED_CONSTANT",
    api_function="SetUserPreferenceInteger",
    error_description="VBA 錯誤: variable not set - swUnitsLinear 未定義",
    original_code="swModelDocExt.SetUserPreferenceInteger swUnitsLinear, 0, swINCHES",
    corrected_code="swModelDocExt.SetUserPreferenceInteger 0, 0, 0  # swUnitsLinear=0",
    api_constants={"swUnitsLinear": 0, "swINCHES": 0},
    solution_explanation="使用數值常數代替未定義的變數名稱",
    tags=["units", "constants"],
    severity="high"
)
```

## 錯誤類型分類

### UNDEFINED_CONSTANT
- **描述**: VBA 中使用了未定義的 SolidWorks 常數變數
- **典型錯誤**: "variable not set"
- **解決方法**: 使用正確的數值代替常數變數名稱

**常見常數值**:
```
swDocPART = 1
swDocASSEMBLY = 2  
swDocDRAWING = 3
swUnitsLinear = 0
swINCHES = 0
swEndCondBlind = 0
swEndCondThroughAll = 1
```

### ARG_NOT_OPTIONAL
- **描述**: API 方法調用時參數錯誤或缺少必要參數
- **典型錯誤**: "Arg not optional"
- **解決方法**: 檢查API文檔，提供正確的參數類型和數量

### API_USAGE_ERROR
- **描述**: API 方法使用不當或調用順序錯誤
- **解決方法**: 參考官方範例，調整調用方式

## 最佳實踐

### 修正流程
1. **搜索**: 先查詢 founding.db 是否有相似錯誤的解決方案
2. **查詢**: 使用 sw-api skill 查詢官方文檔
3. **修正**: 應用解決方案修正代碼
4. **記錄**: 將新發現記錄到 founding.db

### 記錄標準
- **描述清晰**: 詳細描述錯誤現象和原因
- **代碼完整**: 提供足夠的代碼上下文
- **標籤準確**: 使用適當的標籤便於搜索
- **嚴重程度**: 正確評估錯誤的影響程度

### 標籤建議
常用標籤：`units`, `constants`, `extrusion`, `document`, `template`, `save`, `parameters`, `features`, `sketch`

## 數據庫維護

### 導出備份
```bash
python scripts/founding_manager.py export --output findings_backup.json
```

### 檢查數據庫狀態
```bash
# 查看最近的發現記錄
python scripts/founding_manager.py search --limit 10

# 查看高嚴重程度的錯誤
python scripts/founding_manager.py search --severity critical --limit 20
```

## 集成工作流程

### 代碼生成前
```bash
# 檢查相關API是否有已知問題
python scripts/founding_manager.py search --api-function "FeatureExtrusion"
```

### 錯誤修正後
```python
# 立即記錄解決方案
manager.add_finding(...)
```

### 定期維護
- 每週匯出備份
- 檢查重複記錄
- 更新解決方案

這個系統將幫助你建立 SolidWorks API 使用的知識庫，避免重複犯錯並不斷改善代碼生成質量。