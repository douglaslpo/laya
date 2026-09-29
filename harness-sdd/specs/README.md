# Specs de baseline do Laya

Estas specs descrevem o comportamento **atual** do sistema, obtido por engenharia reversa do código (setembro/2026). Servem como contrato para mudanças via SDD-AI: toda proposta em `harness-sdd/changes/<nome>/` deve indicar quais specs altera, e o `/harness:archive` sincroniza o resultado aqui.

## Convenções

- **RF-xx**: requisito funcional (o que o sistema faz).
- **CA-xx**: critério de aceitação verificável (Dado / Quando / Então).
- **CR-xx**: critério de rejeição ou caso-limite que deve ser tratado.
- **INV-xx**: invariante que nenhuma mudança pode quebrar sem decisão explícita.
- **GAP-xx**: divergência conhecida entre intenção e implementação (dívida, não requisito).
- Cada spec lista os arquivos de código e testes que a sustentam.

## Índice

| Capacidade | Spec | Resumo |
|---|---|---|
| Ingestão de eventos | [event-ingestion/spec.md](event-ingestion/spec.md) | `POST /events`, idempotência, fila durável, retries, dead events |
| Pipeline de classificação | [classification-pipeline/spec.md](classification-pipeline/spec.md) | ingest → space → rules → router → workers → stager → emit |
| Ciclo de vida do card | [card-lifecycle/spec.md](card-lifecycle/spec.md) | estados, transições, recuperação, reopen/reprocess |
| Egress | [egress/spec.md](egress/spec.md) | preview, confirmação, execução, contrato `Platform` |
| Conexões e n8n | [connections-n8n/spec.md](connections-n8n/spec.md) | credenciais, OAuth, clones de workflow, sync por versão |
| Agentes CLI | [coding-agents/spec.md](coding-agents/spec.md) | workspace, research, backend de inferência |
| Busca e chat | [retrieval-chat/spec.md](retrieval-chat/spec.md) | busca híbrida, chat com ferramentas, Coherence/trace |
| Agrupamento e aprendizado | [grouping-learning/spec.md](grouping-learning/spec.md) | context groups, entity groups, learners de classificação e contexto |
| Processing rules | [processing-rules/spec.md](processing-rules/spec.md) | automação sobre cards e firing log |
| Omni, resumos e briefing | [omni-summaries/spec.md](omni-summaries/spec.md) | Omni em 4 camadas, group/daily summary, briefing |
| Orçamento | [budget/spec.md](budget/spec.md) | teto mensal em $ e janela de uso de agentes |
| Servidor MCP | [mcp-server/spec.md](mcp-server/spec.md) | transportes, bearer, escopos, space |
| Spaces | [spaces/spec.md](spaces/spec.md) | contextos, fontes, modelos por space, pausa |
| UI do feed | [ui-feed/spec.md](ui-feed/spec.md) | visões card/list/timeline, filtros, tempo real |

## Fluxo

1. `/harness:propose` cria `harness-sdd/changes/<nome>/{proposal,design,tasks}.md` + `specs/` com o **delta** (requisitos adicionados/alterados/removidos, referenciando os IDs daqui).
2. `/harness:apply` → `/harness:test` → `/harness:verify` (valida CA/CR) → `/harness:review`.
3. `/harness:archive` incorpora o delta nesta pasta e grava `review.yaml` na pasta da spec afetada.
