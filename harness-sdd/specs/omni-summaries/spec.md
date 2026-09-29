# Spec: Omni, resumos e briefing

**Status:** baseline · **Donos:** `engine/laya/pipeline/{omni,omni_change,group_summary,summarize,briefing}.py`, `engine/laya/scheduler.py`, `engine/laya/api/omni_api.py`

## Requisitos
- **RF-01** Omni responde "onde estou agora?" com quatro camadas temporais: Attention, Recent, Period, Milestone.
- **RF-02** Cada card emitido entra em `omni_queue`; um loop a cada 10 s adiciona à camada Recent **sem LLM**.
- **RF-03** Ressíntese com LLM (temperatura 0.3) roda no horário `omni.resynthesis_time` (17:00), a cada `rolling_interval_hours` (4) ou ao passar `event_threshold` (50) eventos, com cooldown de 10 min por space; processa em chunks de 40 cards.
- **RF-04** Snapshots são versionados (`omni_snapshots`, com `change_summary_json`); pins do usuário são preservados verbatim.
- **RF-05** Group summary rolling por entity group (debounce 15 s, só em carry-forward, forward-only).
- **RF-06** Daily summary por space (debounce 90 s, até 10 cards por chamada).
- **RF-07** Briefing diário em `briefing.time` (07:00), opcionalmente por space, gera um evento sintético e emite `briefing_ready`.

## Critérios de aceitação
- **CA-01** Dado um card novo, então em até ~10 s ele aparece na camada Recent sem chamada LLM.
- **CA-02** Dado uma ressíntese que devolve itens degenerados (`'...'`), então o resultado é rejeitado e o snapshot anterior permanece.
- **CA-03** Dado um pin, então ele sobrevive a qualquer ressíntese sem alteração.
- **CA-04** Dado uma ressíntese em andamento num space, então a fila daquele space espera (gate por space).
- **CA-05** Dado o engine iniciado depois das 17:00 sem ressíntese do dia, então o scheduler dispara (comparação `>=` com guarda por dia).

## Critérios de rejeição / casos-limite
- **CR-01** Reprocess de card não atualiza group/daily summary nem Omni.
- **CR-02** Cache de Omni é copiado profundamente antes de modificar.
- **CR-03** `_last_omni_date` é global no scheduler (senão o Omni para depois das 17h).

## Invariantes
- **INV-01** Síntese é sempre cruzada entre plataformas, nunca separada por plataforma (decisão #61).
- **INV-02** Restrições estruturais em vez de truncar tokens (JSON íntegro, decisão #60).

## Referências
Testes: `test_omni_api.py`, `test_omni_board_api.py`, `test_omni_change.py`, `test_omni_resynthesis.py`, `test_group_summary.py`, `test_summarize.py`, `test_briefing.py`, `test_scheduler.py`. UI: `ui/src/routes/omni`, `ui/src/lib/omni`, `ui/src/lib/components/omni`.
