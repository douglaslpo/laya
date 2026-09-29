# Spec: Conexões, OAuth e sincronização de workflows n8n

**Status:** baseline · **Donos:** `engine/laya/egress/{connections,oauth}.py`, `engine/laya/integrations/`, `n8n/workflows/`, `ui/src-tauri/src/n8n.rs`

## Requisitos
- **RF-01** O shell Tauri instala/inicia o n8n em `127.0.0.1:45678` com telemetria desligada; um n8n órfão só é morto se sua linha de comando contiver `laya` (senão reporta conflito de porta).
- **RF-02** O bootstrap cria o owner com senha aleatória (keychain `n8n_admin`) e uma API key com os escopos informados pelo n8n.
- **RF-03** `create_connection`: valida credenciais → grava no keychain (`laya-egress`, `{platform}:{connection_id}`) → cria credencial no n8n → clona workflows da plataforma (webhook com sufixo `-{short_id}`, credencial injetada, `errorWorkflow` só em ingestão, metadata `{platform}-config:{wf_id}`) → grava `egress_connections`.
- **RF-04** OAuth (Gmail, Calendar, Outlook, Outlook Calendar, Slack): PKCE S256 (exceto Slack), state CSRF de 10 min, troca de código, tokens no keychain, credencial no n8n, clones; falha no clone desfaz keychain e workflows.
- **RF-05** `refresh_access_token` atualiza keychain e `oauthTokenData` no n8n.
- **RF-06** No startup, `import_workflows` compara `meta.laya_version` dos templates com `~/.laya/data/workflow_versions.json` e propaga para os clones só quando a versão muda, preservando nome, path do webhook e credencial.
- **RF-07** Templates não são criados no n8n; só clones por conexão. O error handler é singleton.

## Critérios de aceitação
- **CA-01** Dado um template com versão nova, quando o engine inicia, então todos os clones daquela plataforma recebem o conteúdo novo com o mesmo path de webhook.
- **CA-02** Dado um template alterado sem bump de versão, então nada é propagado (e o guardrail G-N8N-02 falha no CI).
- **CA-03** Dado um callback OAuth cujo clone falha, então nenhum token fica no keychain e nenhum workflow órfão permanece.
- **CA-04** Dado um state OAuth expirado ou desconhecido, então o callback é rejeitado.
- **CA-05** Dado `n8n_node=""` numa plataforma HTTP genérica, então a credencial não é injetada em todos os nós.

## Critérios de rejeição / casos-limite
- **CR-01** n8n indisponível no startup não bloqueia `/health` (provisionamento em background com retry de 10 min).
- **CR-02** Falhas de transporte do cliente n8n viram `N8nApiError(503)`.
- **CR-03** Escopos Google devem ser os mesmos submetidos à verificação do Google.
- **CR-04** npm ≥ 12 exige `--allow-remote=all` ao instalar o n8n.

## Invariantes
- **INV-01** Segredos só no keychain e no banco cifrado do n8n.
- **INV-02** `_PLATFORM_HTTP_CRED_TYPES` idêntico em `oauth.py` e `n8n_bootstrap.py`.
- **INV-03** Metadata `-config:` sempre no space `default`.

## Referências
Testes: `test_connections.py`, `test_egress_connections.py`, `test_n8n_bootstrap.py`, `test_n8n_settings.py`, `test_keychain.py`. Docs: `docs/n8n-data-persistence.md`, `engine/docs/oauth-app-distribution.md`, `engine/docs/egress-connection-broker.md`. Skill: `laya-n8n-workflows`.

## Lacunas
- **GAP-01** `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (SEC-07).
- **GAP-02** `client_secret` duplicado por conexão (SEC-11).
- **GAP-03** `_propagate_to_clones` preserva só o primeiro webhook.
- **GAP-04** `PLATFORMS` (integrations) e adapters de egress são registros paralelos sem teste de paridade.
