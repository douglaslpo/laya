# Guardrails do Laya

Guardrails são as regras que **não podem regredir**. Cada uma tem um ID, o motivo e como é garantida: **auto** (checada por `scripts/guardrails-check.sh` e pelo CI `guardrails.yml`), **teste** (coberta por teste existente), **regra** (regra do Cursor em `.cursor/rules/`) ou **revisão** (checklist humano).

Rodar localmente: `scripts/guardrails-check.sh`. `ERROR` falha; `WARN` é dívida conhecida, visível mas sem bloquear.

## 1. Engine

| ID | Regra | Motivo | Garantia |
|---|---|---|---|
| G-ENG-01 | Todo I/O é async (aiosqlite, httpx); nada bloqueante no event loop | Um único processo atende pipeline, API, WS e MCP | regra, revisão |
| G-ENG-02 | Escritas multi-etapa atômicas usam `async with db.sqlite.transaction()`; nada lento dentro | Conexão aiosqlite **compartilhada**: o `commit()` de uma task grava as escritas das outras | regra, revisão |
| G-ENG-03 | Status de card só muda via `transition_card_status` | Check-and-set atômico, validação do grafo e broadcast `card_updated` num lugar só. Exceções do próprio pipeline: reset do card provisório e recuperação em massa no startup (`pipeline/queue.py`) e o hot path `_persist_card` (`pipeline/emit.py`) | auto (WARN para a dívida em `api/cards_agent.py` e `mark_card_done` em `api/cards_lifecycle.py`) |
| G-ENG-04 | Timestamps no banco em `YYYY-MM-DD HH:MM:SS` UTC via `db/timeutil.py` | `T` do `isoformat()` quebra comparação lexicográfica (migration 071) | regra |
| G-ENG-05 | Card carrega a hora do **evento**; `group_active_at` só avança | Decisão #85; ordenação do feed | teste |
| G-ENG-06 | Background tasks via `laya.tasks.create_task` | Shutdown cancela só tasks do app. Exceções (loops de vida longa) listadas em `CREATE_TASK_ALLOWLIST` | auto |
| G-ENG-07 | Primitivas de busca só em `laya/retrieval.py` | Stacks chat/trace/card-search tinham divergido (P7-1) | auto |
| G-ENG-08 | Rotas estáticas registradas antes de rotas `/{id}` | `/cards/grouped` e `/processing-rules/reorder` já quebraram (P1-3) | regra, revisão |
| G-ENG-09 | Blocos condicionais de prompt gateados por plataforma/intenção | Custo de tokens em janelas locais pequenas (P6) | teste (`test_tool_gating.py`, `test_router_prompt.py`, `test_stager_prompt.py`) |
| G-ENG-10 | Retry de evento reaproveita `router_output`; reprocess o limpa | Evita custo e reclassificação não determinística | teste |
| G-ENG-11 | `entity_id` só pela propriedade `LayaEvent.entity_id` | Grafia canônica única; senão grupos se fragmentam | revisão |
| G-ENG-12 | Workaround/defesa sempre com comentário do **porquê** | Evita redescobrir o problema | revisão |
| G-ENG-13 | Falhas de parse de LLM degradam (fallback card / `OPS` default); falhas de transporte propagam para a fila | Card nunca some; retry controlado pela fila | teste |
| G-ENG-14 | Chamadas LLM passam por `llm/client.py::llm_call` | Retry, clamp de `max_tokens`, audit, orçamento, backends de agente | revisão |

## 2. Banco de dados

| ID | Regra | Garantia |
|---|---|---|
| G-DB-01 | Migrations `NNN_snake_case.sql`, sequenciais, sem buraco nem duplicata (próxima: **073**) | auto |
| G-DB-02 | Arquivo de migration sem `BEGIN`/`COMMIT` e sem `CREATE TRIGGER` (o runner envolve em transação; triggers FTS vivem em `db/fts.py`) | auto |
| G-DB-03 | Trigger FTS de update observa só colunas indexadas (senão O(N²) em `group_active_at`) | revisão |
| G-DB-04 | Forward-fix sem backfill, salvo quando a correção é permanente (ex.: `entities`) | revisão |
| G-DB-05 | Nova tabela/coluna documentada em `docs/database-schema.md` | revisão |

## 3. UI

| ID | Regra | Garantia |
|---|---|---|
| G-UI-01 | Svelte 5 runes: sem `$:`, `export let`, `on:evento` | auto |
| G-UI-02 | Cores e superfícies por tokens do Design System; sem hex cru em componente novo | regra, revisão |
| G-UI-03 | Toda mudança visual validada em dark/light × glass on/off × paleta acessível × reduced motion | revisão (PR template) |
| G-UI-04 | Lógica pura extraída para `lib/` com teste vitest | regra |
| G-UI-05 | Timeline: cápsula nunca sai do horário real (overflow strip) | teste (`lib/timeline/*.test.ts`) |
| G-UI-06 | Feed em 3 colunas flex round-robin; `feed/+page.svelte` não volta a crescer | revisão |
| G-UI-07 | Markdown/HTML de terceiros só via `MarkdownRender` (DOMPurify); nada de `{@html}` cru | regra, revisão |
| G-UI-08 | Status nunca comunicado só por cor (ver `StatusDot`: forma por status) | revisão |
| G-UI-09 | Sem emoji como ícone | revisão (CONTRIBUTING) |

## 4. n8n e egress

| ID | Regra | Garantia |
|---|---|---|
| G-N8N-01 | Todo workflow tem `meta.laya_version` no formato `AAAA.MM.N` | auto |
| G-N8N-02 | Workflow alterado → versão bumpada em relação à branch base | auto (com git + `GUARDRAILS_BASE_REF`) |
| G-N8N-03 | Capabilities do adapter = Switch do executor; eventos terminais em paridade | teste (`test_egress_registry_parity.py`, `test_terminal_event_parity.py`) |
| G-EGR-01 | Nenhuma escrita externa sem preview + confirmação humana | revisão, regra |
| G-EGR-02 | `validate_payload` no ponto único de envio; erros bloqueiam | teste |
| G-EGR-03 | `connection_id` sem correspondência gera erro — nunca troca de conta em silêncio | teste |
| G-EGR-04 | Timeout de egress = resultado desconhecido, `retryable=False` | teste |
| G-EGR-05 | Nova plataforma segue o checklist da skill `laya-egress-platform` | revisão |

## 5. Segurança

Lacunas detalhadas em [.agents/security.md](../.agents/security.md) (SEC-01…SEC-12).

| ID | Regra | Garantia |
|---|---|---|
| G-SEC-01 | Engine/n8n só em loopback; `TrustedHostMiddleware` e CORS restritos | revisão |
| G-SEC-02 | Escopos MCP padrão: `read` on, `write`/`egress` off | revisão |
| G-SEC-03 | Segredos só no keychain; nunca em settings, logs, argv ou respostas | regra, revisão |
| G-SEC-04 | Conteúdo de terceiros é dado: delimitadores de conteúdo não confiável, sem ferramentas de escrita sem gate humano | regra, revisão |
| G-SEC-05 | CSP do webview e escopo de shell do Tauri (hoje abertos) | auto (WARN até SEC-02 ser resolvida) |
| G-SEC-06 | Testes nunca tocam keychain nem `HOME` reais | teste (conftest) |
| G-SEC-07 | Deps Python instaladas por lock com hashes; lock regenerado ao editar `requirements*.txt` | CI (`engine-deps.yml`) |

## 6. Testes

| ID | Regra | Garantia |
|---|---|---|
| G-TST-01 | Todo comportamento novo ou corrigido tem teste junto | revisão |
| G-TST-02 | Teste async com `@pytest.mark.asyncio` (modo strict) | pytest falha sem |
| G-TST-03 | Mocks de LLM via `llm_call`/`litellm.acompletion`; nenhum teste chama rede (exceto marker `network`) | revisão |
| G-TST-04 | CI por PR: guardrails + pytest + vitest + svelte-check | CI `guardrails.yml` |

## 7. Checklist de revisão (PR)

- [ ] `scripts/guardrails-check.sh` sem `ERROR`
- [ ] Testes escopados passam (ver `.agents/testing.md`)
- [ ] Transições de status via `transition_card_status`
- [ ] Migration nova com o próximo número e documentada
- [ ] Workflow n8n alterado com `laya_version` bumpada
- [ ] Nenhum caminho novo de escrita externa sem confirmação humana
- [ ] Nenhum segredo fora do keychain
- [ ] UI testada nos 4 modos de aparência + paleta acessível
- [ ] Workarounds comentados com o porquê
- [ ] Docs de contrato atualizados (`docs/`, `.agents/project-notes.md`, specs em `harness-sdd/specs/`)

## 8. Evolução

Para promover uma regra de **revisão** a **auto**, adicione a checagem em `scripts/guardrails_check.py` (stdlib apenas), calibre contra o código atual (baseline sem `ERROR`) e registre aqui. Dívida conhecida entra como `WARN` com allowlist explícita no script, nunca silenciada.
