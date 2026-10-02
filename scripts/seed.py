"""Create FICTIONAL products and orders in a LOCAL dev store (needs the read_write seed key).

    set -a; . ./.local/seed.env; set +a
    python scripts/seed.py --store http://localhost:8080
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx

FIRST = ["Asha", "Rohan", "Meera", "Vikram", "Isha", "Karan", "Neha", "Arjun"]
LAST = ["Kulkarni", "Patil", "Deshmukh", "Joshi", "Sharma", "Iyer"]
STATUSES = ["completed"] * 5 + ["processing"] * 4 + ["pending"] * 2 + ["failed"] * 2 + ["refunded", "cancelled", "on-hold"]
PRODUCTS = [
    ("Cotton T-Shirt M", "TSHIRT-M", "499", 40), ("Cotton T-Shirt L", "TSHIRT-L", "499", 3),
    ("Steel Mug", "MUG-01", "299", 0), ("Notebook A5", "NOTE-A5", "149", 120),
    ("Canvas Tote", "TOTE-01", "349", 25), ("Desk Lamp", "LAMP-01", "1299", 6),
    ("Ceramic Planter", "PLANT-01", "599", 14), ("E-book: Pune Walks", "EBOOK-1", "199", None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="http://localhost:8080")
    ap.add_argument("--orders", type=int, default=60)
    args = ap.parse_args()
    if not args.store.startswith(("http://localhost", "http://127.0.0.1")):
        sys.exit("Refusing to seed anything but a local dev store.")
    key, secret = os.environ.get("WOO_CONSUMER_KEY"), os.environ.get("WOO_CONSUMER_SECRET")
    if not (key and secret):
        sys.exit("Load .local/seed.env first (WOO_CONSUMER_KEY / WOO_CONSUMER_SECRET).")

    rng = random.Random(42)  # deterministic: same data every run
    with httpx.Client(base_url=f"{args.store}/wp-json/wc/v3", auth=(key, secret), timeout=60) as http:
        created = []
        for name, sku, price, qty in PRODUCTS:
            body = {"name": name, "sku": sku, "regular_price": price, "type": "simple"}
            if qty is None:
                body["manage_stock"] = False
            else:
                body.update(manage_stock=True, stock_quantity=qty)
            r = http.post("products", json=body)
            if r.status_code == 400 and "sku" in r.text:  # already seeded
                r = http.get("products", params={"sku": sku}); created.append(r.json()[0]["id"]); continue
            r.raise_for_status()
            created.append(r.json()["id"])

        now = datetime.now(timezone.utc)
        for i in range(args.orders):
            first, last = rng.choice(FIRST), rng.choice(LAST)
            when = now - timedelta(days=rng.randint(0, 29), hours=rng.randint(0, 23))
            body = {
                "status": rng.choice(STATUSES),
                "date_created_gmt": when.strftime("%Y-%m-%dT%H:%M:%S"),
                "payment_method": "razorpay", "payment_method_title": "Razorpay (test)",
                "transaction_id": f"pay_TEST{i:04d}",
                "billing": {"first_name": first, "last_name": last, "email": f"{first.lower()}.{last.lower()}{i}@example.com",
                            "phone": f"+91 90000 {rng.randint(10000, 99999)}", "city": "Pune", "state": "MH", "country": "IN"},
                "line_items": [{"product_id": rng.choice(created), "quantity": rng.randint(1, 3)} for _ in range(rng.randint(1, 3))],
            }
            http.post("orders", json=body).raise_for_status()
    print(f"Seeded {len(PRODUCTS)} products and {args.orders} orders (all fictional).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
