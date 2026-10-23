# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Authenticated engine <-> n8n link (SEC-03).

Both directions share one CSPRNG secret kept in the OS keychain
(``security/keychain.py``) and mirrored into a singleton n8n
``httpHeaderAuth`` credential named ``Laya Engine Link``:

* n8n -> engine: ingestion workflows and the error handler send
  ``X-Laya-Link-Token`` on ``POST /events`` / ``POST /ingestion-errors``;
  :func:`require_n8n_link` enforces it.
* engine -> n8n: executor webhooks use ``headerAuth`` with the same credential;
  :func:`link_headers` supplies the header for ``N8nBackend``.

The secret is deliberately NOT handed to n8n through its process env:
workflow expressions can read ``$env`` (SEC-07).
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import HTTPException, Request

from laya.security.keychain import get_n8n_link_secret

log = structlog.get_logger()

LINK_HEADER = "X-Laya-Link-Token"
LINK_CRED_NAME = "Laya Engine Link"
LINK_CRED_TYPE = "httpHeaderAuth"
# Template placeholder id. Intentionally NOT equal to the credential type:
# _merge_credentials treats id == type as a placeholder and backfills it from
# the old workflow by node type, which for httpRequest nodes could pull a
# platform credential into the engine-link node. Clone/propagation paths always
# replace this id with the real credential id via apply_link_credential().
LINK_CRED_PLACEHOLDER_ID = "__LAYA_LINK__"

# Upper bound on how long header-less requests are tolerated for installs that
# predate the link (RF-S3-08), even if clone propagation never completes.
TRANSITION_MAX = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Transition state (settings.security.n8n_link — never holds the secret)
# ---------------------------------------------------------------------------


def get_link_state() -> dict:
    from laya.config import DEFAULT_SETTINGS, load_settings

    default = DEFAULT_SETTINGS["security"]["n8n_link"]
    state = (load_settings().get("security") or {}).get("n8n_link") or {}
    return {**default, **state}


def _save_link_state(**changes) -> None:
    from laya.config import load_settings, save_settings

    settings = load_settings()
    security = settings.setdefault("security", {})
    previous = security.get("n8n_link") or {}
    link = {**previous, **changes}
    # Enforcement is monotonic: once true it never flips back, otherwise a
    # stale write could reopen the header-less window (RF-S3-08).
    if previous.get("enforced"):
        link["enforced"] = True
    security["n8n_link"] = link
    save_settings(settings)


def is_enforced() -> bool:
    return bool(get_link_state().get("enforced"))


def mark_enforced(reason: str) -> None:
    """Persist enforced=true. Idempotent."""
    if is_enforced():
        return
    _save_link_state(enforced=True)
    log.info("n8n_link_enforced", reason=reason)


def start_transition_if_needed() -> None:
    """Start the header-less tolerance window if it isn't running yet."""
    state = get_link_state()
    if state.get("enforced") or state.get("transition_started_at"):
        return
    _save_link_state(transition_started_at=datetime.now(timezone.utc).isoformat())
    log.info("n8n_link_transition_started")


def _parse_ts(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _transition_allows_missing_header() -> bool:
    state = get_link_state()
    if state.get("enforced"):
        return False
    started = _parse_ts(state.get("transition_started_at"))
    if started is None:
        # The window must be bounded even if provisioning never ran; start it
        # at the first header-less request.
        start_transition_if_needed()
        return True
    if datetime.now(timezone.utc) - started >= TRANSITION_MAX:
        mark_enforced(reason="transition_expired")
        return False
    return True


# ---------------------------------------------------------------------------
# FastAPI dependency for the n8n -> engine routes
# ---------------------------------------------------------------------------


async def require_n8n_link(request: Request) -> None:
    """Authenticate an n8n -> engine request by its X-Laya-Link-Token header.

    * secret unavailable (keychain failure / never provisioned) -> 503,
      fail-closed: nothing is accepted without authentication material.
    * header present -> constant-time compare; mismatch is always 401,
      even during the transition window.
    * header absent -> 401 once enforced; tolerated (and logged) only inside
      the RF-S3-08 transition window.

    The presented value is never logged.
    """
    secret = get_n8n_link_secret()
    if not secret:
        log.error("n8n_link_secret_unavailable", path=request.url.path)
        raise HTTPException(status_code=503, detail="engine link unavailable")

    presented = request.headers.get(LINK_HEADER)
    if presented is not None:
        if hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8")):
            return
        log.warning("n8n_link_rejected", reason="invalid_token", path=request.url.path)
        raise HTTPException(status_code=401, detail="unauthorized")

    if _transition_allows_missing_header():
        log.info("n8n_link_transition_accept", path=request.url.path)
        return

    log.warning("n8n_link_rejected", reason="missing_token", path=request.url.path)
    raise HTTPException(status_code=401, detail="unauthorized")


def link_headers() -> dict[str, str]:
    """Headers the engine sends to n8n executor webhooks ({} if no secret)."""
    secret = get_n8n_link_secret()
    return {LINK_HEADER: secret} if secret else {}


# ---------------------------------------------------------------------------
# Workflow credential injection helpers
# ---------------------------------------------------------------------------


def is_link_node(node: dict) -> bool:
    """True for nodes bound to the engine-link credential in the template.

    Identified by credentials.httpHeaderAuth.name == LINK_CRED_NAME. Platform
    credential injection must skip these: bitbucket_server's platform
    credential is also httpHeaderAuth, so matching by type alone would
    overwrite the engine link with the platform token (and vice versa).
    """
    ref = (node.get("credentials") or {}).get(LINK_CRED_TYPE)
    return isinstance(ref, dict) and ref.get("name") == LINK_CRED_NAME


def apply_link_credential(nodes: list[dict], credential_id: str) -> int:
    """Point every link node at the real n8n credential id. Returns count."""
    count = 0
    for node in nodes:
        if is_link_node(node):
            node["credentials"][LINK_CRED_TYPE] = {
                "id": credential_id,
                "name": LINK_CRED_NAME,
            }
            count += 1
    return count
