#!/usr/bin/env python3
"""
記錄 SolidWorks 版本兼容性錯誤的發現
"""

from founding_manager import FoundingManager

def record_version_compatibility_error():
    """記錄 SolidWorks 版本兼容性錯誤"""
    
    manager = FoundingManager()
    
    finding_id = manager.add_finding(
        error_type="VERSION_COMPATIBILITY",
        api_function="FeatureExtrusion2",
        error_description="對象不支持方法錯誤 - 新版 API 方法在舊版 SolidWorks 中不可用",
        original_code="""' 可能不兼容的新版方法
Set swFeature = swFeatureManager.FeatureExtrusion2(True, False, False, 0, 0, diameter/10, 0.01, False, False, False, False, 0.0174532925199433, 0.0174532925199433, False, False, False, False, True, True, True, 0, 0, False)
Set swComponent = swAssemblyDoc.AddComponent5(filePath, 0, "", False, "", 0, 0, 0)
vSketchSegments = swSketchManager.CreateCircle(0, 0, 0, diameter/2, 0, 0)""",
        corrected_code="""' 兼容性更好的基本方法
' 使用基本的 FeatureExtrusion 而非 FeatureExtrusion2
Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, diameter/10, diameter/10, False, False, False, False, 0, 0, False, False, False, False, True, True, True)

' 使用 AddComponent4 或 AddComponent 而非 AddComponent5
Set swComponent = swAssemblyDoc.AddComponent4(filePath, "", 0, 0, 0)
If swComponent Is Nothing Then
    Set swComponent = swAssemblyDoc.AddComponent(filePath, "", 0, 0, 0)
End If

' 使用 CreateCircleByRadius 而非 CreateCircle
swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/2""",
        api_constants={
            "BASIC_EXTRUSION_PARAMS": "簡化參數數量",
            "FALLBACK_METHODS": "提供多個備用方法",
            "OLDER_API_PREFERRED": "優先使用舊版 API"
        },
        solution_explanation="版本兼容性解決方案：1. 使用基本的 API 方法而非最新版本，2. 提供多個備用調用方法，3. 避免複雜參數的新方法，4. 添加詳細的錯誤處理而非拋出異常",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="Basic Simple Elementary FeatureManager VBA examples",
        tags=["compatibility", "version", "basic_api", "fallback", "critical_method"],
        severity="high"
    )
    
    print(f"✅ 已記錄版本兼容性錯誤解決方案 (ID: {finding_id})")
    print("💡 這個記錄將幫助生成更兼容的 SolidWorks API 代碼")
    
    return finding_id

if __name__ == "__main__":
    record_version_compatibility_error()