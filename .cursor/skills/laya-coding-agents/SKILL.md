---
name: laya-coding-agents
description: Guia para os adaptadores de agentes CLI do Laya (Claude Code, Codex, Gemini, Pi, Cursor Agent) no workspace/research e como backends de inferência (agent/<id>/<model>), incluindo sandbox, modos de permissão, sessão, budget por janela e riscos de segurança. Use ao alterar engine/laya/agents, llm/agent_backend.py, workspace de cards, research, ou adicionar um novo agente.
---

# Agentes CLI

## Dois usos distintos

| Uso | Onde | Isolamento |
|---|---|---|
| Workspace / research de card | `agents/<agente>.py` + `session_manager.py`, API `api/cards_agent.py`, `api/workspace_api.py` | Modos do próprio agente (plan/acceptEdits/sandbox); repo do usuário; research em `~/.laya/tmp/research` |
| Backend de inferência | `llm/agent_backend.py` via `llm_call(model="agent/<id>/<model>")` | cwd `mkdtemp` vazio, ferramentas negadas, sem MCP, semáforo `agent_backend_concurrency`=3 |

Tiers de inferência: `claude_code` = **native** (`--json-schema`, `structured_output`); `codex_cli`, `gemini_cli`, `pi_cli` = **best-effort** (schema em texto, `raw_decode` + `jsonschema`, retry ×3 com erro). Cursor **não** é backend de inferência.

## Protocolo (`agents/base.py`)

`start_session(session_id, prompt, repo_path, add_dirs, mode, research, space_id)`, `resume_with_answer`, `stream_events`, `send_input`, `pause`, `resume`, `cancel`, `get_status`. Estenda `BaseCodingAgent` (ciclo de vida comum; exit 143/-15 = cancelado). Processos via `subprocess_helper.AgentProcess`: `create_subprocess_exec` (sem shell), `stdin=DEVNULL`, linha até 10 MB, stderr 200 linhas, inatividade 300 s, pausa SIGSTOP/SIGCONT, término SIGTERM→SIGKILL 5 s.

## Adicionar um agente

```
- [ ] AgentType em models/workspace.py
- [ ] agents/<id>.py estendendo BaseCodingAgent (argv por modo, parsing de stream → WorkspaceEventType)
- [ ] Detecção do binário em config.detect_agent_paths() (valide identidade se o nome for genérico, como o Cursor faz)
- [ ] (Opcional) backend de inferência: AGENT_TIERS + _build_args em llm/agent_backend.py com ferramentas negadas
- [ ] (Opcional) budget: settings.agent_budgets.agents[<id>]
- [ ] UI: CODING_AGENTS / AGENT_BINARY_NAMES em ui/src/lib/config.ts, settings/AgentConfig.svelte
- [ ] Testes de argv/parsing puros (padrão tests/test_cursor_cli_adapter.py, tests/test_agent_backend.py) — sem spawn real
```

## Regras de segurança (não regredir)

- Inferência: nunca habilite ferramentas, MCP ou cwd com dados.
- MCP para agentes de workspace: config em arquivo temporário 0600 (`mcp_config.py`), `--allowedTools` limitado aos escopos.
- Cursor: nunca passar `--model` (persiste como default do usuário); plan/ask read-only; `force` roda shell.
- Não amplie modos (ex.: `--full-auto`, `auto_edit`, `WebFetch` sem domínio) sem aprovação — já são lacunas (SEC-09, SEC-12).
- Não coloque segredos no argv; o ambiente herdado hoje inclui chaves de LLM (SEC-05) — ao mexer, prefira env filtrado.

## Budget por janela (`pipeline/agent_budget.py`)

`window_token_limit`, `window_hours` (5), `pause_at_percent` (85). Sinal nativo do Claude (`rate_limit_info`) é autoritativo. Ao estourar, pausa ingestão até `paused_until`; scheduler tenta retomar a cada 60 s; broadcast `agent_budget_status`.

## Validar

```bash
cd engine && pytest tests/test_agent_backend.py tests/test_claude_code_adapter.py tests/test_cursor_cli_adapter.py \
  tests/test_session_manager.py tests/test_agent_budget.py tests/test_agent_mcp_wiring.py -v
```
