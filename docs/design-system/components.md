# Componentes

Todos em `ui/src/lib/components/`, Svelte 5 com runes. Props tipadas por `interface Props` + `$props()`; callbacks `onxxx`; `$bindable` só onde indicado.

## Primitivos (raiz)

| Componente | Props principais | Quando usar |
|---|---|---|
| `Dropdown` | `id`, `value` (**bindable**), `options {value,label,group?,description?,disabled?}[]`, `onchange`, `placeholder`, `variant 'select'\|'link'`, `size 'sm'\|'md'`, `compact`, `disabled`, `class` | Todo select. Portado para `body`, abre para cima sem espaço, teclado (setas, Enter, Esc, Tab), `role=listbox/option`, `aria-activedescendant` |
| `Titlebar` | snippets `nav`, `center`, `right`; `controlsDisabled` | Barra de 38 px com arraste, duplo clique maximiza, controles de janela no Windows/Linux (72 px reservados no macOS) |
| `MarkdownRender` | `content`, `copyText`, `class`, `showCopy` | Todo markdown/HTML de terceiros (marked + DOMPurify) |
| `PlatformBadge` | `platform` | Chip minúsculo de plataforma (`text-[8px] uppercase`) |
| `HealthBadge` | `status` | Ponto de saúde com `animate-ping` |
| `StartupScreen`, `UpdateBanner`, `VectorStoreBanner` | — | Estados globais do app |

## Feed (`feed/`)

| Componente | Props | Papel |
|---|---|---|
| `ActionCard` | `card`, `onselect`, `ondelete`, `onlink`, `selectedCardId`, `hasSelection`, `lastViewedCardId` | Card do feed (status por fundo + `StatusDot`, persona, prioridade, plataforma, tags) |
| `CardGroup` | grupo de cards | Pilha com "ghost strips" e `.card-stack-badge` |
| `CardDetail` | card selecionado | Painel de 420 px com ações, preview e confirmação |
| `ListGroup`, `ListRow` | — | Visão lista (container queries) |
| `StatusDot` | `status`, `size`, `errorMessage` | Indicador de status com **forma** por estado |
| `FilterPopover` | `open`, `pos`, `hasActiveFilters` | Filtros do feed |
| `RecentDrawer`, `SummaryModal`, `DaySummary`, `GroupSummaryDetail` | — | Painéis auxiliares |
| `BulkActionsDropdown`, `ClassificationDialog`, `LinkDialog`, `OriginalContentModal` | — | Ações sobre cards |
| `timeline/TimelineView`, `ThreadCapsule`, `TimelineControls`, `HeatRail`, `CalendarRail`, `OverflowStrip` | — | Visão timeline (geometria pura em `lib/timeline`) |

## Omni (`omni/`)

`OmniTooltip`; `board/`: `OmniIdentityBar`, `InstrumentCluster`, `AttentionLoad`, `CompressionGauge`, `CompressionFunnel`, `EventVolume`, `PlatformMix`, `TriageColumn`, `ChangelogRail`, `VersionPicker`; `item/`: `ClaimHeader`, `ClaimBreakdown`, `EvidenceList`, `EvidenceRow`, `ItemContextRail`. Usam exclusivamente tokens `--om-*` e a escala `.om-*`.

## Chat (`chat/`)

`ChatSidebar` (460 px, expansível), `ChatConversationList`, `ChatMessage` (streaming, ferramentas).

## Egress (`egress/`)

| Componente | Props | Papel |
|---|---|---|
| `ComposeModal` | — | Compor ação do zero (atalho `c`) |
| `ConfirmAction` | `preview`, `onConfirm`, `onCancel`, `loading` | **Confirmação humana obrigatória** antes de qualquer envio: resumo, avisos, impacto |
| `InlineEditor` | — | Edição do rascunho no card |
| `QuickActions` | — | Ações rápidas sugeridas |
| `DateTimePicker` | — | Data/hora para calendário |

## Dashboard (`dashboard/`)

`StatCard (label, value, subtitle, color)`, `BarChart`, `DonutChart (data, title, size)`, `ThroughputChart`, `WaitTimeChart`, `FeatureCostChart`. Gráficos em SVG próprio; utilitários puros em `chartUtils.ts` (testado).

## Settings (`settings/`)

`AppearanceConfig`, `ModelConfig`, `ModelSelect` (**bindable**), `SpacesConfig`, `IntegrationsConfig`, `PlatformCard`, `PlatformIcon (platform, size=24)`, `ConnectModal`, `SmtpSetupForm`, `RulesEditor`, `ProcessingRulesEditor`, `ContextRulesEditor`, `AuditLogViewer`, `FiringLogViewer`, `TagInput` (**bindable**), `TeamEditor`, `RepoConfig`, `MCPConfig`, `N8nAdvancedSection`, `DataConfig`, `ExportMenu`, `BriefingConfig`, `AgentConfig`, `KeybindingsConfig`, `AboutConfig`.

## Trace / Coherence (`trace/`)

`TraceSearch`, `TraceHeader`, `TraceCard`, `TraceTimeline`, `TraceHistory`.

## Workspace (`workspace/`) e agentes (`agent/`)

`AgentPanel`, `ContextPanel` (**bindable**), `TimelinePanel`; `RunAgentModal`.

## Critérios para um componente novo

- [ ] Props tipadas, callbacks `onxxx`, sem `export let`.
- [ ] Só tokens; mapas semânticos vindos de `cardVisuals.ts`.
- [ ] Variante glass e sólida quando for superfície.
- [ ] Teclado e ARIA conforme `patterns.md`.
- [ ] Lógica não trivial extraída para `lib/` com teste.
- [ ] Documentado nesta página.
