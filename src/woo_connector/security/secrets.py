"""Merchant authorisation: encrypted credential store + WooCommerce `wc-auth` connect flow.

WooCommerce has no OAuth2. Its closest equivalent is the `wc-auth/v1/authorize`
endpoint: the merchant approves a *read-only* key in their own wp-admin, and the
store then POSTs the generated key pair to our `callback_url`. We bind that
callback to the merchant who started the flow with a single-use, expiring
`state` token (sent as `user_id`).
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken

from ..models.errors import AuthError, NotConfiguredError, ValidationError
from .validation import validate_merchant_id, validate_store_url

STATE_TTL_S = 600.0


# ------------------------------------------------------------ credential store


@dataclass(frozen=True)
class StoredCredentials:
    merchant_id: str
    store_url: str
    consumer_key: str
    consumer_secret: str

    def __repr__(self) -> str:  # never let secrets reach logs or tracebacks
        return f"StoredCredentials(merchant_id={self.merchant_id!r}, store_url={self.store_url!r}, secrets=***)"


class CredentialStore:
    """Whole-file Fernet encryption. Fine for one process; see NOTES.md for the multi-tenant design."""

    def __init__(self, path: str | Path, enc_key: str | bytes) -> None:
        self.path = Path(path)
        try:
            self._fernet = Fernet(enc_key)
        except (ValueError, TypeError):
            raise NotConfiguredError(
                "CONNECTOR_ENC_KEY is not a valid Fernet key. Generate one with: woo-connector genkey"
            ) from None

    def _read(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self._fernet.decrypt(self.path.read_bytes()))
        except (InvalidToken, ValueError):
            raise NotConfiguredError(
                "Credential store could not be decrypted (wrong CONNECTOR_ENC_KEY or corrupt file)."
            ) from None

    def _write(self, data: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        blob = self._fernet.encrypt(json.dumps(data).encode())
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".creds-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(blob)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)  # atomic: a crash never leaves a half-written store
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def save(self, creds: StoredCredentials) -> None:
        validate_merchant_id(creds.merchant_id)
        data = self._read()
        data[creds.merchant_id] = {
            "store_url": creds.store_url,
            "consumer_key": creds.consumer_key,
            "consumer_secret": creds.consumer_secret,
        }
        self._write(data)

    def load(self, merchant_id: str) -> StoredCredentials | None:
        row = self._read().get(merchant_id)
        if row is None:
            return None
        return StoredCredentials(merchant_id=merchant_id, **row)

    def delete(self, merchant_id: str) -> bool:
        data = self._read()
        if merchant_id not in data:
            return False
        del data[merchant_id]
        self._write(data)
        return True

    def merchants(self) -> list[str]:
        return sorted(self._read())


# ------------------------------------------------------------------ connect flow


def build_authorize_url(
    store_url: str, *, state: str, callback_url: str, return_url: str, app_name: str = "Agent Studio Connector"
) -> str:
    query = urlencode(
        {
            "app_name": app_name,
            "scope": "read",  # least privilege: the connector never needs to write
            "user_id": state,
            "return_url": return_url,
            "callback_url": callback_url,
        }
    )
    return f"{store_url}/wc-auth/v1/authorize?{query}"


@dataclass
class _Pending:
    merchant_id: str
    store_url: str
    expires_at: float


Verifier = Callable[[str, str, str], Awaitable[None]]


class ConnectFlow:
    """Framework-free state machine so it can be unit tested without HTTP."""

    def __init__(
        self,
        store: CredentialStore,
        *,
        public_base_url: str,
        allow_insecure: bool = False,
        verifier: Verifier | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.public_base_url = public_base_url.rstrip("/")
        self.allow_insecure = allow_insecure
        self._verifier = verifier
        self._clock = clock
        self._pending: dict[str, _Pending] = {}

    def start(self, store_url: str, merchant_id: str) -> str:
        merchant_id = validate_merchant_id(merchant_id)
        store_url = validate_store_url(store_url, allow_local=self.allow_insecure)
        self._purge()
        state = secrets.token_urlsafe(32)
        self._pending[state] = _Pending(merchant_id, store_url, self._clock() + STATE_TTL_S)
        return build_authorize_url(
            store_url,
            state=state,
            callback_url=f"{self.public_base_url}/callback",
            return_url=f"{self.public_base_url}/connected",
        )

    async def complete(self, payload: dict) -> StoredCredentials:
        self._purge()
        state = str(payload.get("user_id", ""))
        pending = self._pending.pop(state, None)  # pop = single use, replay-proof
        if pending is None:
            raise AuthError("Unknown or expired connection request. Start the connect flow again.")

        key, secret = payload.get("consumer_key"), payload.get("consumer_secret")
        if not (isinstance(key, str) and isinstance(secret, str) and key.startswith("ck_") and secret.startswith("cs_")):
            raise ValidationError("Callback did not contain a valid WooCommerce key pair.")
        if payload.get("key_permissions") != "read":
            # Refuse (and never store) anything broader than we asked for.
            raise AuthError(
                "The key was issued with more than read access. Revoke it in WooCommerce > Settings > Advanced > REST API and reconnect."
            )

        if self._verifier is not None:
            await self._verifier(pending.store_url, key, secret)

        creds = StoredCredentials(pending.merchant_id, pending.store_url, key, secret)
        self.store.save(creds)
        return creds

    def _purge(self) -> None:
        now = self._clock()
        for s in [s for s, p in self._pending.items() if p.expires_at <= now]:
            del self._pending[s]
