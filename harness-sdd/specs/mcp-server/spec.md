# Spec: Servidor MCP

**Status:** baseline · **Donos:** `engine/laya/mcp/`, `engine/laya/api/mcp_api.py`

## Requisitos
- **RF-01** Transportes: `/mcp/sse` + `/mcp/messages/` (legado, usado pelos agentes) e Streamable HTTP em `/mcp/`; as rotas legadas são registradas antes do Mount.
- **RF-02** Autenticação bearer `lyat_…` guardada no keychain (`laya_mcp_bearer`), comparada com `hmac.compare_digest`; `mcp.auth_mode="none"` desliga.
- **RF-03** Escopos `read`, `write`, `egress` relidos a cada `list_tools`/`call_tool`; padrão `read=true`, `write=false`, `egress=false`.
- **RF-04** `space_id` via query string, propagado por contextvar.
- **RF-05** Sessões Streamable ociosas encerradas após 600 s.
- **RF-06** Gestão do token: `/mcp/config`, `/mcp/token/*`; `refresh` e `delete` rejeitam `Origin` externo.

## Critérios de aceitação
- **CA-01** Dado um token inválido, então a requisição MCP recebe 401.
- **CA-02** Dado `write=false`, então ferramentas de escrita não aparecem em `list_tools` e `call_tool` delas é negado.
- **CA-03** Dado uma mudança de escopo em Settings, então a próxima chamada já reflete o novo escopo (sem restart).
- **CA-04** Dado `?space_id=x`, então as ferramentas de leitura só retornam dados do space `x`.

## Critérios de rejeição / casos-limite
- **CR-01** Host não-loopback é rejeitado pelo `TrustedHostMiddleware` (a proteção DNS-rebinding do SDK está desligada e é compensada pelo middleware).

## Invariantes
- **INV-01** Escopos padrão mínimos; ampliar exige decisão explícita.
- **INV-02** Nomes de ferramentas derivam das listas de `llm/tools/definitions.py`.

## Referências
Testes: `test_mcp_http.py`, `test_agent_mcp_wiring.py`, `test_isolation.py`.

## Lacunas
- **GAP-01** Com `egress=true`, o cliente MCP pode chamar `confirm_egress` sozinho (SEC-01).
- **GAP-02** `GET /mcp/token/reveal` sem autenticação além de loopback (SEC-10).
