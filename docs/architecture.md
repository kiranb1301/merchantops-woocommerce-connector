# MerchantOps architecture

```text
AI Agent
   |
   | MCP / Streamable HTTP
   v
FastAPI application
   |
   +--> /health /ready
   +--> /connect /callback
   |
   +--> /mcp
          |
       MCPServer
          |
    +-----+------------------+
    |                        |
 Order tools             Product tools
    |                        |
 OrderService           ProductService
    +-----------+------------+
                |
        WooCommerceClient
                |
        WooCommerce REST v3
```

Cross-cutting layers:
- Pydantic request/response models
- encrypted credential storage
- read-only permissions
- rate limiting
- retry/backoff + Retry-After
- circuit breaker
- PII-minimised response shaping
- structured logging and audit events

The MCP layer is intentionally thin. Business/API logic lives in services and the WooCommerce client.
