---
name: logic-bug-scan
description: 嚴格檢查代碼邏輯錯誤、狀態異常、Race condition 及錯誤處理。
license: MIT
---

# Skill: Logic Bug Scan

## Workflow Integration

**Before scanning:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing tests or known issues related to the code being scanned.

## 功能
作為資深工程師，對 module / component 進行代碼檢查：
- 邏輯 bug
- 狀態不一致
- Race condition
- 缺少錯誤處理
- 無法到達的代碼
- 錯誤假設

## 輸入
貼上要檢查的 code，例如：
<貼 code 或 repo path>

markdown
複製程式碼

## 輸出格式
- Potential Bugs
- Why it happens
- Severity (Critical / Major / Minor)

## 使用規範
- 假設用戶行為不可預測
- 假設代碼會上生產環境
- 如需要 API 呼叫，請使用：
  `api-reference\read.yaml` / `api-reference\write.yaml`
- 測試可放：
  `test\api-test\頁面/功能/功能_test.js / .py`