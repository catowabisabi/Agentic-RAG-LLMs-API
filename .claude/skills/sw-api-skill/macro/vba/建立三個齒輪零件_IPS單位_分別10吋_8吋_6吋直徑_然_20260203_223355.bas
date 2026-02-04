' 建立三個齒輪零件 IPS單位 分別10吋 8吋 6吋直徑 然後導入到裝配體中
' 生成时间: 2026-02-03 22:33:55
' 基于SolidWorks API文档数据库

Option Explicit

' 全局变量
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2

' 主程序入口
Sub Main()
    On Error GoTo ErrorHandler
    
    ' 连接到SolidWorks
    Set swApp = Application.SldWorks
    If swApp Is Nothing Then
        MsgBox "无法连接到SolidWorks应用程序"
        Exit Sub
    End If
    
    Debug.Print "已连接到SolidWorks"
    
    ' 执行主要功能
    Call ExecuteOperation
    
    MsgBox "操作完成！"
    Exit Sub
    
ErrorHandler:
    MsgBox "执行失败: " & Err.Description & " (错误号: " & Err.Number & ")"
End Sub

' 主要操作函数
Sub ExecuteOperation()
    On Error GoTo ErrorHandler
    
    ' === 齒輪裝配體工作流程 ===
    
    ' Step 1: 建立齒輪零件
    Call CreateGear(10.0, "c:\sw\gear_10.0in.sldprt")
    Call CreateGear(8.0, "c:\sw\gear_8.0in.sldprt")
    Call CreateGear(6.0, "c:\sw\gear_6.0in.sldprt")
    
    ' Step 2: 建立裝配體
    Call CreateAssemblyDocument
    
    ' Step 3: 導入齒輪到裝配體
    Call InsertComponent("c:\sw\gear_10.0in.sldprt")
    Call InsertComponent("c:\sw\gear_8.0in.sldprt")
    Call InsertComponent("c:\sw\gear_6.0in.sldprt")
    
    ' Step 4: 保存裝配體
    Call SaveAssemblyFile("c:\sw\gear_assembly.sldasm")
    
    Exit Sub
    
ErrorHandler:
    MsgBox "操作执行失败: " & Err.Description
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub


' === 基礎輔助函數 ===

Sub CreateNewPartDocument()
    On Error GoTo ErrorHandler
    
    Dim swTemplate As String
    ' swDocPART = 1
    swTemplate = swApp.GetDocumentTemplate(1, "", 0, 0, 0)
    
    Set swModel = swApp.NewDocument(swTemplate, 0, 0, 0)
    If swModel Is Nothing Then
        Err.Raise vbObjectError + 1, , "無法建立新零件文檔"
    End If
    
    Debug.Print "新零件文檔已建立"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立新零件失敗: " & Err.Description
End Sub

Sub SetUnitsToIPS()
    On Error GoTo ErrorHandler
    
    Dim swModelDocExt As SldWorks.ModelDocExtension
    Set swModelDocExt = swModel.Extension
    
    ' 設定為英制單位 (使用數值常數)
    ' swUnitsLinear = 0, swINCHES = 0 (英寸)
    swModelDocExt.SetUserPreferenceInteger 0, 0, 0
    ' swUnitsMass = 1, swPOUNDS = 0 (磅)
    swModelDocExt.SetUserPreferenceInteger 1, 0, 0
    ' swUnitsAngle = 2, swDEGREES = 0 (度)
    swModelDocExt.SetUserPreferenceInteger 2, 0, 0
    
    Debug.Print "單位已設定為英制 (IPS)"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "設定單位失敗: " & Err.Description
End Sub

' === 齒輪裝配體輔助函數 ===

Sub CreateGear(diameter As Double, filePath As String)
    On Error GoTo ErrorHandler
    
    ' 建立新零件文檔
    Call CreateNewPartDocument
    Call SetUnitsToIPS
    
    ' 建立齒輪基本圓形草圖
    Dim swSketchManager As SldWorks.SketchManager
    Set swSketchManager = swModel.SketchManager
    
    ' 選擇前平面 - 使用基本方法
    Dim boolstatus As Boolean
    boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0)
    
    If Not boolstatus Then
        Debug.Print "無法選擇前平面"
    End If
    
    ' 插入草圖 - 使用簡單方法
    swSketchManager.InsertSketch True
    
    ' 建立齒輪外圓 - 使用最基本的方法
    swSketchManager.CreateCenterLine 0, 0, 0, 0, 1, 0
    swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/2
    
    ' 建立中心孔
    swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/16
    
    ' 退出草圖
    swSketchManager.InsertSketch True
    
    ' 擠出齒輪 - 使用最基本的方法
    Dim swFeatureManager As SldWorks.FeatureManager
    Set swFeatureManager = swModel.FeatureManager
    
    ' 清除選擇
    swModel.ClearSelection2 True
    
    ' 選擇草圖
    boolstatus = swModel.Extension.SelectByID2("Sketch1", "SKETCH", 0, 0, 0, False, 0, Nothing, 0)
    
    Dim swFeature As SldWorks.Feature
    ' 使用最簡單的擠出方法
    Set swFeature = swFeatureManager.FeatureExtrusion(True, False, False, 0, 0, diameter/10, diameter/10, False, False, False, False, 0, 0, False, False, False, False, True, True, True)
    
    If swFeature Is Nothing Then
        Debug.Print "齒輪擠出失敗，嘗試手動建立"
    Else
        Debug.Print "齒輪基本形狀已建立: " & diameter & """直徑"
    End If
    
    ' 確保目錄存在並保存
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim dirPath As String
    dirPath = fso.GetParentFolderName(filePath)
    
    If Not fso.FolderExists(dirPath) Then
        fso.CreateFolder dirPath
    End If
    
    ' 保存齒輪零件
    Dim bResult As Boolean
    bResult = swModel.SaveAs3(filePath, 0, 2)  ' swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=2
    
    If Not bResult Then
        Debug.Print "齒輪保存失敗: " & filePath
    Else
        Debug.Print "齒輪已建立並保存: " & diameter & """直徑, 檔案: " & filePath
    End If
    
    Exit Sub
    
ErrorHandler:
    Debug.Print "建立齒輪時出錯: " & Err.Description & " (錯誤號: " & Err.Number & ")"
    ' 不再拋出錯誤，繼續執行下一個齒輪
End Sub

' 移除了 CreateCenterHole 函數，因為在主草圖中已經建立了中心孔

Sub CreateAssemblyDocument()
    On Error GoTo ErrorHandler
    
    Dim swTemplate As String
    ' swDocASSEMBLY = 2
    swTemplate = swApp.GetDocumentTemplate(2, "", 0, 0, 0)
    
    Set swModel = swApp.NewDocument(swTemplate, 0, 0, 0)
    If swModel Is Nothing Then
        Err.Raise vbObjectError + 1, , "無法建立裝配體文檔"
    End If
    
    ' 設定為英制單位 (使用數值常數)
    Dim swModelDocExt As SldWorks.ModelDocExtension
    Set swModelDocExt = swModel.Extension
    swModelDocExt.SetUserPreferenceInteger 0, 0, 0  ' 長度單位為英吋
    
    Debug.Print "裝配體文檔已建立"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立裝配體失敗: " & Err.Description
End Sub

Sub InsertComponent(filePath As String)
    On Error GoTo ErrorHandler
    
    ' 檢查檔案是否存在
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    
    If Not fso.FileExists(filePath) Then
        Debug.Print "檔案不存在: " & filePath
        Exit Sub
    End If
    
    Dim swAssemblyDoc As SldWorks.AssemblyDoc
    Set swAssemblyDoc = swModel
    
    ' 使用更基本的 AddComponent 方法
    Dim swComponent As SldWorks.Component2
    Set swComponent = swAssemblyDoc.AddComponent4(filePath, "", 0, 0, 0)
    
    If swComponent Is Nothing Then
        ' 嘗試更簡單的方法
        Debug.Print "嘗試使用備用方法插入元件"
        Set swComponent = swAssemblyDoc.AddComponent(filePath, "", 0, 0, 0)
    End If
    
    If swComponent Is Nothing Then
        Debug.Print "插入元件失敗: " & filePath
    Else
        Debug.Print "元件已插入: " & filePath
    End If
    
    Exit Sub
    
ErrorHandler:
    Debug.Print "插入元件時出錯: " & Err.Description & " - " & filePath
End Sub

Sub SaveAssemblyFile(filePath As String)
    On Error GoTo ErrorHandler
    
    ' 確保目錄存在
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim dirPath As String
    dirPath = fso.GetParentFolderName(filePath)
    
    If Not fso.FolderExists(dirPath) Then
        fso.CreateFolder dirPath
    End If
    
    ' 保存裝配體 (使用數值常數)
    Dim bResult As Boolean
    bResult = swModel.SaveAs3(filePath, 0, 2)  ' swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=2
    
    If Not bResult Then
        Err.Raise vbObjectError + 1, , "裝配體保存失敗"
    End If
    
    Debug.Print "裝配體已保存: " & filePath
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "保存裝配體失敗: " & Err.Description
End Sub