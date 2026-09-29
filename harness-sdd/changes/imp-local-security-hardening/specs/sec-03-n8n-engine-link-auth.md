# specs: imp-local-security-hardening — SEC-03 (elo autenticado engine ↔ n8n)

Baselines afetadas: `harness-sdd/specs/event-ingestion/spec.md` (RF-01, RF-08, CA-01, CR-01; fecha **GAP-01**), `harness-sdd/specs/egress/spec.md` (RF-05; fecha **GAP-04**), `harness-sdd/specs/connections-n8n/spec.md` (RF-02, RF-03, RF-06, CA-01, CR-01, INV-01). Guardrails: G-SEC-03, G-N8N-01, G-N8N-02, G-N8N-03, G-ENG-01, G-ENG-06, G-ENG-12.

## Requisitos novos / alterados

- **RF-S3-01** Segredo `laya_n8n_link_secret` gerado com `secrets.token_urlsafe(32)` na primeira necessidade e guardado no keychain (`SERVICE_NAME="laya-engine"`), via `store_/get_/ensure_n8n_link_secret` em `security/keychain.py`. Nunca em settings, logs, argv, env do n8n ou respostas de API.
- **RF-S3-02** (altera `connections-n8n` RF-02) O provisionamento garante uma credencial n8n singleton `httpHeaderAuth` chamada `Laya Engine Link` com `name="X-Laya-Link-Token"` e `value=<segredo>`; guarda o id em metadata do engine; recria/atualiza se ausente ou divergente. Ocorre **antes** de `import_workflows`/`_propagate_to_clones`.
- **RF-S3-03** (altera `event-ingestion` RF-01/RF-08) `POST /events` e `POST /ingestion-errors` exigem `X-Laya-Link-Token` igual ao segredo, comparado com `hmac.compare_digest`; ausente/errado → **401** `{"detail":"unauthorized"}` sem persistir nada e sem logar o valor recebido.
- **RF-S3-04** Workflows de ingestão (11 `*-ingestion.json`) e `laya-error-handler.json`: os nós HTTP Request que chamam `$env.LAYA_ENGINE_URL` em `/events` e `/ingestion-errors` usam `authentication: genericCredentialType`, `genericAuthType: httpHeaderAuth` e referência à credencial `Laya Engine Link` (placeholder no template).
- **RF-S3-05** (altera `egress` RF-05) Os nós Webhook dos 11 `*-executor.json` usam `authentication: headerAuth` com a credencial `Laya Engine Link`; `N8nBackend._post_to_n8n` envia `X-Laya-Link-Token`. Resposta 401/403 do n8n vira `success=False, retryable=False` com erro explícito ("n8n executor rejected engine credentials — re-sync workflows").
- **RF-S3-06** Todos os workflows alterados têm `meta.laya_version` incrementado (G-N8N-01/02), para que `_propagate_to_clones` atualize clones existentes preservando nome, path do webhook e credencial da plataforma (`connections-n8n` RF-06/CA-01).
- **RF-S3-07** A injeção de credencial na clonagem (`egress/connections.py::_clone_workflows_for_connection`) e na propagação (`n8n_bootstrap.py::_propagate_to_clones`) injeta a credencial do elo nos nós marcados e **nunca** sobrescreve a credencial `Laya Engine Link` com a credencial da plataforma — inclusive para `bitbucket_server`, cujo `n8n_type` também é `httpHeaderAuth`.
- **RF-S3-08** Transição para instalações existentes: enquanto `security.n8n_link.enforced` for `false`, o engine aceita requisições sem header (header **errado** é sempre rejeitado) e loga `n8n_link_transition_accept`; a flag vira `true` (persistida) após a primeira propagação bem-sucedida de todos os clones com as versões novas **ou** 24 h após `security.n8n_link.transition_started_at`, o que ocorrer primeiro. Instalação nova (sem clones) começa com `enforced=true`.

## CA-01: evento autenticado é aceito

**Given** o segredo provisionado e `enforced=true`
**When** `POST /events` recebe um `LayaEvent` válido com `X-Laya-Link-Token` correto
**Then** 202 e linha `queued` em `events` (preserva `event-ingestion` CA-01).

## CA-02: provisionamento cria segredo e credencial

**Given** um keychain em memória vazio e n8n mockado
**When** o provisionamento roda
**Then** o segredo é criado com comprimento ≥ 43 caracteres urlsafe, a credencial `Laya Engine Link` do tipo `httpHeaderAuth` é criada com esse valor, e uma segunda execução é idempotente (não cria duplicata nem troca o segredo).

## CA-03: templates carregam a autenticação

**Given** os JSONs em `n8n/workflows/`
**When** um teste estático os percorre
**Then** todo nó HTTP Request para `/events` ou `/ingestion-errors` usa `httpHeaderAuth` com a credencial `Laya Engine Link`, todo nó Webhook de executor tem `authentication: headerAuth`, e todos os arquivos alterados têm `meta.laya_version` maior que o da branch base.

## CA-04: clones recebem a credencial do elo sem perder a da plataforma

**Given** uma conexão `bitbucket_server` (credencial da plataforma também `httpHeaderAuth`) e uma conexão `github`
**When** os workflows são clonados e depois propagados por bump de versão
**Then** os nós de ingestão/webhook referenciam `Laya Engine Link` e os nós de API da plataforma referenciam a credencial da conexão; nenhuma das duas é sobrescrita pela outra.

## CA-05: engine autentica no executor

**Given** um `EgressRequest` confirmado e webhook do executor resolvido
**When** `N8nBackend._post_to_n8n` executa
**Then** a requisição httpx inclui `X-Laya-Link-Token` com o segredo (teste com `httpx` mockado).

## CA-06: migração de instalação existente

**Given** uma instalação com clones antigos (sem header), `enforced=false`
**When** o engine sobe, provisiona a credencial e `_propagate_to_clones` conclui com sucesso
**Then** `security.n8n_link.enforced` passa a `true` e a próxima requisição sem header recebe 401.

## CR-01: sem header ou header errado

**Given** `enforced=true`
**When** `POST /events` ou `POST /ingestion-errors` chega sem header ou com valor errado
**Then** 401, nada é persistido, nenhum `enqueue_event`, e o valor enviado não aparece em logs.

## CR-02: header errado durante a transição

**Given** `enforced=false`
**When** chega um header presente porém inválido
**Then** 401 (a transição só tolera **ausência** de header).

## CR-03: janela de transição expirada

**Given** `enforced=false` e `transition_started_at` há mais de 24 h
**When** chega requisição sem header
**Then** a flag é persistida como `true` e a resposta é 401.

## CR-04: n8n indisponível no startup

**Given** n8n fora do ar
**When** o engine sobe
**Then** `/health` responde normalmente, o provisionamento da credencial entra no retry em background existente (`connections-n8n` CR-01) e o segredo no keychain não é regenerado a cada tentativa.

## CR-05: keychain indisponível

**Given** o keychain falha ao ler/gravar o segredo
**When** chega `POST /events`
**Then** o engine responde 503 (fail-closed, não aceita sem autenticação) e loga `n8n_link_secret_unavailable` sem dados sensíveis.

## CR-06: executor rejeita credencial

**Given** o n8n responde 401/403 ao webhook do executor (clone desatualizado ou segredo divergente)
**When** a ação é executada
**Then** `success=False, retryable=False` com mensagem orientando re-sync; não há retry automático (preserva `egress` INV-03).

## CR-07: segredo fora de superfícies proibidas

**Given** qualquer execução dos testes
**When** se inspecionam `settings.json`, respostas de `/settings`, `/n8n/*`, logs capturados e o env passado ao n8n em `n8n.rs`
**Then** o segredo não aparece em nenhum deles.

## Invariantes

- **INV-S3-01** Nenhum evento é persistido nem executor disparado sem o segredo do elo, exceto na janela de transição documentada (RF-S3-08) e apenas para requisições sem header.
- **INV-S3-02** Segredos só no keychain e no banco cifrado do n8n (`connections-n8n` INV-01).
- **INV-S3-03** `_PLATFORM_HTTP_CRED_TYPES` continua idêntico em `oauth.py` e `n8n_bootstrap.py` (`connections-n8n` INV-02).
- **INV-S3-04** Capabilities dos adapters seguem batendo com os Switch dos executores (G-N8N-03).
