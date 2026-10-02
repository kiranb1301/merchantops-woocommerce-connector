from __future__ import annotations
import logging
from typing import Any

log = logging.getLogger("woo_connector.audit")

def audit_tool_call(*, request_id: str, tool: str, status: str, result_count: int | None = None) -> None:
    # Never include arguments: search terms and customer data can be sensitive.
    extra: dict[str, Any] = {"event": "tool_invocation", "request_id": request_id, "tool": tool, "status": status}
    if result_count is not None:
        extra["result_count"] = result_count
    log.info("tool_invocation", extra=extra)
