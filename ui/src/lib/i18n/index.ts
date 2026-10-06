// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

import { writable, derived, get } from 'svelte/store';
import { getEngineUrl } from '$lib/config';
import { SUPPORTED_LOCALES, type LocaleDict, type SupportedLocale } from './types';

export type { SupportedLocale, LocaleDict } from './types';
export { SUPPORTED_LOCALES } from './types';

// Get initial locale from localStorage or default to pt-BR
const initialLocale: SupportedLocale = (
	typeof window !== 'undefined'
		? (localStorage.getItem('laya_locale') as SupportedLocale) || 'pt-BR'
		: 'pt-BR'
);

export const locale = writable<SupportedLocale>(initialLocale);

// Core dictionary; per-area dictionaries live in ./locales/*.ts and are merged below.
const core: LocaleDict = {
	'pt-BR': {
		// Navigation
		'nav.pulse': 'Pulse',
		'nav.omni': 'Omni',
		'nav.coherence': 'Coerência',
		'nav.hub': 'Central de Comandos',
		'nav.settings': 'Configurações',
		'nav.workspace': 'Espaço de Trabalho',
		'nav.dashboard': 'Painel',
		'nav.status': 'Status do Sistema',

		// Common UI
		'common.today': 'Hoje',
		'common.yesterday': 'Ontem',
		'common.previous_day': 'Dia anterior',
		'common.next_day': 'Próximo dia',
		'common.jump_to_today': 'Ir para hoje',
		'common.click_for_today': 'clique para hoje',
		'common.bookmarked': 'Marcados',
		'common.related': 'Relacionados',
		'common.all_days': 'Todos os dias',
		'common.save': 'Salvar',
		'common.cancel': 'Cancelar',
		'common.edit': 'Editar',
		'common.delete': 'Excluir',
		'common.approve': 'Aprovar',
		'common.dismiss': 'Descartar',
		'common.retry': 'Tentar novamente',
		'common.next': 'Avançar',
		'common.back': 'Voltar',
		'common.loading': 'Carregando...',
		'common.search': 'Pesquisar...',
		'common.copied': 'Copiado!',
		'common.copy': 'Copiar',
		'common.language': 'Idioma',
		'common.more': 'Mais',
		'common.chat': 'Chat',
		'common.close': 'Fechar',
		'common.open': 'Abrir',
		'common.active': 'Ativo',
		'common.archived': 'Arquivado',
		'common.filter': 'Filtrar',
		'common.clear': 'Limpar',
		'common.all': 'Todos',
		'common.yes': 'Sim',
		'common.no': 'Não',
		'common.error': 'Erro',

		// Settings Page & Tabs
		'settings.title': 'Configurações',
		'settings.subtitle': 'Gerencie sua equipe, regras, modelos, repositórios e agente de código',
		'settings.team': 'Equipe',
		'settings.rules': 'Regras',
		'settings.models': 'Modelos',
		'settings.repos': 'Repositórios',
		'settings.agent': 'Agente',
		'settings.integrations': 'Integrações',
		'settings.spaces': 'Espaços',
		'settings.features': 'Recursos',
		'settings.mcp': 'MCP',
		'settings.audit': 'Auditoria',
		'settings.appearance': 'Aparência',
		'settings.keys': 'Teclas',
		'settings.data': 'Dados',
		'settings.about': 'Sobre',
		'settings.need_help': 'Precisa de ajuda para resolver problemas? Exporte diagnósticos para o suporte.',
		'settings.export_diagnostics': 'Exportar Diagnósticos',
		'settings.exporting': 'Exportando...',

		// Appearance Settings
		'appearance.theme_title': 'Aparência',
		'appearance.theme_desc': 'Escolha entre os temas claro e escuro para a interface.',
		'appearance.dark': 'Escuro',
		'appearance.light': 'Claro',
		'appearance.glass_title': 'Tema de Vidro (Glass)',
		'appearance.glass_desc': 'Efeito de vidro fosco em cartões e listas com desfoque de fundo.',
		'appearance.status_colors_title': 'Cores de Status',
		'appearance.status_colors_desc': 'Destaque cartões e linhas pela cor de seu status.',
		'appearance.accessible_colors_title': 'Cores Acessíveis',
		'appearance.accessible_colors_desc': 'Paleta adaptada para daltônicos com melhor contraste.',
		'appearance.reduce_motion_title': 'Reduzir Movimento',
		'appearance.reduce_motion_desc': 'Desativa transições e animações no aplicativo.',
		'appearance.card_descriptions_title': 'Exibir Descrições nos Cartões',
		'appearance.card_descriptions_desc': 'Mostra o resumo nos cartões do feed. Desativar torna os cartões mais compactos.',
		'appearance.card_size_title': 'Tamanho dos Cartões',
		'appearance.card_size_desc': 'Compacto exibe mais cartões na tela. Relaxado mostra o layout completo.',
		'appearance.card_size_compact': 'Compacto',
		'appearance.card_size_relaxed': 'Relaxado',
		'appearance.system_font_title': 'Fonte do Sistema',
		'appearance.system_font_desc': 'Usar a fonte padrão do seu sistema operacional em vez da fonte Inter.',
		'appearance.text_size_title': 'Tamanho do Texto',
		'appearance.text_size_desc': 'Ajuste o tamanho base da fonte para mensagens de chat e conteúdo dos cartões.',

		// Setup & Onboarding
		'setup.welcome': 'Bem-vindo ao Laya',
		'setup.subtitle': 'Vamos configurar o seu Command Center de IA local e conectá-lo ao Ollama ou aos seus provedores.',
		'setup.provider': 'Provedor de IA',
		'setup.api_key': 'Chave de API (API Key)',
		'setup.save_key': 'Salvar Chave',
		'setup.ollama_option': 'Ollama (Servidor Local)',
		'setup.ollama_desc': 'Conecta diretamente ao seu Ollama local para listar e selecionar qual modelo você quer usar.',
		'setup.connect_ollama': 'Conectar Ollama e Buscar Modelos',
		'setup.self_hosted_checkbox': 'Quero usar um modelo local/self-hosted',
		'setup.self_hosted_desc': 'Configurar um provedor local como Ollama, LM Studio ou servidor compatível com OpenAI.',
		'setup.quick_picker': 'Seletor Rápido (Aplicar modelo para todas as etapas):',
		'setup.select_role_models': 'Selecione os modelos para cada etapa do pipeline',

		// Hub Page
		'hub.title': 'Laya Command Center & Central de Aprendizado',
		'hub.subtitle': 'Centralize comandos, ensine contexto aos seus agentes e integre com o Ollama em todos os seus projetos.',
		'hub.tab_commands': 'Central de Comandos & Ingestão',
		'hub.tab_learning': 'Contextos Gerais & Aprendizado por Projeto',
		'hub.tab_agents': 'Agentes Gerais vs. Especializados',
		'hub.tab_mcp': 'Integração MCP (Cursor, Claude, IDEs)',
		'hub.sim_title': 'Simulador de Ingestão de Projetos (Dispatch)',
		'hub.sim_desc': 'Envie um evento de teste do seu projeto. O Laya classificará via Ollama e gerará um Action Card.',
		'hub.sim_send': 'Disparar Evento para o Laya',
		'hub.code_generator': 'Gerador de Código de Integração',
		'hub.learning_title': 'Sistema de Aprendizado de Contextos (Gerais vs. Específicos)',
		'hub.learning_desc': 'À medida que você usa o Laya em diferentes projetos, ele extrai diretivas e regras em linguagem natural a partir das suas aprovações e correções.',
		'hub.teach_rule': 'Ensine uma nova regra ou diretiva ao Laya:',
		'hub.add_rule': 'Adicionar Regra',
		'hub.global_rules': 'Contextos Gerais (Regras Globais)',
		'hub.project_rules': 'Contextos Específicos por Projeto (Spaces)',

		// Status & Badges
		'status.healthy': 'Saudável / Ativo',
		'status.unreachable': 'Inacessível',
		'status.checking': 'Verificando...',
		'status.title': 'Status do Sistema & Métricas',
		'status.subtitle': 'Monitore o estado dos serviços locais, taxas de transferência e banco de dados.',

		// Chat
		'chat.title': 'Assistente Laya',
		'chat.placeholder': 'Faça uma pergunta sobre seus cartões ou projetos...',
		'chat.new_chat': 'Novo Chat',
		'chat.clear_history': 'Limpar Histórico',
		'chat.send': 'Enviar',

		// Omni Board
		'omni.title': 'Omni Workspace',
		'omni.subtitle': 'Visão consolidada do progresso em tempo real entre todas as plataformas',
		'omni.attention_load': 'Carga de Atenção',
		'omni.open_items': 'itens abertos',
		'omni.open_item': 'item aberto',
		'omni.from_events': 'de',
		'omni.events': 'eventos',
		'omni.event': 'evento',
		'omni.nothing_needs_you': 'Nada precisa da sua atenção agora.',
		'omni.event_volume': 'Volume de Eventos',
		'omni.days': 'dias',
		'omni.platform_mix': 'Mix de Plataformas',
		'omni.compression': 'Compressão',
		'omni.distilled': 'destilado',
		'omni.next_synthesis': 'Próxima síntese',
		'omni.triage': 'Triagem',
		'omni.by_priority': 'por prioridade e antiguidade',
		'omni.nothing_needs_attention': 'Nada requer atenção no momento. Tudo o que o Omni rastreia está em andamento ou concluído.',
		'omni.compression_funnel': 'Funil de compressão',
		'omni.needs_attention': 'Requer Atenção',
		'omni.recent': 'Recente',
		'omni.this_week': 'Esta Semana',
		'omni.milestones': 'Marcos',
		'omni.what_changed': 'O que mudou',
		'omni.since_last_looked': 'desde a sua última visualização',
		'omni.new': 'novo',
		'omni.folded': 'agrupado',
		'omni.resolved': 'resolvido',
		'omni.high': 'alta',
		'omni.medium': 'média',
		'omni.low': 'baixa',
		'omni.clear': 'Limpo.',
		'omni.nothing_here_yet': 'Nada por aqui ainda.',
		'omni.viewing_v': 'VISUALIZANDO v',
		'omni.jump_to_latest': 'Ir para o mais recente',
		'omni.synthesizing': 'Sintetizando…',
		'omni.resynthesize': 'Resintetizar',
		'omni.all_spaces': 'Todos os Espaços',

		// Coherence
		'coherence.title': 'Coerência & Grafo Semântico',
		'coherence.subtitle': 'Mapeamento semântico de entidades, tarefas e relacionamentos',

		// Feed
		'feed.title': 'Pulse Feed',
		'feed.empty_title': 'Nenhum cartão encontrado',
		'feed.empty_subtitle': 'Não há cartões que correspondam aos filtros selecionados.'
	},
	'en': {
		// Navigation
		'nav.pulse': 'Pulse',
		'nav.omni': 'Omni',
		'nav.coherence': 'Coherence',
		'nav.hub': 'Command Hub',
		'nav.settings': 'Settings',
		'nav.workspace': 'Workspace',
		'nav.dashboard': 'Dashboard',
		'nav.status': 'System Status',

		// Common UI
		'common.today': 'Today',
		'common.yesterday': 'Yesterday',
		'common.previous_day': 'Previous day',
		'common.next_day': 'Next day',
		'common.jump_to_today': 'Jump to today',
		'common.click_for_today': 'click for today',
		'common.bookmarked': 'Bookmarked',
		'common.related': 'Related',
		'common.all_days': 'All days',
		'common.save': 'Save',
		'common.cancel': 'Cancel',
		'common.edit': 'Edit',
		'common.delete': 'Delete',
		'common.approve': 'Approve',
		'common.dismiss': 'Dismiss',
		'common.retry': 'Retry',
		'common.next': 'Next',
		'common.back': 'Back',
		'common.loading': 'Loading...',
		'common.search': 'Search...',
		'common.copied': 'Copied!',
		'common.copy': 'Copy',
		'common.language': 'Language',
		'common.more': 'More',
		'common.chat': 'Chat',
		'common.close': 'Close',
		'common.open': 'Open',
		'common.active': 'Active',
		'common.archived': 'Archived',
		'common.filter': 'Filter',
		'common.clear': 'Clear',
		'common.all': 'All',
		'common.yes': 'Yes',
		'common.no': 'No',
		'common.error': 'Error',

		// Settings Page & Tabs
		'settings.title': 'Settings',
		'settings.subtitle': 'Manage your team, rules, models, repos, and coding agent',
		'settings.team': 'Team',
		'settings.rules': 'Rules',
		'settings.models': 'Models',
		'settings.repos': 'Repos',
		'settings.agent': 'Agent',
		'settings.integrations': 'Integrations',
		'settings.spaces': 'Spaces',
		'settings.features': 'Features',
		'settings.mcp': 'MCP',
		'settings.audit': 'Audit',
		'settings.appearance': 'Appearance',
		'settings.keys': 'Keys',
		'settings.data': 'Data',
		'settings.about': 'About',
		'settings.need_help': 'Need help troubleshooting? Export diagnostics for support.',
		'settings.export_diagnostics': 'Export Diagnostics',
		'settings.exporting': 'Exporting...',

		// Appearance Settings
		'appearance.theme_title': 'Appearance',
		'appearance.theme_desc': 'Choose between dark and light interface themes.',
		'appearance.dark': 'Dark',
		'appearance.light': 'Light',
		'appearance.glass_title': 'Glass Theme',
		'appearance.glass_desc': 'Frosted glass effect on cards and list rows. Adds backdrop blur and translucent surfaces.',
		'appearance.status_colors_title': 'Status Colors',
		'appearance.status_colors_desc': 'Tint cards and list rows by their status. Turn off for a uniform look.',
		'appearance.accessible_colors_title': 'Accessible Colors',
		'appearance.accessible_colors_desc': 'Colorblind-friendly palette. Shifts status colors for better contrast across all vision types.',
		'appearance.reduce_motion_title': 'Reduce Motion',
		'appearance.reduce_motion_desc': 'Disable tab transitions, panel slides, and card reflow animations.',
		'appearance.card_descriptions_title': 'Show Card Descriptions',
		'appearance.card_descriptions_desc': 'Show summary text on cards in the feed. Turning this off makes cards more compact.',
		'appearance.card_size_title': 'Card Size',
		'appearance.card_size_desc': 'Compact stacks more cards per screen. Relaxed shows the full layout.',
		'appearance.card_size_compact': 'Compact',
		'appearance.card_size_relaxed': 'Relaxed',
		'appearance.system_font_title': 'System Font',
		'appearance.system_font_desc': "Use your operating system's default font instead of Inter.",
		'appearance.text_size_title': 'Text Size',
		'appearance.text_size_desc': 'Adjust the base font size for chat messages and card content.',

		// Setup & Onboarding
		'setup.welcome': 'Welcome to Laya',
		'setup.subtitle': "Let's get you set up. Connect your local Ollama or AI API providers.",
		'setup.provider': 'AI Provider',
		'setup.api_key': 'API Key',
		'setup.save_key': 'Save Key',
		'setup.ollama_option': 'Ollama (Local Server)',
		'setup.ollama_desc': 'Connects directly to your local Ollama to list and select installed models.',
		'setup.connect_ollama': 'Connect Ollama & Discover Models',
		'setup.self_hosted_checkbox': 'I want to use a self-hosted model',
		'setup.self_hosted_desc': 'Configure a local provider like Ollama, LM Studio, or OpenAI-compatible server.',
		'setup.quick_picker': 'Quick Model Picker (Apply model to all roles):',
		'setup.select_role_models': 'Select models for each pipeline role',

		// Hub Page
		'hub.title': 'Laya Command Center & Learning Hub',
		'hub.subtitle': 'Centralize commands, teach context to your agents, and integrate with Ollama across your projects.',
		'hub.tab_commands': 'Command Center & Ingestion',
		'hub.tab_learning': 'General & Per-Project Context Rules',
		'hub.tab_agents': 'General vs. Specialized Agents',
		'hub.tab_mcp': 'MCP Integration (Cursor, Claude, IDEs)',
		'hub.sim_title': 'Project Event Simulator (Dispatch)',
		'hub.sim_desc': 'Send a test event from your project. Laya will classify via Ollama and generate an Action Card.',
		'hub.sim_send': 'Dispatch Event to Laya',
		'hub.code_generator': 'Integration Code Generator',
		'hub.learning_title': 'Context Learning System (General vs. Specific)',
		'hub.learning_desc': 'As you use Laya across projects, it extracts natural language rules from your approvals and corrections.',
		'hub.teach_rule': 'Teach a new rule or directive to Laya:',
		'hub.add_rule': 'Add Rule',
		'hub.global_rules': 'General Contexts (Global Team Rules)',
		'hub.project_rules': 'Project-Specific Contexts (Spaces)',

		// Status & Badges
		'status.healthy': 'Healthy / Active',
		'status.unreachable': 'Unreachable',
		'status.checking': 'Checking...',
		'status.title': 'System Status & Metrics',
		'status.subtitle': 'Monitor local services, throughput rates, and database state.',

		// Chat
		'chat.title': 'Laya Assistant',
		'chat.placeholder': 'Ask a question about your cards or projects...',
		'chat.new_chat': 'New Chat',
		'chat.clear_history': 'Clear History',
		'chat.send': 'Send',

		// Omni Board
		'omni.title': 'Omni Workspace',
		'omni.subtitle': 'Consolidated real-time cross-platform progress view',
		'omni.attention_load': 'Attention load',
		'omni.open_items': 'open items',
		'omni.open_item': 'open item',
		'omni.from_events': 'from',
		'omni.events': 'events',
		'omni.event': 'event',
		'omni.nothing_needs_you': 'Nothing needs you right now.',
		'omni.event_volume': 'Event volume',
		'omni.days': 'days',
		'omni.platform_mix': 'Platform mix',
		'omni.compression': 'Compression',
		'omni.distilled': 'distilled',
		'omni.next_synthesis': 'Next synthesis',
		'omni.triage': 'Triage',
		'omni.by_priority': 'by priority, then age',
		'omni.nothing_needs_attention': 'Nothing needs attention. Everything Omni is tracking is either moving or done.',
		'omni.compression_funnel': 'Compression funnel',
		'omni.needs_attention': 'Needs Attention',
		'omni.recent': 'Recent',
		'omni.this_week': 'This Week',
		'omni.milestones': 'Milestones',
		'omni.what_changed': 'What changed',
		'omni.since_last_looked': 'since you last looked',
		'omni.new': 'new',
		'omni.folded': 'folded',
		'omni.resolved': 'resolved',
		'omni.high': 'high',
		'omni.medium': 'medium',
		'omni.low': 'low',
		'omni.clear': 'Clear.',
		'omni.nothing_here_yet': 'Nothing here yet.',
		'omni.viewing_v': 'VIEWING v',
		'omni.jump_to_latest': 'Jump to latest',
		'omni.synthesizing': 'Synthesizing…',
		'omni.resynthesize': 'Resynthesize',
		'omni.all_spaces': 'All Spaces',

		// Coherence
		'coherence.title': 'Coherence & Semantic Graph',
		'coherence.subtitle': 'Semantic mapping of entities, tasks, and relationships',

		// Feed
		'feed.title': 'Pulse Feed',
		'feed.empty_title': 'No cards found',
		'feed.empty_subtitle': 'There are no cards matching your selected filters.'
	},
	'es': {
		// Navigation
		'nav.pulse': 'Pulse',
		'nav.omni': 'Omni',
		'nav.coherence': 'Coherencia',
		'nav.hub': 'Centro de Comandos',
		'nav.settings': 'Configuración',
		'nav.workspace': 'Espacio de Trabajo',
		'nav.dashboard': 'Panel',
		'nav.status': 'Estado del Sistema',

		// Common UI
		'common.today': 'Hoy',
		'common.yesterday': 'Ayer',
		'common.previous_day': 'Día anterior',
		'common.next_day': 'Día siguiente',
		'common.jump_to_today': 'Ir a hoy',
		'common.click_for_today': 'clic para hoy',
		'common.bookmarked': 'Marcados',
		'common.related': 'Relacionados',
		'common.all_days': 'Todos los días',
		'common.save': 'Guardar',
		'common.cancel': 'Cancelar',
		'common.edit': 'Editar',
		'common.delete': 'Eliminar',
		'common.approve': 'Aprobar',
		'common.dismiss': 'Descartar',
		'common.retry': 'Reintentar',
		'common.next': 'Siguiente',
		'common.back': 'Atrás',
		'common.loading': 'Cargando...',
		'common.search': 'Buscar...',
		'common.copied': '¡Copiado!',
		'common.copy': 'Copiar',
		'common.language': 'Idioma',
		'common.more': 'Más',
		'common.chat': 'Chat',
		'common.close': 'Cerrar',
		'common.open': 'Abrir',
		'common.active': 'Activo',
		'common.archived': 'Archivado',
		'common.filter': 'Filtrar',
		'common.clear': 'Limpiar',
		'common.all': 'Todos',
		'common.yes': 'Sí',
		'common.no': 'No',
		'common.error': 'Error',

		// Settings Page & Tabs
		'settings.title': 'Configuración',
		'settings.subtitle': 'Gestiona tu equipo, reglas, modelos, repositorios y agente de código',
		'settings.team': 'Equipo',
		'settings.rules': 'Reglas',
		'settings.models': 'Modelos',
		'settings.repos': 'Repositorios',
		'settings.agent': 'Agente',
		'settings.integrations': 'Integraciones',
		'settings.spaces': 'Espacios',
		'settings.features': 'Funciones',
		'settings.mcp': 'MCP',
		'settings.audit': 'Auditoría',
		'settings.appearance': 'Apariencia',
		'settings.keys': 'Teclas',
		'settings.data': 'Datos',
		'settings.about': 'Acerca de',
		'settings.need_help': '¿Necesitas ayuda? Exporta diagnósticos para el soporte.',
		'settings.export_diagnostics': 'Exportar Diagnósticos',
		'settings.exporting': 'Exportando...',

		// Appearance Settings
		'appearance.theme_title': 'Apariencia',
		'appearance.theme_desc': 'Elige entre temas claro y oscuro para la interfaz.',
		'appearance.dark': 'Oscuro',
		'appearance.light': 'Claro',
		'appearance.glass_title': 'Tema de Cristal (Glass)',
		'appearance.glass_desc': 'Efecto de cristal esmerilado en tarjetas y listas.',
		'appearance.status_colors_title': 'Colores de Estado',
		'appearance.status_colors_desc': 'Destaca tarjetas y listas según su estado.',
		'appearance.accessible_colors_title': 'Colores Accesibles',
		'appearance.accessible_colors_desc': 'Paleta adaptada para daltónicos con mayor contraste.',
		'appearance.reduce_motion_title': 'Reducir Movimiento',
		'appearance.reduce_motion_desc': 'Desactiva animaciones y transiciones en la aplicación.',
		'appearance.card_descriptions_title': 'Mostrar Descripciones en Tarjetas',
		'appearance.card_descriptions_desc': 'Muestra resumen en las tarjetas. Desactivarlo las hace más compactas.',
		'appearance.card_size_title': 'Tamaño de Tarjeta',
		'appearance.card_size_desc': 'Compacto muestra más tarjetas. Relajado muestra el diseño completo.',
		'appearance.card_size_compact': 'Compacto',
		'appearance.card_size_relaxed': 'Relajado',
		'appearance.system_font_title': 'Fuente del Sistema',
		'appearance.system_font_desc': 'Usa la fuente predeterminada de tu sistema operativo.',
		'appearance.text_size_title': 'Tamaño de Texto',
		'appearance.text_size_desc': 'Ajusta el tamaño base de fuente para chat y contenido.',

		// Setup & Onboarding
		'setup.welcome': 'Bienvenido a Laya',
		'setup.subtitle': 'Configuremos tu Command Center local y conectémoslo a Ollama o tus proveedores.',
		'setup.provider': 'Proveedor de IA',
		'setup.api_key': 'Clave API (API Key)',
		'setup.save_key': 'Guardar Clave',
		'setup.ollama_option': 'Ollama (Servidor Local)',
		'setup.ollama_desc': 'Conecta directamente a tu Ollama local para listar y seleccionar modelos instalados.',
		'setup.connect_ollama': 'Conectar Ollama y Buscar Modelos',
		'setup.self_hosted_checkbox': 'Quiero usar un modelo local / alojado',
		'setup.self_hosted_desc': 'Configurar un proveedor local como Ollama, LM Studio o servidor compatible con OpenAI.',
		'setup.quick_picker': 'Selección Rápida (Aplicar modelo a todas las etapas):',
		'setup.select_role_models': 'Selecciona modelos para cada función del pipeline',

		// Hub Page
		'hub.title': 'Laya Command Center & Centro de Aprendizaje',
		'hub.subtitle': 'Centraliza comandos, enseña contexto a tus agentes e integra con Ollama en todos tus proyectos.',
		'hub.tab_commands': 'Central de Comandos e Ingestión',
		'hub.tab_learning': 'Contextos Generales y Aprendizaje por Proyecto',
		'hub.tab_agents': 'Agentes Generales vs. Especializados',
		'hub.tab_mcp': 'Integración MCP (Cursor, Claude, IDEs)',
		'hub.sim_title': 'Simulador de Ingestión de Proyectos (Dispatch)',
		'hub.sim_desc': 'Envía un evento de prueba de tu proyecto. Laya lo clasificará con Ollama y generará una Action Card.',
		'hub.sim_send': 'Despachar Evento a Laya',
		'hub.code_generator': 'Generador de Código de Integración',
		'hub.learning_title': 'Sistema de Aprendizaje de Contexto (General vs. Específico)',
		'hub.learning_desc': 'A medida que usas Laya en tus proyectos, extrae reglas en lenguaje natural a partir de tus aprobaciones y correcciones.',
		'hub.teach_rule': 'Enseña una nueva regla o directiva a Laya:',
		'hub.add_rule': 'Agregar Regla',
		'hub.global_rules': 'Contextos Generales (Reglas Globales)',
		'hub.project_rules': 'Contextos Específicos por Proyecto (Spaces)',

		// Status & Badges
		'status.healthy': 'Saludable / Activo',
		'status.unreachable': 'Inaccesible',
		'status.checking': 'Verificando...',
		'status.title': 'Estado del Sistema y Métricas',
		'status.subtitle': 'Monitorea servicios locales, rendimiento y base de datos.',

		// Chat
		'chat.title': 'Asistente Laya',
		'chat.placeholder': 'Haz una pregunta sobre tus tarjetas o proyectos...',
		'chat.new_chat': 'Nuevo Chat',
		'chat.clear_history': 'Limpiar Historial',
		'chat.send': 'Enviar',

		// Omni Board
		'omni.title': 'Omni Workspace',
		'omni.subtitle': 'Vista consolidada de progreso en tiempo real',
		'omni.attention_load': 'Carga de Atención',
		'omni.open_items': 'elementos abiertos',
		'omni.open_item': 'elemento abierto',
		'omni.from_events': 'de',
		'omni.events': 'eventos',
		'omni.event': 'evento',
		'omni.nothing_needs_you': 'Nada requiere tu atención en este momento.',
		'omni.event_volume': 'Volumen de Eventos',
		'omni.days': 'días',
		'omni.platform_mix': 'Mezcla de Plataformas',
		'omni.compression': 'Compresión',
		'omni.distilled': 'destilado',
		'omni.next_synthesis': 'Próxima síntesis',
		'omni.triage': 'Triaje',
		'omni.by_priority': 'por prioridad y antigüedad',
		'omni.nothing_needs_attention': 'Nada requiere atención en este momento.',
		'omni.compression_funnel': 'Embudo de compresión',
		'omni.needs_attention': 'Requiere Atención',
		'omni.recent': 'Reciente',
		'omni.this_week': 'Esta Semana',
		'omni.milestones': 'Hitos',
		'omni.what_changed': 'Qué cambió',
		'omni.since_last_looked': 'desde tu última vista',
		'omni.new': 'nuevo',
		'omni.folded': 'agrupado',
		'omni.resolved': 'resuelto',
		'omni.high': 'alta',
		'omni.medium': 'media',
		'omni.low': 'baja',
		'omni.clear': 'Limpio.',
		'omni.nothing_here_yet': 'Nada por aquí todavía.',
		'omni.viewing_v': 'VIENDO v',
		'omni.jump_to_latest': 'Ir a lo más reciente',
		'omni.synthesizing': 'Sintetizando…',
		'omni.resynthesize': 'Resintetizar',
		'omni.all_spaces': 'Todos los Espacios',

		// Coherence
		'coherence.title': 'Coherencia y Grafo Semántico',
		'coherence.subtitle': 'Mapeo semántico de entidades, tareas y relaciones',

		// Feed
		'feed.title': 'Pulse Feed',
		'feed.empty_title': 'No se encontraron tarjetas',
		'feed.empty_subtitle': 'No hay tarjetas que coincidan con los filtros seleccionados.'
	}
};

const areaModules = import.meta.glob<{ default: LocaleDict }>('./locales/*.ts', { eager: true });

export const areaDictionaries: Record<string, LocaleDict> = Object.fromEntries(
	Object.entries(areaModules).map(([path, mod]) => [path, mod.default])
);

export const translations: LocaleDict = SUPPORTED_LOCALES.reduce((acc, loc) => {
	acc[loc] = Object.assign(
		{},
		core[loc],
		...Object.values(areaDictionaries).map((d) => d[loc] ?? {})
	);
	return acc;
}, {} as LocaleDict);

export type TranslateParams = Record<string, string | number>;

function interpolate(text: string, params?: TranslateParams): string {
	if (!params) return text;
	return text.replace(/\{(\w+)\}/g, (match, name: string) =>
		name in params ? String(params[name]) : match
	);
}

export function translate(
	loc: SupportedLocale,
	key: string,
	fallback?: string,
	params?: TranslateParams
): string {
	const text = translations[loc]?.[key] ?? translations.en[key] ?? fallback ?? key;
	return interpolate(text, params);
}

/**
 * Derived store that returns a translation function t(key, fallback, params).
 * `{name}` placeholders in the text are replaced from `params`.
 */
export const t = derived(locale, ($locale) => {
	return (key: string, fallback?: string, params?: TranslateParams): string =>
		translate($locale, key, fallback, params);
});

/** Non-reactive translation for plain .ts modules. */
export function tr(key: string, fallback?: string, params?: TranslateParams): string {
	return translate(get(locale), key, fallback, params);
}

/** BCP 47 tag for Intl / toLocaleString in the current locale. */
export const intlLocale = derived(locale, ($locale) => $locale);

/**
 * Set current locale, persist to localStorage, and sync backend language setting.
 */
export async function setLocale(newLocale: SupportedLocale) {
	locale.set(newLocale);
	if (typeof window !== 'undefined') {
		localStorage.setItem('laya_locale', newLocale);
	}

	try {
		await fetch(`${getEngineUrl()}/settings`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ language: newLocale })
		});
	} catch (e) {
		console.error('Failed to sync backend language setting', e);
	}
}
