from __future__ import annotations
import os
from ..models.errors import NotConfiguredError
from ..security.secrets import CredentialStore
from ..clients.woocommerce_client import WooClient
from ..resilience.rate_limiter import TokenBucket


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _num(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        raise NotConfiguredError(f"{name} must be a number") from None


def store_from_env() -> CredentialStore:
    key = os.environ.get("CONNECTOR_ENC_KEY")
    if not key:
        raise NotConfiguredError("CONNECTOR_ENC_KEY is required to use the credential store.")
    return CredentialStore(os.environ.get("CREDENTIAL_STORE_PATH", "./data/credentials.json"), key)


def build_client_from_env() -> WooClient:
    allow_insecure = _flag("ALLOW_INSECURE_LOCAL")
    url, ck, cs = (os.environ.get(k) for k in ("WOO_STORE_URL", "WOO_CONSUMER_KEY", "WOO_CONSUMER_SECRET"))
    if not (url and ck and cs):
        merchant_id = os.environ.get("MERCHANT_ID")
        if not merchant_id:
            raise NotConfiguredError(
                "Set WOO_STORE_URL/WOO_CONSUMER_KEY/WOO_CONSUMER_SECRET or MERCHANT_ID + CONNECTOR_ENC_KEY."
            )
        creds = store_from_env().load(merchant_id)
        if creds is None:
            raise NotConfiguredError(f"Merchant '{merchant_id}' has not connected a store yet.")
        url, ck, cs = creds.store_url, creds.consumer_key, creds.consumer_secret
    try:
        limiter = TokenBucket(_num("RATE_LIMIT_PER_S", 4.0), _num("RATE_LIMIT_BURST", 8.0))
    except ValueError as exc:
        raise NotConfiguredError(str(exc)) from None
    return WooClient(url, ck, cs, limiter=limiter, max_retries=int(_num("MAX_RETRIES", 4)),
                     allow_insecure=allow_insecure)
