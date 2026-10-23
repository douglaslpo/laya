# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Unit gaps of imp-local-security-hardening not covered elsewhere.

- SEC-03 RF-S3-01 / CA-02 / CR-04 / CR-05: keychain link-secret helpers.
- SEC-01 CR-05: origin_guard.reject_cross_site in isolation.
- SEC-01 CR-02: exact 404/410 contract of the pending-egress REST API.
"""

import re
from unittest.mock import patch

import keyring
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from laya.api.origin_guard import ALLOWED_ORIGINS, reject_cross_site
from laya.egress import pending
from laya.egress.models import EgressPreview, EgressRequest
from laya.security import keychain

URLSAFE = re.compile(r"^[A-Za-z0-9_-]+$")


# ---------------------------------------------------------------------------
# keychain — ensure/get/store link secret
# ---------------------------------------------------------------------------


def _clear_link_secret() -> None:
    try:
        keyring.delete_password(keychain.SERVICE_NAME, keychain.N8N_LINK_SECRET_KEY)
    except Exception:
        pass
    keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)


class TestLinkSecretKeychain:
    def test_generates_urlsafe_secret_when_absent(self):
        _clear_link_secret()
        secret = keychain.ensure_n8n_link_secret()
        assert secret is not None
        assert len(secret) >= 43
        assert URLSAFE.match(secret)
        assert keyring.get_password(keychain.SERVICE_NAME, keychain.N8N_LINK_SECRET_KEY) == secret

    def test_second_call_is_idempotent(self):
        _clear_link_secret()
        first = keychain.ensure_n8n_link_secret()
        keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)
        with patch("keyring.set_password") as set_pw:
            second = keychain.ensure_n8n_link_secret()
        assert second == first
        set_pw.assert_not_called()

    def test_existing_secret_is_returned_unchanged(self):
        from tests.conftest import TEST_N8N_LINK_SECRET

        assert keychain.ensure_n8n_link_secret() == TEST_N8N_LINK_SECRET
        assert keychain.get_n8n_link_secret() == TEST_N8N_LINK_SECRET

    def test_uses_csprng_token_urlsafe(self):
        _clear_link_secret()
        with patch("secrets.token_urlsafe", return_value="x" * 43) as gen:
            assert keychain.ensure_n8n_link_secret() == "x" * 43
        gen.assert_called_once_with(32)

    def test_store_failure_returns_none(self):
        _clear_link_secret()
        with patch("keyring.set_password", side_effect=RuntimeError("locked")):
            assert keychain.ensure_n8n_link_secret() is None
        keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)
        assert keychain.get_n8n_link_secret() is None

    def test_get_returns_none_when_unset(self):
        _clear_link_secret()
        assert keychain.get_n8n_link_secret() is None

    def test_read_error_is_not_cached_as_absent(self):
        """A transient read failure must not poison the cache as 'no secret'."""
        from tests.conftest import TEST_N8N_LINK_SECRET

        keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)
        with patch("keyring.get_password", side_effect=RuntimeError("locked")):
            assert keychain.get_n8n_link_secret() is None
        assert keychain.get_n8n_link_secret() == TEST_N8N_LINK_SECRET

    def test_secret_not_logged(self):
        from structlog.testing import capture_logs

        _clear_link_secret()
        with capture_logs() as logs:
            secret = keychain.ensure_n8n_link_secret()
        assert secret
        assert secret not in repr(logs)


# ---------------------------------------------------------------------------
# origin_guard
# ---------------------------------------------------------------------------


def _request(origin: str | None) -> Request:
    headers = [(b"origin", origin.encode())] if origin is not None else []
    return Request({"type": "http", "method": "POST", "path": "/x", "headers": headers})


class TestOriginGuard:
    def test_missing_origin_allowed(self):
        reject_cross_site(_request(None))

    @pytest.mark.parametrize("origin", sorted(ALLOWED_ORIGINS))
    def test_app_origins_allowed(self, origin):
        reject_cross_site(_request(origin))

    @pytest.mark.parametrize(
        "origin",
        ["https://evil.example", "http://localhost:5174", "null", "http://127.0.0.1:8420"],
    )
    def test_foreign_origin_forbidden(self, origin):
        with pytest.raises(HTTPException) as exc:
            reject_cross_site(_request(origin))
        assert exc.value.status_code == 403

    def test_logs_custom_event(self):
        from structlog.testing import capture_logs

        with capture_logs() as logs, pytest.raises(HTTPException):
            reject_cross_site(_request("https://evil.example"), log_event="custom_block")
        assert any(e.get("event") == "custom_block" for e in logs)


# ---------------------------------------------------------------------------
# pending-egress REST contract (404 / 410)
# ---------------------------------------------------------------------------


def _mcp_entry() -> pending.PendingEgress:
    req = EgressRequest(platform="gmail", action_type="send_email", payload={"to": "a@b.c"})
    preview = EgressPreview(
        platform="gmail", action_type="send_email", summary="Send", details={},
        warnings=[], estimated_impact="low",
    )
    return pending.create(req, preview, "mcp")


@pytest_asyncio.fixture
async def api_client(db, monkeypatch):
    from unittest.mock import AsyncMock

    from laya.main import app

    pending.reset()
    execute = AsyncMock()
    monkeypatch.setattr("laya.egress.execute", execute)
    monkeypatch.setattr("laya.api.websocket.manager.broadcast", AsyncMock())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.execute_mock = execute  # type: ignore[attr-defined]
        yield client
    pending.reset()


@pytest.mark.asyncio
class TestPendingApiContract:
    @pytest.mark.parametrize("action", ["confirm", "reject"])
    async def test_unknown_request_is_404(self, api_client, action):
        resp = await api_client.post(f"/egress/pending/egq_does-not-exist/{action}")
        assert resp.status_code == 404
        assert resp.json()["detail"]
        api_client.execute_mock.assert_not_called()

    @pytest.mark.parametrize("action", ["confirm", "reject"])
    async def test_expired_request_is_410(self, api_client, monkeypatch, action):
        entry = _mcp_entry()
        monkeypatch.setattr(pending, "_now", lambda: entry.expires_at + 1)
        resp = await api_client.post(f"/egress/pending/{entry.request_id}/{action}")
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()
        api_client.execute_mock.assert_not_called()

    async def test_expired_request_hidden_from_listing(self, api_client, monkeypatch):
        entry = _mcp_entry()
        listed = (await api_client.get("/egress/pending")).json()["pending"]
        assert [p["request_id"] for p in listed] == [entry.request_id]
        assert "token" not in listed[0] and "execute_token" not in listed[0]
        assert entry.token not in str(listed)
        monkeypatch.setattr(pending, "_now", lambda: entry.expires_at + 1)
        assert (await api_client.get("/egress/pending")).json()["pending"] == []
