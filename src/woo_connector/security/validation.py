"""Input hardening: store URL validation (basic SSRF guard)."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from ..models.errors import ValidationError

_MERCHANT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_merchant_id(value: str) -> str:
    if not _MERCHANT_ID_RE.match(value or ""):
        raise ValidationError("merchant_id must be 1-64 chars of letters, digits, '-' or '_'")
    return value


def validate_store_url(url: str, *, allow_local: bool = False) -> str:
    """Return a normalised store base URL or raise ValidationError.

    Rules: https only (http allowed solely for local dev), no embedded
    credentials, and no obviously internal hosts. NOTE: this checks the
    literal host only; it does not defend against DNS rebinding (see NOTES.md).
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("store URL must start with https://")
    if parsed.scheme == "http" and not allow_local:
        raise ValidationError("store URL must use https://")
    host = parsed.hostname
    if not host:
        raise ValidationError("store URL has no host")
    if parsed.username or parsed.password:
        raise ValidationError("store URL must not contain credentials")

    if not allow_local:
        lowered = host.lower()
        if lowered == "localhost" or lowered.endswith((".local", ".internal", ".localhost")):
            raise ValidationError("store URL points at an internal host")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None and (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValidationError("store URL points at a private or reserved address")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
