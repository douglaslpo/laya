# Spec: Pipeline de classificação e staging

**Status:** baseline · **Donos:** `engine/laya/pipeline/{ingest,space_resolution,rules,router,workers,stager,emit}.py`, `engine/laya/workers/`

## Contexto
Cada evento reivindicado pela fila passa por etapas determinísticas e LLM até virar um Action Card com ações sugeridas.

## Requisitos
- **RF-01** `run_ingest` determina a relação do ator com o usuário comparando com `team.json` (email → alias → handle → nome) e grava `events.actor_relationship`.
- **RF-02** `resolve_space` mapeia `source.connection_id` para um space via `sources.workflow_id`; sem correspondência, autodescobre no space `default`.
- **RF-03** `run_rules` avalia `rules.json` em ordem; a primeira regra que casa decide: `allow` segue, `drop` marca o evento `filtered` e emite `event_classified{filtered:true}`.
- **RF-04** `run_router` produz `RouterOutput` (`category` ∈ CODE/COMMS/PEOPLE/FINANCE/OPS; `persona` ∈ ENGINEER/COMMS/OPS/SALES/HR/FINANCE; `priority` ∈ LOW/MEDIUM/HIGH/CRITICAL; `confidence` 0–1; `entities`; `requires_research`; `secondary_persona`) com `temperature=0`, usando contexto relacionado, feedback, regras de classificação e correções.
- **RF-05** Se `requires_research`, cria um card provisório (`pending`, "Researching…", hora do evento), roda o worker da persona principal e, se houver, o da secundária com `prior_findings`.
- **RF-06** O worker ENGINEER gera `agent_prompt` e marca `card_status="ready"`; não inicia agente.
- **RF-07** Workers COMMS/HR/SALES/OPS/FINANCE seguem `PERSONA_SPECS` (n_results, role_aware, wrap_draft, fallback).
- **RF-08** `run_stager` (`temperature=0.2`) produz `ActionCardData`: `header` ≤ 80, `summary`, `intelligence_report`, `staged_output`, `suggested_actions`, `privacy_tier` 1–3, até 3 tags minúsculas, `context_match`.
- **RF-09** `run_emit` persiste o card (INSERT ou UPDATE do provisório), enfileira no Omni, faz carry-forward de grupo, auto-resolve irmãos ativos em evento terminal, embeda com `thread_context`, emite `card_created`/`card_updated`, resolve context group e entidades, grava audit e dispara follow-ups.

## Critérios de aceitação
- **CA-01** Dado um evento de bot e uma regra `drop` para bots, quando processado, então fica `filtered` e nenhum card é criado.
- **CA-02** Dado que o LLM do router devolve JSON inválido, então a classificação é `OPS/OPS/MEDIUM` com `confidence=0` e o pipeline continua.
- **CA-03** Dado que o LLM do stager devolve JSON inválido, então é criado um fallback card (o card não some).
- **CA-04** Dado uma ação sugerida para outra plataforma, então ela é descartada, exceto `gmail↔outlook`.
- **CA-05** Dado um evento terminal (ex.: `pr_merged`) de uma entidade com cards ativos, então os irmãos ativos vão para `done`.
- **CA-06** Dado um card emitido, então `card_created` é transmitido **antes** do context grouping e `card_updated{context_id}` depois.
- **CA-07** O `created_at` do card é a hora do evento; `group_active_at` do grupo nunca retrocede.

## Critérios de rejeição / casos-limite
- **CR-01** Exceção num worker vira `WorkerResult(error=…)`; não derruba o pipeline.
- **CR-02** Exceção no pipeline de workers marca o card provisório `failed` com `failed_stage='pipeline'` e relança para a fila.
- **CR-03** Ação malformada é descartada sem descartar o card.
- **CR-04** `privacy_tier` fora de 1–3 é limitado ao intervalo.
- **CR-05** Retry reutiliza o `card_id` existente (UPDATE, não INSERT).

## Invariantes
- **INV-01** `entity_id` = `LayaEvent.entity_id` (`{platform}:{subject.type}:{subject.id or event_id}`).
- **INV-02** Blocos de prompt por plataforma são incluídos só para as plataformas presentes (`build_router_system_prompt`, `build_stager_system_prompt`).
- **INV-03** Conteúdo do evento entra no prompt entre delimitadores de conteúdo não confiável.
- **INV-04** Toda chamada passa por `llm_call` (audit, orçamento, retry).

## Referências
Código: arquivos acima, `llm/prompts/{router,stager,engineer,comms,ops,sales,hr,finance}.py`, `models/classification.py`, `models/card.py`. Testes: `test_ingest.py`, `test_rules.py`, `test_router.py`, `test_router_prompt.py`, `test_workers.py`, `test_stager.py`, `test_stager_prompt.py`, `test_emit.py`, `test_integration_pipeline.py`. Docs: `engine/docs/pipeline-lifecycle.md`.

## Lacunas
- **GAP-01** Workers de persona chamam `llm_call` sem `space_id` → ignoram o modelo configurado no space.
- **GAP-02** `privacy_tier` e `privacy.tier3_*` não restringem envio de conteúdo a modelos em nuvem (SEC-06).
- **GAP-03** Docstring de `resolve_space` diz retornar `None` para `connection_id` nulo; retorna `"default"`.
