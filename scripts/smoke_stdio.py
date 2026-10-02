"""Small local smoke check for the MCP catalogue. Full transport smoke is run after dependency install."""
import asyncio
from woo_connector.mcp.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {"list_orders","get_order","search_orders","list_products","get_product","search_products"}
    assert names == expected, names
    assert all(t.annotations and t.annotations.readOnlyHint for t in tools)
    print("MCP catalogue smoke test: PASS")

if __name__ == "__main__":
    asyncio.run(main())
