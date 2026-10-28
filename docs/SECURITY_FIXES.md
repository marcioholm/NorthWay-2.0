# Relatório de Correções de Segurança (Security Hardening)

Este documento detalha o conjunto de correções e endurecimento (*hardening*) de segurança implementados no NorthWay CRM ao longo das 5 fases da branch `fix/security-critical`.

---

## Sumário Executivo

O projeto passou por uma auditoria completa de segurança e refatoração arquitetural para eliminar riscos críticos de controle de acesso, vazamento de segredos, spoofing de webhooks, vulnerabilidades de IDOR (*Insecure Direct Object Reference*) em ambiente multi-tenant, ataques de CSRF (*Cross-Site Request Forgery*) e abuso de requisições por força bruta (*rate limiting*).

Todas as 5 fases foram validadas com testes automatizados integrados (84 testes passando na suíte do CRM) e testes manuais/automatizados no navegador Chrome com JavaScript ativo.

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
- **Fallbacks Silenciosos de Segurança:** Em caso de ausência de dependências de segurança (`Flask-WTF` ou `Flask-Limiter`), classes dummy permitiam que o sistema subisse completamente desprotegido.

### Medidas Implementadas

#### 1. Configuração do `Flask-WTF` (`CSRFProtect`) e Fail-Closed
- Em `northway_crm/extensions.py`, foram removidos os fallbacks silenciosos (`DummyCSRF` e classe `Limiter` vazia). Se qualquer biblioteca estiver ausente, o sistema falha imediatamente na inicialização com `ImportError` explícito.
- Tratamento centralizado de `CSRFError` em `app.py`:
  - Retorna **HTTP 400 JSON** (`{'error': 'CSRF validation failed', 'reason': ...}`) para requisições AJAX, `fetch` ou endpoints sob prefixos de API.
  - Renderiza tela de erro estilizada com código 400 para requisições HTML convencionais de navegador.

#### 2. Isenções M2M Controladas
- Apenas endpoints legítimos de máquina para máquina (*machine-to-machine*) e webhooks de parceiros que não utilizam cookies de sessão de navegador foram isentos via `csrf.exempt(...)`:
  - `evolution_webhook_bp` (`/api/evolution/webhook`)
  - `internal_api_bp` (`/internal/*`)
  - `jobs_bp` (`/api/cron/*`)
  - `api_ext` (`/api/ext/*`)
  - `api_v1_bp` (`/api/v1/*`)
  - `integrations.asaas_webhook`
  - `billing.asaas_webhook`
  - `forms.submit_form` (submissão de formulário público de lead sem login)
  - `diagnostic_raiox.submit` (diagnóstico público sem login)

#### 3. Interceptador de Fetch, Axios e jQuery com Validação de Mesma Origem (Same-Origin)
- Em `base.html` e `base_minimal.html`, o interceptador global de `window.fetch` valida a origem da requisição antes de anexar cabeçalhos:
  ```javascript
  function isSameOrigin(input) {
      try {
          var urlString = input instanceof Request ? input.url : input;
          var parsed = new URL(urlString, window.location.href);
          return parsed.origin === window.location.origin;
      } catch (e) {
          return false;
      }
  }
  ```
- **Proteção contra Vazamento de Token:** Se uma requisição for despachada para domínios externos (ex.: CDNs, APIs de parceiros, webhooks externos), a verificação de `origin` falha e **nenhum cabeçalho CSRF é enviado**.
- Suporta requisições onde `input` é uma string ou uma instância de `Request` (`input instanceof Request`), adicionando `X-CSRFToken` e `X-CSRF-Token` em ambos os casos.
- Configurado interceptor no Axios (`axios.interceptors.request.use`) e no jQuery (`$.ajaxSetup`) aplicando a mesma validação de `isSameOrigin`.
- Sobrescrita de `HTMLFormElement.prototype.submit` e ouvinte global de evento `submit` na fase de captura (`capture phase`) para injetar `<input type="hidden" name="csrf_token">` automaticamente em formulários dinâmicos e modais.

#### 4. Cobertura de Formulários em Todos os Templates
Foram adicionados tokens `{{ csrf_token() }}` em todos os formulários POST da aplicação, incluindo templates standalone e layouts secundários:
- `checkout_standalone.html`: Meta tag CSRF no `<head>` e input oculto no formulário de checkout.
- `payment_pending.html`: Meta tag CSRF no `<head>` e input oculto no formulário de regularização.
- `setup_company.html`: Input oculto no formulário de configuração inicial da organização.
- `auth/forgot_password.html`: Input oculto no formulário de solicitação de redefinição de senha.
- `auth/reset_password.html`: Input oculto no formulário de confirmação de nova senha.
- `auth/activate_trial.html`: Input oculto no formulário de desbloqueio de período de teste.
- `forms/my_diagnostic.html`: Inputs ocultos nos formulários de concessão e revogação de acesso a diagnósticos.
- `master_global_templates.html`: Migrado de layout inexistente para `base.html` e adicionados tokens nos formulários de criação e exclusão.

#### 5. Gestão de Dependências e Build da Vercel
As dependências `Flask-WTF==1.2.1` e `redis>=5.0.0` foram sincronizadas nos 3 arquivos de requisitos do repositório:
1. `requirements.txt` (raiz): Utilizado no ambiente de desenvolvimento local, testes com pytest e deploys padrão baseados em container.
2. `api/requirements.txt`: **Arquivo utilizado pela Vercel em produção.** Conforme configurado no `vercel.json` (`"src": "api/index.py", "use": "@vercel/python"`), o runtime serverless do `@vercel/python` compila o pacote lambda a partir do diretório `api/`, instalando exclusivamente as dependências presentes em `api/requirements.txt`.
3. `northway_crm/requirements.txt`: Manifesto interno do pacote do CRM.

---

## Configuração do Rate Limiting com Redis no Upstash

Por padrão em desenvolvimento, o rate limiting opera em memória (`memory://`). No entanto, em ambientes serverless como a Vercel, cada invocação pode rodar em uma instância/container independente, tornando a memória não compartilhada.

Para garantir rate limiting consistente em produção, deve-se utilizar um backend Redis externo (como o [Upstash Redis](https://upstash.com/)).

### Passo a Passo para Criação no Upstash e Configuração na Vercel:

1. **Criar a Base no Upstash:**
   - Acesse o console do [Upstash](https://console.upstash.com/).
   - Clique em **Create Database**.
   - Tipo: **Redis**.
   - Nome: `northway-crm-ratelimit`.
   - Região: Escolha a região mais próxima da sua distribuição na Vercel (ex.: `sa-east-1` São Paulo ou `us-east-1`).
   - Clique em **Create**.

2. **Obter a URI de Conexão:**
   - Na página do banco criado no Upstash, vá até a aba **Details**.
   - Na seção **Connect your database**, selecione **redis-py** ou copie a **REST URL** / **Default Connection String**.
   - A string de conexão tem o seguinte formato (com criptografia TLS ativa):
     ```text
     rediss://default:<UPSTASH_PASSWORD>@<UPSTASH_ENDPOINT>:<PORT>
     ```
     *(Importante: utilize o prefixo `rediss://` com duplo 's' para indicar conexão segura TLS).*

3. **Configurar a Variável de Ambiente na Vercel:**
   - Acesse o painel do seu projeto na Vercel: **Settings** -> **Environment Variables**.
   - Adicione uma nova variável:
     - **Key:** `RATELIMIT_STORAGE_URI`
     - **Value:** `rediss://default:sua_senha@seu_endpoint.upstash.io:6379`
     - **Environments:** Production, Preview, Development.
   - Salve e faça um novo deploy.

4. **Verificação de Inicialização:**
   - Na inicialização em produção, se `VERCEL` estiver ativo e `RATELIMIT_STORAGE_URI` estiver configurada, o aviso `⚠️ RATELIMIT WARNING` não será exibido e o `Flask-Limiter` armazenará contadores de forma distribuída entre todas as lambdas.

---

## Resultados dos Testes no Navegador (Chrome com JavaScript Ativo)

A aplicação foi executada localmente com `WTF_CSRF_ENABLED=1` e validada ponta a ponta no navegador Chrome via automação de navegador com JavaScript habilitado:

| # | Operação | Rota / Método | Status HTTP | Erro 400 no Console / Rede? | Status Final |
|---|---|:---:|:---:|:---:|:---:|
| 1 | **Login** | `POST /login` | **302 Found** -> `/master/dashboard` | **Nenhum** | **APROVADO** |
| 2 | **Criar lead pelo modal** | `POST /leads` | **302 Found** -> `/leads` | **Nenhum** | **APROVADO** |
| 3 | **Mover card no pipeline** | `POST /api/leads/2/update_stage` | **200 OK** | **Nenhum** | **APROVADO** |
| 4 | **Marcar tarefa como concluída** | `POST /tasks/1/toggle` | **302 Found** -> `/tasks` | **Nenhum** | **APROVADO** |
| 5 | **Salvar configurações da empresa** | `POST /settings/company` | **302 Found** -> `/settings/company` | **Nenhum** | **APROVADO** |
| 6 | **Abrir página de checkout** | `GET /checkout` | **200 OK** (renderizou formulário e meta CSRF) | **Nenhum** | **APROVADO** |

---

## Verificação e Execução da Suíte de Testes Automatizada

Para executar toda a suíte de segurança localmente:

```bash
PYTHONPATH=.:northway_crm python3 -m pytest northway_crm/tests -v
```

Resultado atual:
- **84 testes executados com sucesso** (0 falhas, 2 skipped).
