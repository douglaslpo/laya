# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""SEC-03 — authenticated engine <-> n8n link (X-Laya-Link-Token).

Covers CA-01, CA-02, CA-05, CA-06 and CR-01..CR-07 of
specs/sec-03-n8n-engine-link-auth.md. CA-03 lives in
test_n8n_workflow_link_static.py; CA-04 in test_n8n_bootstrap.py and
test_egress_connections.py.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import keyring
import pytest
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from laya.security import keychain
from laya.security.n8n_link import (
    LINK_CRED_NAME,
    LINK_CRED_TYPE,
    LINK_HEADER,
    get_link_state,
    link_headers,
)
from tests.conftest import TEST_N8N_LINK_SECRET


@pytest.fixture(autouse=True)
def _isolated_settings():
    """Restore settings.json after each test (link state is persisted there)."""
    import laya.config as cfg

    path = cfg.LAYA_CONFIG_FILE
    original = path.read_text(encoding="utf-8") if path.exists() else None
    cfg._settings_cache = None
    yield
    if original is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(original, encoding="utf-8")
    cfg._settings_cache = None


def _set_link_state(enforced: bool, started_at: str | None = None) -> None:
    from laya.config import load_settings, save_settings

    settings = load_settings()
    settings.setdefault("security", {})["n8n_link"] = {
        "enforced": enforced,
        "transition_started_at": started_at,
    }
    save_settings(settings)


def _event_payload(event_id: str = "evt_link-001") -> dict:
    return {
        "event_id": event_id,
        "timestamp": "2026-09-29T12:00:00Z",
        "source": {"platform": "jira", "raw_event_type": "issue_assigned"},
        "actor": {"name": "Sarah", "email": "sarah@company.com"},
        "subject": {"type": "ticket", "id": "BUG-1", "title": "NPE"},
        "content": {"body": "boom", "attachments": [], "metadata": {}},
    }


def _error_payload() -> dict:
    return {
        "workflow_id": "wf_1",
        "error_message": "boom",
        "occurred_at": "2026-09-29T12:00:00Z",
    }


async def _post(path: str, body: dict, headers: dict | None = None) -> httpx.Response:
    from laya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, json=body, headers=headers or {})


async def _event_count(db) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS n FROM events")
    return rows[0]["n"]


async def _error_count(db) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS n FROM ingestion_errors")
    return rows[0]["n"]


# ---------------------------------------------------------------------------
# CA-01 / CR-01 / CR-02 / CR-03 — route dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.no_link_header
class TestIngestionRoutesAuth:
    async def test_authenticated_event_is_accepted(self, db):
        """CA-01."""
        _set_link_state(enforced=True)
        resp = await _post("/events", _event_payload(), {LINK_HEADER: TEST_N8N_LINK_SECRET})
        assert resp.status_code == 202
        rows = await db.execute_fetchall(
            "SELECT processing_status FROM events WHERE event_id = 'evt_link-001'"
        )
        assert rows and rows[0]["processing_status"] == "queued"

    @pytest.mark.parametrize("headers", [{}, {LINK_HEADER: "wrong-token-value-xyz"}, {LINK_HEADER: ""}])
    async def test_missing_or_wrong_header_rejected_when_enforced(self, db, headers):
        """CR-01: 401, nothing persisted, no enqueue, presented value not logged."""
        _set_link_state(enforced=True)
        with patch("laya.api.events.enqueue_event", new_callable=AsyncMock) as enqueue, \
             capture_logs() as logs:
            resp = await _post("/events", _event_payload(), headers)
            err = await _post("/ingestion-errors", _error_payload(), headers)

        assert resp.status_code == 401
        assert resp.json() == {"detail": "unauthorized"}
        assert err.status_code == 401
        assert await _event_count(db) == 0
        assert await _error_count(db) == 0
        enqueue.assert_not_awaited()
        dumped = json.dumps(logs, default=str)
        assert "wrong-token-value-xyz" not in dumped
        assert TEST_N8N_LINK_SECRET not in dumped

    async def test_authenticated_ingestion_error_is_accepted(self, db):
        _set_link_state(enforced=True)
        resp = await _post("/ingestion-errors", _error_payload(), {LINK_HEADER: TEST_N8N_LINK_SECRET})
        assert resp.status_code == 202
        assert await _error_count(db) == 1

    async def test_wrong_header_rejected_during_transition(self, db):
        """CR-02: the transition only tolerates an absent header."""
        _set_link_state(enforced=False, started_at=datetime.now(timezone.utc).isoformat())
        resp = await _post("/events", _event_payload(), {LINK_HEADER: "nope"})
        assert resp.status_code == 401
        assert await _event_count(db) == 0

    async def test_missing_header_tolerated_inside_window(self, db):
        _set_link_state(enforced=False, started_at=datetime.now(timezone.utc).isoformat())
        with capture_logs() as logs:
            resp = await _post("/events", _event_payload())
        assert resp.status_code == 202
        assert any(e.get("event") == "n8n_link_transition_accept" for e in logs)

    async def test_first_headerless_request_starts_window(self, db):
        _set_link_state(enforced=False, started_at=None)
        resp = await _post("/events", _event_payload())
        assert resp.status_code == 202
        assert get_link_state()["transition_started_at"]

    async def test_expired_window_enforces(self, db):
        """CR-03: > 24 h since transition start -> flag persisted, 401."""
        started = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        _set_link_state(enforced=False, started_at=started)
        resp = await _post("/events", _event_payload())
        assert resp.status_code == 401
        assert get_link_state()["enforced"] is True
        assert await _event_count(db) == 0


# ---------------------------------------------------------------------------
# CR-05 — keychain unavailable -> 503 fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.no_link_header
async def test_keychain_failure_fails_closed(db):
    _set_link_state(enforced=False, started_at=datetime.now(timezone.utc).isoformat())
    keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)
    with patch("keyring.get_password", side_effect=RuntimeError("keychain locked")), \
         capture_logs() as logs:
        resp = await _post("/events", _event_payload())
        with_header = await _post("/events", _event_payload(), {LINK_HEADER: TEST_N8N_LINK_SECRET})

    assert resp.status_code == 503
    assert with_header.status_code == 503
    assert await _event_count(db) == 0
    events = [e for e in logs if e.get("event") == "n8n_link_secret_unavailable"]
    assert events
    assert TEST_N8N_LINK_SECRET not in json.dumps(logs, default=str)


def test_ensure_does_not_regenerate_on_keychain_error():
    keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)
    with patch("keyring.get_password", side_effect=RuntimeError("locked")), \
         patch("keyring.set_password") as set_pw:
        assert keychain.ensure_n8n_link_secret() is None
    set_pw.assert_not_called()


# ---------------------------------------------------------------------------
# CA-05 — engine -> executor header
# ---------------------------------------------------------------------------


def test_link_headers_carry_secret():
    assert link_headers() == {LINK_HEADER: TEST_N8N_LINK_SECRET}


# ---------------------------------------------------------------------------
# CA-02 / CR-04 — provisioning of secret + credential
# ---------------------------------------------------------------------------


def _clear_secret() -> None:
    try:
        keyring.delete_password(keychain.SERVICE_NAME, keychain.N8N_LINK_SECRET_KEY)
    except Exception:
        pass
    keychain._cache_drop(keychain.N8N_LINK_SECRET_KEY)


def _resp(status: int, body) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


@pytest.mark.asyncio
class TestEnsureLinkCredential:
    async def test_creates_secret_and_credential_idempotently(self, tmp_path):
        """CA-02."""
        from laya.integrations.n8n_bootstrap import ensure_link_credential

        _clear_secret()
        client = MagicMock()
        client.get = AsyncMock(return_value=_resp(200, {"data": []}))
        client.post = AsyncMock(return_value=_resp(200, {"id": "cred_1"}))
        client.delete = AsyncMock()

        with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "v.json"), \
             patch("laya.integrations.n8n_bootstrap.get_client", return_value=client):
            cred_id, changed = await ensure_link_credential("http://n8n", "key")

            secret = keychain.get_n8n_link_secret()
            assert cred_id == "cred_1" and changed is True
            assert secret and len(secret) >= 43
            assert all(c.isalnum() or c in "-_" for c in secret)
            body = client.post.call_args.kwargs["json"]
            assert body["name"] == LINK_CRED_NAME
            assert body["type"] == LINK_CRED_TYPE
            assert body["data"] == {"name": LINK_HEADER, "value": secret}

            client.get = AsyncMock(return_value=_resp(200, {"data": [
                {"id": "cred_1", "name": LINK_CRED_NAME, "type": LINK_CRED_TYPE},
            ]}))
            again = await ensure_link_credential("http://n8n", "key")

        assert again == ("cred_1", False)
        assert client.post.await_count == 1
        assert keychain.get_n8n_link_secret() == secret
        stored = (tmp_path / "v.json").read_text()
        assert secret not in stored

    async def test_recreates_divergent_credential(self, tmp_path):
        from laya.integrations.n8n_bootstrap import ensure_link_credential

        client = MagicMock()
        client.get = AsyncMock(return_value=_resp(200, {"data": []}))
        client.post = AsyncMock(return_value=_resp(200, {"id": "cred_1"}))
        client.delete = AsyncMock()
        with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "v.json"), \
             patch("laya.integrations.n8n_bootstrap.get_client", return_value=client):
            await ensure_link_credential("http://n8n", "key")

            keychain.store_n8n_link_secret("rotated-secret-" + "z" * 40)
            client.get = AsyncMock(return_value=_resp(200, {"data": [
                {"id": "cred_1", "name": LINK_CRED_NAME, "type": LINK_CRED_TYPE},
            ]}))
            client.post = AsyncMock(return_value=_resp(200, {"id": "cred_2"}))
            cred_id, changed = await ensure_link_credential("http://n8n", "key")

        assert (cred_id, changed) == ("cred_2", True)
        deleted = [c.args[0] for c in client.delete.call_args_list]
        assert deleted == ["http://n8n/api/v1/credentials/cred_1"]

    async def test_n8n_down_keeps_secret(self, tmp_path):
        """CR-04: failed attempts neither create a credential nor rotate the secret."""
        from laya.integrations.n8n_bootstrap import ensure_link_credential

        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.post = AsyncMock()
        with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "v.json"), \
             patch("laya.integrations.n8n_bootstrap.get_client", return_value=client):
            first = await ensure_link_credential("http://n8n", "key")
            second = await ensure_link_credential("http://n8n", "key")

        assert first == (None, False) and second == (None, False)
        client.post.assert_not_awaited()
        assert keychain.get_n8n_link_secret() == TEST_N8N_LINK_SECRET


# ---------------------------------------------------------------------------
# CA-06 — existing install migrates to enforcement after propagation
# ---------------------------------------------------------------------------


async def _seed_github_clone(db):
    await db.execute(
        """INSERT INTO egress_connections
           (connection_id, platform, name, n8n_credential_id, created_at, updated_at)
           VALUES ('conn_gh', 'github', 'Work', 'cred_gh', '2026-09-29 00:00:00', '2026-09-29 00:00:00')"""
    )
    await db.execute(
        """INSERT INTO sources
           (source_id, name, platform, workflow_id, space_id, source_type, connection_id)
           VALUES ('src_gh', 'GH In', 'github', 'wf_gh', 'default', 'ingestion', 'conn_gh')"""
    )
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.no_link_header
class TestMigration:
    async def _import(self, tmp_path, update_ok: bool, update_error: Exception | None = None):
        from laya.integrations.n8n_bootstrap import import_workflows

        with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "v.json"), \
             patch("laya.integrations.n8n_bootstrap.get_api_key", return_value="key"), \
             patch("laya.integrations.n8n_bootstrap.ensure_link_credential",
                   new_callable=AsyncMock, return_value=("cred_link", False)), \
             patch("laya.integrations.n8n_bootstrap._ensure_error_handler_workflow",
                   new_callable=AsyncMock, return_value="wf_handler"), \
             patch("laya.integrations.n8n_bootstrap._update_workflow",
                   new_callable=AsyncMock, return_value=update_ok, side_effect=update_error):
            return await import_workflows("http://n8n")

    async def test_successful_propagation_enforces(self, db, tmp_path):
        """CA-06."""
        _set_link_state(enforced=False)
        await _seed_github_clone(db)

        assert (await _post("/events", _event_payload("evt_before"))).status_code == 202
        updated = await self._import(tmp_path, update_ok=True)

        assert updated == 1
        assert get_link_state()["enforced"] is True
        resp = await _post("/events", _event_payload("evt_after"))
        assert resp.status_code == 401

    async def test_failed_propagation_keeps_transition_and_retries(self, db, tmp_path):
        _set_link_state(enforced=False)
        await _seed_github_clone(db)

        await self._import(tmp_path, update_ok=False)

        state = get_link_state()
        assert state["enforced"] is False
        assert state["transition_started_at"]
        versions = json.loads((tmp_path / "v.json").read_text())
        assert "Laya - GitHub Ingestion" not in versions

    async def test_orphan_clone_404_does_not_block_enforcement(self, db, tmp_path):
        from laya.integrations.n8n_bootstrap import _WorkflowNotFound

        _set_link_state(enforced=False)
        await _seed_github_clone(db)

        updated = await self._import(tmp_path, update_ok=False, update_error=_WorkflowNotFound("wf_gh"))

        assert updated == 0
        assert get_link_state()["enforced"] is True
        versions = json.loads((tmp_path / "v.json").read_text())
        assert "Laya - GitHub Ingestion" in versions

    async def test_fresh_install_without_clones_enforces(self, db, tmp_path):
        _set_link_state(enforced=False)
        await self._import(tmp_path, update_ok=True)
        assert get_link_state()["enforced"] is True

    async def test_startup_enforces_fresh_install_without_n8n(self, db):
        """RF-S3-08: no clones -> enforced at startup, before n8n is reachable."""
        from laya.integrations.n8n_bootstrap import enforce_link_if_no_clones

        _set_link_state(enforced=False)
        assert await enforce_link_if_no_clones() is True
        assert get_link_state()["enforced"] is True
        assert (await _post("/events", _event_payload())).status_code == 401

    async def test_startup_keeps_transition_when_clones_exist(self, db):
        from laya.integrations.n8n_bootstrap import enforce_link_if_no_clones

        _set_link_state(enforced=False)
        await _seed_github_clone(db)
        assert await enforce_link_if_no_clones() is False
        assert get_link_state()["enforced"] is False


# ---------------------------------------------------------------------------
# INV-S3-01 — link state is engine-owned; PUT /settings cannot reset it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.no_link_header
class TestLinkStateNotUserWritable:
    async def test_put_settings_cannot_disable_enforcement(self, db):
        from laya.main import app

        _set_link_state(enforced=True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/settings", json={
                "security": {"n8n_link": {"enforced": False, "transition_started_at": None}},
                "omni": {"density": "standard"},
            })
        assert resp.status_code == 200
        assert get_link_state()["enforced"] is True

        from laya.config import load_settings
        assert load_settings()["omni"]["density"] == "standard"
        ev = await _post("/events", _event_payload())
        assert ev.status_code == 401
        assert await _event_count(db) == 0

    @pytest.mark.parametrize("bad_security", [None, "off", ["n8n_link"]])
    async def test_put_settings_non_dict_security_keeps_link_state(self, db, bad_security):
        from laya.main import app

        _set_link_state(enforced=True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put("/settings", json={"security": bad_security})
        assert resp.status_code == 200
        assert get_link_state()["enforced"] is True
        ev = await _post("/events", _event_payload())
        assert ev.status_code == 401

    async def test_enforcement_is_monotonic(self, db):
        from laya.security.n8n_link import _save_link_state

        _set_link_state(enforced=True)
        _save_link_state(enforced=False, transition_started_at=None)
        assert get_link_state()["enforced"] is True


# ---------------------------------------------------------------------------
# CR-07 — secret never reaches settings, API responses, logs or n8n env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_secret_absent_from_forbidden_surfaces(db, tmp_path):
    import laya.config as cfg
    from laya.integrations.n8n_bootstrap import ensure_link_credential
    from laya.main import app

    _clear_secret()
    client = MagicMock()
    client.get = AsyncMock(return_value=_resp(200, {"data": []}))
    client.post = AsyncMock(return_value=_resp(200, {"id": "cred_1"}))
    client.delete = AsyncMock()

    with capture_logs() as logs:
        with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "v.json"), \
             patch("laya.integrations.n8n_bootstrap.get_client", return_value=client):
            await ensure_link_credential("http://n8n", "key")
        _set_link_state(enforced=True)
        secret = keychain.get_n8n_link_secret()
        assert secret
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            settings_resp = await c.get("/settings")
            await c.post("/events", json=_event_payload(), headers={LINK_HEADER: secret})
            await c.post("/events", json=_event_payload("evt_bad"), headers={LINK_HEADER: "bad"})

    assert secret not in cfg.LAYA_CONFIG_FILE.read_text(encoding="utf-8")
    assert secret not in settings_resp.text
    assert secret not in (tmp_path / "v.json").read_text()
    assert secret not in json.dumps(logs, default=str)

    n8n_rs = Path(__file__).resolve().parents[2] / "ui" / "src-tauri" / "src" / "n8n.rs"
    if n8n_rs.exists():
        src = n8n_rs.read_text(encoding="utf-8")
        assert "laya_n8n_link_secret" not in src
        assert "LINK_TOKEN" not in src.upper().replace("-", "_")
