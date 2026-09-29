# Spec: Agrupamento de contexto, entidades e aprendizado

**Status:** baseline · **Donos:** `engine/laya/pipeline/{context_grouping,context_presets,entity_resolution,learn,context_learn,learn_common,feedback}.py`

## Requisitos
- **RF-01** **Entity group**: cards com o mesmo `entity_id` formam um grupo com carry-forward; `group_active_at` = MAX do grupo e só avança.
- **RF-02** **Context group**: associação semântica entre plataformas. Usa `context_match` do stager quando presente; senão busca no ChromaDB e confirma com LLM.
- **RF-03** Presets de rigor `strict` / `balanced` / `lenient` sobrescrevem os limiares brutos; os brutos só valem em modo custom.
- **RF-04** Entity resolution em camadas liga referências entre plataformas (ex.: `BUG-1234` ↔ PR ↔ menção no Slack).
- **RF-05** O usuário pode vincular, desvincular e mesclar grupos (`/cards/groups/*`); essas escritas multi-etapa usam `transaction()`.
- **RF-06** `learn.py` extrai **regras de classificação** (persona/prioridade) a partir de correções quando o total pendente passa de `classification_rules_threshold` (15), em lotes, a cada 6 h; injeta no máximo 20 no router e consolida via LLM acima de 40.
- **RF-07** `context_learn.py` extrai **regras de contexto** (diretivas de agrupamento em linguagem natural) de correções de link/unlink (limiar 10) e as injeta no prompt de agrupamento; consolida acima do limite.
- **RF-08** Regras de contexto manuais e aprendidas são gerenciadas em `/context-rules`; regras de classificação em `/classification/rules`.

## Critérios de aceitação
- **CA-01** Dado dois eventos com o mesmo `entity_id`, então o segundo card entra no grupo do primeiro e `group_carried_forward` é emitido.
- **CA-02** Dado um card cujo `context_match` aponta um grupo existente, então ele entra nesse grupo sem busca vetorial.
- **CA-03** Dado 15 correções de classificação pendentes, quando o learner roda, então novas regras são criadas e as correções marcadas como processadas.
- **CA-04** Dado uma falha no meio de uma mescla de grupos, então nada é aplicado (rollback).
- **CA-05** Dado o preset `strict`, então os limiares efetivos são os do preset, não os de `settings.json`.

## Critérios de rejeição / casos-limite
- **CR-01** Correções mais antigas que `corrections_retention_days` (30) são descartadas.
- **CR-02** Crescimento de regras é limitado por consolidação (prompt do router/agrupamento não cresce sem teto).

## Invariantes
- **INV-01** Context group ≠ entity group ≠ tags.
- **INV-02** Regras de classificação ≠ regras de contexto ≠ regras de filtro ≠ processing rules.

## Referências
Testes: `test_emit.py`, `test_entity_resolution.py`, `test_context_presets.py`, `test_context_learn.py`, `test_learn_consolidation.py`, `test_context_rules_api.py`, `test_feedback.py`, `test_db_transaction.py`. Docs: `docs/tuning-parameters.md`.

## Lacunas
- **GAP-01** Tabela `entities` acumula duplicatas (`INSERT OR IGNORE` com UUID novo e sem UNIQUE) — P4-3.
- **GAP-02** `docs/tuning-parameters.md` não lista `classification_rules_max_injection` nem `classification_rules_consolidation_threshold`.
