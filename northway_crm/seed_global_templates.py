import json
from app import app
from models import db, DriveFolderTemplate

TEMPLATES = [
    {
        "name": "🔹 TEMPLATE 01 — NorthWay | Crescimento Contínuo (Padrão)",
        "structure": [
            {"name": "Contrato & Financeiro"},
            {
                "name": "Diagnóstico & Direção",
                "children": [
                    {"name": "Diagnóstico da Empresa"},
                    {"name": "Posicionamento & Oferta"},
                    {"name": "Jornada do Cliente"},
                    {"name": "Metas & KPIs"}
                ]
            },
            {
                "name": "Acessos & Contas",
                "children": [
                    {"name": "Redes Sociais"},
                    {"name": "Google (Ads / Analytics / GMB)"},
                    {"name": "Meta Ads"}
                ]
            },
            {
                "name": "ATRAIR",
                "children": [
                    {
                        "name": "Tráfego Pago",
                        "children": [{"name": "Google Ads"}, {"name": "Meta Ads"}]
                    },
                    {
                        "name": "Landing Pages",
                        "children": [{"name": "Estrutura"}, {"name": "Copies"}, {"name": "Versões Publicadas"}]
                    },
                    {"name": "Criativos de Aquisição"}
                ]
            },
            {
                "name": "ENGAJAR",
                "children": [
                    {"name": "Conteúdo & Social Media"},
                    {"name": "Endomarketing"},
                    {"name": "Relacionamento & Experiência"}
                ]
            },
            {
                "name": "VENDER",
                "children": [
                    {"name": "Ofertas"},
                    {"name": "Funil & Conversão"}
                ]
            },
            {
                "name": "RETER & VENDER DE NOVO",
                "children": [
                    {"name": "Remarketing"},
                    {"name": "Pós-venda"},
                    {"name": "Fidelização"}
                ]
            },
            {
                "name": "Relatórios & Resultados",
                "children": [
                    {"name": "Relatórios Mensais"},
                    {"name": "Dashboards"},
                    {"name": "Insights"}
                ]
            }
        ]
    },
    {
        "name": "🔹 TEMPLATE 02 — NorthWay | Growth por Ciclo",
        "structure": [
            {
                "name": "Onboarding & Base",
                "children": [{"name": "Acessos"}, {"name": "Checklist Inicial"}, {"name": "Materiais Base"}]
            },
            {
                "name": "Estratégia",
                "children": [
                    {"name": "Diagnóstico"},
                    {"name": "Direção Estratégica"},
                    {"name": "Jornada & Funil"},
                    {"name": "KPIs"}
                ]
            },
            {
                "name": "Banco de Ativos",
                "children": [{"name": "Logos"}, {"name": "Fotos"}, {"name": "Vídeos"}, {"name": "Identidade"}]
            },
            {
                "name": "Execução por Ciclo",
                "children": [
                    {
                        "name": "Ciclo 01 - Aquisição",
                        "children": [{"name": "Tráfego"}, {"name": "Landing Pages"}, {"name": "Relatório"}]
                    },
                    {
                        "name": "Ciclo 02 - Engajamento",
                        "children": [{"name": "Conteúdo"}, {"name": "Endomarketing"}, {"name": "Relatório"}]
                    },
                    {
                        "name": "Ciclo 03 - Retenção",
                        "children": [{"name": "Remarketing"}, {"name": "Pós-venda"}, {"name": "Relatório"}]
                    }
                ]
            },
            {
                "name": "Histórico & Decisões",
                "children": [{"name": "Insights"}, {"name": "Ajustes"}, {"name": "Decisões Tomadas"}]
            }
        ]
    },
    {
        "name": "🔹 TEMPLATE 03 — Agência de Marketing / Social Media",
        "structure": [
            {"name": "Contrato & Briefing"},
            {
                "name": "Branding",
                "children": [{"name": "Logo"}, {"name": "Identidade Visual"}, {"name": "Manual de Marca"}]
            },
            {
                "name": "Social Media",
                "children": [
                    {"name": "Planejamento"},
                    {
                        "name": "Criativos",
                        "children": [{"name": "Feed"}, {"name": "Stories"}, {"name": "Reels"}]
                    },
                    {"name": "Copies"},
                    {"name": "Aprovados"}
                ]
            },
            {
                "name": "Tráfego Pago",
                "children": [{"name": "Criativos"}, {"name": "Copies"}, {"name": "Relatórios"}]
            },
            {"name": "Relatórios & Resultados"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 04 — Tráfego Pago (Google & Meta)",
        "structure": [
            {"name": "Contrato & Escopo"},
            {
                "name": "Planejamento",
                "children": [{"name": "Público & Oferta"}, {"name": "Estratégia"}]
            },
            {
                "name": "Google Ads",
                "children": [{"name": "Campanhas"}, {"name": "Criativos"}, {"name": "Relatórios"}]
            },
            {
                "name": "Meta Ads",
                "children": [{"name": "Campanhas"}, {"name": "Criativos"}, {"name": "Relatórios"}]
            },
            {
                "name": "Landing Pages",
                "children": [{"name": "Estrutura"}, {"name": "Copies"}, {"name": "Testes"}]
            },
            {"name": "Resultados & Otimizações"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 05 — Consultoria / Estratégia",
        "structure": [
            {"name": "Contrato & Escopo"},
            {
                "name": "Diagnóstico",
                "children": [{"name": "Questionários"}, {"name": "Análises"}, {"name": "Insights"}]
            },
            {
                "name": "Planejamento",
                "children": [{"name": "Estratégia"}, {"name": "Roadmap"}, {"name": "KPIs"}]
            },
            {"name": "Execução"},
            {"name": "Relatórios"},
            {"name": "Reuniões & Atas"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 06 — Endomarketing & Cultura",
        "structure": [
            {"name": "Contrato & Escopo"},
            {
                "name": "Diagnóstico Interno",
                "children": [{"name": "Pesquisas"}, {"name": "Clima Organizacional"}]
            },
            {
                "name": "Planejamento",
                "children": [{"name": "Campanhas"}, {"name": "Ações Internas"}]
            },
            {
                "name": "Materiais",
                "children": [{"name": "Comunicados"}, {"name": "Criativos"}]
            },
            {"name": "Execução"},
            {"name": "Resultados & Feedback"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 07 — Landing Pages & Conversão",
        "structure": [
            {"name": "Contrato & Briefing"},
            {
                "name": "Pesquisa & Estratégia",
                "children": [{"name": "Oferta"}, {"name": "Persona"}]
            },
            {"name": "Estrutura da Página"},
            {"name": "Copies"},
            {"name": "Design"},
            {"name": "Versões Publicadas"},
            {"name": "Testes & Otimizações"},
            {"name": "Resultados"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 08 — TI / Software / Automação",
        "structure": [
            {"name": "Contrato & Proposta"},
            {"name": "Levantamento de Requisitos"},
            {
                "name": "Documentação Técnica",
                "children": [{"name": "APIs"}, {"name": "Diagramas"}, {"name": "Credenciais"}]
            },
            {"name": "Desenvolvimento"},
            {"name": "Homologação"},
            {"name": "Produção"},
            {"name": "Relatórios & Logs"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 09 — Jurídico / Contábil",
        "structure": [
            {"name": "Contrato & Procuração"},
            {"name": "Documentos do Cliente"},
            {"name": "Processos"},
            {"name": "Petições & Protocolos"},
            {"name": "Pareceres"},
            {"name": "Financeiro"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 10 — Obras / Arquitetura / Engenharia",
        "structure": [
            {"name": "Contrato & Escopo"},
            {
                "name": "Projeto",
                "children": [{"name": "Plantas"}, {"name": "3D / Render"}, {"name": "Aprovações"}]
            },
            {
                "name": "Execução",
                "children": [{"name": "Cronograma"}, {"name": "Fotos da Obra"}, {"name": "Medições"}]
            },
            {"name": "Fornecedores"},
            {"name": "Relatórios"},
            {"name": "Entrega Final"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 11 — Treinamentos / Mentoria / Cursos",
        "structure": [
            {"name": "Contrato & Inscrição"},
            {
                "name": "Materiais",
                "children": [{"name": "Aulas"}, {"name": "Slides"}, {"name": "Apostilas"}]
            },
            {"name": "Exercícios"},
            {"name": "Certificados"},
            {"name": "Feedback & Avaliações"}
        ]
    },
    {
        "name": "🔹 TEMPLATE 12 — Universal / Simples",
        "structure": [
            {"name": "Contrato & Financeiro"},
            {"name": "Onboarding"},
            {"name": "Materiais"},
            {"name": "Entregas"},
            {"name": "Relatórios"}
        ]
    }
]

def seed():
    with app.app_context():
        # Clear existing global templates to avoid duplicates during dev
        # DriveFolderTemplate.query.filter_by(scope='global').delete()
        
        for t_data in TEMPLATES:
            # Check if exists by name
            exists = DriveFolderTemplate.query.filter_by(name=t_data["name"], scope='global').first()
            if exists:
                print(f"Skipping {t_data['name']} (already exists)")
                continue
                
            template = DriveFolderTemplate(
                name=t_data["name"],
                structure_json=json.dumps(t_data["structure"]),
                scope='global',
                company_id=None
            )
            db.session.add(template)
            print(f"Adding {t_data['name']}...")
        
        db.session.commit()
        print("✅ Global templates seeded successfully!")

if __name__ == "__main__":
    seed()
