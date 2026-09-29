# tasks: imp-local-security-hardening

> Pré-requisito: aprovação explícita das mudanças de contrato listadas em `design.md` e resposta às questões em aberto do `proposal.md`.

## SEC-01 — confirmação humana de egress via MCP + token CSPRNG

- [ ] T-01: Criar `engine/laya/llm/tools/origin.py` (contextvar `tool_call_origin`, `current_origin()` fail-closed = `"mcp"`) e setar a origem em `mcp/http_server.py::call_tool` (`"mcp"`) e nas duas chamadas de `execute_tool` em `pipeline/chat.py` (`"chat"`), com set/reset em `finally` [S]
- [ ] T-02: Criar `engine/laya/egress/pending.py` (segredo `secrets.token_bytes(32)` por processo, token `egr_<nonce>.<sig>`, verificação `hmac.compare_digest` antes do lookup, TTL 300 s, uso único, vínculo de origem, `list_pending()` sanitizado) e remover `_TOKEN_SECRET`/`_generate_token`/`_pending_requests` de `tool_handlers.py` [M]
- [ ] T-03: Adaptar `tool_handlers.py`: `handle_egress_tool` ramifica por origem (MCP → pendência + broadcast `egress_confirmation_request` + resposta `awaiting_user_confirmation` sem token; chat → comportamento atual); `handle_confirm_egress` só para origem `chat`; extrair `execute_pending()` com `log_to_audit(source=...)` [M]
- [ ] T-04: `definitions.py` + `mcp/scope.py` + `mcp/http_server.py`: `chat_only_tool_names()` (`confirm_egress`) excluído sempre de `list_tools` e negado em `call_tool` via MCP com mensagem própria [S]
- [ ] T-05: Criar `engine/laya/api/egress_pending_api.py` (`GET /egress/pending`, `POST /egress/pending/{request_id}/confirm|reject`, checagem de `Origin` compartilhada com `mcp_api.py`, broadcast `egress_confirmation_resolved`) e registrar o router respeitando G-ENG-08 [M]
- [ ] T-06: UI: `ui/src/lib/egress/pendingConfirmations.ts` + vitest; tratar os dois tipos WS em `stores/websocket.ts` e recarregar `GET /egress/pending` ao reconectar [M]
- [ ] T-07: UI: `EgressConfirmModal.svelte` (Svelte 5 runes, tokens do Design System, acessível, validado em dark/light × glass × paleta acessível × reduced motion) montado em `routes/+layout.svelte` [M]
- [ ] T-08: Testes `engine/tests/test_egress_mcp_confirmation.py` cobrindo CA-01..CA-06 e CR-01..CR-06 de `specs/sec-01-egress-mcp-confirmation.md`; ajustar `test_mcp_http.py` [M]

## SEC-02 — CSP e capabilities do webview Tauri

- [ ] T-09: Auditar origens reais usadas pelo webview (`fetch`, `WebSocket`, `<img>`, `blob:`, `data:`, chamadas diretas a providers self-hosted em `routes/setup/+page.svelte`) e registrar o resultado no PR [S]
- [ ] T-10: Definir `app.security.csp` e `app.security.devCsp` em `ui/src-tauri/tauri.conf.json` conforme RF-S2-01; validar `tauri dev` e build de produção sem violações de CSP nas telas de CA-02 [M]
- [ ] T-11: Remover `shell:allow-execute`, `shell:allow-spawn`, `shell:allow-stdin-write` de `capabilities/default.json`; `cargo check` em `ui/src-tauri`; verificar `open` em `CardDetail.svelte` e `ConnectModal.svelte` [S]
- [ ] T-12: `scripts/guardrails_check.py::check_tauri`: WARN → ERROR (CSP nula/ausente, `'unsafe-eval'` ou `*` em `script-src`/`connect-src`, shell sem escopo) e registrar em `docs/guardrails.md` [S]

## SEC-03 — elo autenticado engine ↔ n8n

- [ ] T-13: `security/keychain.py`: `laya_n8n_link_secret` com `store_/get_/ensure_n8n_link_secret()` (`secrets.token_urlsafe(32)`) [S]
- [ ] T-14: Criar `engine/laya/security/n8n_link.py` (`require_n8n_link` com transição RF-S3-08 e 503 fail-closed, `link_headers()`, constantes, helpers `is_link_node`/`apply_link_credential`) e `DEFAULT_SETTINGS["security"]["n8n_link"]` em `config.py` + `docs/tuning-parameters.md` [M]
- [ ] T-15: Aplicar `Depends(require_n8n_link)` em `POST /events` (`api/events.py`) e `POST /ingestion-errors` (`api/ingestion_errors.py`); atualizar `engine/tests/conftest.py` com segredo no keyring em memória e header padrão para os testes existentes [M]
- [ ] T-16: `egress/backends/n8n.py::_post_to_n8n`: enviar `X-Laya-Link-Token`; mapear 401/403 para `retryable=False` com mensagem de re-sync; testes em `test_egress_n8n_backend.py` [S]
- [ ] T-17: Provisionamento: `ensure_link_credential()` (credencial singleton `httpHeaderAuth` "Laya Engine Link", idempotente, recria se divergente) chamado antes de `import_workflows` em `n8n_bootstrap.py`; funções auxiliares em `n8n_client.py` se necessário [M]
- [ ] T-18: Injeção de credencial: aplicar o helper do elo em `connections.py::_clone_workflows_for_connection`, `n8n_bootstrap.py::_propagate_to_clones`, `_ensure_error_handler_workflow` e no caminho de clone OAuth; garantir que a credencial da plataforma (incl. `bitbucket_server` `httpHeaderAuth`) não sobrescreve nós do elo e vice-versa; marcar `enforced=true` após propagação completa [L]
- [ ] T-19: Atualizar os 11 `*-ingestion.json`, os 11 `*-executor.json` e `laya-error-handler.json` (HTTP Request → `httpHeaderAuth`; Webhook → `headerAuth`; placeholder `Laya Engine Link`) com bump de `meta.laya_version`; rodar `test_egress_registry_parity.py` e `test_terminal_event_parity.py` [M]
- [ ] T-20: Testes `engine/tests/test_n8n_link_auth.py` (CA-01, CA-02, CA-05, CA-06, CR-01..CR-07) e `engine/tests/test_n8n_workflow_link_static.py` (CA-03); casos de CA-04 em `test_n8n_bootstrap.py`/`test_egress_connections.py` [L]
- [ ] T-21: Teste manual ponta a ponta com n8n real: instalação existente (clones antigos → propagação → enforcement), nova conexão Gmail/Slack/Bitbucket Server, ingestão e execução de uma ação confirmada; registrar no PR [M]

## Documentação, specs e fechamento

- [ ] T-22: Atualizar baselines `harness-sdd/specs/{egress,mcp-server,event-ingestion,connections-n8n}/spec.md` (RF/CA/CR/INV novos; GAPs fechados: egress GAP-01/02/04, mcp-server GAP-01, event-ingestion GAP-01) [S]
- [ ] T-23: Atualizar `.agents/security.md` (SEC-01..SEC-04 para "Proteções existentes"; risco residual como SEC-13 sugerido) e `docs/api-contracts.md` (`/egress/pending*`, tipos WS, header do elo) [S]
- [ ] T-24: Rodar `scripts/guardrails-check.sh` sem `ERROR`, pytest escopado (`test_egress_mcp_confirmation.py test_n8n_link_auth.py test_n8n_workflow_link_static.py test_mcp_http.py test_ingest.py test_n8n_bootstrap.py test_egress_n8n_backend.py test_egress_connections.py test_egress_registry_parity.py test_terminal_event_parity.py`), `npx vitest run src/lib/egress`, `svelte-check` e `cargo check` [S]
