# design: imp-local-security-hardening

> **Aprovação de contrato necessária antes do apply** (regra `laya-core`): novo tipo WS `egress_confirmation_request`/`egress_confirmation_resolved`, endpoints `/egress/pending*`, remoção de `confirm_egress` da superfície MCP, CSP/capabilities Tauri, header obrigatório `X-Laya-Link-Token` em `POST /events`, `POST /ingestion-errors` e webhooks de executor. Sem migration de banco (próxima seria `073_*.sql`, não usada).

## Visão geral

```
SEC-01  MCP client ──call_tool(send_email)──> mcp/http_server (origin=mcp)
                                              └─> execute_tool ─> tool_handlers.handle_egress_tool
                                                   ├─ preview()
                                                   ├─ pending store {request_id, origin=mcp}
                                                   └─ WS egress_confirmation_request ─> UI modal
        UI "Enviar" ─> POST /egress/pending/{id}/confirm ─> egress.execute ─> audit(source="mcp")
        confirm_egress: somente origin=chat (fora de list_tools/call_tool do MCP)

SEC-02  tauri.conf.json csp/devCsp  +  capabilities/default.json só shell:allow-open

SEC-03  n8n ingestion ──X-Laya-Link-Token (cred "Laya Engine Link")──> POST /events | /ingestion-errors
        engine N8nBackend ──X-Laya-Link-Token──> n8n executor Webhook (headerAuth, mesma cred)
        segredo: keychain laya-engine/laya_n8n_link_secret  →  credencial n8n httpHeaderAuth
```

## Arquivos a criar

| Caminho | Propósito |
|---|---|
| `engine/laya/llm/tools/origin.py` | Contextvar `tool_call_origin: ContextVar[Literal["chat","mcp"] | None]` + helper `current_origin()` que retorna `"mcp"` quando não definido (fail-closed). SPDX header. |
| `engine/laya/egress/pending.py` | Store em memória das solicitações/tokens pendentes: geração (`secrets.token_bytes(32)` por processo, `secrets.token_urlsafe(16)` nonce, HMAC-SHA256), verificação com `hmac.compare_digest`, TTL 300 s, uso único, vínculo de origem, `list_pending()` sanitizado. Extraído de `tool_handlers.py` para ser reutilizado pela API. |
| `engine/laya/api/egress_pending_api.py` | Router `GET /egress/pending`, `POST /egress/pending/{request_id}/confirm`, `POST /egress/pending/{request_id}/reject`; reutiliza a checagem de `Origin` (extrair `_reject_cross_site` de `api/mcp_api.py` para um helper compartilhado, ex. `laya/api/origin_guard.py`, se preferível a importar símbolo privado). Registrar **antes** de qualquer rota `/egress/{param}` (G-ENG-08). |
| `engine/laya/security/n8n_link.py` | `require_n8n_link` (dependência FastAPI para as rotas de ingestão, com lógica de transição RF-S3-08), `link_headers()` para o backend n8n, `ensure_link_credential()` para o provisionamento, constantes `LINK_HEADER = "X-Laya-Link-Token"`, `LINK_CRED_NAME = "Laya Engine Link"`, `LINK_CRED_TYPE = "httpHeaderAuth"`. |
| `ui/src/lib/egress/pendingConfirmations.ts` | Lógica pura da fila de confirmações (add/resolve/expire/dedupe por `request_id`, ordenação por `expires_at`). |
| `ui/src/lib/egress/pendingConfirmations.test.ts` | Vitest da lógica acima (CA-07 de SEC-01). |
| `ui/src/lib/components/egress/EgressConfirmModal.svelte` | Modal Svelte 5 runes com preview (resumo, detalhes, avisos, impacto, conta) e ações Enviar/Rejeitar; tokens do Design System; padrão de modal existente (ver skill `laya-ui-design-system`). |
| `engine/tests/test_egress_mcp_confirmation.py` | CA/CR de SEC-01 (MCP sem `confirm_egress`, pendência, confirm/reject, vínculo de origem, expiração, `Origin` externo, token CSPRNG). |
| `engine/tests/test_n8n_link_auth.py` | CA/CR de SEC-03 no engine (dependência, transição, 401/503, headers no backend, provisionamento idempotente, segredo fora de logs/settings). |
| `engine/tests/test_n8n_workflow_link_static.py` | Teste estático dos JSONs (CA-03 de SEC-03): nós de ingestão/error handler com `httpHeaderAuth`, webhooks de executor com `headerAuth`. |

## Arquivos a modificar

| Caminho | Mudanças |
|---|---|
| `engine/laya/egress/tool_handlers.py` | Remover `_TOKEN_SECRET` derivado de `time.time_ns()`, `_generate_token` e `_pending_requests` locais (passam a `egress/pending.py`). `handle_egress_tool`: se `current_origin()=="mcp"` cria pendência MCP + broadcast `egress_confirmation_request` e retorna `awaiting_user_confirmation` sem token; se `chat`, mantém retorno com `execute_token`. `handle_confirm_egress`: exige origem `chat`, verifica assinatura antes do lookup, rejeita pendências `mcp`. Nova função `execute_pending(request_id, origin="mcp")` compartilhada com a API (execução + `log_to_audit` com `source`). Comentários do porquê (G-ENG-12). |
| `engine/laya/llm/tools/definitions.py` | Nova função `chat_only_tool_names() -> {"confirm_egress"}`; manter `egress_tool_names()` para o chat, mas expor `mcp_egress_tool_names()` = egress − chat-only (ou equivalente) para o escopo MCP. |
| `engine/laya/mcp/scope.py` | `enabled_tool_names` exclui `chat_only_tool_names()` sempre; docstring atualizada. |
| `engine/laya/mcp/http_server.py` | `call_tool`: negar chat-only com mensagem própria; setar `tool_call_origin="mcp"` (set/reset em try/finally) antes de `execute_tool`. Aplicar também ao transporte legado `/mcp/sse` se usar outro caminho. |
| `engine/laya/pipeline/chat.py` | Setar `tool_call_origin="chat"` em volta das duas chamadas a `execute_tool` (linhas ~366 e ~677). |
| `engine/laya/llm/tools/executor.py` | Sem mudança de dispatch; eventualmente defesa extra: `confirm_egress` com origem ≠ `chat` retorna erro. |
| `engine/laya/llm/prompts/chat.py` | Nenhuma mudança de fluxo; só revisar texto se mencionar MCP. |
| `engine/laya/main.py` (ou onde os routers são incluídos) | Incluir `egress_pending_api.router`; garantir ordem estática antes de rotas com parâmetro. |
| `engine/laya/api/mcp_api.py` | Se extraído, `_reject_cross_site` passa a importar do helper compartilhado (sem mudança de comportamento). |
| `engine/laya/api/events.py` | `receive_event` ganha `Depends(require_n8n_link)`. |
| `engine/laya/api/ingestion_errors.py` | `POST /ingestion-errors` ganha `Depends(require_n8n_link)`. |
| `engine/laya/security/keychain.py` | `N8N_LINK_SECRET_KEY = "laya_n8n_link_secret"` + `store_/get_/ensure_n8n_link_secret()` no padrão de `laya_mcp_bearer` (cache existente). |
| `engine/laya/integrations/n8n_bootstrap.py` | Em `provision_n8n_background`/`ensure_n8n_ready`: chamar `ensure_link_credential()` antes de `import_workflows`. `_propagate_to_clones`: injetar credencial do elo nos nós marcados e pular a injeção da plataforma nesses nós (colisão `httpHeaderAuth` do `bitbucket_server`); ao concluir sem falhas, marcar `security.n8n_link.enforced=true`. `_ensure_error_handler_workflow`: injetar credencial do elo. |
| `engine/laya/egress/connections.py` | `_clone_workflows_for_connection`: mesma regra de injeção/skip do elo (manter as duas implementações em sincronia; considerar helper compartilhado em `security/n8n_link.py`, ex. `apply_link_credential(nodes, cred_ref)` + `is_link_node(node)`). |
| `engine/laya/egress/oauth.py` | Revisar o caminho de clone OAuth (se não reutilizar `_clone_workflows_for_connection`) para aplicar o mesmo helper. |
| `engine/laya/egress/backends/n8n.py` | `_post_to_n8n`: headers `link_headers()`; mapear 401/403 para `retryable=False` com mensagem de re-sync. |
| `engine/laya/integrations/n8n_client.py` | Se necessário, funções `get_credential`/`update_credential` para recriar a credencial do elo. |
| `engine/laya/config.py` | `DEFAULT_SETTINGS["security"]["n8n_link"] = {"enforced": False, "transition_started_at": None}` (não secretos). |
| `engine/tests/conftest.py` | Fixture que provisiona o segredo no keyring em memória e um helper/cliente com `X-Laya-Link-Token` padrão, para que testes existentes de `/events` (`test_ingest.py`, `test_integration_pipeline.py`, etc.) continuem passando. |
| `engine/tests/test_mcp_http.py` | Ajustar expectativas de `list_tools` com `egress=true` (sem `confirm_egress`). |
| `engine/tests/test_n8n_bootstrap.py` | Casos de provisionamento da credencial e propagação com elo. |
| `engine/tests/test_egress_n8n_backend.py` | Header enviado e mapeamento 401/403. |
| `n8n/workflows/*-ingestion.json` (11) | Nós "POST to Laya Engine" (e POST `/ingestion-errors` do github) com `authentication: genericCredentialType`, `genericAuthType: httpHeaderAuth`, `credentials.httpHeaderAuth = {id: "__LAYA_LINK__", name: "Laya Engine Link"}`; bump de `meta.laya_version`. GETs a `/metadata`/`/repos` ficam como estão (fora de escopo), mas podem receber o header sem custo — decidir no apply. |
| `n8n/workflows/*-executor.json` (11) | Nó `Webhook`: `parameters.authentication = "headerAuth"`, `credentials.httpHeaderAuth` placeholder `Laya Engine Link`; bump de versão. Switch/capabilities intactos (G-N8N-03). |
| `n8n/workflows/laya-error-handler.json` | Nó POST `/ingestion-errors` autenticado; bump de versão. |
| `ui/src-tauri/tauri.conf.json` | `app.security.csp` e `app.security.devCsp` conforme RF-S2-01. |
| `ui/src-tauri/capabilities/default.json` | Remover `shell:allow-execute`, `shell:allow-spawn`, `shell:allow-stdin-write`. |
| `ui/src/lib/stores/websocket.ts` (ou roteador de mensagens WS) | Tratar `egress_confirmation_request`/`egress_confirmation_resolved` alimentando `pendingConfirmations`; ao reconectar, `GET /egress/pending`. |
| `ui/src/routes/+layout.svelte` | Montar `EgressConfirmModal` globalmente. |
| `scripts/guardrails_check.py` | `check_tauri`: WARN → ERROR para CSP nula/ausente, `'unsafe-eval'`/`*` em `script-src`/`connect-src`, e permissões de shell sem escopo. |
| `harness-sdd/specs/egress/spec.md` | RF-06 atualizado (origem, token CSPRNG); novo RF de pendências MCP; CR-01 estendido; GAP-01, GAP-02, GAP-04 marcados como fechados. |
| `harness-sdd/specs/mcp-server/spec.md` | RF-03/INV-02 com exceção chat-only; novo CA "confirm_egress nunca via MCP"; GAP-01 fechado. |
| `harness-sdd/specs/event-ingestion/spec.md` | RF-01/RF-08 com header obrigatório; CR novos (401/503); GAP-01 fechado. |
| `harness-sdd/specs/connections-n8n/spec.md` | RF-02/RF-03/RF-06 com credencial do elo e regra de injeção; nova INV do elo. |
| `.agents/security.md` | Mover SEC-01, SEC-02, SEC-03 e SEC-04 para "Proteções existentes"; registrar risco residual (endpoints REST da UI sem token de sessão) como novo SEC-13 sugerido. |
| `docs/api-contracts.md` | Documentar `/egress/pending*`, tipos WS novos, header `X-Laya-Link-Token` em `/events` e `/ingestion-errors`. |
| `docs/guardrails.md` | Registrar ERROR de CSP/shell no `check_tauri`. |
| `docs/tuning-parameters.md` | `security.n8n_link.*` (flag automática, não editável pelo usuário). |

## Arquivos fora de escopo (doNotTouch)

- `harness-sdd/changes/**` (exceto esta pasta), `harness-sdd/archive/**`, `.claude/`, `.cursor/`, `AGENTS.md`, `.agents/*.md` exceto `security.md`
- `engine/requirements*.lock`, `ui/package-lock.json`, `ui/src-tauri/Cargo.lock` (nenhuma dependência nova)
- `engine/laya/db/migrations/**` (sem migration)
- `ui/src-tauri/src/n8n.rs` (env do n8n — SEC-07 é follow-up; **não** passar o segredo por env)
- `engine/laya/agents/**`, `engine/laya/llm/agent_backend.py` (SEC-05/08/09/12)
- `engine/laya/api/mcp_api.py` `/mcp/token/reveal` (SEC-10)

## Padrões e convenções

- **Contextvar por requisição**: seguir `current_space_id` em `mcp/http_server.py` (set + reset em `finally`).
- **Tokens/segredos**: `secrets.token_urlsafe` / `secrets.token_bytes`; comparação `hmac.compare_digest` (regra `laya-security`); keychain via `security/keychain.py` com `SERVICE_NAME="laya-engine"`; testes usam keyring em memória (nunca o real).
- **Checagem de `Origin`**: mesmo conjunto `_ALLOWED_ORIGINS` de `api/mcp_api.py`.
- **Broadcast WS**: `manager.broadcast({"type": ..., "payload": ...})` como `open_compose`; documentar em `docs/api-contracts.md`.
- **Auditoria**: `log_to_audit(step="execute", metadata={"source": ...})` como em `handle_confirm_egress`; rejeição com `step="egress_rejected"` (ou equivalente) e `success=False`.
- **n8n**: bump `meta.laya_version` `AAAA.MM.N`; credencial referenciada por placeholder no template e substituída na clonagem/propagação; injeção por plataforma nunca toca nós do elo (identificação por `credentials.httpHeaderAuth.name == LINK_CRED_NAME` no template).
- **Engine**: async em tudo; provisionamento no fluxo de background existente (`provision_n8n_background`); nada de rede dentro de `transaction()`; defesas com comentário do porquê.
- **UI**: Svelte 5 runes (`$state`, `$derived`, `$props`, `onclick`), tokens OKLCH/`text-laya-*`, validar dark/light × glass × paleta acessível × reduced motion (G-UI-03); lógica pura em `lib/` com vitest.
- **Testes**: pytest-asyncio strict (`@pytest.mark.asyncio`), fixtures de `engine/tests/conftest.py`, ASGITransport para API, httpx/n8n mockados; execução escopada conforme `.agents/testing.md`.

## Validação cross-repo

A mudança altera o contrato entre dois processos do mesmo repositório (engine ↔ n8n via workflows empacotados), não entre repositórios; não há serviço externo a coordenar pelo bus. Se algum consumidor externo chamar `POST /events` diretamente (integrações de terceiros fora de `n8n/workflows/`), ele passará a receber 401 após a transição — registrar no changelog. Referência: `harness-prereqs/BUS-CROSS-REPO.md` (não aplicável além desta nota).

## Dependências entre tarefas

1. **Base SEC-01** (`origin.py`, `pending.py`) → handlers/MCP/chat → API `/egress/pending*` → UI (store + modal + WS) → testes.
2. **SEC-03** keychain + `n8n_link.py` → dependência nas rotas + backend → provisionamento/credencial → helper de injeção (connections + bootstrap) → workflows JSON + bump → transição/flag → testes. A dependência de rota e a transição precisam estar prontas **antes** de trocar os JSONs, e o `conftest` precisa do header antes de ligar o enforcement para não quebrar a suíte.
3. **SEC-02** é independente; fazer depois do modal de SEC-01 para validar a CSP também com a UI nova.
4. Guardrails (`check_tauri` ERROR) depois de SEC-02 aplicado; specs de baseline/docs por último.
