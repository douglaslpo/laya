# Convenções e invariantes

Versão completa e justificada: [docs/guardrails.md](../docs/guardrails.md). Regras do Cursor: `.cursor/rules/laya-*.mdc`.

## Engine
1. **Async em tudo** (aiosqlite, httpx). Nada bloqueante no event loop.
2. **Uma conexão SQLite compartilhada.** Sequências de escrita que precisam ser atômicas usam `async with transaction():` (`db/sqlite.py`). Nada lento (rede/subprocess) dentro do bloco. O hot path `_persist_card` fica fora de propósito.
3. **Status de card só via `transition_card_status`** (check-and-set + broadcast). `allow_restore=True` só em reopen/reprocess.
4. **Timestamps** `YYYY-MM-DD HH:MM:SS` UTC via `db/timeutil.py`. Card carrega a hora do **evento**; `group_active_at` só avança.
5. **`entity_id` canônico** = `LayaEvent.entity_id` (`{platform}:{subject.type}:{subject.id or event_id}`); correção de formato é do workflow n8n, não do emit.
6. **Background tasks** via `laya.tasks.create_task` (o shutdown cancela só as tasks do app).
7. **Retrieval** só por `laya/retrieval.py`.
8. **Rotas estáticas antes de `/{id}`** (`/cards/grouped`, `/processing-rules/reorder`, MCP legado antes do Mount `/mcp`).
9. **Prompts condicionais gateados** por plataforma/intenção; resultados de ferramenta do chat limitados (12K chars).
10. **Retry de evento não repete o router** (usa `router_output` persistido); reprocess limpa esse campo.
11. **Broadcast antes do context grouping** no emit (confirmação LLM é bloqueante).
12. **FTS**: trigger de update observa só colunas indexadas.
13. **Comentar workarounds**: todo hack/defesa leva comentário com o porquê e o que quebra sem ele.
14. **Migrations**: próximo número (073+), arquivo sem `BEGIN/COMMIT`/triggers (o runner envolve em transação), forward-fix sem backfill salvo quando necessário.
15. **Egress**: validação no ponto único (`validate_payload`), `connection_id` nunca troca de conta em silêncio, timeout = resultado desconhecido (sem retry).

## UI
1. Svelte 5 runes; props `let { … }: Props = $props()`; callbacks `onxxx`; eventos `onclick`.
2. Estado global em stores `svelte/store`; mensagens WS via `lastMessage` consumidas em `$effect`.
3. Cores e superfícies por **tokens** (`--color-laya-*`, `surface-*`, `--tl-*`, `--om-*`), nunca hex cru em componente novo. Ver `docs/design-system/`.
4. Lógica pura extraída para `lib/` com teste vitest; `feed/+page.svelte` não deve voltar a crescer (use `lib/feed`, `lib/utils/flip.ts`, `components/feed/`).
5. Timeline: **uma cápsula nunca sai do seu horário real** — o que não cabe vai para o overflow strip.
6. Feed: layout de 3 colunas flex com distribuição round-robin (não CSS columns).
7. Sem emoji como ícone na UI.

## n8n
1. Todo workflow alterado em `n8n/workflows/` → bump de `meta.laya_version` (`AAAA.MM.N`).
2. Placeholders de credencial com `id == tipo`; webhook de executor com `httpMethod`; ingestão posta em `{{$env.LAYA_ENGINE_URL}}/events`.
3. Capabilities do adapter e o Switch do executor devem bater (testes de paridade).

## Processo
- Specs de baseline em `harness-sdd/specs/`; mudanças novas via `/harness:propose` em `harness-sdd/changes/<nome>/`.
- Atualize `CLAUDE.md`/`docs/` quando mudar um contrato documentado (há drift conhecido: contagem de migrations, `event-schema.md` outbound, `tuning-parameters.md`).
