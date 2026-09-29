# Testes

<!-- harness:testing-policy:start -->
## SDD-AI — test execution defaults

These rules align with **`METHODOLOGY-CONTRACT.md` §3–§3.1** shipped with SDD-AI (`harness-prereqs` in your skills install). **Concrete baseline and narrowed commands for this repo** belong in markdown **below** this marked block (not between the `harness:testing-policy` markers) so `check-update` can refresh policy text without erasing your commands.

- **Only `/harness:test` runs the full suite** — and only the **affected component's** suite, once per cycle. Every other phase that runs tests (`/harness:apply`, `/harness:bug` fix, `/harness:verify` smoke) does **scoped runs** only — it narrows the runner to **packages/paths/modules touched by the change** (paths after `--`, `-p`/`-pl`, `-Dtest=…`, `pytest` paths, `go test ./…`, workspace filters, etc.). These phases derive the command via `harness sdd test-scope … --no-baseline-fallback`, which returns an **empty command on fallback** — so they **physically cannot** run the whole suite. On fallback they run only touched test files, else SKIP and defer to `/harness:test`.
- **`/harness:verify` never runs the full suite** — `/harness:test` is its mandatory prior step. If there is no test evidence, verify defers to `/harness:test` instead of running it.
- **Full suite** — Only `/harness:test` (component-bounded, once) or **CI / pre-merge**. Non-test phases never run it, even on unreliable scope (they SKIP). Full runs cost more CPU/RAM.
- **Tests to add or change** — Keep them **next to** the behavior under change (follow this repo’s layout). Do not run unrelated suites “to be safe”.
<!-- harness:testing-policy:end -->

## Repo-specific commands

### Engine — pytest (`engine/tests/`, 85 arquivos planos, ~1.100 testes)

Baseline (suíte completa):
```bash
cd engine && source .venv/bin/activate && pytest -m "not network"
```

Escopado (padrão):
```bash
pytest tests/test_cards_api.py                                   # um arquivo
pytest tests/test_cards_api.py::TestCardsAPI::test_get_cards_empty -v
pytest tests/test_router.py tests/test_stager_prompt.py -k batch  # filtro por nome
```

Mapa rápido módulo → testes (mesmo nome, prefixo `test_`): `pipeline/router.py` → `test_router.py`, `test_router_prompt.py`; `pipeline/stager.py` → `test_stager*.py`; `egress/platforms/*` → `test_egress_platforms.py`, `test_platform_interface.py`, `test_egress_registry_parity.py`, `test_terminal_event_parity.py`; `api/cards_*` → `test_cards_api.py`, `test_card_move.py`, `test_reprocess.py`; `pipeline/queue.py` → `test_queue_concurrency.py`, `test_batch_routing.py`, `test_dead_events.py`; `db/sqlite.transaction` → `test_db_transaction.py`; migrations/timestamps → `test_timestamp_canonical.py`, `test_fts.py`; `retrieval.py` → `test_retrieval.py`; `llm/tools/definitions.py` → `test_tool_gating.py`; `llm/agent_backend.py` → `test_agent_backend.py`; `integrations/n8n_bootstrap.py` → `test_n8n_bootstrap.py`. Na dúvida: `rg -l "<modulo>" engine/tests`.

Regras:
- Sem `pytest.ini`: pytest-asyncio em **modo strict** → todo teste async precisa `@pytest.mark.asyncio` (função ou classe); fixtures async usam `@pytest_asyncio.fixture`.
- Marker `network` para testes que baixam modelo de embedding.
- `conftest.py` isola `HOME` num tmpdir e instala um keyring em memória **antes** de qualquer `import laya` — nunca importe `laya` acima desse bloco.
- Fixture `db`: SQLite `:memory:` com todas as migrations + FTS5, patch em `laya.db.sqlite._db`, reset de caches de módulo.
- Mocks de LLM: `patch("laya.pipeline.<mod>.llm_call", new_callable=AsyncMock)` (preferido) ou `patch("litellm.acompletion")` com `_make_mock_llm_response(dict)` quando o teste precisa passar pelo `client.py`.
- API: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
- httpx/n8n: substituir `httpx.AsyncClient` no módulo por `AsyncMock` com `__aenter__/__aexit__` (não há `respx`).
- Broadcast WS: `patch("<mod>.manager.broadcast")`.
- Helpers: `from tests.conftest import insert_test_event, insert_test_card`.
- Arquivos novos começam com `# SPDX-License-Identifier: Apache-2.0`.

### UI — vitest (`ui/src/**/*.test.ts`, ambiente node, só lógica pura)

Baseline:
```bash
cd ui && npm test && npm run check
```

Escopado:
```bash
cd ui && npx vitest run src/lib/feed/cardUpdateReducer.test.ts
cd ui && npx vitest run src/lib/timeline
```

Regras: extraia lógica de componentes para módulos puros em `lib/{feed,timeline,omni,utils,stores}` e teste lá (não há Testing Library/Playwright nem DOM). Mudança visual exige teste manual nos temas **dark e light**, com e sem **glass**, e com **paleta acessível**.

### Rust
```bash
cd ui/src-tauri && cargo check
```

### Guardrails (sempre, é barato)
```bash
scripts/guardrails-check.sh            # checa só o necessário, ~1 s
```

### CI
- `.github/workflows/guardrails.yml`: guardrails + pytest (`-m "not network"`) + vitest + svelte-check em PR.
- `.github/workflows/engine-deps.yml`: locks + smoke install (matriz SO × Python) — só quando deps mudam ou semanalmente.
