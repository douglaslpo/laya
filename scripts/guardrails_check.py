#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Automated guardrails for the Laya repository.

Each check encodes an invariant from docs/guardrails.md. ERROR fails the run,
WARN reports known debt without failing (so the baseline stays green while the
debt is visible). Stdlib only, so it runs before any venv exists.

Usage:
    scripts/guardrails-check.sh                 # all checks
    GUARDRAILS_BASE_REF=origin/develop scripts/guardrails-check.sh
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "laya"
MIGRATIONS = ENGINE / "db" / "migrations"
UI_SRC = ROOT / "ui" / "src"
WORKFLOWS = ROOT / "n8n" / "workflows"

errors: list[str] = []
warnings: list[str] = []


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def error(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def py_files() -> list[Path]:
    return [p for p in ENGINE.rglob("*.py") if "__pycache__" not in p.parts]


# ---------------------------------------------------------------- migrations
def check_migrations() -> None:
    files = sorted(MIGRATIONS.glob("*.sql"))
    numbers: dict[int, list[str]] = {}
    for f in files:
        m = re.match(r"^(\d{3})_[a-z0-9_]+\.sql$", f.name)
        if not m:
            error(f"[migrations] nome fora do padrão NNN_snake_case.sql: {rel(f)}")
            continue
        numbers.setdefault(int(m.group(1)), []).append(f.name)
        text = f.read_text(encoding="utf-8")
        # migrate.py wraps each file in BEGIN…COMMIT together with schema_version;
        # an inner BEGIN/COMMIT or a trigger body (which contains ';') breaks it.
        if re.search(r"^\s*(BEGIN|COMMIT)\b", text, re.I | re.M):
            error(f"[migrations] {rel(f)} contém BEGIN/COMMIT (o runner já envolve em transação)")
        if re.search(r"CREATE\s+TRIGGER", text, re.I):
            error(f"[migrations] {rel(f)} cria trigger (triggers vivem em db/fts.py)")
    for n, names in numbers.items():
        if len(names) > 1:
            error(f"[migrations] número duplicado {n:03d}: {', '.join(names)}")
    if numbers:
        expected = set(range(1, max(numbers) + 1))
        missing = sorted(expected - set(numbers))
        if missing:
            error(f"[migrations] buracos na numeração: {', '.join(f'{n:03d}' for n in missing)}")


# ------------------------------------------------------------------- svelte
SVELTE_LEGACY = [
    (re.compile(r"^\s*\$:\s"), "declaração reativa `$:` (use $derived/$effect)"),
    (re.compile(r"\bexport\s+let\s"), "`export let` (use $props())"),
    (re.compile(r"\son:[a-z]+[=|]"), "diretiva `on:evento` (use onevento={...})"),
]


def check_svelte() -> None:
    for f in UI_SRC.rglob("*.svelte"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for pat, why in SVELTE_LEGACY:
                if pat.search(line):
                    error(f"[svelte5] {rel(f)}:{i} {why}")


# ---------------------------------------------------------------------- n8n
def git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def workflow_version(data: dict) -> str | None:
    return (data.get("meta") or {}).get("laya_version")


def check_n8n() -> None:
    current: dict[str, str | None] = {}
    for f in sorted(WORKFLOWS.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            error(f"[n8n] JSON inválido em {rel(f)}: {exc}")
            continue
        v = workflow_version(data)
        if not v:
            error(f"[n8n] {rel(f)} sem meta.laya_version")
        elif not re.fullmatch(r"\d{4}\.\d{2}\.\d+", v):
            error(f"[n8n] {rel(f)} meta.laya_version fora do formato AAAA.MM.N: {v}")
        current[rel(f)] = v

    base = os.environ.get("GUARDRAILS_BASE_REF")
    if git("rev-parse", "--is-inside-work-tree") is None:
        return
    if not base:
        for candidate in ("origin/develop", "origin/main", "develop", "main"):
            if git("rev-parse", "--verify", "--quiet", candidate):
                base = candidate
                break
    if not base:
        return
    changed = git("diff", "--name-only", f"{base}...HEAD", "--", "n8n/workflows") or ""
    changed += git("diff", "--name-only", "HEAD", "--", "n8n/workflows") or ""
    for path in sorted(set(filter(None, changed.splitlines()))):
        old_raw = git("show", f"{base}:{path}")
        if old_raw is None or path not in current:
            continue
        try:
            old_v = workflow_version(json.loads(old_raw))
        except json.JSONDecodeError:
            continue
        if old_v == current[path]:
            error(
                f"[n8n] {path} mudou em relação a {base} mas meta.laya_version "
                f"continua {old_v} (a sync de clones só propaga quando a versão muda)"
            )


# ------------------------------------------------------------------- engine
# Long-lived loops and SDK-owned tasks that predate laya.tasks or must outlive
# its shutdown sweep. New entries need a comment in docs/guardrails.md (G-ENG-06).
CREATE_TASK_ALLOWLIST = {
    "tasks.py",
    "pipeline/queue.py",
    "scheduler.py",
    "egress/health.py",
    "agents/staging_cleanup.py",
    "agents/subprocess_helper.py",
    "mcp/http_server.py",
    "api/omni_api.py",
}

# Pipeline-owned writes allowed to bypass transition_card_status (G-ENG-03):
# provisional-card reset and startup bulk recovery in the queue (no clients are
# connected yet and a per-card CAS would be N round-trips), and the emit hot
# path _persist_card, which deliberately stays outside transaction()/CAS.
STATUS_WRITE_ALLOWED = {"models/card_lifecycle.py", "pipeline/queue.py", "pipeline/emit.py"}

# Known debt: user/agent-facing status writes that skip validation and CAS.
STATUS_WRITE_DEBT = {"api/cards_agent.py", "api/cards_lifecycle.py"}


def check_engine() -> None:
    # Multiline: most SQL lives in triple-quoted strings spanning several lines.
    status_re = re.compile(
        r"UPDATE\s+action_cards\s+SET\s+(?:(?!\bWHERE\b)[^;])*?(?<![\w.])status\s*=",
        re.I,
    )
    for f in py_files():
        r = str(f.relative_to(ENGINE))
        text = f.read_text(encoding="utf-8")
        lines = text.splitlines()

        if "asyncio.create_task(" in text and r not in CREATE_TASK_ALLOWLIST:
            for i, line in enumerate(lines, 1):
                if "asyncio.create_task(" in line:
                    error(f"[engine] {rel(f)}:{i} asyncio.create_task direto (use laya.tasks.create_task)")

        if r not in STATUS_WRITE_ALLOWED:
            for m in status_re.finditer(text):
                i = text.count("\n", 0, m.start()) + 1
                msg = f"[engine] {rel(f)}:{i} UPDATE de status fora de transition_card_status"
                (warn if r in STATUS_WRITE_DEBT else error)(msg)

        if r != "retrieval.py":
            for i, line in enumerate(lines, 1):
                if re.match(r"\s*(async\s+)?def\s+(reciprocal_rank_fusion|_?rrf|extract_keywords|fts_or_like)\b", line):
                    error(f"[engine] {rel(f)}:{i} reimplementa primitiva de retrieval (use laya/retrieval.py)")
                if r != "db/fts.py" and re.match(r"\s*_?STOPWORDS\s*[:=]", line):
                    error(f"[engine] {rel(f)}:{i} define STOPWORDS próprio (use laya.retrieval.STOPWORDS)")


# -------------------------------------------------------------------- tauri
CSP_STRICT_DIRECTIVES = ("script-src", "connect-src")
# A bare scheme source allows every host on that scheme, i.e. it is a wildcard.
# `ipc:` is not listed: it is Tauri's own IPC channel, not a network origin.
CSP_SCHEME_WILDCARDS = {
    "script-src": {"https:", "http:", "ws:", "wss:", "data:"},
    "connect-src": {"https:", "http:", "ws:", "wss:"},
}
SHELL_UNSCOPED = {"shell:allow-execute", "shell:allow-spawn", "shell:allow-stdin-write"}


def csp_directives(csp: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in csp.split(";"):
        tokens = part.split()
        if tokens:
            out[tokens[0].lower()] = tokens[1:]
    return out


def check_csp(key: str, csp: object) -> None:
    if not isinstance(csp, str) or not csp.strip():
        error(f"[tauri] app.security.{key} nula/ausente no webview (G-SEC-05)")
        return
    directives = csp_directives(csp)
    if "default-src" not in directives:
        error(f"[tauri] app.security.{key} sem default-src (G-SEC-05)")
    for name in CSP_STRICT_DIRECTIVES:
        # A missing directive falls back to default-src, so that is what gets enforced.
        sources = directives.get(name, directives.get("default-src", []))
        if "'unsafe-eval'" in sources:
            error(f"[tauri] app.security.{key} permite 'unsafe-eval' em {name} (G-SEC-05)")
        if any(s == "*" or s.startswith("*") for s in sources):
            error(f"[tauri] app.security.{key} usa curinga em {name} (G-SEC-05)")
        schemes = sorted(CSP_SCHEME_WILDCARDS[name] & {s.lower() for s in sources})
        if schemes:
            error(f"[tauri] app.security.{key} usa esquema sem host em {name}: "
                  f"{' '.join(schemes)} (G-SEC-05)")


def check_tauri() -> None:
    conf = ROOT / "ui" / "src-tauri" / "tauri.conf.json"
    if conf.exists():
        data = json.loads(conf.read_text(encoding="utf-8"))
        security = (data.get("app") or {}).get("security") or {}
        check_csp("csp", security.get("csp"))
        check_csp("devCsp", security.get("devCsp"))
        # Only style-src may opt out of Tauri's hash/nonce injection (CSP3 makes
        # injected hashes neutralize 'unsafe-inline'). Opting script-src out, or
        # everything via `true`, drops the protection for bundled scripts.
        disable = security.get("dangerousDisableAssetCspModification", False)
        if disable is True or (isinstance(disable, list) and "script-src" in disable):
            error("[tauri] app.security.dangerousDisableAssetCspModification desativa "
                  "a injeção de CSP em script-src (G-SEC-05)")
    cap_dir = ROOT / "ui" / "src-tauri" / "capabilities"
    for cap in sorted(cap_dir.glob("*.json")):
        perms = json.loads(cap.read_text(encoding="utf-8")).get("permissions", [])
        # Scoped entries are objects ({"identifier": ..., "allow": [...]}); only the
        # bare string form grants the plugin-wide default scope.
        loose = [p for p in perms if isinstance(p, str) and p in SHELL_UNSCOPED]
        if loose:
            error(f"[tauri] {rel(cap)} com permissões de shell sem escopo: {', '.join(loose)} (G-SEC-05)")


def main() -> int:
    for check in (check_migrations, check_svelte, check_n8n, check_engine, check_tauri):
        check()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    nxt = max((int(p.name[:3]) for p in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")), default=0) + 1
    print(
        f"\nguardrails: {len(errors)} erro(s), {len(warnings)} aviso(s). "
        f"Próxima migration: {nxt:03d}."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
