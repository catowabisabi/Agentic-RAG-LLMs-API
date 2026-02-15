"""
Excel Service

高層次的 Excel 操作服務，供 Agents 使用。
提供 LLM 友好的接口來操作 Excel 文件。
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from mcp.providers.excel_provider import ExcelProvider, ExcelProviderError

logger = logging.getLogger(__name__)


class ExcelService:
    """Excel 操作服務（單例）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, base_path: Optional[str] = None):
        if self._initialized:
            return
            
        # 默認使用項目根目錄下的 excel_files 文件夾
        if base_path is None:
            base_path = Path.cwd() / "excel_files"
        
        self.provider = ExcelProvider(base_path=str(base_path))
        self._initialized = True
        
        logger.info(f"ExcelService initialized with base_path: {base_path}")
    
    # ========================================
    # 便捷方法（供 LLM/Agent 使用）
    # ========================================
    
    async def create_excel(
        self, 
        filename: str, 
        sheet_name: str = "Sheet1"
    ) -> str:
        """
        創建新的 Excel 文件
        
        Args:
            filename: 文件名 (如 "report.xlsx")
            sheet_name: 初始工作表名稱
            
        Returns:
            操作結果消息
        """
        try:
            result = self.provider.create_workbook(filename, sheet_name)
            return result["message"]
        except ExcelProviderError as e:
            logger.error(f"Failed to create Excel: {e}")
            return f"Error: {e}"
    
    async def read_excel(
        self,
        filename: str,
        sheet_name: str,
        start_cell: str = "A1",
        end_cell: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        讀取 Excel 數據
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            start_cell: 起始單元格
            end_cell: 結束單元格 (可選)
            
        Returns:
            {"data": List[List], "rows": int, "cols": int}
        """
        try:
            data = self.provider.read_range(
                filename, sheet_name, start_cell, end_cell
            )
            return {
                "data": data,
                "rows": len(data),
                "cols": len(data[0]) if data else 0
            }
        except ExcelProviderError as e:
            logger.error(f"Failed to read Excel: {e}")
            return {"error": str(e), "data": []}
    
    async def write_excel(
        self,
        filename: str,
        sheet_name: str,
        data: List[List[Any]],
        start_cell: str = "A1"
    ) -> str:
        """
        寫入數據到 Excel
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            data: 二維數組數據
            start_cell: 起始單元格
            
        Returns:
            操作結果消息
        """
        try:
            result = self.provider.write_data(
                filename, sheet_name, data, start_cell
            )
            return result["message"]
        except ExcelProviderError as e:
            logger.error(f"Failed to write Excel: {e}")
            return f"Error: {e}"
    
    async def add_formula(
        self,
        filename: str,
        sheet_name: str,
        cell: str,
        formula: str
    ) -> str:
        """
        添加公式到單元格
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            cell: 單元格地址 (如 "A1")
            formula: Excel 公式 (如 "SUM(A1:A10)" 或 "=SUM(A1:A10)")
            
        Returns:
            操作結果消息
        """
        try:
            result = self.provider.apply_formula(
                filename, sheet_name, cell, formula
            )
            return result["message"]
        except ExcelProviderError as e:
            logger.error(f"Failed to add formula: {e}")
            return f"Error: {e}"
    
    async def format_range(
        self,
        filename: str,
        sheet_name: str,
        cell_range: str,
        **style_kwargs
    ) -> str:
        """
        格式化單元格範圍
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            cell_range: 單元格範圍 (如 "A1:D10")
            **style_kwargs: 樣式參數
                - font_name: 字體名稱
                - font_size: 字體大小
                - font_bold: 粗體 (True/False)
                - font_color: 字體顏色 (HEX, 如 "FF0000")
                - bg_color: 背景顏色 (HEX, 如 "FFFF00")
                - border: 邊框 (True/False)
            
        Returns:
            操作結果消息
        """
        try:
            result = self.provider.format_cells(
                filename, sheet_name, cell_range, **style_kwargs
            )
            return result["message"]
        except ExcelProviderError as e:
            logger.error(f"Failed to format cells: {e}")
            return f"Error: {e}"
    
    async def get_info(self, filename: str) -> Dict[str, Any]:
        """
        獲取 Excel 文件資訊
        
        Args:
            filename: 文件名
            
        Returns:
            文件資訊字典
        """
        try:
            return self.provider.get_workbook_info(filename)
        except ExcelProviderError as e:
            logger.error(f"Failed to get Excel info: {e}")
            return {"error": str(e)}
    
    async def create_sheet(
        self, 
        filename: str, 
        sheet_name: str
    ) -> str:
        """
        創建新工作表
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            
        Returns:
            操作結果消息
        """
        try:
            result = self.provider.create_sheet(filename, sheet_name)
            return result["message"]
        except ExcelProviderError as e:
            logger.error(f"Failed to create sheet: {e}")
            return f"Error: {e}"
    
    # ========================================
    # LLM 專用操作（自動化場景）
    # ========================================
    
    async def create_table_from_dict(
        self,
        filename: str,
        sheet_name: str,
        data_dict: Dict[str, List],
        start_cell: str = "A1",
        with_header: bool = True
    ) -> str:
        """
        從字典創建表格（自動添加標題行）
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            data_dict: 數據字典 {"列名": [值1, 值2, ...]}
            start_cell: 起始單元格
            with_header: 是否添加標題行
            
        Returns:
            操作結果消息
            
        Example:
            data = {
                "Name": ["Alice", "Bob", "Charlie"],
                "Age": [25, 30, 35],
                "City": ["NY", "LA", "SF"]
            }
            await excel_service.create_table_from_dict(
                "people.xlsx", "Sheet1", data
            )
        """
        try:
            # 轉換字典為二維數組
            headers = list(data_dict.keys())
            rows = []
            
            if with_header:
                rows.append(headers)
            
            # 轉置數據
            num_rows = len(next(iter(data_dict.values())))
            for i in range(num_rows):
                row = [data_dict[col][i] for col in headers]
                rows.append(row)
            
            result = self.provider.write_data(
                filename, sheet_name, rows, start_cell
            )
            
            # 如果有標題，格式化標題行
            if with_header:
                from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
                col_letter, row_num = coordinate_from_string(start_cell)
                start_col = column_index_from_string(col_letter)
                end_col_letter = chr(ord(col_letter) + len(headers) - 1)
                header_range = f"{start_cell}:{end_col_letter}{row_num}"
                
                self.provider.format_cells(
                    filename, sheet_name, header_range,
                    font_bold=True,
                    bg_color="D3D3D3",
                    border=True
                )
            
            return f"Table created successfully with {len(rows)} rows"
            
        except Exception as e:
            logger.error(f"Failed to create table from dict: {e}")
            return f"Error: {e}"
    
    async def analyze_data(
        self,
        filename: str,
        sheet_name: str,
        data_range: str
    ) -> Dict[str, Any]:
        """
        分析 Excel 數據（統計資訊）
        
        Args:
            filename: 文件名
            sheet_name: 工作表名稱
            data_range: 數據範圍 (如 "A1:D10")
            
        Returns:
            統計資訊字典
        """
        try:
            # 解析範圍
            start, end = data_range.split(":")
            data = self.provider.read_range(
                filename, sheet_name, start, end
            )
            
            if not data:
                return {"error": "No data found"}
            
            # 基本統計
            stats = {
                "total_rows": len(data),
                "total_cols": len(data[0]) if data else 0,
                "has_header": isinstance(data[0][0], str) if data else False,
                "sample_data": data[:3] if len(data) > 3 else data
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to analyze data: {e}")
            return {"error": str(e)}


# 單例獲取
_excel_service_instance = None


def get_excel_service(base_path: Optional[str] = None) -> ExcelService:
    """獲取 ExcelService 單例"""
    global _excel_service_instance
    if _excel_service_instance is None:
        _excel_service_instance = ExcelService(base_path)
    return _excel_service_instance
