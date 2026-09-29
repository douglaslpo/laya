# specs: imp-local-security-hardening — SEC-01 (confirmação humana de egress via MCP + token CSPRNG)

Baselines afetadas: `harness-sdd/specs/egress/spec.md` (RF-06, CR-01, INV-01; fecha **GAP-01** e **GAP-02**), `harness-sdd/specs/mcp-server/spec.md` (RF-03, INV-01, INV-02; fecha **GAP-01**). Guardrails: G-EGR-01, G-SEC-02, G-SEC-03, G-SEC-04.

## Requisitos novos / alterados

- **RF-S1-01** (altera `egress` RF-06) Toda chamada de ferramenta carrega uma origem (`chat` | `mcp`) em contextvar; o servidor MCP define `mcp` antes de `execute_tool`; o loop de chat (`pipeline/chat.py`) define `chat`. Ausência de origem é tratada como `mcp` (fail-closed).
- **RF-S1-02** (altera `mcp-server` RF-03/INV-02) `confirm_egress` é classificada como ferramenta **somente-chat**: não aparece em `list_tools` e é negada em `call_tool` via MCP, independentemente dos escopos.
- **RF-S1-03** Ferramenta de egress chamada com origem `mcp` gera preview e cria uma solicitação pendente `{request_id, origin:"mcp", preview, platform, action_type, space_id, expires_at}`; faz broadcast WS `egress_confirmation_request` e responde ao cliente MCP `{"status":"awaiting_user_confirmation", "request_id", "summary", "warnings", "instruction"}` **sem** `execute_token`.
- **RF-S1-04** Endpoints REST: `GET /egress/pending` (lista solicitações não expiradas, sem segredos), `POST /egress/pending/{request_id}/confirm` (executa, audita `source="mcp"`, broadcast `egress_confirmation_resolved{status:"done"|"failed"}`), `POST /egress/pending/{request_id}/reject` (descarta, audita rejeição, broadcast `egress_confirmation_resolved{status:"rejected"}`). Ambos `POST` rejeitam `Origin` externo (mesmo critério de `_reject_cross_site` em `api/mcp_api.py`).
- **RF-S1-05** UI exibe modal de confirmação com o preview (resumo, detalhes, avisos, impacto, plataforma/conta) para cada `egress_confirmation_request`, com ações "Enviar" e "Rejeitar"; carrega pendentes via `GET /egress/pending` ao (re)conectar o WS.
- **RF-S1-06** (substitui `egress` GAP-02) Segredo de assinatura por processo `secrets.token_bytes(32)`; token = `egr_<nonce>.<sig>` com `nonce = secrets.token_urlsafe(16)` e `sig = HMAC-SHA256(secret, nonce|origin)` truncado ≥ 128 bits; verificação da assinatura com `hmac.compare_digest` **antes** de consultar o store. Uso único e TTL de 300 s mantidos.

## CA-01: MCP não enxerga nem executa `confirm_egress`

**Given** escopos MCP `read=true, write=true, egress=true`
**When** o cliente MCP chama `list_tools` e depois `call_tool("confirm_egress", {...})`
**Then** `confirm_egress` não está na lista e a chamada retorna erro JSON-RPC (METHOD_NOT_FOUND ou equivalente) com mensagem indicando que a confirmação é exclusiva da UI; nenhuma chamada a `egress.execute` ocorre.

## CA-02: egress via MCP cria solicitação pendente e notifica a UI

**Given** escopo `egress=true` e uma conexão Gmail válida
**When** o cliente MCP chama `send_email` com payload válido
**Then** `egress.preview` é chamado, `egress.execute` **não** é chamado, a resposta tem `status="awaiting_user_confirmation"` e `request_id` e não contém `execute_token`, e um broadcast `egress_confirmation_request` com o mesmo `request_id` e o preview é emitido.

## CA-03: confirmação na UI executa e audita

**Given** uma solicitação pendente MCP não expirada
**When** a UI chama `POST /egress/pending/{request_id}/confirm` sem `Origin` externo
**Then** `egress.execute` é chamado uma única vez com o `EgressRequest` do preview, `log_to_audit` registra `step="execute"`, `metadata.source="mcp"`, a solicitação é removida do store e `egress_confirmation_resolved` é emitido com o resultado.

## CA-04: rejeição na UI descarta sem executar

**Given** uma solicitação pendente MCP
**When** a UI chama `POST /egress/pending/{request_id}/reject`
**Then** nada é executado, a solicitação some de `GET /egress/pending`, a rejeição é auditada e `egress_confirmation_resolved{status:"rejected"}` é emitido.

## CA-05: fluxo do chat interno continua funcionando

**Given** o chat interno (origem `chat`) chama `send_email` e recebe `execute_token`
**When** o LLM do chat chama `confirm_egress` com esse token dentro de 5 min
**Then** a ação é executada e auditada com `source="chat"` (comportamento de `egress` RF-06 preservado).

## CA-06: token gerado por CSPRNG e verificado em tempo constante

**Given** o módulo `egress/tool_handlers.py` carregado
**When** tokens são gerados
**Then** o segredo vem de `secrets.token_bytes` (não de `time`), dois tokens consecutivos para o mesmo `platform/action_type` são diferentes, e a verificação usa `hmac.compare_digest` (testável por patch/spy).

## CA-07: UI lista pendentes após reconexão

**Given** duas solicitações pendentes criadas enquanto a UI estava desconectada
**When** o WS reconecta
**Then** a UI chama `GET /egress/pending` e exibe as duas solicitações na fila de confirmação (lógica de fila coberta por vitest).

## CR-01: token do chat não confirma solicitação MCP e vice-versa

**Given** uma solicitação pendente criada com origem `mcp`
**When** o chat chama `confirm_egress` com o `request_id` (ou um token forjado a partir dele)
**Then** a chamada é rejeitada com erro de token inválido e nada é executado; **e** um `execute_token` de origem `chat` enviado a `POST /egress/pending/{id}/confirm` retorna 404.

## CR-02: solicitação expirada ou reutilizada

**Given** uma solicitação MCP com mais de 300 s ou já confirmada/rejeitada
**When** `POST /egress/pending/{request_id}/confirm` é chamado
**Then** resposta 404/410 com erro explícito, nada é executado (estende `egress` CR-01).

## CR-03: token com assinatura inválida

**Given** um token `egr_<nonce>.<sig>` com `sig` alterada ou formato inválido
**When** `confirm_egress` é chamado
**Then** retorna erro sem consultar o store e sem executar; o valor do token não aparece em logs.

## CR-04: origem desconhecida é fail-closed

**Given** `execute_tool` invocado sem origem definida no contextvar
**When** uma ferramenta de egress é chamada
**Then** o comportamento é o de origem `mcp` (solicitação pendente, sem `execute_token`).

## CR-05: `Origin` externo nos endpoints de pendência

**Given** uma requisição com header `Origin: https://evil.example`
**When** chama `POST /egress/pending/{id}/confirm` ou `/reject`
**Then** resposta 403 e a solicitação permanece intacta.

## CR-06: escopo `egress=false`

**Given** `egress=false`
**When** o cliente MCP chama `send_email`
**Then** negado como hoje (`mcp-server` CA-02), nenhuma solicitação pendente é criada.

## Invariantes

- **INV-S1-01** Nenhuma ação iniciada via MCP é executada sem ação explícita do usuário na UI do Laya (reforça `egress` INV-01 / G-EGR-01).
- **INV-S1-02** Escopos MCP padrão inalterados (`mcp-server` INV-01 / G-SEC-02).
- **INV-S1-03** Tokens e segredos nunca em logs, respostas REST de listagem ou broadcast WS (`request_id` é identificador opaco, não credencial de execução via MCP).
