#!/usr/bin/env python3
"""
SolidWorks API 發現記錄管理器
用於記錄和查詢 API 錯誤修正的學習數據庫
"""

import sqlite3
import json
import datetime
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

class FoundingManager:
    """管理 SolidWorks API 發現記錄"""
    
    def __init__(self, db_path: str = "assets/founding.db"):
        self.db_path = Path(__file__).parent.parent / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """初始化數據庫結構"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    api_function TEXT NOT NULL,
                    error_description TEXT NOT NULL,
                    original_code TEXT NOT NULL,
                    corrected_code TEXT NOT NULL,
                    api_constants TEXT,  -- JSON格式的常數定義
                    solution_explanation TEXT NOT NULL,
                    vba_file_path TEXT,
                    skill_query_used TEXT,  -- 使用的skill查詢
                    tags TEXT,  -- 標籤，以逗號分隔
                    severity TEXT DEFAULT 'medium',  -- low, medium, high, critical
                    status TEXT DEFAULT 'resolved'  -- resolved, pending, verified
                )
            """)
            
            # 創建索引以提高查詢效率
            conn.execute("CREATE INDEX IF NOT EXISTS idx_error_type ON findings(error_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_function ON findings(api_function)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON findings(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON findings(tags)")
    
    def add_finding(self, 
                   error_type: str,
                   api_function: str,
                   error_description: str,
                   original_code: str,
                   corrected_code: str,
                   solution_explanation: str,
                   api_constants: Optional[Dict[str, Any]] = None,
                   vba_file_path: Optional[str] = None,
                   skill_query_used: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   severity: str = 'medium') -> int:
        """
        新增發現記錄
        
        Args:
            error_type: 錯誤類型 (如: UNDEFINED_CONSTANT, ARG_NOT_OPTIONAL, API_USAGE_ERROR)
            api_function: 相關的API函數名稱
            error_description: 錯誤描述
            original_code: 原始有問題的代碼
            corrected_code: 修正後的代碼
            solution_explanation: 解決方案說明
            api_constants: API常數定義字典
            vba_file_path: VBA檔案路徑
            skill_query_used: 使用的skill查詢字符串
            tags: 標籤列表
            severity: 嚴重程度
        
        Returns:
            新記錄的ID
        """
        timestamp = datetime.datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO findings (
                    timestamp, error_type, api_function, error_description,
                    original_code, corrected_code, api_constants, solution_explanation,
                    vba_file_path, skill_query_used, tags, severity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, error_type, api_function, error_description,
                original_code, corrected_code, 
                json.dumps(api_constants) if api_constants else None,
                solution_explanation, vba_file_path, skill_query_used,
                ','.join(tags) if tags else None, severity
            ))
            
            return cursor.lastrowid
    
    def search_findings(self, 
                       error_type: Optional[str] = None,
                       api_function: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       severity: Optional[str] = None,
                       limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索發現記錄
        
        Args:
            error_type: 錯誤類型過濾
            api_function: API函數名稱過濾
            tags: 標籤過濾
            severity: 嚴重程度過濾
            limit: 結果限制數量
        
        Returns:
            匹配的記錄列表
        """
        query = "SELECT * FROM findings WHERE 1=1"
        params = []
        
        if error_type:
            query += " AND error_type = ?"
            params.append(error_type)
        
        if api_function:
            query += " AND api_function LIKE ?"
            params.append(f"%{api_function}%")
        
        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f"%{tag}%")
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['api_constants']:
                    result['api_constants'] = json.loads(result['api_constants'])
                if result['tags']:
                    result['tags'] = result['tags'].split(',')
                results.append(result)
            
            return results
    
    def get_similar_errors(self, api_function: str, limit: int = 5) -> List[Dict[str, Any]]:
        """獲取相似的錯誤記錄"""
        return self.search_findings(api_function=api_function, limit=limit)
    
    def export_findings(self, output_file: str = "findings_export.json"):
        """導出所有發現記錄為JSON格式"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings ORDER BY timestamp DESC")
            
            findings = []
            for row in cursor.fetchall():
                finding = dict(row)
                if finding['api_constants']:
                    finding['api_constants'] = json.loads(finding['api_constants'])
                if finding['tags']:
                    finding['tags'] = finding['tags'].split(',')
                findings.append(finding)
        
        output_path = Path(__file__).parent.parent / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(findings, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 導出完成: {output_path}")
        return str(output_path)

def main():
    """命令行界面"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SolidWorks API 發現記錄管理器")
    parser.add_argument("action", choices=["search", "export"], help="操作類型")
    parser.add_argument("--error-type", help="錯誤類型過濾")
    parser.add_argument("--api-function", help="API函數名稱過濾")
    parser.add_argument("--tags", help="標籤過濾，以逗號分隔")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"], help="嚴重程度過濾")
    parser.add_argument("--limit", type=int, default=10, help="結果限制數量")
    parser.add_argument("--output", help="導出檔案名稱")
    
    args = parser.parse_args()
    
    manager = FoundingManager()
    
    if args.action == "search":
        tags = args.tags.split(',') if args.tags else None
        results = manager.search_findings(
            error_type=args.error_type,
            api_function=args.api_function,
            tags=tags,
            severity=args.severity,
            limit=args.limit
        )
        
        print(f"🔍 找到 {len(results)} 條記錄:")
        for i, result in enumerate(results, 1):
            print(f"\n--- 記錄 {i} ---")
            print(f"時間: {result['timestamp']}")
            print(f"錯誤類型: {result['error_type']}")
            print(f"API函數: {result['api_function']}")
            print(f"錯誤描述: {result['error_description']}")
            print(f"解決方案: {result['solution_explanation']}")
            if result['tags']:
                print(f"標籤: {', '.join(result['tags'])}")
    
    elif args.action == "export":
        output_file = args.output or "findings_export.json"
        manager.export_findings(output_file)

if __name__ == "__main__":
    main()