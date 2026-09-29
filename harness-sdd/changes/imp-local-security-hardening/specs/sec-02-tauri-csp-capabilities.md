# specs: imp-local-security-hardening — SEC-02 (CSP e capabilities do webview Tauri)

Não há spec de baseline dedicada ao shell Tauri; esta mudança fecha **SEC-02** de `.agents/security.md` e os `WARN` correspondentes em `scripts/guardrails_check.py` (`check_tauri`). Guardrails: G-SEC-01, G-UI-07.

## Requisitos novos / alterados

- **RF-S2-01** `ui/src-tauri/tauri.conf.json` define `app.security.csp` (produção) e `app.security.devCsp` (dev) não nulos. Diretivas mínimas de produção:
  - `default-src 'self'`
  - `script-src 'self'` (Tauri injeta hashes/nonces dos scripts inline do bundle SvelteKit estático; sem `'unsafe-eval'`)
  - `style-src 'self' 'unsafe-inline'` (atributos `style=` do Svelte e data-URI em CSS inline)
  - `img-src 'self' data: blob: asset: http://asset.localhost`
  - `font-src 'self' data:`
  - `connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:8420 ws://127.0.0.1:8420 http://localhost:8420 ws://localhost:8420`
  - `object-src 'none'`, `base-uri 'self'`, `frame-ancestors 'none'`, `form-action 'none'`
  - `devCsp` acrescenta `http://localhost:5173 ws://localhost:5173` em `connect-src`/`script-src` para Vite/HMR.
  - Qualquer origem adicional detectada na verificação da implementação (ex.: URLs de provider self-hosted chamadas direto do webview em `routes/setup/+page.svelte`) deve ser justificada em comentário no design ou roteada pelo engine — não liberar `*`.
- **RF-S2-02** `ui/src-tauri/capabilities/default.json` não contém `shell:allow-execute`, `shell:allow-spawn` nem `shell:allow-stdin-write`. `shell:allow-open` permanece (usado por `CardDetail.svelte` e `ConnectModal.svelte`) com o escopo padrão do plugin (http/https/mailto).
- **RF-S2-03** `scripts/guardrails_check.py::check_tauri` reporta **ERROR** (não mais WARN) se a CSP for nula/ausente, se contiver `'unsafe-eval'` ou `*` em `script-src`/`connect-src`, ou se alguma das três permissões de shell voltar sem escopo.

## CA-01: CSP presente e restritiva

**Given** o `tauri.conf.json` após a mudança
**When** `scripts/guardrails-check.sh` roda
**Then** não há WARN/ERROR de CSP, e a CSP de produção contém `default-src 'self'`, `object-src 'none'` e `connect-src` limitado a `self`/IPC/engine em loopback.

## CA-02: app funciona com a CSP

**Given** o build de produção (`npm run build` + `cargo tauri build` ou `tauri dev` com `devCsp`)
**When** o usuário abre feed, chat, settings (incluindo conectar integração OAuth que chama `open`), timeline, coherence (download via `blob:`), setup de provider e o modal de confirmação de egress
**Then** não há violações de CSP no console do webview, REST e WebSocket (`ws://127.0.0.1:8420/ws`) funcionam, imagens `data:`/`blob:` e GIFs de `lib/assets` carregam.

## CA-03: permissões de shell reduzidas

**Given** `capabilities/default.json`
**When** inspecionado (e `cargo check` em `ui/src-tauri`)
**Then** só `shell:allow-open` resta do plugin shell, o build compila e engine/n8n continuam sendo iniciados pelo Rust (`sidecar.rs`, `n8n.rs`) sem regressão.

## CA-04: links externos continuam abrindo

**Given** um card com URL `https://…` ou o fluxo OAuth do `ConnectModal`
**When** o usuário clica para abrir
**Then** o navegador do sistema abre a URL via `plugin-shell` `open`.

## CR-01: regressão de CSP falha o guardrail

**Given** alguém volta `"csp": null` ou adiciona `'unsafe-eval'`
**When** `scripts/guardrails-check.sh` roda
**Then** sai com `ERROR` e código de saída ≠ 0.

## CR-02: regressão de shell falha o guardrail

**Given** alguém readiciona `shell:allow-execute` (ou `spawn`/`stdin-write`) sem escopo
**When** `scripts/guardrails-check.sh` roda
**Then** sai com `ERROR`.

## CR-03: tentativa de executar comando pelo webview

**Given** código JS no webview chamando `Command.create('sh', …).execute()` do `@tauri-apps/plugin-shell`
**When** executado
**Then** o Tauri nega por falta de permissão (verificação manual/documentada no PR).

## CR-04: conexão a origem não listada

**Given** o webview tentando `fetch('https://evil.example')` ou `new WebSocket('ws://127.0.0.1:45678')`
**When** executado
**Then** a CSP bloqueia (verificação manual no DevTools do webview).

## Invariantes

- **INV-S2-01** Capabilities Tauri só diminuem nesta mudança; qualquer ampliação futura exige aprovação (regra `laya-security`).
- **INV-S2-02** Markdown de terceiros continua passando por `MarkdownRender`/DOMPurify (G-UI-07); a CSP é defesa em profundidade, não substituto.
