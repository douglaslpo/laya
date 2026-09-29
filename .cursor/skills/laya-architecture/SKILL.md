---
name: laya-architecture
description: Mapa mental do Laya (Tauri + SvelteKit + FastAPI + n8n) — onde cada responsabilidade vive, fluxo evento→card→ação, e qual skill/spec consultar em seguida. Use ao iniciar qualquer tarefa no repositório Laya, ao investigar um bug sem saber a camada, ou quando o usuário perguntar como o Laya funciona.
---

# Laya — arquitetura

## Fluxo em uma linha

Fonte → **n8n ingestion** → `POST /events` → fila (`pipeline/queue.py`) → ingest → space → rules → **router** → workers (se `requires_research`) → **stager** → **emit** (card + broadcast WS) → UI → usuário aprova → `executor.py` → **egress** (n8n executor / SMTP) → plataforma.

## Onde procurar

| Pergunta | Arquivo(s) |
|---|---|
| Por que o evento não virou card? | `api/events.py`, `pipeline/queue.py` (`process_event`, `_mark_failed`), `pipeline/rules.py`, tabela `events.processing_status`, `/events/dead`, `/events/filtered` |
| Classificação errada | `pipeline/router.py`, `llm/prompts/router.py`, `pipeline/learn.py`, `classification_rules` |
| Texto/ação sugerida ruim | `pipeline/stager.py`, `llm/prompts/stager.py`, `workers/persona.py` |
| Card agrupado errado | `pipeline/context_grouping.py`, `context_presets.py`, `context_learn.py`, `emit._resolve_context_grouping` |
| Status travado | `models/card_lifecycle.py`, `queue.recover_stalled_cards`, `api/cards_lifecycle.py` |
| Ação não enviada | `pipeline/executor.py`, `egress/router.py`, `egress/backends/n8n.py`, `n8n/workflows/*-executor.json`, `action_log` |
| Busca/chat | `laya/retrieval.py`, `pipeline/chat.py`, `llm/tools/`, `db/fts.py`, `db/chromadb_store.py` |
| Omni | `pipeline/omni.py`, `omni_change.py`, `api/omni_api.py`, `ui/src/routes/omni`, `ui/src/lib/omni` |
| Agentes / workspace | `agents/*`, `api/cards_agent.py`, `api/workspace_api.py`, `llm/agent_backend.py` |
| Custo / pausa | `pipeline/budget.py`, `pipeline/agent_budget.py`, `api/budget_api.py` |
| Processo não sobe | `ui/src-tauri/src/sidecar.rs`, `n8n.rs`, `engine/laya/main.py` (startup), `~/.laya/logs/` |
| Visual / tema | `ui/src/app.css`, `ui/src/routes/+layout.svelte`, `ui/src/lib/stores/{theme,glassTheme,…}.ts` |

Caminhos do engine são relativos a `engine/laya/`.

## Conceitos que confundem

- **Space**: contexto do usuário que agrupa fontes; `space_id` atravessa todo o pipeline; default `'default'`. Modelos podem ser sobrescritos por space.
- **Context group** (agrupamento semântico entre plataformas) ≠ **entity group** (mesmo `entity_id`, carry-forward) ≠ **tags**.
- **Classification rules** (persona/prioridade, aprendidas de correções) ≠ **context rules** (diretivas de agrupamento) ≠ **filter rules** (`rules.json`, allow/drop) ≠ **processing rules** (automação sobre cards com firing log).
- **Engineer worker** não roda agente: gera `agent_prompt`; o agente roda no **workspace** quando o usuário pede.
- **Agente como backend de inferência** (`agent/<id>/<model>`) ≠ **agente de workspace**.
- `failed` é inativo mas **não** terminal (pode ser re-tentado).

## Próximos passos

- Pipeline/LLM → skill `laya-pipeline`
- Nova plataforma/ação externa → skill `laya-egress-platform`
- Schema/migration → skill `laya-db-migrations`
- UI → skill `laya-ui-design-system`
- Agentes CLI → skill `laya-coding-agents`
- Workflows n8n → skill `laya-n8n-workflows`
- Testes → skill `laya-testing`
- Contratos de comportamento → `harness-sdd/specs/<capacidade>/spec.md`
- Design completo → `docs/sdd/SDD.md`; invariantes → `docs/guardrails.md`
