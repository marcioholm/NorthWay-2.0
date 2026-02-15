
import os
import sys
from sqlalchemy import create_engine, text

# Get DB URL from environment
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Try to find crm.db in current dir
    if os.path.exists('crm.db'):
        db_url = 'sqlite:///crm.db'
    else:
        print("❌ DATABASE_URL not found and crm.db not in current directory.")
        sys.exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to {db_url}...")

engine = create_engine(db_url)

with engine.connect() as conn:
    print("🚀 Running migrations...")

    # 1. Update User Table
    print("   Adding commercial fields to 'user' table...")
    fields = [
        ("funcao_comercial", "VARCHAR(100)"),
        ("tipo_vinculo", "VARCHAR(20)"),
        ("papel_comercial_id", "VARCHAR(36)"),
        ("regra_comissao_id", "VARCHAR(36)")
    ]
    for field, ftype in fields:
        try:
            conn.execute(text(f"ALTER TABLE user ADD COLUMN {field} {ftype};"))
            print(f"   ✅ user.{field} added.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print(f"   ℹ️ user.{field} already exists.")
            else:
                print(f"   ⚠️ Error adding user.{field}: {e}")

    # 2. Create Papeis Comerciais
    print("   Creating 'papeis_comerciais' table...")
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS papeis_comerciais (
        id VARCHAR(36) PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES company(id),
        nome VARCHAR(100) NOT NULL,
        descricao TEXT,
        tipo_vinculo VARCHAR(20) NOT NULL,
        ativo BOOLEAN DEFAULT TRUE,
        created_at DATETIME,
        updated_at DATETIME
    );
    """))

    # 3. Create Regras Comissao
    print("   Creating 'regras_comissao' table...")
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS regras_comissao (
        id VARCHAR(36) PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES company(id),
        papel_comercial_id VARCHAR(36) NOT NULL REFERENCES papeis_comerciais(id),
        modelo VARCHAR(50) NOT NULL,
        parametros JSON NOT NULL,
        ativo BOOLEAN DEFAULT TRUE,
        created_at DATETIME,
        updated_at DATETIME
    );
    """))

    # 4. Create Comissao Snapshots
    print("   Creating 'comissao_snapshots' table...")
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS comissao_snapshots (
        id VARCHAR(36) PRIMARY KEY,
        contract_id INTEGER NOT NULL REFERENCES contract(id),
        beneficiario_id INTEGER NOT NULL REFERENCES user(id),
        papel_comercial_id VARCHAR(36) NOT NULL REFERENCES papeis_comerciais(id),
        regra_id VARCHAR(36) NOT NULL REFERENCES regras_comissao(id),
        modelo VARCHAR(50) NOT NULL,
        percentual_provisorio FLOAT NOT NULL,
        percentual_definitivo FLOAT,
        data_fechamento DATETIME,
        competencia_fechamento VARCHAR(7) NOT NULL,
        base_calculo VARCHAR(20) DEFAULT 'valor_pago',
        recorrente BOOLEAN DEFAULT TRUE
    );
    """))

    # 5. Create Contas a Pagar
    print("   Creating 'contas_a_pagar' table...")
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS contas_a_pagar (
        id VARCHAR(36) PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES company(id),
        tipo VARCHAR(20) NOT NULL,
        beneficiario_id INTEGER REFERENCES user(id),
        contract_id INTEGER REFERENCES contract(id),
        cliente_id INTEGER REFERENCES client(id),
        asaas_payment_id VARCHAR(50),
        competencia VARCHAR(7) NOT NULL,
        valor_base_contratual NUMERIC(12, 2) NOT NULL,
        valor_pago_cliente_total NUMERIC(12, 2) NOT NULL,
        juros_cliente NUMERIC(12, 2) DEFAULT 0.00,
        multa_cliente NUMERIC(12, 2) DEFAULT 0.00,
        percentual_aplicado FLOAT NOT NULL,
        valor_comissao_calculado NUMERIC(12, 2) NOT NULL,
        valor_final_pago_colaborador NUMERIC(12, 2),
        juros_pago_colaborador NUMERIC(12, 2) DEFAULT 0.00,
        eh_ajuste BOOLEAN DEFAULT FALSE,
        referencia_comissao_id VARCHAR(36) REFERENCES contas_a_pagar(id),
        status VARCHAR(20) DEFAULT 'A_PAGAR',
        data_pagamento DATETIME,
        created_at DATETIME,
        updated_at DATETIME
    );
    """))

    conn.commit()
    print("\n✅ Migration completed.")
