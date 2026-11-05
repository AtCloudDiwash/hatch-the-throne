"""MCP server stub (T1.1). Tools arrive in T3.7."""
from mcp.server.mcpserver import MCPServer

server = MCPServer("legacyguard")


def main() -> None:
    server.run("stdio")
