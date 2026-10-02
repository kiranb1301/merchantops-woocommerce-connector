from __future__ import annotations
from typing import Any
from ..clients.woocommerce_client import ApiResponse, WooClient
from ..models.common import Pagination
from ..models.errors import NotFoundError, ValidationError
from ..models.products import Product, ProductListResponse, ProductSearchRequest, ProductSummary
from .order_service import _cursor, _page

STOCK_STATUSES=("instock","outofstock","onbackorder")
MAX_LIMIT=100


def _summary(raw:dict[str,Any])->ProductSummary:
    return ProductSummary(id=raw.get("id"),name=raw.get("name"),sku=raw.get("sku") or None,status=raw.get("status"),
                           price=raw.get("price"),stock_status=raw.get("stock_status"),
                           stock_quantity=raw.get("stock_quantity"))


def _detail(raw:dict[str,Any])->Product:
    return Product(**_summary(raw).model_dump(),type=raw.get("type"),regular_price=raw.get("regular_price"),
                    sale_price=raw.get("sale_price") or None,manage_stock=raw.get("manage_stock"),
                    backorders=raw.get("backorders"),categories=[x.get("name") for x in raw.get("categories") or []],
                    date_modified=raw.get("date_modified_gmt") or raw.get("date_modified"))


def _response(resp:ApiResponse,items:list[ProductSummary],page:int,per_page:int,filters:dict[str,Any])->ProductListResponse:
    has_next=resp.total_pages is not None and page<resp.total_pages
    return ProductListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            per_page=per_page,
            total_items=resp.total,
            total_pages=resp.total_pages,
            has_next=has_next,
            next_cursor=_cursor(filters, page + 1) if has_next else None,
        ),
    )


class ProductService:
    def __init__(self,client:WooClient): self.client=client

    async def list_products(self,*,page:int=1,per_page:int=20,status:str|None=None,
                            cursor:str|None=None)->ProductListResponse:
        if not 1<=per_page<=MAX_LIMIT: 
            raise ValidationError("per_page must be 1-100")
        
        filters={"status":status,"per_page":per_page}; page=_page(cursor,filters) if cursor else page
        
        params={"page":page,"per_page":per_page}
        if status: 
            params["status"]=status
        resp=await self.client.get("products",params)
        return _response(resp,[_summary(x) for x in resp.data],page,per_page,filters)

    async def get_product(self,product_id:int)->Product:
        if not isinstance(product_id,int) or isinstance(product_id,bool) or product_id<1:
            raise ValidationError("product_id must be a positive integer")
        
        return _detail((await self.client.get(f"products/{product_id}")).data)

    async def search_products(self,req:ProductSearchRequest,cursor:str|None=None)->ProductListResponse:
        allowed={"name","sku","global_unique_id","description","short_description"}
        if any(f not in allowed for f in req.search_fields): 
            raise ValidationError(f"search_fields must be from: {sorted(allowed)}")
        
        filters=req.model_dump(); page=_page(cursor,filters) if cursor else req.page
        
        params={"page":page,"per_page":req.per_page}
        if req.query: 
            params["search"]=req.query
        allowed={"name","sku","global_unique_id","description","short_description"}
        fields=[f for f in req.search_fields if f in allowed]
        
        if fields: 
            params["search_fields"]=",".join(fields)
        resp=await self.client.get("products",params)
        
        return _response(resp,[_summary(x) for x in resp.data],page,req.per_page,filters)
