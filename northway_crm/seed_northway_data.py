
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
import random

def seed_data():
    conn = sqlite3.connect('crm.db')
    cursor = conn.cursor()

    print("🚀 Starting data seeding for NorthWay...")

    # 1. Ensure Company 6 is Active
    cursor.execute("UPDATE company SET payment_status = 'active', subscription_status = 'active' WHERE id = 6")
    
    # 2. Check if Admin@northway.com.br exists, if not create
    cursor.execute("SELECT id FROM user WHERE email = 'Admin@northway.com.br'")
    user_exists = cursor.fetchone()
    
    if not user_exists:
        pw_hash = generate_password_hash('admin123')
        cursor.execute("""
            INSERT INTO user (name, email, password_hash, role, company_id, created_at, is_super_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('Admin NorthWay', 'Admin@northway.com.br', pw_hash, 'admin', 6, datetime.now(timezone.utc), 0))
        user_id = cursor.lastrowid
        print(f"✅ Created User: Admin@northway.com.br (ID: {user_id})")
    else:
        user_id = user_exists[0]
        print(f"ℹ️ User Admin@northway.com.br already exists (ID: {user_id})")

    # 3. Ensure "Administrador" role exists for company 6
    cursor.execute("SELECT id FROM role WHERE name = 'Administrador' AND company_id = 6")
    role_exists = cursor.fetchone()
    if not role_exists:
        import json
        admin_perms = json.dumps([
            'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
            'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
            'company_settings_view', 'processes_view', 'library_view', 
            'prospecting_view', 'admin_view'
        ])
        cursor.execute("INSERT INTO role (name, company_id, is_default, permissions) VALUES (?, ?, ?, ?)",
                       ('Administrador', 6, 1, admin_perms))
        role_id = cursor.lastrowid
        cursor.execute("UPDATE user SET role_id = ? WHERE id = ?", (role_id, user_id))
        print(f"✅ Created Role: Administrador (ID: {role_id})")
    else:
        role_id = role_exists[0]
        cursor.execute("UPDATE user SET role_id = ? WHERE id = ?", (role_id, user_id))

    # 4. Create Pipeline "Escala NorthWay"
    cursor.execute("SELECT id FROM pipeline WHERE name = 'Escala NorthWay' AND company_id = 6")
    pipeline_exists = cursor.fetchone()
    if not pipeline_exists:
        cursor.execute("INSERT INTO pipeline (name, company_id, created_at) VALUES (?, ?, ?)",
                       ('Escala NorthWay', 6, datetime.now(timezone.utc)))
        pipeline_id = cursor.lastrowid
        print(f"✅ Created Pipeline: Escala NorthWay (ID: {pipeline_id})")
    else:
        pipeline_id = pipeline_exists[0]
        print(f"ℹ️ Pipeline Escala NorthWay already exists (ID: {pipeline_id})")

    # 5. Create Pipeline Stages
    stages = [
        ('Novo Lead', 0),
        ('Qualificação', 1),
        ('Apresentação', 2),
        ('Negociação', 3),
        ('Fechado (Ganhou)', 4),
        ('Perdido', 5)
    ]
    stage_ids = {}
    for name, order in stages:
        cursor.execute("SELECT id FROM pipeline_stage WHERE name = ? AND pipeline_id = ?", (name, pipeline_id))
        s_exists = cursor.fetchone()
        if not s_exists:
            cursor.execute("INSERT INTO pipeline_stage (name, \"order\", pipeline_id, company_id) VALUES (?, ?, ?, ?)",
                           (name, order, pipeline_id, 6))
            stage_ids[name] = cursor.lastrowid
        else:
            stage_ids[name] = s_exists[0]
    
    # Associate user with pipeline
    cursor.execute("SELECT user_id FROM user_pipeline_association WHERE user_id = ? AND pipeline_id = ?", (user_id, pipeline_id))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO user_pipeline_association (user_id, pipeline_id) VALUES (?, ?)", (user_id, pipeline_id))

    # 6. Seed Leads (25 realistic leads)
    lead_names = [
        "Ricardo Santos", "Mariana Oliveira", "Lucas Ferreira", "Ana Paula Souza", "Bruno Mendes",
        "Carla Dias", "Eduardo Gomes", "Fernanda Lima", "Gustavo Rocha", "Helena Castro",
        "Igor Silva", "Juliana Costa", "Kevin White", "Laura Martins", "Marcos Viana",
        "Natália Ramos", "Otávio Pereira", "Priscila Nogueira", "Rafael Barbosa", "Sofia Xavier",
        "Tiago Fontana", "Ursula Andrade", "Victor Hugo", "Wanessa Camargo", "Yago Torres"
    ]
    sources = ["Meta Ads", "Google Search", "LinkedIn", "Referral", "Cold Outreach"]
    interests = ["High-Performance Growth", "CRM Implementation", "Scientific Marketing", "Sales Strategy"]

    print("🌱 Seeding leads...")
    for i, name in enumerate(lead_names):
        # Unique email and phone
        email = f"{name.lower().replace(' ', '.')}@example.com"
        phone = f"+55119{random.randint(7000, 9999)}{random.randint(1000, 9999)}"
        source = random.choice(sources)
        interest = random.choice(interests)
        
        # Distribute leads among stages
        if i < 8: stage_name = 'Novo Lead'
        elif i < 14: stage_name = 'Qualificação'
        elif i < 18: stage_name = 'Apresentação'
        elif i < 22: stage_name = 'Negociação'
        else: stage_name = 'Perdido'
        
        status = 'new'
        if stage_name in ['Qualificação', 'Apresentação', 'Negociação']: status = 'in_progress'
        if stage_name == 'Perdido': status = 'lost'

        # Check if exists
        cursor.execute("SELECT id FROM lead WHERE email = ? AND company_id = 6", (email,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO lead (name, email, phone, source, interest, status, company_id, pipeline_id, pipeline_stage_id, assigned_to_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, email, phone, source, interest, status, 6, pipeline_id, stage_ids[stage_name], user_id, datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))))

    # 7. Seed Clients (8 active clients)
    client_companies = [
        "Techflow Solutions", "Gourmet Garden", "Solar Peak", "FitLife Academia", 
        "Global Logistics", "Innovate HR", "Blue Horizon Estate", "Urban Gear"
    ]
    
    print("💼 Seeding clients...")
    for i, c_name in enumerate(client_companies):
        email = f"contato@{c_name.lower().replace(' ', '')}.com.br"
        
        cursor.execute("SELECT id FROM client WHERE name = ? AND company_id = 6", (c_name,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO client (name, email, phone, company_id, account_manager_id, status, health_status, start_date, monthly_value, service, contract_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c_name, email, "+551133221122", 6, user_id, 'ativo', 'verde', (datetime.now(timezone.utc) - timedelta(days=random.randint(60, 180))).date(), 
                  random.randint(2500, 7500), "Growth Consulting", "mensal", datetime.now(timezone.utc)))
            client_id = cursor.lastrowid
            
            # Create a contract for each client
            cursor.execute("SELECT id FROM contract_template WHERE company_id = 6 LIMIT 1")
            tmpl = cursor.fetchone()
            if not tmpl:
                cursor.execute("INSERT INTO contract_template (company_id, name, type, content, active) VALUES (?, ?, ?, ?, ?)",
                               (6, 'Contrato de Escala Padrão', 'contract', '<h1>Contrato de Prestação de Serviços</h1><p>...</p>', 1))
                tmpl_id = cursor.lastrowid
            else:
                tmpl_id = tmpl[0]
            
            cursor.execute("INSERT INTO contract (client_id, company_id, template_id, status, created_at, code) VALUES (?, ?, ?, ?, ?, ?)",
                           (client_id, 6, tmpl_id, 'signed', datetime.now(timezone.utc), f"CTR-2024-{i+1:03d}"))
            contract_id = cursor.lastrowid

            # Create Transactions (MRR history)
            for m in range(0, 3): # Last 3 months
                due = (datetime.now(timezone.utc) - timedelta(days=m*30)).date()
                status = 'paid' if m > 0 or random.random() > 0.5 else 'pending'
                paid_date = due if status == 'paid' else None
                cursor.execute("""
                    INSERT INTO "transaction" (contract_id, client_id, company_id, description, amount, due_date, status, paid_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (contract_id, client_id, 6, f"Mensalidade NorthWay - Mes {3-m}", 4500.0, due, status, paid_date, datetime.now(timezone.utc)))

    # 8. Seed Financial Expenses (Financial Dashboard data)
    categories = ['Marketing', 'Equipe', 'Escritório', 'Impostos']
    print("💰 Seeding expenses...")
    for cat_name in categories:
        cursor.execute("SELECT id FROM financial_category WHERE name = ? AND company_id = 6", (cat_name,))
        cat_data = cursor.fetchone()
        if not cat_data:
            cursor.execute("INSERT INTO financial_category (name, type, company_id, is_default) VALUES (?, ?, ?, ?)",
                           (cat_name, 'expense', 6, 1))
            cat_id = cursor.lastrowid
        else:
            cat_id = cat_data[0]
        
        for i in range(5):
           cursor.execute("""
               INSERT INTO expense (description, amount, due_date, status, category_id, company_id, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           """, (f"Pagamento {cat_name} {i+1}", random.randint(500, 2000), datetime.now(timezone.utc).date(), 'paid', cat_id, 6, user_id, datetime.now(timezone.utc)))

    # 9. Seed Tasks
    print("📅 Seeding tasks...")
    task_titles = ["Follow-up Proposta", "Reunião de Alinhamento", "Enviar Contrato", "Analisar Métricas", "Call de Onboarding"]
    for i in range(15):
        due = datetime.now(timezone.utc) + timedelta(days=random.randint(-5, 10))
        status = 'concluida' if due < datetime.now(timezone.utc) else 'pendente'
        cursor.execute("""
            INSERT INTO task (title, due_date, priority, status, company_id, assigned_to_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (random.choice(task_titles), due, 'media', status, 6, user_id))

    conn.commit()
    conn.close()
    print("✨ Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()
