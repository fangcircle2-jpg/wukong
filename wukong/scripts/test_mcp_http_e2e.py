"""
MCP HTTP End-to-End Integration Test

Uses the real @modelcontextprotocol/server-everything MCP server via npx.
Tests HTTP-based transports: Streamable HTTP and SSE.

The full chain: MCPManager → McpClient → mcp SDK → real MCP server (over HTTP).

Prerequisites:
    - Node.js / npx installed
    - Internet access (to download @modelcontextprotocol/server-everything via npx)

Run:
    .venv/Scripts/python scripts/test_mcp_http_e2e.py
"""

import asyncio
import socket
import subprocess
import sys
import time

PORT = 3001


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("localhost", port)) == 0


async def wait_for_port(port: int, timeout: float = 30.0) -> bool:
    """Poll until the server is listening on the given port."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if is_port_open(port):
            return True
        await asyncio.sleep(0.5)
    return False


def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children (Windows-compatible)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
        )
    else:
        import signal
        import os
        os.killpg(os.getpgid(pid), signal.SIGTERM)


async def test_transport(
    transport_label: str,
    server_transport_arg: str,
    mcp_url: str,
    mcp_transport: str,
) -> bool:
    """Test a single HTTP-based transport against server-everything.

    Args:
        transport_label: Human-readable name for log output.
        server_transport_arg: Arg passed to server-everything ("streamableHttp" or "sse").
        mcp_url: URL for MCPServerConfig.url.
        mcp_transport: Transport type for MCPServerConfig.transport ("http" or "sse").

    Returns:
        True if all checks passed.
    """
    print(f"\n{'=' * 60}")
    print(f"  {transport_label}")
    print(f"{'=' * 60}")

    # --- 1. Start server-everything as subprocess ---
    print(f"[start]   npx server-everything {server_transport_arg} ...")
    cmd = f"npx -y @modelcontextprotocol/server-everything {server_transport_arg}"
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
    )

    try:
        # --- 2. Wait for server ready ---
        print(f"[wait]    waiting for port {PORT} ...")
        ready = await wait_for_port(PORT, timeout=30.0)
        if not ready:
            print(f"[FAIL]    Server did not start on port {PORT} within 30s")
            return False
        print(f"[ready]   Server listening on port {PORT}")

        # --- 3. Connect via MCPManager ---
        from wukong.core.mcp.config import MCPServerConfig, MCPSettings
        from wukong.core.mcp.manager import MCPManager
        from wukong.core.tools.registry import ToolRegistry

        settings = MCPSettings(
            mcpServers={
                "everything": MCPServerConfig(
                    url=mcp_url,
                    transport=mcp_transport,
                    timeout=30_000,
                )
            }
        )
        registry = ToolRegistry()
        manager = MCPManager(settings)

        print("[connect] connecting to MCP server ...")
        async with manager:
            counts = await manager.connect_all(registry)
            if not counts:
                print("[FAIL]    No servers connected")
                return False

            tool_names = sorted(registry.list_names())
            print(f"[connect] ok — {counts['everything']} tool(s) registered")
            print(f"[tools]   {tool_names}")

            # --- 4. Call echo tool ---
            ok = True
            echo_tool = registry.get("everything__echo")
            if echo_tool:
                print("\n[call]    everything__echo ...")
                result = await echo_tool.execute(
                    workspace_dir="",
                    mcp_manager=manager,
                    message="hello from wu-zhao HTTP e2e test!",
                )
                print(f"[result]  success={result.success}")
                if result.success and result.output:
                    print(f"[result]  output: {result.output!r}")
                    if "hello from wu-zhao" in result.output:
                        print("[OK]      echo content verified")
                    else:
                        print("[FAIL]    echo content mismatch")
                        ok = False
                else:
                    print(f"[FAIL]    echo error: {result.error}")
                    ok = False
            else:
                print("[SKIP]    echo tool not found")

            # --- 5. Call get-sum tool ---
            sum_tool = registry.get("everything__get-sum")
            if sum_tool:
                print("\n[call]    everything__get-sum(a=2, b=3) ...")
                result = await sum_tool.execute(
                    workspace_dir="",
                    mcp_manager=manager,
                    a=2,
                    b=3,
                )
                print(f"[result]  success={result.success}")
                if result.success and result.output:
                    print(f"[result]  output: {result.output!r}")
                    if "5" in result.output:
                        print("[OK]      get-sum result verified (2+3=5)")
                    else:
                        print("[FAIL]    get-sum result mismatch")
                        ok = False
                else:
                    print(f"[FAIL]    get-sum error: {result.error}")
                    ok = False
            else:
                print("[SKIP]    get-sum tool not found")

        status = "PASS" if ok else "FAIL"
        print(f"\n[{status}]  {transport_label} done")
        return ok

    finally:
        # --- 6. Kill server ---
        print(f"[cleanup] stopping server (pid={proc.pid}) ...")
        kill_process_tree(proc.pid)
        print("[cleanup] done")


async def main() -> int:
    results: dict[str, bool] = {}

    # Test 1: Streamable HTTP
    results["Streamable HTTP"] = await test_transport(
        transport_label="Streamable HTTP (transport=http)",
        server_transport_arg="streamableHttp",
        mcp_url=f"http://localhost:{PORT}/mcp",
        mcp_transport="http",
    )

    await asyncio.sleep(2)

    # Test 2: SSE
    results["SSE"] = await test_transport(
        transport_label="SSE (transport=sse)",
        server_transport_arg="sse",
        mcp_url=f"http://localhost:{PORT}/sse",
        mcp_transport="sse",
    )

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    all_ok = True
    for name, passed in results.items():
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name}")
        if not passed:
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
