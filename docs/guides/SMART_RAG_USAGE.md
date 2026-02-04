# 智能 RAG 搜索 API 測試

## 測試三種模式

### 1. 智能路由模式（Auto）
```bash
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SolidWorks API 使用方法",
    "mode": "auto",
    "top_k": 5
  }'
```

預期：AI 自動選擇 `solidworks` 數據庫並返回相關結果

### 2. 多數據庫模式（Multi）
```bash
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python trading bot",
    "mode": "multi",
    "top_k": 3
  }'
```

預期：搜索所有數據庫，返回合併結果

### 3. 手動選擇模式（Manual）
```bash
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "agentic workflow examples",
    "mode": "agentic-example",
    "top_k": 5
  }'
```

預期：只搜索 `agentic-example` 數據庫

## UI 使用說明

1. 打開 http://localhost:1131/rag
2. 選擇三種模式之一：
   - **智能路由**：讓 AI 自動選擇最佳數據庫
   - **多數據庫**：搜索所有數據庫
   - **手動選擇**：從下拉清單選擇特定數據庫
3. 輸入問題，點擊搜索
4. 查看結果，包含來源數據庫信息

## API 返回格式

```json
{
  "query": "用戶問題",
  "mode": "auto/multi/single",
  "selected_databases": ["database1", "database2"],
  "reasoning": "AI 選擇原因（僅 auto 模式）",
  "database_counts": {
    "database1": 3,
    "database2": 2
  },
  "results": [
    {
      "content": "文檔內容",
      "score": 0.85,
      "source_database": "solidworks",
      "database_description": "SolidWorks 完整文檔",
      "metadata": {
        "title": "文檔標題",
        "category": "technical"
      }
    }
  ],
  "count": 5
}
```

## 整合到其他應用

### Python
```python
import requests

def smart_rag_search(query, mode="auto"):
    response = requests.post(
        "http://localhost:1130/rag/smart-query",
        json={"query": query, "mode": mode, "top_k": 5}
    )
    return response.json()

# 使用
result = smart_rag_search("SolidWorks API", mode="auto")
print(f"找到 {result['count']} 個結果")
for r in result['results']:
    print(f"- {r['content'][:100]}... (來源: {r['source_database']})")
```

### JavaScript/TypeScript
```typescript
async function smartRAGSearch(query: string, mode: string = 'auto') {
  const response = await fetch('http://localhost:1130/rag/smart-query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, mode, top_k: 5 })
  });
  return await response.json();
}

// 使用
const result = await smartRAGSearch('SolidWorks API', 'auto');
console.log(`找到 ${result.count} 個結果`);
```

### cURL
```bash
# 智能路由
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query":"你的問題","mode":"auto"}'

# 多數據庫
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query":"你的問題","mode":"multi"}'

# 指定數據庫
curl -X POST http://localhost:1130/rag/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query":"你的問題","mode":"solidworks"}'
```
