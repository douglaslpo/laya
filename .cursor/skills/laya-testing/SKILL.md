---
name: laya-testing
description: Escreve e roda testes no Laya — pytest-asyncio (modo strict) com fixtures do engine/tests/conftest.py, mocks de LLM/httpx/n8n/WebSocket, testes de API via ASGITransport, e vitest para lógica pura da UI. Use ao criar/corrigir testes, investigar teste falhando, ou escolher o comando escopado para uma mudança.
---

# Testes no Laya

Política e comandos: `.agents/testing.md` (execução **escopada** por padrão).

## Engine — esqueleto

```python
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import insert_test_card, insert_test_event


@pytest.mark.asyncio
class TestCardDone:
    async def test_marks_done_and_broadcasts(self, db):
        await insert_test_event(db, event_id="evt-1")
        await insert_test_card(db, card_id="card-1", event_id="evt-1", status="ready")

        from laya.main import app
        with patch("laya.models.card_lifecycle.manager.broadcast", new_callable=AsyncMock) as bc:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/cards/card-1/done")

        assert resp.status_code == 200
        row = await (await db.execute("SELECT status FROM action_cards WHERE card_id='card-1'")).fetchone()
        assert row["status"] == "done"
        bc.assert_awaited()
```

Assinaturas: `insert_test_event(db, event_id="evt_test", platform="jira", …, space_id=None)`, `insert_test_card(db, card_id="card_test", event_id="evt_test", priority="HIGH", persona="ENGINEER", category="CODE", status="pending", …)`. O broadcast de transição sai de `laya.models.card_lifecycle.manager`; outros módulos importam o próprio `manager` — patch sempre no módulo que chama.

## Mocks

| Alvo | Como |
|---|---|
| LLM numa etapa | `patch("laya.pipeline.<mod>.llm_call", new_callable=AsyncMock, return_value=...)` |
| LLM passando pelo client | `patch("litellm.acompletion", new_callable=AsyncMock, return_value=_make_mock_llm_response({...}))` + `patch("laya.llm.client.load_settings")` |
| ChromaDB | fixture `mock_chromadb` |
| team/rules/repos | fixtures `mock_team`, `mock_rules`, `mock_repos` |
| httpx / n8n | `mock_client = AsyncMock(); mock_client.__aenter__ = AsyncMock(return_value=mock_client); mock_client.__aexit__ = AsyncMock(return_value=False)`; `patch("laya.integrations.n8n_bootstrap.httpx.AsyncClient", return_value=mock_client)` |
| Egress n8n | `patch("laya.egress.backends.n8n.get_n8n_config")`, `patch("laya.egress.route_and_execute")` |
| Broadcast WS | `patch("<mod>.manager.broadcast", new_callable=AsyncMock)` |
| Agentes CLI | testar montagem de argv e parsing como funções puras — nunca spawn real |

## Regras

- `@pytest.mark.asyncio` sempre (modo strict); fixtures async com `@pytest_asyncio.fixture`.
- Nunca importe `laya` acima do bloco de isolamento do `conftest.py`.
- Sem rede; se inevitável, `@pytest.mark.network`.
- Novo módulo → `tests/test_<modulo>.py` no diretório plano.
- Teste de regressão de bug reproduz o bug antes da correção.

## UI — vitest

```ts
import { describe, expect, it } from 'vitest';
import type { ActionCard } from '$lib/api/types';
import { computeHasPending, computeTopPriority } from '$lib/feed/cardUpdateReducer';

describe('computeTopPriority', () => {
  it('escolhe a maior prioridade do grupo', () => {
    const cards = [
      { card_id: 'a', priority: 'LOW', status: 'ready' },
      { card_id: 'b', priority: 'CRITICAL', status: 'done' },
    ] as ActionCard[];
    expect(computeTopPriority(cards)).toBe('CRITICAL');
    expect(computeHasPending(cards)).toBeTypeOf('boolean');
  });
});
```

Leia o módulo antes (regras exatas de prioridade podem excluir cards inativos). Ambiente `node`, sem DOM: extraia a lógica do componente para `lib/` e teste lá.

## Comandos

```bash
cd engine && pytest tests/test_x.py -v                 # escopado
cd engine && pytest -m "not network"                   # completo (só se pedido/CI)
cd ui && npx vitest run src/lib/feed                   # escopado
cd ui && npm test && npm run check                     # completo UI
scripts/guardrails-check.sh
```
