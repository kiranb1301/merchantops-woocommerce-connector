from __future__ import annotations
from typing import Final

READ_ONLY_TOOLS: Final[frozenset[str]] = frozenset({
    "list_orders", "get_order", "search_orders",
    "list_products", "get_product", "search_products",
})
FORBIDDEN_WRITE_OPERATIONS: Final[frozenset[str]] = frozenset({
    "create", "update", "delete", "refund",
})
