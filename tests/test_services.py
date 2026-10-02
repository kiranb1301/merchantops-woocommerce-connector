import pytest
from woo_connector.models.errors import NotFoundError, ValidationError
from woo_connector.models.orders import OrderSearchRequest
from woo_connector.models.products import ProductSearchRequest
from woo_connector.services.order_service import OrderService
from woo_connector.services.product_service import ProductService

@pytest.fixture
def services(client):
    return OrderService(client), ProductService(client)

async def test_orders_are_typed_and_paginated(services):
    orders,_=services
    out=await orders.list_orders(per_page=20)
    assert len(out.items)==20
    assert out.pagination.total_items==45
    assert out.pagination.has_next is True
    assert out.pagination.next_cursor

async def test_order_pii_is_minimised(services):
    orders,_=services
    out=await orders.get_order(3)
    assert out.customer.email=="a***@example.com"
    assert "SECRET" not in str(out.model_dump())
    assert out.line_items[0].sku=="TSHIRT-M"

async def test_order_validation_and_not_found(services):
    orders,_=services
    with pytest.raises(ValidationError): await orders.get_order(0)
    with pytest.raises(NotFoundError): await orders.get_order(999)

async def test_product_search_and_get(services):
    _,products=services
    out=await products.search_products(ProductSearchRequest(query="Product",search_fields=["name"]))
    assert out.items[0].name=="Product 1"
    assert (await products.get_product(2)).sku=="MUG-01"

async def test_search_orders(services):
    orders,_=services
    out=await orders.search_orders(OrderSearchRequest(query="asha7@"))
    assert [x.id for x in out.items]==[7]
