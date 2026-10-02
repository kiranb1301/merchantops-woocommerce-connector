# MCP tool contract

Exactly six read-only primitives are exposed:

| Tool | Purpose |
|---|---|
| `list_orders` | Paginated order listing/filtering |
| `get_order` | One order by ID |
| `search_orders` | Search/filter orders by text, status, customer and dates |
| `list_products` | Paginated product catalogue |
| `get_product` | One product by ID |
| `search_products` | Product search using supported WooCommerce search fields |

No customer write operations, refunds, order mutations, or product mutations are exposed.

Pagination uses `page`/`per_page` externally and an opaque `next_cursor` for agent continuation.
The cursor is bound to the query filters so it cannot be reused for a different query.

Responses are normalized rather than passing through raw WooCommerce JSON.
