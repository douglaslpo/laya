# Spec: Ingestão de eventos

**Status:** baseline · **Donos:** `engine/laya/api/events.py`, `engine/laya/pipeline/queue.py`

## Contexto
Workflows n8n de ingestão normalizam eventos de cada plataforma para o schema `LayaEvent` e os enviam ao engine. O engine aceita rápido, persiste e processa de forma assíncrona numa fila durável em SQLite.

## Requisitos
- **RF-01** `POST /events` aceita um `LayaEvent` válido e responde **202** sem processá-lo de forma síncrona. A rota exige o header `X-Laya-Link-Token` (dependência `require_n8n_link` em `security/n8n_link.py`), comparado com `hmac.compare_digest` ao segredo do elo engine↔n8n (keychain `laya_n8n_link_secret`).
- **RF-02** O evento é persistido em `events` com `raw_json` completo e `processing_status='queued'`.
- **RF-03** O consumidor busca eventos `queued` e `retrying` vencidos (`next_retry_at <= now`), `queued` primeiro, depois por `created_at`.
- **RF-04** Eventos são processados com concorrência limitada por `pipeline.max_concurrent_events` (padrão 4).
- **RF-05** Com mais de um evento na janela `event_batch_window_seconds`, o router pode classificar em lote (uma chamada LLM por space), exceto com provider local/agente ou disjuntor armado.
- **RF-06** Falha no processamento: `attempts < max_retry_attempts` (3) → `retrying` com backoff `min(2**attempts, 300)` s; senão `dead` + broadcast `audit_failure{kind:"dead_event"}`.
- **RF-07** `POST /events/dead/retry` zera tentativas, incrementa `manual_retries` e reenfileira.
- **RF-08** Erros do n8n chegam em `POST /ingestion-errors` (mesma autenticação `X-Laya-Link-Token` de RF-01) e são coalescidos por fingerprint numa janela de 30 min.
- **RF-09** O reaper devolve para `retrying` eventos presos em `processing` há mais de 2× `model_timeout` e cancela a task correspondente.
- **RF-10** Transição para instalações anteriores ao elo: enquanto `settings.security.n8n_link.enforced=false`, requisições **sem** header são aceitas e logadas como `n8n_link_transition_accept` (header presente e errado é sempre 401). `enforced` vira `true` (persistido) quando a propagação de clones conclui sem falhas (ou não há clones) **ou** 24 h após `transition_started_at` (a janela começa no provisionamento ou na primeira requisição sem header), o que ocorrer primeiro. Sem nenhuma linha em `sources` com `connection_id`, o startup marca `enforced=true` antes de depender do n8n (instalação nova). `enforced` é monotônico e o estado é do engine: `PUT /settings` ignora `security.n8n_link`. `settings.security.n8n_link` nunca contém o segredo.

## Critérios de aceitação
- **CA-01** Dado um `LayaEvent` válido e `X-Laya-Link-Token` correto, quando enviado a `POST /events`, então a resposta é 202 e existe uma linha em `events` com `processing_status='queued'`.
- **CA-02** Dado um `event_id` já `completed` ou `filtered`, quando reenviado, então nada muda (idempotência).
- **CA-03** Dado um `event_id` `dead`, quando reenviado pelo n8n, então volta para a fila.
- **CA-04** Dado um evento cuja etapa lança exceção de transporte, quando processado 3 vezes sem sucesso, então termina `dead` e um `audit_failure` é emitido.
- **CA-05** Dado um retry, quando o router já tem `router_output` persistido, então o router **não** é chamado de novo.
- **CA-06** Dado o engine reiniciado com eventos em `processing`, quando sobe, então eles voltam a `retrying` (`recover_stalled_events`).
- **CA-07** Dado uma instalação com clones antigos e `enforced=false`, quando o engine provisiona a credencial do elo e a propagação conclui sem falhas, então `enforced` passa a `true` e a próxima requisição sem header recebe 401.

## Critérios de rejeição / casos-limite
- **CR-01** Payload inválido (ex.: `subject.type` fora de `^[a-z][a-z0-9_]{0,31}$`) → 422, nada persistido.
- **CR-02** Campos de ator nulos são normalizados para `""`, não rejeitados.
- **CR-03** `subject.id` vazio → `entity_id` usa `event_id` (evita colapsar grupos).
- **CR-04** Uma task travada não pode bloquear o loop do consumidor (`asyncio.wait` com timeout de 30 s).
- **CR-05** Batch routing com resultado parcial ou exceção arma o disjuntor por 300 s e cai para roteamento individual.
- **CR-06** `CancelledError` marca falha e é relançado (não engolido).
- **CR-07** `POST /events` ou `POST /ingestion-errors` sem header (com `enforced=true`) ou com header errado (sempre) → **401** `{"detail":"unauthorized"}`, nada persistido, nenhum `enqueue_event`, valor recebido nunca logado.
- **CR-08** `enforced=false` e `transition_started_at` há ≥ 24 h → a flag é persistida como `true` e a requisição sem header recebe 401.
- **CR-09** Segredo do elo indisponível (falha do keychain / nunca provisionado) → **503** `{"detail":"engine link unavailable"}` (fail-closed) e log `n8n_link_secret_unavailable` sem dados sensíveis.

## Invariantes
- **INV-01** Ingestão nunca chama LLM de forma síncrona na requisição HTTP.
- **INV-02** `_claim_event` é atômico (`UPDATE … WHERE processing_status IN ('queued','retrying')`).
- **INV-03** Estados de evento: `queued → processing → completed | filtered | retrying → dead`.
- **INV-04** Nenhum evento ou erro de ingestão é persistido sem o segredo do elo, exceto na janela de transição de RF-10 e apenas para requisições sem header.

## Referências
Código: `api/events.py`, `api/ingestion_errors.py`, `security/n8n_link.py`, `pipeline/queue.py`, `models/event.py`. Testes: `test_ingest.py`, `test_n8n_link_auth.py`, `test_queue_concurrency.py`, `test_batch_routing.py`, `test_dead_events.py`, `test_filtered_events.py`, `test_error_handling.py`, `test_integration_pipeline.py`. Docs: `docs/event-schema.md`, `docs/api-contracts.md`.

## Lacunas
- ~~**GAP-01**~~ **Fechado** (`imp-local-security-hardening`): `POST /events` e `POST /ingestion-errors` exigem `X-Laya-Link-Token` (RF-01, RF-08, RF-10).
- **GAP-02** Pausar um space não drena eventos já enfileirados.
