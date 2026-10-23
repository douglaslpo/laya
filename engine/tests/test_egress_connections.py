# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Connection Broker — credential management."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from laya.egress.connections import (
    create_connection,
    list_all_connections,
    remove_connection,
    test_connection as check_connection,
    _validate_credentials,
)
from laya.egress.models import ConnectionResult


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_jira_valid(self):
        with patch("laya.egress.connections.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            valid, error = await _validate_credentials("jira", {
                "domain": "https://company.atlassian.net",
                "email": "user@co.com",
                "apiToken": "token123",
            })
            assert valid is True
            assert error is None

    @pytest.mark.asyncio
    async def test_jira_invalid(self):
        with patch("laya.egress.connections.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            valid, error = await _validate_credentials("jira", {
                "domain": "https://company.atlassian.net",
                "email": "user@co.com",
                "apiToken": "bad_token",
            })
            assert valid is False
            assert "Invalid" in error or "credentials" in error.lower()

    @pytest.mark.asyncio
    async def test_jira_missing_fields(self):
        valid, error = await _validate_credentials("jira", {"domain": "x"})
        assert valid is False
        assert "Missing" in error

    @pytest.mark.asyncio
    async def test_github_valid(self):
        with patch("laya.egress.connections.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            valid, error = await _validate_credentials("github", {"accessToken": "ghp_abc"})
            assert valid is True

    @pytest.mark.asyncio
    async def test_slack_oauth_skips_validation(self):
        valid, error = await _validate_credentials("slack", {})
        assert valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_bitbucket_valid(self):
        with patch("laya.egress.connections.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            valid, error = await _validate_credentials("bitbucket", {
                "email": "user@co.com",
                "accessToken": "pw",
            })
            assert valid is True

    @pytest.mark.asyncio
    async def test_oauth_platform_auto_valid(self):
        valid, error = await _validate_credentials("gmail", {})
        assert valid is True  # OAuth tokens pre-validated during flow

    @pytest.mark.asyncio
    async def test_unknown_platform_passes(self):
        valid, error = await _validate_credentials("notion", {"apiKey": "x"})
        assert valid is True


class TestCreateConnection:
    @pytest.mark.asyncio
    async def test_create_connection_success(self, db):
        """Test successful connection creation with mocked validation and keychain."""
        with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(True, None)):
            with patch("laya.egress.connections._store_in_keychain", return_value=True):
                with patch("laya.egress.connections._provision_to_n8n", new_callable=AsyncMock, return_value="n8n_cred_1"):
                    # Mock workflow cloning to prevent creating real workflows in n8n
                    with patch("laya.egress.connections._clone_workflows_for_connection", new_callable=AsyncMock, return_value=(2, [])):
                        result = await create_connection("jira", {"email": "x", "apiToken": "y", "domain": "z"})

                        assert result.status == "connected"
                        assert result.connection_id is not None
                        assert "comment" in result.capabilities

                        # Verify DB record
                        rows = await db.execute_fetchall("SELECT * FROM egress_connections")
                        assert len(rows) == 1
                        assert rows[0]["platform"] == "jira"
                        assert rows[0]["status"] == "connected"

    @pytest.mark.asyncio
    async def test_create_connection_validation_failure(self, db):
        with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(False, "Bad token")):
            result = await create_connection("jira", {"email": "x"})
            assert result.status == "failed"
            assert "Bad token" in result.error

    @pytest.mark.asyncio
    async def test_create_connection_unknown_platform(self, db):
        result = await create_connection("totally_unknown", {})
        assert result.status == "failed"
        assert "Unknown" in result.error


class TestListConnections:
    @pytest.mark.asyncio
    async def test_list_empty(self, db):
        conns = await list_all_connections()
        assert conns == []

    @pytest.mark.asyncio
    async def test_list_after_create(self, db):
        with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(True, None)):
            with patch("laya.egress.connections._store_in_keychain", return_value=True):
                with patch("laya.egress.connections._provision_to_n8n", new_callable=AsyncMock, return_value="cred1"):
                    with patch("laya.egress.connections._clone_workflows_for_connection", new_callable=AsyncMock, return_value=(2, [])):
                        await create_connection("github", {"accessToken": "ghp_abc"}, name="GitHub Main")

        conns = await list_all_connections()
        assert len(conns) == 1
        assert conns[0].platform == "github"
        assert conns[0].name == "GitHub Main"
        assert "comment" in conns[0].capabilities


class TestRemoveConnection:
    @pytest.mark.asyncio
    async def test_remove_connection(self, db):
        # Create first
        with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(True, None)):
            with patch("laya.egress.connections._store_in_keychain", return_value=True):
                with patch("laya.egress.connections._provision_to_n8n", new_callable=AsyncMock, return_value="cred1"):
                    with patch("laya.egress.connections._clone_workflows_for_connection", new_callable=AsyncMock, return_value=(2, [])):
                        result = await create_connection("slack", {"accessToken": "xoxb"})

        # Verify exists
        conns = await list_all_connections()
        assert len(conns) == 1

        # Remove
        with patch("laya.egress.connections._remove_from_keychain"):
            with patch("laya.integrations.n8n_client.delete_credential", new_callable=AsyncMock):
                with patch("laya.egress.connections._remove_connection_workflows", new_callable=AsyncMock):
                    await remove_connection(result.connection_id)

        # Verify gone
        conns = await list_all_connections()
        assert len(conns) == 0


class TestCheckConnection:
    @pytest.mark.asyncio
    async def test_revalidate_connection(self, db):
        # Create
        with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(True, None)):
            with patch("laya.egress.connections._store_in_keychain", return_value=True):
                with patch("laya.egress.connections._provision_to_n8n", new_callable=AsyncMock, return_value="cred1"):
                    with patch("laya.egress.connections._clone_workflows_for_connection", new_callable=AsyncMock, return_value=(2, [])):
                        result = await create_connection("github", {"accessToken": "ghp_abc"})

        # Test it
        with patch("laya.egress.connections._get_from_keychain", return_value={"accessToken": "ghp_abc"}):
            with patch("laya.egress.connections._validate_credentials", new_callable=AsyncMock, return_value=(True, None)):
                valid, error = await check_connection(result.connection_id)
                assert valid is True

        # Verify status updated
        conns = await list_all_connections()
        assert conns[0].status == "connected"
        assert conns[0].last_validated_at is not None


# ---------------------------------------------------------------------------
# SEC-03 CA-04: cloned workflows bind the engine link and the platform
# credential to the right nodes, never one over the other.
# ---------------------------------------------------------------------------


class TestCloneLinkCredential:
    async def _clone(self, db, tmp_path, platform, cred_id, *, link_id="cred_link_123"):
        from laya.egress.connections import _clone_workflows_for_connection

        posted: list[dict] = []

        async def _post(url, headers=None, json=None, timeout=None):
            posted.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"id": f"wf_{len(posted)}"}
            return resp

        client = MagicMock()
        client.post = AsyncMock(side_effect=_post)
        with patch("laya.security.keychain.get_api_key", return_value="n8n-key"), \
             patch("laya.http_client.get_client", return_value=client), \
             patch("laya.integrations.n8n_bootstrap._get_existing_workflows",
                   new_callable=AsyncMock, return_value={}), \
             patch("laya.integrations.n8n_bootstrap._VERSIONS_FILE", tmp_path / "versions.json"), \
             patch("laya.integrations.n8n_bootstrap.get_link_credential_id", return_value=link_id), \
             patch("laya.integrations.n8n_bootstrap.ensure_link_credential",
                   new_callable=AsyncMock, return_value=(None, False)), \
             patch("laya.integrations.n8n_client.activate_workflow", new_callable=AsyncMock), \
             patch("laya.egress.connections._get_from_keychain",
                   return_value={"server": "https://bbs.local/", "allowInsecureSsl": False}):
            result = await _clone_workflows_for_connection(
                platform, f"conn_{platform}", "Work", cred_id,
            )
        return result, {wf["name"]: wf for wf in posted}

    @staticmethod
    def _creds(wf):
        return {n["name"]: (n.get("credentials") or {}) for n in wf["nodes"]}

    @pytest.mark.asyncio
    async def test_bitbucket_server_clone_keeps_link_and_platform_apart(self, db, tmp_path):
        from laya.security.n8n_link import LINK_CRED_NAME

        (activated, errors), wfs = await self._clone(db, tmp_path, "bitbucket_server", "cred_bbs")
        assert errors == [] and activated == 2
        link_ref = {"id": "cred_link_123", "name": LINK_CRED_NAME}

        ingestion = self._creds(wfs["Laya Bitbucket Server - Work (Ingestion)"])
        assert ingestion["POST to Laya Engine"]["httpHeaderAuth"] == link_ref
        assert ingestion["Get Pull Requests"]["httpHeaderAuth"] == {"id": "cred_bbs", "name": "Work"}

        executor_wf = wfs["Laya Bitbucket Server - Work (Executor)"]
        executor = self._creds(executor_wf)
        assert executor["Webhook"]["httpHeaderAuth"] == link_ref
        assert executor["Merge PR"]["httpHeaderAuth"] == {"id": "cred_bbs", "name": "Work"}
        webhook = next(n for n in executor_wf["nodes"] if n["name"] == "Webhook")
        assert webhook["parameters"]["path"].startswith("bitbucket-server-executor-")

    @pytest.mark.asyncio
    async def test_github_clone_binds_link_nodes(self, db, tmp_path):
        from laya.security.n8n_link import LINK_CRED_NAME

        (activated, errors), wfs = await self._clone(db, tmp_path, "github", "cred_gh")
        assert errors == [] and activated == 2
        link_ref = {"id": "cred_link_123", "name": LINK_CRED_NAME}

        ingestion = self._creds(wfs["Laya GitHub - Work (Ingestion)"])
        assert ingestion["POST to Laya Engine"]["httpHeaderAuth"] == link_ref
        assert ingestion["POST Repo Errors"]["httpHeaderAuth"] == link_ref
        assert ingestion["Get Issues and PRs"]["githubApi"]["id"] == "cred_gh"
        executor = self._creds(wfs["Laya GitHub - Work (Executor)"])
        assert executor["Webhook"]["httpHeaderAuth"] == link_ref
        assert executor["Close Issue"]["githubApi"]["id"] == "cred_gh"

    @pytest.mark.asyncio
    async def test_clone_aborts_without_link_credential(self, db, tmp_path):
        (activated, errors), wfs = await self._clone(db, tmp_path, "github", "cred_gh", link_id=None)
        assert activated == 0
        assert wfs == {}
        assert any("engine-link credential" in e for e in errors)
