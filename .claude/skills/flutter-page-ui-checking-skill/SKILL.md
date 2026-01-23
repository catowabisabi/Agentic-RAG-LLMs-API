---
name: flutter-page-ui-check
description: 使用 JS + Playwright / Selenium，自動檢查 Flutter Web App 特定頁面及其子頁面 UI / State / Loading。
license: MIT
---

# Skill: Flutter Page UI Check

## Workflow Integration

**Before starting any new UI check:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing UI tests or scripts that can be reused.
2.  **Update References**: If you create a new reusable test script, use the `review-existing-code-references-skill` to add it to the reference file.

## 功能
此 Skill 用於：
1. 指定 Flutter Web App 頁面及其子頁面進行 UI / State / Loading 檢查
2. 自動模擬用戶操作，捕捉錯誤和異常行為
3. 支援慢網路、快速點擊、跳頁等情況
4. 將檢測結果自動生成到 logs 與 todo list

## 適用場景
- Flutter Web App
- React / Angular / Vue 網頁也可使用 Playwright / Selenium

## 測試流程
**建議啟動方式** (使用優化版 start_flutter_skill):
```bash
# 在獨立 CMD 中快速啟動（3-5秒）
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"

# 或使用 Windows 選單
test/playwright-test/flutter_quick_start.bat
```
目標 URL: `http://localhost:8899`

**或使用開發模式**:
```bash
# 開發模式（熱重載）
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py --dev"
```

2. 自動訪問主頁及指定子頁面

## 檢查以下項目：

- Loading states

- Disabled states

- Double-click issues

- Missing visual feedback

- State 未更新（操作成功或失敗後）

- 支援慢網路、快速點擊、跳頁測試

## 將測試結果生成：

Logs: test\api-test\logs\YYYY-MM-DD-HH-mm-ss-logs.txt
Todo: C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\Todo\todo_YYYY_MM_DD.txt

## JS / Playwright 範例

const { chromium } = require('playwright');
const fs = require('fs');
const dateTime = new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 主頁
  await page.goto('http://localhost:5000');

  // 檢查特定元素
  const logs = [];
  try {
    await page.waitForSelector('#main-content', { timeout: 5000 });
    logs.push('Main content loaded ✅');
  } catch {
    logs.push('Main content not loaded ❌');
  }

  // 子頁面列表
  const subPages = [
    '/dashboard',
    '/settings',
    '/profile'
  ];

  for (const path of subPages) {
    await page.goto(`http://localhost:5000${path}`);
    try {
      await page.waitForSelector('#page-root', { timeout: 5000 });
      logs.push(`${path} loaded ✅`);
    } catch {
      logs.push(`${path} failed to load ❌`);
    }
  }

  // 寫入 log
  const logPath = `test/api-test/logs/${dateTime}-logs.txt`;
  fs.writeFileSync(logPath, logs.join('\n'), 'utf-8');
  console.log(`Logs saved to ${logPath}`);

  await browser.close();
})();


## 使用規範
### Flutter App Root:
- C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\

## 測試檔放置：
test\api-test\flutter-page-ui-check\test-ui.js

## 若需要呼叫 NodeBB API，請使用：
api-reference\read.yaml / api-reference\write.yaml

## Todo list 更新：
C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\Todo\todo_YYYY_MM_DD.txt

## 日誌保存：
test\api-test\logs\YYYY-MM-DD-HH-mm-ss-logs.txt