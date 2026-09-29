# Spec: Egress (ações externas)

**Status:** baseline · **Dono:** `engine/laya/egress/`

## Contexto
Ações aprovadas (responder e-mail, comentar PR, transicionar ticket…) saem pelo egress, que enriquece, valida, mostra preview e executa via webhook n8n do executor da conexão ou via SMTP.

## Requisitos
- **RF-01** Cada plataforma é uma subclasse de `Platform` com `name`, `capabilities`, `identifiers_from_event`, `normalize_payload`, `validate_payload` (e opcionais como `terminal_event_types`, `payload_credential_fields`, `draft_schema`).
- **RF-02** Plataformas suportadas: gmail, outlook, smtp, jira, notion, github, bitbucket, bitbucket_server, slack, linear, google_calendar, outlook_calendar.
- **RF-03** `enrichment.py` é o caminho único de enriquecimento para preview e execução: normaliza `None`→`""`, busca o evento de origem, aplica `identifiers_from_event` (valor do engine vence o do LLM) e `normalize_payload`.
- **RF-04** `build_preview` gera resumo pelo `summary_template`, avisos estáticos e dinâmicos (transição terminal, e-mail com > 3 destinatários) e `impact`.
- **RF-05** O backend n8n resolve o webhook por `connection_id` → mesmo space → qualquer executor → settings → defaults, e monta o envelope `{action_id: egr_<card_id>, source_event_id, target, action_type, payload, event_*}`.
- **RF-06** Ações do chat geram preview + `execute_token` (uso único, 5 min); `confirm_egress` executa e audita com `source="chat"`.
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

## Critérios de rejeição / casos-limite
- **CR-01** `execute_token` reutilizado ou expirado → rejeitado.
- **CR-02** Calendar marcado como `gmail` é remapeado para `"calendar"` (não `google_calendar`, que dá 404).
- **CR-03** `_PLATFORM_KEYWORDS`: "bitbucket server" resolve antes de "bitbucket".
- **CR-04** Campo ausente no `summary_template` vira `"unknown"`, não quebra o preview.

## Invariantes
- **INV-01** Nenhuma escrita externa sem preview + confirmação humana (decisão #28).
- **INV-02** Preview e execução compartilham o mesmo enriquecimento.
- **INV-03** Timeout nunca é re-tentado automaticamente (evita envio duplicado).

## Referências
Código: `egress/platforms/*`, `egress/registry.py`, `egress/router.py`, `egress/enrichment.py`, `egress/backends/{n8n,smtp}.py`, `egress/tools.py`, `egress/tool_handlers.py`, `api/egress_api.py`, `api/actions_api.py`, `pipeline/executor.py`. Testes: `test_egress_platforms.py`, `test_platform_interface.py`, `test_egress_registry_parity.py`, `test_terminal_event_parity.py`, `test_egress_router.py`, `test_egress_n8n_backend.py`, `test_egress_models.py`, `test_executor.py`. Docs: `engine/docs/egress-*.md`. Skill: `laya-egress-platform`.

## Lacunas
- **GAP-01** Cliente MCP com escopo `egress` pode chamar `confirm_egress` sem humano (SEC-01).
- **GAP-02** Segredo HMAC do token derivado de `time.time_ns()` (SEC-04).
- **GAP-03** Sem idempotência no servidor para `/egress/execute` (P4-24).
- **GAP-04** Webhooks de executor n8n sem autenticação (SEC-03).
- **GAP-05** Seção "Outbound Action Schema" de `docs/event-schema.md` desatualizada.
