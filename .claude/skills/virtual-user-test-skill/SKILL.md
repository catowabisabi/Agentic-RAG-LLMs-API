---
name: virtual-user-test
description: 功能完成後，模擬非技術用戶試用，找 UX 與使用流程問題。
license: MIT
---

# Skill: Virtual User Test

## Workflow Integration

**Before starting virtual user tests:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing user tests or scripts that can be reused.
2.  **Update References**: If you create a new reusable test script, use the `review-existing-code-references-skill` to add it to the reference file.

## 功能
當 module / component 完成後，讓虛擬用戶：
1. 嘗試使用功能，不知道內部邏輯
2. 描述：
   - 點擊了什麼
   - 預期結果
   - 實際結果
3. 找出任何破碎、不清楚或令人困擾的 UX

**為 Flutter Web App 測試**: 使用 `start_flutter_skill` 啟動應用程式
```bash
# 在獨立 CMD 中快速啟動（3-5秒）
start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"
```
目標 URL: `http://localhost:8899`

## 輸入
貼上 code 或 repo path，例如：
<貼 code 或 repo path>

r
複製程式碼

## 輸出格式
- User actions
- Expected behavior
- Actual behavior
- UX Issues

## 使用規範
- 可放測試檔在：
  `test\api-test\頁面\功能\功能_test.js / .py`
- 每次 log 放在：
  `test\api-test\logs\YYYY-MM-DD-HH-mm-ss-logs.txt`
- 若需要 demo data，可使用：
  `add_demo_data\add_demo_jobs.py`