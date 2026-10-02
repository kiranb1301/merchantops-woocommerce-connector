from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from .common import Pagination


class CustomerSummary(BaseModel):
    id: int | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class OrderItem(BaseModel):
    product_id: int | None = None
    sku: str | None = None
    name: str | None = None
    quantity: int | None = None
    total: str | None = None


class OrderSummary(BaseModel):
    id: int
    number: str | None = None
    status: str | None = None
    currency: str | None = None
    total: str | None = None
    date_created: str | None = None
    date_modified: str | None = None
    payment_method: str | None = None
    customer: CustomerSummary


class Order(OrderSummary):
    transaction_id: str | None = None
    payment_method_title: str | None = None
    date_paid: str | None = None
    total_tax: str | None = None
    shipping_total: str | None = None
    discount_total: str | None = None
    customer_note: str | None = None
    line_items: list[OrderItem] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    items: list[OrderSummary]
    pagination: Pagination


class OrderSearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=100)
    status: str | None = None
    customer_id: int | None = Field(default=None, ge=1)
    after: str | None = None
    before: str | None = None
    page: int = Field(default=1, ge=1, le=1000)
    per_page: int = Field(default=20, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value is not None and value not in {"any", "pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"}:
            raise ValueError("unsupported WooCommerce order status")
        
        return value
