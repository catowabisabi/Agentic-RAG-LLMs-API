"""
MCP Package

Model Context Protocol server and providers for the multi-agent system.

此模組使用延遲導入避免循環導入問題。
"""

def get_mcp_server():
    """延遲導入 MCPAgentServer 避免循環導入"""
    from mcp.server import MCPAgentServer
    return MCPAgentServer

__all__ = ["get_mcp_server"]
