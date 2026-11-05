"""T3.7: the MCP tool answers over the real stdio protocol."""
import asyncio
import json
import os
import sys

import pytest

from conftest import PLUGIN, REPO, commit_all


def call_tool(root, tool, args):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=[str(PLUGIN / "scripts" / "mcp_launch.py")],
                                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool(tool, args)
                return [t.name for t in tools.tools], result.content[0].text
    return asyncio.run(asyncio.wait_for(go(), 40))


def test_impact_over_stdio(repo):
    (repo / "b.py").write_text("from app import add\n\ndef total(x):\n    return add(x, 1)\n")
    commit_all(repo)
    from guardlib import config as cfgmod
    from indexer.__main__ import refresh
    refresh(cfgmod.load_config(str(repo)))
    names, text = call_tool(repo, "impact", {"symbol": "add"})
    assert "impact" in names
    assert "total() [names]" in text
