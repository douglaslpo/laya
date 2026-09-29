# Resumo

Laya intercepta eventos (Jira, Slack, Gmail, GitHub, Bitbucket Cloud/Server, Linear, Notion, Google Calendar, Outlook e-mail/calendário) via n8n, classifica com personas LLM (Engineer, Comms, Ops, Sales, HR, Finance), prepara ações e mostra **Action Cards** que o usuário aprova, edita ou descarta. Ações aprovadas saem pelo egress (n8n ou SMTP).

| Item | Valor |
|---|---|
| Linguagens | Python 3.10–3.14 (engine), TypeScript/Svelte 5 (UI), Rust (shell Tauri v2), JSON (workflows n8n) |
| Frameworks | FastAPI + asyncio + aiosqlite + LiteLLM; SvelteKit (SPA, adapter-static) + Skeleton v4 + Tailwind v4; Tauri v2 |
| Storage | SQLite WAL + FTS5 (`~/.laya/data/laya.db`), ChromaDB embarcado (`~/.laya/data/chromadb`), keychain do SO |
| Testes | `pytest` + `pytest-asyncio` (modo strict) no engine; `vitest` (ambiente node, só lógica pura) na UI; `svelte-check` para tipos |
| Deps | pip/uv com locks gerados (`engine/requirements*.lock`), npm (`ui/package-lock.json`), cargo |
| Portas | Engine 8420 · Vite 5173 · n8n 45678 (todas em loopback) |

## Comandos que importam

```bash
scripts/setup-dev.sh                                   # setup único
scripts/dev.sh                                         # Tauri dev (sobe engine + n8n)
cd engine && source .venv/bin/activate && pytest       # testes engine
cd ui && npm test && npm run check                     # testes + tipos UI
scripts/guardrails-check.sh                            # guardrails automáticos
```

## Always
- Rodar os testes escopados ao que mudou (ver `testing.md`) e `scripts/guardrails-check.sh` antes de concluir.
- Mudar status de card só via `transition_card_status` (`engine/laya/models/card_lifecycle.py`).
- Nova migration = próximo número sequencial (hoje: **073**), sem `BEGIN/COMMIT`/triggers no arquivo.
- Bump de `meta.laya_version` em todo workflow de `n8n/workflows/` alterado.
- Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) e tokens do Design System.

## Never
- `$:` reativo, `export let` ou `on:click` na UI.
- `asyncio.create_task` direto em código de app (use `laya.tasks.create_task`) — exceções são os loops de vida longa já listados em `scripts/guardrails-check.sh`.
- Timestamps com `isoformat()` no banco (use `db/timeutil.db_now`/`db_ts`).
- Enviar ação externa (egress) sem confirmação humana, ou retentar egress após timeout.
- Reimplementar stopwords, RRF ou fallback FTS→LIKE fora de `laya/retrieval.py`.

## Ask (pedir confirmação antes)
- Alterar o contrato `LayaEvent`, o schema de `action_cards` ou o grafo de transições de status.
- Mudar escopos MCP padrão, capabilities do Tauri, CSP ou modos de permissão dos agentes CLI.
- Adicionar dependência Python (exige `scripts/lock-deps.sh` + `check-locks.sh`).
- Alterar prompts de router/stager que mudam custo de tokens em janelas locais pequenas.
- Tocar em fluxos que já são "não mexer" no plano de remediação (fila durável, sync de workflows, FLIP do feed).
