from app import create_app, db
from models import ProcessTemplate, ClientChecklist, Company
import json

def migrate():
    app = create_app()
    with app.app_context():
        # 1. Create Tables
        print("Creating ProcessTemplate and ClientChecklist tables...")
        db.create_all()
        
        # 2. Seed Default NorthWay Process
        # The user provided a very specific 9-step checklist.
        # We will add this to all existing companies.
        
        default_steps = [
            {
                "title": "CHECILIST 1 — FECHAMENTO E CONTRATO",
                "items": [
                    "Proposta aprovada",
                    "Plano contratado definido",
                    "Forma de pagamento confirmada",
                    "Contrato assinado",
                    "Cliente cadastrado no CRM",
                    "Pasta do cliente criada (Drive/Notion)"
                ]
            },
            {
                "title": "CHECKLIST 2 — ONBOARDING DO CLIENTE (48H)",
                "items": [
                    "Enviar formulário de briefing",
                    "Solicitar acessos (Instagram, FB, Ads, Analytics)",
                    "Definir responsável do cliente",
                    "Agendar reunião de Kickoff"
                ]
            },
            {
                "title": "CHECKLIST 3 — REUNIÃO DE KICKOFF",
                "items": [
                    "Entendimento do negócio (Objetivos, Público, Tom)",
                    "Definição de KPIs",
                    "Alinhamento de expectativas",
                    "Registrar tudo em documento padrão"
                ]
            },
            {
                "title": "CHECKLIST 4 — DIAGNÓSTICO E PLANEJAMENTO",
                "items": [
                    "Análise das redes sociais e concorrentes",
                    "Definição de objetivo do mês",
                    "Planejamento de conteúdo e campanhas",
                    "Calendário aprovado pelo cliente"
                ]
            },
            {
                "title": "CHECKLIST 5 — PRODUÇÃO DE CONTEÚDO",
                "items": [
                    "Criar pautas e copies",
                    "Criar artes e vídeos",
                    "Revisar e enviar para aprovação",
                    "Ajustes e agendamento"
                ]
            },
            {
                "title": "CHECKLIST 6 — TRÁFEGO PAGO",
                "items": [
                    "Criar e configurar campanhas (Públicos, Criativos)",
                    "Subir campanhas",
                    "Monitorar desempenho e otimizar"
                ]
            },
            {
                "title": "CHECKLIST 7 — MONITORAMENTO",
                "items": [
                    "Coletar métricas sociais e de tráfego",
                    "Analisar resultados e gerar insights"
                ]
            },
            {
                "title": "CHECKLIST 8 — RELATÓRIO E REUNIÃO",
                "items": [
                    "Criar e enviar relatório mensal",
                    "Realizar reunião mensal",
                    "Planejar próximo mês"
                ]
            },
            {
                "title": "CHECKLIST 9 — ESCALA / UPSELL (TRIMESTRAL)",
                "items": [
                    "Avaliar maturidade do cliente",
                    "Identificar gargalos e sugerir upgrades",
                    "Registrar oportunidades no CRM"
                ]
            }
        ]

        companies = Company.query.all()
        for company in companies:
            # Check if exists
            exists = ProcessTemplate.query.filter_by(company_id=company.id, name='Fluxo Padrão NorthWay').first()
            if not exists:
                print(f"Seeding default process for Company {company.name}...")
                template = ProcessTemplate(
                    name='Fluxo Padrão NorthWay',
                    description='Checklist completo de Onboarding a Escala.',
                    steps=default_steps, # SQLAlchemy handles JSON serialization if using SQLite JSON type or we pass dict
                    company_id=company.id
                )
                db.session.add(template)
        
        db.session.commit()
        print("Migration and Seeding complete.")

if __name__ == '__main__':
    migrate()
