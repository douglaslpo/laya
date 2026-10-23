# Validação manual — imp-local-security-hardening

> Checklist de validação ponta a ponta (T-10, T-11, T-21 e CA/CR manuais de SEC-01, SEC-02 e SEC-03). Execução pendente pelo usuário: marque cada item e cole evidências (print/log) no PR.
>
> Pré-requisitos: Rust/`cargo` instalados (não disponíveis no ambiente em que a mudança foi implementada), `engine/.venv` pronto, `ui/node_modules` instalado, n8n real provisionado pelo app.

## 0. Compilação do shell Tauri (pendente — cargo ausente no ambiente de implementação)

- [ ] `cd ui/src-tauri && cargo check` compila sem erros com as capabilities reduzidas (só `shell:allow-open` do plugin shell).
- [ ] `sidecar.rs` e `n8n.rs` continuam iniciando engine e n8n (o spawn é feito pelo Rust, não pelo webview).

## 1. CSP do webview (SEC-02 — CA-02, CR-04)

Abra o DevTools do webview (clique direito → Inspecionar, ou `Ctrl+Shift+I` no build de dev) e mantenha a aba **Console** filtrada por `Content-Security-Policy` / `Refused to`.

### 1.1 `tauri dev` (usa `devCsp`)

- [ ] `cd ui && npm run tauri dev` sobe sem violação de CSP na carga inicial (HMR do Vite em `localhost:5173` funcionando).
- [ ] **Feed**: cards carregam, GIFs/PNGs de `lib/assets` aparecem, atualização ao vivo pelo WebSocket `ws://127.0.0.1:8420/ws` funciona.
- [ ] **Chat**: enviar mensagem, receber streaming, renderização de markdown.
- [ ] **Settings → Integrações (OAuth)**: "Conectar" abre o navegador do sistema via `shell open` (CA-04) e o callback conclui.
- [ ] **Timeline**: navegação e carregamento sem erros.
- [ ] **Coherence**: download/exportação via `blob:` funciona.
- [ ] **Setup de provider** (`routes/setup`): teste de conexão com provider (as chamadas passam pelo engine; nenhuma chamada direta do webview a host externo).
- [ ] **Modal de egress** (ver seção 3) abre e fecha sem violação.
- [ ] Links externos de card (`CardDetail`) abrem no navegador do sistema.

### 1.2 Build de produção (usa `csp`)

- [ ] `cd ui && npm run build && npm run tauri build` conclui.
- [ ] Repetir todos os itens de 1.1 no app instalado/empacotado, sem violações no console.
- [ ] **Comportamento esperado novo**: imagens remotas em markdown de terceiros (ex.: `![](https://…)` num e-mail/ticket) **não** carregam — são bloqueadas por `img-src` (defesa contra rastreamento/exfiltração). Registrar no PR como mudança intencional, não regressão.

### 1.3 Bloqueios (CR-04, CR-03)

No console do DevTools:

- [ ] `fetch('https://evil.example')` → bloqueado pela CSP (`connect-src`).
- [ ] `new WebSocket('ws://127.0.0.1:45678')` → bloqueado pela CSP.
- [ ] `const { Command } = await import('@tauri-apps/plugin-shell'); await Command.create('sh', ['-c', 'id']).execute()` → **negado** pelo Tauri por falta de permissão (`shell.execute not allowed` ou equivalente). No build de produção, se o import dinâmico não estiver disponível, usar `window.__TAURI_INTERNALS__.invoke('plugin:shell|execute', {program: 'sh', args: ['-c','id'], options: {}})` → erro de permissão.

## 2. Guardrail de regressão (SEC-02 — CR-01, CR-02) — opcional, local

- [ ] Trocar temporariamente `"csp"` por `null` em `ui/src-tauri/tauri.conf.json` → `scripts/guardrails-check.sh` sai com `ERROR`. Reverter.
- [ ] Readicionar temporariamente `"shell:allow-execute"` em `capabilities/default.json` → `ERROR`. Reverter.

## 3. Confirmação humana de egress via MCP (SEC-01)

Preparação: Settings → MCP → habilitar escopo **egress** (e copiar o bearer `lyat_…`). Ter uma conexão Gmail válida. Usar um cliente MCP real (ex.: Claude Code/Cursor apontando para `http://127.0.0.1:8420/mcp/`) ou o MCP Inspector.

- [ ] `list_tools` **não** contém `confirm_egress` (com `read`/`write`/`egress` ligados).
- [ ] `call_tool("confirm_egress", {...})` → erro `METHOD_NOT_FOUND` dizendo que a confirmação é exclusiva da UI.
- [ ] `call_tool("send_email", {to: <seu e-mail>, subject: "teste SEC-01", body: "…"})` → resposta `status: "awaiting_user_confirmation"` com `request_id` (`egreq_…`) e **sem** `execute_token`; nenhum e-mail enviado ainda.
- [ ] O **modal de confirmação** aparece no app com resumo, detalhes, avisos, impacto e plataforma/conta.
- [ ] **Send** ("Enviar") → o e-mail chega; o modal fecha; `GET /egress/pending` fica vazio; Audit mostra `step=execute` com `source=mcp`.
- [ ] Repetir e clicar **Reject** ("Rejeitar") → nada é enviado; Audit mostra `step=egress_rejected` (`success=false`, `source=mcp`).
- [ ] Criar uma pendência, fechar/recarregar a UI (ou derrubar o WS) e reabrir → a pendência reaparece (UI recarrega `GET /egress/pending` ao reconectar).
- [ ] Esperar > 5 min sem responder → a pendência some da fila; `POST /egress/pending/<id>/confirm` responde **410**.
- [ ] `curl -X POST http://127.0.0.1:8420/egress/pending/<id>/confirm -H 'Origin: https://evil.example'` → **403** e a pendência continua na fila.
- [ ] `curl -X POST http://127.0.0.1:8420/egress/pending/egreq_inexistente/confirm` → **404**.
- [ ] Chat interno: pedir "envie um e-mail para …", confirmar no chat → executa normalmente e Audit registra `source=chat` (fluxo antigo preservado).
- [ ] Escopo `egress` desligado → `send_email` via MCP é negado e nenhum modal aparece.

### 3.1 Checagem visual do modal (G-UI-03)

Para cada combinação, verificar contraste, foco visível, legibilidade e ausência de sobreposição:

| Tema | Glass | Paleta acessível | Reduced motion | OK |
|---|---|---|---|---|
| dark | off | off | off | [ ] |
| dark | on | off | off | [ ] |
| dark | off | on | off | [ ] |
| dark | on | on | on | [ ] |
| light | off | off | off | [ ] |
| light | on | off | off | [ ] |
| light | off | on | off | [ ] |
| light | on | on | on | [ ] |

- [ ] Navegação só por teclado: `Tab` alterna entre Reject/Send; `Esc` **rejeita** a pendência (padrão seguro: nada é enviado e o Audit registra `egress_rejected`); leitor de tela anuncia o diálogo (`role=dialog`, `aria-modal`).
- [ ] Com reduced motion ligado, o modal aparece sem animação de entrada.

## 4. Elo autenticado engine ↔ n8n com n8n real (SEC-03 / T-21)

### 4.1 Instalação existente (migração)

Partir de uma instalação com conexões e clones criados **antes** desta branch (workflows sem autenticação, `security.n8n_link` ausente em `~/.laya/settings.json`).

- [ ] Subir o app com a branch → log do engine mostra criação da credencial "Laya Engine Link" e `n8n_template_version_changed` para os templates (versões `2026.09.x`).
- [ ] No n8n (`http://127.0.0.1:45678`): existe **uma** credencial "Laya Engine Link" (tipo Header Auth); os nós "POST to Laya Engine" dos clones de ingestão e o Webhook dos executores referenciam essa credencial; os nós de API continuam com a credencial da conexão (verificar especialmente um clone **Bitbucket Server**).
- [ ] Após a propagação: log `n8n_link_enforced reason=clones_propagated` e `~/.laya/settings.json` com `security.n8n_link.enforced = true` (e **sem** o segredo).
- [ ] Reiniciar o app → não cria credencial duplicada nem troca o segredo (idempotente).

### 4.2 Conexões novas

- [ ] Criar conexão **Gmail** (OAuth), **Slack** (OAuth) e **Bitbucket Server** (token/httpHeaderAuth) → clones criados com a credencial do elo nos nós do elo e a credencial da plataforma nos demais.

### 4.3 Ingestão e execução

- [ ] Gerar um evento real (e-mail recebido, mensagem no Slack, PR/comentário no Bitbucket Server) → evento chega ao feed (`POST /events` 202 no log, sem `n8n_link_rejected`).
- [ ] Aprovar uma ação de card (ex.: responder e-mail, comentar no PR) → executor n8n aceita o webhook e a ação é executada.
- [ ] Forçar um erro de ingestão (ex.: credencial inválida temporária) → aparece em `GET /ingestion-errors` (POST do error handler autenticado).

### 4.4 Rejeições

- [ ] `curl -i -X POST http://127.0.0.1:8420/events -H 'Content-Type: application/json' -H 'X-Laya-Link-Token: errado' -d '{}'` → **401** `{"detail":"unauthorized"}`; o log não contém o valor enviado.
- [ ] Mesmo `curl` **sem** o header (com `enforced=true`) → **401**.
- [ ] `curl -i -X POST http://127.0.0.1:8420/ingestion-errors -H 'X-Laya-Link-Token: errado' …` → **401**.
- [ ] `curl -i -X POST http://127.0.0.1:45678/webhook/<path-do-executor> -d '{}'` sem header → n8n recusa (401/403); nada executado.
- [ ] (Opcional) Apagar a credencial "Laya Engine Link" no n8n e reiniciar → engine recria e re-aponta os clones; ações voltam a executar. Enquanto divergente, a execução falha com "n8n executor rejected engine credentials — re-sync workflows" sem retry.
- [ ] (Opcional) Keychain indisponível → `POST /events` responde **503** e log `n8n_link_secret_unavailable`.

## 5. Registro

- [ ] Resultado de cada seção anotado no PR (incluindo o resultado de `cargo check` e prints do console sem violações de CSP).
