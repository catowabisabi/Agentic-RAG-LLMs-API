"""
sw_code_generator.py - SolidWorks API 代码生成器 (改進版)
=============================================
基于RAG数据库智能生成C#和VBA代码

使用方式:
python sw_code_generator.py --request "创建拉伸特征" --lang csharp
python sw_code_generator.py --request "批量另存为PDF" --lang vba
"""

import sqlite3
import re
import os
import argparse
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============
MAIN_DB = "asset/sw_api_doc.db"  # 修正資料庫路徑為相對路徑
OUTPUT_DIR_CSHARP = "macro/csharp"
OUTPUT_DIR_VBA = "macro/vba"

# ============== C#代码模板 ==============
CSHARP_TEMPLATE = """// {description}
// 生成时间: {timestamp}
// 基于SolidWorks API文档数据库

using System;
using System.Runtime.InteropServices;
using SldWorks;
using SwConst;

namespace SolidWorksAutomation
{{
    /// <summary>
    /// {class_description}
    /// </summary>
    public class {class_name}
    {{
        private SldWorks swApp;
        private ModelDoc2 swModel;
        
        /// <summary>
        /// 初始化SolidWorks连接
        /// </summary>
        public {class_name}()
        {{
            try
            {{
                // 连接到SolidWorks应用程序
                swApp = (SldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
                swApp.Visible = true;
                
                // 获取活动文档
                swModel = (ModelDoc2)swApp.ActiveDoc;
                if (swModel == null)
                {{
                    throw new Exception("没有活动的SolidWorks文档。请先打开一个文档。");
                }}
                
                Console.WriteLine($"已连接到SolidWorks，活动文档: {{swModel.GetTitle()}}");
            }}
            catch (Exception ex)
            {{
                throw new Exception($"初始化SolidWorks失败: {{ex.Message}}");
            }}
        }}
        
{generated_methods}
        
        /// <summary>
        /// 清理COM对象资源
        /// </summary>
        public void Cleanup()
        {{
            try
            {{
                if (swModel != null)
                {{
                    Marshal.ReleaseComObject(swModel);
                    swModel = null;
                }}
                
                if (swApp != null)
                {{
                    Marshal.ReleaseComObject(swApp);
                    swApp = null;
                }}
                
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();
            }}
            catch (Exception ex)
            {{
                Console.WriteLine($"清理资源时出错: {{ex.Message}}");
            }}
        }}
        
        /// <summary>
        /// 析构函数，确保资源清理
        /// </summary>
        ~{class_name}()
        {{
            Cleanup();
        }}
    }}
    
    /// <summary>
    /// 程序入口点
    /// </summary>
    class Program
    {{
        static void Main(string[] args)
        {{
            {class_name} automation = null;
            
            try
            {{
                automation = new {class_name}();
                automation.Execute();
                Console.WriteLine("操作完成！");
            }}
            catch (Exception ex)
            {{
                Console.WriteLine($"执行失败: {{ex.Message}}");
            }}
            finally
            {{
                automation?.Cleanup();
            }}
            
            Console.WriteLine("按任意键退出...");
            Console.ReadKey();
        }}
    }}
}}"""

# ============== VBA代码模板 ==============
VBA_TEMPLATE = """' {description}
' 生成时间: {timestamp}
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
    
{generated_code}
    
    Exit Sub
    
ErrorHandler:
    MsgBox "操作执行失败: " & Err.Description
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub

{generated_functions}"""

def query_api_info(search_term):
    """查询API信息"""
    try:
        conn = sqlite3.connect(MAIN_DB)
        cursor = conn.cursor()
        
        # 查询相关文档和代码示例
        cursor.execute("""
            SELECT 
                d.title,
                d.interface_name,
                d.doc_type,
                d.description,
                d.full_text,
                ce.language,
                ce.code,
                ce.title as code_title
            FROM documents d
            LEFT JOIN code_examples ce ON d.id = ce.doc_id
            WHERE d.title LIKE ? 
                OR d.interface_name LIKE ?
                OR d.full_text LIKE ?
            LIMIT 10
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        results = cursor.fetchall()
        
        # 查询相关chunks
        cursor.execute("""
            SELECT 
                c.chunk_type,
                c.content,
                c.context_prefix,
                d.title
            FROM chunks c
            JOIN documents d ON c.doc_id = d.id
            WHERE c.content LIKE ?
                OR d.title LIKE ?
                OR d.interface_name LIKE ?
            ORDER BY 
                CASE c.chunk_type
                    WHEN 'syntax' THEN 1
                    WHEN 'description' THEN 2
                    WHEN 'parameters' THEN 3
                    WHEN 'example' THEN 4
                    ELSE 5
                END
            LIMIT 20
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        chunks = cursor.fetchall()
        conn.close()
        
        return {
            'documents': results,
            'chunks': chunks
        }
        
    except Exception as e:
        print(f"数据库查询失败: {e}")
        return {'documents': [], 'chunks': []}

def analyze_request(request_text):
    """分析用户请求，提取关键信息"""
    request_lower = request_text.lower()
    
    # 操作类型识别 - 擴展更多操作
    operations = {
        'new_part': ['新建零件', '建立零件', '新的零件', 'new part', 'create part', '建立新的零件文檔'],
        'multiple_parts': ['三個', '多個', '幾個', 'three', 'multiple', 'several', '分別'],
        'gear': ['齒輪', 'gear', 'gears', '齒輪零件'],
        'assembly': ['裝配體', 'assembly', '組裝', '導入到', 'import to', 'asm'],
        'sketch': ['草圖', 'sketch', '繪製', '建立草圖', '矩形', 'rectangle', '圓形', 'circle'],
        'extrude': ['擠出', 'extrude', '拉伸', '凸台'],
        'hole': ['孔', 'hole', '打孔', '鑽孔', '洞'],
        'save': ['保存', '另存為', 'save', 'export', '導出', '儲存'],
        'units': ['單位', 'units', 'ips', '英制', 'metric', '公制'],
        'plane': ['平面', 'plane', '前平面', 'front', '上平面', 'top', '右平面', 'right'],
        'dimensions': ['尺寸', 'dimension', '吋', 'inch', 'mm', 'millimeter', '直徑', 'diameter']
    }
    
    detected_operations = []
    for op_type, keywords in operations.items():
        if any(keyword in request_lower for keyword in keywords):
            detected_operations.append(op_type)
    
    # 文档类型识别
    doc_types = {
        'part': ['零件', 'part', '實體'],
        'assembly': ['裝配體', 'assembly', '組裝'],
        'drawing': ['工程圖', 'drawing', '圖紙']
    }
    
    detected_doc_type = 'general'
    for doc_type, keywords in doc_types.items():
        if any(keyword in request_lower for keyword in keywords):
            detected_doc_type = doc_type
            break
    
    # 提取关键API名词
    api_keywords = []
    common_apis = [
        'ModelDoc2', 'PartDoc', 'AssemblyDoc', 'DrawingDoc',
        'FeatureManager', 'SelectionManager', 'SaveAs', 'FeatureExtrusion'
    ]
    
    for api in common_apis:
        if api.lower() in request_lower:
            api_keywords.append(api)
    
    return {
        'operations': detected_operations,
        'doc_type': detected_doc_type,
        'api_keywords': api_keywords,
        'search_terms': detected_operations + [detected_doc_type] + api_keywords
    }

def extract_dimensions(request_text):
    """從請求文本中提取尺寸信息"""
    import re
    dimensions = {}
    
    # 匹配常見尺寸格式
    width_match = re.search(r'(\d+(?:\.\d+)?)(?:吋|inch|\")?\s*[xX×]\s*(\d+(?:\.\d+)?)(?:吋|inch|\")?', request_text)
    if width_match:
        dimensions['width'] = float(width_match.group(2))  # 寬度
        dimensions['height'] = float(width_match.group(1))  # 高度
    
    # 匹配擠出深度
    depth_match = re.search(r'擠出(?:為)?(\d+(?:\.\d+)?)(?:吋|inch|\")?', request_text)
    if depth_match:
        dimensions['depth'] = float(depth_match.group(1))
    
    # 匹配孔徑
    hole_match = re.search(r'(\d+(?:/\d+)?)(?:吋|inch|\")?(?:的)?孔', request_text)
    if hole_match:
        hole_str = hole_match.group(1)
        if '/' in hole_str:
            num, den = hole_str.split('/')
            dimensions['hole_diameter'] = float(num) / float(den)
        else:
            dimensions['hole_diameter'] = float(hole_str)
    
    # 匹配多個直徑尺寸 (例如: 10吋 8吋 6吋)
    diameter_matches = re.findall(r'(\d+(?:\.\d+)?)(?:吋|inch|\")', request_text)
    if len(diameter_matches) >= 3:
        dimensions['gear_diameters'] = [float(d) for d in diameter_matches[:3]]
    elif len(diameter_matches) > 0:
        dimensions['gear_diameters'] = [float(d) for d in diameter_matches]
    
    return dimensions

def extract_file_path(request_text):
    """從請求文本中提取檔案保存路徑"""
    path_match = re.search(r'保存(?:為|至|到)\s*([a-zA-Z]:[/\\][^\s]+\.sldprt)', request_text)
    if path_match:
        return path_match.group(1).replace('/', '\\')
    
    return "c:\\sw\\output.sldprt"  # 預設路徑

def generate_gear_assembly_workflow(request_text):
    """生成齒輪裝配體工作流程"""
    dimensions = extract_dimensions(request_text)
    gear_diameters = dimensions.get('gear_diameters', [10, 8, 6])
    
    gear_calls = []
    for i, diameter in enumerate(gear_diameters, 1):
        gear_calls.append(f'    Call CreateGear({diameter}, "c:\\sw\\gear_{diameter}in.sldprt")')
    
    return f'''    ' === 齒輪裝配體工作流程 ===
    
    ' Step 1: 建立齒輪零件
{chr(10).join(gear_calls)}
    
    ' Step 2: 建立裝配體
    Call CreateAssemblyDocument
    
    ' Step 3: 導入齒輪到裝配體
{chr(10).join([f'    Call InsertComponent("c:\\sw\\gear_{d}in.sldprt")' for d in gear_diameters])}
    
    ' Step 4: 保存裝配體
    Call SaveAssemblyFile("c:\\sw\\gear_assembly.sldasm")'''

def generate_complete_part_workflow(request_text):
    """生成完整的零件建立工作流程"""
    # 分析尺寸信息
    dimensions = extract_dimensions(request_text)
    file_path = extract_file_path(request_text)
    
    return f'''    ' === 完整零件建立工作流程 ===
    
    ' Step 1: 建立新零件文檔
    Call CreateNewPartDocument
    
    ' Step 2: 設定單位系統
    Call SetUnitsToIPS
    
    ' Step 3: 建立草圖
    Call CreateRectangleSketch({dimensions.get('width', 8)}, {dimensions.get('height', 1)})
    
    ' Step 4: 建立擠出特徵
    Call CreateExtrusionFeature({dimensions.get('depth', 5)})
    
    ' Step 5: 建立中心孔
    Call CreateCenterHole({dimensions.get('hole_diameter', 0.375)})
    
    ' Step 6: 保存檔案
    Call SavePartFile("{file_path}")'''

def generate_vba_functions():
    """生成完整的VBA輔助函數"""
    return '''
' === 輔助函數 ===

Sub CreateNewPartDocument()
    On Error GoTo ErrorHandler
    
    Dim swTemplate As String
    swTemplate = swApp.GetDocumentTemplate(swDocPART, "", 0, 0, 0)
    
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
    
    ' 設定為英制單位
    swModelDocExt.SetUserPreferenceInteger swUnitsLinear, 0, swINCHES
    swModelDocExt.SetUserPreferenceInteger swUnitsMass, 0, swPOUNDS
    
    Debug.Print "單位已設定為英制 (IPS)"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "設定單位失敗: " & Err.Description
End Sub

Sub CreateRectangleSketch(width As Double, height As Double)
    On Error GoTo ErrorHandler
    
    Dim swSketchManager As SldWorks.SketchManager
    Set swSketchManager = swModel.SketchManager
    
    ' 選擇前平面
    swModel.Extension.SelectByID2 "Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    
    ' 插入草圖
    swSketchManager.InsertSketch True
    
    ' 建立中心矩形
    swSketchManager.CreateCenterRectangle 0, 0, 0, width/2, height/2, 0
    
    ' 退出草圖
    swSketchManager.InsertSketch True
    
    Debug.Print "矩形草圖已建立: " & width & """ x " & height & """"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立草圖失敗: " & Err.Description
End Sub

Sub CreateExtrusionFeature(depth As Double)
    On Error GoTo ErrorHandler
    
    Dim swFeatureManager As SldWorks.FeatureManager
    Set swFeatureManager = swModel.FeatureManager
    
    Dim swFeature As SldWorks.Feature
    Set swFeature = swFeatureManager.FeatureExtrusion2( _
        True, False, False, _
        swEndCondBlind, swEndCondBlind, _
        depth, 0, _
        False, False, False, False, _
        1.396263402, 1.396263402, _
        False, False, False, False, _
        True, True, True)
    
    If swFeature Is Nothing Then
        Err.Raise vbObjectError + 1, , "擠出特徵建立失敗"
    End If
    
    Debug.Print "擠出特徵已建立: " & depth & """"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立擠出失敗: " & Err.Description
End Sub

Sub CreateCenterHole(diameter As Double)
    On Error GoTo ErrorHandler
    
    Dim swSketchManager As SldWorks.SketchManager
    Set swSketchManager = swModel.SketchManager
    
    ' 選擇前表面
    swModel.Extension.SelectByID2 "", "FACE", 0, 0, 2.5, False, 0, Nothing, 0
    
    ' 插入草圖
    swSketchManager.InsertSketch True
    
    ' 建立圓形 (半徑 = 直徑/2)
    swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/2
    
    ' 退出草圖
    swSketchManager.InsertSketch True
    
    ' 建立切除特徵
    Dim swFeatureManager As SldWorks.FeatureManager
    Set swFeatureManager = swModel.FeatureManager
    
    Dim swCutFeature As SldWorks.Feature
    Set swCutFeature = swFeatureManager.FeatureCut4( _
        True, False, False, _
        swEndCondThroughAll, swEndCondBlind, _
        0, 0, _
        False, False, False, False, _
        0, 0, _
        False, False, False, False, False, _
        False, False, _
        True, True, True)
    
    If swCutFeature Is Nothing Then
        Err.Raise vbObjectError + 1, , "孔特徵建立失敗"
    End If
    
    Debug.Print "中心孔已建立: 直徑 " & diameter & """"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立孔特徵失敗: " & Err.Description
End Sub

Sub SavePartFile(filePath As String)
    On Error GoTo ErrorHandler
    
    ' 確保目錄存在
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim dirPath As String
    dirPath = fso.GetParentFolderName(filePath)
    
    If Not fso.FolderExists(dirPath) Then
        fso.CreateFolder dirPath
    End If
    
    ' 保存檔案
    Dim bResult As Boolean
    bResult = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)
    
    If Not bResult Then
        Err.Raise vbObjectError + 1, , "檔案保存失敗"
    End If
    
    Debug.Print "檔案已保存: " & filePath
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "保存檔案失敗: " & Err.Description
End Sub'''

def generate_gear_assembly_functions():
    """生成齒輪裝配體輔助函數"""
    return '''
' === 齒輪裝配體輔助函數 ===

Sub CreateGear(diameter As Double, filePath As String)
    On Error GoTo ErrorHandler
    
    ' 建立新零件文檔
    Call CreateNewPartDocument
    Call SetUnitsToIPS
    
    ' 建立齒輪基本圓形草圖
    Dim swSketchManager As SldWorks.SketchManager
    Set swSketchManager = swModel.SketchManager
    
    ' 選擇前平面
    swModel.Extension.SelectByID2 "Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    
    ' 插入草圖
    swSketchManager.InsertSketch True
    
    ' 建立齒輪外圓 (半徑 = 直徑/2)
    swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/2
    
    ' 建立中心孔 (直徑的1/8作為軸孔)
    swSketchManager.CreateCircleByRadius 0, 0, 0, diameter/16
    
    ' 退出草圖
    swSketchManager.InsertSketch True
    
    ' 擠出齒輪 (厚度為直徑的1/10)
    Dim swFeatureManager As SldWorks.FeatureManager
    Set swFeatureManager = swModel.FeatureManager
    
    Dim swFeature As SldWorks.Feature
    Set swFeature = swFeatureManager.FeatureExtrusion2( _
        True, False, False, _
        swEndCondBlind, swEndCondBlind, _
        diameter/10, 0, _
        False, False, False, False, _
        1.396263402, 1.396263402, _
        False, False, False, False, _
        True, True, True)
    
    If swFeature Is Nothing Then
        Err.Raise vbObjectError + 1, , "齒輪擠出失敗"
    End If
    
    ' 切除中心孔
    ' 選擇中心圓
    swModel.Extension.SelectByID2 "", "SKETCHSEGMENT", 0, 0, 0, False, 0, Nothing, 0
    
    Dim swCutFeature As SldWorks.Feature
    Set swCutFeature = swFeatureManager.FeatureCut4( _
        True, False, False, _
        swEndCondThroughAll, swEndCondBlind, _
        0, 0, _
        False, False, False, False, _
        0, 0, _
        False, False, False, False, False, _
        False, False, _
        True, True, True)
    
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
    bResult = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)
    
    If Not bResult Then
        Err.Raise vbObjectError + 1, , "齒輪保存失敗"
    End If
    
    Debug.Print "齒輪已建立並保存: " & diameter & """直徑, 檔案: " & filePath
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立齒輪失敗: " & Err.Description
End Sub

Sub CreateAssemblyDocument()
    On Error GoTo ErrorHandler
    
    Dim swTemplate As String
    swTemplate = swApp.GetDocumentTemplate(swDocASSEMBLY, "", 0, 0, 0)
    
    Set swModel = swApp.NewDocument(swTemplate, 0, 0, 0)
    If swModel Is Nothing Then
        Err.Raise vbObjectError + 1, , "無法建立裝配體文檔"
    End If
    
    ' 設定為英制單位
    Dim swModelDocExt As SldWorks.ModelDocExtension
    Set swModelDocExt = swModel.Extension
    swModelDocExt.SetUserPreferenceInteger swUnitsLinear, 0, swINCHES
    
    Debug.Print "裝配體文檔已建立"
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "建立裝配體失敗: " & Err.Description
End Sub

Sub InsertComponent(filePath As String)
    On Error GoTo ErrorHandler
    
    Dim swAssemblyDoc As SldWorks.AssemblyDoc
    Set swAssemblyDoc = swModel
    
    ' 插入元件
    Dim swComponent As SldWorks.Component2
    Set swComponent = swAssemblyDoc.AddComponent5(filePath, 0, "", False, "", 0, 0, 0)
    
    If swComponent Is Nothing Then
        Err.Raise vbObjectError + 1, , "插入元件失敗: " & filePath
    End If
    
    Debug.Print "元件已插入: " & filePath
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "插入元件失敗: " & Err.Description
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
    
    ' 保存裝配體
    Dim bResult As Boolean
    bResult = swModel.SaveAs3(filePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)
    
    If Not bResult Then
        Err.Raise vbObjectError + 1, , "裝配體保存失敗"
    End If
    
    Debug.Print "裝配體已保存: " & filePath
    Exit Sub
    
ErrorHandler:
    Err.Raise Err.Number, Err.Source, "保存裝配體失敗: " & Err.Description
End Sub'''

def generate_vba_code(operations, api_info, request_text):
    """生成VBA代码 - 增強版"""
    
    # 檢查是否是齒輪裝配體工作流程
    if 'gear' in operations and 'assembly' in operations:
        return generate_gear_assembly_workflow(request_text)
    # 檢查是否是完整的零件建立流程
    elif ('new_part' in operations and 'sketch' in operations and 'extrude' in operations) or '建立新的零件' in request_text:
        return generate_complete_part_workflow(request_text)
    elif 'save' in operations:
        file_path = extract_file_path(request_text)
        return f'    Call SavePartFile("{file_path}")'
    elif 'sketch' in operations:
        dimensions = extract_dimensions(request_text)
        return f'    Call CreateRectangleSketch({dimensions.get("width", 1)}, {dimensions.get("height", 1)})'
    elif 'extrude' in operations:
        dimensions = extract_dimensions(request_text)
        return f'    Call CreateExtrusionFeature({dimensions.get("depth", 1)})'
    else:
        return '''    ' 通用操作
    Dim docTitle As String
    Dim docType As Long
    
    ' 獲取文檔信息
    docTitle = swModel.GetTitle()
    docType = swModel.GetType()
    
    Debug.Print "文檔標題: " & docTitle
    Debug.Print "文檔類型: " & docType'''

def generate_csharp_method(operations, api_info, method_name):
    """生成C#方法"""
    if 'save' in operations:
        return f'''        public void {method_name}()
        {{
            // C# Save implementation
            Console.WriteLine("Save operation");
        }}'''
    else:
        return f'''        public void {method_name}()
        {{
            // C# Generic operation
            Console.WriteLine("Generic operation");
        }}'''

def save_code_file(code, language, description, request_hash):
    """保存代码文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 生成文件名
    safe_desc = re.sub(r'[^\w\s-]', '', description)[:30]
    safe_desc = re.sub(r'[-\s]+', '_', safe_desc)
    
    if language.lower() == 'csharp':
        filename = f"{safe_desc}_{timestamp}.cs"
        filepath = Path(OUTPUT_DIR_CSHARP) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
    else:  # VBA
        filename = f"{safe_desc}_{timestamp}.bas"
        filepath = Path(OUTPUT_DIR_VBA) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    return str(filepath)

def generate_code(request_text, language='csharp'):
    """主代码生成函数"""
    print(f"正在分析请求: {request_text}")
    
    # 分析请求
    analysis = analyze_request(request_text)
    print(f"检测到操作: {analysis['operations']}")
    print(f"文档类型: {analysis['doc_type']}")
    
    # 查询API信息
    api_info = None
    for term in analysis['search_terms']:
        if term:
            api_info = query_api_info(term)
            if api_info['documents']:
                break
    
    if not api_info:
        api_info = {'documents': [], 'chunks': []}
    
    print(f"找到 {len(api_info['documents'])} 个相关API文档")
    print(f"找到 {len(api_info['chunks'])} 个相关代码片段")
    
    # 生成代码
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if language.lower() == 'csharp':
        # 生成C#代码
        class_name = "SolidWorksAutomation" + datetime.now().strftime("%Y%m%d%H%M%S")
        method_name = "Execute"
        
        methods = generate_csharp_method(analysis['operations'], api_info, method_name)
        
        code = CSHARP_TEMPLATE.format(
            description=request_text,
            timestamp=timestamp,
            class_name=class_name,
            class_description=f"自动生成的SolidWorks操作类: {request_text}",
            generated_methods=methods
        )
        
    else:  # VBA
        # 生成VBA代码 - 使用增強版生成函數
        main_code = generate_vba_code(analysis['operations'], api_info, request_text)
        
        # 如果是齒輪裝配工作流程，添加齒輪輔助函數
        if 'gear' in analysis['operations'] and 'assembly' in analysis['operations']:
            functions = generate_gear_assembly_functions()
        # 如果是完整工作流程，添加輔助函數
        elif '建立新的零件' in request_text or ('new_part' in analysis['operations'] and 'sketch' in analysis['operations']):
            functions = generate_vba_functions()
        
        code = VBA_TEMPLATE.format(
            description=request_text,
            timestamp=timestamp,
            generated_code=main_code,
            generated_functions=functions
        )
    
    # 保存文件
    filepath = save_code_file(code, language, request_text, hash(request_text))
    
    return {
        'filepath': filepath,
        'code': code,
        'api_info': api_info,
        'analysis': analysis
    }

def main():
    parser = argparse.ArgumentParser(description='SolidWorks API 代码生成器')
    parser.add_argument('--request', '-r', required=True, help='功能需求描述')
    parser.add_argument('--lang', '-l', choices=['csharp', 'vba'], default='csharp', help='目标语言')
    parser.add_argument('--output', '-o', help='输出文件路径（可选）')
    
    args = parser.parse_args()
    
    print("="*60)
    print("SolidWorks API 代码生成器 (改進版)")
    print("="*60)
    
    try:
        result = generate_code(args.request, args.lang)
        
        print(f"\n✅ 代码生成完成!")
        print(f"文件路径: {result['filepath']}")
        print(f"语言: {args.lang.upper()}")
        print(f"基于 {len(result['api_info']['documents'])} 个API文档生成")
        
        # 显示生成的代码片段
        print(f"\n生成的代码片段:")
        print("-" * 40)
        print(result['code'][:500] + "..." if len(result['code']) > 500 else result['code'])
        
    except Exception as e:
        print(f"❌ 代码生成失败: {e}")

if __name__ == "__main__":
    main()