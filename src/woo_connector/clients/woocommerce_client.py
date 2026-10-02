"""Read-only WooCommerce REST client with retries, rate limiting and a circuit breaker."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from .. import __version__
from ..models.errors import (
    AuthError,
    ConnectorError,
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)
from ..observability.logging import current_request_id
from ..resilience.rate_limiter import TokenBucket
from ..resilience.circuit_breaker import CircuitBreaker
from ..resilience.retry import backoff_delay, parse_retry_after
from ..security.validation import validate_store_url

log = logging.getLogger("woo_connector.client")

RETRYABLE_5XX = {500, 502, 503, 504}


@dataclass
class ApiResponse:
    data: Any
    total: int | None = None
    total_pages: int | None = None


def _int_header(headers: httpx.Headers, name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, ValueError):
        return None


class WooClient:
    """GET-only client. There is deliberately no method that can write."""

    def __init__(
        self,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        *,
        limiter: TokenBucket | None = None,
        breaker: CircuitBreaker | None = None,
        max_retries: int = 4,
        max_elapsed_s: float = 45.0,
        max_retry_after_s: float = 30.0,
        timeout_s: float = 15.0,
        allow_insecure: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.base = validate_store_url(store_url, allow_local=allow_insecure) + "/wp-json/wc/v3"
        self.max_retries = max_retries
        self.max_elapsed_s = max_elapsed_s
        self.max_retry_after_s = max_retry_after_s
        self._limiter = limiter or TokenBucket(4.0, 8)
        self._breaker = breaker or CircuitBreaker()
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        # follow_redirects=False so credentials can never be replayed to another host.
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth(consumer_key, consumer_secret),
            timeout=timeout_s,
            transport=transport,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": f"woo-mcp-connector/{__version__}",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "WooClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> ApiResponse:
        url = f"{self.base}/{path.lstrip('/')}"
        started = self._clock()
        attempt = 0

        while True:
            self._breaker.before_call()
            await self._limiter.acquire()

            error: ConnectorError
            server_delay: float | None = None
            status: int | str = "network_error"

            try:
                resp = await self._http.get(url, params=params)
            except httpx.HTTPError as exc:
                self._breaker.record_failure()
                error = UpstreamError(f"Network error talking to the store ({type(exc).__name__})")
                
            else:
                status = resp.status_code
                if 200 <= status < 300:
                    self._breaker.record_success()
                    self._log(path, params, status, attempt, started)
                    return self._parse(resp)
                
                if status == 429:
                    # Throttled, not broken: do not count against the breaker.
                    server_delay = parse_retry_after(resp.headers.get("Retry-After"))
                    error = RateLimitedError(
                        "The store is rate limiting requests.",
                        retry_after_s=server_delay,
                        status=429,
                    )
                    
                elif status in RETRYABLE_5XX:
                    self._breaker.record_failure()
                    server_delay = parse_retry_after(resp.headers.get("Retry-After"))
                    error = UpstreamError(f"The store returned HTTP {status}.", status=status)
                    
                else:
                    self._breaker.record_success()  # store is healthy; our request was wrong
                    self._log(path, params, status, attempt, started)
                    raise self._terminal_error(resp)

            self._log(path, params, status, attempt, started)

            if attempt >= self.max_retries:
                raise error
            
            if server_delay is not None and server_delay > self.max_retry_after_s:
                raise error  # asked to wait longer than we are willing to; tell the agent
            
            delay = backoff_delay(attempt, rng=self._rng)
            
            if server_delay is not None:
                delay = max(delay, server_delay)
            if (self._clock() - started) + delay > self.max_elapsed_s:
                raise error
            await self._sleep(delay)
            attempt += 1

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _parse(resp: httpx.Response) -> ApiResponse:
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("The store returned a non-JSON response.") from exc
        return ApiResponse(
            data=data,
            total=_int_header(resp.headers, "X-WP-Total"),
            total_pages=_int_header(resp.headers, "X-WP-TotalPages"),
        )

    @staticmethod
    def _terminal_error(resp: httpx.Response) -> ConnectorError:
        status = resp.status_code
        if status in (401, 403):
            return AuthError(
                "The store rejected the credentials or the key lacks permission.",
                status=status,
            )
        if status == 404:
            return NotFoundError("The requested resource was not found.", status=404)
        
        if 300 <= status < 400:
            return UpstreamError(
                "The store redirected the request. Use the canonical https:// store URL.",
                status=status,
            )
            
        detail = ""
        
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = str(body.get("message", ""))[:200]
        except ValueError:
            pass
        
        return UpstreamError(
            f"The store rejected the request (HTTP {status}). {detail}".strip(),
            status=status,
        )

    def _log(self, path: str, params: dict | None, status: int | str, attempt: int, started: float) -> None:
        # Log param *names* only: search terms can contain customer PII.
        log.info(
            "woo_request",
            extra={
                "path": path,
                "param_keys": sorted(params) if params else [],
                "status": status,
                "attempt": attempt,
                "elapsed_ms": int((self._clock() - started) * 1000),
                "req": current_request_id(),
            },
        )
