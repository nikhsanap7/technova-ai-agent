"""MCP client: starts the MCP server, discovers tools and calls them.

For simplicity each call starts a fresh server process (stdio). That is slower
than keeping one open, but very robust, and fine for this project.
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,            # the Python from your .venv
    args=["-m", "tools.mcp_server"],
    cwd=str(PROJECT_ROOT),
)


async def list_tools() -> list[dict]:
    """Discover tools: returns name, description and input schema of each."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {"name": t.name, "description": t.description,
                 "input_schema": t.inputSchema}
                for t in result.tools
            ]


async def call_tool(name: str, arguments: dict) -> dict:
    """Call one tool and return its result as a dict."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            text = result.content[0].text if result.content else ""
            if result.isError:
                return {"ok": False, "error": text or "Tool call failed"}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"ok": False, "error": f"Unreadable tool output: {text}"}


# Synchronous wrappers (handy for Streamlit later)
def list_tools_sync() -> list[dict]:
    return asyncio.run(list_tools())


def call_tool_sync(name: str, arguments: dict) -> dict:
    return asyncio.run(call_tool(name, arguments))


if __name__ == "__main__":
    # Manual test: run with  python -m tools.mcp_client
    print("=== Discovered tools ===")
    for t in list_tools_sync():
        print(f"- {t['name']}: {list(t['input_schema'].get('properties', {}).keys())}")

    tests = [
        ("get_customer", {"customer_id": 1025}),
        ("search_orders", {"status": "Pending", "country": "Germany"}),
        ("search_products", {"stock_below": 10}),
        ("search_unpaid_invoices", {}),
        ("get_customer", {"customer_id": 9999}),
        ("update_order_status", {"order_id": 9999, "status": "Delivered"}),
        ("update_order_status", {"order_id": 5001, "status": "Banana"}),
    ]
    for name, args in tests:
        print(f"\n>>> {name} {args}")
        print(json.dumps(call_tool_sync(name, args), indent=2)[:600])