# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""SEC-03 CA-03 — bundled n8n workflows carry the engine-link authentication."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from laya.security.n8n_link import (
    LINK_CRED_NAME,
    LINK_CRED_PLACEHOLDER_ID,
    LINK_CRED_TYPE,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / "n8n" / "workflows"
ENGINE_ROUTES = ("/events", "/ingestion-errors")
LINK_REF = {"id": LINK_CRED_PLACEHOLDER_ID, "name": LINK_CRED_NAME}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.json"))


def _is_engine_post(node: dict) -> bool:
    params = node.get("parameters") or {}
    url = str(params.get("url", "")).strip()
    return (
        node.get("type") == "n8n-nodes-base.httpRequest"
        and params.get("method") == "POST"
        and "LAYA_ENGINE_URL" in url
        and url.endswith(ENGINE_ROUTES)
    )


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_engine_posts_use_link_credential(path):
    data = _load(path)
    posts = [n for n in data["nodes"] if _is_engine_post(n)]
    if path.name.endswith("-ingestion.json") or path.name == "laya-error-handler.json":
        assert posts, f"{path.name}: expected a POST to the engine"
    for node in posts:
        params = node["parameters"]
        assert params.get("authentication") == "genericCredentialType", node["name"]
        assert params.get("genericAuthType") == LINK_CRED_TYPE, node["name"]
        assert (node.get("credentials") or {}).get(LINK_CRED_TYPE) == LINK_REF, node["name"]


@pytest.mark.parametrize(
    "path",
    [p for p in _workflow_files() if p.name.endswith("-executor.json")],
    ids=lambda p: p.name,
)
def test_executor_webhooks_use_header_auth(path):
    data = _load(path)
    webhooks = [
        n for n in data["nodes"]
        if n.get("type") == "n8n-nodes-base.webhook" and (n.get("parameters") or {}).get("httpMethod")
    ]
    assert webhooks, f"{path.name}: executor without webhook"
    for node in webhooks:
        assert node["parameters"].get("authentication") == "headerAuth", node["name"]
        assert (node.get("credentials") or {}).get(LINK_CRED_TYPE) == LINK_REF, node["name"]


def test_expected_workflow_counts():
    names = [p.name for p in _workflow_files()]
    assert sum(n.endswith("-ingestion.json") for n in names) == 11
    assert sum(n.endswith("-executor.json") for n in names) == 11
    assert "laya-error-handler.json" in names


def _base_ref() -> str | None:
    base = os.environ.get("GUARDRAILS_BASE_REF", "develop")
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", base],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return base


def test_changed_workflows_bump_version():
    base = _base_ref()
    if base is None:
        pytest.skip("base ref not available")
    for path in _workflow_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            old_raw = subprocess.run(
                ["git", "show", f"{base}:{rel}"],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            ).stdout
        except subprocess.CalledProcessError:
            continue  # new file
        old = json.loads(old_raw)
        new = _load(path)
        if old == new:
            continue
        old_v = (old.get("meta") or {}).get("laya_version")
        new_v = (new.get("meta") or {}).get("laya_version")
        assert _version_tuple(new_v) > _version_tuple(old_v), f"{rel}: {old_v} -> {new_v}"
