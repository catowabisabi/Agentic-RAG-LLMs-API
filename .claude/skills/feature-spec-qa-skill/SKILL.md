---
name: feature-spec-qa
description: 用來在功能開發前，模擬新手用戶行為，找 UX 與流程問題。
license: MIT
---

# Skill: Feature Spec QA

## Workflow Integration

**Before starting QA analysis:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing tests or specs that might be relevant.

## 功能
當你有一個新功能描述（feature description / PR / README / issue）時，
此 Skill 會：
1. 模擬第一次使用者流程
2. 列出完整步驟
3. 找出：
   - 壞掉流程
   - UX 混亂或不清楚
   - 缺少狀態或提示
   - 未處理邊界情況
4. 預測 bug（不用執行程式碼）
5. 按嚴重性排序：Critical / Major / Minor

## 輸入
貼上功能描述，例如：
<貼上你的功能描述 / PR / README / issue>

r
複製程式碼

## 輸出格式
- User Flow Simulation
- Issues Found (with severity)
- Suggested Fixes (高階建議，不含程式碼)

## 使用規範
- 可在 `todo_list` 建立 TODO 文件：
  `C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\Todo\todo_YYYY_MM_DD.txt`
- 可記錄檢測結果在 `test\api-test\logs\YYYY-MM-DD-HH-mm-ss-logs.txt`