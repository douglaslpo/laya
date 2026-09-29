# Spec: Ingestão de eventos

**Status:** baseline · **Donos:** `engine/laya/api/events.py`, `engine/laya/pipeline/queue.py`

## Contexto
Workflows n8n de ingestão normalizam eventos de cada plataforma para o schema `LayaEvent` e os enviam ao engine. O engine aceita rápido, persiste e processa de forma assíncrona numa fila durável em SQLite.

## Requisitos
- **RF-01** `POST /events` aceita um `LayaEvent` válido e responde **202** sem processá-lo de forma síncrona.
- **RF-02** O evento é persistido em `events` com `raw_json` completo e `processing_status='queued'`.
- **RF-03** O consumidor busca eventos `queued` e `retrying` vencidos (`next_retry_at <= now`), `queued` primeiro, depois por `created_at`.
- **RF-04** Eventos são processados com concorrência limitada por `pipeline.max_concurrent_events` (padrão 4).
- **RF-05** Com mais de um evento na janela `event_batch_window_seconds`, o router pode classificar em lote (uma chamada LLM por space), exceto com provider local/agente ou disjuntor armado.
- **RF-06** Falha no processamento: `attempts < max_retry_attempts` (3) → `retrying` com backoff `min(2**attempts, 300)` s; senão `dead` + broadcast `audit_failure{kind:"dead_event"}`.
- **RF-07** `POST /events/dead/retry` zera tentativas, incrementa `manual_retries` e reenfileira.
- **RF-08** Erros do n8n chegam em `POST /ingestion-errors` e são coalescidos por fingerprint numa janela de 30 min.
- **RF-09** O reaper devolve para `retrying` eventos presos em `processing` há mais de 2× `model_timeout` e cancela a task correspondente.

## Critérios de aceitação
- **CA-01** Dado um `LayaEvent` válido, quando enviado a `POST /events`, então a resposta é 202 e existe uma linha em `events` com `processing_status='queued'`.
- **CA-02** Dado um `event_id` já `completed` ou `filtered`, quando reenviado, então nada muda (idempotência).
- **CA-03** Dado um `event_id` `dead`, quando reenviado pelo n8n, então volta para a fila.
- **CA-04** Dado um evento cuja etapa lança exceção de transporte, quando processado 3 vezes sem sucesso, então termina `dead` e um `audit_failure` é emitido.
- **CA-05** Dado um retry, quando o router já tem `router_output` persistido, então o router **não** é chamado de novo.
- **CA-06** Dado o engine reiniciado com eventos em `processing`, quando sobe, então eles voltam a `retrying` (`recover_stalled_events`).

## Critérios de rejeição / casos-limite
- **CR-01** Payload inválido (ex.: `subject.type` fora de `^[a-z][a-z0-9_]{0,31}$`) → 422, nada persistido.
- **CR-02** Campos de ator nulos são normalizados para `""`, não rejeitados.
- **CR-03** `subject.id` vazio → `entity_id` usa `event_id` (evita colapsar grupos).
- **CR-04** Uma task travada não pode bloquear o loop do consumidor (`asyncio.wait` com timeout de 30 s).
- **CR-05** Batch routing com resultado parcial ou exceção arma o disjuntor por 300 s e cai para roteamento individual.
- **CR-06** `CancelledError` marca falha e é relançado (não engolido).

## Invariantes
- **INV-01** Ingestão nunca chama LLM de forma síncrona na requisição HTTP.
- **INV-02** `_claim_event` é atômico (`UPDATE … WHERE processing_status IN ('queued','retrying')`).
- **INV-03** Estados de evento: `queued → processing → completed | filtered | retrying → dead`.

## Referências
Código: `api/events.py`, `api/ingestion_errors.py`, `pipeline/queue.py`, `models/event.py`. Testes: `test_ingest.py`, `test_queue_concurrency.py`, `test_batch_routing.py`, `test_dead_events.py`, `test_filtered_events.py`, `test_error_handling.py`, `test_integration_pipeline.py`. Docs: `docs/event-schema.md`, `docs/api-contracts.md`.

## Lacunas
- **GAP-01** `POST /events` não tem autenticação (SEC-03): qualquer processo local injeta eventos.
- **GAP-02** Pausar um space não drena eventos já enfileirados.
