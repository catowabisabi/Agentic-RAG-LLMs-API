# Excel Provider 使用指南

## 功能概述

Excel Provider 提供了完整的 Excel 文件操作能力，讓 LLM Agent 可以：
- 創建和管理 Excel 工作簿
- 讀寫數據
- 應用公式
- 格式化單元格
- 工作表管理

## 安裝依賴

```bash
pip install openpyxl>=3.1.5
```

或更新整個環境：
```bash
pip install -r docker/requirements.txt
```

## 快速開始

### 1. 直接使用 ExcelService

```python
from services.excel_service import get_excel_service

# 獲取服務實例
excel_service = get_excel_service()

# 創建新的 Excel 文件
await excel_service.create_excel("report.xlsx", "Sales Data")

# 寫入數據
data = [
    ["Product", "Price", "Quantity"],
    ["Apple", 1.2, 100],
    ["Banana", 0.5, 200],
    ["Orange", 0.8, 150]
]
await excel_service.write_excel("report.xlsx", "Sales Data", data)

# 添加公式計算總計
await excel_service.add_formula("report.xlsx", "Sales Data", "D2", "=B2*C2")
await excel_service.add_formula("report.xlsx", "Sales Data", "D3", "=B3*C3")
await excel_service.add_formula("report.xlsx", "Sales Data", "D4", "=B4*C4")

# 格式化標題行
await excel_service.format_range(
    "report.xlsx", "Sales Data", "A1:D1",
    font_bold=True,
    bg_color="4472C4",
    font_color="FFFFFF",
    border=True
)

# 讀取數據
result = await excel_service.read_excel("report.xlsx", "Sales Data")
print(f"Read {result['rows']} rows, {result['cols']} columns")
```

### 2. 在 Tool Agent 中註冊

```python
# 在 agents/auxiliary/tool_agent.py 中

from mcp.providers.excel_provider import ExcelProvider

class ToolAgent(BaseAgent):
    def __init__(self, ...):
        # ...existing code...
        
        # 初始化 Excel Provider
        self.excel_provider = ExcelProvider(base_path="./excel_files")
        
        # 註冊 Excel 工具
        self._register_excel_tools()
    
    def _register_excel_tools(self):
        """註冊 Excel 相關工具"""
        
        # 創建 Excel 文件
        self.register_tool(
            name="create_excel",
            description="Create a new Excel workbook",
            parameters={"filepath": "string", "sheet_name": "string"},
            handler=self._excel_create_handler
        )
        
        # 讀取 Excel 數據
        self.register_tool(
            name="read_excel",
            description="Read data from Excel file",
            parameters={"filepath": "string", "sheet_name": "string", "start_cell": "string", "end_cell": "string"},
            handler=self._excel_read_handler
        )
        
        # 寫入 Excel 數據
        self.register_tool(
            name="write_excel",
            description="Write data to Excel file",
            parameters={"filepath": "string", "sheet_name": "string", "data": "array", "start_cell": "string"},
            handler=self._excel_write_handler
        )
        
        # 應用公式
        self.register_tool(
            name="excel_formula",
            description="Apply Excel formula to a cell",
            parameters={"filepath": "string", "sheet_name": "string", "cell": "string", "formula": "string"},
            handler=self._excel_formula_handler
        )
    
    async def _excel_create_handler(self, filepath: str, sheet_name: str = "Sheet1") -> str:
        """創建 Excel 文件處理器"""
        try:
            result = self.excel_provider.create_workbook(filepath, sheet_name)
            return f"Created: {result['message']}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def _excel_read_handler(
        self, 
        filepath: str, 
        sheet_name: str, 
        start_cell: str = "A1", 
        end_cell: str = None
    ) -> str:
        """讀取 Excel 數據處理器"""
        try:
            data = self.excel_provider.read_range(filepath, sheet_name, start_cell, end_cell)
            return f"Read {len(data)} rows: {data}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def _excel_write_handler(
        self, 
        filepath: str, 
        sheet_name: str, 
        data: list, 
        start_cell: str = "A1"
    ) -> str:
        """寫入 Excel 數據處理器"""
        try:
            result = self.excel_provider.write_data(filepath, sheet_name, data, start_cell)
            return result['message']
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def _excel_formula_handler(
        self, 
        filepath: str, 
        sheet_name: str, 
        cell: str, 
        formula: str
    ) -> str:
        """應用公式處理器"""
        try:
            result = self.excel_provider.apply_formula(filepath, sheet_name, cell, formula)
            return result['message']
        except Exception as e:
            return f"Error: {str(e)}"
```

### 3. 在 LLM 對話中使用

用戶可以這樣提問：

```
用戶: 幫我創建一個 Excel 文件，記錄這個月的銷售數據
LLM: [使用 create_excel 工具]

用戶: 在 A1 到 C1 寫入標題：產品、價格、數量
LLM: [使用 write_excel 工具]

用戶: 在 A2 寫入"蘋果"，B2 寫入 1.2，C2 寫入 100
LLM: [使用 write_excel 工具]

用戶: 在 D2 添加公式計算總價（價格*數量）
LLM: [使用 excel_formula 工具，formula="=B2*C2"]

用戶: 把標題行變成粗體，背景色設置為藍色
LLM: [使用 format_cells 工具]
```

## 進階用法

### 1. 批量創建報表

```python
from services.excel_service import get_excel_service

async def create_monthly_report(month: str, sales_data: dict):
    """創建月度銷售報表"""
    excel_service = get_excel_service()
    
    filename = f"sales_report_{month}.xlsx"
    
    # 使用字典直接創建表格
    await excel_service.create_table_from_dict(
        filename=filename,
        sheet_name="Sales",
        data_dict=sales_data,
        with_header=True
    )
    
    # 添加統計
    await excel_service.add_formula(
        filename, "Sales", "B10", "=SUM(B2:B9)"
    )
    
    # 格式化
    await excel_service.format_range(
        filename, "Sales", "A1:D1",
        font_bold=True,
        bg_color="4472C4",
        font_color="FFFFFF"
    )
    
    return f"Report created: {filename}"

# 使用示例
sales_data = {
    "Product": ["Apple", "Banana", "Orange"],
    "Price": [1.2, 0.5, 0.8],
    "Quantity": [100, 200, 150]
}

await create_monthly_report("2026-02", sales_data)
```

### 2. 數據分析

```python
async def analyze_sales_data(filename: str):
    """分析銷售數據"""
    excel_service = get_excel_service()
    
    # 讀取數據
    data = await excel_service.read_excel(filename, "Sales", "A1", "D10")
    
    # 統計分析
    stats = await excel_service.analyze_data(filename, "Sales", "A1:D10")
    
    print(f"Total rows: {stats['total_rows']}")
    print(f"Total columns: {stats['total_cols']}")
    print(f"Sample data: {stats['sample_data']}")
    
    return stats
```

## 常見使用場景

### 場景 1: 數據導出
```python
# 從數據庫或 API 獲取數據後導出為 Excel
async def export_to_excel(data_list: list, filename: str):
    excel_service = get_excel_service()
    
    # 轉換數據格式
    rows = [
        ["ID", "Name", "Email", "Created"],
        *[[item['id'], item['name'], item['email'], item['created']] for item in data_list]
    ]
    
    await excel_service.write_excel(filename, "Users", rows)
    return filename
```

### 場景 2: 自動化報表生成
```python
# 定期生成報表
async def generate_weekly_report():
    excel_service = get_excel_service()
    
    filename = f"weekly_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    # 創建多個工作表
    await excel_service.create_excel(filename, "Summary")
    await excel_service.create_sheet(filename, "Details")
    await excel_service.create_sheet(filename, "Charts")
    
    # 寫入數據到各個工作表
    # ...
    
    return filename
```

### 場景 3: 數據清洗和轉換
```python
# 讀取舊 Excel，清洗數據，寫入新 Excel
async def clean_excel_data(input_file: str, output_file: str):
    excel_service = get_excel_service()
    
    # 讀取
    data = await excel_service.read_excel(input_file, "Sheet1")
    
    # 清洗（去除空行、格式化）
    cleaned = [row for row in data['data'] if any(cell is not None for cell in row)]
    
    # 寫入新文件
    await excel_service.write_excel(output_file, "Cleaned", cleaned)
    
    return output_file
```

## API 參考

### ExcelService 方法

| 方法 | 參數 | 返回 | 說明 |
|------|------|------|------|
| `create_excel` | filename, sheet_name | str | 創建新 Excel 文件 |
| `read_excel` | filename, sheet_name, start_cell, end_cell | Dict | 讀取數據 |
| `write_excel` | filename, sheet_name, data, start_cell | str | 寫入數據 |
| `add_formula` | filename, sheet_name, cell, formula | str | 添加公式 |
| `format_range` | filename, sheet_name, cell_range, **styles | str | 格式化 |
| `get_info` | filename | Dict | 獲取文件資訊 |
| `create_sheet` | filename, sheet_name | str | 創建工作表 |
| `create_table_from_dict` | filename, sheet_name, data_dict | str | 從字典創建表格 |
| `analyze_data` | filename, sheet_name, data_range | Dict | 分析數據 |

### 格式化選項

```python
await excel_service.format_range(
    filename="report.xlsx",
    sheet_name="Sheet1",
    cell_range="A1:D10",
    font_name="Arial",          # 字體名稱
    font_size=12,               # 字體大小
    font_bold=True,             # 粗體
    font_color="FF0000",        # 字體顏色 (紅色)
    bg_color="FFFF00",          # 背景顏色 (黃色)
    border=True                 # 邊框
)
```

## 注意事項

1. **文件路徑**: 默認基於 `excel_files/` 目錄，可以使用相對路徑或絕對路徑
2. **公式格式**: 公式可以帶或不帶 `=` 前綴，系統會自動處理
3. **顏色格式**: 使用 6 位 HEX 格式，不帶 `#` 符號（如 `"FF0000"` 表示紅色）
4. **單元格地址**: 使用 Excel 標準格式（如 `"A1"`, `"B2:D10"`）
5. **錯誤處理**: 所有方法都包含錯誤處理，會返回錯誤消息而不是拋出異常

## 故障排除

### 問題 1: 找不到文件
```python
# 確認文件路徑
excel_service = get_excel_service(base_path="./your/custom/path")
```

### 問題 2: 公式不計算
```python
# Excel 文件需要在 Excel 程序中打開才會自動計算
# 或者在讀取時使用 data_only=False
```

### 問題 3: 中文亂碼
```python
# openpyxl 默認支持 UTF-8，應該沒有中文問題
# 如果出現，檢查數據源編碼
```
