---
name: laya-egress-platform
description: Checklist passo a passo para adicionar ou alterar uma plataforma/conector no Laya (adapter Platform de egress, credenciais, OAuth, workflows n8n de ingestão e executor, UI e testes de paridade). Use quando o usuário pedir nova integração, nova ação externa (action_type), suporte on-prem, ou mudança em capabilities de GitHub/Jira/Slack/Gmail/etc.
---

# Adicionar / alterar plataforma

"Adicionar plataforma = 1 arquivo" vale para o **contrato de egress**; o conector completo toca ~12 pontos. Copie o checklist:

```
- [ ] 1. Adapter engine/laya/egress/platforms/<nome>.py (subclasse de Platform) + PLATFORM = XPlatform()
- [ ] 2. Registrar em _REGISTRY (e _DISPATCH se tiver enrichment) em platforms/__init__.py
- [ ] 3. Entrada em integrations/platforms.py (label, category, icon, n8n_type, n8n_node, oauth, workflows, fields…)
- [ ] 4. _validate_<nome> + ramo em connections._validate_credentials
- [ ] 5. OAuth (se aplicável): OAUTH_PROVIDERS, _PLATFORM_HTTP_CRED_TYPES (oauth.py E n8n_bootstrap.py), _PLATFORM_NODE_TYPES, node_type_map
- [ ] 6. n8n/workflows/<nome>-ingestion.json e <nome>-executor.json com meta.laya_version
- [ ] 7. DEFAULT_SETTINGS["n8n"]["webhooks"] em config.py
- [ ] 8. _PLATFORM_KEYWORDS (ordem: específico antes do genérico) e _FIELD_META se houver campos novos
- [ ] 9. Prompts: _CODE_PLATFORMS/_ISSUE_PLATFORMS (llm/prompts/router.py, stager.py) se couber
- [ ] 10. Casos fixos: registry.format_source_ref, enrichment.get_prefill_for_card, self_emails
- [ ] 11. UI: settings/PlatformIcon.svelte, lib/utils/cardVisuals.ts (cor + label), ActionCard/CardGroup se necessário
- [ ] 12. Testes: _PLATFORM_TO_WORKFLOW no teste de paridade, test_platform_interface.py, test_terminal_event_parity.py, test_egress_platforms.py
- [ ] 13. docs/event-schema.md, .agents/project-notes.md (lista de plataformas), spec harness-sdd/specs/egress/spec.md
```

## Contrato `Platform` (`egress/platforms/base.py`)

Obrigatórios: `name`, `capabilities: list[EgressCapability]`, `identifiers_from_event(action_type, event_id, content_metadata, event_row, self_emails=None) -> dict` (valor do engine vence o do LLM), `normalize_payload(action_type, payload) -> dict`, `validate_payload(action_type, payload) -> list[str]`.

Opcionais: `terminal_event_types`, `payload_credential_fields` (injeta campos da conexão no payload, ex. `{"server": "base_url"}`), `compose_guidance`, `body_field`, `draft_schema`, `chapter_default`, `polish_guidance`, `source_ref_config`, `platform_hint`.

`EgressCapability`: `action_type`, `label`, `requires_fields`, `optional_fields`, `content_fields` (o que o LLM emite), `optional_content_fields`, `description`, `confirmation_required=True`, `summary_template`, `warnings`, `impact` (low/medium/high).

Esqueleto:

```python
# SPDX-License-Identifier: Apache-2.0
from laya.egress.models import EgressCapability
from laya.egress.platforms.base import Platform


class AcmePlatform(Platform):
    name = "acme"
    terminal_event_types = frozenset({"ticket_closed"})
    capabilities = [
        EgressCapability(
            action_type="comment",
            label="Comment",
            requires_fields=["ticket_id", "body"],
            content_fields=["body"],
            summary_template="Comment on {ticket_id}",
            impact="low",
        ),
    ]

    def identifiers_from_event(self, action_type, event_id, content_metadata, event_row, self_emails=None):
        return {"ticket_id": content_metadata.get("ticket_id", "")}

    def normalize_payload(self, action_type, payload):
        payload.setdefault("body", payload.pop("text", ""))
        return payload

    def validate_payload(self, action_type, payload):
        return [f"missing {f}" for f in ("ticket_id", "body") if not payload.get(f)]


PLATFORM = AcmePlatform()
```

## Executor n8n

Webhook POST com `httpMethod` (o clone adiciona sufixo `-{short_id}`), Switch em `action_type` **idêntico** às capabilities, resposta via `respondToWebhook` `{success, result: {url}, error}`. Placeholders de credencial com `id == tipo`.

## Invariantes

- Preview e execução pelo mesmo `enrichment.py`.
- `connection_id` sem match → erro; nunca outra conta.
- Timeout → `retryable=False`.
- On-prem: dirigido por `host` (`GET /repos?host=`, metadata `{platform}-config:{workflow_id}`, `payload_credential_fields`) — sem predicados cloud-vs-server.

## Validar

```bash
cd engine && pytest tests/test_egress_platforms.py tests/test_platform_interface.py \
  tests/test_egress_registry_parity.py tests/test_terminal_event_parity.py tests/test_connections.py -v
scripts/guardrails-check.sh
```
