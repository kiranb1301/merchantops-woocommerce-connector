# MerchantOps Final Verification Report

## Submission scope

This repository implements the Razorpay-style private merchant connector assignment using WooCommerce, Python, FastAPI and MCP.

## Architecture checks

- [x] FastAPI is the host application.
- [x] MCP Streamable HTTP is mounted under `/mcp`.
- [x] MCP session manager is entered through the host application's lifespan.
- [x] Six read-only tools are exposed.
- [x] MCP tools call services rather than talking directly to HTTP.
- [x] Services normalize third-party responses into typed Pydantic models.
- [x] WooCommerce access is isolated in a GET-only client.
- [x] Security/resilience/observability are separated into dedicated modules.

## Tool contract

```text
list_orders
get_order
search_orders
list_products
get_product
search_products
```

No write/refund/delete/update operation is exposed.

## Automated verification completed in the packaging environment

```text
Python compileall                 PASS
Client tests                     PASS
Service tests                    PASS
Model tests                      PASS
Circuit breaker tests            PASS
Full local pytest                 12 passed, 2 skipped
```

The two skipped tests are the MCP/HTTP-host tests because the packaging environment does not have the MCP v2 package installed and has no external package-network access.

The repository contains 15 tests total. With `mcp[cli]` installed, the two MCP-dependent test modules are expected to execute as part of the full suite.

## MCP v2 verification procedure

After installing dependencies:

```bash
pip install -e ".[dev]"
pytest
```

Start the combined application:

```bash
uvicorn woo_connector.main:app --host 127.0.0.1 --port 8000
```

Verify the actual Streamable HTTP transport:

```bash
python scripts/verify_mcp_http.py
```

Use the current MCP Inspector:

```bash
npx @modelcontextprotocol/inspector --cli \
  --transport http \
  --server-url http://127.0.0.1:8000/mcp \
  --method tools/list
```

## Live WooCommerce verification procedure

Provide a read-only WooCommerce API key:

```bash
export WOO_STORE_URL=https://your-store.example.com
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
python scripts/verify_woocommerce.py
```

This uses GET requests only.

## Local fictional WooCommerce verification

If Docker is available:

```bash
docker compose up -d
docker compose logs setup
```

The setup script installs WooCommerce into a throwaway local WordPress instance and creates separate read-only and read-write keys. Only the read-only key belongs in the connector configuration. The seed key exists only for fictional local data creation.

Then run:

```bash
set -a
. ./.local/connector.env
set +a
python scripts/seed.py --store http://localhost:8080
```

Use the connector with `ALLOW_INSECURE_LOCAL=1` only for this local environment.

## Important honest limitation

The authoring environment used to prepare this archive does not have Docker and cannot reach external package registries. Therefore no claim is made that this exact environment completed a live WooCommerce or MCP Inspector network exchange. The repository contains reproducible commands for those final external checks.
