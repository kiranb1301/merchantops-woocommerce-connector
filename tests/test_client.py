import httpx, pytest
from woo_connector.models.errors import RateLimitedError, UpstreamError
from woo_connector.resilience.circuit_breaker import CircuitBreaker

def resp(status,headers=None): return httpx.Response(status,json={"message":"x"},headers=headers or {})

async def test_client_reads_pagination(client):
    async with client as c:
        out=await c.get("orders",{"page":1,"per_page":10})
    assert out.total==45 and out.total_pages==5 and len(out.data)==10

async def test_429_retry_after(client,store,sleeper):
    store.faults=[resp(429,{"Retry-After":"2"})]
    async with client as c: await c.get("orders")
    assert len(store.requests)==2 and sleeper.calls[-1]>=2

async def test_5xx_retry(client,store):
    store.faults=[resp(503),resp(502)]
    async with client as c: out=await c.get("orders")
    assert len(store.requests)==3 and out.total==45

async def test_no_write_methods(client):
    assert not any(hasattr(client,m) for m in ("post","put","patch","delete"))

def test_rejects_insecure():
    from woo_connector.clients.woocommerce_client import WooClient
    with pytest.raises(Exception): WooClient("http://shop.example.test","ck","cs")
