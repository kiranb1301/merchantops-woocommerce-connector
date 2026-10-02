# MerchantOps — WooCommerce Agent Connector

A secure, read-only, MCP-compatible WooCommerce connector designed for an Agent Studio / Forward-Deployed Engineer workflow.

## 1. Problem

An AI agent needs controlled access to merchant commerce data without being given a raw WooCommerce API surface or unnecessary customer data.

## 2. Solution

MerchantOps exposes exactly six read-only MCP tools:

- `list_orders`
- `get_order`
- `search_orders`
- `list_products`
- `get_product`
- `search_products`

The connector translates agent-facing tool calls into WooCommerce REST API requests, validates inputs, normalizes responses into typed models, masks customer PII, handles pagination/rate limits/retries, and emits structured audit events.

WooCommerce REST API v3 is used under `/wp-json/wc/v3/`. The implementation only uses GET operations for the agent surface.

## 3. Architecture

```text
AI Agent
   │
   │ MCP / Streamable HTTP
   ▼
FastAPI application
   │
   ├── /health
   ├── /ready
   ├── /connect + /callback
   │
   └── /mcp
          │
          ▼
      MCPServer
          │
          ├── Order tools ──► OrderService ──┐
          │                                   │
          └── Product tools ► ProductService ┘
                                              │
                                              ▼
                                      WooCommerceClient
                                              │
                           auth / timeout / retry / rate limit
                           circuit breaker / redirect protection
                                              │
                                              ▼
                                      WooCommerce REST API
```

Cross-cutting controls:

- least-privilege read-only credentials
- Pydantic validation and typed internal contracts
- PII minimization
- structured logs and audit events
- request IDs
- retry/backoff with `Retry-After`
- client-side token-bucket rate limiting
- circuit breaker
- explicit pagination and filter-bound continuation cursors

## 4. Repository structure

```text
src/woo_connector/
├── main.py                    # FastAPI host + MCP mounting/lifespan
├── api/                       # health and merchant connection routes
├── mcp/                       # MCP server + tool definitions
├── services/                  # business/data normalization layer
├── clients/                   # WooCommerce HTTP integration
├── models/                    # Pydantic request/response contracts
├── security/                  # credential and URL/permission controls
├── resilience/                # retry, rate limiting, circuit breaker
├── observability/             # structured logs and audit events
└── config/                    # environment/configuration

tests/                         # unit/service/client/MCP/host tests
scripts/                       # smoke checks and local/demo helpers
docs/                          # architecture, security, tools, demo, limits
evals/                         # agent-tool selection cases
```

## 5. Requirements

- Python 3.10+
- A WooCommerce store for live integration testing
- Node.js 22.19+ only if using the current MCP Inspector CLI/web package

## 6. Installation

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

The development extra includes the MCP CLI needed for the `mcp dev` workflow.

## 7. Configuration

For local development with a real WooCommerce store:

```bash
export WOO_STORE_URL=https://your-store.example.com
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
```

Do not commit real credentials.

For a local fictional/dev WooCommerce instance only:

```bash
export WOO_STORE_URL=http://localhost:8080
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
export ALLOW_INSECURE_LOCAL=1
```

## 8. Run as stdio MCP server

```bash
woo-mcp
```

Or:

```bash
python -m woo_connector.mcp.server
```

The MCP Inspector can launch this directly:

```bash
npx @modelcontextprotocol/inspector --cli python -m woo_connector.mcp.server --method tools/list
```

## 9. Run the combined FastAPI + MCP service

```bash
uvicorn woo_connector.main:app --host 127.0.0.1 --port 8000
```

Endpoints:

```text
GET  http://127.0.0.1:8000/health
GET  http://127.0.0.1:8000/ready
MCP  http://127.0.0.1:8000/mcp
```

Verify the FastAPI host:

```bash
python scripts/verify_fastapi.py
```

Verify the actual MCP transport and six-tool contract:

```bash
python scripts/verify_mcp_http.py
```

To also make a read-only WooCommerce-backed tool call:

```bash
python scripts/verify_mcp_http.py --call-tool
```

## 10. MCP Inspector — HTTP

The current Inspector supports Streamable HTTP. With the FastAPI service running:

```bash
npx @modelcontextprotocol/inspector --cli \
  --transport http \
  --server-url http://127.0.0.1:8000/mcp \
  --method tools/list
```

For a tool call:

```bash
npx @modelcontextprotocol/inspector --cli \
  --transport http \
  --server-url http://127.0.0.1:8000/mcp \
  --method tools/call \
  --tool-name list_products \
  --tool-arg page=1 \
  --tool-arg per_page=5
```

The web Inspector can also be started with:

```bash
npx @modelcontextprotocol/inspector
```

Then connect to `http://127.0.0.1:8000/mcp` using Streamable HTTP.

## 11. Verify against a real WooCommerce store

Use a **read-only WooCommerce REST API key** and run:

```bash
export WOO_STORE_URL=https://your-store.example.com
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
python scripts/verify_woocommerce.py
```

The script performs only GET requests and reports product/order counts returned by the store. It never creates, updates, deletes, or refunds records.

## 12. Local fictional-data demo

If Docker is available, the repository includes a throwaway WordPress + WooCommerce environment:

```bash
docker compose up -d
docker compose logs setup
```

Then load the generated local read-only connector key and seed fictional data:

```bash
set -a
. ./.local/connector.env
set +a
python scripts/seed.py --store http://localhost:8080
```

The seed script refuses non-local URLs. The connector must use `ALLOW_INSECURE_LOCAL=1` only for this local environment.

See [docs/demo.md](docs/demo.md) and [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md).

## 13. Tool contract

| Tool | Purpose | Mutation |
|---|---|---|
| `list_orders` | Paginated order listing/filtering | None |
| `get_order` | Retrieve one order | None |
| `search_orders` | Search/filter orders | None |
| `list_products` | Paginated catalogue listing | None |
| `get_product` | Retrieve one product | None |
| `search_products` | Search catalogue | None |

No customer mutation, order mutation, product mutation, refund, or delete tool is exposed.

## 14. Security model

- WooCommerce credentials are supplied through environment variables or the encrypted demo credential store.
- The connector client exposes GET only.
- Redirects are disabled so credentials are not automatically replayed to another host.
- Store URLs are validated; local HTTP is permitted only with an explicit development flag.
- Agent responses are normalized rather than returning raw WooCommerce JSON.
- Customer email and phone are masked.
- Search terms and credentials are not written to structured logs.
- Audit records contain tool name, request ID, status and optional result count, not tool arguments.

See [docs/security.md](docs/security.md).

## 15. Resilience

Retryable upstream conditions include network errors, HTTP 408/429 and 5xx responses. Backoff uses exponential equal jitter and respects `Retry-After` when safe.

A token bucket reduces request bursts. A circuit breaker fails fast after repeated upstream failures and allows a half-open recovery probe.

The connector does not claim or depend on a universal WooCommerce REST API rate limit; upstream throttling is handled from actual responses such as HTTP 429.

## 16. Pagination

WooCommerce pagination metadata is mapped from `X-WP-Total` and `X-WP-TotalPages`.

The connector does not automatically fetch every page. It returns pagination metadata and an opaque continuation cursor. The cursor is bound to the original filter set so it cannot be reused for a different query.

## 17. Verification status for this submission

Verified end-to-end against a local fictional WooCommerce store:

- Python source compilation: PASS
- Full automated test suite: PASS — `15 passed`
- FastAPI `/health`: PASS
- FastAPI `/ready`: PASS
- FastAPI `/mcp` route: PASS
- MCP Streamable HTTP initialization: PASS
- MCP `tools/list`: PASS
- `list_products`: PASS — 8 products with pagination
- `get_product`: PASS — product retrieval by ID
- `search_products`: PASS — positive and no-match searches
- `list_orders`: PASS — 60 fictional orders with pagination
- `get_order`: PASS — order retrieval by ID
- `search_orders`: PASS — status filtering returned 5 failed orders
- customer PII masking: PASS — email and phone are masked in agent-facing responses
- client-side token-bucket rate limiting: PASS
- HTTP 429 / `Retry-After` handling: PASS
- retry/backoff handling for transient upstream errors: PASS
- circuit-breaker handling: PASS
- read-only MCP tool surface: PASS

The live verification used only a local Dockerized WooCommerce development store containing fictional products and orders. No real merchant credentials or production customer data were used.

The connector exposes six read-only MCP tools:

- `list_orders`
- `get_order`
- `search_orders`
- `list_products`
- `get_product`
- `search_products`

The agent-facing surface does not expose write, refund, delete, or other mutation operations.
## 18. Limitations / production evolution

Current v1 intentionally does not include:

- write/refund/mutation tools
- webhook/event ingestion
- distributed Redis rate limiting
- persistent response caching
- multi-tenant secret management
- egress proxy/DNS-rebinding hardening
- direct joining of WooCommerce orders to Razorpay payment records

A production evolution could add those capabilities behind explicit authorization and audit controls.

See [docs/limitations.md](docs/limitations.md).
