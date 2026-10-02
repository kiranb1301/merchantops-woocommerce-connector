from __future__ import annotations

import functools, os
from typing import Any

from pydantic import BaseModel

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from ..config.settings import build_client_from_env
from ..models.errors import ConnectorError
from ..models.orders import OrderSearchRequest
from ..models.products import ProductSearchRequest
from ..observability.logging import configure_logging, new_request_id
from ..observability.audit import audit_tool_call
from ..services.order_service import OrderService
from ..services.product_service import ProductService

mcp = MCPServer(
    "merchantops-woocommerce",
    instructions=(
        "Read-only WooCommerce merchant connector. Use orders and products tools to retrieve "
        "merchant data. Customer email and phone are masked. No write, refund, delete, or mutation "
        "operations are exposed. Pagination is explicit through page/per_page and next_cursor."
    ),
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)

_client = None
_orders = None
_products = None


def _services():
    global _client, _orders, _products
    if _orders is None:
        _client = build_client_from_env()
        _orders, _products = OrderService(_client), ProductService(_client)
    return _orders, _products


def set_services(orders=None, products=None):
    global _orders, _products
    _orders, _products = orders, products


def _serialize(value: Any) -> Any:
    """Convert internal typed models to MCP-safe JSON-compatible data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _guard(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        rid = new_request_id()
        try:
            result = _serialize(await fn(*args, **kwargs))
            audit_tool_call(
                request_id=rid,
                tool=fn.__name__,
                status="success",
                result_count=len(result.get("items", [])) if isinstance(result, dict) and "items" in result else None,
            )
            return result
        except ConnectorError as exc:
            audit_tool_call(request_id=rid, tool=fn.__name__, status=exc.code)
            return {"error": exc.to_dict(), "request_id": rid}
        except Exception:
            audit_tool_call(request_id=rid, tool=fn.__name__, status="internal_error")
            return {"error": {"code":"internal_error","message":"Unexpected connector failure."}, "request_id":rid}
    return wrapper


@mcp.tool(annotations=READ_ONLY)
@_guard
async def list_orders(page:int=1, per_page:int=20, status:str="any",
                      after:str|None=None, before:str|None=None, cursor:str|None=None) -> dict[str,Any]:
    """List merchant orders with optional status/date filters. Read-only."""
    orders,_ = _services()
    return await orders.list_orders(page=page,per_page=per_page,status=status,after=after,before=before,cursor=cursor)


@mcp.tool(annotations=READ_ONLY)
@_guard
async def get_order(order_id:int) -> dict[str,Any]:
    """Retrieve one merchant order by WooCommerce order ID. Read-only."""
    orders,_ = _services()
    return await orders.get_order(order_id)


@mcp.tool(annotations=READ_ONLY)
@_guard
async def search_orders(query:str|None=None, status:str|None=None, customer_id:int|None=None,
                        after:str|None=None, before:str|None=None, page:int=1,
                        per_page:int=20, cursor:str|None=None) -> dict[str,Any]:
    """Search/filter multiple merchant orders by text, status, customer or date range. Read-only."""
    orders,_ = _services()
    req=OrderSearchRequest(query=query,status=status,customer_id=customer_id,after=after,before=before,page=page,per_page=per_page)
    return await orders.search_orders(req,cursor)


@mcp.tool(annotations=READ_ONLY)
@_guard
async def list_products(page:int=1, per_page:int=20, status:str|None=None,
                        cursor:str|None=None) -> dict[str,Any]:
    """List merchant catalogue products. Read-only."""
    _,products=_services()
    return await products.list_products(page=page,per_page=per_page,status=status,cursor=cursor)


@mcp.tool(annotations=READ_ONLY)
@_guard
async def get_product(product_id:int) -> dict[str,Any]:
    """Retrieve one merchant product by WooCommerce product ID. Read-only."""
    _,products=_services()
    return await products.get_product(product_id)


@mcp.tool(annotations=READ_ONLY)
@_guard
async def search_products(query:str|None=None, search_fields:list[str]|None=None,
                          page:int=1, per_page:int=20, cursor:str|None=None) -> dict[str,Any]:
    """Search merchant products by name, SKU or supported WooCommerce search fields. Read-only."""
    _,products=_services()
    req=ProductSearchRequest(query=query,search_fields=search_fields or ["name","sku"],page=page,per_page=per_page)
    return await products.search_products(req,cursor)


def configure() -> None:
    configure_logging(os.environ.get("LOG_LEVEL","INFO"))


def main() -> None:
    configure()
    mcp.run(transport="stdio")
