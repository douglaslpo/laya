# Comandos

## Desenvolvimento
| Comando | O que faz |
|---|---|
| `scripts/setup-dev.sh` | Verifica python3/node/npm/cargo, cria `engine/.venv` (`pip install --require-hashes -r requirements-dev.lock`), `npm install` em `ui`, instala n8n em `~/.laya/n8n_module`, cria `~/.laya/{data,logs}` |
| `scripts/dev.sh` | `npx @tauri-apps/cli dev` (Vite 5173 + janela Tauri, que sobe engine e n8n); trap mata 8420/45678 ao sair |
| `cd engine && source .venv/bin/activate && python -m laya.main` | Engine standalone (backend-only) |
| `cd ui && npm run dev` | Só frontend, sem shell Tauri |
| `curl -X POST http://127.0.0.1:8420/prompts/reload` | Recarrega overrides de `~/.laya/prompts/` |

## Qualidade
| Comando | O que faz |
|---|---|
| `scripts/guardrails-check.sh` | Checagens automáticas de invariantes (migrations, runes, n8n version, status, tasks, retrieval) |
| `cd engine && pytest -m "not network"` | Suíte do engine |
| `cd ui && npm test` / `npm run check` | Vitest / svelte-check |
| `cd ui/src-tauri && cargo check` | Compilação do shell |

## Dependências Python
| Comando | O que faz |
|---|---|
| `scripts/lock-deps.sh [--upgrade-package X]` | `uv pip compile --universal --python-version 3.10 --generate-hashes --no-build` |
| `scripts/check-locks.sh -v` | Wheels disponíveis em 5 alvos × Python 3.10–3.14 (inclui `EXPECTED_UNAVAILABLE`) |
| `scripts/smoke-install.sh [--python X] [--ml] [--source ranges]` | Venv descartável → instala como o `sidecar.rs` → import → embedding → pytest |

## Build e release
| Comando | O que faz |
|---|---|
| `scripts/build.sh [--target T] [--universal] [--sign ID] [--skip-engine]` | `bundle-engine.sh` + `npx tauri build` |
| `scripts/bundle-engine.sh` | Copia `engine/laya`, requirements + locks (sem dev) e `n8n/workflows` para `ui/src-tauri/resources/engine/`; remove `__pycache__` |
| tag `v*` | `release.yml`: matriz macOS arm/x64, Linux x64, Windows; release em rascunho assinado |

## CI
- `guardrails.yml` — PRs e push: guardrails, pytest, vitest, svelte-check.
- `engine-deps.yml` — locks + smoke (paths de deps, cron segunda 06:00, manual).
- `release.yml` — tags `v*`.
- `pages.yml` — deploy de `landing/`.

## Convenções de contribuição
Branches `feat/`, `fix/`, `docs/`; commits no imperativo (≤ 72 chars); checklist do `.github/PULL_REQUEST_TEMPLATE.md`. Base de SDD configurada no harness: `develop` (ver `harness sdd config`).
