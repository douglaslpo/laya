# Spec: Spaces

**Status:** baseline · **Donos:** `engine/laya/api/spaces_api.py`, `engine/laya/models/space.py`, `engine/laya/pipeline/space_resolution.py`

## Requisitos
- **RF-01** Um space agrupa fontes (`sources`, com `source_type` `ingestion` ou `executor` e `workflow_id`) e tem nome, posição, `is_default`, `paused`.
- **RF-02** Existe sempre o space `default` (`space_id='default'`), que não pode ser excluído.
- **RF-03** Modelos por papel podem ser sobrescritos por space (`router_model`, `stager_model`, `chat_model`, `trace_model`, `omni_model`) e o agente de código (`coding_agent`); resolução space → global → fallback.
- **RF-04** Chaves de API por space ficam no keychain (`space_api_keys` guarda só a referência).
- **RF-05** Repositórios por space (`space_repos`).
- **RF-06** `PUT /spaces/{id}/paused` desativa/reativa os workflows de ingestão do space no n8n.
- **RF-07** Excluir um space é uma operação multi-etapa em `transaction()`.
- **RF-08** `space_id` atravessa pipeline, busca, MCP, Omni, briefing e resumos diários.

## Critérios de aceitação
- **CA-01** Dado um evento cujo `connection_id` pertence ao space `work`, então o card é criado com `space_id='work'`.
- **CA-02** Dado um `stager_model` definido no space, então o stager daquele space usa esse modelo.
- **CA-03** Dado a exclusão de um space com falha no meio, então nada é removido.
- **CA-04** Dado um space pausado, então seus workflows de ingestão ficam inativos no n8n.

## Critérios de rejeição / casos-limite
- **CR-01** `connection_id` desconhecido → autodescoberta cria a fonte no space `default`.
- **CR-02** Exclusão do space `default` → rejeitada.

## Referências
Testes: `test_spaces_api.py`, `test_isolation.py`.

## Lacunas
- **GAP-01** Workers de persona ignoram o modelo do space (ver spec `classification-pipeline`, GAP-01).
- **GAP-02** Pausar não drena eventos já enfileirados.
