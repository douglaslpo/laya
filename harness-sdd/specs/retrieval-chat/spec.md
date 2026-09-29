# Spec: Busca híbrida, chat e Coherence

**Status:** baseline · **Donos:** `engine/laya/retrieval.py`, `engine/laya/db/{fts,chromadb_store}.py`, `engine/laya/pipeline/chat.py`, `engine/laya/llm/tools/`, `engine/laya/api/{chat_api,trace_api}.py`

## Requisitos
- **RF-01** Recuperação combina busca vetorial (ChromaDB `laya_memory`, filtros por `space_id`) e BM25 FTS5 (`cards_fts`, `events_fts`, tokenizer `porter unicode61`) via Reciprocal Rank Fusion.
- **RF-02** Sem FTS5 no SQLite, a busca lexical cai para `LIKE` (`fts_or_like`).
- **RF-03** `action_cards.thread_context` é indexado para que follow-ups curtos ("Aprovado.") sejam encontráveis pelas palavras do fio.
- **RF-04** O chat (`POST /chat` ou WS `chat_message`) monta contexto, seleciona grupos de ferramentas por palavras-chave (`select_chat_tools`) e executa até 20 iterações de ferramentas; resultados de ferramenta limitados a 12.000 caracteres.
- **RF-05** Streaming emite `chat_stream_start`, `chat_stream_chunk`, `chat_stream_tool`, `chat_stream_done`; título de conversa via `conversation_title_updated`.
- **RF-06** Ferramentas de regras permitem listar/criar/editar/excluir regras de filtro, classificação e processamento, com auditoria e broadcast `rules_changed`.
- **RF-07** Coherence (`POST /trace`) descobre ocorrências de uma entidade entre plataformas (RRF, filtro opcional por LLM, clustering union-find) e gera narrativa em streaming (`trace_*`); pode ser cancelado.
- **RF-08** Data/hora é injetada na última mensagem do usuário, não no system prompt.

## Critérios de aceitação
- **CA-01** Dado um termo exato (ex.: `BUG-1234`) presente só no texto, então o resultado aparece via BM25 mesmo com baixa similaridade vetorial.
- **CA-02** Dado um SQLite sem FTS5, então a busca retorna resultados via `LIKE` sem erro.
- **CA-03** Dado uma pergunta sem relação com regras, então as ferramentas de regras não são enviadas ao modelo.
- **CA-04** Dado uma ferramenta que retorna 50.000 caracteres, então o modelo recebe no máximo 12.000.
- **CA-05** Dado um trace em andamento, quando `POST /trace/cancel` é chamado, então a requisição do trace termina com 499 "Trace cancelled" e `trace_cancelled` é emitido.

## Critérios de rejeição / casos-limite
- **CR-01** Consultas com caracteres especiais de FTS5 são escapadas.
- **CR-02** Stopwords removidas antes do BM25 (`extract_keywords`).
- **CR-03** Esgotadas 20 iterações, o chat responde com o que tem (não entra em loop).

## Invariantes
- **INV-01** `extract_keywords`, `reciprocal_rank_fusion` e `fts_or_like` existem só em `laya/retrieval.py` (`db/fts.py` mantém stopwords próprias para evitar import circular).
- **INV-02** Nomes de ferramentas expostas ao MCP derivam de `read_tool_names`, `write_tool_names`, `egress_tool_names`.

## Referências
Testes: `test_retrieval.py`, `test_fts.py`, `test_chromadb.py`, `test_related_context.py`, `test_chat_api.py`, `test_integration_chat.py`, `test_tool_gating.py`, `test_trace_api.py`, `test_tool_call_audit.py`, `test_contact_tools.py`. Docs: `engine/docs/egress-chat-tools.md`, `engine/docs/rag-shortcomings.md` (referência geral de RAG).
