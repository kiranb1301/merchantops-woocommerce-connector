# Demo / Verification Runbook

## A. Static and unit verification

```bash
pip install -e ".[dev]"
pytest
```

Expected in a fully provisioned environment:

```text
15 tests passed
```

The MCP-specific tests require the MCP v2 dependency. In an offline environment where `mcp` cannot be installed, those tests are skipped rather than being falsely reported as passed.

## B. FastAPI host

Start:

```bash
uvicorn woo_connector.main:app --host 127.0.0.1 --port 8000
```

Verify:

```bash
python scripts/verify_fastapi.py
```

Expected:

```text
FastAPI /health: PASS
FastAPI /ready: PASS
FastAPI /mcp route: PASS
```

## C. MCP HTTP transport

```bash
python scripts/verify_mcp_http.py
```

Expected:

```text
MCP /mcp connection: PASS (...)
Tools: get_order, get_product, list_orders, list_products, search_orders, search_products
```

The optional `--call-tool` flag performs a real read-only `list_products` call through MCP and therefore requires valid WooCommerce credentials.

## D. MCP Inspector

Current MCP Inspector supports Streamable HTTP:

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

## E. Real WooCommerce verification

Use a read-only API key:

```bash
export WOO_STORE_URL=https://your-store.example.com
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
python scripts/verify_woocommerce.py
```

The verification performs GET requests only.

## F. Local fictional store

For a local WooCommerce-compatible development environment only:

```bash
export WOO_STORE_URL=http://localhost:8080
export WOO_CONSUMER_KEY=ck_...
export WOO_CONSUMER_SECRET=cs_...
export ALLOW_INSECURE_LOCAL=1
python scripts/seed.py --store http://localhost:8080
```

The seed script refuses non-local URLs.

## G. Docker connector image

Build and run the connector itself:

```bash
docker build -t merchantops-woocommerce .
docker run --rm -p 8000:8000 \
  -e WOO_STORE_URL=https://your-store.example.com \
  -e WOO_CONSUMER_KEY=ck_... \
  -e WOO_CONSUMER_SECRET=cs_... \
  merchantops-woocommerce
```

Use a read-only key. Do not place production secrets in the image or Dockerfile.
