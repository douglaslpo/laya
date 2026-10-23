# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Execution handlers for egress tools.

These handlers are called when the in-app chat LLM or an external MCP client
invokes an egress tool. They follow a preview -> confirm -> execute pattern:

- origin ``chat``: the preview carries a signed ``execute_token`` that the chat
  passes to ``confirm_egress`` after asking the user.
- origin ``mcp``: the preview becomes a pending request that only the user can
  confirm or reject in the Laya UI (``/egress/pending/*``); no token is ever
  returned to the MCP client.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

import laya.egress as egress
from laya.egress import pending
from laya.egress.models import EgressRequest, EgressResult
from laya.llm.tools.origin import current_origin


log = structlog.get_logger()

WS_CONFIRMATION_REQUEST = "egress_confirmation_request"
WS_CONFIRMATION_RESOLVED = "egress_confirmation_resolved"


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------


async def handle_egress_tool(
    tool_name: str, arguments: dict, space_id: str | None
) -> str:
    """Universal handler for egress action tools (send_email, comment_on_ticket, etc.).

    Builds an EgressRequest and calls preview(). For the in-app chat, returns the
    preview with an execute_token so the LLM can ask the user and confirm. For
    MCP (or any untagged caller — fail-closed), registers a pending request and
    asks the UI to confirm it; the MCP client gets no way to execute it.
    """
    request = _build_request(tool_name, arguments, space_id)

    # Chat has no originating event to derive the account from, so resolve a
    # connection for the platform and set it explicitly. Without this the executor
    # silently used the oldest connection (the wrong account with 2+ accounts) AND
    # Jira never received its base URL, falling back to the literal
    # your-domain.atlassian.net (review §2 egress — P4-22). The n8n backend derives
    # jira_base_url from the connection creds once connection_id is set.
    if not request.connection_id:
        conn_id = await _resolve_connection_id(request.platform, space_id)
        if conn_id:
            request.connection_id = conn_id

    # Get preview
    preview = await egress.preview(request)

    origin = current_origin()
    entry = pending.create(request, preview, origin)

    if origin == "chat":
        return json.dumps({
            "status": "preview",
            "summary": preview.summary,
            "details": preview.details,
            "warnings": preview.warnings,
            "estimated_impact": preview.estimated_impact,
            "execute_token": entry.token,
            "instruction": (
                "Show this preview to the user and ask for confirmation. "
                "If they confirm, call confirm_egress with the execute_token."
            ),
        })

    # MCP: the confirmation must come from the human in the Laya UI. Returning a
    # token here would let the MCP client confirm its own egress (SEC-01).
    await _broadcast(WS_CONFIRMATION_REQUEST, pending.to_public(entry))
    log.info(
        "egress_mcp_confirmation_requested",
        request_id=entry.request_id,
        platform=request.platform,
        action_type=request.action_type,
    )
    return json.dumps({
        "status": "awaiting_user_confirmation",
        "request_id": entry.request_id,
        "summary": preview.summary,
        "warnings": preview.warnings,
        "instruction": (
            "The action was NOT executed. The user must review and confirm it in "
            f"the Laya app within {pending.TOKEN_TTL_SECONDS // 60} minutes; "
            "it cannot be confirmed over MCP."
        ),
    })


async def handle_open_compose(
    arguments: dict, space_id: str | None
) -> str:
    """Open the compose editor in the UI via WebSocket broadcast."""
    from laya.api.websocket import manager

    await manager.broadcast({
        "type": "open_compose",
        "payload": {
            "platform": arguments["platform"],
            "action_type": arguments["action_type"],
            "prefill": arguments.get("prefill", {}),
            "source_card_id": arguments.get("source_card_id"),
        },
    })

    platform = arguments["platform"]
    action_type = arguments["action_type"]
    return json.dumps({
        "status": "compose_opened",
        "message": (
            f"Opened the {action_type} editor for {platform}. "
            "The user can edit and send from the UI."
        ),
    })


async def handle_confirm_egress(
    arguments: dict, space_id: str | None
) -> str:
    """Execute a previously previewed egress action after user confirmation.

    Only the in-app chat may confirm. The MCP server already hides and denies
    this tool, but the check is repeated here so no future dispatch path (or an
    untagged caller, which defaults to "mcp") can confirm egress on its own.
    """
    if current_origin() != "chat":
        return json.dumps({
            "status": "error",
            "error": (
                "confirm_egress is only available to the in-app Laya chat. "
                "Actions requested over MCP must be confirmed by the user in the Laya UI."
            ),
        })

    token = arguments.get("execute_token", "")
    try:
        entry = pending.consume_token(token, origin="chat")
    except pending.PendingLookupError as e:
        # Never echo or log the token value itself.
        if e.reason == "expired":
            message = "Token has expired. Ask the user to try the action again."
        elif e.reason == "invalid_token":
            message = "Invalid execute token. Ask the user to try the action again."
        else:
            message = "Token expired or already used. Ask the user to try the action again."
        return json.dumps({"status": "error", "error": message})

    return json.dumps(await execute_pending(entry))


async def execute_pending(entry: pending.PendingEgress) -> dict[str, Any]:
    """Execute a confirmed pending request and audit it with its origin.

    Shared by the chat ``confirm_egress`` tool and the UI confirmation endpoint.
    The caller must already have removed ``entry`` from the pending store.
    """
    request = entry.request
    try:
        result = await egress.execute(request)
    except Exception as e:
        # The entry was already taken from the store, so an unhandled raise would
        # leave the send unaudited and the UI card stuck. The outcome on the
        # platform is unknown, hence retryable=False (same rule as timeouts).
        log.error("egress_pending_execute_error", request_id=entry.request_id,
                  error=type(e).__name__)
        result = EgressResult(
            success=False, error=f"Execution error: {type(e).__name__}", retryable=False,
        )

    # Audit the outbound action. This is the real send/post moment for chat- and
    # MCP-driven egress; the executor.py path audits UI-triggered actions the same
    # way. metadata.source marks which path requested it ("chat" | "mcp").
    # Local import avoids an import cycle with the LLM client.
    from laya.llm.client import log_to_audit

    await log_to_audit(
        event_id=None, card_id=None, step="execute",
        model="n/a", input_tokens=0, output_tokens=0, latency_ms=0,
        success=result.success,
        error=result.error,
        metadata={
            "action_type": request.action_type,
            "target_platform": request.platform,
            "result_url": result.result_url,
            "source": entry.origin,
            "request_id": entry.request_id,
        },
    )

    if result.success:
        response: dict[str, Any] = {
            "status": "done",
            "message": "Action executed successfully.",
        }
        if result.result_url:
            response["result_url"] = result.result_url
        if result.result_data:
            response["result_data"] = result.result_data
        return response
    return {
        "status": "failed",
        "error": result.error or "Action failed",
        "retryable": result.retryable,
    }


async def reject_pending(entry: pending.PendingEgress) -> None:
    """Audit a pending request the user rejected (nothing is executed)."""
    from laya.llm.client import log_to_audit

    request = entry.request
    await log_to_audit(
        event_id=None, card_id=None, step="egress_rejected",
        model="n/a", input_tokens=0, output_tokens=0, latency_ms=0,
        success=False,
        error="rejected by user",
        metadata={
            "action_type": request.action_type,
            "target_platform": request.platform,
            "source": entry.origin,
            "request_id": entry.request_id,
        },
    )


async def broadcast_resolved(request_id: str, status: str, **extra: Any) -> None:
    """Tell the UI a pending confirmation left the queue."""
    await _broadcast(
        WS_CONFIRMATION_RESOLVED, {"request_id": request_id, "status": status, **extra}
    )


async def _broadcast(msg_type: str, payload: dict[str, Any]) -> None:
    from laya.api.websocket import manager

    # A broadcast failure must not lose the pending request: the UI also reloads
    # GET /egress/pending on (re)connect, so log and continue.
    try:
        await manager.broadcast({"type": msg_type, "payload": payload})
    except Exception as e:
        log.warning("egress_confirmation_broadcast_failed", type=msg_type, error=str(e))


# ---------------------------------------------------------------------------
# Request builders (tool arguments -> EgressRequest)
# ---------------------------------------------------------------------------


def _build_request(
    tool_name: str, arguments: dict, space_id: str | None
) -> EgressRequest:
    """Map a tool name + arguments to an EgressRequest."""

    if tool_name == "send_email":
        return _build_email_request(arguments, space_id)
    elif tool_name == "comment_on_ticket":
        return _build_comment_request(arguments, space_id)
    elif tool_name == "transition_ticket":
        return _build_transition_request(arguments, space_id)
    elif tool_name == "create_ticket":
        return _build_create_ticket_request(arguments, space_id)
    elif tool_name == "pr_action":
        return _build_pr_request(arguments, space_id)
    elif tool_name == "send_slack_message":
        return _build_slack_request(arguments, space_id)
    else:
        raise ValueError(f"Unknown egress tool: {tool_name}")


async def _resolve_connection_id(platform: str, space_id: str | None) -> str | None:
    """Pick a connected connection for a chat-driven egress action.

    Prefers one scoped to this space, else any connected connection for the
    platform (review §2 egress — P4-22)."""
    from laya.db.sqlite import get_db
    try:
        db = await get_db()
        rows = await db.execute_fetchall(
            "SELECT connection_id, space_id FROM egress_connections "
            "WHERE platform = ? AND status = 'connected' ORDER BY created_at",
            (platform,),
        )
    except Exception:
        return None
    if not rows:
        return None
    if space_id:
        for r in rows:
            if r["space_id"] == space_id:
                return r["connection_id"]
    return rows[0]["connection_id"]


def _build_email_request(args: dict, space_id: str | None) -> EgressRequest:
    platform = args.get("platform", "gmail")
    payload: dict[str, Any] = {
        "to": args["to"],
        "subject": args["subject"],
        "body": args["body"],
    }
    if args.get("thread_id"):
        payload["thread_id"] = args["thread_id"]
    if args.get("cc"):
        payload["cc"] = args["cc"]
    if args.get("bcc"):
        payload["bcc"] = args["bcc"]

    return EgressRequest(
        platform=platform,
        action_type="send_email",
        payload=payload,
        space_id=space_id,
    )


def _build_comment_request(args: dict, space_id: str | None) -> EgressRequest:
    platform = args["platform"]
    ticket_id = args["ticket_id"]
    comment = args["comment"]

    if platform == "jira":
        payload: dict[str, Any] = {"issue_key": ticket_id, "comment": comment}
    elif platform == "github":
        # Parse "owner/repo#123" format
        owner, repo, number = _parse_github_ref(ticket_id)
        payload = {"owner": owner, "repo": repo, "issue_number": number, "comment": comment}
    elif platform == "linear":
        payload = {"issue_id": ticket_id, "body": comment}
    else:
        payload = {"ticket_id": ticket_id, "comment": comment}

    return EgressRequest(
        platform=platform,
        action_type="comment",
        payload=payload,
        space_id=space_id,
    )


def _build_transition_request(args: dict, space_id: str | None) -> EgressRequest:
    platform = args["platform"]
    payload: dict[str, Any] = {
        "issue_key": args["ticket_id"],
        "target_status": args["target_status"],
    }
    if args.get("comment"):
        payload["comment"] = args["comment"]

    action_type = "transition" if platform == "jira" else "update_status"
    if platform == "linear":
        payload = {"issue_id": args["ticket_id"], "state_id": args["target_status"]}

    return EgressRequest(
        platform=platform,
        action_type=action_type,
        payload=payload,
        space_id=space_id,
    )


def _build_create_ticket_request(args: dict, space_id: str | None) -> EgressRequest:
    platform = args["platform"]

    if platform == "jira":
        payload: dict[str, Any] = {
            "project": args["project"],
            "summary": args["title"],
        }
        if args.get("description"):
            payload["description"] = args["description"]
        if args.get("type"):
            payload["type"] = args["type"]
        if args.get("priority"):
            payload["priority"] = args["priority"]
        if args.get("assignee"):
            payload["assignee"] = args["assignee"]
    elif platform == "github":
        owner, repo = args["project"].split("/", 1) if "/" in args["project"] else ("", args["project"])
        payload = {"owner": owner, "repo": repo, "title": args["title"]}
        if args.get("description"):
            payload["body"] = args["description"]
        if args.get("labels"):
            payload["labels"] = args["labels"]
        if args.get("assignee"):
            payload["assignees"] = args["assignee"]
    elif platform == "linear":
        payload = {"team_id": args["project"], "title": args["title"]}
        if args.get("description"):
            payload["description"] = args["description"]
        if args.get("priority"):
            payload["priority"] = args["priority"]
        if args.get("assignee"):
            payload["assignee_id"] = args["assignee"]
    else:
        payload = dict(args)

    return EgressRequest(
        platform=platform,
        action_type="create_issue",
        payload=payload,
        space_id=space_id,
    )


def _build_pr_request(args: dict, space_id: str | None) -> EgressRequest:
    platform = args["platform"]
    pr_id = args["pr_id"]
    action = args["action"]

    if platform == "github":
        owner, repo, number = _parse_github_ref(pr_id)
        payload: dict[str, Any] = {"owner": owner, "repo": repo, "pr_number": number}
        if args.get("comment"):
            payload["comment"] = args["comment"]
        if action == "merge":
            payload["merge_method"] = args.get("merge_strategy", "squash")

        # Map action names to egress action_types
        action_type_map = {
            "approve": "approve_pr",
            "request_changes": "request_changes",
            "comment": "comment",
            "merge": "merge_pr",
        }
        action_type = action_type_map.get(action, action)

    elif platform in ("bitbucket", "bitbucket_server"):
        parts = pr_id.split("/")
        if len(parts) >= 3:
            workspace, repo, pr_num = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            workspace, repo = parts[0], parts[1]
            pr_num = ""
        else:
            workspace, repo, pr_num = "", "", pr_id

        payload = {"workspace": workspace, "repo": repo, "pr_id": pr_num}
        if args.get("comment"):
            payload["comment"] = args["comment"]
        if action == "merge":
            payload["merge_strategy"] = args.get("merge_strategy", "squash")

        action_type_map = {
            "approve": "approve_pr",
            "decline": "decline_pr",
            "comment": "comment_pr",
            "merge": "merge_pr",
        }
        action_type = action_type_map.get(action, action)
    else:
        payload = dict(args)
        action_type = action

    return EgressRequest(
        platform=platform,
        action_type=action_type,
        payload=payload,
        space_id=space_id,
    )


def _build_slack_request(args: dict, space_id: str | None) -> EgressRequest:
    payload: dict[str, Any] = {
        "channel": args["channel"],
        "message": args["message"],
    }

    action_type = "send_message"
    if args.get("thread_ts"):
        payload["thread_ts"] = args["thread_ts"]
        action_type = "reply_thread"

    return EgressRequest(
        platform="slack",
        action_type=action_type,
        payload=payload,
        space_id=space_id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_github_ref(ref: str) -> tuple[str, str, int]:
    """Parse 'owner/repo#123' into (owner, repo, number)."""
    if "#" in ref:
        repo_part, num_str = ref.rsplit("#", 1)
        parts = repo_part.split("/")
        owner = parts[0] if len(parts) >= 2 else ""
        repo = parts[1] if len(parts) >= 2 else parts[0]
        try:
            number = int(num_str)
        except ValueError:
            number = 0
    else:
        # Try to extract just a number
        parts = ref.split("/")
        owner = parts[0] if len(parts) >= 3 else ""
        repo = parts[1] if len(parts) >= 3 else ""
        try:
            number = int(parts[-1])
        except ValueError:
            number = 0

    return owner, repo, number
