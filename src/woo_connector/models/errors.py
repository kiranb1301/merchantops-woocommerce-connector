from __future__ import annotations

from typing import Any


class ConnectorError(Exception):
    code = "connector_error"

    def __init__(self, message: str, *, retry_after_s: float | None = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.retry_after_s = retry_after_s
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.retry_after_s is not None:
            out["retry_after_s"] = round(self.retry_after_s, 1)
        if self.status is not None:
            out["upstream_status"] = self.status
        return out


class NotConfiguredError(ConnectorError): 
    code = "not_configured"
    
class ValidationError(ConnectorError): 
    code = "invalid_input"
    
class AuthError(ConnectorError): 
    code = "auth_failed"
    
class NotFoundError(ConnectorError): 
    code = "not_found"
    
class RateLimitedError(ConnectorError): 
    code = "rate_limited"
    
class UpstreamError(ConnectorError): 
    code = "upstream_error"
    
class CircuitOpenError(ConnectorError): 
    code = "circuit_open"
