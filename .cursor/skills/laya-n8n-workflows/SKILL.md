---
name: laya-n8n-workflows
description: Como criar e alterar workflows n8n empacotados do Laya (ingestão → LayaEvent → POST /events; executores por action_type), versionamento meta.laya_version, clonagem por conexão e sync de versões. Use ao editar n8n/workflows/*.json, normalização de eventos de uma plataforma, n8n_bootstrap.py ou quando um evento chega com campos errados.
---

# Workflows n8n

## Tipos

| Tipo | Forma | Saída |
|---|---|---|
| `<plataforma>-ingestion.json` | `scheduleTrigger` ou trigger nativo → Code/HTTP → normalização | `POST {{$env.LAYA_ENGINE_URL}}/events` com `LayaEvent`; erros → `POST /ingestion-errors` |
| `<plataforma>-executor.json` | Webhook POST (`httpMethod`) → Switch `action_type` → HTTP/nó nativo | `respondToWebhook` `{success, result{url|pr_url|message_url}, error}` |
| `laya-error-handler.json` | singleton (`__error_handler_id__`) | ligado só aos clones de ingestão |

## `LayaEvent` (resumo — completo em `docs/event-schema.md`)

```json
{
  "event_id": "jira:BUG-1234:comment:10042",
  "timestamp": "2026-09-29T12:00:00Z",
  "source": {"platform": "jira", "connection_id": "{{$workflow.id}}", "raw_event_type": "comment_created"},
  "actor": {"name": "Ana", "email": "ana@x.com", "platform_handle": "ana"},
  "subject": {"type": "issue", "id": "BUG-1234", "title": "NPE in PaymentService", "url": "https://…"},
  "content": {"body": "…", "attachments": [], "metadata": {}}
}
```

- `event_id` determinístico (reentrega é idempotente: `INSERT OR IGNORE`; evento `dead` volta à fila).
- `subject.type` casa `^[a-z][a-z0-9_]{0,31}$`; `subject.id` estável e não vazio (define o `entity_id` e o agrupamento).
- `source.connection_id` = id do workflow clonado (resolve o space).
- Tipos de evento terminais precisam bater com `terminal_event_types` do adapter.

## Ciclo de vida

1. Templates em `n8n/workflows/` **não** são criados no n8n; cada conexão gera **clones** (`connections.py`): webhook ganha sufixo `-{short_id}`, credencial injetada, metadata `{platform}-config:{wf_id}` gravada no space `default`, registro em `workflow_versions.json`.
2. No startup, `n8n_bootstrap.import_workflows` compara `meta.laya_version` do template com `~/.laya/data/workflow_versions.json` e só então propaga para os clones (`_propagate_to_clones`), preservando nome, path do webhook e credencial.

## Checklist de alteração

```
- [ ] Editar o JSON (preferir exportar do n8n e limpar ids de credencial para placeholders id == tipo)
- [ ] Bump meta.laya_version (AAAA.MM.N) — obrigatório
- [ ] Executor: ramos do Switch == capabilities do adapter
- [ ] scripts/guardrails-check.sh (valida JSON, formato e bump contra a branch base)
- [ ] pytest tests/test_egress_registry_parity.py tests/test_terminal_event_parity.py tests/test_n8n_bootstrap.py
- [ ] Testar ao vivo: reiniciar o app e confirmar que o clone recebeu a versão nova
```

## Armadilhas

- `_propagate_to_clones` preserva só o primeiro webhook do workflow.
- Webhook default `"calendar": "calendar-executor"` não existe como template; clones funcionam via tabela `sources`.
- Executores não recebem `errorWorkflow`; falhas aparecem em `action_cards.last_error`.
- Webhooks de executor e `/events` não têm autenticação (SEC-03).
- npm ≥ 12 exige `--allow-remote=all` para instalar o n8n (tarball do `xlsx`).
