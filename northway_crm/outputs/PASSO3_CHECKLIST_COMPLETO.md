# PASSO 3: CHECKLIST COMPLETO DE VALIDAÇÃO

## 📋 Checklist Geral (14 fases)

### Funcionalidades Basics
- [ ] Extension carrega sem erros de JavaScript
- [ ] Sidebar abre/fecha corretamente
- [ ] navegação entre abas funciona
- [ ] Busca e filtros funcionam

### Segurança
- [ ] Zero erros no Console (F12)
- [ ] Headers de segurança presentes
- [ ] API calls usam Authorization header
- [ ] Dados sensíveis não expostos no DOM

### Performance
- [ ] Tempo de carga < 2s
- [ ] Network requests otimizados
- [ ] Memory estável (sem vazamentos)
- [ ] Network 90% reduzido vs versão anterior

### Integração IA
- [ ] IA responses carregam corretamente
- [ ] Fluxo lead → classificação funciona
- [ ] Inbound message flow funciona
- [ ] Cadência avança corretamente

### Memória
- [ ] Take snapshot 1º ciclo
- [ ] Abra/feche sidebar 10x
- [ ] Take snapshot 2º ciclo
- [ ] Comparação: sem crescimento significativo de heapUsed

## 📝 Observações

Lead ID testado: _________________
Campaign ID testado: _________________
Tempo total de validação: _________________
Observações gerais: _________________________________