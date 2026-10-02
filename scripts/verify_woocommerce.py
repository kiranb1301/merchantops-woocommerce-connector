"""Verify the connector against a real WooCommerce store using read-only credentials.

Set WOO_STORE_URL, WOO_CONSUMER_KEY and WOO_CONSUMER_SECRET before running.
The script performs only GET requests and never writes merchant data.
"""

from __future__ import annotations

import asyncio
import os

from woo_connector.clients.woocommerce_client import WooClient
from woo_connector.services.order_service import OrderService
from woo_connector.services.product_service import ProductService


async def main() -> None:
    required = ["WOO_STORE_URL", "WOO_CONSUMER_KEY", "WOO_CONSUMER_SECRET"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    async with WooClient(
        os.environ["WOO_STORE_URL"],
        os.environ["WOO_CONSUMER_KEY"],
        os.environ["WOO_CONSUMER_SECRET"],
    ) as client:
        orders = OrderService(client)
        products = ProductService(client)

        product_page = await products.list_products(page=1, per_page=3)
        order_page = await orders.list_orders(page=1, per_page=3)

        print("WooCommerce connectivity: PASS")
        print(f"Products returned: {len(product_page.items)}")
        print(f"Orders returned: {len(order_page.items)}")
        print(f"Product total reported: {product_page.pagination.total_items}")
        print(f"Order total reported: {order_page.pagination.total_items}")
        print("Verification is read-only; no merchant records were changed.")


if __name__ == "__main__":
    asyncio.run(main())
