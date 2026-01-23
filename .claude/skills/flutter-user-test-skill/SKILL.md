---
name: flutter-user-test
description: 使用 Playwright 對 Flutter Web App 進行完整虛擬用戶測試。自動啟動 App、等待正確 Port、登入、檢查所有頁面的 AppBar、Drawer、資料、子頁、可互動按鈕，並記錄所有操作與問題。
license: MIT
---

# Skill: Flutter User Test

## Workflow Integration

**Before starting user tests:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing user tests or scripts that can be reused.
2.  **Update References**: If you create a new reusable test script, use the `review-existing-code-references-skill` to add it to the reference file.

## 功能
此 Skill 整合多個測試能力，對 Flutter Web App 進行完整的虛擬用戶測試：

**⚡ 快速啟動**: 建議使用優化版 `start_flutter_skill` 來啟動 Flutter Web App 於端口 8899
```bash
# 在獨立 CMD 中快速啟動（3-5秒）
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"

# 或使用 Windows 選單
test/playwright-test/flutter_quick_start.bat
```

1. **自動啟動 Flutter Web App** - 使用優化版 `start_flutter_skill` 的快速啟動模式
2. **等待 App 載入** - 從終端輸出提取正確的 Port
3. **模擬真實用戶** - 使用指定帳號登入
4. **完整 UI 檢查**：
   - AppBar（標題、返回鍵、動作按鈕）
   - Drawer / BottomNavigationBar
   - 頁面資料載入狀態
   - 子頁面導航
   - 所有可互動按鈕
5. **記錄所有操作與問題**

## 使用流程

### Step 1: 啟動 Flutter Web App
**建議方式** (使用優化版 start_flutter_skill):
```bash
# 在獨立 CMD 中快速啟動
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"
```

**或使用批次檔**:
```bash
# 使用圖形選單
test/playwright-test/flutter_quick_start.bat
```

**目標 URL**: `http://localhost:8899`

### Step 2: 等待 App 載入並提取 Port
從終端輸出尋找類似：
```
The Flutter DevTools debugger and profiler is available at: http://127.0.0.1:9100
Launching lib\main.dart on Chrome at http://localhost:XXXXX
```
提取 `localhost:XXXXX` 的實際 Port。

### Step 3: 執行測試腳本
```powershell
cd test\api-test\flutter-user-test
node test-user-flow.js --port=XXXXX --user=demo2 --password=demo123
```

## 測試項目清單

### 1. 頁面結構檢查
```javascript
const pageChecklist = {
  appBar: {
    title: '檢查標題是否顯示',
    backButton: '檢查返回按鈕（非首頁）',
    actions: '檢查右側動作按鈕',
  },
  drawer: {
    exists: '檢查 Drawer 是否存在',
    menuItems: '檢查選單項目',
    userInfo: '檢查用戶資訊顯示',
  },
  bottomNav: {
    exists: '檢查底部導航列',
    items: '檢查導航項目',
    activeState: '檢查當前選中狀態',
  },
  content: {
    loading: '檢查載入狀態',
    data: '檢查資料是否載入',
    empty: '檢查空狀態處理',
    error: '檢查錯誤狀態處理',
  }
};
```

### 2. 互動元素檢查
```javascript
const interactionChecklist = {
  buttons: '所有按鈕可點擊',
  forms: '表單可輸入與提交',
  lists: '列表項目可點擊',
  dialogs: '對話框可開啟與關閉',
  pullToRefresh: '下拉刷新功能',
  scroll: '滾動行為正常',
};
```

### 3. 狀態檢查
```javascript
const stateChecklist = {
  loading: '載入中顯示 Loading 指示器',
  disabled: '操作中按鈕 disabled',
  doubleClick: '防止重複點擊',
  feedback: '操作後有視覺回饋',
  stateUpdate: '成功/失敗後狀態更新',
};
```

## 頁面路由清單

```javascript
const routes = {
  // 認證
  login: '/nodebb/login',
  register: '/nodebb/register',
  
  // 論壇
  forumHome: '/nodebb/home',
  category: '/nodebb/category?cid=1',
  topic: '/nodebb/topic?tid=1',
  createTopic: '/nodebb/create-topic',
  search: '/nodebb/search',
  
  // 個人
  profile: '/nodebb/profile',
  editProfile: '/nodebb/edit-profile',
  notifications: '/nodebb/notifications',
  settings: '/nodebb/settings',
  history: '/nodebb/history',
  
  // 生活服務
  housing: '/life-services/housing',
  jobs: '/life-services/jobs',
  services: '/life-services/services',
  flyers: '/life-services/flyers',
  bookmarks: '/life-services/bookmarks',
};
```

## 輸出格式

### User Action Log
```
[時間戳] [頁面] [動作] [預期結果] [實際結果] [狀態]
```

### Issue Report
```
頁面: /nodebb/home
問題: Drawer 開啟後無法關閉
嚴重性: Critical
重現步驟:
  1. 點擊左上角漢堡選單
  2. Drawer 開啟
  3. 點擊遮罩層
預期: Drawer 關閉
實際: Drawer 保持開啟
```

## 檔案位置

### 測試腳本
```
test\api-test\flutter-user-test\test-user-flow.js
test\api-test\flutter-user-test\page-inspector.js
test\api-test\flutter-user-test\interaction-tester.js
```

### 日誌輸出
```
test\api-test\logs\YYYY-MM-DD-HH-mm-ss-user-test-logs.txt
test\api-test\logs\screenshots\*.png
```

### Todo 輸出
```
Todo\todo_YYYY_MM_DD.txt
```

## Flutter Web 元素選擇器

Flutter Web 使用 Semantics，常用選擇器：

```javascript
// 文字元素
await page.getByText('登入');

// Role-based
await page.getByRole('button', { name: '登入' });

// Aria label
await page.locator('[aria-label="返回"]');

// Flutter semantics
await page.locator('flt-semantics-placeholder');

// 座標點擊（最後手段）
await page.mouse.click(x, y);
```

## 等待 Flutter 載入

```javascript
async function waitForFlutterLoad(page, timeout = 15000) {
  // 等待 Flutter 容器
  await page.waitForSelector('flt-glass-pane, flutter-view', { timeout });
  
  // 額外等待初始化
  await page.waitForTimeout(2000);
  
  // 檢查是否有載入中指示器
  const hasLoading = await page.locator('.loading, [aria-busy="true"]').count();
  if (hasLoading > 0) {
    await page.waitForSelector('.loading, [aria-busy="true"]', { state: 'hidden', timeout });
  }
}
```

## 提取 Flutter Console Port

```javascript
function extractPortFromOutput(output) {
  // 尋找 "http://localhost:XXXXX" 模式
  const match = output.match(/http:\/\/localhost:(\d+)/);
  if (match) {
    return parseInt(match[1], 10);
  }
  return null;
}
```

## 完整測試流程

```javascript
async function runFullUserTest(config) {
  const { port, username, password } = config;
  const baseUrl = `http://localhost:${port}`;
  
  // 1. 啟動瀏覽器
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // 2. 登入
  await page.goto(`${baseUrl}/#/nodebb/login`);
  await waitForFlutterLoad(page);
  await performLogin(page, username, password);
  
  // 3. 逐頁測試
  for (const [name, route] of Object.entries(routes)) {
    await testPage(page, baseUrl, name, route);
  }
  
  // 4. 生成報告
  await generateReport();
  
  await browser.close();
}
```

## 使用規範

1. **必須使用 `quick_start_scripts\run_flutter_webapp.bat`** 啟動 App
2. **必須等待終端輸出** 取得正確 Port
3. **必須記錄所有操作** 到 logs
4. **必須截圖** 每個頁面
5. **必須檢查** AppBar、Drawer、Content、Buttons
6. **必須報告** 所有 UX 問題

## 相關 Skills

- `virtual-user-test` - 虛擬用戶測試流程
- `flutter-page-ui-check` - Flutter UI 檢查
- `ui-state-loading-check` - 狀態檢查
- `webapp-testing` - Playwright 基礎

## API 參考

如需呼叫後端 API：
- `api-reference\read.yaml`
- `api-reference\write.yaml`
