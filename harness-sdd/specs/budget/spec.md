# Spec: Orçamento de LLM e de agentes

**Status:** baseline · **Donos:** `engine/laya/pipeline/{budget,agent_budget}.py`, `engine/laya/api/budget_api.py`

## Requisitos
- **RF-01** Custo mensal (fuso de `briefing.timezone`) calculado de `audit_log` × `MODEL_PRICING`; modelos desconhecidos (locais, agentes) custam $0; chamadas falhas também contam.
- **RF-02** `check_budget()` após cada `llm_call`: ao passar do teto, desativa todos os workflows de ingestão no n8n, registra em `budget_paused_workflows` e emite `budget_status`.
- **RF-03** Virada de mês gera snapshot em `monthly_costs` e retoma automaticamente; meses sem snapshot são recuperados no startup.
- **RF-04** `POST /budget/resume` retoma manualmente.
- **RF-05** Custos agregados por feature via `STEP_TO_FEATURE` (Pulse, Coherence, Omni, Chat, Briefing, Egress, System) para o dashboard.
- **RF-06** Budget de agentes por janela móvel: `settings.agent_budgets.agents[<id>] = {window_token_limit, window_hours: 5, pause_at_percent: 85}`; sinal nativo do Claude (`rate_limit_info`) é autoritativo.
- **RF-07** Ao atingir o limite de janela, pausa a ingestão até `paused_until`; o scheduler tenta retomar a cada 60 s; broadcast `agent_budget_status`; `POST /agent-budget/resume` manual.

## Critérios de aceitação
- **CA-01** Dado custo acumulado acima do teto, quando a próxima chamada termina, então os workflows de ingestão são desativados e a UI mostra o banner de orçamento.
- **CA-02** Dado o primeiro dia do mês seguinte, então os workflows pausados por orçamento são reativados.
- **CA-03** Dado um agente a 85 % da janela, então a ingestão pausa até o fim da janela e retoma sozinha.

## Critérios de rejeição / casos-limite
- **CR-01** Workflows pausados manualmente pelo usuário não são reativados pelo auto-resume: só os registrados em `budget_paused_workflows` (a tabela é esvaziada após o resume).
- **CR-02** Falha ao falar com o n8n durante a pausa não pode derrubar o pipeline de eventos.

## Referências
Testes: `test_agent_budget.py`, `test_dashboard_api.py`, `test_integration_dashboard.py`. UI: `ui/src/lib/stores/budget.ts`, banners em `ui/src/routes/+layout.svelte`.
