---
name: laya-db-migrations
description: Procedimento para mudar o schema SQLite do Laya (migrations numeradas, FTS5, transações na conexão compartilhada, timestamps canônicos, ChromaDB). Use ao criar tabela/coluna, escrever migration em engine/laya/db/migrations, mexer em db/fts.py, db/sqlite.py, ou quando houver dúvida sobre atomicidade de escritas.
---

# Migrations e dados

## Criar migration

1. Descubra o número: `scripts/guardrails-check.sh` imprime "Próxima migration: NNN".
2. Crie `engine/laya/db/migrations/NNN_descricao_snake.sql`.
3. Regras do arquivo:
   - sem `BEGIN`/`COMMIT` (o `db/migrate.py` envolve em transação com `schema_version`);
   - sem `CREATE TRIGGER` (triggers FTS em `db/fts.py`);
   - timestamps `YYYY-MM-DD HH:MM:SS` UTC;
   - SQLite não tem `ALTER COLUMN`: para trocar tipo/constraint, recrie a tabela.
4. Colunas novas de card → `CARD_SELECT_COLUMNS` em `api/cards_common.py` e modelos em `models/card.py`.
5. Documente em `docs/database-schema.md`.
6. Teste: a fixture `db` aplica tudo; rode os testes da feature + `tests/test_timestamp_canonical.py`, `tests/test_fts.py`.

Exemplo (recriar tabela para adicionar UNIQUE):

```sql
CREATE TABLE entities_new (
    entity_id TEXT PRIMARY KEY,
    canonical TEXT NOT NULL,
    platform TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    UNIQUE (canonical, platform)
);
INSERT OR IGNORE INTO entities_new SELECT entity_id, canonical, platform, created_at FROM entities;
DROP TABLE entities;
ALTER TABLE entities_new RENAME TO entities;
```

(Colunas ilustrativas — confira o schema real antes.)

## Atomicidade na conexão compartilhada

Há **uma** conexão aiosqlite para o processo inteiro: o `commit()` de qualquer task grava as escritas pendentes das outras. Para invariantes multi-escrita:

```python
from laya.db.sqlite import get_db, transaction

async with transaction():           # asyncio.Lock + commit/rollback
    db = await get_db()
    await db.execute("DELETE FROM context_group_members WHERE context_id = ?", (cid,))
    await db.execute("DELETE FROM context_groups WHERE context_id = ?", (cid,))
```

- Nada de rede/subprocess/LLM dentro do bloco.
- Não chame `commit()` dentro do bloco.
- O hot path `_persist_card` fica fora de propósito (throughput).

## Timestamps

`from laya.db.timeutil import db_now, db_ts, db_ts_from_epoch`. Nunca `datetime.isoformat()` em coluna comparada lexicograficamente.

## FTS5

`cards_fts(card_id, header, summary, intelligence, thread_context)`, `events_fts(event_id, subject_title, content_body)`, tokenizer `porter unicode61`, triggers `_ai/_ad/_au`, backfill quando vazia, fallback para `LIKE` sem FTS5 (`retrieval.fts_or_like`). Trigger de update observa só colunas indexadas. Nova coluna indexada → ajuste `db/fts.py` e o backfill.

## ChromaDB

Coleção `laya_memory` em `~/.laya/data/chromadb`; metadados `entity_id`, `entity_refs`, `space_id`, `tags`. Trocar modelo de embedding exige recriar a coleção.

## Dívidas conhecidas

- `entities` acumula duplicatas (P4-3): `INSERT OR IGNORE` com UUID novo e sem UNIQUE.
- `CLAUDE.md` e o plano de remediação citam contagens de migration desatualizadas.
