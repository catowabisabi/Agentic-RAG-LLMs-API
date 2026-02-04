# SolidWorks API Reference

## Core Interfaces

### SldWorks (Application Interface)
Primary interface for SolidWorks application control.

**Key Methods:**
- `ActiveDoc` - Get the currently active document
- `NewDocument(template, paperSize, width, height)` - Create new document
- `OpenDoc6(fileName, docType, options, configuration, errors, warnings)` - Open document
- `CloseDoc(docName)` - Close document
- `Visible` - Control application visibility

### ModelDoc2 (Document Interface)
Base interface for all SolidWorks documents (parts, assemblies, drawings).

**Key Methods:**
- `SaveAs3(fileName, version, options)` - Save document with options
- `GetType()` - Returns document type (swDocPART, swDocASSEMBLY, swDocDRAWING)
- `GetTitle()` - Get document title
- `FeatureManager` - Access to feature management
- `SelectionManager` - Access to selection operations
- `SketchManager` - Access to sketching operations

### PartDoc (Part Document Interface)
Extends ModelDoc2 for part-specific operations.

### AssemblyDoc (Assembly Document Interface)  
Extends ModelDoc2 for assembly-specific operations.

**Key Methods:**
- `AddComponent4(compName, configuration, x, y, z)` - Insert component
- `GetComponents(topLevelOnly)` - Get assembly components
- `AddMate4(mateType, alignType, flip, distance, angle)` - Create mates

### DrawingDoc (Drawing Document Interface)
Extends ModelDoc2 for drawing-specific operations.

**Key Methods:**
- `CreateDrawViewFromModelView3(modelName, viewName, x, y, options)` - Create drawing view
- `InsertTableAnnotation2(type, x, y, anchor, templateName, rows, cols)` - Insert table

## Feature Management

### FeatureManager
Manages features in the FeatureTree.

**Key Methods:**
- `FeatureExtrusion2(...)` - Create extrude feature
- `FeatureRevolve2(...)` - Create revolve feature
- `FeatureCut3(...)` - Create cut feature
- `InsertMirrorFeature2(...)` - Create mirror feature
- `InsertPatternTableDriven2(...)` - Create driven pattern

### Feature
Represents individual features.

**Key Properties:**
- `Name` - Feature name
- `GetTypeName2()` - Feature type
- `IsSuppressed()` - Suppression state
- `SetSuppression2(state, markForDecoupling, config)` - Control suppression

## Sketching

### SketchManager
Manages sketch operations.

**Key Methods:**
- `InsertSketch(planar)` - Start/end sketch
- `CreateLine(x1, y1, z1, x2, y2, z2)` - Create line
- `CreateArc(xc, yc, zc, x1, y1, z1, x2, y2, z2, direction)` - Create arc
- `CreateCornerRectangle(x1, y1, z1, x3, y3, z3)` - Create rectangle
- `CreateCircleByRadius(xc, yc, zc, radius)` - Create circle

## Selection Management

### SelectionMgr
Manages object selection.

**Key Methods:**
- `GetSelectedObject6(mark, selIndex)` - Get selected object
- `GetSelectionCount2(mark)` - Get selection count
- `AddSelectionListObject(object, selData)` - Add to selection
- `CreateSelectData()` - Create selection data object

## Common Enumerations

### swDocumentTypes_e
- `swDocNONE = 0`
- `swDocPART = 1` 
- `swDocASSEMBLY = 2`
- `swDocDRAWING = 3`

### swSaveAsVersion_e
- `swSaveAsCurrentVersion = 0`
- `swSaveAsOptions_Silent = 1`
- `swSaveAsOptions_Copy = 2`

### swFeatureNameID_e
- `swFmExtrude = 24`
- `swFmCut = 25`
- `swFmRevolve = 27`
- `swFmSweep = 28`
- `swFmLoft = 29`

## Error Handling Patterns

### Return Value Checking
Most SolidWorks API methods return boolean success indicators:

```csharp
bool result = swModel.SaveAs3(fileName, version, options);
if (!result) {
    // Handle error
    throw new Exception("Save operation failed");
}
```

### GetLastError Pattern
Some operations provide detailed error information:

```csharp
int errors = 0, warnings = 0;
swApp.OpenDoc6(fileName, docType, options, "", ref errors, ref warnings);
if (errors != 0) {
    // Handle specific errors
}
```

### COM Exception Handling
Always wrap COM operations in try-catch:

```csharp
try {
    // SolidWorks API call
} 
catch (COMException ex) {
    // Handle COM-specific errors
}
catch (Exception ex) {
    // Handle general errors
}
```

## Best Practices

### COM Object Lifecycle
- Always release COM objects when done
- Use using statements where possible
- Call GC.Collect() after major operations

### Performance Optimization
- Suppress view updates during batch operations: `swModel.FeatureManager.EnableFeatureTree = false`
- Use selection sets for bulk operations
- Minimize document switches in assemblies

### Error Prevention
- Check for null references before API calls
- Validate input parameters
- Use appropriate coordinate systems
- Handle document state changes (active document switching)

## File Format Support

### Export Formats
- PDF, DXF, DWG, STEP, IGES, STL, 3MF
- Various image formats (JPG, PNG, BMP, TIFF)
- Neutral formats (Parasolid, ACIS)

### Import Formats  
- STEP, IGES, Parasolid, ACIS
- 3D formats (3MF, OBJ)
- 2D formats (DXF, DWG)

## Units and Coordinate Systems

### Default Units
- Length: Meters
- Angles: Radians  
- Mass: Kilograms

### Coordinate Systems
- Model coordinates (global)
- Component coordinates (local to component)
- View coordinates (relative to drawing view)