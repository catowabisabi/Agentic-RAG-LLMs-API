#!/usr/bin/env python3
"""
SolidWorks API 方法參數快速查詢工具
在寫代碼前快速查看常見方法的正確參數，避免 bug
"""

from founding_manager import FoundingManager
import sys

def quick_check(method_name=None):
    """快速查看 SolidWorks API 方法的正確參數"""
    
    manager = FoundingManager()
    
    if method_name:
        # 查詢特定方法
        findings = manager.search_findings(api_function=method_name, limit=5)
        if not findings:
            print(f"❌ 沒有找到 '{method_name}' 的記錄")
            return
        
        print(f"🔍 {method_name} 方法參數:")
        for finding in findings:
            print(f"\n✅ 正確用法:")
            print(f"{finding['corrected_code']}")
            
            if finding.get('api_constants'):
                print(f"\n📊 常數值:")
                for name, value in finding['api_constants'].items():
                    print(f"   {name} = {value}")
    else:
        # 顯示所有關鍵方法的快速參考
        critical_findings = manager.search_findings(tags=['critical_method'], limit=10)
        
        print("🚀 SolidWorks API 關鍵方法快速參考\n" + "="*50)
        
        methods_summary = {}
        for finding in critical_findings:
            method = finding['api_function']
            if method not in methods_summary:
                methods_summary[method] = finding
        
        for method, finding in methods_summary.items():
            print(f"\n🔧 {method}:")
            
            # 顯示關鍵常數
            if finding.get('api_constants'):
                key_constants = list(finding['api_constants'].items())[:3]  # 顯示前3個最重要的
                for name, value in key_constants:
                    print(f"   {name} = {value}")
                if len(finding['api_constants']) > 3:
                    print(f"   ... (+{len(finding['api_constants'])-3} 更多)")
            
            # 顯示典型錯誤
            error_summary = finding['error_description'].split(' - ')[-1] if ' - ' in finding['error_description'] else finding['error_description']
            print(f"   ⚠️  常見錯誤: {error_summary}")
        
        print(f"\n💡 使用 'python quick_check.py <方法名>' 查看詳細用法")

def main():
    """命令行界面"""
    if len(sys.argv) > 1:
        method_name = sys.argv[1]
        quick_check(method_name)
    else:
        quick_check()

if __name__ == "__main__":
    main()