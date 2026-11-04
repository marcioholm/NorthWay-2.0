# NorthWay Lead Copilot (Extensão Chrome)

Extensão oficial para enriquecimento acelerado de prospecção fria B2B. Extrai sócios, anúncios Meta e Instagram com 1 clique diretamente para o Google Sheets ou para o NorthWay CRM.

---

## 🚀 Como Instalar no Google Chrome (1 Minuto)

1. Abra o **Google Chrome** e acesse: `chrome://extensions/`
2. No canto superior direito, ative a chave **"Modo do desenvolvedor"** (Developer mode).
3. No canto superior esquerdo, clique no botão **"Carregar sem compactação"** (Load unpacked).
4. Selecione a pasta deste projeto:
   `/Users/Marci.Holm/Downloads/NorthWay-2.0-main/tools/northway-copilot-extension`
5. Pronto! O ícone do **NorthWay Lead Copilot** aparecerá na barra de extensões do seu navegador. Fixe-o (pin) para facilitar o acesso.

---

## 🎯 Como Usar no Dia a Dia da Prospecção

### 1. Enriquecimento de Sócios & Decisores (CNPJ.biz ou Casa dos Dados)
* Ao abrir qualquer página de empresa no [CNPJ.biz](https://cnpj.biz) ou [Casa dos Dados](https://casadosdados.com.br):
* Clique no ícone da extensão no Chrome.
* Os campos de **Nome da Empresa, CNPJ, Sócios/Decisores (QSA), Telefone, E-mail e Cidade/UF** serão preenchidos automaticamente.

### 2. Checagem de Anúncios (Biblioteca de Anúncios Meta)
* Ao abrir a [Biblioteca de Anúncios do Facebook](https://www.facebook.com/ads/library):
* A extensão detecta quantos anúncios a empresa tem rodando e marca automaticamente como **🟢 Sim (X anúncios)** ou **⚪ Não**.
* Isso informa na hora se a empresa já investe em marketing ou se é lead frio para oferta de tráfego/gestão.

### 3. Checagem de Instagram
* Na página do Instagram da empresa (`instagram.com/nomedaempresa`):
* A extensão puxa o `@handle`, quantidade de seguidores e descrição da bio.

---

## 📤 Destino dos Dados (3 Opções)

1. **📋 Copiar p/ Sheets (Mais rápido):**
   * Clique em "Copiar p/ Sheets" e dê `Ctrl + V` em qualquer linha da sua planilha do Google Sheets. Cada dado cai exatamente na sua respectiva coluna.
2. **📥 Baixar CSV:**
   * Conforme você prospecta, clique em "Salvar Lead na Planilha Local". Ao final do dia, clique em "Baixar CSV" para exportar a lista completa formatada com cabeçalhos e caracteres em UTF-8.
3. **🚀 Enviar ao CRM:**
   * Cadastra o lead instantaneamente no NorthWay CRM local (`http://localhost:5000/api/leads`).

