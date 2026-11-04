// NorthWay Lead Copilot - Content Script
// Extrator cirúrgico para Casa dos Dados, CNPJ.biz, Meta Ads e Instagram

(function () {
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'EXTRACT_PAGE_DATA') {
      const data = extractDataFromCurrentPage();
      sendResponse({ success: true, data: data });
    }
    return true;
  });

  function extractDataFromCurrentPage() {
    const url = window.location.href;
    const hostname = window.location.hostname;

    let payload = {
      sourceUrl: url,
      sourceSite: hostname,
      companyName: '',
      cnpj: '',
      socios: [],
      phone: '',
      email: '',
      city: '',
      state: '',
      hasAds: null,
      adCount: null,
      instagram: '',
      instagramFollowers: '',
      notes: ''
    };

    try {
      if (hostname.includes('casadosdados.com.br')) {
        extractCasaDosDados(payload);
      } else if (hostname.includes('cnpj.biz')) {
        extractCnpjBiz(payload);
      } else if (hostname.includes('facebook.com') && url.includes('/ads/library')) {
        extractMetaAds(payload);
      } else if (hostname.includes('instagram.com')) {
        extractInstagram(payload);
      }
    } catch (err) {
      console.warn('[NorthWay Copilot] Erro na extração:', err);
    }

    return payload;
  }

  // 1. Extrator Cirúrgico Casa dos Dados
  function extractCasaDosDados(out) {
    const docText = document.body.innerText;

    // A) CNPJ: Busca o padrão com máscara ou os 14 dígitos após "CNPJ:"
    const cnpjMatch = docText.match(/\b\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}\b/);
    if (cnpjMatch) {
      out.cnpj = cnpjMatch[0];
    } else {
      const rawCnpj = docText.match(/CNPJ:\s*(\d{14})/i);
      if (rawCnpj) {
        const c = rawCnpj[1];
        out.cnpj = `${c.slice(0,2)}.${c.slice(2,5)}.${c.slice(5,8)}/${c.slice(8,12)}-${c.slice(12,14)}`;
      }
    }

    // B) Razão Social & Nome Fantasia: Procura diretamente pelo rótulo "Razão Social:"
    // Na Casa dos Dados, o texto fica em blocos como:
    // "Razão Social:\nPRANA SOLAR SERVICOS ELETRICOS LTDA"
    const razaoMatch = docText.match(/Razão\s*Social:?\s*[\r\n]+\s*([^\r\n]+)/i) || 
                       docText.match(/Razão\s*Social:?\s*([^\r\n]+)/i);
    
    const fantasiaMatch = docText.match(/Nome\s*Fantasia:?\s*[\r\n]+\s*([^\r\n]+)/i) ||
                          docText.match(/Nome\s*Fantasia:?\s*([^\r\n]+)/i);

    let razao = razaoMatch ? razaoMatch[1].trim() : '';
    let fantasia = fantasiaMatch ? fantasiaMatch[1].trim() : '';

    // Filtra strings que sejam lixo ou seletores
    if (razao.toLowerCase().includes('selecionar') || razao.toLowerCase().includes('buscar')) {
      razao = '';
    }
    if (fantasia.toLowerCase().includes('selecionar') || fantasia.toLowerCase().includes('buscar') || fantasia.toLowerCase() === 'sem motivo') {
      fantasia = '';
    }

    if (fantasia && fantasia.length > 2 && fantasia !== 'NÃO INFORMADO') {
      out.companyName = fantasia + (razao && razao !== fantasia ? ` (${razao})` : '');
    } else if (razao) {
      out.companyName = razao;
    } else {
      // Fallback: tenta pegar pelo título da página
      const h1 = document.querySelector('h1');
      if (h1 && !h1.innerText.includes('Selecionar')) {
        out.companyName = h1.innerText.replace(/CNPJ:?.*/i, '').trim();
      }
    }

    // C) Sócios & QSA: Busca seções de Quadro Societário
    const sociosList = [];
    document.querySelectorAll('a, p, span, div').forEach(el => {
      const href = el.getAttribute('href') || '';
      if (href.includes('/socio/')) {
        const t = el.innerText.trim();
        if (t && t.length > 2 && t.length < 70 && !sociosList.includes(t)) {
          sociosList.push(t);
        }
      }
    });

    // Se não encontrou por links, busca por texto com Qualificação
    if (sociosList.length === 0) {
      const qsaMatches = docText.match(/Nome\/Nome Empresarial:?\s*([^\r\n]+)/gi);
      if (qsaMatches) {
        qsaMatches.forEach(m => {
          const name = m.replace(/Nome\/Nome Empresarial:?\s*/i, '').trim();
          if (name && !sociosList.includes(name)) sociosList.push(name);
        });
      }
    }
    out.socios = sociosList.slice(0, 5);

    // D) Telefone: Busca por bloco "Telefone:" ou padrão (XX) XXXXX-XXXX
    const telBlock = docText.match(/Telefone[s]?:?\s*[\r\n]*\s*(\(?\d{2}\)?\s*(?:9\d{4}|\d{4})[-.\s]?\d{4})/i) ||
                     docText.match(/Contato\s*Telefônico:?\s*[\r\n]*\s*(\(?\d{2}\)?\s*(?:9\d{4}|\d{4})[-.\s]?\d{4})/i);
    
    if (telBlock) {
      out.phone = telBlock[1].trim();
    } else {
      // Procura qualquer padrão de telefone válido no texto (evitando dígitos colados de CNPJ)
      const allPhones = docText.match(/\(\d{2}\)\s*(?:9\d{4}|\d{4})[-.\s]?\d{4}/g);
      if (allPhones && allPhones.length > 0) {
        out.phone = allPhones[0].trim();
      }
    }

    // E) E-mail
    const emailBlock = docText.match(/E-mail:?\s*[\r\n]*\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
    if (emailBlock) {
      out.email = emailBlock[1].toLowerCase().trim();
    } else {
      const generalEmail = docText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
      if (generalEmail && !generalEmail[0].includes('casadosdados') && !generalEmail[0].includes('wix')) {
        out.email = generalEmail[0].toLowerCase().trim();
      }
    }

    // F) Município e UF
    const munMatch = docText.match(/Município:?\s*[\r\n]*\s*([^\r\n]+)/i);
    const ufMatch = docText.match(/Estado:?\s*[\r\n]*\s*([A-Z]{2})/i) || docText.match(/UF:?\s*[\r\n]*\s*([A-Z]{2})/i);
    
    if (munMatch) out.city = munMatch[1].trim();
    if (ufMatch) out.state = ufMatch[1].trim();
  }

  // 2. Extrator Cirúrgico CNPJ.BIZ
  function extractCnpjBiz(out) {
    const docText = document.body.innerText;

    // CNPJ
    const cnpjMatch = docText.match(/\b\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}\b/);
    if (cnpjMatch) out.cnpj = cnpjMatch[0];

    // Razão Social & Nome Fantasia no CNPJ.biz
    const razaoMatch = docText.match(/Razão\s*Social:?\s*([^\r\n]+)/i);
    const fantasiaMatch = docText.match(/Nome\s*Fantasia:?\s*([^\r\n]+)/i);

    let razao = razaoMatch ? razaoMatch[1].trim() : '';
    let fantasia = fantasiaMatch ? fantasiaMatch[1].trim() : '';

    if (fantasia && fantasia.length > 2 && fantasia.toUpperCase() !== 'NÃO INFORMADO') {
      out.companyName = fantasia + (razao && razao !== fantasia ? ` (${razao})` : '');
    } else if (razao) {
      out.companyName = razao;
    } else {
      const h1 = document.querySelector('h1');
      if (h1) {
        let title = h1.innerText.replace(/CNPJ\s*-\s*/i, '').trim();
        if (out.cnpj) {
          title = title.replace(new RegExp('\\s*-\\s*' + out.cnpj.replace(/[./-]/g, '\\$&'), 'i'), '');
        }
        out.companyName = title.trim();
      }
    }

    // Sócios
    const sociosList = [];
    document.querySelectorAll('p, li, div, tr').forEach(el => {
      const t = (el.innerText || '').trim();
      if ((t.includes('Sócio') || t.includes('Administrador') || t.includes('Diretor')) && t.length > 5 && t.length < 100) {
        if (!t.toLowerCase().startsWith('quadro de sócios')) {
          sociosList.push(t.replace(/\s+/g, ' '));
        }
      }
    });
    out.socios = Array.from(new Set(sociosList)).slice(0, 5);

    // Telefone
    const telMatch = docText.match(/Telefone[s]?:?\s*(\(?\d{2}\)?\s*(?:9\d{4}|\d{4})[-.\s]?\d{4})/i) ||
                    docText.match(/\(\d{2}\)\s*(?:9\d{4}|\d{4})[-.\s]?\d{4}/);
    if (telMatch) out.phone = telMatch[1] || telMatch[0];

    // Email
    const emailMatch = docText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    if (emailMatch && !emailMatch[0].includes('cnpj.biz')) {
      out.email = emailMatch[0].toLowerCase();
    }

    // Localidade
    const munMatch = docText.match(/Município:\s*([^\n\r-]+)[-\/]?\s*([A-Z]{2})/i);
    if (munMatch) {
      out.city = munMatch[1].trim();
      out.state = munMatch[2].trim().toUpperCase();
    }
  }

  // 3. Extrator Meta Ads Library
  function extractMetaAds(out) {
    const text = document.body.innerText;
    out.companyName = '';

    const pageHeader = document.querySelector('h1, h2, div[role="heading"]');
    if (pageHeader && !pageHeader.innerText.includes('Biblioteca de Anúncios')) {
      out.companyName = pageHeader.innerText.trim();
    }

    const countMatch = text.match(/([0-9.,]+)\s+resultado(s)?/i) || text.match(/~([0-9.,]+)\s+resultado/i);

    if (text.includes('Nenhum anúncio correspondente') || text.includes('0 resultado')) {
      out.hasAds = false;
      out.adCount = 0;
    } else if (countMatch) {
      out.hasAds = true;
      out.adCount = parseInt(countMatch[1].replace(/\D/g, ''), 10);
    } else {
      const adCards = document.querySelectorAll('div[data-testid], div[role="region"]');
      out.hasAds = adCards.length > 0;
      out.adCount = adCards.length;
    }
  }

  // 4. Extrator Instagram
  function extractInstagram(out) {
    const handleMatch = window.location.pathname.replace(/\//g, '');
    if (handleMatch && !['explore', 'direct', 'reels', 'stories'].includes(handleMatch)) {
      out.instagram = '@' + handleMatch;
      out.companyName = '';
    }

    const metaDesc = document.querySelector('meta[name="description"]')?.content || '';
    const followersMatch = metaDesc.match(/([0-9.,KMBkmb]+)\s+(?:Followers|seguidores)/i);
    if (followersMatch) {
      out.instagramFollowers = followersMatch[1];
    }
  }
})();
