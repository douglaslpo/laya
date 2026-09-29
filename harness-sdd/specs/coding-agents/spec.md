# Spec: Agentes CLI (workspace, research e inferência)

**Status:** baseline · **Donos:** `engine/laya/agents/`, `engine/laya/llm/agent_backend.py`, `engine/laya/api/{cards_agent,workspace_api}.py`

## Requisitos
- **RF-01** Agentes suportados no workspace: `claude_code`, `gemini_cli`, `codex_cli`, `pi_cli`, `cursor_cli` (`AgentType`).
- **RF-02** Sessões têm estados `starting, running, awaiting_input, paused, completed, failed, cancelled` e eventos `agent_message, user_response, tool_call, file_read, file_write, approval_request, approval_response, status_change, error, questions_dismissed`, persistidos em `workspace_sessions`/`workspace_events`.
- **RF-03** Processos rodam via `create_subprocess_exec` (sem shell), `stdin=DEVNULL`, buffer de linha 10 MB, timeout de inatividade 300 s (não conta pausado), pausa SIGSTOP/SIGCONT, término SIGTERM→SIGKILL em 5 s; exit 143/-15 = cancelado.
- **RF-04** Research grava arquivos só sob `~/.laya/tmp/research`, validados por `realpath` + `relative_to`.
- **RF-05** MCP para agentes de workspace é passado em arquivo temporário 0600, com `--allowedTools` limitado aos escopos.
- **RF-06** `llm_call(model="agent/<id>/<model>")` roda a etapa num CLI instalado: cwd temporário vazio apagado ao final, ferramentas negadas, sem MCP, semáforo `agent_backend_concurrency`=3.
- **RF-07** Tier native (`claude_code`): schema via `--json-schema`. Tier best-effort (`codex_cli`, `gemini_cli`, `pi_cli`): schema em texto, extração com `raw_decode`, validação `jsonschema`, até 3 reenvios com o erro.
- **RF-08** Uso de agentes é medido por janela (`agent_budget.py`); ver spec `budget`.
- **RF-09** Na inicialização, sessões órfãs são recuperadas e arquivos de staging com mais de 24 h são limpos a cada hora.

## Critérios de aceitação
- **CA-01** Dado um modelo `agent/claude_code/sonnet`, quando uma etapa é chamada, então o subprocesso recebe `--disallowedTools` com os built-ins e roda num diretório vazio.
- **CA-02** Dado uma resposta best-effort inválida contra o schema, então há até 3 reenvios; esgotados, a chamada falha e é auditada como falha.
- **CA-03** Dado um caminho de research fora de `~/.laya/tmp/research` (inclusive via symlink), então a leitura é negada.
- **CA-04** Dado o Cursor Agent, então `--model` nunca é passado; modos `plan`/`ask` são somente leitura.
- **CA-05** Dado um agente sem saída por 300 s (não pausado), então a sessão é encerrada como falha.

## Critérios de rejeição / casos-limite
- **CR-01** `agent/<id>` sem modelo usa o padrão do agente; modelos com `/` no nome são preservados (split só nas duas primeiras barras).
- **CR-02** Binário com nome genérico (`agent` do Cursor) é validado por identidade antes de ser usado.
- **CR-03** Pausa não tem efeito no Windows (sem SIGSTOP) — documentado.

## Invariantes
- **INV-01** Backend de inferência nunca recebe ferramentas, MCP nem cwd com dados.
- **INV-02** Modos de permissão só são ampliados com decisão explícita.
- **INV-03** Engineer worker não inicia agente; só gera `agent_prompt`.

## Referências
Testes: `test_agent_backend.py`, `test_claude_code_adapter.py`, `test_cursor_cli_adapter.py`, `test_session_manager.py`, `test_agent_mcp_wiring.py`, `test_agent_detection.py`, `test_workspace_api.py`, `test_workspace_models.py`. Skill: `laya-coding-agents`.

## Lacunas
- **GAP-01** Subprocessos herdam `os.environ` com chaves de LLM (SEC-05).
- **GAP-02** Prompts com conteúdo sensível no argv (SEC-08).
- **GAP-03** `WebFetch`/`WebSearch` sem restrição de domínio em research; MCP de usuário carregável na inferência (SEC-09).
- **GAP-04** Codex retoma com `--full-auto`; Gemini research com `auto_edit` sem limite de diretório (SEC-12).
- **GAP-05** Fluxo de perguntas e respostas do agente sem verificação ao vivo (P4-26).
