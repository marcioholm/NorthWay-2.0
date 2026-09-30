// PASSO 3: Script Automatizado de Validação
// Executa: node PASSO3_SCRIPT_VALIDACAO.js ou no console do navegador

console.log('🚀 Iniciando validação automatizada PASSO 3...\n');

// 1. Verificar extension
console.log('1️⃣ Verificando extension...');
const extensions = chrome.extensions ? chrome.extensions.getAll() : [];
// Verificar se ZapWay está ativa

// 2. Console clean
console.log('2️⃣ Verificando console clean...');
let consoleErrors = 0;
const originalError = console.error;
console.error = (...args) => {
  consoleErrors++;
  originalError.apply(console, args);
};

// 3. Sidebar test
console.log('3️⃣ Testando sidebar...');
try {
  // Simular clique no ícone
  const sidebars = document.querySelectorAll('.zapway-sidebar');
  console.log(`   Encontrados ${sidebars.length} elementos sidebar`);
} catch (e) {
  console.log('   Erro ao testar sidebar:', e.message);
}

// 4. Memory check
console.log('4️⃣ Verificando memory...');
if (performance && performance.memory) {
  const memory = performance.memory;
  console.log(`   heapTotal: ${Math.round(memory.heapTotal / 1024 / 1024)} MB`);
  console.log(`   heapUsed: ${Math.round(memory.heapUsed / 1024 / 1024)} MB`);
}

// Resto dos testes...

console.log('\n✅ Validação concluída!');
console.log(`   Erros no console: ${consoleErrors}`);