# Redesenho Visual & Nova Identidade de Interface (UI) — NorthWay CRM

Este documento consolida o relatório executivo e técnico do redesenho completo de interface do **NorthWay CRM**, estruturado na branch `feat/ui-redesign`.

---

## 1. Resumo Executivo

A modernização visual transformou o NorthWay CRM em uma aplicação corporativa de alto impacto estético, alinhada aos padrões de design de ponta do mercado de SaaS:
- **Tipografia:** Adoção de **Plus Jakarta Sans** como fonte primária de interface, complementada por **Outfit** e **Inter** com renderização antialiased.
- **Arquitetura de Layout (Shell Flutuante):** Contêiner externo suave (`nw-canvas`) abrigando o cartão mestre flutuante (`nw-shell-card`) com raio de 32px e cabeçalho de navegação unificado por pílulas de contorno elegante.
- **Painéis Discretos & Cartões:** Substituição de sombras pesadas e bordas cinzas genéricas por `nw-panel` translúcido com bordas refinadas (`--nw-border: #E8E9EC`).
- **Navegação & Segmentação:** Barra de navegação em pílula com rotas principais (Dashboard, Pipeline, Leads, Clientes, Prospecção, Tarefas, Financeiro e menu "Mais") com abas ativas em destaque sutil.

---

## 2. Decisões de Escopo (WhatsApp & Kanban)

Por alinhamento e confirmação explícita de operação de negócio:
- **WhatsApp:** Não está em uso. O módulo de chat e atendimento foi **completamente excluído** do escopo de redesenho e o link foi removido dos menus de navegação (desktop e mobile).
- **Kanban de Tarefas:** Não está em uso. O kanban de execução foi **excluído** e removido da barra de navegação. 
- **Lista de Tarefas Simples (`/tasks`):** Mantida e totalmente redesenhada como checklist diário focado em produtividade operacional e comercial.

---

## 3. Tokens & Componentes do Design System (`nw-*`)

Os tokens foram implementados em `northway_crm/tailwind.config.js` e compilados em `northway_crm/static/css/tailwind.min.css`:

### Paleta de Cores
| Token | Variável CSS | Valor Hex | Finalidade |
|---|---|---|---|
| Canvas | `--nw-canvas` | `#F4F5F7` | Fundo externo da aplicação |
| Shell Card | `--nw-card` | `#FFFFFF` | Cartão mestre da página |
| Shell Hover/Alt | `--nw-shell` | `#F8F9FA` | Fundo de pílulas, inputs e tabelas |
| Ink (Texto Principal) | `--nw-ink` | `#111827` | Títulos e ênfase máxima |
| Texto Secundário | `--nw-text-2` | `#4B5563` | Subtítulos e labels |
| Texto Terciário | `--nw-text-3` | `#9CA3AF` | Metadados e placeholders |
| Borda Padrão | `--nw-border` | `#E8E9EC` | Bordas e divisores de cards |
| Borda Forte | `--nw-border-strong` | `#D1D5DB` | Foco e bordas de controle |
| Brand / Destaque | `--nw-brand` | `#E11D48` / `#FA0102` | Cor de marca e CTAs primários |
| Status Sucesso | `--nw-status-success`| `#059669` | Conversões, ganhos e ativos |

### Componentes Utilitários Reutilizáveis
- `.nw-shell-container`: Margens e padding responsivo do contêiner externo.
- `.nw-shell-card`: Cartão mestre com borda suave, raio arredondado (32px) e sombra sutil.
- `.nw-panel`: Superfície interna com borda fina e cantos curvos para segmentar seções.
- `.nw-btn`, `.nw-btn-accent`, `.nw-btn-subtle`: Botões consistentes com transição e microinterações.
- `.nw-badge`: Indicadores de status refinados em formato pílula.
- `.nw-input`: Campos de texto e seleção com altura ergonômica e foco na cor da marca.

---

## 4. Módulos e Telas Redesencontradas

### Fase 0 & 1 — Infraestrutura Visual & Baseline
- Levantamento de 155 templates do ecossistema NorthWay.
- Captura de 32 screenshots em `docs/ui-baseline/`.
- Configuração de tokens em `tailwind.config.js`, criação de `templates/macros.html` e `templates/ui_kit.html`.

### Fase 2 — Base Shell & Navegação Global
- **`templates/base.html`:** Refatoração da casca base, barra de navegação flutuante por pílulas, menu de perfil com avatar arredondado e barra secundária contextual para Prospecção. Removidos itens inativos de WhatsApp e Kanban.

### Fase 3 — Telas Modelo
- **`templates/leads.html`:** Tabela executiva com avatar de lead, badges de qualificação, filtros rápidos e paginação estilizada.
- **`templates/pipeline.html`:** Quadro de funil comercial com cartões elegantes, contadores de valor monetário e transições suaves de drag-and-drop preservando Alpine.js.
- **`templates/dashboard.html`:** Métricas principais em cards discretos, gráficos Chart.js em paleta harmoniosa e manifesto NorthWay em destaque escuro.

### Fase 4 — Módulos Operacionais & de Negócio
- **Módulo 1 (Home & Clientes):**
  - `templates/home.html`
  - `templates/clients.html`
  - `templates/client_details.html`
- **Módulo 2 (Detalhe do Lead):**
  - `templates/lead_details.html` (drawer lateral, histórico de atividades, abas contextuais e ações rápidas).
- **Módulo 4 (Prospecção Ativa):**
  - `templates/prospecting/dashboard.html`
  - `templates/prospecting/campaigns.html`
  - `templates/prospecting/discover.html`
  - `templates/prospecting/messages.html`
- **Módulo 5 (Tarefas Simples):**
  - `templates/tasks.html` (progresso global, abas em pílula "Funil", "Clientes", "Geral" e "Concluídas").
- **Módulo 6 (Financeiro, DRE e Contas a Pagar):**
  - `templates/financial/dashboard.html`
  - `templates/financial/strategic_dre.html`
  - `templates/financial/accounts_payable.html`
- **Módulo 7 (Contratos e Orçamentos):**
  - `templates/contracts/index.html`
  - `templates/contracts/view_contract.html`
  - `templates/commercial/budget_history.html`
  - `templates/commercial/budget_generator.html`
- **Módulo 8 (Metas, Performance e Modelos):**
  - `templates/goals.html`
  - `templates/commercial/performance.html`
  - `templates/settings_templates.html`
- **Módulo 9 (Configurações da Empresa e Equipe):**
  - `templates/_settings_layout.html`
  - `templates/company_settings.html`
  - `templates/admin/users.html`
  - `templates/settings_team.html`
- **Módulo 10 (Autenticação):**
  - `templates/login.html`
  - `templates/register.html`
  - `templates/auth/forgot_password.html`
  - `templates/auth/reset_password.html`

---

## 5. Garantias de Integridade & Regras Invioláveis

| Regra Inviolável | Status | Verificação |
|---|---|---|
| **0 arquivos Python modificados** | ✅ Aprovado | Nenhuma linha de `.py` foi alterada no redesign |
| **Nenhuma rota ou `url_for` quebrada** | ✅ Aprovado | Todos os parâmetros e links foram mantidos integralmente |
| **Integridade de Formulários** | ✅ Aprovado | Atributos `name`, `id` e `type` de inputs 100% preservados |
| **Alpine.js & Scripts Inline** | ✅ Aprovado | Diretivas `x-data`, `x-model`, `@click` e tags `<script>` intactos |
| **Segurança e CSRF** | ✅ Aprovado | `{{ csrf_token() }}` mantido em todos os formulários |
| **Suíte de Testes Automatizados** | ✅ Aprovado | **33 passed, 2 skipped** (resultado idêntico à base inicial) |

---

## 6. Galeria de Screenshots Antes / Depois

Os screenshots capturados via Puppeteer estão organizados nas seguintes pastas:
- **Baseline (Antes):** `docs/ui-baseline/`
- **Capturas por Fase:**
  - `docs/ui-phase2/` (Base Shell)
  - `docs/ui-phase3/` (Modelos: Leads, Pipeline, Dashboard)
  - `docs/ui-phase4-m1/` (Home & Clientes)
  - `docs/ui-phase4-m2/` (Detalhe do Lead)
  - `docs/ui-phase4-m4/` (Prospecção)
  - `docs/ui-phase4-m5/` (Tarefas)
  - `docs/ui-phase4-m6/` (Financeiro & DRE)
  - `docs/ui-phase4-m7/` (Contratos & Orçamentos)
  - `docs/ui-phase4-m8/` (Metas, Performance & Modelos)
  - `docs/ui-phase4-m9/` (Configurações & Equipe)
  - `docs/ui-phase4-m10/` (Autenticação)
- **Validação Final (Depois):** `docs/ui-after/` (44 telas completas desktop e mobile).
