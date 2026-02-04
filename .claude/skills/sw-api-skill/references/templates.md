# Code Generation Templates

This file contains detailed code templates and patterns used by the SolidWorks API code generator.

## C# Templates

### Base Class Template
```csharp
using System;
using System.IO;
using System.Runtime.InteropServices;
using SldWorks;
using SwConst;

namespace SolidWorksAutomation
{
    public class {ClassName}
    {
        private SldWorks swApp;
        private ModelDoc2 swModel;
        private bool disposed = false;
        
        public {ClassName}()
        {
            InitializeSolidWorks();
        }
        
        private void InitializeSolidWorks()
        {
            try
            {
                swApp = (SldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
                if (swApp == null)
                    throw new Exception("无法启动SolidWorks应用程序");
                    
                swApp.Visible = true;
                swModel = (ModelDoc2)swApp.ActiveDoc;
                
                if (swModel == null)
                    throw new Exception("没有活动的SolidWorks文档");
                    
                Console.WriteLine($"已连接到SolidWorks，文档类型: {(swDocumentTypes_e)swModel.GetType()}");
            }
            catch (Exception ex)
            {
                throw new Exception($"SolidWorks初始化失败: {ex.Message}");
            }
        }
        
        {GeneratedMethods}
        
        public void Cleanup()
        {
            if (!disposed)
            {
                try
                {
                    if (swModel != null)
                    {
                        Marshal.ReleaseComObject(swModel);
                        swModel = null;
                    }
                    
                    if (swApp != null)
                    {
                        Marshal.ReleaseComObject(swApp);
                        swApp = null;
                    }
                    
                    GC.Collect();
                    GC.WaitForPendingFinalizers();
                    GC.Collect();
                    
                    disposed = true;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"清理资源时出错: {ex.Message}");
                }
            }
        }
        
        ~{ClassName}()
        {
            Cleanup();
        }
    }
}
```

### Method Templates

#### Save/Export Operations
```csharp
public bool {MethodName}(string filePath, swSaveAsVersion_e version = swSaveAsVersion_e.swSaveAsCurrentVersion)
{
    try
    {
        string directory = Path.GetDirectoryName(filePath);
        if (!Directory.Exists(directory))
            Directory.CreateDirectory(directory);
            
        bool result = swModel.SaveAs3(filePath, (int)version, (int)swSaveAsOptions_e.swSaveAsOptions_Silent);
        
        if (result)
        {
            Console.WriteLine($"文件已保存: {filePath}");
            return true;
        }
        else
        {
            throw new Exception("保存操作返回失败状态");
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"保存失败: {ex.Message}");
        return false;
    }
}
```

#### Feature Creation
```csharp
public Feature {MethodName}(double depth, bool reverseDirection = false)
{
    try
    {
        FeatureManager featMgr = swModel.FeatureManager;
        if (featMgr == null)
            throw new Exception("无法获取特征管理器");
            
        // 创建草图
        bool sketchResult = swModel.SketchManager.InsertSketch(true);
        if (!sketchResult)
            throw new Exception("创建草图失败");
            
        // 绘制草图几何体
        swModel.SketchManager.CreateCornerRectangle(0, 0, 0, 0.05, 0.05, 0);
        
        // 退出草图
        swModel.SketchManager.InsertSketch(true);
        
        // 创建拉伸特征
        Feature feature = featMgr.FeatureExtrusion2(
            true, false, reverseDirection,
            0, 0, depth, 0.01, false, false,
            false, false, 1.396263402, 1.396263402,
            false, false, false, false,
            true, true, true);
            
        if (feature == null)
            throw new Exception("拉伸特征创建失败");
            
        Console.WriteLine($"拉伸特征已创建: {feature.Name}");
        return feature;
    }
    catch (Exception ex)
    {
        Console.WriteLine($"特征创建失败: {ex.Message}");
        return null;
    }
}
```

## VBA Templates

### Base Module Template
```vba
Option Explicit

' 全局变量
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2

Sub Main()
    On Error GoTo ErrorHandler
    
    ' 初始化SolidWorks
    Call InitializeSolidWorks
    
    ' 执行主要操作
    Call ExecuteOperations
    
    MsgBox "所有操作已完成", vbInformation
    Exit Sub
    
ErrorHandler:
    MsgBox "执行失败: " & Err.Description & " (错误号: " & Err.Number & ")", vbCritical
End Sub

Private Sub InitializeSolidWorks()
    On Error GoTo ErrorHandler
    
    Set swApp = Application.SldWorks
    If swApp Is Nothing Then
        Err.Raise vbObjectError + 1, , "无法连接到SolidWorks应用程序"
    End If
    
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        Err.Raise vbObjectError + 2, , "没有活动的SolidWorks文档"
    End If
    
    Debug.Print "已连接到SolidWorks，文档类型: " & swModel.GetType()
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub

{GeneratedSubs}
```

### Function Templates

#### Save/Export Functions
```vba
Function {FunctionName}(ByVal filePath As String) As Boolean
    On Error GoTo ErrorHandler
    
    Dim fso As Object
    Dim folderPath As String
    Dim result As Boolean
    
    Set fso = CreateObject("Scripting.FileSystemObject")
    folderPath = fso.GetParentFolderName(filePath)
    
    ' 确保目录存在
    If Not fso.FolderExists(folderPath) Then
        fso.CreateFolder folderPath
    End If
    
    ' 保存文件
    result = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)
    
    If result Then
        Debug.Print "文件已保存: " & filePath
        {FunctionName} = True
    Else
        Err.Raise vbObjectError + 1, , "保存操作失败"
    End If
    
    Exit Function
    
ErrorHandler:
    Debug.Print "保存失败: " & Err.Description
    {FunctionName} = False
End Function
```

#### Feature Creation Functions
```vba
Function {FunctionName}(ByVal depth As Double) As SldWorks.Feature
    On Error GoTo ErrorHandler
    
    Dim featMgr As SldWorks.FeatureManager
    Dim feat As SldWorks.Feature
    Dim bResult As Boolean
    
    ' 获取特征管理器
    Set featMgr = swModel.FeatureManager
    If featMgr Is Nothing Then
        Err.Raise vbObjectError + 1, , "无法获取特征管理器"
    End If
    
    ' 创建草图
    bResult = swModel.SketchManager.InsertSketch(True)
    If Not bResult Then
        Err.Raise vbObjectError + 2, , "创建草图失败"
    End If
    
    ' 绘制矩形
    swModel.SketchManager.CreateCornerRectangle 0, 0, 0, 0.05, 0.05, 0
    
    ' 退出草图
    swModel.SketchManager.InsertSketch True
    
    ' 创建拉伸特征
    Set feat = featMgr.FeatureExtrusion2(True, False, False, _
        0, 0, depth, 0.01, False, False, _
        False, False, 1.396263402, 1.396263402, _
        False, False, False, False, _
        True, True, True)
    
    If feat Is Nothing Then
        Err.Raise vbObjectError + 3, , "拉伸特征创建失败"
    End If
    
    Debug.Print "拉伸特征已创建: " & feat.Name
    Set {FunctionName} = feat
    
    Exit Function
    
ErrorHandler:
    Debug.Print "特征创建失败: " & Err.Description
    Set {FunctionName} = Nothing
End Function
```

## Common Patterns

### Progress Reporting (C#)
```csharp
private void ReportProgress(string message, int current, int total)
{
    double percentage = (double)current / total * 100;
    Console.WriteLine($"[{percentage:F1}%] {message}");
}
```

### Progress Reporting (VBA)
```vba
Private Sub ReportProgress(ByVal message As String, ByVal current As Long, ByVal total As Long)
    Dim percentage As Double
    percentage = (current / total) * 100
    Debug.Print Format(percentage, "0.0") & "% - " & message
End Sub
```

### Error Logging (C#)
```csharp
private void LogError(string operation, Exception ex)
{
    string logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {operation}: {ex.Message}";
    Console.WriteLine(logMessage);
    // Optional: Write to file
    // File.AppendAllText("errors.log", logMessage + Environment.NewLine);
}
```

### Error Logging (VBA)
```vba
Private Sub LogError(ByVal operation As String, ByVal errorMsg As String)
    Dim logMessage As String
    logMessage = Format(Now, "yyyy-mm-dd hh:mm:ss") & " - " & operation & ": " & errorMsg
    Debug.Print logMessage
    ' Optional: Write to file
    ' Open "errors.log" For Append As #1
    ' Print #1, logMessage
    ' Close #1
End Sub
```