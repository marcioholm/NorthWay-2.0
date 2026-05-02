/**
 * NORTHWAY ASSESSORIA - CONFIGURAÇÃO DE APRESENTAÇÃO
 * Este arquivo contém os dados dinâmicos da apresentação.
 * Para usar, copie o conteúdo abaixo para o bloco <script id="config-data"> 
 * ou carregue este arquivo no HTML.
 */

// ── EXEMPLO: NEW FIT SUPLEMENTOS ───────────────────
const CONFIG_NEW_FIT = {
  cliente: {
    nome: "NEW FIT SUPLEMENTOS",
    segmento: "Suplementos",
    cidade: "Norte Pioneiro do Paraná",
    mes_ano: "Maio de 2026"
  },
  contato: {
    instagram: "@northway.mkt",
    whatsapp: "(42) 99989-6358",
    email: "marciogholmm@gmail.com"
  },
  investimento: {
    valor: "R$ 750",
    periodo: "por mês",
    desc: "Planejamento 3–5 anos · 4 Pilares NorthWay · Funil de Vendas · Business Model Canvas · Metas SMART · Plano 90 dias · Google Meu Negócio · Rotina de Gestão · Gráfico Gantt",
    nao_incluso: [
      "Gestão de redes sociais (upgrade)",
      "Tráfego pago Meta / Google Ads (upgrade)",
      "Criação de identidade visual",
      "Verba de mídia (custo direto)"
    ]
  },
  diagnostico: {
    frase_capa: "Hoje você trabalha para o mês fechar. Nosso papel é fazer a sua empresa trabalhar para crescer.",
    comparativo: [
      { antes: "Sem planejamento estratégico", depois: "Plano claro de 3 a 5 anos" },
      { antes: "Sem metas definidas", depois: "Metas SMART mensais e anuais" },
      { antes: "Operando no improviso", depois: "Rotina de gestão estruturada" },
      { antes: "Exclusividade desperdiçada", depois: "Exclusividade como diferencial central" },
      { antes: "Presença digital no Instagram", depois: "Google Meu Negócio ativo e otimizado" },
      { antes: "Dono preso no operacional", depois: "Empresa com direção e previsibilidade" }
    ]
  },
  metas: {
    ano1: ["Faturamento mensal alvo", "Nº de clientes ativos/mês", "Ticket médio por venda", "Leads mensais necessários"],
    ano3: ["Capacidade operacional ampliada", "Equipe mínima estruturada", "Redução da dependência do dono"],
    ano5: ["Referência consolidada na região", "Múltiplos canais de receita", "Empresa sem dono no operacional"]
  },
  plano90: [
    { num: "01", foco: "Fundação", acoes: ["BMC validado", "Missão, Visão e Valores", "Metas SMART"] },
    { num: "02", foco: "Posicionamento", acoes: ["Persona e proposta de valor", "Exclusividade regional", "GMN otimizado"] },
    { num: "03", foco: "Atração", acoes: ["Oferta clara", "Parcerias locais", "Campanha de lançamento"] },
    { num: "04", foco: "Vendas", acoes: ["Processo de atendimento", "Script de vendas", "Kits e follow-up"] },
    { num: "05", foco: "Gestão", acoes: ["Indicadores semanais", "Reunião mensal", "Ajuste estratégico"] }
  ],
  gantt: [
    { group: 'ESTRATÉGIA E IDENTIDADE' },
    { label: 'Reunião de Imersão / Diagnóstico', s: 1, e: 1, type: 'red' },
    { label: 'Business Model Canvas', s: 2, e: 2, type: 'red' },
    { label: 'Missão, Visão e Valores', s: 3, e: 3, type: 'red' },
    { label: 'Manifesto de Marca', s: 3, e: 3, type: 'red' },
    { label: 'Persona e Posicionamento', s: 3, e: 4, type: 'red' },
    { group: 'METAS E PLANEJAMENTO' },
    { label: 'Metas SMART — Ano 1 / 3 / 5', s: 4, e: 4, type: 'red' },
    { label: 'Roadmap 90 dias', s: 4, e: 4, type: 'red' },
    { group: 'DIGITAL E PRESENÇA' },
    { label: 'Google Meu Negócio — Setup', s: 2, e: 3, type: 'red' },
    { label: 'GMN — Postagens e reputação', s: 4, e: 12, type: 'gray' },
    { group: 'OS 4 PILARES — EXECUÇÃO' },
    { label: 'ATRAIR — Parcerias e canais', s: 5, e: 7, type: 'red' },
    { label: 'ENGAJAR — Conteúdo e depoimentos', s: 6, e: 9, type: 'gray' },
    { label: 'VENDER — Script de vendas', s: 5, e: 6, type: 'red' },
    { label: 'RETER — Programa de fidelidade', s: 8, e: 12, type: 'gray' },
    { group: 'FUNIL DE VENDAS' },
    { label: 'Topo — Atração ativa', s: 5, e: 12, type: 'blue' },
    { label: 'Meio — Engajamento', s: 6, e: 12, type: 'blue' },
    { label: 'Fundo — Conversão e follow-up', s: 5, e: 12, type: 'blue' },
    { label: 'Pós-venda — Fidelização', s: 9, e: 12, type: 'blue' },
    { group: 'ROTINA DE GESTÃO' },
    { label: 'Reunião mensal (45 min)', s: 4, e: 12, type: 'gray' },
    { label: 'Revisão de metas e indicadores', s: 4, e: 12, type: 'gray' }
  ],
  proximos_passos: [
    "Aprovação da proposta e assinatura do contrato",
    "Pagamento da primeira mensalidade",
    "Agendamento da Reunião de Imersão (1h30) — Semana 1",
    "Início das entregas conforme cronograma Gantt"
  ],
  frase_closing: "O que não é medido não pode ser acompanhado e, se não podemos acompanhar, não podemos escalar."
};

// ── TEMPLATE EM BRANCO ──────────────────────────────
/*
const CONFIG_BLANK = {
  cliente: {
    nome: "",
    segmento: "",
    cidade: "",
    mes_ano: ""
  },
  contato: {
    instagram: "",
    whatsapp: "",
    email: ""
  },
  investimento: {
    valor: "",
    periodo: "",
    desc: "",
    nao_incluso: []
  },
  diagnostico: {
    frase_capa: "",
    comparativo: [
      { antes: "", depois: "" }
    ]
  },
  metas: {
    ano1: [],
    ano3: [],
    ano5: []
  },
  plano90: [
    { num: "01", foco: "", acoes: [] }
  ],
  gantt: [],
  proximos_passos: [],
  frase_closing: ""
};
*/
