# Spec: Ciclo de vida do Action Card

**Status:** baseline · **Dono:** `engine/laya/models/card_lifecycle.py`

## Estados e transições

| De | Para |
|---|---|
| `pending` | ready, dismissed, archived, done, agent_running, executing, failed |
| `ready` | requires_approval, dismissed, archived, done, agent_running, executing, failed |
| `requires_approval` | ready, dismissed, archived, done, executing |
| `agent_running` | ready, done, failed, dismissed, awaiting_input, executing |
| `awaiting_input` | ready, done, dismissed, agent_running |
| `executing` | done, failed |
| `done` | archived, agent_running |
| `failed` | ready, dismissed, archived, executing, agent_running |
| `dismissed` | ready, archived |
| `archived` | — |

`TERMINAL_STATUSES = {done, dismissed, archived}` (gravam `resolved_at`). `INACTIVE_STATUSES = TERMINAL ∪ {failed}`.

## Requisitos
- **RF-01** `transition_card_status(card_id, new_status, *, actor, reason, feedback_type, failed_stage, last_error, save_previous, extra_fields, allow_restore)` valida a transição, aplica check-and-set (`UPDATE … WHERE card_id=? AND status=?`) e emite `card_updated`.
- **RF-02** Status não terminal e diferente de `failed` limpa `resolved_at`, `failed_stage` e `last_error`.
- **RF-03** `failed_stage` ∈ {`pipeline`, `action_execution`, `agent_spawn`, `agent_execution`}; `actor` ∈ {`user`, `processing_rule`, `agent`, `pipeline`, `executor`}.
- **RF-04** `/cards/{id}/reopen` restaura `previous_status` (ou `pending`) com `allow_restore=True`; `/cards/{id}/reprocess` limpa `router_output` e reenfileira o evento.
- **RF-05** No startup, `recover_stalled_cards`: `pending` com evento ainda re-tentável → apagado; `pending` com evento `dead`/`completed` → `failed/pipeline`; `agent_running` → `ready`; `executing` → `failed/action_execution`.
- **RF-06** O executor só aceita cards em `pending`, `ready`, `failed` ou `agent_running`, passa para `executing` e termina em `done` ou `failed/action_execution`.

## Critérios de aceitação
- **CA-01** Dado um card `ready`, quando o usuário o dispensa, então fica `dismissed`, com `resolved_at` preenchido, e `card_updated` é emitido.
- **CA-02** Dado um card `archived`, quando qualquer transição é pedida, então ela é rejeitada.
- **CA-03** Dado duas requisições concorrentes mudando o mesmo card, então só uma vence e a outra recebe `ValueError("Concurrent status change")`.
- **CA-04** Dado um card `failed`, quando reaberto para `ready`, então `failed_stage` e `last_error` são limpos.
- **CA-05** Dado o engine reiniciado com um card em `executing`, então ele vira `failed` com `failed_stage='action_execution'` (a ação pode ter saído ou não — o usuário decide).

## Critérios de rejeição / casos-limite
- **CR-01** Transição fora da tabela → erro, nenhum campo alterado.
- **CR-02** `allow_restore=True` só é aceito nos fluxos de reopen/reprocess.
- **CR-03** Egress que lança exceção vira `EgressResult(success=False)`; o card nunca fica preso em `executing`.

## Invariantes
- **INV-01** Toda mudança de status feita por usuário, regra, agente ou executor passa por `transition_card_status`. Exceções apenas do próprio pipeline: reset do card provisório e recuperação em massa (`pipeline/queue.py`) e `_persist_card` (`pipeline/emit.py`).
- **INV-02** `failed` é inativo mas re-tentável; nunca é tratado como terminal.
- **INV-03** Limpeza por retenção só apaga cards em `archived`, `dismissed`, `done` ou `failed`.

## Referências
Código: `models/card_lifecycle.py`, `api/cards_lifecycle.py`, `api/cards_agent.py`, `pipeline/executor.py`, `pipeline/queue.py`. Testes: `test_card_move.py`, `test_cards_api.py`, `test_reprocess.py`, `test_executor.py`, `test_actions_api.py`. Guardrail: G-ENG-03.

## Lacunas
- **GAP-01** `api/cards_agent.py` (9 pontos) e `mark_card_done` em `api/cards_lifecycle.py` escrevem status direto, sem validação do grafo nem check-and-set.
- **GAP-02** Reopen de card `failed_stage='pipeline'` vai para `pending` sem reenfileirar o evento; no próximo startup volta a `failed`.
