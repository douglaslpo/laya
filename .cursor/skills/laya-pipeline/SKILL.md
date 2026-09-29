---
name: laya-pipeline
description: Guia para modificar o pipeline de eventos do Laya (queue, router, workers/personas, stager, emit, pós-emit, learners, budget) e os prompts/chamadas LLM. Use ao alterar classificação, staging de ações, personas, prompts em engine/laya/llm/prompts, llm_call, retries da fila ou etapas pós-emit.
---

# Pipeline de eventos e LLM

## Mapa

`engine/laya/pipeline/queue.py::process_event` orquestra: `_claim_event` → `run_ingest` → `resolve_space` → `run_rules` → router (cache de batch → `router_output` persistido → `run_router`) → `_run_workers_pipeline` (se `requires_research`) ou `_run_simple_pipeline` → `run_stager` → `run_emit` → `_mark_completed`.

Falhas: `attempts < max_retry_attempts` → `retrying` com backoff `min(2**n, 300)`; senão `dead` + broadcast `audit_failure`.

## Checklist ao mudar uma etapa

```
- [ ] Entrada/saída tipadas pelos modelos em engine/laya/models/ (RouterOutput, ActionCardData, WorkerResult)
- [ ] Parse falho degrada (fallback) — transporte falho propaga para a fila
- [ ] llm_call(role=..., space_id=...) — passe space_id
- [ ] Prompt condicional gateado por plataforma/intenção
- [ ] Nenhum status escrito fora de transition_card_status
- [ ] Custo registrado (audit_log via llm_call) e STEP_TO_FEATURE atualizado se for etapa nova
- [ ] Teste com llm_call mockado (tests/test_<etapa>.py)
- [ ] Spec harness-sdd/specs/classification-pipeline/spec.md atualizada
```

## Adicionar uma persona

1. Enum `persona` em `models/classification.py`.
2. `PERSONA_SPECS` em `workers/persona.py` (`n_results`, `role_aware`, `wrap_draft`, fallback).
3. Prompt `llm/prompts/<persona>.py` + nome de override `~/.laya/prompts/<persona>.md` (lista no README).
4. Regras de desambiguação no prompt do router.
5. Cor da persona no Design System (`docs/design-system/foundations.md`) e em `lib/utils/cardVisuals.ts`.
6. Testes: `tests/test_workers.py`, `tests/test_router_prompt.py`.

## Prompts

- Um módulo por papel em `engine/laya/llm/prompts/`. Overrides do usuário em `~/.laya/prompts/<nome>.md` substituem por completo; `POST /prompts/reload`.
- Montagem dinâmica: `build_router_system_prompt(platforms)`, `build_stager_system_prompt(platform)`, `llm/tools/definitions.select_chat_tools()`. Siga o padrão para qualquer bloco novo.
- Data/hora vai na **última mensagem do usuário**, não no system prompt (cache de prompt).
- Conteúdo de terceiros entre delimitadores de conteúdo não confiável.
- Golden tests de tamanho/gating: `test_router_prompt.py`, `test_stager_prompt.py`, `test_tool_gating.py`.

## `llm_call`

`llm/client.py::llm_call(role, …, space_id=None)`: resolve modelo (space → global → fallback), prefixa provedor (`claude*`→`anthropic/`, `gpt|o1|o3|o4`→`openai/`, `gemini*`→`gemini/`, `{provider_id}/…` custom, `agent/<id>/<model>` backend de agente), tenacity 1–30 s sem retry em 4xx determinístico, recupera JSON truncado ou dobra `max_tokens` até o teto, registra audit e checa orçamento.

## Pós-emit

`_trigger_followups` (via `laya.tasks.create_task`): group summary (só carry-forward, debounce 15 s), daily summary (debounce 90 s, até 10 cards), processing rules (semáforo 4). Omni consome `omni_queue` a cada 10 s sem LLM; ressíntese agendada em chunks de 40.

## Armadilhas conhecidas

- Workers de persona chamam `llm_call` **sem** `space_id` (usam modelo global) — dívida.
- Reopen de card com `failed_stage='pipeline'` vai para `pending` sem reenfileirar o evento (use `/reprocess`).
- Pausar space não drena a fila já enfileirada.
- `privacy_tier`/`tier3_*` não restringem envio a cloud (SEC-06).
- Retry não repete o router; reprocess limpa `router_output` de propósito.
- Broadcast acontece **antes** do context grouping.
