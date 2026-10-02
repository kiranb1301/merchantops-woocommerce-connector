"""End-to-end MCP-over-HTTP verification.

Prerequisites:
  1. Start the app: uvicorn woo_connector.main:app --host 127.0.0.1 --port 8000
  2. Install the project dependencies, including mcp.

This verifies the real /mcp transport, discovers all six tools, and optionally
calls one read-only tool when WooCommerce credentials are configured.
"""

from __future__ import annotations

import argparse
import asyncio

from mcp import Client

EXPECTED = {
    "list_orders",
    "get_order",
    "search_orders",
    "list_products",
    "get_product",
    "search_products",
}


async def main(url: str, call_tool: bool) -> None:
    async with Client(url) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        missing = EXPECTED - names
        extra = names - EXPECTED
        if missing or extra:
            raise SystemExit(f"MCP tool contract mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

        print(f"MCP /mcp connection: PASS ({url})")
        print("Tools:", ", ".join(sorted(names)))

        if call_tool:
            result = await client.call_tool("list_products", {"page": 1, "per_page": 1})
            if result.is_error:
                raise SystemExit(f"MCP tool call failed: {result.content}")
            print("list_products tool call: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--call-tool", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.call_tool))
