# PASSO 3: Reference de Comandos

## Comandos Rápidos (Terminal)

```bash
# Abrir extension page
open -a Google\ Chrome chrome://extensions

# Abrir DevTools
open -a Google\ Chrome --args --new-window about:blank

# Limpar console do Chrome
# Cmd + L (foco) + Delete

# Ver memory
# DevTools → Memory → Take snapshot

# Reiniciar extension
# Clique em "Disable" então "Enable" em chrome://extensions
```

## Atalhos de Teclado

| Atalho | Ação |
|--------|------|
| Cmd + Shift + P | Abrir Paleta de Comandos |
| Cmd + Option + I | Abrir DevTools |
| Cmd + Option + J | Abrir Console |
| Cmd + [ / ] | Navegar abas sidebar |
| Esc | Fechar sidebar |

## Endpoints API (Internal - n8n Integration)

Todos os endpoints abaixo exigem header: `Authorization: Bearer <valor da env CRM_INTERNAL_API_KEY>`

### POST /api/internal/prospecting/context
- Retorna contexto completo para geração de mensagem de um lead
- Inclui: current_step, attempts_so_far, intent_status, campaign, settings, ai_credentials, whatsapp_integration

### POST /api/internal/prospecting/pending-batch
- Retorna leads prontos para próximo step da cadência
- Chamado pelo scheduler n8n a cada 15 minutos
- Body opcional: `{ "tenant_id": 1, "campaign_id": 5, "limit": 50 }`

### POST /api/internal/prospecting/schedule-next
- Avança ou pausa a cadência de um lead após classificação de IA
- Body: `{ "tenant_id", "lead_id", "campaign_id", "classification", "summary", ... }`

### POST /api/internal/prospecting/inbound-context
- Resolve tenant, lead e histórico a partir do telefone do remetente
- Grava mensagem inbound e retorna contexto para classificação

### POST /api/internal/prospecting/inbound-result
- Salva resultado da classificação IA (intent, memória, ai_log)
```