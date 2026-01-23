---
name: start-flutter
description: 提供快速、可靠的方式啟動 Flutter Web 應用程式於指定端口（8899），支援構建一次後重用，大幅縮短測試時的啟動時間。
---


# Flutter Web App Startup Skill (優化版)

## Workflow Integration

**Before starting Flutter:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing startup scripts or configurations.

## 目的
提供快速、可靠的方式啟動 Flutter Web 應用程式於指定端口（8899），支援構建一次後重用機制，避免每次測試都需要重新編譯，大幅縮短啟動時間。

## 核心功能
- **智能構建管理**: 構建一次後重用，只在需要時重新構建
- **快速啟動**: 後續啟動只需 3-5 秒（vs 原本的 2-5 分鐘）
- **多種模式**: 快速模式、重建模式、開發模式
- **端口管理**: 自動清理端口 8899 上的現有進程
- **Web 伺服器**: 內建 HTTP 伺服器提供構建後的文件
- **CORS 支援**: 自動處理跨域請求問題

## 使用方式

### 快速啟動 (推薦用於測試)
```bash
python test/playwright-test/flutter_quick_start.py
```

### 強制重新構建
```bash
python test/playwright-test/flutter_quick_start.py --rebuild
```

### 開發模式 (熱重載)
```bash
python test/playwright-test/flutter_quick_start.py --dev
```

### 其他選項
```bash
# 自定義端口
python test/playwright-test/flutter_quick_start.py --port 8080

# 查看幫助
python test/playwright-test/flutter_quick_start.py --help
```

### Windows 快速選單
```bash
# 執行批次檔，提供圖形選單
test/playwright-test/flutter_quick_start.bat
```

## 主要組件
1. **優化啟動腳本**: `test/playwright-test/flutter_quick_start.py` (主要工具)
2. **完整版啟動器**: `test/playwright-test/start_flutter.py` (功能更豐富，但啟動較慢)
3. **Windows 選單**: `test/playwright-test/flutter_quick_start.bat`
4. **原批次檔**: `quick_start_scripts/run_flutter_webapp.bat` (開發模式用)

## 技術細節

### 啟動模式比較
| 模式 | 首次啟動 | 後續啟動 | 熱重載 | 用途 |
|------|----------|----------|---------|------|
| 快速模式 | 2-5 分鐘 | **3-5 秒** | ❌ | 測試 |
| 開發模式 | 2-5 分鐘 | 2-5 分鐘 | ✅ | 開發 |

### 構建管理
- **自動檢測**: 檢查 `build/web/` 目錄是否存在
- **時間戳**: 顯示構建時間（X 分鐘前/小時前/天前）
- **智能重用**: 除非明確要求，否則重用現有構建
- **Web 伺服器**: 使用 Python HTTP 伺服器提供靜態文件

### 端口配置
- **固定端口**: 8899 (可自定義)
- **自動清理**: 啟動前自動終止佔用端口的進程
- **CORS 處理**: 自動添加必要的 CORS 標頭

## 整合指南

### 測試 Skills 整合
其他測試相關的 skills 可以透過以下方式整合：

1. **快速啟動應用程式**:
   ```python
   # 在測試開始前執行（快速模式）
   os.system('python test/playwright-test/flutter_quick_start.py')
   ```

2. **等待應用程式就緒**:
   ```python
   # 等待端口 8899 可用
   import time, requests
   for _ in range(30):
       try:
           requests.get('http://localhost:8899', timeout=5)
           break
       except:
           time.sleep(2)
   ```

3. **測試目標 URL**:
   ```
   http://localhost:8899
   ```

### Skill 間協作
- **flutter-user-test**: 自動啟動應用程式後進行用戶測試
- **flutter-page-ui-check**: 檢查特定頁面前確保應用程式運行
- **virtual-user-test**: 功能測試前快速啟動應用程式

## 常見問題

### Q: 什麼時候使用哪種模式？
A: 
- **測試時**: 使用快速模式 (預設)
- **開發時**: 使用開發模式 (`--dev`)
- **代碼改動後**: 使用重建模式 (`--rebuild`)

### Q: 如何確認是否使用了快取構建？
A: 啟動時會顯示「構建狀態: 有 (X 分鐘前)」

### Q: 快速模式和開發模式的差別？
A: 快速模式使用預構建文件，啟動快但無熱重載；開發模式有熱重載但每次啟動都慢。

### Q: 如何清除構建快取？
A: 刪除 `build/` 目錄或使用 `--rebuild` 參數。

## 效能對比

### 啟動時間
- **傳統方式**: 每次 2-5 分鐘
- **快速模式**: 首次 2-5 分鐘，後續 **3-5 秒**
- **效能提升**: 後續啟動快 **95%+**

### 資源使用
- **開發模式**: 高 CPU 使用率 (編譯)
- **快速模式**: 低 CPU 使用率 (靜態伺服器)

## 相依性
- Flutter SDK (版本 3.0+)
- Python 3.7+
- Chrome 瀏覽器
- Windows 環境

## 更新日誌
- **v3.0** (2026-01): 新增快速啟動與構建重用機制
- **v2.0**: CMD 視窗整合，避免 VS Code 終端衝突
- **v1.0**: 初始版本，支援端口 8899 啟動