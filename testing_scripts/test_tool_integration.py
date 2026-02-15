"""
Test Tool Agent Integration
============================

測試新整合的MCP Providers:
- Excel Provider (6 tools)
- File Control Provider (5 tools)  
- Brave Search Provider (2 tools)
- Communication Provider (2 tools)

用法:
    python testing_scripts/test_tool_integration.py
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.auxiliary.tool_agent import ToolAgent


async def test_excel_tools():
    """測試Excel工具"""
    print("\n" + "="*60)
    print("Testing Excel Tools")
    print("="*60)
    
    agent = ToolAgent()
    
    # Test 1: Create Excel
    print("\n[Test 1] Create Excel File")
    result = await agent.execute_tool(
        tool_name="excel_create",
        tool_input={
            "file_path": "test_output.xlsx",
            "sheet_names": ["Sheet1", "Data"]
        }
    )
    print(f"Result: {result}")
    
    # Test 2: Write Excel
    print("\n[Test 2] Write Excel Data")
    result = await agent.execute_tool(
        tool_name="excel_write",
        tool_input={
            "file_path": "test_output.xlsx",
            "sheet_name": "Sheet1",
            "data": [
                ["Name", "Age", "City"],
                ["Alice", 30, "NYC"],
                ["Bob", 25, "LA"]
            ],
            "start_cell": "A1"
        }
    )
    print(f"Result: {result}")
    
    # Test 3: Read Excel
    print("\n[Test 3] Read Excel Data")
    result = await agent.execute_tool(
        tool_name="excel_read",
        tool_input={
            "file_path": "test_output.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:C3"
        }
    )
    print(f"Result: {result}")


async def test_file_tools():
    """測試檔案控制工具"""
    print("\n" + "="*60)
    print("Testing File Control Tools")
    print("="*60)
    
    agent = ToolAgent()
    
    # Test 1: Write Text File
    print("\n[Test 1] Write Text File")
    result = await agent.execute_tool(
        tool_name="file_write_text",
        tool_input={
            "path": "test_file.txt",
            "content": "Hello from Tool Agent!\nThis is a test file."
        }
    )
    print(f"Result: {result}")
    
    # Test 2: Read Text File
    print("\n[Test 2] Read Text File")
    result = await agent.execute_tool(
        tool_name="file_read_text",
        tool_input={
            "path": "test_file.txt"
        }
    )
    print(f"Result: {result}")
    
    # Test 3: Write JSON
    print("\n[Test 3] Write JSON File")
    result = await agent.execute_tool(
        tool_name="file_write_json",
        tool_input={
            "path": "test_data.json",
            "content": {
                "name": "Tool Agent",
                "version": "2.0",
                "features": ["Excel", "FileControl", "BraveSearch", "Communication"]
            }
        }
    )
    print(f"Result: {result}")
    
    # Test 4: Read JSON
    print("\n[Test 4] Read JSON File")
    result = await agent.execute_tool(
        tool_name="file_read_json",
        tool_input={
            "path": "test_data.json"
        }
    )
    print(f"Result: {result}")


async def test_brave_search():
    """測試Brave Search工具（需要API Key）"""
    print("\n" + "="*60)
    print("Testing Brave Search Tools")
    print("="*60)
    
    # Check if API key is set
    if not os.getenv("BRAVE_API_KEY"):
        print("\n⚠️ BRAVE_API_KEY not set in environment")
        print("Set it with: export BRAVE_API_KEY=your_key_here")
        print("Skipping Brave Search tests...")
        return
    
    agent = ToolAgent()
    
    # Test 1: Web Search
    print("\n[Test 1] Web Search")
    result = await agent.execute_tool(
        tool_name="brave_web_search",
        tool_input={
            "query": "Python asyncio tutorial",
            "count": 3
        }
    )
    print(f"Result: {result}")


async def test_communication():
    """測試Communication工具（需要Gmail OAuth）"""
    print("\n" + "="*60)
    print("Testing Communication Tools")
    print("="*60)
    
    print("\n⚠️ Communication tools require Gmail OAuth setup")
    print("Skipping Communication tests (requires manual OAuth flow)...")
    print("To test manually, use:")
    print("  - comm_send_email: Send email via Gmail")
    print("  - comm_read_emails: Read recent Gmail messages")


async def main():
    """運行所有測試"""
    print("\n" + "="*70)
    print(" Tool Agent Integration Tests")
    print("="*70)
    print("Testing MCP Providers integrated into Tool Agent:")
    print("  ✓ Excel Provider (6 tools)")
    print("  ✓ File Control Provider (5 tools)")
    print("  ✓ Brave Search Provider (2 tools)")
    print("  ✓ Communication Provider (2 tools)")
    print("="*70)
    
    try:
        # Test Excel Tools
        await test_excel_tools()
        
        # Test File Control Tools
        await test_file_tools()
        
        # Test Brave Search (if API key available)
        await test_brave_search()
        
        # Communication info (requires OAuth setup)
        await test_communication()
        
        print("\n" + "="*70)
        print("✅ All Tests Completed!")
        print("="*70)
        print("\nGenerated Files:")
        print("  - test_output.xlsx (Excel file)")
        print("  - test_file.txt (Text file)")
        print("  - test_data.json (JSON file)")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
