# PASSO 3: VALIDAÇÃO COMPLETA NO NAVEGADOR

## 📋 Etapas (30-45 minutos)

### ✅ Etapa 1: Load & Console (5 min)
- [ ] Acesse `chrome://extensions`
- [ ] Confirme Zapway está **ATIVA** (toggle azul)
- [ ] F12 → Abra Console
- [ ] Recarregue a página (Cmd+R)
- [ ] Verifique se há **zero erros vermelhos**
- [ ] Digite `console.log('✅ Teste')` e execute

### ✅ Etapa 2: Sidebar & Funcionalidades (10 min)
- [ ] Clique no ícone ZapWay
- [ ] Sidebar abre sem animações travadas
- [ ] Navegue entre abas: Contatos, Cadências, Configurações
- [ ] Teste busca e filtros
- [ ] Feche e abra sidebar 3x - verifique memória estável

### ✅ Etapa 3: Network & Performance (10 min)
- [ ] Abra DevTools → aba Network
- [ ] Recarregue a página
- [ ] Verifique se requests são **HTTPS apenas**
- [ ] Confirme headers de segurança presentes
- [ ] Monitore tempo de load < 2s

### ✅ Etapa 4: Memory Leak Test (10 min)
- [ ] DevTools → Memory → Take snapshot (heap)
- [ ] Abra/feche sidebar 10x
- [ ] Take snapshot 2º
- [ ] Compare snapshots - **sem vazamentos significativos**
- [ ] Verifique se `heapUsed` não cresce consistentemente

### ✅ Etapa 5: Full Test (10 min)
- [ ] Teste fluxo completo: Lead → Cadência → Classificação
- [ ] Verifique se IA responses carregam
- [ ] Teste inbound message flow
- [ ] Confirme API calls usam headers auth corretos

## 📊 Resultados Esperados
- Console: **0 erros**
- Network: **100% HTTPS**, headers de segurança presentes
- Memory: **Estável**, sem vazamentos após 10 ciclos
- Sidebar: **Funciona suavemente** em todas as abas