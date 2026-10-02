from woo_connector.models.orders import OrderSearchRequest
from woo_connector.models.products import ProductSearchRequest

def test_request_models_validate():
    assert OrderSearchRequest(per_page=100).per_page==100
    assert ProductSearchRequest(search_fields=["name","sku"]).search_fields==["name","sku"]
