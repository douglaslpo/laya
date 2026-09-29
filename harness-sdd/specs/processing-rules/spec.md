# Spec: Processing rules

**Status:** baseline · **Donos:** `engine/laya/pipeline/processing_rules.py`, `engine/laya/models/processing_rules.py`, `engine/laya/api/processing_rules_api.py`

## Requisitos
- **RF-01** Regras são avaliadas após o emit de cada card (semáforo de 4), na ordem definida pelo usuário (`/processing-rules/reorder`).
- **RF-02** Condições: `field` + operador (`equals, not_equals, contains, not_contains, starts_with, ends_with, in, not_in, matches, gt, gte, lt, lte, exists, not_exists`), compostas por `all`, `any`, `not`; profundidade máxima 32.
- **RF-03** Ações: `set_status` (dismissed/archived/done), `set_priority`, `bookmark`, `run_entity_agent`, `execute_egress`, `send_notification`, `add_tag`.
- **RF-04** Limites por regra: `rate_limit`, `cooldown_secs`, `max_daily`; no máximo 5 disparos por card; `set_status` terminal interrompe as regras seguintes.
- **RF-05** Toda avaliação que dispara é registrada em `processing_rule_firings` com resultado `success`, `error` ou `skipped` e o motivo; consultável em `/processing-rules/firings` e `/{id}/history`.
- **RF-06** Após `processing_rules.auto_disable_threshold` (5) erros consecutivos, a regra é desativada e `processing_rule_auto_disabled` é emitido.
- **RF-07** `/processing-rules/preview-matches` mostra quais cards casariam sem executar.
- **RF-08** Regras com `space_id` NULL são globais.

## Critérios de aceitação
- **CA-01** Dado uma regra `set_status=dismissed` para um remetente, então cards desse remetente são dispensados com `actor='processing_rule'` e o firing é registrado como `success`.
- **CA-02** Dado 5 erros seguidos numa regra, então ela fica desativada.
- **CA-03** Dado uma regra em cooldown, então o firing é `skipped` com motivo.
- **CA-04** Dado duas regras e a primeira arquiva o card, então a segunda não é avaliada.

## Critérios de rejeição / casos-limite
- **CR-01** Erro numa regra é logado e nunca propaga para o pipeline.
- **CR-02** `run_entity_agent` usa lock por entidade (sem dois agentes para a mesma entidade).
- **CR-03** Condição com profundidade > 32 é rejeitada.
- **CR-04** Rota `/processing-rules/reorder` registrada antes de `/processing-rules/{id}`.

## Invariantes
- **INV-01** Mudanças de status feitas por regras passam por `transition_card_status`.
- **INV-02** `execute_egress` por regra continua sujeito às validações do egress.
- **INV-03** (Design IA, `engine/docs/ai-processing-rules.md`) avaliação de gatilho sem ferramentas; execução com whitelist; regras novas em dry-run.

## Referências
Testes: `test_processing_rules.py`, `test_firing_log_api.py`. Docs: `engine/docs/ai-processing-rules.md`.
