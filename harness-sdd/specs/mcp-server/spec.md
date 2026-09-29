# Spec: Servidor MCP

**Status:** baseline · **Donos:** `engine/laya/mcp/`, `engine/laya/api/mcp_api.py`

## Requisitos
- **RF-01** Transportes: `/mcp/sse` + `/mcp/messages/` (legado, usado pelos agentes) e Streamable HTTP em `/mcp/`; as rotas legadas são registradas antes do Mount.
- **RF-02** Autenticação bearer `lyat_…` guardada no keychain (`laya_mcp_bearer`), comparada com `hmac.compare_digest`; `mcp.auth_mode="none"` desliga.
- **RF-03** Escopos `read`, `write`, `egress` relidos a cada `list_tools`/`call_tool`; padrão `read=true`, `write=false`, `egress=false`. Ferramentas **somente-chat** (`chat_only_tool_names()`, hoje `confirm_egress`) ficam fora de `list_tools` e são negadas em `call_tool` independentemente dos escopos (checagem feita antes da de escopo).
- **RF-04** `space_id` via query string, propagado por contextvar.
- **RF-05** Sessões Streamable ociosas encerradas após 600 s.
- **RF-06** Gestão do token: `/mcp/config`, `/mcp/token/*`; `refresh` e `delete` rejeitam `Origin` externo (checagem compartilhada em `api/origin_guard.py`).
- **RF-07** `call_tool` define `tool_call_origin="mcp"` (set/reset em `finally`) antes de `execute_tool`; com isso, ferramentas de egress chamadas via MCP viram pendências confirmadas só pelo usuário na UI (`egress` RF-10/RF-11) e o cliente recebe `awaiting_user_confirmation` + `request_id`, nunca `execute_token`.

## Critérios de aceitação
- **CA-01** Dado um token inválido, então a requisição MCP recebe 401.
- **CA-02** Dado `write=false`, então ferramentas de escrita não aparecem em `list_tools` e `call_tool` delas é negado.
- **CA-03** Dado uma mudança de escopo em Settings, então a próxima chamada já reflete o novo escopo (sem restart).
- **CA-04** Dado `?space_id=x`, então as ferramentas de leitura só retornam dados do space `x`.
- **CA-05** Dado escopos `read=true, write=true, egress=true`, então `confirm_egress` não aparece em `list_tools` e `call_tool("confirm_egress")` retorna erro JSON-RPC `METHOD_NOT_FOUND` informando que a confirmação é exclusiva da UI; `egress.execute` não é chamado.
- **CA-06** Dado `egress=true`, quando o cliente chama `send_email`, então a resposta é `awaiting_user_confirmation` sem `execute_token` e nada é executado até a confirmação na UI.

## Critérios de rejeição / casos-limite
- **CR-01** Host não-loopback é rejeitado pelo `TrustedHostMiddleware` (a proteção DNS-rebinding do SDK está desligada e é compensada pelo middleware).
- **CR-02** Dado `egress=false`, `call_tool` de ferramenta de egress é negado e nenhuma pendência é criada.

## Invariantes
- **INV-01** Escopos padrão mínimos; ampliar exige decisão explícita.
- **INV-02** Nomes de ferramentas derivam das listas de `llm/tools/definitions.py`, menos as somente-chat (`chat_only_tool_names()`), que nunca são expostas via MCP.
- **INV-03** Nenhuma chamada MCP executa egress sem ação explícita do usuário na UI do Laya.

## Referências
Testes: `test_mcp_http.py`, `test_agent_mcp_wiring.py`, `test_isolation.py`, `test_egress_mcp_confirmation.py`.

## Lacunas
- ~~**GAP-01**~~ **Fechado** (`imp-local-security-hardening`): `confirm_egress` é somente-chat e egress via MCP exige confirmação humana na UI (RF-03, RF-07).
- **GAP-02** `GET /mcp/token/reveal` sem autenticação além de loopback (SEC-10).
