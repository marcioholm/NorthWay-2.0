// NorthWay Lead Copilot - Modern Controller (Raycast / Linear UI)

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const elSitePill = document.getElementById('currentSiteLabel');
  const elSiteNameTxt = document.getElementById('siteNameTxt');
  const elCompanyName = document.getElementById('companyName');
  const elCnpj = document.getElementById('cnpj');
  const elCityState = document.getElementById('cityState');
  const elSocios = document.getElementById('socios');
  const elPhone = document.getElementById('phone');
  const elEmail = document.getElementById('email');
  const elAdCount = document.getElementById('adCount');
  const elInstagram = document.getElementById('instagram');
  const elInstagramFollowers = document.getElementById('instagramFollowers');
  const elNotes = document.getElementById('notes');
  const elLeadCountBadge = document.getElementById('leadCountBadge');
  
  // Toast
  const elToastBar = document.getElementById('toastBar');
  const elToastIcon = document.getElementById('toastIcon');
  const elToastMessage = document.getElementById('toastMessage');

  // Badges
  const badgeCnpj = document.getElementById('badgeCnpj');
  const badgeSocios = document.getElementById('badgeSocios');
  const badgeContact = document.getElementById('badgeContact');
  const badgeAds = document.getElementById('badgeAds');
  const badgeInsta = document.getElementById('badgeInsta');

  // Buttons
  const btnResetDraft = document.getElementById('btnResetDraft');
  const btnAdsYes = document.getElementById('btnAdsYes');
  const btnAdsNo = document.getElementById('btnAdsNo');
  const btnSaveLead = document.getElementById('btnSaveLead');
  const btnCopyTsv = document.getElementById('btnCopyTsv');
  const btnExportCsv = document.getElementById('btnExportCsv');
  const btnSendToCrm = document.getElementById('btnSendToCrm');
  const btnClearQueue = document.getElementById('btnClearQueue');

  let hasAdsValue = null;
  let activeTabUrl = '';
  let toastTimer = null;

  // 1. Carrega o rascunho persistido e lista acumulada
  const { currentDraft = {}, leads = [] } = await chrome.storage.local.get(['currentDraft', 'leads']);
  restoreDraftToForm(currentDraft);
  updateSavedCount(leads.length);

  // 2. Seletor de Anúncios Meta Ads
  btnAdsYes.addEventListener('click', () => {
    hasAdsValue = true;
    btnAdsYes.className = 'toggle-chip active-green';
    btnAdsNo.className = 'toggle-chip';
    if (!elAdCount.value || elAdCount.value === '0') elAdCount.value = '1';
    saveCurrentDraft();
    updateBadges();
  });

  btnAdsNo.addEventListener('click', () => {
    hasAdsValue = false;
    btnAdsNo.className = 'toggle-chip active-red';
    btnAdsYes.className = 'toggle-chip';
    elAdCount.value = '0';
    saveCurrentDraft();
    updateBadges();
  });

  // Salvar rascunho instantaneamente a cada digitação
  [elCompanyName, elCnpj, elPhone, elSocios, elEmail, elCityState, elAdCount, elInstagram, elInstagramFollowers, elNotes].forEach(input => {
    input.addEventListener('input', () => {
      saveCurrentDraft();
      updateBadges();
    });
  });

  // 3. Comunicação com a aba ativa e extração automática
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) {
      activeTabUrl = tab.url || '';
      detectSiteTag(activeTabUrl);

      chrome.tabs.sendMessage(tab.id, { action: 'EXTRACT_PAGE_DATA' }, (response) => {
        if (chrome.runtime.lastError) {
          // Injeção de fallback caso a aba estivesse aberta antes da extensão
          chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          }, () => {
            if (!chrome.runtime.lastError) {
              chrome.tabs.sendMessage(tab.id, { action: 'EXTRACT_PAGE_DATA' }, mergeExtractedData);
            }
          });
        } else if (response && response.success) {
          mergeExtractedData(response);
        }
      });
    }
  } catch (err) {
    console.warn('Erro ao consultar aba ativa:', err);
  }

  function detectSiteTag(url) {
    if (url.includes('cnpj.biz')) {
      elSiteNameTxt.textContent = 'CNPJ.biz';
      elSitePill.style.background = 'rgba(2, 132, 199, 0.2)';
      elSitePill.style.borderColor = 'rgba(2, 132, 199, 0.4)';
    } else if (url.includes('casadosdados.com.br')) {
      elSiteNameTxt.textContent = 'Casa dos Dados';
      elSitePill.style.background = 'rgba(79, 70, 229, 0.2)';
      elSitePill.style.borderColor = 'rgba(79, 70, 229, 0.4)';
    } else if (url.includes('facebook.com/ads/library')) {
      elSiteNameTxt.textContent = 'Meta Ads';
      elSitePill.style.background = 'rgba(16, 185, 129, 0.2)';
      elSitePill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    } else if (url.includes('instagram.com')) {
      elSiteNameTxt.textContent = 'Instagram';
      elSitePill.style.background = 'rgba(225, 48, 108, 0.2)';
      elSitePill.style.borderColor = 'rgba(225, 48, 108, 0.4)';
    } else {
      elSiteNameTxt.textContent = 'Navegação';
    }
  }

  // 4. Mesclagem Inteligente de Dados da Página Atual
  function mergeExtractedData(response) {
    if (!response || !response.data) return;
    const d = response.data;
    let addedCount = 0;

    // Razão Social / Fantasia
    const isBadName = !elCompanyName.value || 
                      elCompanyName.value.toLowerCase().includes('biblioteca') || 
                      elCompanyName.value.toLowerCase().includes('selecionar') ||
                      elCompanyName.value.toLowerCase().includes('buscar');

    if (d.companyName && isBadName) {
      elCompanyName.value = d.companyName;
      addedCount++;
    }

    // CNPJ
    if (d.cnpj && !elCnpj.value) {
      elCnpj.value = d.cnpj;
      addedCount++;
    }

    // Sócios
    if (d.socios && d.socios.length > 0 && (!elSocios.value || elSocios.value.length < 5)) {
      elSocios.value = d.socios.join('; ');
      addedCount++;
    }

    // Telefone
    if (d.phone && (!elPhone.value || elPhone.value.length < 8)) {
      elPhone.value = d.phone;
      addedCount++;
    }

    // Email
    if (d.email && !elEmail.value) {
      elEmail.value = d.email;
      addedCount++;
    }

    // Localidade
    if ((d.city || d.state) && !elCityState.value) {
      const loc = [d.city, d.state].filter(Boolean).join(' - ');
      if (loc) {
        elCityState.value = loc;
        addedCount++;
      }
    }

    // Anúncios Meta
    if (d.hasAds === true) {
      btnAdsYes.click();
      if (d.adCount !== null) elAdCount.value = d.adCount;
      addedCount++;
    } else if (d.hasAds === false && hasAdsValue === null) {
      btnAdsNo.click();
      addedCount++;
    }

    // Instagram
    if (d.instagram && !elInstagram.value) {
      elInstagram.value = d.instagram;
      addedCount++;
    }
    if (d.instagramFollowers && !elInstagramFollowers.value) {
      elInstagramFollowers.value = d.instagramFollowers;
      addedCount++;
    }

    if (d.notes && !elNotes.value) {
      elNotes.value = d.notes;
    }

    saveCurrentDraft();
    updateBadges();

    if (addedCount > 0) {
      showToast('✨', `${addedCount} campo(s) detectados e mesclados!`, 'success');
    }
  }

  // 5. Concluir Empresa & Salvar Linha
  btnSaveLead.addEventListener('click', async () => {
    const lead = getFormData();
    if (!lead.companyName && !lead.cnpj && !lead.phone) {
      showToast('⚠️', 'Preencha ao menos Nome, CNPJ ou Telefone.', 'error');
      return;
    }

    const storage = await chrome.storage.local.get('leads');
    const leadsList = storage.leads || [];

    // Checa duplicatas pelo CNPJ para atualizar em vez de duplicar
    const existingIdx = lead.cnpj ? leadsList.findIndex(l => l.cnpj === lead.cnpj) : -1;
    if (existingIdx >= 0) {
      leadsList[existingIdx] = lead;
      showToast('🔄', 'Empresa atualizada com sucesso!', 'success');
    } else {
      leadsList.push(lead);
      showToast('✅', 'Lead consolidado com sucesso!', 'success');
    }

    await chrome.storage.local.set({ leads: leadsList, currentDraft: {} });
    updateSavedCount(leadsList.length);
    resetFormFields();
  });

  // 6. Botão "Nova Empresa" (Limpar rascunho com feedback rápido)
  btnResetDraft.addEventListener('click', async () => {
    if (confirm('Deseja iniciar outra empresa? O rascunho em aberto será limpo.')) {
      await chrome.storage.local.set({ currentDraft: {} });
      resetFormFields();
      showToast('🧹', 'Rascunho zerado para nova empresa.', 'success');
    }
  });

  // 7. Copiar Linha TSV para Google Sheets (Ctrl+V perfeito)
  btnCopyTsv.addEventListener('click', () => {
    const lead = getFormData();
    const row = [
      new Date().toLocaleDateString('pt-BR'),
      lead.companyName,
      lead.cnpj,
      lead.socios,
      lead.phone,
      lead.email,
      lead.cityState,
      lead.hasAds === true ? 'SIM' : (lead.hasAds === false ? 'NÃO' : 'NÃO VERIFICADO'),
      lead.adCount || '0',
      lead.instagram,
      lead.instagramFollowers,
      lead.notes,
      activeTabUrl
    ].map(val => (val || '').toString().replace(/\t/g, ' ')).join('\t');

    navigator.clipboard.writeText(row).then(() => {
      showToast('📋', 'Copiado! Basta dar Ctrl+V no Sheets.', 'success');
    }).catch(() => {
      showToast('❌', 'Erro ao copiar.', 'error');
    });
  });

  // 8. Baixar CSV formatado UTF-8
  btnExportCsv.addEventListener('click', async () => {
    const { leads = [] } = await chrome.storage.local.get('leads');
    if (leads.length === 0) {
      showToast('⚠️', 'Nenhum lead salvo para baixar.', 'error');
      return;
    }

    const headers = [
      'Data de Captura',
      'Nome / Razão Social',
      'CNPJ',
      'Sócios / Tomadores de Decisão',
      'Telefone / WhatsApp',
      'E-mail',
      'Cidade - UF',
      'Anúncios Meta Ativos',
      'Qtd Anúncios',
      'Instagram',
      'Seguidores Instagram',
      'Observações SDR',
      'URL Origem'
    ];

    const rows = leads.map(l => [
      l.savedAt || new Date().toISOString(),
      `"${(l.companyName || '').replace(/"/g, '""')}"`,
      `"${(l.cnpj || '').replace(/"/g, '""')}"`,
      `"${(l.socios || '').replace(/"/g, '""')}"`,
      `"${(l.phone || '').replace(/"/g, '""')}"`,
      `"${(l.email || '').replace(/"/g, '""')}"`,
      `"${(l.cityState || '').replace(/"/g, '""')}"`,
      l.hasAds === true ? 'SIM' : (l.hasAds === false ? 'NÃO' : ''),
      l.adCount || '0',
      `"${(l.instagram || '').replace(/"/g, '""')}"`,
      `"${(l.instagramFollowers || '').replace(/"/g, '""')}"`,
      `"${(l.notes || '').replace(/"/g, '""')}"`,
      `"${(l.sourceUrl || '').replace(/"/g, '""')}"`
    ].join(';'));

    const csvContent = '\uFEFF' + headers.join(';') + '\n' + rows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `leads_northway_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('📥', `${leads.length} leads exportados!`, 'success');
  });

  // 9. Enviar ao CRM Local
  btnSendToCrm.addEventListener('click', async () => {
    const lead = getFormData();
    if (!lead.companyName && !lead.phone) {
      showToast('⚠️', 'Informe ao menos Razão Social ou Telefone.', 'error');
      return;
    }

    try {
      showToast('⏳', 'Enviando ao CRM...', 'success');
      const payload = {
        name: lead.companyName,
        company: lead.companyName,
        phone: lead.phone,
        email: lead.email,
        notes: `CNPJ: ${lead.cnpj} | Sócios: ${lead.socios} | Meta Ads: ${lead.hasAds ? 'Sim ('+lead.adCount+')' : 'Não'} | Insta: ${lead.instagram} (${lead.instagramFollowers}) | Obs: ${lead.notes}`
      };

      const res = await fetch('http://localhost:5000/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast('🚀', 'Lead adicionado ao NorthWay CRM!', 'success');
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast('❌', errData.error || 'Erro na resposta do CRM.', 'error');
      }
    } catch (err) {
      showToast('⚠️', 'CRM indisponível em localhost:5000.', 'error');
    }
  });

  // 10. Limpar lista
  btnClearQueue.addEventListener('click', async () => {
    if (confirm('Deseja limpar todos os leads salvos nesta sessão?')) {
      await chrome.storage.local.set({ leads: [] });
      updateSavedCount(0);
      showToast('🗑️', 'Lista de leads zerada.', 'success');
    }
  });

  // Helpers de Estado
  function getFormData() {
    return {
      companyName: elCompanyName.value.trim(),
      cnpj: elCnpj.value.trim(),
      phone: elPhone.value.trim(),
      socios: elSocios.value.trim(),
      email: elEmail.value.trim(),
      cityState: elCityState.value.trim(),
      hasAds: hasAdsValue,
      adCount: elAdCount.value.trim(),
      instagram: elInstagram.value.trim(),
      instagramFollowers: elInstagramFollowers.value.trim(),
      notes: elNotes.value.trim(),
      sourceUrl: activeTabUrl,
      savedAt: new Date().toISOString()
    };
  }

  function restoreDraftToForm(d) {
    if (!d) return;
    if (d.companyName) elCompanyName.value = d.companyName;
    if (d.cnpj) elCnpj.value = d.cnpj;
    if (d.phone) elPhone.value = d.phone;
    if (d.socios) elSocios.value = d.socios;
    if (d.email) elEmail.value = d.email;
    if (d.cityState) elCityState.value = d.cityState;
    if (d.hasAds === true) {
      hasAdsValue = true;
      btnAdsYes.className = 'toggle-chip active-green';
      if (d.adCount) elAdCount.value = d.adCount;
    } else if (d.hasAds === false) {
      hasAdsValue = false;
      btnAdsNo.className = 'toggle-chip active-red';
    }
    if (d.instagram) elInstagram.value = d.instagram;
    if (d.instagramFollowers) elInstagramFollowers.value = d.instagramFollowers;
    if (d.notes) elNotes.value = d.notes;

    updateBadges();
  }

  function saveCurrentDraft() {
    const draft = getFormData();
    chrome.storage.local.set({ currentDraft: draft });
  }

  function resetFormFields() {
    elCompanyName.value = '';
    elCnpj.value = '';
    elPhone.value = '';
    elSocios.value = '';
    elEmail.value = '';
    elCityState.value = '';
    elAdCount.value = '';
    elInstagram.value = '';
    elInstagramFollowers.value = '';
    elNotes.value = '';
    hasAdsValue = null;
    btnAdsYes.className = 'toggle-chip';
    btnAdsNo.className = 'toggle-chip';
    updateBadges();
  }

  function updateBadges() {
    badgeCnpj.className = elCnpj.value ? 'badge-chip active' : 'badge-chip';
    badgeSocios.className = elSocios.value ? 'badge-chip active' : 'badge-chip';
    badgeContact.className = (elPhone.value || elEmail.value) ? 'badge-chip active' : 'badge-chip';
    badgeAds.className = hasAdsValue !== null ? 'badge-chip active' : 'badge-chip';
    badgeInsta.className = elInstagram.value ? 'badge-chip active' : 'badge-chip';
  }

  function updateSavedCount(count) {
    elLeadCountBadge.textContent = count;
  }

  function showToast(icon, message, type = 'success') {
    if (toastTimer) clearTimeout(toastTimer);
    elToastIcon.textContent = icon;
    elToastMessage.textContent = message;
    elToastBar.className = type;
    toastTimer = setTimeout(() => {
      elToastBar.className = '';
      elToastBar.style.display = 'none';
    }, 3500);
  }
});
