
import sqlite3
import uuid
import random
import json
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

def seed_creative_data():
    print("🚀 Starting CREATIVE data seeding for NorthWay...")
    import os
    
    # DETERMINE DB PATH CHECK
    # Match app.py logic: if root is not writable, use /tmp
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = 'crm.db'
    
    if not os.access(base_dir, os.W_OK):
        print("⚠️ Read-only filesystem detected. Using /tmp/crm.db")
        db_path = '/tmp/crm.db'
    
    print(f"📂 using database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- 1. USER & COMPANY SETUP ---
    # Target: Admin@northway.com.br
    email = "Admin@northway.com.br"
    print(f"👤 target user: {email}")

    # Check/Create User
    cursor.execute("SELECT id, company_id FROM user WHERE email = ?", (email,))
    user_row = cursor.fetchone()

    if user_row:
        user_id, company_id = user_row
        print(f"✅ User found (ID: {user_id}). Updating Company (ID: {company_id})...")
        # Ensure company is active and pro
        cursor.execute("UPDATE company SET name = 'NorthWay Demo', plan = 'pro', status = 'active', payment_status = 'active' WHERE id = ?", (company_id,))
    else:
        # Create Company
        cursor.execute("INSERT INTO company (name, plan, status, payment_status, created_at) VALUES (?, ?, ?, ?, ?)",
                       ("NorthWay Demo", "pro", "active", "active", datetime.now(timezone.utc)))
        company_id = cursor.lastrowid
        
        # Create Role
        admin_perms = json.dumps([
            'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
            'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
            'company_settings_view', 'processes_view', 'library_view', 
            'prospecting_view', 'admin_view'
        ])
        cursor.execute("INSERT INTO role (name, company_id, is_default, permissions) VALUES (?, ?, ?, ?)",
                       ('Administrador', company_id, 1, admin_perms))
        role_id = cursor.lastrowid
        
        # Create User
        pw_hash = generate_password_hash('123456') # Simple pass for demo
        cursor.execute("""
            INSERT INTO user (name, email, password_hash, role, company_id, role_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('Admin NorthWay', email, pw_hash, 'admin', company_id, role_id, datetime.now(timezone.utc)))
        user_id = cursor.lastrowid
        print(f"✅ Created New User & Company (User ID: {user_id}, Company ID: {company_id})")

    # Clean existing data for this company to avoid clutter
    print("🧹 Cleaning existing demo data for this company...")
    cursor.execute("DELETE FROM lead WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM client WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM 'transaction' WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM expense WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM task WHERE company_id = ?", (company_id,))
    cursor.execute("DELETE FROM pipeline WHERE company_id = ? AND name = 'Processo de Escala'", (company_id,))
    
    # --- 2. PIPELINE & LEADS ---
    # Create "Processo de Escala" Pipeline
    cursor.execute("INSERT INTO pipeline (name, company_id, created_at) VALUES (?, ?, ?)",
                   ('Processo de Escala', company_id, datetime.now(timezone.utc)))
    pipeline_id = cursor.lastrowid
    
    stages = [
        ('Novo Lead', 0), ('Qualificação', 1), ('Apresentação', 2), 
        ('Negociação', 3), ('Fechado (Ganhou)', 4), ('Perdido', 5)
    ]
    stage_ids = {}
    for name, order in stages:
        cursor.execute("INSERT INTO pipeline_stage (name, \"order\", pipeline_id, company_id) VALUES (?, ?, ?, ?)",
                       (name, order, pipeline_id, company_id))
        stage_ids[name] = cursor.lastrowid

    # Associate User
    cursor.execute("DELETE FROM user_pipeline_association WHERE user_id = ? AND pipeline_id = ?", (user_id, pipeline_id))
    cursor.execute("INSERT INTO user_pipeline_association (user_id, pipeline_id) VALUES (?, ?)", (user_id, pipeline_id))

    # Generate 50 Leads
    lead_sources = ["Instagram Ads", "Google Search", "Indicação", "Outbound", "Webinar"]
    names_first = ["Ana", "Bruno", "Carlos", "Daniela", "Eduardo", "Fernanda", "Gustavo", "Helena", "Igor", "Juliana", "Lucas", "Mariana", "Nicolas", "Olivia", "Pedro", "Rafael", "Sofia", "Thiago", "Vitor", "Yasmin"]
    names_last = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins"]
    
    print("🌱 Seeding 50 Leads...")
    for i in range(50):
        first = random.choice(names_first)
        last = random.choice(names_last)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}_{i}@example.com"
        phone = f"119{random.randint(7000, 9999)}{random.randint(1000, 9999)}"
        source = random.choice(lead_sources)
        
        # Distribution
        if i < 15: s_name = 'Novo Lead'
        elif i < 25: s_name = 'Qualificação'
        elif i < 35: s_name = 'Apresentação'
        elif i < 42: s_name = 'Negociação'
        elif i < 46: s_name = 'Fechado (Ganhou)'
        else: s_name = 'Perdido'
        
        status = 'new'
        if s_name in ['Qualificação', 'Apresentação', 'Negociação']: status = 'in_progress'
        if s_name == 'Fechado (Ganhou)': status = 'won' # Or converted? checks model
        if s_name == 'Perdido': status = 'lost'
        
        # Recent dates
        created = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 60))
        
        cursor.execute("""
            INSERT INTO lead (name, email, phone, source, status, company_id, pipeline_id, pipeline_stage_id, assigned_to_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, source, status, company_id, pipeline_id, stage_ids[s_name], user_id, created))

    # --- 3. CLIENTS & FINANCIALS ---
    print("💼 Seeding Clients & Financial History...")
    
    # Financial Categories
    cats = {'revenue': None, 'expense': None, 'cost': None}
    for c_type, c_name in [('revenue', 'Vendas Serviço'), ('expense', 'Despesas Operacionais'), ('cost', 'Investimento Marketing')]:
        cursor.execute("SELECT id FROM financial_category WHERE company_id = ? AND type = ?", (company_id, c_type))
        row = cursor.fetchone()
        if row:
            cats[c_type] = row[0]
        else:
            cursor.execute("INSERT INTO financial_category (name, type, company_id) VALUES (?, ?, ?)", (c_name, c_type, company_id))
            cats[c_type] = cursor.lastrowid

    # Clients list
    clients_def = [
        ("TechStart Solutions", "Tecnologia", 4500.00),
        ("Grupo Varejo Brasil", "Varejo", 3200.00),
        ("Consultoria Alpha", "Consultoria", 2800.00),
        ("Logística Express", "Logística", 5100.00),
        ("Clínica Bem Estar", "Saúde", 1900.00),
        ("Educação Futuro", "Educação", 3500.00),
        ("Construtora Ramos", "Construção", 6000.00),
        ("Agência Criativa", "Marketing", 2500.00),
        ("Restaurante Sabor", "Alimentação", 1500.00),
        ("Advocacia Mendes", "Jurídico", 4000.00),
        ("Imobiliária Lar", "Imobiliário", 3000.00),
        ("Fitness Academia", "Esportes", 2200.00)
    ]

    # Ensure a Contract Template exists
    cursor.execute("SELECT id FROM contract_template WHERE company_id = ?", (company_id,))
    tmpl_row = cursor.fetchone()
    if tmpl_row:
        template_id = tmpl_row[0]
    else:
        cursor.execute("INSERT INTO contract_template (name, type, content, company_id, user_id, active) VALUES (?, ?, ?, ?, ?, ?)",
                       ('Contrato Padrão', 'service', '<p>Contrato...</p>', company_id, user_id, 1))
        template_id = cursor.lastrowid
        
    for c_name, niche, mrr in clients_def:
        # Create Client
        start_date = (datetime.now(timezone.utc) - timedelta(days=random.randint(60, 365))).date()
        cursor.execute("""
            INSERT INTO client (name, email, company_id, status, health_status, account_manager_id, created_at, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (c_name, f"contato@{c_name.lower().replace(' ','')}.com", company_id, 'ativo', 'verde', user_id, datetime.now(timezone.utc), start_date))
        client_id = cursor.lastrowid
        
        # Create Dummy Contract
        cursor.execute("INSERT INTO contract (client_id, company_id, template_id, status, created_at, code) VALUES (?, ?, ?, ?, ?, ?)",
                       (client_id, company_id, template_id, 'signed', datetime.now(timezone.utc), f"CTR-{random.randint(100,999)}"))
        contract_id = cursor.lastrowid
        
        # Generate 6 months of transactions (Revenue)
        for m in range(6):
            date_ref = datetime.now(timezone.utc) - timedelta(days=m*30)
            due_date = date_ref.replace(day=random.randint(5, 25))
            
            # Last month simulated as 'pending' for some
            status = 'paid'
            if m == 0 and random.random() > 0.3: status = 'pending'
            
            paid_date = due_date if status == 'paid' else None
            
            cursor.execute("""
                INSERT INTO 'transaction' (description, amount, status, due_date, paid_date, company_id, client_id, contract_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"Mensalidade - {c_name}", mrr, status, due_date, paid_date, company_id, client_id, contract_id, date_ref))

    # Expenses (Cost & Operational)
    print("💰 Seeding Expenses...")
    expenses_def = [
        ("Servidores AWS", 850.00, cats['expense']),
        ("Licença Software CRM", 450.00, cats['expense']),
        ("Campanha Google Ads", 2500.00, cats['cost']),
        ("Campanha Instagram", 1800.00, cats['cost']),
        ("Aluguel Escritório", 3000.00, cats['expense']),
        ("Equipe de Vendas", 8000.00, cats['expense'])
    ]
    
    for m in range(6):
        date_ref = datetime.now(timezone.utc) - timedelta(days=m*30)
        for desc, amount, cat_id in expenses_def:
             # Variations
             act_amount = amount * random.uniform(0.9, 1.1)
             due_date = date_ref.replace(day=random.randint(1, 28))
             
             status = 'paid'
             if m == 0 and due_date.date() > datetime.now().date(): status = 'pending'
             
             cursor.execute("""
                INSERT INTO expense (description, amount, status, due_date, paid_date, category_id, company_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
             """, (desc, act_amount, status, due_date, (due_date if status=='paid' else None), cat_id, company_id, user_id, date_ref))


    # --- 4. TASKS ---
    print("📅 Seeding Tasks...")
    tasks = [
        ("Reunião de Alinhamento - TechStart", "media", "pendente"),
        ("Enviar Proposta - Novo Lead", "alta", "pendente"),
        ("Renovar Contrato - Grupo Varejo", "alta", "pendente"),
        ("Acompanhamento mensal - Clínica", "baixa", "concluida"),
        ("Feedback Campanha Marketing", "media", "concluida"),
        ("Ajustar Pipeline de Vendas", "media", "pendente")
    ]
    
    for title, prio, status in tasks:
        due = datetime.now(timezone.utc) + timedelta(days=random.randint(-2, 5))
        cursor.execute("INSERT INTO task (title, priority, status, due_date, company_id, assigned_to_id) VALUES (?, ?, ?, ?, ?, ?)",
                       (title, prio, status, due, company_id, user_id))

    conn.commit()
    conn.close()
    print("✨ CREATIVE SEEDING COMPLETE! ✨")
    print(f"👉 Login: {email} / 123456")

if __name__ == "__main__":
    seed_creative_data()
