# Segurança

Modelo: app desktop de usuário único, tudo em loopback, human-in-the-loop para qualquer escrita externa (decisão #28). Ameaças principais: **prompt injection** vinda de conteúdo de e-mail/Slack/tickets, **processos locais maliciosos** falando com portas locais, **exfiltração** via agentes CLI.

## Proteções existentes (não regredir)
- Engine e n8n só em `127.0.0.1`; `TrustedHostMiddleware` só loopback (anti DNS rebinding); CORS restrito a localhost/tauri.
- MCP: bearer `lyat_…` comparado com `hmac.compare_digest`; escopos padrão `read` on, `write`/`egress` off; config MCP dos agentes em arquivo temporário 0600 (fora do argv).
- Egress: validação obrigatória; token de confirmação do chat de uso único (5 min); timeout sem retry; `connection_id` sem fallback silencioso.
- Egress via MCP (ex-SEC-01, `imp-local-security-hardening`): origem da chamada no contextvar `tool_call_origin` (ausente = `mcp`, fail-closed); `confirm_egress` é somente-chat (fora de `list_tools`, negado em `call_tool`); egress pedido via MCP vira pendência confirmada só pelo usuário no `EgressConfirmModal` (`POST /egress/pending/{id}/confirm|reject`, `Origin` externo → 403; rejeição auditada como `egress_rejected`).
- Token de egress (ex-SEC-04): segredo por processo `secrets.token_bytes(32)`, token `egr_<nonce>.<sig>` (HMAC-SHA256, 128 bits), verificação com `hmac.compare_digest` antes do lookup, vínculo de origem, pendências só em memória (`egress/pending.py`).
- Webview Tauri (ex-SEC-02): `app.security.csp`/`devCsp` restritivas (`default-src 'self'`, `script-src 'self'` sem `'unsafe-eval'`, `connect-src` só self/IPC/engine em loopback, `img-src` sem origens remotas, `object-src 'none'`, `frame-ancestors 'none'`); do plugin shell resta só `shell:allow-open`. `dangerousDisableAssetCspModification: ["style-src"]` mantém `'unsafe-inline'` efetivo em `style-src` (hashes injetados o anulariam no CSP3); `script-src` segue com injeção do Tauri. `scripts/guardrails_check.py::check_tauri` falha com `ERROR` em qualquer regressão.
- Elo engine↔n8n (ex-SEC-03): segredo `laya_n8n_link_secret` no keychain espelhado na credencial n8n `httpHeaderAuth` "Laya Engine Link"; `POST /events` e `POST /ingestion-errors` exigem `X-Laya-Link-Token` (401 errado/ausente, 503 se o segredo estiver indisponível); webhooks de executor usam `headerAuth` e o engine envia o header. Janela de transição de no máximo 24 h só para requisições **sem** header em instalações antigas (`security.n8n_link.enforced`).
- OAuth: PKCE S256, state CSRF 10 min, rollback de keychain/workflows se o clone falhar.
- n8n: senha do owner aleatória (keychain), telemetria off, `N8N_LISTEN_ADDRESS=127.0.0.1`.
- Deps: instalação por lock com `--require-hashes --only-binary :all:`.
- Agentes como backend de inferência: cwd temporário vazio, ferramentas negadas, sandbox read-only.
- Research: `realpath` + `relative_to` em `~/.laya/tmp/research`.
- Delimitadores de conteúdo não confiável nos prompts (decisão #32); avaliação de gatilho de processing rule sem ferramentas.
- Testes nunca tocam o keychain real (keyring em memória) nem o `HOME` real.

## Lacunas conhecidas (tratar como dívida priorizada)
| ID | Severidade | Lacuna | Onde |
|---|---|---|---|
| SEC-05 | Média | Subprocessos de agentes herdam `os.environ` com chaves de LLM exportadas | `agents/subprocess_helper.py`, `security/keychain.py` |
| SEC-06 | Média | `privacy.tier3_*` definido mas nunca aplicado; `privacy_tier` não restringe envio a cloud | `config.py:55-58` |
| SEC-07 | Média | `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` expõe ambiente às expressões n8n | `ui/src-tauri/src/n8n.rs` |
| SEC-08 | Média | Prompts com conteúdo sensível no argv dos agentes (visível no `ps`) | `llm/agent_backend.py`, adaptadores |
| SEC-09 | Média | `WebFetch`/`WebSearch` sem restrição de domínio em research + MCP de usuário carregável (sem `--strict-mcp-config`) | `agents/claude_code.py`, `llm/agent_backend.py` |
| SEC-10 | Baixa | `GET /mcp/token/reveal` sem autenticação além de loopback | `api/mcp_api.py` |
| SEC-11 | Baixa | `client_secret` OAuth duplicado em cada conexão | `egress/oauth.py` |
| SEC-12 | Baixa | Codex retoma com `--full-auto`; Gemini research com `auto_edit` sem limite de diretório | `agents/codex_cli.py`, `agents/gemini_cli.py` |
| SEC-13 | Média | Endpoints REST da UI (incl. `POST /egress/pending/{id}/confirm`) protegidos só por loopback + checagem de `Origin`: um processo local que conheça o `request_id` (ou que envie requisições sem `Origin`) pode confirmar/rejeitar. Sugestão: token de sessão da UI emitido pelo shell Tauri | `api/egress_pending_api.py`, `api/origin_guard.py`, demais routers da UI |

SEC-01…SEC-04 foram resolvidos pela mudança `imp-local-security-hardening` (ver "Proteções existentes").

## Regras para mudanças
- Nunca adicionar caminho de escrita externa sem preview + confirmação humana explícita.
- Nunca ampliar escopos MCP padrão, capabilities Tauri ou modos de permissão de agentes sem aprovação.
- Segredos só no keychain; nunca em `settings.json`, logs, argv ou respostas de API (exceto fluxos de "reveal" explícitos).
- Conteúdo de terceiros é **dado**, não instrução: mantenha delimitadores e nunca dê ferramentas de escrita a etapas que leem conteúdo não confiável sem gate humano.
- Markdown renderizado passa por `DOMPurify` (`MarkdownRender.svelte`); não use `{@html}` sem sanitizar.
- Reporte de vulnerabilidades: `SECURITY.md`.
