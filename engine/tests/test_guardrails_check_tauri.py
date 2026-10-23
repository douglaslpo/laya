# Copyright 2026 Aayush Chawla
# SPDX-License-Identifier: Apache-2.0

"""SEC-02 CA-01 / CR-01 / CR-02: scripts/guardrails_check.py Tauri rules.

The script is loaded via importlib (it is not a package) and pointed at a
temporary ROOT so regressions can be simulated without touching the repo.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "guardrails_check.py"

GOOD_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:8420 ws://127.0.0.1:8420; "
    "object-src 'none'"
)


@pytest.fixture
def gc(monkeypatch):
    spec = importlib.util.spec_from_file_location("guardrails_check_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_tauri(root: Path, csp, dev_csp=GOOD_CSP, permissions=None, extra=None) -> None:
    tauri = root / "ui" / "src-tauri"
    (tauri / "capabilities").mkdir(parents=True)
    security = dict(extra or {})
    if csp is not ...:
        security["csp"] = csp
    if dev_csp is not ...:
        security["devCsp"] = dev_csp
    (tauri / "tauri.conf.json").write_text(json.dumps({"app": {"security": security}}))
    (tauri / "capabilities" / "default.json").write_text(
        json.dumps({"permissions": permissions if permissions is not None else ["shell:allow-open"]})
    )


def _run_tauri(gc, monkeypatch, tmp_path) -> list[str]:
    monkeypatch.setattr(gc, "ROOT", tmp_path)
    gc.errors.clear()
    gc.warnings.clear()
    gc.check_tauri()
    return list(gc.errors)


def test_repo_tauri_config_passes(gc):
    """CA-01: the committed tauri.conf.json / capabilities raise no Tauri error."""
    gc.errors.clear()
    gc.check_tauri()
    assert [e for e in gc.errors if e.startswith("[tauri]")] == []


def test_repo_csp_is_restrictive(gc):
    conf = json.loads((REPO_ROOT / "ui" / "src-tauri" / "tauri.conf.json").read_text())
    csp = gc.csp_directives(conf["app"]["security"]["csp"])
    assert csp["default-src"] == ["'self'"]
    assert csp["object-src"] == ["'none'"]
    assert "'unsafe-eval'" not in csp.get("script-src", [])
    for src in csp["connect-src"]:
        assert src in ("'self'", "ipc:") or "localhost" in src or "127.0.0.1" in src


def test_repo_capabilities_have_no_unscoped_shell(gc):
    perms = json.loads(
        (REPO_ROOT / "ui" / "src-tauri" / "capabilities" / "default.json").read_text()
    )["permissions"]
    assert not {p for p in perms if isinstance(p, str)} & gc.SHELL_UNSCOPED


def test_good_config_has_no_errors(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, GOOD_CSP)
    assert _run_tauri(gc, monkeypatch, tmp_path) == []


@pytest.mark.parametrize("csp", [None, "", "   ", ...])
def test_null_or_missing_csp_is_error(gc, monkeypatch, tmp_path, csp):
    _write_tauri(tmp_path, csp)
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("app.security.csp nula/ausente" in e for e in errors)


def test_null_dev_csp_is_error(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, GOOD_CSP, dev_csp=None)
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("app.security.devCsp nula/ausente" in e for e in errors)


def test_missing_default_src_is_error(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, "script-src 'self'; connect-src 'self'")
    assert any("sem default-src" in e for e in _run_tauri(gc, monkeypatch, tmp_path))


def test_unsafe_eval_is_error(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, GOOD_CSP.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"))
    assert any("'unsafe-eval' em script-src" in e for e in _run_tauri(gc, monkeypatch, tmp_path))


def test_unsafe_eval_via_default_src_fallback_is_error(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, "default-src 'self' 'unsafe-eval'")
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("'unsafe-eval' em script-src" in e for e in errors)


@pytest.mark.parametrize("directive", ["script-src", "connect-src"])
@pytest.mark.parametrize("wildcard", ["*", "*.example.com"])
def test_wildcard_is_error(gc, monkeypatch, tmp_path, directive, wildcard):
    _write_tauri(tmp_path, f"default-src 'self'; {directive} 'self' {wildcard}")
    assert any(f"curinga em {directive}" in e for e in _run_tauri(gc, monkeypatch, tmp_path))


@pytest.mark.parametrize("scheme", ["https:", "ws:"])
def test_bare_scheme_in_connect_src_is_error(gc, monkeypatch, tmp_path, scheme):
    _write_tauri(tmp_path, f"default-src 'self'; connect-src 'self' {scheme}")
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("esquema sem host em connect-src" in e for e in errors)


def test_ipc_scheme_is_allowed(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, "default-src 'self'; connect-src 'self' ipc:")
    assert _run_tauri(gc, monkeypatch, tmp_path) == []


@pytest.mark.parametrize(
    "perm", ["shell:allow-execute", "shell:allow-spawn", "shell:allow-stdin-write"]
)
def test_unscoped_shell_permission_is_error(gc, monkeypatch, tmp_path, perm):
    _write_tauri(tmp_path, GOOD_CSP, permissions=["shell:allow-open", perm])
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("shell sem escopo" in e and perm in e for e in errors)


def test_scoped_shell_permission_object_is_allowed(gc, monkeypatch, tmp_path):
    scoped = {"identifier": "shell:allow-execute", "allow": [{"name": "x", "cmd": "x"}]}
    _write_tauri(tmp_path, GOOD_CSP, permissions=["shell:allow-open", scoped])
    assert _run_tauri(gc, monkeypatch, tmp_path) == []


def test_disable_csp_modification_for_style_src_is_allowed(gc, monkeypatch, tmp_path):
    _write_tauri(tmp_path, GOOD_CSP, extra={"dangerousDisableAssetCspModification": ["style-src"]})
    assert _run_tauri(gc, monkeypatch, tmp_path) == []


@pytest.mark.parametrize("value", [True, ["script-src"], ["style-src", "script-src"]])
def test_disable_csp_modification_for_script_src_is_error(gc, monkeypatch, tmp_path, value):
    _write_tauri(tmp_path, GOOD_CSP, extra={"dangerousDisableAssetCspModification": value})
    errors = _run_tauri(gc, monkeypatch, tmp_path)
    assert any("dangerousDisableAssetCspModification" in e for e in errors)


def test_main_exits_nonzero_on_tauri_error(gc, monkeypatch, tmp_path, capsys):
    """CR-01/CR-02: an ERROR makes main() return a non-zero exit code."""
    _write_tauri(tmp_path, None, permissions=["shell:allow-execute"])
    (tmp_path / "engine" / "laya" / "db" / "migrations").mkdir(parents=True)
    monkeypatch.setattr(gc, "ROOT", tmp_path)
    monkeypatch.setattr(gc, "MIGRATIONS", tmp_path / "engine" / "laya" / "db" / "migrations")
    for name in ("check_migrations", "check_svelte", "check_n8n", "check_engine"):
        monkeypatch.setattr(gc, name, lambda: None)
    gc.errors.clear()
    gc.warnings.clear()
    assert gc.main() == 1
    out = capsys.readouterr().out
    assert "ERROR [tauri]" in out
