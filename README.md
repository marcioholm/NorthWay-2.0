# Northway CRM

CRM moderno baseado em Flask para gerenciamento de leads, prospects e clientes com integração Supabase, Google OAuth e múltiplos módulos de funcionalidade.

## Stack

- **Backend:** Python Flask 3.0.3
- **Database:** Supabase (PostgreSQL)
- **Auth:** Google OAuth 2.0
- **Frontend:** HTML / CSS / JavaScript (templates Flask)
- **ORM:** SQLAlchemy
- **Deploy:** Vercel

## Setup

### Requisitos

- Python 3.8+
- PostgreSQL (via Supabase)
- Google OAuth credentials

### Instalação

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais
```

### Rodar localmente

```bash
python northway_crm/app.py
```

Acesse em `http://localhost:5000`

### Migrations

```bash
flask db upgrade
flask db downgrade
```

### Seed Data

```bash
python northway_crm/seed_northway_data.py
```

### Compilar CSS (Tailwind UI Redesign)

```bash
cd northway_crm
npm run build:css
# ou diretamente via npx:
npx tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.min.css --minify
```

## Estrutura

- `/northway_crm/` — App principal
  - `app.py` — Aplicação Flask
  - `models.py` — Modelos SQLAlchemy
  - `auth.py` — Autenticação
  - `routes/` — Blueprints de rotas
  - `services/` — Serviços (Supabase, etc)
  - `templates/` — Templates Jinja2
  - `static/` — CSS, JS, imagens

## Variáveis de Ambiente & Banco de Dados

Veja `.env.example` para a lista completa.

### Banco de Dados em Produção (Supabase Pooler)
Em ambientes serverless (Vercel), a variável `DATABASE_URL` deve obrigatoriamente apontar para o **Supabase Connection Pooler em modo transaction (porta 6543)**, e **não** para a conexão direta (porta 5432).
- Exemplo: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`
- O `psycopg2` não utiliza prepared statements no servidor por padrão, garantindo total compatibilidade com o transaction pooling do PgBouncer.
- O pool da aplicação está configurado com `pool_size=1, max_overflow=2, pool_recycle=300, pool_pre_ping=True, pool_timeout=10` e keepalives ativos.

## Deploy

Push para `main` faz deploy automático na Vercel.
