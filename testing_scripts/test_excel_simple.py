"""
簡化的 Excel Provider 測試

直接測試 Excel Provider，無需其他依賴
"""

import sys
from pathlib import Path

# 添加項目路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.providers.excel_provider import ExcelProvider


def test_excel_provider():
    """測試 Excel Provider 基本功能"""
    print("=" * 60)
    print("🧪 Excel Provider 基本測試")
    print("=" * 60)
    
    # 創建 Provider 實例
    print("\n1️⃣ 初始化 Excel Provider...")
    excel = ExcelProvider(base_path="./excel_files_test")
    print(f"   ✓ Provider 已初始化，基礎路徑: {excel.base_path}")
    
    # 測試 1: 創建工作簿
    print("\n2️⃣ 測試創建工作簿...")
    result = excel.create_workbook("test1.xlsx", "MySheet")
    print(f"   ✓ {result['message']}")
    
    # 測試 2: 寫入數據
    print("\n3️⃣ 測試寫入數據...")
    data = [
        ["Name", "Age", "City"],
        ["Alice", 25, "Beijing"],
        ["Bob", 30, "Shanghai"],
        ["Charlie", 35, "Guangzhou"]
    ]
    result = excel.write_data("test1.xlsx", "MySheet", data, "A1")
    print(f"   ✓ {result['message']}")
    
    # 測試 3: 讀取數據
    print("\n4️⃣ 測試讀取數據...")
    read_data = excel.read_range("test1.xlsx", "MySheet", "A1", "C4")
    print(f"   ✓ 讀取到 {len(read_data)} 行數據")
    print(f"   數據預覽: {read_data[:2]}")
    
    # 測試 4: 添加公式
    print("\n5️⃣ 測試添加公式...")
    result = excel.apply_formula("test1.xlsx", "MySheet", "D1", "=B1+10")
    print(f"   ✓ {result['message']}")
    
    # 測試 5: 格式化單元格
    print("\n6️⃣ 測試格式化...")
    result = excel.format_cells(
        "test1.xlsx", "MySheet", "A1:C1",
        font_bold=True,
        bg_color="4472C4",
        font_color="FFFFFF",
        border=True
    )
    print(f"   ✓ {result['message']}")
    
    # 測試 6: 獲取工作簿資訊
    print("\n7️⃣ 測試獲取資訊...")
    info = excel.get_workbook_info("test1.xlsx")
    print(f"   ✓ 文件名: {info['filename']}")
    print(f"   ✓ 工作表: {info['sheets']}")
    print(f"   ✓ 文件大小: {info['size']} bytes")
    
    # 測試 7: 創建新工作表
    print("\n8️⃣ 測試創建新工作表...")
    result = excel.create_sheet("test1.xlsx", "Sheet2")
    print(f"   ✓ {result['message']}")
    
    # 測試 8: 多工作表寫入
    print("\n9️⃣ 測試多工作表操作...")
    data2 = [
        ["Product", "Price"],
        ["Apple", 1.2],
        ["Banana", 0.5]
    ]
    excel.write_data("test1.xlsx", "Sheet2", data2, "A1")
    print(f"   ✓ Sheet2 數據已寫入")
    
    print("\n" + "=" * 60)
    print("✅ 所有測試通過！")
    print("=" * 60)
    print(f"\n生成的測試文件: {excel.base_path / 'test1.xlsx'}")
    print("\n你可以用 Excel 打開這個文件查看結果。\n")


if __name__ == "__main__":
    try:
        test_excel_provider()
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
