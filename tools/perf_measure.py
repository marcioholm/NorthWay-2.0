#!/usr/bin/env python3
import os
import sys
import time
import random
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

# Ensure project root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CRM_PATH = os.path.join(REPO_ROOT, 'northway_crm')
if CRM_PATH not in sys.path:
    sys.path.insert(0, CRM_PATH)

DB_FILE = os.path.join(REPO_ROOT, 'perf_benchmark.db')
DATABASE_URL = f"sqlite:///{DB_FILE}"

os.environ['DATABASE_URL'] = DATABASE_URL
os.environ['SECRET_KEY'] = 'perf-measurement-secret-key-123'
os.environ['RATELIMIT_ENABLED'] = 'False'
os.environ['WTF_CSRF_ENABLED'] = 'False'
os.environ['TESTING'] = 'True'

from app import create_app
from models import (
    db, Company, User, Pipeline, PipelineStage, Lead, Client,
    Task, Interaction, Transaction, ContractTemplate, Contract,
    Goal, Opportunity, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES,
    ProspectingCampaign
)
from sqlalchemy import event
from sqlalchemy.engine import Engine

app = create_app({
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
    'WTF_CSRF_ENABLED': False,
    'RATELIMIT_ENABLED': False
})

def seed_database():
    print(f"[*] Checking database: {DB_FILE}")
    if os.path.exists(DB_FILE):
        with app.app_context():
            lead_count = Lead.query.count()
            if lead_count >= 3000:
                print(f"[+] Reusing existing database with {lead_count} leads.")
                return

    print("[*] Creating schema and seeding performance test dataset...")
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except OSError:
            pass

    with app.app_context():
        db.create_all()

        # 1 Empresa
        company = Company(
            id=1,
            name="NorthWay Performance Corp",
            document="12.345.678/0001-90",
            cpf_cnpj="12345678000190",
            status="active",
            payment_status="active",
            plan="pro",
            features={"prospecting": True, "whatsapp": True},
            tax_rate=0.05
        )
        db.session.add(company)
        db.session.commit()

        # 6 Usuários
        pwd_hash = generate_password_hash("perfpass123")
        users = [
            User(id=1, name="Admin NorthWay", email="admin@northway.com.br", password_hash=pwd_hash, role=ROLE_ADMIN, company_id=1),
            User(id=2, name="Gestor Comercial", email="gestor@northway.com.br", password_hash=pwd_hash, role=ROLE_MANAGER, company_id=1),
            User(id=3, name="Vendedor Alfa", email="alfa@northway.com.br", password_hash=pwd_hash, role=ROLE_SALES, company_id=1),
            User(id=4, name="Vendedor Beta", email="beta@northway.com.br", password_hash=pwd_hash, role=ROLE_SALES, company_id=1),
            User(id=5, name="Vendedor Gama", email="gama@northway.com.br", password_hash=pwd_hash, role=ROLE_SALES, company_id=1),
            User(id=6, name="Vendedor Delta", email="delta@northway.com.br", password_hash=pwd_hash, role=ROLE_SALES, company_id=1),
        ]
        db.session.bulk_save_objects(users)
        db.session.commit()

        # 1 Pipeline com 6 Etapas
        pipeline = Pipeline(id=1, name="Pipeline Comercial", company_id=1)
        db.session.add(pipeline)
        db.session.commit()

        stages = [
            PipelineStage(id=1, name="Novo Lead", pipeline_id=1, company_id=1, order=1),
            PipelineStage(id=2, name="Qualificação", pipeline_id=1, company_id=1, order=2),
            PipelineStage(id=3, name="Apresentação", pipeline_id=1, company_id=1, order=3),
            PipelineStage(id=4, name="Negociação", pipeline_id=1, company_id=1, order=4),
            PipelineStage(id=5, name="Fechado", pipeline_id=1, company_id=1, order=5),
            PipelineStage(id=6, name="Perdido", pipeline_id=1, company_id=1, order=6),
        ]
        db.session.bulk_save_objects(stages)
        db.session.commit()

        # 300 Clientes
        clients = []
        now = datetime.utcnow()
        for i in range(1, 301):
            clients.append(Client(
                id=i,
                name=f"Cliente Empresa {i:03d} Ltda",
                email=f"contato@cliente{i:03d}.com.br",
                phone=f"+55119888{i:04d}",
                company_id=1,
                account_manager_id=(i % 6) + 1,
                status="ativo" if i % 5 != 0 else "onboarding",
                health_status="verde" if i % 3 != 0 else ("amarelo" if i % 6 == 0 else "vermelho"),
                payment_status="em_dia" if i % 7 != 0 else "atrasado",
                start_date=(now - timedelta(days=i * 2)).date(),
                monthly_value=1500.0 + (i % 20) * 250.0,
                service="Consultoria Growth",
                contract_type="mensal",
                created_at=now - timedelta(days=i * 2)
            ))
        db.session.bulk_save_objects(clients)
        db.session.commit()

        # 3000 Leads
        leads = []
        statuses = ["new", "in_progress", "in_progress", "in_progress", "won", "lost"]
        for i in range(1, 3001):
            stage_idx = (i % 6) + 1
            leads.append(Lead(
                id=i,
                name=f"Lead Prospect {i:04d}",
                phone=f"+55119777{i:04d}",
                email=f"lead{i:04d}@empresa{i:04d}.com.br",
                company_id=1,
                pipeline_id=1,
                pipeline_stage_id=stage_idx,
                assigned_to_id=(i % 6) + 1,
                status=statuses[stage_idx - 1],
                estimated_value=3000.0 + (i % 15) * 500.0,
                created_at=now - timedelta(days=(i % 120), hours=(i % 24)),
                lost_at=(now - timedelta(days=(i % 30))) if stage_idx == 6 else None,
                lost_reason="Preço fora do budget" if stage_idx == 6 else None
            ))
        db.session.bulk_save_objects(leads)
        db.session.commit()

        # 1500 Tarefas (750 com lead, 750 com cliente)
        tasks = []
        today = now.date()
        for i in range(1, 1501):
            is_lead = (i <= 750)
            target_lead_id = i if is_lead else None
            target_client_id = ((i - 751) % 300) + 1 if not is_lead else None
            
            # Calibrate assigned user: 200 tasks assigned to user 1 so home reflects real dashboard volume
            assigned_id = 1 if (i <= 100 or i % 6 == 0) else ((i % 5) + 2)
            # Most tasks of user 1 are pending and due today/overdue
            if assigned_id == 1:
                status = "pendente" if (i % 4 != 0) else "concluida"
                due_dt = datetime.combine(today - timedelta(days=(i % 5)), datetime.min.time()) + timedelta(hours=14)
            else:
                day_offset = (i % 15) - 5
                due_dt = datetime.combine(today + timedelta(days=day_offset), datetime.min.time()) + timedelta(hours=14)
                status = "concluida" if (i % 2 == 0) else "pendente"

            tasks.append(Task(
                id=i,
                title=f"Tarefa #{i:04d} - {'Follow-up Lead' if is_lead else 'Alinhamento Cliente'}",
                description="Verificar pontos pendentes da reunião e enviar proposta atualizada.",
                due_date=due_dt,
                status=status,
                priority="alta" if i % 4 == 0 else ("urgente" if i % 10 == 0 else "media"),
                company_id=1,
                assigned_to_id=assigned_id,
                created_by_user_id=1,
                lead_id=target_lead_id,
                client_id=target_client_id,
                completed_at=(now - timedelta(hours=2)) if status == "concluida" else None
            ))
        db.session.bulk_save_objects(tasks)
        db.session.commit()

        # 4000 Interações (2000 com lead, 2000 com cliente)
        interactions = []
        types = ['ligacao', 'reuniao', 'email', 'nota', 'tarefa_criada']
        for i in range(1, 4001):
            is_lead = (i % 2 == 1)
            target_lead_id = ((i * 7) % 3000) + 1 if is_lead else None
            target_client_id = ((i * 3) % 300) + 1 if not is_lead else None
            interactions.append(Interaction(
                id=i,
                lead_id=target_lead_id,
                client_id=target_client_id,
                user_id=(i % 6) + 1,
                company_id=1,
                type=types[i % len(types)],
                content=f"Registro de interação #{i} realizada com sucesso.",
                created_at=now - timedelta(days=(i % 90), minutes=(i % 60))
            ))
        db.session.bulk_save_objects(interactions)
        db.session.commit()

        # 2500 Transações
        transactions = []
        rev_types = ['recorrente', 'pontual', 'setup_onboarding']
        for i in range(1, 2501):
            due_d = date(2026, ((i % 12) + 1), ((i % 27) + 1))
            status = 'paid' if (i % 3 != 0) else ('pending' if (i % 6 != 0) else 'overdue')
            transactions.append(Transaction(
                id=i,
                client_id=(i % 300) + 1,
                company_id=1,
                description=f"Mensalidade Recorrente Parcela #{((i % 12) + 1):02d}",
                amount=1200.0 + (i % 15) * 100.0,
                due_date=due_d,
                status=status,
                paid_date=due_d if status == 'paid' else None,
                revenue_type=rev_types[i % len(rev_types)],
                created_at=now - timedelta(days=(i % 180))
            ))
        db.session.bulk_save_objects(transactions)
        db.session.commit()

        # Support records for Goals, Contracts, Prospecting
        tmpl = ContractTemplate(
            id=1,
            company_id=1,
            name="Contrato Padrão de Prestação de Serviços",
            description="Modelo oficial de prestação de serviços",
            type="contract",
            content="<h1>Contrato</h1><p>Cláusulas contratuais do cliente {{nome}}.</p>",
            active=True
        )
        db.session.add(tmpl)
        db.session.commit()

        contracts = []
        for i in range(1, 21):
            contracts.append(Contract(
                id=i,
                client_id=(i % 300) + 1,
                company_id=1,
                template_id=1,
                code=f"CTR-2026-{i:03d}",
                status="signed" if i % 2 == 0 else "draft",
                amount=3500.0,
                created_at=now - timedelta(days=i * 5)
            ))
        db.session.bulk_save_objects(contracts)
        db.session.commit()

        goals = []
        for m in range(1, 13):
            goals.append(Goal(
                company_id=1,
                user_id=None,
                month=m,
                year=2026,
                target_amount=100000.0,
                min_new_sales=20000.0,
                type="revenue"
            ))
        db.session.bulk_save_objects(goals)
        db.session.commit()

        campaign = ProspectingCampaign(
            id=1,
            company_id=1,
            name="Campanha Inbound/Outbound Q4",
            status="active"
        )
        db.session.add(campaign)
        db.session.commit()

        print("[+] Seed completed successfully!")

def run_benchmarks():
    client = app.test_client()

    # Authenticate user 1 (Admin) in session
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_fresh'] = True
        sess['company_id'] = 1

    query_log = []
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        query_log.append(statement)

    event.listen(Engine, "before_cursor_execute", before_cursor_execute)

    pages = [
        ('/home', 'Home'),
        ('/dashboard', 'Dashboard'),
        ('/leads', 'Leads'),
        ('/pipeline', 'Pipeline'),
        ('/leads/1', 'Lead Details (/leads/1)'),
        ('/clients', 'Clients'),
        ('/clients/1', 'Client Details (/clients/1)'),
        ('/tasks', 'Tasks'),
        ('/financial', 'Financial'),
        ('/prospecting/dashboard', 'Prospecting Dashboard'),
        ('/goals', 'Goals'),
        ('/contracts', 'Contracts')
    ]

    print("\n" + "=" * 80)
    print("MEDICAO DE PERFORMANCE (BENCHMARK)")
    print("=" * 80)

    results = []

    for path, label in pages:
        # Warmup pass
        client.get(path)

        # Timed & counted pass
        query_log.clear()
        t0 = time.perf_counter()
        resp = client.get(path)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        n_queries = len(query_log)
        payload_bytes = len(resp.data)
        payload_kb = payload_bytes / 1024

        status = resp.status_code
        results.append({
            'path': path,
            'label': label,
            'queries': n_queries,
            'time_ms': elapsed_ms,
            'kb': payload_kb,
            'status': status
        })

    print(f"\n| {'Página':<30} | {'Status':<6} | {'Queries SQL':<12} | {'Tempo (ms)':<12} | {'Tamanho (KB)':<14} |")
    print(f"|{'-'*32}|{'-'*8}|{'-'*14}|{'-'*14}|{'-'*16}|")
    for r in results:
        print(f"| {r['path']:<30} | {r['status']:<6} | {r['queries']:<12} | {r['time_ms']:<12.1f} | {r['kb']:<14.1f} |")
    print("=" * 80)

    return results

if __name__ == '__main__':
    seed_database()
    run_benchmarks()
