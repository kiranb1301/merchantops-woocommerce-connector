from __future__ import annotations
from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    total_items: int | None = Field(default=None, ge=0)
    total_pages: int | None = Field(default=None, ge=0)
    has_next: bool
    next_cursor: str | None = None
