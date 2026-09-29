# Stack

## Engine (Python)
- `engine/requirements.txt` (core, faixas), `requirements-ml.txt` (torch + sentence-transformers, opcional), `requirements-dev.txt` (core + `pytest>=8`, `pytest-asyncio>=1`).
- Instalação **sempre pelos locks** (`*.lock`, hashes, universais 3.10–3.14). Após editar um `.txt`: `scripts/lock-deps.sh` → `scripts/check-locks.sh` → `scripts/smoke-install.sh`.
- Principais: FastAPI, uvicorn, aiosqlite, httpx, LiteLLM, tenacity, ChromaDB (ONNX embutido; modelo padrão nomic-embed-text-v1.5, 768d), keyring, mcp SDK, jsonschema.

## UI
- `ui/package.json`: Svelte ^5.55, SvelteKit ^2.61, Vite ^7, Tailwind ^4.3 (`@tailwindcss/vite`), `@skeletonlabs/skeleton` ^4.12 (só CSS base + tema `cerberus`; `skeleton-svelte` instalado mas não usado), `marked` + `dompurify`, `@tauri-apps/api` + plugins os/process/shell/updater, Vitest ^4, svelte-check ^4.
- Fontes auto-hospedadas: `ui/static/fonts/InterVariable.woff2`, `GeistMono-Variable.woff2`. Sem biblioteca de ícones (SVG inline estilo Heroicons).

## Shell
- `ui/src-tauri/Cargo.toml`: Tauri v2, tokio, reqwest **rustls-only** (se aparecer `-lssl`, algum crate puxou `native-tls`). `uv` fixado em `runtime.rs` (precisa bater com `UV_VERSION` do CI).

## n8n
- `n8n@2.15.0` instalado em `~/.laya/n8n_module` (npm com `--allow-remote=all`, por causa do tarball do `xlsx`). Dados e credenciais cifradas em `~/.laya/n8n/`.

## Configuração do usuário (`~/.laya/`)
| Arquivo | Conteúdo |
|---|---|
| `settings.json` | modelos por papel, pipeline, smart_grouping, tuning, omni, briefing, retention, mcp, agent_budgets, agent_paths, custom_providers, logging |
| `team.json` | membros (um com `role=self`) |
| `rules.json` | regras de filtro `allow`/`drop` |
| `repos.json` | repositórios locais e metadados (`host` para on-prem) |
| `prompts/*.md` | overrides de prompt (o engine nunca escreve aqui) |

`load_settings()` tem cache por mtime, merge profundo de 2 níveis com `DEFAULT_SETTINGS` (`engine/laya/config.py`) e devolve cópia profunda. Parâmetros ajustáveis: `docs/tuning-parameters.md`.

## Variáveis de ambiente
`LAYA_ENGINE_HOST`, `LAYA_ENGINE_PORT` (8420), `N8N_URL`, `LAYA_ENGINE_URL` (lido pelos workflows), `LAYA_LOG_LEVEL`, `LAYA_PARENT_PID` (watchdog). Chaves de LLM ficam no keychain e são exportadas para `os.environ` na inicialização (`security/keychain.py`).

## Segredos
Keychain do SO: serviço `laya-engine` (chaves de provedor, por space, token MCP `laya_mcp_bearer`), `laya-egress` (`{platform}:{connection_id}`, `oauth:{platform}:client`, `smtp:{connection_id}`), `n8n_admin`. Detalhes e lacunas: `security.md`.

## Dados
| Store | Local |
|---|---|
| SQLite | `~/.laya/data/laya.db` (72 migrations em `engine/laya/db/migrations/`, FTS5 `cards_fts`/`events_fts`) |
| ChromaDB | `~/.laya/data/chromadb` (coleção `laya_memory`; trocar modelo de embedding exige recriar) |
| Logs | `~/.laya/logs/engine.log` (10 MB × 5), `engine-stdout.log` e `n8n.log` (10 MB × 3) |
| Tmp agentes | `~/.laya/tmp/research`, `~/.laya/tmp/agent-staging` (limpeza > 24 h) |

Esquema: `docs/database-schema.md`. Contratos: `docs/api-contracts.md`, `docs/event-schema.md`.
