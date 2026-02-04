#!/usr/bin/env python3
"""
更新和優化 SolidWorks API 方法參數的重要 insights
專注於記錄常見的方法參數錯誤，供代碼生成時參考
"""

import sqlite3
import json
from pathlib import Path
from founding_manager import FoundingManager

def update_key_insights():
    """更新關鍵的 SolidWorks API 方法參數 insights"""
    
    manager = FoundingManager()
    
    # 清理現有記錄，重新插入優化的版本
    with sqlite3.connect(manager.db_path) as conn:
        conn.execute("DELETE FROM findings")
    
    print("🧹 清理舊記錄")
    
    # 核心方法參數 insights - 專注於常見錯誤和解決方案
    key_insights = [
        {
            "error_type": "UNDEFINED_CONSTANT",
            "api_function": "SetUserPreferenceInteger",
            "error_description": "單位設定參數錯誤 - swUnitsLinear, swINCHES, swUnitsMass, swPOUNDS 等常數未定義",
            "original_code": "swModelDocExt.SetUserPreferenceInteger swUnitsLinear, 0, swINCHES\nswModelDocExt.SetUserPreferenceInteger swUnitsMass, 0, swPOUNDS",
            "corrected_code": "' IPS 單位系統設定\nswModelDocExt.SetUserPreferenceInteger 0, 0, 0  ' swUnitsLinear=0, swINCHES=0\nswModelDocExt.SetUserPreferenceInteger 1, 0, 0  ' swUnitsMass=1, swPOUNDS=0\nswModelDocExt.SetUserPreferenceInteger 2, 0, 0  ' swUnitsAngle=2, swDEGREES=0",
            "api_constants": {
                "swUnitsLinear": 0,
                "swINCHES": 0,
                "swUnitsMass": 1,
                "swPOUNDS": 0,
                "swUnitsAngle": 2,
                "swDEGREES": 0,
                "swUnitsTemperature": 3,
                "swFAHRENHEIT": 0
            },
            "solution_explanation": "使用數值常數設定文檔單位。IPS系統: 長度=英寸(0,0), 質量=磅(1,0), 角度=度(2,0)",
            "tags": ["units", "IPS", "preferences", "constants", "critical_method"],
            "severity": "critical"
        },
        
        {
            "error_type": "UNDEFINED_CONSTANT",
            "api_function": "GetDocumentTemplate",
            "error_description": "文檔模板類型錯誤 - swDocPART, swDocASSEMBLY, swDocDRAWING 常數未定義",
            "original_code": "swTemplate = swApp.GetDocumentTemplate(swDocPART, \"\", 0, 0, 0)\nswTemplate = swApp.GetDocumentTemplate(swDocASSEMBLY, \"\", 0, 0, 0)",
            "corrected_code": "' 文檔類型數值\nswTemplate = swApp.GetDocumentTemplate(1, \"\", 0, 0, 0)  ' swDocPART=1\nswTemplate = swApp.GetDocumentTemplate(2, \"\", 0, 0, 0)  ' swDocASSEMBLY=2",
            "api_constants": {
                "swDocPART": 1,
                "swDocASSEMBLY": 2,
                "swDocDRAWING": 3
            },
            "solution_explanation": "SolidWorks 文檔類型枚舉: Part=1, Assembly=2, Drawing=3。創建文檔時必須使用正確數值",
            "tags": ["document", "template", "constants", "critical_method"],
            "severity": "high"
        },
        
        {
            "error_type": "ARG_NOT_OPTIONAL",
            "api_function": "FeatureExtrusion",
            "error_description": "擠出特徵參數錯誤 - 擠出條件常數未定義導致參數錯誤",
            "original_code": "Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, swEndCondBlind, swEndCondBlind, depth, 0.01, ...)",
            "corrected_code": "' 擠出條件數值\nSet swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, depth, 0.01, ...)  ' swEndCondBlind=0\n' 切除穿透\nSet swCutFeature = swFeatureManager.FeatureExtrusion(False, False, True, 1, 0, 0, 0, ...)  ' swEndCondThroughAll=1",
            "api_constants": {
                "swEndCondBlind": 0,
                "swEndCondThroughAll": 1,
                "swEndCondMidPlane": 6,
                "swEndCondUpToNext": 2,
                "swEndCondUpToVertex": 3,
                "swEndCondUpToSurface": 4,
                "swEndCondOffsetFromSurface": 5
            },
            "solution_explanation": "擠出條件枚舉: Blind=0(盲孔), ThroughAll=1(完全穿透), MidPlane=6(中間平面)。複雜API需明確數值參數",
            "tags": ["extrusion", "feature", "parameters", "constants", "critical_method"],
            "severity": "critical"
        },
        
        {
            "error_type": "UNDEFINED_CONSTANT",
            "api_function": "SaveAs3",
            "error_description": "檔案保存選項錯誤 - 保存選項常數未定義",
            "original_code": "bResult = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)",
            "corrected_code": "' 保存選項數值\nbResult = swModel.SaveAs3(filePath, 0, 2)  ' swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=2",
            "api_constants": {
                "swSaveAsCurrentVersion": 0,
                "swSaveAsOptions_Silent": 2,
                "swSaveAsOptions_UpdateInactiveViews": 1,
                "swSaveAsOptions_Copy": 4
            },
            "solution_explanation": "保存選項: CurrentVersion=0(當前版本), Silent=2(安靜模式), UpdateInactiveViews=1(更新視圖)",
            "tags": ["save", "options", "constants", "critical_method"],
            "severity": "medium"
        }
    ]
    
    # 插入優化的記錄
    inserted_ids = []
    for insight in key_insights:
        finding_id = manager.add_finding(
            error_type=insight["error_type"],
            api_function=insight["api_function"], 
            error_description=insight["error_description"],
            original_code=insight["original_code"],
            corrected_code=insight["corrected_code"],
            api_constants=insight["api_constants"],
            solution_explanation=insight["solution_explanation"],
            tags=insight["tags"],
            severity=insight["severity"]
        )
        inserted_ids.append(finding_id)
        print(f"✅ 更新 {insight['api_function']} insight (ID: {finding_id})")
    
    print(f"\n🎯 已更新 {len(key_insights)} 個關鍵方法參數 insights")
    print("💡 這些記錄將幫助自動避免常見的 SolidWorks API 錯誤")
    
    return inserted_ids

def show_critical_methods():
    """顯示關鍵方法的快速參考"""
    
    manager = FoundingManager()
    critical_findings = manager.search_findings(tags=['critical_method'], limit=10)
    
    print("\n📋 SolidWorks API 關鍵方法參數速查:")
    print("=" * 50)
    
    for finding in critical_findings:
        print(f"\n🔧 {finding['api_function']}:")
        
        if finding['api_constants']:
            for const_name, const_value in finding['api_constants'].items():
                print(f"   {const_name} = {const_value}")
        
        print(f"   錯誤: {finding['error_description'].split(' - ')[1] if ' - ' in finding['error_description'] else finding['error_description']}")

if __name__ == "__main__":
    print("🔄 更新 SolidWorks API 關鍵方法參數 insights...")
    update_key_insights()
    show_critical_methods()