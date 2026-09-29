# proposal: imp-local-security-hardening

## Objetivo

Fechar as três lacunas de segurança de severidade **Alta** documentadas em `.agents/security.md` — SEC-01 (cliente MCP confirma egress sem humano), SEC-02 (CSP nula + permissões de shell sem escopo no webview Tauri) e SEC-03 (`POST /events`, `POST /ingestion-errors` e webhooks de executor n8n sem autenticação) — sem quebrar a UX local-first e preservando o invariante de preview + confirmação humana de todo egress (decisão #28, `egress` INV-01, G-EGR-01). De carona, o segredo HMAC do token de egress deixa de ser derivado de `time.time_ns()` e passa a vir de CSPRNG com verificação em tempo constante (fecha também SEC-04 / `egress` GAP-02, porque o usuário o incluiu no escopo de SEC-01).

## Escopo

**Inclui:**

- **SEC-01 — gate humano para egress originado via MCP**
  - Contexto de origem da chamada de ferramenta (`chat` vs `mcp`) propagado por contextvar até os handlers de egress (padrão já usado por `current_space_id` em `mcp/http_server.py`).
  - `confirm_egress` fica fora da superfície MCP (não aparece em `list_tools` e `call_tool` é negado mesmo com escopo `egress=true`).
  - Ferramentas de egress chamadas via MCP geram preview + uma **solicitação de confirmação pendente** exibida na UI do Laya (broadcast WebSocket novo `egress_confirmation_request`); só o clique do usuário na UI executa (`POST /egress/pending/{request_id}/confirm`), com opção de rejeitar.
  - Tokens/solicitações pendentes vinculados à origem: token emitido no chat não é confirmável por MCP e solicitação MCP não é confirmável por `confirm_egress` do chat.
  - Segredo de assinatura por processo via `secrets.token_bytes(32)`; token com nonce aleatório (`secrets.token_urlsafe`) + assinatura HMAC-SHA256 verificada com `hmac.compare_digest` antes de consultar o store; uso único e TTL de 5 min preservados.
  - Auditoria `log_to_audit` com `source="mcp"` para execuções confirmadas na UI e registro de rejeições.
- **SEC-02 — webview Tauri**
  - CSP restritiva em `ui/src-tauri/tauri.conf.json` (`app.security.csp` e `devCsp`) compatível com a SPA: `connect-src` só para `http://127.0.0.1:8420` / `ws://127.0.0.1:8420` (e `localhost` equivalentes), `ipc:`/`http://ipc.localhost`; `script-src 'self'` (Tauri injeta hashes dos scripts inline do build); `img-src 'self' data: blob:`; `style-src 'self' 'unsafe-inline'` (Svelte usa `style=`), `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`; em dev, liberar Vite `http://localhost:5173` + HMR `ws://localhost:5173`.
  - Remover `shell:allow-execute`, `shell:allow-spawn` e `shell:allow-stdin-write` de `capabilities/default.json` — a exploração mostrou que o frontend só usa `open` de `@tauri-apps/plugin-shell` (`CardDetail.svelte`, `ConnectModal.svelte`) e que todos os processos (engine, n8n, uv, npm) são lançados pelo Rust via `std/tokio::process::Command`, não pelo plugin. `shell:allow-open` permanece com o escopo padrão (http/https/mailto).
  - Promover os `WARN` de SEC-02 em `scripts/guardrails_check.py` para `ERROR` (regressão passa a falhar).
- **SEC-03 — elo autenticado engine ↔ n8n**
  - Segredo compartilhado `laya_n8n_link_secret` gerado com `secrets.token_urlsafe(32)` e guardado no keychain (`laya-engine`), com helpers em `security/keychain.py` no padrão de `laya_mcp_bearer`.
  - Credencial n8n singleton do tipo `httpHeaderAuth` (nome fixo `Laya Engine Link`, header `X-Laya-Link-Token`) criada/atualizada pelo provisionamento (`n8n_bootstrap.py`), antes da propagação de workflows.
  - Engine exige o header em `POST /events` e `POST /ingestion-errors` (dependência FastAPI, `hmac.compare_digest`, 401 sem vazar detalhes).
  - Workflows de ingestão + `laya-error-handler.json` enviam o header via credencial (`genericCredentialType` + `httpHeaderAuth`); webhooks dos 11 executores passam a `authentication: headerAuth` com a mesma credencial; engine envia o header em `N8nBackend._post_to_n8n`.
  - Bump de `meta.laya_version` em todos os workflows alterados (G-N8N-01/02) para que `_propagate_to_clones` atualize clones existentes; clonagem (`connections.py`, `n8n_bootstrap.py`) injeta a credencial do elo e **não** a sobrescreve com a credencial da plataforma (colisão real: `bitbucket_server` usa `n8n_type = "httpHeaderAuth"`).
  - Caminho de migração para instalações existentes: janela de transição só até a primeira propagação bem-sucedida (flag persistida), depois enforcement permanente.
- Testes pytest (modo strict) e vitest; atualização das specs de baseline `egress`, `mcp-server`, `event-ingestion`, `connections-n8n`, de `.agents/security.md`, `docs/api-contracts.md` e `docs/guardrails.md`.

**Exclui:**

- SEC-04..SEC-12 como itens próprios — SEC-04 é fechado apenas no que se sobrepõe a SEC-01 (segredo HMAC); os demais ficam como follow-up: SEC-05 (env dos subprocessos de agentes), SEC-06 (`privacy.tier3_*`), SEC-07 (`N8N_BLOCK_ENV_ACCESS_IN_NODE=false`), SEC-08 (prompts no argv), SEC-09 (WebFetch/MCP de usuário), SEC-10 (`/mcp/token/reveal`), SEC-11 (`client_secret` duplicado), SEC-12 (`--full-auto`/`auto_edit`).
- Autenticação geral dos endpoints REST usados pela UI (`/egress/execute`, `/actions/execute`, `/egress/pending/*`, `/metadata/*`, `/repos`): continuam protegidos só por loopback + `TrustedHostMiddleware` + checagem de `Origin`. Um token de sessão da UI injetado pelo Tauri fica como follow-up (ver "Riscos residuais").
- Mudar o fluxo de confirmação do **chat interno** (continua: preview → usuário diz "sim" → LLM chama `confirm_egress`), exceto o vínculo de origem e o novo formato de token.
- Ferramenta MCP nova para consultar status da solicitação (questão em aberto abaixo).
- Migração de `@tauri-apps/plugin-shell` `open` para `tauri-plugin-opener`.
- Migration de banco: não é necessária (segredos no keychain, estado de transição em settings). Se a implementação precisar persistir solicitações pendentes, usar `073_*.sql` e revisar este proposal antes.

## Justificativa

As três lacunas transformam o modelo "loopback + humano no loop" em algo contornável: (1) um agente/cliente MCP com escopo `egress` — inclusive um alvo de prompt injection vinda de e-mail/Slack — pode enviar e-mails e comentar em tickets sem que o usuário veja nada; (2) qualquer XSS no webview vira execução arbitrária de comandos porque o plugin shell expõe `execute`/`spawn` sem escopo e não há CSP; (3) qualquer processo local pode injetar eventos (que viram cards e contexto de LLM — vetor de prompt injection persistente) ou disparar executores n8n diretamente, pulando preview, validação e auditoria. São os itens de maior severidade da dívida priorizada e já existem `WARN` no guardrails para SEC-02.

## Restrições

- **Mudança de contrato — requer aprovação explícita antes do `/harness:apply`** (regra `laya-core`): novo tipo WS `egress_confirmation_request` (+ `egress_confirmation_resolved`), novos endpoints `GET /egress/pending`, `POST /egress/pending/{request_id}/confirm|reject`, remoção de `confirm_egress` da superfície MCP (escopos MCP), capabilities Tauri reduzidas, CSP nova, header obrigatório em `POST /events`/`POST /ingestion-errors` e nos webhooks de executor.
- Escopos MCP padrão não mudam (`read` on, `write`/`egress` off — G-SEC-02, `mcp-server` INV-01).
- Segredos só no keychain e no banco cifrado do n8n (G-SEC-03, `connections-n8n` INV-01); nunca em `settings.json`, logs, argv, env do n8n ou respostas de API. O segredo do elo **não** pode ser passado ao n8n por variável de ambiente (`$env` é legível por expressões enquanto SEC-07 estiver aberto).
- Engine 100% async (G-ENG-01); background via `laya.tasks.create_task` (G-ENG-06); defesas não óbvias com comentário do porquê (G-ENG-12).
- Qualquer workflow alterado em `n8n/workflows/` exige bump de `meta.laya_version` (G-N8N-01/02); paridade Switch/capabilities intacta (G-N8N-03).
- `/health` e o startup não podem bloquear se o n8n estiver indisponível (`connections-n8n` CR-01).
- UI em Svelte 5 runes e tokens do Design System (G-UI-01/02/03); lógica pura em `lib/` com vitest (G-UI-04).
- `scripts/guardrails-check.sh` sem `ERROR` ao final.

## Riscos residuais e questões em aberto

- **Risco residual:** os endpoints REST da UI (incluindo o novo `POST /egress/pending/{id}/confirm`) não têm autenticação além de loopback/`Origin`. Um processo local não-navegador (ex.: agente CLI com shell) ainda poderia chamá-los. SEC-01 fecha o bypass **pelo protocolo MCP**; o fechamento completo exige token de sessão da UI (follow-up sugerido: SEC-13).
- **Questão 1:** um único segredo para as duas direções (proposto, por simplicidade de provisionamento) ou dois segredos separados (ingestão vs executor)?
- **Questão 2:** o cliente MCP precisa consultar o resultado da execução (ex.: ferramenta read-only `egress_request_status`)? Proposto: não nesta mudança; o resultado aparece na UI e no audit log.
- **Questão 3:** duração máxima da janela de transição na atualização (proposto: até a primeira propagação bem-sucedida dos clones ou no máximo 24 h após o primeiro startup da versão nova — timestamp persistido —, o que vier primeiro; cada requisição aceita sem header gera log `n8n_link_transition_accept`). Instalações novas (sem clones) não têm janela.
