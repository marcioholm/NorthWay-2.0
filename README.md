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

## Variáveis de Ambiente

Veja `.env.example` para a lista completa.

## Deploy

Push para `main` faz deploy automático na Vercel.
