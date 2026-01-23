---
name: nodebb-life-services-controller
description: >
  控制與擴充 NodeBB Plugin Life Services，
  並整合 Flutter App、本地 CORS Proxy、NodeBB 官方 API。
  本 Skill 定義 API 參考優先順序、Demo Data、測試規範、
  Plugin 更新流程、Todo / Log 規則。
license: MIT
---

## 🔴 API 使用最高優先規則（必須）

### Workflow Integration

**Before starting any controller work:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing controller logic, tests, or scripts.
2.  **Update References**: If you create a new reusable script or controller logic, use the `review-existing-code-references-skill` to add it to the reference file.

如需新增或修改任何 NodeBB 功能：

### ✅ 必須先參考以下文件
- api-reference\read.yaml
- api-reference\write.yaml

❌ 不可在未檢查 API 文件情況下：
- 猜測 endpoint
- 自行設計未定義 API
- 直接改 NodeBB Core 行為

---

## 🧪 Demo Data 規則（嚴格）

如需加入 demo data：

### 📁 只可使用 Python
- 資料夾：add_demo_data\
- 檔案範例：add_demo_data\add_demo_jobs.py


### 規則
- 必須參考既有格式與結構
- 不可將 demo data 寫死於 Plugin 或 Flutter UI
- Demo Data 只作測試用途

---

## 🎨 Logo 使用規範

如需使用 Logo：
- 白色 Logo：assets\images\logo.png
- 灰色 Logo：assets\images\logo2.png

❌ 不可新增其他 Logo  
❌ 不可改動原圖

---

## 🔐 測試帳戶（僅限測試）

### 👤 一般用戶（User）
- id: demo2
- password: demo123

### 🛡 管理員（Admin）
- id: demo3
- password: demo123

⚠️ 僅用於：
- 登入介面測試
- API 呼叫測試

❌ 不可用於 production data

---

## 🧩 Life Services Plugin 修改規則（非常重要）

### 📄 Plugin 來源檔案
NodeBB-Plugin-Life-Services-Folder\library.js

### 修改規則
- 所有 Life Services API 修改 **只可改此檔**
- 不可分散到其他檔案
- 不可直接改 container 內檔案

---

## 🚀 Plugin 更新與部署流程（固定）

### 本機檔案位置
C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App
NodeBB-Plugin-Life-Services-Folder\library.js

### VPS 目標位置
/srv/nodebb/nodebb-plugin-life-services-updated/library.js

### Project Root
/srv/nodebb#

### SSH 登入方法
ssh root@31.97.9.151 
password: Good4me1986.


### 更新流程（順序不可錯）
1. 更新本機 `library.js`
2. 上傳至 VPS 專案目錄
3. 執行：root@vps:/srv/nodebb/sync-plugin.sh

## ▶️ Flutter App 重啟規則（必須）

每次修改 Plugin 或 API 後，**必須執行以下兩個 batch：**
quick_start_scripts\run_flutter_webapp.bat
quick_start_scripts\run_flutter_wifi_same_ip.bat

如出錯：
- 必須修正
- 不可忽略錯誤繼續測試

---

## 🧪 API / 功能測試規範（強制）

如建立新功能或測試功能：

### 📁 測試位置
test\api-test\

### 命名規則
test\api-test<頁面><功能><功能>_test.js
test\api-test<頁面><功能><功能>_test.py

### 範例
test\api-test\life-services\housing\test-housing.js
test\api-test\life-services\jobs\add_job\test-add_jobs.py


---

## 📝 Todo List 規範（更新）

### 📁 位置
todo_list\

### 📄 檔名格式
YYYY-MM-DD-HH-mm-ss-todo.md

### 內容要求
- 列出：
  - ✅ 已完成
  - ⏳ 未完成
- 每次工作必須對應一份 Todo

---

## 📄 Log 規範（更新）

### 📁 位置
test\api-test\logs\

### 📄 檔名格式
YYYY-MM-DD-HH-mm-ss-logs.txt

### 內容要求
- 記錄：
  - 成功操作
  - 失敗原因
  - 尚未完成事項

---

## 📚 Refactor 規範

如涉及結構重整或重構：

- 必須參考：
reference\REFACTOR_GUIDE.md

❌ 不可自行重構
❌ 不可破壞既有 API 相容性

---

## 🤖 Agent 行為最終約束摘要
- API → 先查 YAML
- Demo data → Python only
- Plugin → 只改 library.js
- 改完 → sync-plugin.sh
- 再跑 Flutter scripts
- 功能一定要有 test
- 每次一定有 todo + log
