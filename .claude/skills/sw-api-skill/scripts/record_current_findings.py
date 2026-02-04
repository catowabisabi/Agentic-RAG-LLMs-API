#!/usr/bin/env python3
"""
記錄當前 VBA 巨集修正的發現
"""

from founding_manager import FoundingManager

def record_current_findings():
    """記錄齒輪巨集修正過程中的所有發現"""
    
    manager = FoundingManager()
    
    # 記錄 1: SetUserPreferenceInteger 常數未定義
    finding_id_1 = manager.add_finding(
        error_type="UNDEFINED_CONSTANT",
        api_function="SetUserPreferenceInteger",
        error_description="VBA 錯誤: variable not set - swUnitsLinear, swINCHES, swUnitsMass, swPOUNDS 等常數未定義",
        original_code="""swModelDocExt.SetUserPreferenceInteger swUnitsLinear, 0, swINCHES
swModelDocExt.SetUserPreferenceInteger swUnitsMass, 0, swPOUNDS
swModelDocExt.SetUserPreferenceInteger swUnitsAngle, 0, swDEGREES""",
        corrected_code="""' 使用數值常數代替未定義的變數
swModelDocExt.SetUserPreferenceInteger 0, 0, 0  ' swUnitsLinear=0, swINCHES=0
swModelDocExt.SetUserPreferenceInteger 1, 0, 0  ' swUnitsMass=1, swPOUNDS=0  
swModelDocExt.SetUserPreferenceInteger 2, 0, 0  ' swUnitsAngle=2, swDEGREES=0""",
        api_constants={
            "swUnitsLinear": 0,
            "swINCHES": 0,
            "swUnitsMass": 1,
            "swPOUNDS": 0,
            "swUnitsAngle": 2,
            "swDEGREES": 0
        },
        solution_explanation="SolidWorks API 常數需要使用數值而非變數名稱。通過查詢 API 文檔確定正確的枚舉值。",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="SetUserPreferenceInteger units swUnitsLinear swINCHES",
        tags=["units", "IPS", "constants", "preferences"],
        severity="high"
    )
    
    # 記錄 2: GetDocumentTemplate 文檔類型常數
    finding_id_2 = manager.add_finding(
        error_type="UNDEFINED_CONSTANT",
        api_function="GetDocumentTemplate",
        error_description="VBA 錯誤: variable not set - swDocPART, swDocASSEMBLY 文檔類型常數未定義",
        original_code="""swTemplate = swApp.GetDocumentTemplate(swDocPART, "", 0, 0, 0)
swTemplate = swApp.GetDocumentTemplate(swDocASSEMBLY, "", 0, 0, 0)""",
        corrected_code="""' swDocPART = 1, swDocASSEMBLY = 2
swTemplate = swApp.GetDocumentTemplate(1, "", 0, 0, 0)
swTemplate = swApp.GetDocumentTemplate(2, "", 0, 0, 0)""",
        api_constants={
            "swDocPART": 1,
            "swDocASSEMBLY": 2,
            "swDocDRAWING": 3
        },
        solution_explanation="SolidWorks 文檔類型枚舉值: Part=1, Assembly=2, Drawing=3。使用數值代替未定義的常數變數。",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="swDocASSEMBLY swDocPART document template",
        tags=["document", "template", "constants"],
        severity="high"
    )
    
    # 記錄 3: FeatureExtrusion 參數錯誤
    finding_id_3 = manager.add_finding(
        error_type="ARG_NOT_OPTIONAL",
        api_function="FeatureExtrusion",
        error_description="VBA 錯誤: Arg not optional - FeatureExtrusion 參數中的 swEndCondBlind, swEndCondThroughAll 未定義",
        original_code="""Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, swEndCondBlind, swEndCondBlind, diameter/10, 0.01, False, False, False, False, 0.0174532925, 0.0174532925, False, False, False, False, True, False, False)
Set swCutFeature = swFeatureManager.FeatureExtrusion(False, False, True, swEndCondThroughAll, swEndCondBlind, 0, 0, False, False, False, False, 0, 0, False, False, False, False, True, False, False)""",
        corrected_code="""' swEndCondBlind = 0, swEndCondThroughAll = 1
Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, diameter/10, 0.01, False, False, False, False, 0.0174532925, 0.0174532925, False, False, False, False, True, False, False)
Set swCutFeature = swFeatureManager.FeatureExtrusion(False, False, True, 1, 0, 0, 0, False, False, False, False, 0, 0, False, False, False, False, True, False, False)""",
        api_constants={
            "swEndCondBlind": 0,
            "swEndCondThroughAll": 1,
            "swEndCondMidPlane": 6
        },
        solution_explanation="SolidWorks 擠出條件枚舉值: Blind=0, ThroughAll=1, MidPlane=6。複雜的 API 方法需要明確的數值參數。",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="FeatureExtrusion parameters swEndCondBlind",
        tags=["extrusion", "feature", "parameters", "constants"],
        severity="critical"
    )
    
    # 記錄 4: SaveAs3 保存選項常數
    finding_id_4 = manager.add_finding(
        error_type="UNDEFINED_CONSTANT",
        api_function="SaveAs3",
        error_description="VBA 錯誤: variable not set - swSaveAsCurrentVersion, swSaveAsOptions_Silent 保存選項常數未定義",
        original_code="""bResult = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)""",
        corrected_code="""' swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=2
bResult = swModel.SaveAs3(filePath, 0, 2)""",
        api_constants={
            "swSaveAsCurrentVersion": 0,
            "swSaveAsOptions_Silent": 2,
            "swSaveAsOptions_UpdateInactiveViews": 1
        },
        solution_explanation="SolidWorks 保存選項: CurrentVersion=0, Silent=2。需要使用正確的數值參數以避免 VBA 編譯錯誤。",
        vba_file_path="建立三個齒輪零件_IPS單位_分別10吋_8吋_6吋直徑_然_20260203_223355.bas",
        skill_query_used="SaveAs3 swSaveAsCurrentVersion swSaveAsOptions_Silent",
        tags=["save", "options", "constants"],
        severity="medium"
    )
    
    print(f"✅ 已記錄 4 個發現:")
    print(f"   1. SetUserPreferenceInteger 常數問題 (ID: {finding_id_1})")
    print(f"   2. GetDocumentTemplate 文檔類型 (ID: {finding_id_2})")  
    print(f"   3. FeatureExtrusion 參數錯誤 (ID: {finding_id_3})")
    print(f"   4. SaveAs3 保存選項常數 (ID: {finding_id_4})")
    
    return [finding_id_1, finding_id_2, finding_id_3, finding_id_4]

if __name__ == "__main__":
    record_current_findings()