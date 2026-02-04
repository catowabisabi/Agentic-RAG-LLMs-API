#!/usr/bin/env python3
"""
記錄 FeatureExtrusion COM 錯誤的新發現
"""

from founding_manager import FoundingManager

def record_featureextrusion_com_error():
    """記錄 FeatureExtrusion COM 調用失敗錯誤"""
    
    manager = FoundingManager()
    
    finding_id = manager.add_finding(
        error_type="COM_OBJECT_ERROR",
        api_function="FeatureExtrusion", 
        error_description="COM 對象調用失敗 - 錯誤號 -2147221503，通常由草圖選擇或參數問題導致",
        original_code="""' 有問題的調用方式
swModel.Extension.SelectByID2 "", "SKETCHREGION", 0, 0, 0, False, 0, Nothing, 0
Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, diameter/10, 0.01, False, False, False, False, 0.0174532925, 0.0174532925, False, False, False, False, True, False, False)""",
        corrected_code="""' 修正的調用方式 - 明確選擇草圖和使用正確參數
boolstatus = swModel.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, False, 0, Nothing, 0)
Set swFeature = swFeatureManager.FeatureExtrusion2(True, False, False, 0, 0, diameter/10, 0.01, False, False, False, False, 0.0174532925199433, 0.0174532925199433, False, False, False, False, True, True, True, 0, 0, False)
' 或者使用備用方法
If swFeature Is Nothing Then
    Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, diameter/10, diameter/10, False, False, False, False, 1.5707963267949, 1.5707963267949, False, False, False, False, True, True, True)
End If""",
        api_constants={
            "COM_ERROR_CODE": -2147221503,
            "swEndCondBlind": 0,
            "SKETCH_SELECTION_TYPE": "SKETCH"
        },
        solution_explanation="FeatureExtrusion COM 錯誤的解決方案：1. 明確選擇草圖名稱而非空字符串，2. 使用 FeatureExtrusion2 方法，3. 提供備用調用方式，4. 確保參數正確",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="FeatureExtrusion2 simple extrusion extrude sketch",
        tags=["extrusion", "COM_error", "sketch_selection", "critical_method", "error_-2147221503"],
        severity="critical"
    )
    
    print(f"✅ 已記錄 FeatureExtrusion COM 錯誤解決方案 (ID: {finding_id})")
    print("💡 這個記錄將幫助避免常見的草圖選擇和擠出調用錯誤")
    
    return finding_id

if __name__ == "__main__":
    record_featureextrusion_com_error()