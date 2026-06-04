# Northway CRM

## O que é
CRM moderno baseado em Flask para gerenciamento de leads, prospects e clientes. Integra com Supabase para banco de dados, Google OAuth para autenticação e contém múltiplos módulos de funcionalidade (prospecção, contratos, etc).

## Stack
- **Backend:** Python Flask 3.0.3
- **Database:** Supabase (PostgreSQL)
- **Auth:** Google OAuth 2.0
- **Frontend:** HTML / CSS / JavaScript (templates Flask)
- **Deploy:** Vercel
- **ORM:** SQLAlchemy com Flask-SQLAlchemy

## Estrutura
- `/northway_crm/app.py` — App principal Flask
- `/northway_crm/models.py` — Modelos SQLAlchemy
- `/northway_crm/auth.py` — Lógica de autenticação
- `/northway_crm/routes/` — Blueprints de rotas
- `/northway_crm/services/` — Serviços (Supabase, etc)
- `/northway_crm/templates/` — Templates HTML Jinja2
- `/northway_crm/static/` — CSS, JS, imagens
- `/northway_crm/maintenance/` — Scripts de manutenção
- `/northway_crm/scripts/` — Utilitários e seed data

## Comandos
```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar localmente
python northway_crm/app.py

# Migrations
flask db upgrade

# Seed data
python northway_crm/seed_northway_data.py
```

## Git Workflow
- Branch `dev` para desenvolvimento
- Branch `main` para produção
- NUNCA push direto na main (Vercel)

## Variáveis de Ambiente
Ver `.env.example` para todas as variáveis necessárias.
Principais:
- `SUPABASE_URL` — URL do projeto Supabase
- `SUPABASE_KEY` — Chave pública Supabase
- `GOOGLE_OAUTH_ID` / `GOOGLE_OAUTH_SECRET` — Google OAuth
- `DATABASE_URL` — Conexão PostgreSQL
- `SECRET_KEY` — Chave secreta Flask
- `CRM_INTERNAL_API_KEY` — Chave para autenticação entre n8n e CRM (via header `Authorization: Bearer <token>`)

## Endpoints internos para integração n8n

Todos os endpoints abaixo exigem header: `Authorization: Bearer <valor da env CRM_INTERNAL_API_KEY>`

### POST /api/internal/prospecting/context
Retorna contexto completo para geração de mensagem de um lead.
Inclui: current_step, attempts_so_far, intent_status, campaign, settings, ai_credentials, whatsapp_integration.

### POST /api/internal/prospecting/pending-batch
Retorna leads prontos para próximo step da cadência (next_action_at <= now, status não bloqueado).
Chamado pelo scheduler n8n a cada 15 minutos.
Body opcional: `{ "tenant_id": 1, "campaign_id": 5, "limit": 50 }`
Retorna: lista de leads com tenant_id, campaign_id, next_step, preferred_channel, manual_approval_required

### POST /api/internal/prospecting/schedule-next
Avança ou pausa a cadência de um lead após classificação de IA.
Chamado pelo n8n após processar a resposta de um lead.
Body: `{ "tenant_id", "lead_id", "campaign_id", "classification", "summary", ... }`
Classifications de pausa (notifica comercial): interessado, pediu_preco, pediu_material, reuniao
Classifications de encerramento: sem_interesse, ja_tem_agencia, descartado
Classifications de reagendamento: agora_nao, duvida, respondeu

### POST /api/internal/prospecting/inbound-context
Resolve tenant, lead e histórico a partir do telefone do remetente.
Grava mensagem inbound e retorna contexto para classificação.

### POST /api/internal/prospecting/inbound-result
Salva resultado da classificação IA (intent, memória, ai_log).
