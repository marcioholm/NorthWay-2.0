# Relatório de Correções de Segurança (Security Hardening)

Este documento detalha o conjunto de correções e endurecimento (*hardening*) de segurança implementados no NorthWay CRM ao longo das 5 fases da branch `fix/security-critical`.

---

## Sumário Executivo

O projeto passou por uma auditoria completa de segurança e refatoração arquitetural para eliminar riscos críticos de controle de acesso, vazamento de segredos, spoofing de webhooks, vulnerabilidades de IDOR (*Insecure Direct Object Reference*) em ambiente multi-tenant, ataques de CSRF (*Cross-Site Request Forgery*) e abuso de requisições por força bruta (*rate limiting*).

Todas as 5 fases foram validadas com testes automatizados integrados (83 testes passando na suíte do CRM).

---

## Fase 1: Remoção de Rotas de Depuração, Backdoors e Proteção Administrativa

### Vulnerabilidades Corrigidas
- **Backdoors de Autenticação:** Existência de endpoints de desenvolvimento que permitiam login sem credenciais (`/login_debug`, `/login-debug`, `/bypass-login`).
- **Endpoints Públicos de Migração/Manutenção:** Rotas HTTP que executavam migrações no banco de dados sem proteção adequada (`/admin/run-initial-migrations`, `/emergency-migration`, `/debug_schema`, `/master/migrate-integrations`, `/sys_admin/init-db`).

### Medidas Implementadas
1. **Remoção Definitiva de Atalhos de Login:** Todos os manipuladores e rotas de bypass foram totalmente eliminados do código-fonte.
2. **Desacoplamento de Migrações da Camada Web:** Rotas de inicialização e migração emergencial foram removidas. Operações de banco foram transferidas exclusivamente para migrações do Alembic/Flask-Migrate (`flask db upgrade`) e comandos CLI de manutenção invocados via terminal seguro.
3. **Restrição Estrita de Acesso SuperAdmin:** Rotas sob `/sys_admin` e `/master` tiveram suas regras reforçadas com decorators obrigatórios verificando `current_user.is_authenticated` e `current_user.is_super_admin == True`.
4. **Isolamento de Ambiente:** Operações de diagnóstico foram restritas a testes e desativadas em ambientes de produção.

---

## Fase 2: Gestão Estrita de Segredos e Verificação Criptográfica (Fail-Closed)

### Vulnerabilidades Corrigidas
- **Segredos Hardcoded / Padrões Inseguros:** Variáveis de ambiente críticas possuíam valores default ou fallback em texto plano (ex: `'secret'`, `'default_key'`).
- **Ataques de Temporização (Timing Attacks):** Validação de assinaturas de webhook e tokens de serviço utilizando comparação simples de strings (`==`), vulnerável a análise estatística de tempo de resposta.
- **Degradação Silenciosa em Inicialização:** Aplicação subia em estado vulnerável caso variáveis essenciais estivessem ausentes.

### Medidas Implementadas
1. **Arquitetura Fail-Closed:**
   - A inicialização da fábrica (`create_app`) agora valida a presença obrigatória de `SECRET_KEY` e, em ambiente de produção (Vercel), de `DATABASE_URL`.
   - Se qualquer chave obrigatória estiver ausente ou em branco, a aplicação interrompe a execução com `RuntimeError`, impedindo que o CRM funcione sem proteção de sessão.
2. **Comparações em Tempo Constante:**
   - Todas as validações de tokens de webhook e chaves secretas foram migradas para `hmac.compare_digest`.
   - Aplicado na validação do webhook do Asaas (`ASAAZ_WEBHOOK_TOKEN`), webhook de Billing (`BILLING_WEBHOOK_SECRET`) e rotas de Cron (`CRON_SECRET`).
3. **Sanitização de Logs e Conexões:**
   - Mascaramento de senhas nas strings de conexão de banco (`db_url_with_password`) para impedir vazamento de credenciais nos logs do servidor.

---

## Fase 3: Autenticação Segura dos Webhooks da Evolution API (WhatsApp)

### Vulnerabilidades Corrigidas
- **Ausência de Autenticação no Webhook do WhatsApp:** O endpoint `/api/evolution/webhook` aceitava mensagens recebidas sem validar a autenticidade da origem, permitindo injeção forjada de conversas ou comandos.
- **Construção Insegura de URLs de Webhook:** URLs podiam ser geradas sem forçar HTTPS ou apontando para hosts incorretos.

### Medidas Implementadas
1. **Autenticação Criptográfica de Webhooks:**
   - Introdução da variável `EVOLUTION_WEBHOOK_TOKEN`.
   - O endpoint do webhook agora exige o token via cabeçalho `X-Webhook-Token`, `Authorization: Bearer <token>` ou parâmetro de consulta `token`.
   - Validação realizada via `hmac.compare_digest`. Requisições inválidas ou sem token recebem rejeição imediata com HTTP 401.
2. **URL Builder Seguro (`build_evolution_webhook_url`):**
   - Força protocolo HTTPS em ambientes de produção e constrói a URL oficial do webhook com parâmetros de segurança.
3. **CLI de Ressincronização de Webhooks:**
   - Adicionado comando `flask evolution resync-webhooks` para configurar e atualizar de forma idempotente a URL do webhook autenticado em todas as instâncias conectadas na Evolution API.

---

## Fase 4: Isolamento Multi-Tenant Estrito e Eliminação de IDOR

### Vulnerabilidades Corrigidas
- **IDOR (Insecure Direct Object Reference):** Endpoints permitiam consultar, alterar ou excluir registros (leads, tarefas, clientes, etapas, funis, checklists) apenas informando o ID na URL ou corpo do request, sem verificar se o registro pertencia à empresa (`company_id`) do usuário autenticado.
- **Vazamento Cruzado de Etapas (`import_lead`):** Ao importar um lead passando um `stage_id` pertencente à outra empresa, o sistema aceitava ou caía silenciosamente no funil padrão, violando o isolamento entre inquilinos (*tenants*).

### Medidas Implementadas
1. **Escopamento Rigoroso de Queries:**
   - Todas as consultas que recebem IDs de `request.json`, `request.form`, `request.args` ou parâmetros de rota foram reescritas com filtro explícito `company_id == current_user.company_id`.
2. **Correção do `import_lead` em `prospecting.py`:**
   - O `stage_id` fornecido agora é consultado via join: `PipelineStage.pipeline` com `Pipeline.company_id == current_user.company_id`.
   - Caso a etapa não pertença a um funil da empresa autenticada, a requisição retorna **HTTP 404** imediatamente, sem mascaramento ou fallback silencioso.
3. **Escopamento de Usuários Atribuídos:**
   - Endpoints de transferência de tarefas, checklists e reatribuição de leads validam que `assigned_to_id`, `responsible_id` e `account_manager_id` pertencem à mesma empresa do usuário logado (`User.company_id == current_user.company_id`). Tentativas de vincular colaboradores de outros tenants resultam em 404.
4. **Isolamento no `FormService`:**
   - Processamento de submissões de formulários públicos restringe estritamente `target_client` e `target_lead` ao `tenant_id` registrado na instância do formulário (`FormInstance`).
5. **Cobertura Automatizada de Testes de Tenant:**
   - Criado `test_multi_tenant_idor.py` cobrindo 75 testes automatizados de tentativa de acesso cruzado entre empresas para Leads, Clientes, Tarefas, Funis, Contratos e Checklists.

---

## Fase 5: Proteção CSRF Global e Rate Limiting

### Vulnerabilidades Corrigidas
- **Ausência de Proteção CSRF:** Formulários POST e chamadas AJAX não exigiam tokens anti-falsificação de solicitação entre sites.
- **Ataques de Força Bruta (Brute-Force / Credential Stuffing):** Endpoints sensíveis de autenticação não possuíam limitação de taxa de requisição por IP.

### Medidas Implementadas
1. **Configuração do `Flask-WTF` (`CSRFProtect`):**
   - Inicialização do `csrf.init_app(app)` no ciclo de vida da aplicação.
   - Tratamento centralizado de `CSRFError`:
     - Retorna **HTTP 400 JSON** (`{'error': 'CSRF validation failed', 'reason': ...}`) para requisições AJAX, `fetch` ou endpoints sob prefixos de API.
     - Renderiza tela de erro estilizada com código 400 para requisições HTML convencionais de navegador.
2. **Isenções M2M Controladas:**
   - Apenas endpoints legítimos de máquina para máquina (*machine-to-machine*) e webhooks de parceiros que não utilizam cookies de sessão foram isentos via `csrf.exempt(...)`:
     - `evolution_webhook_bp` (`/api/evolution/webhook`)
     - `internal_api_bp` (`/internal/*`)
     - `jobs_bp` (`/api/cron/*`)
     - `api_ext` (`/api/ext/*`)
     - `api_v1_bp` (`/api/v1/*`)
     - `integrations.asaas_webhook`
     - `billing.asaas_webhook`
     - `forms.submit_form` (submissão de formulário público sem login)
     - `diagnostic_raiox.submit` (diagnóstico público)
3. **Camada Frontend Unificada de Injeção de Token CSRF:**
   - Em `base.html` e `base_minimal.html`, foi adicionada a meta-tag `<meta name="csrf-token" content="{{ csrf_token() }}">`.
   - Implementado script interceptor JavaScript global e resiliente que:
     - Intercepta `window.fetch` para injetar os cabeçalhos `X-CSRFToken` e `X-CSRF-Token` em todas as chamadas `POST`, `PUT`, `DELETE` e `PATCH`.
     - Configura `jQuery.ajaxSetup` caso jQuery esteja presente.
     - Configura `axios.defaults.headers.common` caso Axios esteja presente.
     - Adiciona ouvinte global de `submit` na fase de captura (`capture phase`) em todo o documento, injetando `<input type="hidden" name="csrf_token" value="...">` automaticamente em qualquer formulário POST (inclusive modais e formulários criados dinamicamente).
     - Sobrescreve `HTMLFormElement.prototype.submit` para garantir a injeção do token mesmo quando formulários gerados via script chamam `.submit()` programaticamente.
   - Inclusão explícita do campo `csrf_token` em todos os formulários Jinja2 renderizados pelo servidor (Login, Registro, Nova Tarefa, Novo Lead, Importação de Leads, Funil, Clientes, Configurações da Empresa e Geração de Contratos).
4. **Rate Limiting com `Flask-Limiter`:**
   - Endpoints sensíveis protegidos contra ataques automatizados de força bruta:
     - `POST /login`: 10 requisições por minuto por IP.
     - `POST /register`: 5 requisições por minuto por IP.
     - `POST /forgot_password`: 5 requisições por minuto por IP.
     - `POST /reset_password/<token>`: 5 requisições por minuto por IP.
     - `POST /api/ext/login`: 10 requisições por minuto por IP.
5. **Suíte de Testes da Fase 5 (`test_csrf_and_ratelimit.py`):**
   - Foram testados e aprovados os fluxos principais com CSRF ativo:
     - Login: rejeição sem token (400), sucesso com token (302).
     - Criar lead: rejeição sem token (400), sucesso com token (302).
     - Mover card no pipeline: rejeição sem header (400), sucesso com `X-CSRFToken` (200).
     - Salvar tarefa: rejeição sem token (400), sucesso com token (302).
     - Salvar configurações da empresa: rejeição sem token (400), sucesso com token (302).
     - Gerar contrato: rejeição sem token (400), sucesso com token (302).
     - Rate limit no login e na API da extensão: disparo de HTTP 429 após exceder a taxa limite.

---

## Verificação e Execução dos Testes

Para executar toda a suíte de segurança localmente:

```bash
PYTHONPATH=.:northway_crm python3 -m pytest northway_crm/tests -v
```

Resultado atual:
- **83 testes executados com sucesso** (0 falhas).
