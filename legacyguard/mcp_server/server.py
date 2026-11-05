"""Pull queries from Claude over stdio (FR-21). Reads the same SQLite index as the hooks (D-019)."""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from guardlib import config as cfgmod
from guardlib import impact as impact_lib
from guardlib.paths import find_root
from indexer import db

server = MCPServer("legacyguard")


def _load():
    root = find_root(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return cfgmod.load_config(root)


@server.tool()
def impact(symbol: str, depth: int = 3) -> str:
    """Who depends on a function: callers up to 3 hops, routes, tests, co-changed files. Each item names its source.

    Name matches can over-match same-named functions and miss dynamic calls.
    """
    try:
        cfg = _load()
    except (cfgmod.ConfigMissing, cfgmod.ConfigError) as exc:
        return f"LegacyGuard is inactive here: {exc}"
    conn = db.connect(cfg.root)
    try:
        return impact_lib.impact_text(conn, cfg, symbol, min(max(depth, 1), impact_lib.HOPS))
    finally:
        conn.close()


def main() -> None:
    server.run("stdio")
