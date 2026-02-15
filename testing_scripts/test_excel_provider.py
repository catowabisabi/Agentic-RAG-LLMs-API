"""
Excel Provider 測試腳本

測試 Excel 操作功能是否正常運行。
"""

import asyncio
import sys
from pathlib import Path

# 添加項目路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.excel_service import get_excel_service


async def test_basic_operations():
    """測試基本操作"""
    print("=" * 60)
    print("測試 1: 基本 Excel 操作")
    print("=" * 60)
    
    excel_service = get_excel_service()
    
    # 1. 創建 Excel 文件
    print("\n1️⃣ 創建 Excel 文件...")
    result = await excel_service.create_excel("test_report.xlsx", "TestSheet")
    print(f"   ✓ {result}")
    
    # 2. 寫入數據
    print("\n2️⃣ 寫入數據...")
    data = [
        ["Product", "Price", "Quantity", "Total"],
        ["Apple", 1.2, 100, None],
        ["Banana", 0.5, 200, None],
        ["Orange", 0.8, 150, None]
    ]
    result = await excel_service.write_excel("test_report.xlsx", "TestSheet", data)
    print(f"   ✓ {result}")
    
    # 3. 添加公式
    print("\n3️⃣ 添加公式...")
    for i in range(2, 5):
        result = await excel_service.add_formula(
            "test_report.xlsx", "TestSheet", f"D{i}", f"=B{i}*C{i}"
        )
    print(f"   ✓ 公式已添加")
    
    # 4. 格式化標題行
    print("\n4️⃣ 格式化標題行...")
    result = await excel_service.format_range(
        "test_report.xlsx", "TestSheet", "A1:D1",
        font_bold=True,
        bg_color="4472C4",
        font_color="FFFFFF",
        border=True
    )
    print(f"   ✓ {result}")
    
    # 5. 讀取數據驗證
    print("\n5️⃣ 讀取數據驗證...")
    result = await excel_service.read_excel("test_report.xlsx", "TestSheet")
    print(f"   ✓ 讀取 {result['rows']} 行, {result['cols']} 列")
    print(f"   數據預覽: {result['data'][:2]}")
    
    print("\n✅ 基本操作測試完成!\n")


async def test_table_from_dict():
    """測試從字典創建表格"""
    print("=" * 60)
    print("測試 2: 從字典創建表格")
    print("=" * 60)
    
    excel_service = get_excel_service()
    
    # 準備數據
    sales_data = {
        "日期": ["2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05"],
        "產品": ["蘋果", "香蕉", "橙子", "葡萄", "西瓜"],
        "數量": [100, 200, 150, 80, 120],
        "單價": [1.2, 0.5, 0.8, 2.0, 1.5],
        "總額": [120, 100, 120, 160, 180]
    }
    
    print("\n1️⃣ 創建銷售數據表...")
    result = await excel_service.create_table_from_dict(
        "sales_data.xlsx",
        "Daily Sales",
        sales_data,
        with_header=True
    )
    print(f"   ✓ {result}")
    
    # 添加總計公式
    print("\n2️⃣ 添加總計公式...")
    await excel_service.add_formula(
        "sales_data.xlsx", "Daily Sales", "C7", "=SUM(C2:C6)"
    )
    await excel_service.add_formula(
        "sales_data.xlsx", "Daily Sales", "E7", "=SUM(E2:E6)"
    )
    print(f"   ✓ 總計公式已添加")
    
    # 格式化總計行
    print("\n3️⃣ 格式化總計行...")
    await excel_service.format_range(
        "sales_data.xlsx", "Daily Sales", "A7:E7",
        font_bold=True,
        bg_color="FFC000",
        border=True
    )
    print(f"   ✓ 格式化完成")
    
    print("\n✅ 字典表格測試完成!\n")


async def test_multi_sheet():
    """測試多工作表操作"""
    print("=" * 60)
    print("測試 3: 多工作表操作")
    print("=" * 60)
    
    excel_service = get_excel_service()
    
    # 1. 創建主文件
    print("\n1️⃣ 創建工作簿...")
    await excel_service.create_excel("multi_sheet.xlsx", "Summary")
    print(f"   ✓ 工作簿已創建")
    
    # 2. 添加多個工作表
    print("\n2️⃣ 添加多個工作表...")
    sheets = ["Q1", "Q2", "Q3", "Q4"]
    for sheet in sheets:
        await excel_service.create_sheet("multi_sheet.xlsx", sheet)
        print(f"   ✓ 工作表 '{sheet}' 已創建")
    
    # 3. 在每個工作表寫入數據
    print("\n3️⃣ 寫入季度數據...")
    for i, sheet in enumerate(sheets, 1):
        data = [
            ["Month", "Revenue"],
            [f"Month {i*3-2}", 10000 + i*1000],
            [f"Month {i*3-1}", 12000 + i*1000],
            [f"Month {i*3}", 11000 + i*1000]
        ]
        await excel_service.write_excel("multi_sheet.xlsx", sheet, data)
        print(f"   ✓ {sheet} 數據已寫入")
    
    # 4. 獲取文件資訊
    print("\n4️⃣ 獲取文件資訊...")
    info = await excel_service.get_info("multi_sheet.xlsx")
    print(f"   ✓ 文件名: {info['filename']}")
    print(f"   ✓ 工作表: {', '.join(info['sheets'])}")
    print(f"   ✓ 文件大小: {info['size']} bytes")
    
    print("\n✅ 多工作表測試完成!\n")


async def test_data_analysis():
    """測試數據分析"""
    print("=" * 60)
    print("測試 4: 數據分析")
    print("=" * 60)
    
    excel_service = get_excel_service()
    
    # 準備分析數據
    data = {
        "員工": ["張三", "李四", "王五", "趙六", "錢七"],
        "部門": ["銷售", "技術", "銷售", "技術", "行政"],
        "年齡": [28, 32, 25, 35, 30],
        "薪資": [8000, 12000, 7000, 15000, 6000]
    }
    
    print("\n1️⃣ 創建員工數據表...")
    await excel_service.create_table_from_dict(
        "employee_data.xlsx",
        "Employees",
        data,
        with_header=True
    )
    print(f"   ✓ 員工數據表已創建")
    
    # 分析數據
    print("\n2️⃣ 分析數據...")
    stats = await excel_service.analyze_data(
        "employee_data.xlsx",
        "Employees",
        "A1:D6"
    )
    print(f"   ✓ 總行數: {stats['total_rows']}")
    print(f"   ✓ 總列數: {stats['total_cols']}")
    print(f"   ✓ 有標題: {'是' if stats['has_header'] else '否'}")
    print(f"   ✓ 數據樣本:")
    for row in stats['sample_data']:
        print(f"      {row}")
    
    print("\n✅ 數據分析測試完成!\n")


async def run_all_tests():
    """運行所有測試"""
    print("\n" + "=" * 60)
    print("🚀 Excel Provider 完整測試")
    print("=" * 60 + "\n")
    
    try:
        await test_basic_operations()
        await test_table_from_dict()
        await test_multi_sheet()
        await test_data_analysis()
        
        print("=" * 60)
        print("🎉 所有測試通過!")
        print("=" * 60)
        print("\n生成的文件:")
        print("  - test_report.xlsx")
        print("  - sales_data.xlsx")
        print("  - multi_sheet.xlsx")
        print("  - employee_data.xlsx")
        print("\n請檢查 excel_files/ 目錄查看生成的文件。\n")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
