# Estabilização do CRM

## O que esta entrega corrige

- Remove login de depuração sem credenciais e rotas públicas de migração.
- Exige SECRET_KEY; falha de inicialização ou blueprint não produz uma aplicação parcialmente carregada.
- Restringe consulta de leads, tarefas e execução manual de cadências à empresa autenticada.
- Protege todos os jobs do blueprint de cron com Authorization: Bearer CRON_SECRET.
- Usa cache privado nas APIs, corrige sessão expirada e evita stack traces nos erros gerais.
- Serializa a conversão de um lead no PostgreSQL e impede duplicação com índice único em client.lead_id.
- Corrige all_time e períodos do dashboard; usa agregação SQL compatível com SQLite e PostgreSQL.
- Reconhece tarefas concluídas no dashboard e inclui tarefas para mais tarde no dia.
- Pagina o funil em 50 cartões por coluna, preserva totais globais e pesquisa no servidor.
- Calcula atividade e progresso dos cartões em lote, sem carregar todas as interações/tarefas.
- Calcula a saúde de clientes em lote para exibição, sem gravações na listagem.
- Pagina conversas e mensagens do WhatsApp, busca novas mensagens por cursor e permite carregar o histórico anterior.
- Pausa polling de abas ocultas e preserva o histórico renderizado quando não há mudança.
- Escapa mensagens e nomes na renderização modificada da inbox.
- Implementa a alteração de etapa pela barra lateral do WhatsApp com validação de empresa/funil.
- Persiste entregas de webhooks com tentativas limitadas, lease recuperável e identificador estável nos reenvios.
- Identifica WhatsApp e prospecção/IA como beta; mantém o controle de acesso por empresa existente.

## Antes de publicar

1. Use homologação com banco descartável ou cópia autorizada. Não execute pytest apontando para produção: as fixtures criam e removem tabelas.
2. Confira duplicações com `SELECT lead_id, count(*) FROM client WHERE lead_id IS NOT NULL GROUP BY lead_id HAVING count(*) > 1;`. Reconcilie casos existentes preservando os dados; a migração aborta se encontrar duplicações.
3. Faça backup e aplique `migrations/20260915_stabilization.sql` antes do deploy. Ela é aditiva; não execute os scripts de manutenção genéricos como substituto desta migração.
4. Configure SECRET_KEY e DATABASE_URL. A ausência de SECRET_KEY agora impede a inicialização. Se alterar uma chave de sessão já utilizada, os usuários precisarão entrar novamente.
5. Configure CRON_SECRET no servidor e em cada agendador que chama `/api/cron/*`. Essas rotas agora exigem `Authorization: Bearer <CRON_SECRET>`; chamadas antigas sem token receberão 401.
6. Agende `/api/cron/webhook-deliveries` com esse cabeçalho. Cada chamada processa uma entrega; ajuste a frequência/capacidade ao volume e ao timeout do provedor. Para maior volume, use um worker persistente que chame `process_deliveries` em lotes limitados dentro do app context.
7. Valide os testes e a navegação em homologação antes do merge/deploy. Não foi executada migração no banco real nesta entrega.

## Testes

Na raiz, após instalar requirements.txt e pytest:

```sh
PYTHONPATH=.:northway_crm python -m pytest northway_crm/tests -q
node northway_crm/tests/test_inbox_frontend.cjs
```

O primeiro comando usa SQLite em memória por padrão. Para PostgreSQL, defina TEST_DATABASE_URL para um banco **exclusivo e descartável de teste**, incluindo sslmode apropriado. O workflow CRM regression tests executa ambos os bancos. As dependências de produção não foram atualizadas; a validação local usa Python 3.12.

Os testes cobrem autenticação, isolamento, conversão repetida, períodos dos gráficos, listagem sem gravações, paginação do funil/conversas/histórico, alteração de etapa e retentativas de webhook. O teste JavaScript usa os handlers reais com DOM/HTTP simulados; não substitui homologação visual em navegador.

## Operação da fila

`webhook_delivery.status` pode ser pending, processing, delivered, failed ou cancelled. O worker tenta até cinco vezes, com espera crescente. Uma entrega processing fica disponível novamente após cinco minutos se o processo morrer. Webhook desativado cancela a entrega pendente.

Para reprocessar uma entrega failed após corrigir a causa, um operador autorizado pode definir status=pending, attempts=0 e available_at=CURRENT_TIMESTAMP, mantendo o id. O destino deve deduplicar X-NorthWay-Request-Id: a entrega é pelo menos uma vez, não uma promessa de execução exatamente uma vez no sistema externo.

A fila é persistida quando dispatch_webhooks é chamado. Chamadores legados que já confirmaram a alteração comercial antes dessa chamada ainda têm uma pequena janela entre as duas transações; transformar todos esses produtores em uma outbox atômica é uma etapa posterior.

## Medição e saída do beta

Ative PERFORMANCE_LOGGING=1 para registrar endpoint, status, duração e tamanho da resposta, sem corpo, parâmetros ou credenciais. Compare p50/p95 com volumes representativos e confira planos de consulta no PostgreSQL real. Não há medição de ganho percentual em produção nesta entrega.

Antes de retirar o beta de WhatsApp/prospecção: testar envio, reconexão, falha do provedor, interrupção de cadência, eventos repetidos/fora de ordem e aprovação humana. As integrações reais não foram acionadas pelos testes locais.

Ainda pendem do plano amplo: provisionamento de Drive totalmente assíncrono, validação do ciclo de estorno/NFS-e, revisão completa dos módulos secundários, retentativas de todos os provedores, testes concorrentes reais de conversão, auditoria de todas as rotas e homologação com carga de produção. O CRM não está certificado como 100% funcional por este PR.

## Reversão

Reverter o código restaura a versão anterior, inclusive suas falhas de segurança. Prefira corrigir ou desabilitar especificamente o recurso com problema. A tabela da fila e os índices são aditivos e podem ser mantidos para preservar entregas pendentes. Não remova dados da fila ao reverter; interrompa seu agendador se necessário e reconcilie entregas antes da retomada.
