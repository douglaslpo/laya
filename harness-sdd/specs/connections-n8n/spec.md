# Spec: Conexões, OAuth e sincronização de workflows n8n

**Status:** baseline · **Donos:** `engine/laya/egress/{connections,oauth}.py`, `engine/laya/integrations/`, `engine/laya/security/n8n_link.py`, `n8n/workflows/`, `ui/src-tauri/src/n8n.rs`

## Requisitos
- **RF-01** O shell Tauri instala/inicia o n8n em `127.0.0.1:45678` com telemetria desligada; um n8n órfão só é morto se sua linha de comando contiver `laya` (senão reporta conflito de porta).
- **RF-02** O bootstrap cria o owner com senha aleatória (keychain `n8n_admin`) e uma API key com os escopos informados pelo n8n. Antes de implantar qualquer workflow (`_ensure_error_handler_workflow`, `import_workflows`/`_propagate_to_clones`), `ensure_link_credential()` garante a credencial singleton `httpHeaderAuth` **"Laya Engine Link"** (`name="X-Laya-Link-Token"`, `value=<segredo do elo>`); o id e um fingerprint do segredo ficam em `~/.laya/data/workflow_versions.json` (`__link_credential_id__`/`__link_credential_fp__`) — arquivo de metadados do engine, não uma tabela do banco; o segredo em si nunca é gravado ali. É idempotente; recria (e remove cópias antigas) se ausente ou divergente, e nesse caso re-aponta todos os clones mesmo sem bump de versão. Se a credencial não puder ser garantida, nada é implantado e o retry em background tenta de novo.
- **RF-03** `create_connection`: valida credenciais → grava no keychain (`laya-egress`, `{platform}:{connection_id}`) → cria credencial no n8n → clona workflows da plataforma (webhook com sufixo `-{short_id}`, credencial injetada, credencial do elo aplicada aos nós do elo, `errorWorkflow` só em ingestão, metadata `{platform}-config:{wf_id}`) → grava `egress_connections`.
- **RF-04** OAuth (Gmail, Calendar, Outlook, Outlook Calendar, Slack): PKCE S256 (exceto Slack), state CSRF de 10 min, troca de código, tokens no keychain, credencial no n8n, clones; falha no clone desfaz keychain e workflows.
- **RF-05** `refresh_access_token` atualiza keychain e `oauthTokenData` no n8n.
- **RF-06** No startup, `import_workflows` compara `meta.laya_version` dos templates com `~/.laya/data/workflow_versions.json` e propaga para os clones só quando a versão muda (ou quando a credencial do elo foi recriada), preservando nome, path do webhook e credencial da plataforma. Templates com clone que falhou mantêm a versão anterior registrada para serem re-tentados no próximo startup. Propagação completa sem falhas marca `settings.security.n8n_link.enforced=true` (ver `event-ingestion` RF-10); caso contrário inicia a janela de transição.
- **RF-07** Templates não são criados no n8n; só clones por conexão. O error handler é singleton.
- **RF-08** Elo autenticado engine↔n8n: segredo `laya_n8n_link_secret` gerado com `secrets.token_urlsafe(32)` e guardado só no keychain (`SERVICE_NAME="laya-engine"`). Nos templates, os nós HTTP Request para `/events` e `/ingestion-errors` (11 `*-ingestion.json` + `laya-error-handler.json`) usam `authentication: genericCredentialType`, `genericAuthType: httpHeaderAuth`; o Webhook dos 11 `*-executor.json` usa `authentication: headerAuth`. Ambos referenciam `credentials.httpHeaderAuth = {id: "__LAYA_LINK__", name: "Laya Engine Link"}`.
- **RF-09** Regra de injeção de credencial (clonagem em `connections.py::_clone_workflows_for_connection`, propagação em `n8n_bootstrap.py::_propagate_to_clones`, error handler e clone OAuth): nós do elo são identificados por `credentials.httpHeaderAuth.name == "Laya Engine Link"` (`is_link_node`) e recebem o id real via `apply_link_credential()`; a injeção da credencial da plataforma **pula** esses nós. O placeholder do elo **não** usa `id` igual ao tipo, porque `_merge_credentials` preencheria o placeholder pelo tipo do nó e poderia trazer a credencial da plataforma (ex.: `bitbucket_server`, também `httpHeaderAuth`).

## Critérios de aceitação
- **CA-01** Dado um template com versão nova, quando o engine inicia, então todos os clones daquela plataforma recebem o conteúdo novo com o mesmo path de webhook.
- **CA-02** Dado um template alterado sem bump de versão, então nada é propagado (e o guardrail G-N8N-02 falha no CI).
- **CA-03** Dado um callback OAuth cujo clone falha, então nenhum token fica no keychain e nenhum workflow órfão permanece.
- **CA-04** Dado um state OAuth expirado ou desconhecido, então o callback é rejeitado.
- **CA-05** Dado `n8n_node=""` numa plataforma HTTP genérica, então a credencial não é injetada em todos os nós.
- **CA-06** Dado um keychain vazio e n8n mockado, quando o provisionamento roda duas vezes, então o segredo (≥ 43 caracteres urlsafe) e a credencial "Laya Engine Link" são criados uma única vez (sem duplicata nem troca de segredo).
- **CA-07** Dado uma conexão `bitbucket_server` e uma `github`, quando clonadas e depois propagadas por bump, então os nós do elo referenciam "Laya Engine Link" e os nós de API referenciam a credencial da conexão; nenhuma sobrescreve a outra.
- **CA-08** Todos os templates carregam a autenticação do elo (teste estático `test_n8n_workflow_link_static.py`).

## Critérios de rejeição / casos-limite
- **CR-01** n8n indisponível no startup não bloqueia `/health` (provisionamento em background com retry de 10 min); o segredo do elo no keychain não é regenerado a cada tentativa.
- **CR-02** Falhas de transporte do cliente n8n viram `N8nApiError(503)`.
- **CR-03** Escopos Google devem ser os mesmos submetidos à verificação do Google.
- **CR-04** npm ≥ 12 exige `--allow-remote=all` ao instalar o n8n.
- **CR-05** Falha ao propagar algum clone mantém `enforced=false` (janela de transição limitada a 24 h) e o template é re-tentado no próximo startup.

## Invariantes
- **INV-01** Segredos só no keychain e no banco cifrado do n8n (inclui o segredo do elo: nunca em settings, logs, argv, env do n8n ou respostas de API).
- **INV-02** `_PLATFORM_HTTP_CRED_TYPES` idêntico em `oauth.py` e `n8n_bootstrap.py`.
- **INV-03** Metadata `-config:` sempre no space `default`.
- **INV-04** A credencial "Laya Engine Link" e a credencial da plataforma nunca se sobrescrevem em nenhum caminho de injeção (clone, propagação, error handler, OAuth).

## Referências
Testes: `test_connections.py`, `test_egress_connections.py`, `test_n8n_bootstrap.py`, `test_n8n_settings.py`, `test_keychain.py`, `test_n8n_link_auth.py`, `test_n8n_workflow_link_static.py`. Docs: `docs/n8n-data-persistence.md`, `engine/docs/oauth-app-distribution.md`, `engine/docs/egress-connection-broker.md`. Skill: `laya-n8n-workflows`.

## Lacunas
- **GAP-01** `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (SEC-07).
- **GAP-02** `client_secret` duplicado por conexão (SEC-11).
- **GAP-03** `_propagate_to_clones` preserva só o primeiro webhook.
- **GAP-04** `PLATFORMS` (integrations) e adapters de egress são registros paralelos sem teste de paridade.
