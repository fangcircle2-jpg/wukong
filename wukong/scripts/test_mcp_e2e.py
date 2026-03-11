"""
MCP End-to-End Integration Test

Uses the real @modelcontextprotocol/server-filesystem MCP server via npx.
Tests the full chain: MCPManager → McpClient → mcp SDK → real MCP server.

Prerequisites:
    - Node.js / npx installed
    - Internet access (to download @modelcontextprotocol/server-filesystem via npx)

Run:
    .venv/Scripts/python scripts/test_mcp_e2e.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path


async def main() -> int:
    # 1. Prepare a temp directory the filesystem server can access
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "hello.txt").write_text("Hello from wukong MCP test!\n", encoding="utf-8")
        (tmp / "data.json").write_text('{"key": "value"}\n', encoding="utf-8")

        print(f"[setup] temp dir: {tmp}")
        print(f"[setup] files: {[f.name for f in tmp.iterdir()]}")

        # 2. Build MCPSettings pointing to the filesystem server
        from wukong.core.mcp.config import MCPServerConfig, MCPSettings
        settings = MCPSettings(
            mcpServers={
                "filesystem": MCPServerConfig(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", str(tmp)],
                    timeout=30_000,
                )
            }
        )

        # 3. Connect via MCPManager and register tools
        from wukong.core.mcp.manager import MCPManager
        from wukong.core.tools.registry import ToolRegistry
        registry = ToolRegistry()
        manager = MCPManager(settings)

        print("\n[connect] connecting to filesystem MCP server...")
        async with manager:
            counts = await manager.connect_all(registry)
            if not counts:
                print("[FAIL] No servers connected")
                return 1

            print(f"[connect] servers: {counts}")
            print(f"[tools]  registered: {registry.list_names()}")

            # 4. Verify expected tools are present
            expected = {"filesystem__read_file", "filesystem__list_directory"}
            registered = set(registry.list_names())
            missing = expected - registered
            if missing:
                print(f"[WARN] Expected tools not found: {missing}")
                print(f"       Available: {sorted(registered)}")
            else:
                print(f"[OK]   Expected tools present: {sorted(expected)}")

            # 5. Call list_directory
            print("\n[call]  filesystem__list_directory ...")
            list_tool = registry.get("filesystem__list_directory")
            if list_tool is None:
                # Try to find any list-like tool
                list_tool = next(
                    (registry.get(n) for n in registry.list_names() if "list" in n.lower()),
                    None,
                )
            if list_tool:
                result = await list_tool.execute(
                    workspace_dir=str(tmp),
                    mcp_manager=manager,
                    path=str(tmp),
                )
                print(f"[result] success={result.success}")
                if result.success:
                    print(f"[result] output:\n{result.output}")
                else:
                    print(f"[result] error: {result.error}")
            else:
                print("[SKIP]  no list tool found")

            # 6. Call read_file
            print("\n[call]  filesystem__read_file ...")
            read_tool = registry.get("filesystem__read_file")
            if read_tool is None:
                read_tool = next(
                    (registry.get(n) for n in registry.list_names() if "read" in n.lower()),
                    None,
                )
            if read_tool:
                result = await read_tool.execute(
                    workspace_dir=str(tmp),
                    mcp_manager=manager,
                    path=str(tmp / "hello.txt"),
                )
                print(f"[result] success={result.success}")
                if result.success:
                    print(f"[result] output: {result.output!r}")
                    assert "Hello from wukong" in (result.output or ""), "Content mismatch!"
                    print("[OK]   Content verified.")
                else:
                    print(f"[result] error: {result.error}")
            else:
                print("[SKIP]  no read tool found")

        print("\n[disconnect] done, all connections closed.")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
