"""Operator CLI: genkey, connect (run the OAuth-style flow), status, disconnect."""

from __future__ import annotations

import argparse
import os
import sys

from cryptography.fernet import Fernet

from .security.secrets import ConnectFlow
from .config.settings import store_from_env

from .models.errors import ConnectorError
from .observability.logging import configure_logging


def _cmd_genkey(_: argparse.Namespace) -> int:
    print(Fernet.generate_key().decode())
    return 0


def _cmd_connect(args: argparse.Namespace) -> int:
    import uvicorn
    os.environ["PUBLIC_BASE_URL"] = args.public_url
    from .main import app
    print(f"Run the connector app at {args.public_url}; merchant connect endpoint is /connect.", file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0

def _cmd_status(_: argparse.Namespace) -> int:
    merchants = store_from_env().merchants()
    print("\n".join(merchants) if merchants else "(no connected merchants)")
    return 0


def _cmd_disconnect(args: argparse.Namespace) -> int:
    removed = store_from_env().delete(args.merchant_id)
    print("removed" if removed else "not found")
    if removed:
        print(
            "Also revoke the key in WooCommerce > Settings > Advanced > REST API: "
            "deleting it here does not invalidate it on the store.",
            file=sys.stderr,
        )
    return 0 if removed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="woo-connector")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("genkey", help="print a new CONNECTOR_ENC_KEY").set_defaults(fn=_cmd_genkey)

    p = sub.add_parser("connect", help="run the merchant connect flow")
    p.add_argument("--public-url", required=True, help="externally reachable https base URL of this app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    p.set_defaults(fn=_cmd_connect)

    sub.add_parser("status", help="list connected merchants").set_defaults(fn=_cmd_status)

    p = sub.add_parser("disconnect", help="delete a merchant's stored credentials")
    p.add_argument("merchant_id")
    p.set_defaults(fn=_cmd_disconnect)

    args = parser.parse_args(argv)
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    try:
        return args.fn(args)
    except ConnectorError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
