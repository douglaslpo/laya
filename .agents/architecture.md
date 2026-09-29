# Arquitetura

```
Fontes (Jira, Slack, Gmail…) → n8n :45678 (ingestion workflows) → POST /events → Engine :8420
                                                                       │
                                  SQLite+FTS5 / ChromaDB (~/.laya/data) ┤
                                                                       ▼
                               UI SvelteKit (Tauri webview, REST + WS /ws)
                                                                       │ aprovação
                                                                       ▼
                                   Egress → n8n executor webhook | SMTP → plataforma
```

Detalhe completo: [docs/sdd/SDD.md](../docs/sdd/SDD.md). Diagramas Mermaid: `engine/docs/pipeline-lifecycle.md`.

## Camadas

| Camada | Local | Responsabilidade |
|---|---|---|
| Shell Tauri | `ui/src-tauri/src/` | Ciclo de vida do engine (`sidecar.rs`: venv `~/.laya/venv`, spawn, kill por process group) e do n8n (`n8n.rs`), tray, logs rotativos (`rotating_log.rs`), comandos nativos (`lib.rs`). |
| UI | `ui/src/` | SPA SvelteKit. Rotas: `feed` (Pulse), `omni`, `coherence`, `dashboard`, `settings`, `workspace/[card_id]`, `setup`, `status`, `legal`. Cliente REST `lib/api/engine.ts`, WS `lib/stores/websocket.ts`. |
| Engine | `engine/laya/` | FastAPI async. `main.py` (startup, middlewares, routers, `/ws`), `pipeline/`, `api/`, `egress/`, `agents/`, `llm/`, `mcp/`, `db/`, `workers/`, `security/`. |
| n8n | `n8n/workflows/` | 11 workflows de ingestão + 11 executores + `laya-error-handler`. Clonados por conexão pelo engine. |

## Pipeline principal (`engine/laya/pipeline/queue.py`)

`POST /events` (202, `INSERT OR IGNORE`, status `queued`) → consumidor da fila (batch routing opcional, semáforo `max_concurrent_events`, reaper) → `process_event`:

1. `ingest.run_ingest` — relação do ator com `team.json`.
2. `space_resolution.resolve_space` — `connection_id` → space (fallback `default`).
3. `rules.run_rules` — regras `allow`/`drop` de `rules.json` (primeira que casa decide).
4. `router.run_router` — `RouterOutput` (category, persona, priority, confidence, requires_research…). Parse falho → `OPS/MEDIUM`, confidence 0.
5. `workers.run_workers` (só se `requires_research`) — `workers/persona.py` (`PERSONA_SPECS`) ou `workers/engineer.py` (gera `agent_prompt`, não spawna agente).
6. `stager.run_stager` — `ActionCardData` (header, summary, staged_output, suggested_actions, privacy_tier, tags, context_match).
7. `emit.run_emit` — persiste card, carry-forward de grupo, auto-resolve em evento terminal, embed + `thread_context`, broadcast, context grouping, entity resolution, audit, follow-ups (group summary, daily summary, processing rules).

Estados de evento: `queued → processing → completed | filtered | retrying → dead` (backoff `min(2**n, 300)` s, `max_retry_attempts`=3).

Pós-emit / paralelos: `omni.py` (fila `omni_queue` + ressíntese agendada), `processing_rules.py`, `group_summary.py`, `summarize.py`, `briefing.py`, `learn.py` / `context_learn.py` (+ `learn_common.py`), `budget.py`, `agent_budget.py`, `chat.py`, `executor.py`.

## Ciclo de vida do card (`models/card_lifecycle.py`)

`pending, ready, requires_approval, agent_running, awaiting_input, executing, done, failed, dismissed, archived`. Terminais (`resolved_at`): `done, dismissed, archived`. Inativos: + `failed` (re-tentável). Transição = check-and-set atômico (`UPDATE … WHERE status=?`) + broadcast `card_updated`. Ver spec `harness-sdd/specs/card-lifecycle/spec.md`.

## API

~27 routers registrados em `main.py`. Cards: `api/cards_api.py` agrega `cards_feed` → `cards_lifecycle` → `cards_readstate` → `cards_payload` → summary → `cards_agent` → `cards_groups` (**ordem importa**: `/cards/grouped` antes de `/cards/{card_id}`). Projeção canônica `CARD_SELECT_COLUMNS` em `cards_common.py`. WS `/ws`: entrada `approve_action`, `deny_action`, `user_input`, `session_control`, `execute_action`, `chat_message`; saída `card_created/updated/deleted`, `event_classified`, `chat_stream_*`, `trace_*`, `omni_updated`, `budget_status`, `audit_failure`, `settings_changed` etc.

## Egress (`engine/laya/egress/`)

Contrato `platforms/base.py::Platform` (obrigatórios: `name`, `capabilities`, `identifiers_from_event`, `normalize_payload`, `validate_payload`). `platforms/__init__.py` mantém `_REGISTRY` e `_DISPATCH`; `registry.py` é fachada. Backends: `backends/n8n.py` (resolve webhook por `connection_id` sem fallback silencioso de conta) e `backends/smtp.py`. Preview e execução compartilham `enrichment.py`. Chat usa `tools.py` + `tool_handlers.py` (token de confirmação de uso único, 5 min).

## Agentes (`engine/laya/agents/`, `llm/agent_backend.py`)

Workspace/research: adaptadores Claude Code, Codex, Gemini, Pi, Cursor sobre `BaseCodingAgent` + `AgentProcess` (sem shell, stdin DEVNULL, timeout de inatividade 300 s). Inferência: `llm_call(model="agent/<id>/<model>")` em cwd temporário vazio com ferramentas negadas; `claude_code` = tier native (`--json-schema`), demais best-effort (schema em texto + validação + retry ×3).

## LLM (`engine/laya/llm/`)

`client.py::llm_call` (LiteLLM, tenacity, sem retry em 4xx determinístico, clamp de `max_tokens`, resolução de modelo space → global). Prompts por papel em `llm/prompts/`, sobrescrevíveis em `~/.laya/prompts/*.md` (`POST /prompts/reload`). Blocos condicionais **gateados por plataforma/intenção** (`build_router_system_prompt`, `build_stager_system_prompt`, `select_chat_tools`).

## Busca híbrida

`laya/retrieval.py` (`extract_keywords`, `reciprocal_rank_fusion`, `fts_or_like`) combina ChromaDB (`laya_memory`) com BM25 FTS5 (`cards_fts`, `events_fts`, triggers em `db/fts.py`).

## MCP (`engine/laya/mcp/`)

Servidor HTTP/SSE + Streamable HTTP em `/mcp`, bearer `lyat_…` no keychain, escopos `read` (padrão on), `write` e `egress` (padrão off), space via query string.
