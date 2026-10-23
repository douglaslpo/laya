# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Cross-site (CSRF) guard for state-changing loopback endpoints."""

from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from starlette.requests import Request

log = structlog.get_logger()

# Origins the in-app UI / bundled webview legitimately calls from. A browser
# cannot forge the Origin header, and non-browser callers (n8n, curl, the ASGI
# test client) omit it — so an Origin that is present but not in this set is a
# cross-site (CSRF) attempt against a state-changing endpoint (review §6).
ALLOWED_ORIGINS = frozenset({
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
})


def reject_cross_site(request: Request, log_event: str = "cross_site_blocked") -> None:
    """Raise 403 when the request carries an Origin outside ALLOWED_ORIGINS."""
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        log.warning(log_event, origin=origin, path=str(request.url.path))
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-site origin not allowed")
