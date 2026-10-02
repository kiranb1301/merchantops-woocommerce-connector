import pytest
pytest.importorskip("mcp")

def test_mcp_exposes_exact_read_only_surface():
    from woo_connector.mcp.server import mcp
    names={x.name for x in __import__("asyncio").run(mcp.list_tools())}
    assert names=={"list_orders","get_order","search_orders","list_products","get_product","search_products"}
