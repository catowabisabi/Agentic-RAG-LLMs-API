---
name: sw-api-code-generator
description: Query SolidWorks API documentation database to provide structured API information for Agent code generation. This skill extracts API methods, parameters, and code examples from the comprehensive SolidWorks database, which the Agent then uses to generate accurate VBA or C# automation code. Use when users request SolidWorks API programming help, code generation, or need specific API usage information.
---

# SolidWorks API Documentation Query Skill

Agent skill for extracting SolidWorks API information from a comprehensive database. This skill provides structured API data that the Agent uses to generate accurate SolidWorks automation code.

## How It Works

### 🔧 **Skill Responsibility:**
- Query 689MB SolidWorks API documentation database
- Extract relevant API methods, parameters, and code examples  
- Return structured JSON data to the Agent

### 🤖 **Agent Responsibility:**
- Use skill-provided API data to understand correct usage
- Generate accurate VBA or C# code based on real API documentation
- Handle error checking and code structure

## Quick Start

Query API information for Agent use:
```bash
python scripts/api_query_tool.py --search FeatureExtrusion SaveAs3 --output json
```

View human-readable results:
```bash
python scripts/api_query_tool.py --search SketchManager --output text
```

## Core Capabilities

- **Smart API Discovery**: Query 609MB documentation database for precise API information
- **Dual Language Support**: Generate production-ready C# and VBA code
- **Complete Error Handling**: Include try-catch blocks and resource cleanup
- **Official Examples**: Base generation on 2,396 verified SolidWorks code samples
- **Context-Aware**: Generate code with proper initialization and cleanup

## Code Generation Workflow

1. **Request Analysis**: Parse user requirements and identify SolidWorks operations
2. **API Lookup**: Query documentation database for relevant interfaces and methods
3. **Template Selection**: Choose appropriate code structure (C# class or VBA module)
4. **Code Assembly**: Combine API calls with best practices and error handling
5. **File Output**: Save with descriptive names and timestamps

## Supported Operations

### Document Operations
- Open/Save/Close documents
- Export to various formats (PDF, STEP, IGES, STL)
- Document properties and metadata
- Configuration management

### Part Operations  
- Feature creation (Extrude, Revolve, Sweep, Loft)
- Sketching operations
- Pattern and mirror features
- Material assignment

### Assembly Operations
- Component insertion and positioning
- Mate creation and editing
- Interference detection
- Bill of Materials (BOM) operations

### Drawing Operations
- View creation and manipulation
- Annotation and dimensioning
- Sheet management
- Drawing templates

### Batch Operations
- Bulk file processing
- Automated workflows
- Progress reporting
- Error logging

## Generated Code Structure

### C# Template
```csharp
namespace SolidWorksAutomation {
    public class AutomationClass {
        private SldWorks swApp;
        private ModelDoc2 swModel;
        
        // Initialization with error handling
        // Main operation methods
        // COM object cleanup
    }
}
```

### VBA Template  
```vba
Option Explicit
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2

Sub Main()
    ' SolidWorks connection
    ' Error handling
    ' Main operations
End Sub
```

## Database Resources

The skill uses three specialized databases located in `assets/`:

- **sw_api_doc.db** (609MB): Complete API documentation with 11,087 documents
- **sw_api_doc_vector.db** (51MB): Vector embeddings for semantic search  
- **founding.db** (New): Learning database for API error corrections and solutions

### Founding Database System

The `founding.db` is a learning database that records API errors discovered during code generation and their solutions. This enables:

- **Error Prevention**: Check for known issues before generating code
- **Solution Reuse**: Apply proven fixes to similar problems
- **Knowledge Accumulation**: Build expertise over time
- **Pattern Recognition**: Identify common API usage mistakes

#### Founding Record Format

Each finding record contains:
- **Error Type**: UNDEFINED_CONSTANT, ARG_NOT_OPTIONAL, API_USAGE_ERROR
- **API Function**: Specific SolidWorks API method affected
- **Error Description**: Detailed problem description
- **Original Code**: Problematic code snippet
- **Corrected Code**: Fixed code snippet
- **API Constants**: JSON object with correct constant values
- **Solution Explanation**: How and why the fix works
- **Skill Query Used**: Query that helped find the solution
- **Tags**: Categorization labels for easy searching
- **Severity**: low, medium, high, critical

#### Usage Workflow

1. **Before Code Generation**: Search founding.db for similar API usage patterns
2. **During Error Fixing**: Query the database for known solutions
3. **After Problem Resolution**: Record new findings for future reference

#### Founding Manager Commands

```bash
# Search for similar errors
python scripts/founding_manager.py search --api-function "SetUserPreferenceInteger" --limit 5

# Filter by error type
python scripts/founding_manager.py search --error-type "UNDEFINED_CONSTANT"

# Search by tags
python scripts/founding_manager.py search --tags "units,constants" --severity high

# Export all findings
python scripts/founding_manager.py export --output findings_backup.json
```

Both documentation and learning databases are automatically queried during code generation to ensure accuracy and incorporate lessons learned from previous error resolutions.

## Error Handling Standards

All generated code includes:
- Connection verification
- Operation result checking  
- Exception handling with meaningful messages
- Resource cleanup (COM objects in C#)
- Progress feedback for long operations

## File Management

Generated files are saved with descriptive names:
- **Format**: `{Operation}_{YYYYMMDD}_{HHMMSS}.{ext}`
- **C# files**: Saved as `.cs` files
- **VBA files**: Saved as `.bas` files
- **Location**: Current working directory or specified path

## Advanced Features

### API Intelligence
The system can identify:
- Required interfaces for specific operations
- Parameter types and validation
- Return value handling
- Related API methods and properties

### Learning System
The founding.db learning database provides:
- **Error Pattern Recognition**: Identify recurring API usage mistakes
- **Solution Templates**: Reuse proven fixes for similar problems
- **Knowledge Evolution**: Continuously improve code generation accuracy
- **Predictive Prevention**: Avoid known issues before they occur

### Code Quality
Generated code follows SolidWorks best practices:
- Proper COM object management
- Standard error handling patterns
- Performance optimization
- Documentation comments

### Extensibility
Easily add support for:
- New SolidWorks APIs
- Additional output formats
- Custom code templates
- Specialized workflows

Use this skill whenever you need to transform SolidWorks operations into executable code, whether for one-time automation tasks or building comprehensive SolidWorks applications.