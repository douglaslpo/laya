# Spec: Egress (ações externas)

**Status:** baseline · **Dono:** `engine/laya/egress/`

## Contexto
Ações aprovadas (responder e-mail, comentar PR, transicionar ticket…) saem pelo egress, que enriquece, valida, mostra preview e executa via webhook n8n do executor da conexão ou via SMTP.

## Requisitos
- **RF-01** Cada plataforma é uma subclasse de `Platform` com `name`, `capabilities`, `identifiers_from_event`, `normalize_payload`, `validate_payload` (e opcionais como `terminal_event_types`, `payload_credential_fields`, `draft_schema`).
- **RF-02** Plataformas suportadas: gmail, outlook, smtp, jira, notion, github, bitbucket, bitbucket_server, slack, linear, google_calendar, outlook_calendar.
- **RF-03** `enrichment.py` é o caminho único de enriquecimento para preview e execução: normaliza `None`→`""`, busca o evento de origem, aplica `identifiers_from_event` (valor do engine vence o do LLM) e `normalize_payload`.
- **RF-04** `build_preview` gera resumo pelo `summary_template`, avisos estáticos e dinâmicos (transição terminal, e-mail com > 3 destinatários) e `impact`.
- **RF-05** O backend n8n resolve o webhook por `connection_id` → mesmo space → qualquer executor → settings → defaults, e monta o envelope `{action_id: egr_<card_id>, source_event_id, target, action_type, payload, event_*}`. A requisição ao webhook do executor envia `X-Laya-Link-Token` (segredo do elo engine↔n8n, ver `connections-n8n` RF-08); resposta 401/403 do n8n vira `success=False, retryable=False` com mensagem de re-sync dos workflows.
- **RF-06** Toda chamada de ferramenta carrega uma origem (`chat` | `mcp`) no contextvar `tool_call_origin` (`llm/tools/origin.py`); o loop do chat define `chat`, o servidor MCP define `mcp` e origem ausente é tratada como `mcp` (fail-closed). Ações do chat geram preview + `execute_token` (uso único, 5 min); `confirm_egress` (somente origem `chat`) executa e audita com `source="chat"`.
- **RF-09** Pendências e tokens vivem em memória em `egress/pending.py`: segredo por processo `secrets.token_bytes(32)`; token `egr_<nonce>.<sig>` com `nonce = secrets.token_urlsafe(16)` e `sig = HMAC-SHA256(secret, nonce|origin)` truncado a 128 bits; assinatura verificada com `hmac.compare_digest` **antes** do lookup; TTL 300 s; uso único; vínculo de origem (uma entrada de outra origem é reportada como inexistente e permanece intacta). Reinício do engine descarta todas as pendências.
- **RF-10** Ferramenta de egress com origem `mcp` gera preview, cria pendência `{request_id: egreq_…, origin:"mcp", …}`, faz broadcast WS `egress_confirmation_request` (payload sanitizado, sem token) e responde ao cliente MCP `{"status":"awaiting_user_confirmation", request_id, summary, warnings, instruction}` sem `execute_token`.
- **RF-11** API de pendências (`api/egress_pending_api.py`, registrada antes de rotas `/egress/{param}`): `GET /egress/pending` lista pendências MCP não expiradas (ordenadas por `expires_at`, sem segredos); `POST /egress/pending/{request_id}/confirm` executa, audita `step="execute"`, `metadata.source="mcp"` e emite `egress_confirmation_resolved{status:"done"|"failed"}`; `POST /egress/pending/{request_id}/reject` descarta, audita `step="egress_rejected"` (`success=False`) e emite `egress_confirmation_resolved{status:"rejected"}`. Os dois `POST` rejeitam `Origin` externo (403, `api/origin_guard.py`). A UI mostra `EgressConfirmModal` e recarrega `GET /egress/pending` ao (re)conectar o WS.
- **RF-07** Ações de card passam por `/actions/execute` → `pipeline/executor.py` (ciclo de vida do card + `action_log`).
- **RF-08** `open_url` é resolvido no cliente, sem egress.

## Critérios de aceitação
- **CA-01** Dado um payload que falha em `validate_payload`, então nada é enviado e os erros são retornados.
- **CA-02** Dado um `connection_id` sem executor correspondente, então a execução falha com erro explícito (não usa outra conta).
- **CA-03** Dado um timeout no webhook, então o resultado é `success=False, retryable=False` (resultado desconhecido).
- **CA-04** Dado um `ConnectError`, então `retryable=True`.
- **CA-05** Dado uma plataforma on-prem (Bitbucket Server), então `base_url`/`allow_insecure_ssl` da conexão são injetados via `payload_credential_fields`, sem predicados cloud-vs-server.
- **CA-06** As capabilities de cada adapter batem com os ramos do Switch do executor n8n correspondente.
- **CA-07** Dado `dry_run`, então retorna sucesso sem executar.
- **CA-08** Dado um cliente MCP com `egress=true` chamando `send_email`, então `egress.preview` é chamado, `egress.execute` não, a resposta é `awaiting_user_confirmation` com `request_id` e sem `execute_token`, e `egress_confirmation_request` é emitido com o mesmo `request_id`.
- **CA-09** Dado uma pendência MCP não expirada, quando a UI chama `POST /egress/pending/{id}/confirm`, então `egress.execute` roda uma única vez, a auditoria registra `source="mcp"`, a pendência sai do store e `egress_confirmation_resolved` é emitido; `…/reject` não executa nada e audita `egress_rejected`.
- **CA-10** Dois tokens consecutivos para a mesma ação são diferentes e a verificação usa `hmac.compare_digest`.

## Critérios de rejeição / casos-limite
- **CR-01** `execute_token` reutilizado, expirado ou com assinatura inválida → rejeitado sem executar (assinatura inválida nem consulta o store; o token nunca é logado). `POST /egress/pending/{id}/confirm|reject` com id desconhecido, já resolvido ou de outra origem → **404**; expirado → **410**.
- **CR-05** Token de origem `chat` não resolve pendência `mcp` e vice-versa.
- **CR-06** `Origin` externo em `POST /egress/pending/{id}/confirm|reject` → 403 e a pendência permanece intacta.
- **CR-07** Executor n8n responde 401/403 → `success=False, retryable=False`, sem retry automático.
- **CR-02** Calendar marcado como `gmail` é remapeado para `"calendar"` (não `google_calendar`, que dá 404).
- **CR-03** `_PLATFORM_KEYWORDS`: "bitbucket server" resolve antes de "bitbucket".
- **CR-04** Campo ausente no `summary_template` vira `"unknown"`, não quebra o preview.

## Invariantes
- **INV-01** Nenhuma escrita externa sem preview + confirmação humana (decisão #28).
- **INV-02** Preview e execução compartilham o mesmo enriquecimento.
- **INV-03** Timeout nunca é re-tentado automaticamente (evita envio duplicado).
- **INV-04** Nenhuma ação iniciada via MCP é executada sem ação explícita do usuário na UI do Laya; `confirm_egress` nunca é acessível via MCP.
- **INV-05** Tokens e segredos nunca aparecem em logs, respostas de listagem (`GET /egress/pending`) ou broadcasts WS; `request_id` é identificador opaco, não credencial de execução.

## Referências
Código: `egress/platforms/*`, `egress/registry.py`, `egress/router.py`, `egress/enrichment.py`, `egress/backends/{n8n,smtp}.py`, `egress/tools.py`, `egress/tool_handlers.py`, `egress/pending.py`, `llm/tools/origin.py`, `api/egress_api.py`, `api/egress_pending_api.py`, `api/origin_guard.py`, `api/actions_api.py`, `pipeline/executor.py`, `ui/src/lib/egress/pendingConfirmations.ts`, `ui/src/lib/components/egress/EgressConfirmModal.svelte`. Testes: `test_egress_platforms.py`, `test_platform_interface.py`, `test_egress_registry_parity.py`, `test_terminal_event_parity.py`, `test_egress_router.py`, `test_egress_n8n_backend.py`, `test_egress_models.py`, `test_executor.py`, `test_egress_mcp_confirmation.py`, `ui/src/lib/egress/pendingConfirmations.test.ts`. Docs: `engine/docs/egress-*.md`. Skill: `laya-egress-platform`.

## Lacunas
- ~~**GAP-01**~~ **Fechado** (`imp-local-security-hardening`): `confirm_egress` é somente-chat; egress via MCP exige confirmação na UI (RF-10, RF-11).
- ~~**GAP-02**~~ **Fechado** (`imp-local-security-hardening`): segredo por processo via `secrets.token_bytes(32)` e verificação em tempo constante (RF-09).
- **GAP-03** Sem idempotência no servidor para `/egress/execute` (P4-24).
- ~~**GAP-04**~~ **Fechado** (`imp-local-security-hardening`): webhooks de executor exigem `X-Laya-Link-Token` via `headerAuth` (RF-05).
- **GAP-05** Seção "Outbound Action Schema" de `docs/event-schema.md` desatualizada.
- **GAP-06** `POST /egress/pending/{id}/confirm` é protegido só por loopback + checagem de `Origin`; um processo local que conheça o `request_id` pode confirmar (SEC-13 — token de sessão da UI sugerido).
