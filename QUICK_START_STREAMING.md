# Quick Start Guide - Streaming & MCP Integration

## 快速啟動

### 1. 安裝依賴

```bash
# 安裝Python依賴（如果還沒安裝openpyxl）
pip install openpyxl>=3.1.5

# 或者重新安裝所有依賴
pip install -r docker/requirements.txt
```

### 2. 啟動服務

```bash
# 啟動API
start_api.bat

# 啟動UI（新終端）
start_ui.bat
```

### 3. 測試Streaming

1. 打開瀏覽器訪問 `http://localhost:3000`
2. 確認看到聊天界面
3. 檢查底部控制按鈕中有 **"⚡ Stream On"** 按鈕（紫色=啟用）
4. 發送一條訊息：
   ```
   Hello, can you explain what streaming is?
   ```
5. 觀察回應是否逐字顯示（而不是一次性出現）

**預期行為:**
- ✅ 訊息逐字出現
- ✅ 有輕微的打字動畫效果
- ✅ 速度感覺更快
- ✅ 如果失敗，自動fallback到regular模式

### 4. 測試MCP Tools

#### 4a. 測試Excel工具

```bash
# 運行測試腳本
python testing_scripts/test_tool_integration.py
```

**預期輸出:**
```
==================================================
Testing Excel Tools
==================================================

[Test 1] Create Excel File
Result: {"success": true, ...}

[Test 2] Write Excel Data
Result: {"success": true, ...}

[Test 3] Read Excel Data
Result: {"data": [["Name", "Age", "City"], ...]}

✅ All Tests Completed!
```

**生成檔案:**
- `test_output.xlsx`
- `test_file.txt`
- `test_data.json`

#### 4b. 通過Chat測試工具

發送以下訊息到Chat（確保RAG和Streaming都啟用）：

**Excel測試:**
```
請幫我創建一個Excel文件叫 "sales.xlsx"，包含以下資料：
產品名稱 | 價格 | 庫存
蘋果 | 10 | 100
香蕉 | 5 | 200
```

**檔案操作測試:**
```
請幫我寫一個JSON文件 "config.json"，內容是：
{
  "app_name": "MyApp",
  "version": "1.0.0",
  "features": ["streaming", "tools"]
}
```

**搜索測試（需要API key）:**
```
請幫我搜索一下 "Python async programming best practices"
```

### 5. 環境設置（可選功能）

#### Brave Search（可選）

如果想使用搜索功能：

```bash
# Windows PowerShell
$env:BRAVE_API_KEY = "your_brave_api_key_here"

# 或者添加到環境變數
# 1. 打開"系統屬性" > "環境變數"
# 2. 新增變數: BRAVE_API_KEY = your_key
# 3. 重啟終端
```

獲取API Key: https://brave.com/search/api/

#### Gmail OAuth（可選）

Communication tools需要Gmail OAuth設置（目前跳過）

---

## UI功能說明

### 控制按鈕

打開Chat介面後，訊息輸入框下方有三個toggle按鈕：

1. **🔄 Background Mode / ⏳ Wait Mode**
   - 綠色 = 異步模式（後台處理）
   - 灰色 = 同步模式（等待響應）

2. **⚡ Stream On / 📝 Stream Off** ← 新增！
   - 紫色 = Streaming啟用（推薦）
   - 灰色 = Regular模式

3. **🔍 RAG On / 💬 RAG Off**
   - 藍色 = RAG搜索啟用
   - 灰色 = RAG禁用

### 推薦設置

**最快用戶體驗:**
- ⏳ Wait Mode (synchronous)
- ⚡ Stream On
- 🔍 RAG On

**最穩定處理:**
- 🔄 Background Mode (async)
- 📝 Stream Off
- 🔍 RAG On

---

## 故障排除

### Streaming不工作

**症狀:** 訊息一次性出現，沒有逐字效果

**檢查:**
```bash
# 1. 確認API正在運行
curl http://localhost:1130/health

# 2. 檢查瀏覽器console（F12）
# 看是否有錯誤訊息

# 3. 測試streaming endpoint
curl -X POST http://localhost:1130/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "use_rag": false}'
```

**解決:**
- 如果streaming失敗，系統會自動fallback
- 可以手動點擊toggle切換到regular模式

### Tool執行錯誤

**症狀:** Chat說找不到工具或執行失敗

**檢查:**
```bash
# 1. 確認Tool Agent可用
python -c "from agents.auxiliary.tool_agent import ToolAgent; print('OK')"

# 2. 檢查openpyxl
python -c "import openpyxl; print('openpyxl OK')"

# 3. 運行測試
python testing_scripts/test_tool_integration.py
```

**解決:**
```bash
# 重新安裝依賴
pip install -r docker/requirements.txt

# 或單獨安裝
pip install openpyxl>=3.1.5
```

### Import錯誤

**症狀:** `Import "openpyxl" could not be resolved`

這是正常的IDE警告（如果還沒安裝）

**解決:**
```bash
pip install openpyxl>=3.1.5
```

---

## 驗證清單

使用以下清單確認所有功能正常：

- [ ] API啟動成功 (`http://localhost:1130`)
- [ ] UI啟動成功 (`http://localhost:3000`)
- [ ] 可以發送訊息並收到回應
- [ ] Streaming按鈕可見且可切換
- [ ] 啟用streaming時看到逐字效果
- [ ] 可以創建Excel文件（通過chat或test script）
- [ ] 可以讀寫文字/JSON檔案
- [ ] （可選）Brave搜索可用（需API key）

---

## 下一步

### 立即測試
1. ✅ 運行 `test_tool_integration.py`
2. ✅ 在Chat測試streaming效果
3. ✅ 嘗試通過chat創建Excel

### 進階配置
1. 設置Brave API Key（搜索功能）
2. 配置Gmail OAuth（郵件功能）
3. 自定義streaming延遲（修改 `asyncio.sleep(0.02)`）

### 開發擴展
1. 添加更多MCP Providers (GitHub, Database, etc.)
2. 實現真正的LLM streaming（當前是post-processing）
3. 添加PDF讀取支援（file_read_pdf）

---

## 文檔

詳細文檔請參考：
- **完整報告:** `docs/STREAMING_AND_PROVIDER_INTEGRATION.md`
- **Excel使用:** `docs/guides/EXCEL_PROVIDER_GUIDE.md`
- **測試腳本:** `testing_scripts/test_tool_integration.py`

---

**Status:** ✅ Ready to Use

**版本:** Streaming + 4 MCP Providers Integration (2024)
