from __future__ import annotations
import math, httpx, pytest
from typing import Callable
from woo_connector.clients.woocommerce_client import WooClient
from woo_connector.resilience.rate_limiter import TokenBucket
from woo_connector.resilience.circuit_breaker import CircuitBreaker

BASE="https://shop.example.test"

def order(i:int)->dict:
    return {"id":i,"number":str(i),"status":"processing","currency":"INR","total":"100.00",
            "date_created_gmt":"2026-09-01T10:00:00","payment_method":"razorpay","transaction_id":f"pay_{i}",
            "customer_id":i,"billing":{"first_name":"Asha","last_name":"Kulkarni","email":f"asha{i}@example.com",
            "phone":"+91 98765 43210","city":"Pune","state":"MH","country":"IN","address_1":"SECRET"},
            "line_items":[{"product_id":7,"sku":"TSHIRT-M","name":"T-Shirt","quantity":2,"total":"100.00"}]}

def product(i:int,sku:str)->dict:
    return {"id":i,"name":f"Product {i}","sku":sku,"status":"publish","type":"simple","price":"499",
            "regular_price":"499","sale_price":"","stock_status":"instock","manage_stock":True,
            "stock_quantity":10,"backorders":"no","categories":[{"name":"Apparel"}]}

class FakeStore:
    def __init__(self):
        self.orders=[order(i) for i in range(1,46)]
        self.products=[product(1,"TSHIRT-M"),product(2,"MUG-01")]
        self.requests=[]; self.faults=[]
    def _page(self,items,req):
        q=req.url.params; per=int(q.get("per_page",20)); page=int(q.get("page",1))
        chunk=items[(page-1)*per:page*per]
        return httpx.Response(200,json=chunk,headers={"X-WP-Total":str(len(items)),
            "X-WP-TotalPages":str(max(1,math.ceil(len(items)/per)))})
    def handler(self,req):
        self.requests.append(req)
        if self.faults:
            x=self.faults.pop(0)
            if isinstance(x,Exception): raise x
            return x
        path=req.url.path.removeprefix("/wp-json/wc/v3/"); q=req.url.params
        if path=="orders":
            items=self.orders
            if q.get("status"): items=[x for x in items if x["status"]==q["status"]]
            if q.get("search"): items=[x for x in items if q["search"].lower() in x["number"] or q["search"].lower() in x["billing"]["email"]]
            return self._page(items,req)
        if path.startswith("orders/"):
            oid=int(path.split("/")[1])
            for x in self.orders:
                if x["id"]==oid: return httpx.Response(200,json=x)
            return httpx.Response(404,json={"message":"not found"})
        if path=="products": return self._page(self.products,req)
        if path.startswith("products/"):
            pid=int(path.split("/")[1])
            for x in self.products:
                if x["id"]==pid: return httpx.Response(200,json=x)
            return httpx.Response(404,json={})
        return httpx.Response(404,json={})

class Sleeper:
    def __init__(self): self.calls=[]; self.now=0.0
    async def __call__(self,secs): self.calls.append(secs); self.now+=secs
    def clock(self): return self.now

@pytest.fixture
def store(): return FakeStore()
@pytest.fixture
def sleeper(): return Sleeper()
@pytest.fixture
def client(store,sleeper):
    return WooClient(BASE,"ck_test","cs_test",transport=httpx.MockTransport(store.handler),
                     limiter=TokenBucket(1000,1000,clock=sleeper.clock,sleep=sleeper),
                     breaker=CircuitBreaker(clock=sleeper.clock),sleep=sleeper,clock=sleeper.clock,rng=lambda:.5)
