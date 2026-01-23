---
name: ui-state-loading-check
description: 專門檢查 UI、State、Loading、Disabled 狀態及快速操作問題。
license: MIT
---

# Skill: UI / State / Loading Check

## Workflow Integration

**Before starting UI checks:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing UI tests or scripts that can be reused.
2.  **Update References**: If you create a new reusable test script, use the `review-existing-code-references-skill` to add it to the reference file.

## 功能
檢查 UI 行為：
- Loading states
- Disabled states
- Double-click issues
- 缺少視覺提示
- State 未更新（成功/失敗後）

**為 Flutter Web App 測試**: 使用 `start_flutter_skill` 啟動應用程式
```bash
# 在獨立 CMD 中快速啟動（3-5秒）
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"
```
目標 URL: `http://localhost:8899`

## 模擬情況
- 慢網絡
- 用戶快速點擊
- 用戶中途離開操作

## 輸入
貼上 code 或 component，例如：
<貼 code 或 repo path>

markdown
複製程式碼

## 輸出格式
- UI/UX Failures
- Steps to Reproduce
- Severity

## 使用規範
- 適合 React / Flutter
- 測試放：
  `test\api-test\頁面/功能/功能_test.js / .py`
- Log 存：
  `test\api-test\logs\YYYY-MM-DD-HH-mm-ss-logs.txt`