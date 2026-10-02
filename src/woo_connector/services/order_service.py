from __future__ import annotations

import base64, hashlib, json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from ..clients.woocommerce_client import ApiResponse, WooClient
from ..models.common import Pagination
from ..models.errors import NotFoundError, ValidationError
from ..models.orders import CustomerSummary, Order, OrderItem, OrderListResponse, OrderSearchRequest, OrderSummary

ORDER_STATUSES = ("pending","processing","on-hold","completed","cancelled","refunded","failed")
MAX_LIMIT = 100


def _iso(value: str, field: str) -> str:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValidationError(f"{field} must be an ISO 8601 date or datetime.") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _cursor(filters: dict[str, Any], page: int) -> str:
    digest = hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return base64.urlsafe_b64encode(json.dumps({"page": page, "filters": digest}).encode()).decode().rstrip("=")


def _page(cursor: str | None, filters: dict[str, Any]) -> int:
    if not cursor: return 1
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        expected = hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()[:12]
        
        if raw["filters"] != expected or int(raw["page"]) < 1:
            raise ValueError
        return int(raw["page"])
    
    except Exception:
        raise ValidationError("cursor is invalid or does not match the current filters.") from None


def _customer(order: dict[str, Any]) -> CustomerSummary:
    billing = order.get("billing") or {}
    first, last = (billing.get("first_name") or "").strip(), (billing.get("last_name") or "").strip()
    name = f"{first} {last[:1]}.".strip() if last else first or None
    email = billing.get("email")
    if email and "@" in email:
        local, _, domain = email.partition("@")
        email = f"{local[:1]}***@{domain}"
    else:
        email = None
    digits = "".join(c for c in str(billing.get("phone") or "") if c.isdigit())
    phone = ("*" * (len(digits)-4) + digits[-4:]) if len(digits) > 4 else ("****" if digits else None)
    
    return CustomerSummary(id=order.get("customer_id") or None, name=name, email=email, phone=phone,
                           city=billing.get("city") or None, state=billing.get("state") or None,
                           country=billing.get("country") or None)


def _summary(raw: dict[str, Any]) -> OrderSummary:
    return OrderSummary(
        id=raw.get("id"), number=raw.get("number"), status=raw.get("status"),
        currency=raw.get("currency"), total=raw.get("total"),
        date_created=raw.get("date_created_gmt") or raw.get("date_created"),
        date_modified=raw.get("date_modified_gmt") or raw.get("date_modified"),
        payment_method=raw.get("payment_method"), customer=_customer(raw),
    )


def _detail(raw: dict[str, Any]) -> Order:
    return Order(
        **_summary(raw).model_dump(),
        transaction_id=raw.get("transaction_id") or None,
        payment_method_title=raw.get("payment_method_title"),
        date_paid=raw.get("date_paid_gmt") or raw.get("date_paid"),
        total_tax=raw.get("total_tax"), shipping_total=raw.get("shipping_total"),
        discount_total=raw.get("discount_total"), customer_note=raw.get("customer_note") or None,
        line_items=[
            OrderItem(product_id=x.get("product_id"), sku=x.get("sku") or None, name=x.get("name"),
                      quantity=x.get("quantity"), total=x.get("total"))
            for x in raw.get("line_items") or []
        ],
    )


def _list_response(resp: ApiResponse, items: list[OrderSummary], page: int, per_page: int, filters: dict[str, Any]) -> OrderListResponse:
    total_pages = resp.total_pages
    has_next = total_pages is not None and page < total_pages
    return OrderListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            per_page=per_page,
            total_items=resp.total,
            total_pages=total_pages,
            has_next=has_next,
            next_cursor=_cursor(filters, page + 1) if has_next else None,
        ),
    )


class OrderService:
    def __init__(self, client: WooClient): 
        self.client = client

    async def list_orders(self, *, page: int=1, per_page: int=20, status: str="any",
                          after: str|None=None, before: str|None=None, cursor: str|None=None) -> OrderListResponse:
        
        if status != "any" and status not in ORDER_STATUSES:
            raise ValidationError(f"status must be 'any' or one of: {', '.join(ORDER_STATUSES)}")
        if not 1 <= per_page <= MAX_LIMIT: 
            raise ValidationError("per_page must be 1-100")
        if not 1 <= page <= 1000: 
            raise ValidationError("page must be between 1 and 1000")
        
        filters={"status":status,"after":after,"before":before,"per_page":per_page}
        
        page=_page(cursor,filters) if cursor else page
        params={"page":page,"per_page":per_page,"orderby":"date","order":"desc"}
        if status != "any": 
            params["status"]=status
        if after: 
            params["after"]=_iso(after,"after")
        if before: 
            params["before"]=_iso(before,"before")
            
        resp=await self.client.get("orders",params)
        
        return _list_response(resp,[_summary(x) for x in resp.data],page,per_page,filters)

    async def get_order(self, order_id: int) -> Order:
        
        if not isinstance(order_id,int) or isinstance(order_id,bool) or order_id<1:
            raise ValidationError("order_id must be a positive integer")
        
        return _detail((await self.client.get(f"orders/{order_id}")).data)

    async def search_orders(self, req: OrderSearchRequest, cursor: str|None=None) -> OrderListResponse:
        if req.query is not None and not req.query.strip(): 
            raise ValidationError("query must not be empty")
        filters=req.model_dump()
        
        page=_page(cursor,filters) if cursor else req.page
        params={"page":page,"per_page":req.per_page,"search":req.query} if req.query else {"page":page,"per_page":req.per_page}
        if req.status and req.status != "any": 
            params["status"]=req.status
        if req.customer_id: 
            params["customer"]=req.customer_id
        if req.after: 
            params["after"]=_iso(req.after,"after")
        if req.before: 
            params["before"]=_iso(req.before,"before")
            
        resp=await self.client.get("orders",params)
        return _list_response(resp,[_summary(x) for x in resp.data],page,req.per_page,filters)

    async def summary(self, *, after: str|None=None, before: str|None=None, max_pages: int=10) -> dict[str, Any]:
        if not 1<=max_pages<=20: 
            raise ValidationError("max_pages must be 1-20")
        params={"status":"any","per_page":100}
        
        if after: 
            params["after"]=_iso(after,"after")
        if before:
            params["before"]=_iso(before,"before")
            
        buckets:dict[str,dict[str,dict[str,Any]]]={}; page=counted=0; truncated=False
        while True:
            page += 1
            resp=await self.client.get("orders",{**params,"page":page})
            for raw in resp.data:
                cur=raw.get("currency") or "UNKNOWN"; st=raw.get("status") or "unknown"
                cell=buckets.setdefault(cur,{}).setdefault(st,{"count":0,"total":Decimal("0")})
                cell["count"]+=1; counted+=1
                
                try: 
                    cell["total"] += Decimal(str(raw.get("total","0")))
                except InvalidOperation: 
                    pass
                
            if not resp.total_pages or page>=resp.total_pages: 
                break
            if page>=max_pages: truncated=True; 
            break
        
        return {"period":{"after":after,"before":before},"orders_counted":counted,
                "by_currency":{c:{s:{"count":v["count"],"total":str(v["total"])} for s,v in b.items()} for c,b in buckets.items()},
                "truncated":truncated}
