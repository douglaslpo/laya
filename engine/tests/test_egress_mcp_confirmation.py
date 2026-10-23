# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""SEC-01: egress requested over MCP needs a human confirmation in the Laya UI.

Covers CA-01..CA-06 and CR-01..CR-06 of
harness-sdd/changes/imp-local-security-hardening/specs/sec-01-egress-mcp-confirmation.md.
"""

import hmac
import json
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mcp import types

from laya.egress import pending, tool_handlers
from laya.egress.models import EgressPreview, EgressRequest, EgressResult
from laya.llm.tools.executor import execute_tool
from laya.llm.tools.origin import current_origin, tool_origin
from laya.mcp import http_server
from laya.mcp.scope import enabled_tool_names

EMAIL_ARGS = {"to": "alice@example.com", "subject": "Hi", "body": "Hello"}
ALL_SCOPES = {"read": True, "write": True, "egress": True}


def _preview(request: EgressRequest) -> EgressPreview:
    return EgressPreview(
        platform=request.platform,
        action_type=request.action_type,
        summary="Send email to alice@example.com",
        details={"to": "alice@example.com"},
        warnings=["External recipient"],
        estimated_impact="medium",
    )


@pytest.fixture(autouse=True)
def _clean_store():
    pending.reset()
    yield
    pending.reset()


@pytest.fixture
def egress_mocks(monkeypatch):
    """Mock egress.preview / egress.execute / WS broadcast."""
    preview = AsyncMock(side_effect=_preview)
    execute = AsyncMock(return_value=EgressResult(success=True, result_url="https://mail/1"))
    broadcast = AsyncMock()
    monkeypatch.setattr("laya.egress.preview", preview)
    monkeypatch.setattr("laya.egress.execute", execute)
    monkeypatch.setattr("laya.api.websocket.manager.broadcast", broadcast)
    return {"preview": preview, "execute": execute, "broadcast": broadcast}


@pytest.fixture
def mcp_server(monkeypatch):
    def _with_scopes(scopes):
        monkeypatch.setattr(http_server, "_current_scopes", lambda: scopes)
        return http_server.build_mcp_server()

    return _with_scopes


async def _mcp_call(server, name: str, arguments: dict) -> types.CallToolResult:
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name=name, arguments=arguments)
    )
    return (await handler(req)).root


async def _mcp_list(server) -> list[str]:
    handler = server.request_handlers[types.ListToolsRequest]
    result = (await handler(types.ListToolsRequest(method="tools/list"))).root
    return [t.name for t in result.tools]


async def _audit_rows(db, step):
    rows = await db.execute_fetchall("SELECT * FROM audit_log WHERE step = ?", (step,))
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata"]) if d.get("metadata") else {}
        out.append(d)
    return out


def _mcp_entry() -> pending.PendingEgress:
    req = EgressRequest(platform="gmail", action_type="send_email", payload={"to": "a@b.c"})
    return pending.create(req, _preview(req), "mcp")


@pytest_asyncio.fixture
async def api_client(db):
    from laya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# CA-01 — confirm_egress is invisible and denied over MCP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConfirmEgressNotOnMcp:
    async def test_scope_helper_excludes_confirm_egress(self):
        names = enabled_tool_names(ALL_SCOPES)
        assert "confirm_egress" not in names
        assert "send_email" in names

    async def test_list_tools_hides_confirm_egress(self, mcp_server):
        names = await _mcp_list(mcp_server(ALL_SCOPES))
        assert "confirm_egress" not in names
        assert "send_email" in names

    async def test_call_tool_denies_confirm_egress(self, mcp_server, egress_mocks):
        result = await _mcp_call(mcp_server(ALL_SCOPES), "confirm_egress", {"execute_token": "egr_x.y"})
        assert result.isError is True
        assert "only available to the in-app Laya chat" in result.content[0].text
        egress_mocks["execute"].assert_not_called()


# ---------------------------------------------------------------------------
# CA-02 — MCP egress creates a pending request, no token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMcpEgressCreatesPending:
    async def test_send_email_over_mcp_awaits_user(self, db, mcp_server, egress_mocks):
        result = await _mcp_call(mcp_server(ALL_SCOPES), "send_email", EMAIL_ARGS)
        assert result.isError is False
        body = json.loads(result.content[0].text)

        assert body["status"] == "awaiting_user_confirmation"
        assert body["request_id"].startswith("egreq_")
        assert "execute_token" not in body
        assert "egr_" not in result.content[0].text.replace("egreq_", "")
        egress_mocks["preview"].assert_awaited_once()
        egress_mocks["execute"].assert_not_called()

        egress_mocks["broadcast"].assert_awaited_once()
        msg = egress_mocks["broadcast"].await_args.args[0]
        assert msg["type"] == "egress_confirmation_request"
        assert msg["payload"]["request_id"] == body["request_id"]
        assert msg["payload"]["preview"]["summary"] == "Send email to alice@example.com"
        assert "token" not in json.dumps(msg)

    async def test_mcp_tool_call_is_tagged_mcp(self, mcp_server, monkeypatch):
        seen = {}

        async def fake_execute_tool(name, arguments, space_id=None):
            seen["origin"] = current_origin()
            return "{}"

        monkeypatch.setattr(http_server, "execute_tool", fake_execute_tool)
        await _mcp_call(mcp_server(ALL_SCOPES), "search_cards", {})
        assert seen["origin"] == "mcp"


# ---------------------------------------------------------------------------
# CA-03 / CA-04 — UI confirm / reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPendingApi:
    async def test_list_is_sanitized(self, api_client):
        entry = _mcp_entry()
        resp = await api_client.get("/egress/pending")
        assert resp.status_code == 200
        items = resp.json()["pending"]
        assert [i["request_id"] for i in items] == [entry.request_id]
        assert entry.token not in resp.text
        assert entry.nonce not in resp.text

    async def test_confirm_executes_once_and_audits(self, db, api_client, egress_mocks):
        entry = _mcp_entry()
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

        egress_mocks["execute"].assert_awaited_once_with(entry.request)
        rows = await _audit_rows(db, "execute")
        assert len(rows) == 1
        assert rows[0]["metadata"]["source"] == "mcp"
        assert (await api_client.get("/egress/pending")).json()["pending"] == []

        msg = egress_mocks["broadcast"].await_args.args[0]
        assert msg["type"] == "egress_confirmation_resolved"
        assert msg["payload"] == {
            "request_id": entry.request_id, "status": "done", "result_url": "https://mail/1",
        }

    async def test_confirm_execute_exception_audits_and_resolves_failed(
        self, db, api_client, egress_mocks
    ):
        entry = _mcp_entry()
        egress_mocks["execute"].side_effect = RuntimeError("boom")
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/confirm")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["retryable"] is False
        rows = await _audit_rows(db, "execute")
        assert len(rows) == 1
        assert rows[0]["success"] in (0, False)
        assert rows[0]["metadata"]["source"] == "mcp"
        msg = egress_mocks["broadcast"].await_args.args[0]
        assert msg["type"] == "egress_confirmation_resolved"
        assert msg["payload"]["status"] == "failed"
        assert msg["payload"]["request_id"] == entry.request_id

    async def test_reject_discards_without_executing(self, db, api_client, egress_mocks):
        entry = _mcp_entry()
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        egress_mocks["execute"].assert_not_called()
        assert (await api_client.get("/egress/pending")).json()["pending"] == []
        rows = await _audit_rows(db, "egress_rejected")
        assert len(rows) == 1
        assert rows[0]["metadata"]["source"] == "mcp"
        msg = egress_mocks["broadcast"].await_args.args[0]
        assert msg["type"] == "egress_confirmation_resolved"
        assert msg["payload"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# CA-05 — internal chat flow unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestChatFlow:
    async def test_chat_preview_then_confirm(self, db, egress_mocks):
        with tool_origin("chat"):
            out = json.loads(await execute_tool("send_email", dict(EMAIL_ARGS)))
            assert out["status"] == "preview"
            token = out["execute_token"]
            egress_mocks["broadcast"].assert_not_called()

            done = json.loads(await execute_tool("confirm_egress", {"execute_token": token}))
        assert done["status"] == "done"
        egress_mocks["execute"].assert_awaited_once()
        rows = await _audit_rows(db, "execute")
        assert rows[0]["metadata"]["source"] == "chat"

    async def test_chat_token_single_use(self, db, egress_mocks):
        with tool_origin("chat"):
            token = json.loads(await execute_tool("send_email", dict(EMAIL_ARGS)))["execute_token"]
            await execute_tool("confirm_egress", {"execute_token": token})
            again = json.loads(await execute_tool("confirm_egress", {"execute_token": token}))
        assert again["status"] == "error"
        assert egress_mocks["execute"].await_count == 1


# ---------------------------------------------------------------------------
# CA-06 / CR-03 — CSPRNG tokens and constant-time verification
# ---------------------------------------------------------------------------


class TestTokenCrypto:
    def test_secret_is_csprng_bytes(self):
        assert isinstance(pending._SECRET, bytes)
        assert len(pending._SECRET) == 32
        assert not hasattr(tool_handlers, "_TOKEN_SECRET")

    def test_consecutive_tokens_differ(self):
        req = EgressRequest(platform="gmail", action_type="send_email", payload={})
        a = pending.create(req, _preview(req), "chat")
        b = pending.create(req, _preview(req), "chat")
        assert a.token != b.token
        assert a.token.startswith("egr_") and "." in a.token

    def test_verification_uses_compare_digest(self, monkeypatch):
        req = EgressRequest(platform="gmail", action_type="send_email", payload={})
        entry = pending.create(req, _preview(req), "chat")
        calls = []
        real_compare = hmac.compare_digest

        def spy(a, b):
            calls.append((a, b))
            return real_compare(a, b)

        monkeypatch.setattr(pending.hmac, "compare_digest", spy)
        assert pending.consume_token(entry.token, "chat") is entry
        assert calls

    @pytest.mark.parametrize("mutate", [
        lambda t: t[:-1] + ("0" if t[-1] != "0" else "1"),  # tampered signature
        lambda t: t.split(".")[0],                          # no signature
        lambda t: "garbage",                                # wrong format
    ])
    def test_invalid_signature_rejected_before_lookup(self, mutate, monkeypatch):
        req = EgressRequest(platform="gmail", action_type="send_email", payload={})
        entry = pending.create(req, _preview(req), "chat")
        lookups = []
        real_get = dict.get

        class SpyDict(dict):
            def get(self, *a, **kw):
                lookups.append(a)
                return real_get(self, *a, **kw)

        monkeypatch.setattr(pending, "_by_nonce", SpyDict(pending._by_nonce))
        monkeypatch.setattr(pending, "_store", SpyDict(pending._store))
        with pytest.raises(pending.PendingLookupError) as exc:
            pending.consume_token(mutate(entry.token), "chat")
        assert exc.value.reason == "invalid_token"
        assert lookups == []

    @pytest.mark.asyncio
    async def test_invalid_token_not_logged(self, db, egress_mocks, capsys):
        forged = "egr_abcdefghijklmnop.0123456789abcdef0123456789abcdef"
        with tool_origin("chat"):
            out = json.loads(await execute_tool("confirm_egress", {"execute_token": forged}))
        assert out["status"] == "error"
        assert forged not in out["error"]
        captured = capsys.readouterr()
        assert forged not in captured.out + captured.err
        egress_mocks["execute"].assert_not_called()


# ---------------------------------------------------------------------------
# CR-01 — chat and MCP entries cannot resolve each other
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOriginBinding:
    async def test_chat_cannot_confirm_mcp_request(self, db, egress_mocks):
        entry = _mcp_entry()
        forged = f"egr_{entry.nonce}.{pending._sign(entry.nonce, 'chat')}"
        with tool_origin("chat"):
            by_id = json.loads(await execute_tool("confirm_egress", {"execute_token": entry.request_id}))
            by_forged = json.loads(await execute_tool("confirm_egress", {"execute_token": forged}))
            by_real = json.loads(await execute_tool("confirm_egress", {"execute_token": entry.token}))
        assert by_id["status"] == by_forged["status"] == by_real["status"] == "error"
        egress_mocks["execute"].assert_not_called()
        assert [i["request_id"] for i in pending.list_pending()] == [entry.request_id]

    async def test_chat_token_on_pending_api_is_404(self, api_client, egress_mocks):
        with tool_origin("chat"):
            token = json.loads(await execute_tool("send_email", dict(EMAIL_ARGS)))["execute_token"]
        resp = await api_client.post(f"/egress/pending/{token}/confirm")
        assert resp.status_code == 404
        egress_mocks["execute"].assert_not_called()

    async def test_chat_request_id_on_pending_api_is_404(self, api_client, egress_mocks):
        req = EgressRequest(platform="gmail", action_type="send_email", payload={})
        chat_entry = pending.create(req, _preview(req), "chat")
        resp = await api_client.post(f"/egress/pending/{chat_entry.request_id}/confirm")
        assert resp.status_code == 404
        egress_mocks["execute"].assert_not_called()


# ---------------------------------------------------------------------------
# CR-02 — expired or reused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExpiryAndReuse:
    async def test_expired_request_not_executed(self, api_client, egress_mocks, monkeypatch):
        entry = _mcp_entry()
        monkeypatch.setattr(pending, "_now", lambda: entry.expires_at + 1)
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/confirm")
        assert resp.status_code in (404, 410)
        egress_mocks["execute"].assert_not_called()

    async def test_reused_request_not_executed_twice(self, db, api_client, egress_mocks):
        entry = _mcp_entry()
        assert (await api_client.post(f"/egress/pending/{entry.request_id}/confirm")).status_code == 200
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/confirm")
        assert resp.status_code == 404
        assert egress_mocks["execute"].await_count == 1

    async def test_rejected_request_cannot_be_confirmed(self, db, api_client, egress_mocks):
        entry = _mcp_entry()
        await api_client.post(f"/egress/pending/{entry.request_id}/reject")
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/confirm")
        assert resp.status_code == 404
        egress_mocks["execute"].assert_not_called()


# ---------------------------------------------------------------------------
# CR-04 — unknown origin is fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFailClosedOrigin:
    async def test_untagged_egress_behaves_as_mcp(self, db, egress_mocks):
        assert current_origin() == "mcp"
        out = json.loads(await execute_tool("send_email", dict(EMAIL_ARGS)))
        assert out["status"] == "awaiting_user_confirmation"
        assert "execute_token" not in out
        egress_mocks["execute"].assert_not_called()

    async def test_untagged_confirm_egress_refused(self, db, egress_mocks):
        req = EgressRequest(platform="gmail", action_type="send_email", payload={})
        chat_entry = pending.create(req, _preview(req), "chat")
        out = json.loads(await execute_tool("confirm_egress", {"execute_token": chat_entry.token}))
        assert out["status"] == "error"
        egress_mocks["execute"].assert_not_called()
        # The refused call must not burn the chat's pending entry.
        assert chat_entry.request_id in pending._store

    async def test_executor_refuses_mcp_confirm_without_calling_handler(self, monkeypatch):
        handler = AsyncMock(return_value=json.dumps({"status": "done"}))
        monkeypatch.setattr("laya.llm.tools.executor.handle_confirm_egress", handler)
        with tool_origin("mcp"):
            out = json.loads(await execute_tool("confirm_egress", {"execute_token": "egr_x.y"}))
        assert out["status"] == "error"
        assert "only available to the in-app Laya chat" in out["error"]
        handler.assert_not_called()

        with tool_origin("chat"):
            await execute_tool("confirm_egress", {"execute_token": "egr_x.y"})
        handler.assert_awaited_once()


# ---------------------------------------------------------------------------
# CR-05 — cross-site Origin on pending endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrossSiteOrigin:
    @pytest.mark.parametrize("action", ["confirm", "reject"])
    async def test_external_origin_forbidden(self, api_client, egress_mocks, action):
        entry = _mcp_entry()
        resp = await api_client.post(
            f"/egress/pending/{entry.request_id}/{action}",
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403
        egress_mocks["execute"].assert_not_called()
        assert [i["request_id"] for i in pending.list_pending()] == [entry.request_id]

    async def test_app_origin_allowed(self, db, api_client, egress_mocks):
        entry = _mcp_entry()
        resp = await api_client.post(
            f"/egress/pending/{entry.request_id}/confirm",
            headers={"Origin": "tauri://localhost"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CR-06 — egress scope off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEgressScopeOff:
    async def test_send_email_denied_without_pending(self, mcp_server, egress_mocks):
        server = mcp_server({"read": True, "write": True, "egress": False})
        result = await _mcp_call(server, "send_email", EMAIL_ARGS)
        assert result.isError is True
        assert "not enabled in the current MCP scope" in result.content[0].text
        assert pending.list_pending() == []
        egress_mocks["preview"].assert_not_called()
