# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Tests for n8n auto-provisioning (bootstrap)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from laya.integrations.n8n_bootstrap import (
    _create_api_key,
    _create_owner,
    _try_login,
    _wait_for_n8n,
    ensure_n8n_ready,
    import_workflows,
)


@pytest.mark.asyncio
class TestWaitForN8n:
    """Tests for _wait_for_n8n health polling."""

    async def test_returns_true_when_healthy(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _wait_for_n8n("http://localhost:45678", timeout=2.0)

        assert result is True

    async def test_returns_false_on_timeout(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _wait_for_n8n("http://localhost:45678", timeout=1.5)

        assert result is False


@pytest.mark.asyncio
class TestTryLogin:
    """Tests for _try_login."""

    async def test_returns_cookies_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.cookies = {"n8n-auth": "session-cookie"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _try_login("http://localhost:45678", "a@b.com", "pass")

        assert result == {"n8n-auth": "session-cookie"}

    async def test_returns_none_on_failure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _try_login("http://localhost:45678", "a@b.com", "wrong")

        assert result is None


@pytest.mark.asyncio
class TestCreateOwner:
    """Tests for _create_owner."""

    async def test_returns_cookies_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.cookies = {"n8n-auth": "owner-cookie"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _create_owner("http://localhost:45678", "a@b.com", "pass")

        assert result == {"n8n-auth": "owner-cookie"}

    async def test_returns_none_when_owner_exists(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"message":"Instance owner already setup"}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _create_owner("http://localhost:45678", "a@b.com", "pass")

        assert result is None


@pytest.mark.asyncio
class TestCreateApiKey:
    """Tests for _create_api_key."""

    async def test_extracts_key_from_data_wrapper(self):
        """Handles n8n response with {data: {rawApiKey: ...}} wrapper."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"rawApiKey": "test-key-123", "label": "laya-engine"}}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _create_api_key("http://localhost:45678", {"n8n-auth": "cookie"})

        assert result == "test-key-123"

    async def test_extracts_key_from_flat_response(self):
        """Handles n8n response with {rawApiKey: ...} directly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"rawApiKey": "flat-key-456"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = await _create_api_key("http://localhost:45678", {"n8n-auth": "cookie"})

        assert result == "flat-key-456"


@pytest.mark.asyncio
class TestEnsureN8nReady:
    """Tests for the main ensure_n8n_ready orchestrator."""

    async def test_returns_unreachable_when_n8n_down(self):
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=False):
            with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                result = await ensure_n8n_ready()

        assert result["status"] == "unreachable"
        assert "not running" in result["message"]

    async def test_returns_already_configured_when_key_valid(self):
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=True):
            with patch("laya.integrations.n8n_bootstrap._test_existing_api_key", new_callable=AsyncMock, return_value=True):
                with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                    result = await ensure_n8n_ready()

        assert result["status"] == "already_configured"
        assert result["has_api_key"] is True

    async def test_full_bootstrap_fresh_n8n(self):
        """Fresh n8n: create owner succeeds → create API key → import workflows."""
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=True):
            with patch("laya.integrations.n8n_bootstrap._test_existing_api_key", new_callable=AsyncMock, return_value=False):
                with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value=None):
                    with patch("laya.integrations.n8n_bootstrap._create_owner", new_callable=AsyncMock, return_value={"n8n-auth": "cookie"}):
                        with patch("laya.integrations.n8n_bootstrap.store_api_key", return_value=True):
                            with patch("laya.integrations.n8n_bootstrap._create_api_key", new_callable=AsyncMock, return_value="test-api-key"):
                                with patch("laya.integrations.n8n_bootstrap.import_workflows", new_callable=AsyncMock, return_value=5):
                                    with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                                        result = await ensure_n8n_ready()

        assert result["status"] == "ready"
        assert result["has_api_key"] is True
        assert "5 workflows" in result["message"]

    async def test_login_when_owner_exists(self):
        """Owner already exists (create returns None) → login succeeds → create API key."""
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=True):
            with patch("laya.integrations.n8n_bootstrap._test_existing_api_key", new_callable=AsyncMock, return_value=False):
                with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value="stored_pass"):
                    with patch("laya.integrations.n8n_bootstrap._create_owner", new_callable=AsyncMock, return_value=None):
                        with patch("laya.integrations.n8n_bootstrap._try_login", new_callable=AsyncMock, return_value={"n8n-auth": "cookie"}):
                            with patch("laya.integrations.n8n_bootstrap._create_api_key", new_callable=AsyncMock, return_value="new-key"):
                                with patch("laya.integrations.n8n_bootstrap.store_api_key", return_value=True):
                                    with patch("laya.integrations.n8n_bootstrap.import_workflows", new_callable=AsyncMock, return_value=0):
                                        with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                                            result = await ensure_n8n_ready()

        assert result["status"] == "ready"

    async def test_returns_error_when_login_fails(self):
        """Owner exists but login fails → error."""
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=True):
            with patch("laya.integrations.n8n_bootstrap._test_existing_api_key", new_callable=AsyncMock, return_value=False):
                with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value="wrong_pass"):
                    with patch("laya.integrations.n8n_bootstrap._create_owner", new_callable=AsyncMock, return_value=None):
                        with patch("laya.integrations.n8n_bootstrap._try_login", new_callable=AsyncMock, return_value=None):
                            with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                                result = await ensure_n8n_ready()

        assert result["status"] == "error"
        assert "cannot authenticate" in result["message"].lower()

    async def test_returns_error_when_api_key_creation_fails(self):
        """Authenticated but API key creation fails → error."""
        with patch("laya.integrations.n8n_bootstrap._wait_for_n8n", new_callable=AsyncMock, return_value=True):
            with patch("laya.integrations.n8n_bootstrap._test_existing_api_key", new_callable=AsyncMock, return_value=False):
                with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value=None):
                    with patch("laya.integrations.n8n_bootstrap._create_owner", new_callable=AsyncMock, return_value={"n8n-auth": "cookie"}):
                        with patch("laya.integrations.n8n_bootstrap.store_api_key", return_value=True):
                            with patch("laya.integrations.n8n_bootstrap._create_api_key", new_callable=AsyncMock, return_value=None):
                                with patch("laya.integrations.n8n_bootstrap.get_n8n_config", return_value={"base_url": "http://localhost:45678"}):
                                    result = await ensure_n8n_ready()

        assert result["status"] == "error"
        assert "failed to create api key" in result["message"].lower()


@pytest.mark.asyncio
class TestImportWorkflows:
    """Tests for workflow import."""

    async def test_imports_workflow_files(self, tmp_path):
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        (wf_dir / "test-workflow.json").write_text(json.dumps({
            "name": "Test", "active": True, "meta": {"laya_version": "2026.04.1"},
        }))

        # Mock GET /api/v1/workflows to return empty list (no existing workflows)
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"data": []}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_get_resp)

        versions_file = tmp_path / "versions.json"

        with patch("laya.integrations.n8n_bootstrap.WORKFLOWS_DIR", wf_dir):
            with patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", versions_file):
                with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value="test-key"):
                    with patch("laya.integrations.n8n_bootstrap.get_client", return_value=mock_client), \
                         patch("laya.integrations.n8n_bootstrap.ensure_link_credential",
                               new_callable=AsyncMock, return_value=("cred_link", False)), \
                         patch("laya.integrations.n8n_bootstrap.mark_enforced"), \
                         patch("laya.integrations.n8n_bootstrap.start_transition_if_needed"):
                        count = await import_workflows("http://localhost:45678")

        # No clones to update, so count is 0, but version should be tracked
        assert count == 0
        saved = json.loads(versions_file.read_text())
        assert saved["Test"] == "2026.04.1"

    async def test_skips_when_no_api_key(self):
        with patch("laya.integrations.n8n_bootstrap.get_api_key", return_value=None):
            count = await import_workflows("http://localhost:45678")

        assert count == 0

    async def test_defers_when_link_credential_unavailable(self, tmp_path):
        """CR-04: without the link credential nothing is deployed; the
        background retry picks it up later."""
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        with patch("laya.integrations.n8n_bootstrap.WORKFLOWS_DIR", wf_dir), \
             patch("laya.integrations.n8n_bootstrap.get_api_key", return_value="test-key"), \
             patch("laya.integrations.n8n_bootstrap.ensure_link_credential",
                   new_callable=AsyncMock, return_value=(None, False)), \
             patch("laya.integrations.n8n_bootstrap._ensure_error_handler_workflow",
                   new_callable=AsyncMock) as handler:
            with pytest.raises(RuntimeError):
                await import_workflows("http://localhost:45678")
        handler.assert_not_awaited()


@pytest.mark.asyncio
class TestBootstrapEndpoint:
    """Tests for POST /settings/n8n/bootstrap endpoint."""

    async def test_endpoint_returns_result(self):
        from laya.main import app

        mock_result = {
            "status": "ready",
            "message": "n8n provisioned successfully (5 workflows imported)",
            "has_api_key": True,
        }

        with patch("laya.api.settings_api.ensure_n8n_ready", new_callable=AsyncMock, return_value=mock_result):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/settings/n8n/bootstrap")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["has_api_key"] is True


# ---------------------------------------------------------------------------
# SEC-03 CA-04: propagation keeps engine-link and platform credentials apart
# ---------------------------------------------------------------------------

_LINK_ID = "cred_link_123"


async def _seed_clone(db, platform, conn_id, cred_id, source_type, wf_id, name, webhook_path=None):
    await db.execute(
        """INSERT OR IGNORE INTO egress_connections
           (connection_id, platform, name, n8n_credential_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, '2026-09-29 00:00:00', '2026-09-29 00:00:00')""",
        (conn_id, platform, f"{platform} conn", cred_id),
    )
    await db.execute(
        """INSERT INTO sources
           (source_id, name, platform, workflow_id, space_id, source_type, webhook_path, connection_id)
           VALUES (?, ?, ?, ?, 'default', ?, ?, ?)""",
        (f"src_{wf_id}", name, platform, wf_id, source_type, webhook_path, conn_id),
    )
    await db.commit()


def _creds_by_node(update_data):
    return {n["name"]: (n.get("credentials") or {}) for n in update_data["nodes"]}


@pytest.mark.asyncio
class TestPropagateLinkCredential:
    async def test_bitbucket_server_and_github_keep_both_credentials(self, db):
        from laya.integrations.n8n_bootstrap import _propagate_to_clones
        from laya.security.n8n_link import LINK_CRED_NAME

        await _seed_clone(db, "bitbucket_server", "conn_bbs", "cred_bbs", "ingestion", "wf_bbs_in", "BBS In")
        await _seed_clone(db, "bitbucket_server", "conn_bbs", "cred_bbs", "executor", "wf_bbs_ex", "BBS Ex",
                          webhook_path="bitbucket-server-executor-bbs")
        await _seed_clone(db, "github", "conn_gh", "cred_gh", "ingestion", "wf_gh_in", "GH In")
        await _seed_clone(db, "github", "conn_gh", "cred_gh", "executor", "wf_gh_ex", "GH Ex",
                          webhook_path="github-executor-gh")

        captured: dict[str, dict] = {}

        async def _fake_update(base_url, api_key, wf_id, data):
            captured[wf_id] = data
            return True

        templates = [
            "Laya - Bitbucket Server Ingestion", "Laya - Bitbucket Server Executor",
            "Laya - GitHub Ingestion", "Laya - GitHub Executor",
        ]
        with patch("laya.integrations.n8n_bootstrap._update_workflow", side_effect=_fake_update):
            updated, failed = await _propagate_to_clones("http://n8n", "key", templates, _LINK_ID)

        assert updated == 4 and failed == set()
        link_ref = {"id": _LINK_ID, "name": LINK_CRED_NAME}

        bbs_in = _creds_by_node(captured["wf_bbs_in"])
        assert bbs_in["POST to Laya Engine"]["httpHeaderAuth"] == link_ref
        assert bbs_in["Get Pull Requests"]["httpHeaderAuth"]["id"] == "cred_bbs"

        bbs_ex = _creds_by_node(captured["wf_bbs_ex"])
        assert bbs_ex["Webhook"]["httpHeaderAuth"] == link_ref
        assert bbs_ex["Comment on PR"]["httpHeaderAuth"]["id"] == "cred_bbs"
        webhook = next(n for n in captured["wf_bbs_ex"]["nodes"] if n["name"] == "Webhook")
        assert webhook["parameters"]["path"] == "bitbucket-server-executor-bbs"
        assert webhook["parameters"]["authentication"] == "headerAuth"

        gh_in = _creds_by_node(captured["wf_gh_in"])
        assert gh_in["POST to Laya Engine"]["httpHeaderAuth"] == link_ref
        assert gh_in["POST Repo Errors"]["httpHeaderAuth"] == link_ref
        assert gh_in["Get Issues and PRs"]["githubApi"]["id"] == "cred_gh"

        gh_ex = _creds_by_node(captured["wf_gh_ex"])
        assert gh_ex["Webhook"]["httpHeaderAuth"] == link_ref
        assert gh_ex["Close Issue"]["githubApi"]["id"] == "cred_gh"

    async def test_failed_clone_update_reports_template(self, db):
        from laya.integrations.n8n_bootstrap import _propagate_to_clones

        await _seed_clone(db, "github", "conn_gh", "cred_gh", "ingestion", "wf_gh_in", "GH In")
        with patch("laya.integrations.n8n_bootstrap._update_workflow",
                   new_callable=AsyncMock, return_value=False):
            updated, failed = await _propagate_to_clones(
                "http://n8n", "key", ["Laya - GitHub Ingestion"], _LINK_ID,
            )
        assert updated == 0
        assert failed == {"Laya - GitHub Ingestion"}
