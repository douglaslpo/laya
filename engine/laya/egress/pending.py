# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""In-memory store of previewed egress actions awaiting human confirmation.

Two flows share this store:

- ``origin="chat"``: the in-app chat receives a signed ``execute_token`` and
  confirms it via the ``confirm_egress`` tool after asking the user.
- ``origin="mcp"``: an external MCP client never receives a token. The entry
  is only resolvable by the user through ``POST /egress/pending/{request_id}``
  in the Laya UI (see ``laya.api.egress_pending_api``).

Tokens are ``egr_<nonce>.<sig>`` where ``sig = HMAC-SHA256(secret, nonce|origin)``
with a per-process CSPRNG secret. The signature is verified in constant time
BEFORE the store is consulted, so a malformed or forged token never reaches
the lookup and the store cannot be probed. Entries are single use and expire
after ``TOKEN_TTL_SECONDS``. Nothing here is persisted: an engine restart
drops every pending action, which is the safe failure mode.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from laya.egress.models import EgressPreview, EgressRequest
from laya.llm.tools.origin import ToolOrigin

TOKEN_TTL_SECONDS = 300
TOKEN_PREFIX = "egr_"
REQUEST_ID_PREFIX = "egreq_"
# 32 hex chars = 128 bits of HMAC-SHA256 output.
_SIG_HEX_LEN = 32

# Regenerated on every engine start; tokens intentionally do not survive restarts.
_SECRET = secrets.token_bytes(32)


class PendingLookupError(Exception):
    """Raised when a token / request_id cannot be resolved.

    ``reason`` is one of ``"invalid_token"``, ``"not_found"``, ``"expired"``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class PendingEgress:
    request_id: str
    nonce: str
    token: str
    origin: ToolOrigin
    request: EgressRequest
    preview: EgressPreview
    created_at: float
    expires_at: float


# Keyed by request_id; _by_nonce maps the token nonce back to its request_id.
_store: dict[str, PendingEgress] = {}
_by_nonce: dict[str, str] = {}


def _now() -> float:
    return time.time()


def _sign(nonce: str, origin: str) -> str:
    msg = f"{nonce}|{origin}".encode()
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:_SIG_HEX_LEN]


def _verify_token(token: str, origin: str) -> str | None:
    """Return the nonce when ``token`` carries a valid signature for ``origin``."""
    if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
        return None
    nonce, sep, sig = token[len(TOKEN_PREFIX):].partition(".")
    if not sep or not nonce or len(sig) != _SIG_HEX_LEN:
        return None
    if not hmac.compare_digest(sig, _sign(nonce, origin)):
        return None
    return nonce


def _remove(entry: PendingEgress) -> None:
    _store.pop(entry.request_id, None)
    _by_nonce.pop(entry.nonce, None)


def cleanup_expired() -> None:
    """Drop every expired entry."""
    now = _now()
    for entry in [e for e in _store.values() if now > e.expires_at]:
        _remove(entry)


def create(
    request: EgressRequest, preview: EgressPreview, origin: ToolOrigin
) -> PendingEgress:
    """Register a previewed request and return the new pending entry."""
    cleanup_expired()
    nonce = secrets.token_urlsafe(16)
    now = _now()
    entry = PendingEgress(
        request_id=f"{REQUEST_ID_PREFIX}{secrets.token_urlsafe(12)}",
        nonce=nonce,
        token=f"{TOKEN_PREFIX}{nonce}.{_sign(nonce, origin)}",
        origin=origin,
        request=request,
        preview=preview,
        created_at=now,
        expires_at=now + TOKEN_TTL_SECONDS,
    )
    _store[entry.request_id] = entry
    _by_nonce[nonce] = entry.request_id
    return entry


def _take(entry: PendingEgress | None, origin: ToolOrigin) -> PendingEgress:
    # An entry of another origin is reported as not found and left intact, so
    # e.g. a chat token can never resolve (or burn) an MCP request.
    if entry is None or entry.origin != origin:
        raise PendingLookupError("not_found")
    # Pop before any await in the caller: the event loop cannot interleave
    # another confirm between this check and the removal, which is what makes
    # confirmation single use.
    _remove(entry)
    if _now() > entry.expires_at:
        raise PendingLookupError("expired")
    return entry


def consume_token(token: str, origin: ToolOrigin) -> PendingEgress:
    """Resolve and remove the entry referenced by a signed execute token."""
    nonce = _verify_token(token, origin)
    if nonce is None:
        raise PendingLookupError("invalid_token")
    request_id = _by_nonce.get(nonce)
    return _take(_store.get(request_id) if request_id else None, origin)


def pop_by_request_id(request_id: str, origin: ToolOrigin = "mcp") -> PendingEgress:
    """Resolve and remove a pending entry by its opaque request_id."""
    return _take(_store.get(request_id), origin)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_public(entry: PendingEgress) -> dict[str, Any]:
    """Sanitized view for REST listings and WS broadcasts — never the token."""
    preview = entry.preview
    return {
        "request_id": entry.request_id,
        "origin": entry.origin,
        "platform": entry.request.platform,
        "action_type": entry.request.action_type,
        "space_id": entry.request.space_id,
        "connection_id": entry.request.connection_id,
        "preview": {
            "summary": preview.summary,
            "details": preview.details,
            "warnings": list(preview.warnings),
            "estimated_impact": preview.estimated_impact,
        },
        "created_at": _iso(entry.created_at),
        "expires_at": _iso(entry.expires_at),
    }


def list_pending(origin: ToolOrigin = "mcp") -> list[dict[str, Any]]:
    """Non-expired entries of ``origin``, soonest-expiring first, sanitized."""
    cleanup_expired()
    entries = sorted(
        (e for e in _store.values() if e.origin == origin),
        key=lambda e: e.expires_at,
    )
    return [to_public(e) for e in entries]


def reset() -> None:
    """Drop all entries (tests)."""
    _store.clear()
    _by_nonce.clear()
