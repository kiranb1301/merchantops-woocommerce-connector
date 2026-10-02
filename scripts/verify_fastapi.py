"""Verify the combined FastAPI host and the mounted MCP endpoint.

Run the application first:
  uvicorn woo_connector.main:app --host 127.0.0.1 --port 8000

For the protocol-level MCP check use verify_mcp_http.py.
"""

from __future__ import annotations

import argparse

import httpx


def main(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert health.json() == {"status": "ok"}

        ready = client.get("/ready")
        ready.raise_for_status()
        assert ready.json() == {"status": "ready"}

        response = client.get("/mcp")
        # Streamable HTTP endpoints generally do not make GET a normal JSON API;
        # a non-404 response proves the route is mounted. Protocol behavior is
        # verified by verify_mcp_http.py / MCP Inspector.
        assert response.status_code != 404, response.text[:500]

    print("FastAPI /health: PASS")
    print("FastAPI /ready: PASS")
    print("FastAPI /mcp route: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    main(args.base_url)
