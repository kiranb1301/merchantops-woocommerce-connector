from __future__ import annotations
from pydantic import BaseModel, Field
from .common import Pagination


class ProductSummary(BaseModel):
    id: int
    name: str | None = None
    sku: str | None = None
    status: str | None = None
    price: str | None = None
    stock_status: str | None = None
    stock_quantity: int | float | None = None


class Product(ProductSummary):
    type: str | None = None
    regular_price: str | None = None
    sale_price: str | None = None
    manage_stock: bool | None = None
    backorders: str | None = None
    categories: list[str] = Field(default_factory=list)
    date_modified: str | None = None


class ProductSearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=100)
    search_fields: list[str] = Field(default_factory=lambda: ["name", "sku"])
    page: int = Field(default=1, ge=1, le=1000)
    per_page: int = Field(default=20, ge=1, le=100)


class ProductListResponse(BaseModel):
    items: list[ProductSummary]
    pagination: Pagination
