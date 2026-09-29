# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Per-call origin of a tool invocation (in-app chat vs. external MCP client).

Egress tools behave differently depending on who asked: the in-app chat may
confirm its own previews (the user is looking at the conversation), but an MCP
client must never be able to confirm egress by itself — its requests become
pending confirmations that only a human resolves in the Laya UI.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

ToolOrigin = Literal["chat", "mcp"]

tool_call_origin: contextvars.ContextVar[ToolOrigin | None] = contextvars.ContextVar(
    "laya_tool_call_origin", default=None
)


def current_origin() -> ToolOrigin:
    """Return the origin of the current tool call.

    Fail-closed: an unset origin is treated as ``"mcp"`` (the least trusted
    caller). A new code path that forgets to tag its calls then gets the
    pending-confirmation flow instead of silently gaining the chat's ability
    to confirm egress without the user seeing a confirmation dialog.
    """
    origin = tool_call_origin.get()
    return "chat" if origin == "chat" else "mcp"


@contextmanager
def tool_origin(origin: ToolOrigin) -> Iterator[None]:
    """Tag every tool call inside the block with ``origin`` (set + reset)."""
    token = tool_call_origin.set(origin)
    try:
        yield
    finally:
        tool_call_origin.reset(token)
