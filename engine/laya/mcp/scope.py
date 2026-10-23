# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""MCP tool-scope filtering.

The Settings → MCP UI exposes three toggles (read / write / egress). A tool is
callable over MCP only if its category is enabled. Tool→category mapping is
derived live from `laya.llm.tools.definitions` so new tools added there are
picked up automatically with no constant updates here.

Chat-only tools (`chat_only_tool_names()`, e.g. `confirm_egress`) are never
callable over MCP, whatever the toggles: egress requested over MCP is confirmed
by the user in the Laya UI, never by the MCP client itself.
"""

from __future__ import annotations

from typing import TypedDict

from laya.llm.tools.definitions import (
    chat_only_tool_names,
    egress_tool_names,
    mcp_egress_tool_names,
    read_tool_names,
    write_tool_names,
)


class ToolScopes(TypedDict, total=False):
    read: bool
    write: bool
    egress: bool


def enabled_tool_names(scopes: ToolScopes) -> set[str]:
    """Return the set of tool names callable over MCP for the given scope toggles."""
    out: set[str] = set()
    if scopes.get("read"):
        out |= read_tool_names()
    if scopes.get("write"):
        out |= write_tool_names()
    if scopes.get("egress"):
        out |= mcp_egress_tool_names()
    return out - chat_only_tool_names()


def scope_of(tool_name: str) -> str | None:
    """Return 'read' | 'write' | 'egress' for a tool, or None if unknown."""
    if tool_name in read_tool_names():
        return "read"
    if tool_name in write_tool_names():
        return "write"
    if tool_name in egress_tool_names():
        return "egress"
    return None
