# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Human confirmation of egress actions requested over MCP.

An MCP client calling an egress tool only gets a preview and a ``request_id``;
the action runs exclusively when the user clicks "Send" in the Laya UI, which
calls ``POST /egress/pending/{request_id}/confirm``. Every route here is static
under ``/egress/pending`` and this router is included before ``egress_api`` so
no ``/egress/{param}`` route can shadow it (G-ENG-08).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from starlette.requests import Request

from laya.api.origin_guard import reject_cross_site
from laya.egress import pending, tool_handlers

log = structlog.get_logger()

router = APIRouter()


def _take_or_raise(request_id: str) -> pending.PendingEgress:
    try:
        return pending.pop_by_request_id(request_id, origin="mcp")
    except pending.PendingLookupError as e:
        if e.reason == "expired":
            raise HTTPException(
                status.HTTP_410_GONE,
                "Confirmation request expired. Ask the MCP client to request the action again.",
            ) from None
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Confirmation request not found or already resolved.",
        ) from None


@router.get("/egress/pending")
async def list_pending_egress() -> dict[str, Any]:
    """Non-expired MCP confirmation requests (sanitized, no tokens)."""
    return {"pending": pending.list_pending(origin="mcp")}


@router.post("/egress/pending/{request_id}/confirm")
async def confirm_pending_egress(request_id: str, request: Request) -> dict[str, Any]:
    """Execute a pending MCP egress request after explicit user confirmation."""
    # A cross-site page must not be able to click "Send" on the user's behalf.
    reject_cross_site(request, log_event="egress_pending_cross_site_blocked")
    entry = _take_or_raise(request_id)
    result = await tool_handlers.execute_pending(entry)
    extra: dict[str, Any] = {}
    if result.get("result_url"):
        extra["result_url"] = result["result_url"]
    if result.get("error"):
        extra["error"] = result["error"]
    await tool_handlers.broadcast_resolved(request_id, result["status"], **extra)
    log.info("egress_mcp_confirmed", request_id=request_id, status=result["status"])
    return {"request_id": request_id, **result}


@router.post("/egress/pending/{request_id}/reject")
async def reject_pending_egress(request_id: str, request: Request) -> dict[str, Any]:
    """Discard a pending MCP egress request without executing it."""
    reject_cross_site(request, log_event="egress_pending_cross_site_blocked")
    entry = _take_or_raise(request_id)
    await tool_handlers.reject_pending(entry)
    await tool_handlers.broadcast_resolved(request_id, "rejected")
    log.info("egress_mcp_rejected", request_id=request_id)
    return {"request_id": request_id, "status": "rejected"}
