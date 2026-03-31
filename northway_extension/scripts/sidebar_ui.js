/**
 * ZapWay Sidebar UI & State
 */

const getEl = (id) => NWState.shadowRoot ? NWState.shadowRoot.getElementById(id) : null;

/**
 * Enhanced Toast Replacement for alert()
 * @param {string} message 
 * @param {string} type 'success' | 'error' | 'warning' | 'info'
 * @param {number} duration 
 */
function toast(message, type = 'info', duration = 4000) {
    nwLog(`Toast [${type}]: ${message}`);
    const container = getEl('nw-toast-container') || document.getElementById('nw-toast-container');
    let dynamicContainer = container;

    if (!dynamicContainer) {
        dynamicContainer = document.createElement('div');
        dynamicContainer.id = 'nw-toast-container';
        dynamicContainer.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: ${NWState.isSidebarCollapsed ? 20 : SIDEBAR_WIDTH + 20}px;
            z-index: 999999;
            display: flex;
            flex-direction: column;
            gap: 8px;
            pointer-events: none;
            transition: right 0.3s ease;
        `;
        document.body.appendChild(dynamicContainer);
    }

    const colors = {
        success: { bg: 'rgba(0,230,153,0.12)', border: 'rgba(0,230,153,0.25)', text: '#00e699', icon: '✓' },
        error: { bg: 'rgba(255,31,75,0.12)', border: 'rgba(255,31,75,0.25)', text: '#ff1f4b', icon: '✕' },
        warning: { bg: 'rgba(255,193,7,0.12)', border: 'rgba(255,193,7,0.25)', text: '#ffc107', icon: '⚠' },
        info: { bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.25)', text: '#818cf8', icon: 'ℹ' },
    };

    const c = colors[type] || colors.info;
    const el = document.createElement('div');
    el.style.cssText = `
        background: ${c.bg};
        border: 1px solid ${c.border};
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 12px;
        font-weight: 600;
        color: ${c.text};
        font-family: Inter, sans-serif;
        max-width: 280px;
        pointer-events: auto;
        cursor: pointer;
        display: flex;
        align-items: flex-start;
        gap: 8px;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        animation: nw-slide-in 0.3s cubic-bezier(0.4,0,0.2,1) forwards;
    `;
    el.innerHTML = `<span style="flex-shrink:0;font-weight:800">${c.icon}</span><span>${message}</span>`;
    el.onclick = () => el.remove();
    dynamicContainer.appendChild(el);
    
    setTimeout(() => {
        el.style.animation = 'nw-slide-out 0.3s ease forwards';
        setTimeout(() => el.remove(), 300);
    }, duration);
}

function showState(state) {
    const states = ['idle', 'loading', 'new', 'contact', 'group', 'broadcast', 'automation'];
    states.forEach(s => {
        const el = getEl(`nw-state-${s}`);
        if (el) el.classList.add('hidden');
    });

    const active = getEl(`nw-state-${state}`);
    if (active) active.classList.remove('hidden');

    if (state === 'automation') AutomationEngine.render();
    if (state === 'idle') {
        sendMsg({ action: "GET_TODAY_STATS" }).then(stats => {
            if (stats) {
                const elSent = getEl('nw-idle-stat-sent');
                const elCrm = getEl('nw-idle-stat-crm');
                if (elSent) elSent.textContent = stats.sent || 0;
                if (elCrm) elCrm.textContent = stats.crm || 0;
            }
        });
    }

    // Toggle Templates
    const tplContainer = getEl('nw-templates-container');
    if (tplContainer) {
        if (['new', 'contact'].includes(state)) tplContainer.classList.remove('hidden');
        else tplContainer.classList.add('hidden');
    }
}

async function updateSidebar(name, phone, searchName = null, avatarUrl = null) {
    nwLog(`[ZapWay][Sidebar] render lead: ${name} (${phone})`);
    showState('loading');

    // Exibe nome e avatar imediatamente (antes da resposta do CRM)
    const initials = name ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'NW';
    const nameEl = getEl('nw-contact-name');
    const initialsEl = getEl('nw-contact-initials');
    const img = getEl('nw-contact-img');

    if (nameEl) nameEl.textContent = name || 'Desconhecido';
    if (initialsEl) initialsEl.textContent = initials;

    if (img && initialsEl) {
        if (avatarUrl) {
            img.src = avatarUrl;
            img.classList.remove('hidden');
            initialsEl.classList.add('hidden');
        } else {
            img.classList.add('hidden');
            initialsEl.classList.remove('hidden');
        }
    }

    try {
        nwLog('[ZapWay][CRM] sync start →', { phone, name: searchName });
        const response = await sendMsg({ action: "GET_CONTACT", phone, name: searchName });
        nwLog('[ZapWay][CRM] sync result →', response);

        if (!response || response.error) {
            // API inacessível: exibe estado "Novo Lead" com dados já detectados
            // O currentPhone é MANTIDO para evitar loop infinito de detecção
            nwLog('[ZapWay][CRM] API indisponível — exibindo estado parcial');
            const connEl = getEl('nw-connection-status');
            if (connEl) connEl.className = 'status-dot disconnected';
            NWState.currentLeadId = null;
            showState('new');
            const collapsedEl = getEl('nw-new-collapsed');
            const formEl = getEl('nw-new-form');
            if (collapsedEl) collapsedEl.classList.remove('hidden');
            if (formEl) formEl.classList.add('hidden');
            const newNameEl = getEl('nw-new-name');
            const newPhoneEl = getEl('nw-new-phone');
            if (newNameEl) newNameEl.value = name || '';
            if (newPhoneEl) newPhoneEl.value = phone ? String(phone).replace(/\D/g, '') : '';
            loadPipelines(null, 'nw-new-stage');
            return;
        }

        const connEl = getEl('nw-connection-status');
        if (connEl) connEl.className = 'status-dot connected';

        if (response.found === false) {
            nwLog('[ZapWay][Sidebar] Contato não encontrado no CRM — estado "Novo Lead"');
            NWState.currentLeadId = null;
            showState('new');
            const c = getEl('nw-new-collapsed');
            const f = getEl('nw-new-form');
            const n = getEl('nw-new-name');
            const p = getEl('nw-new-phone');
            if (c) c.classList.remove('hidden');
            if (f) f.classList.add('hidden');
            if (n) n.value = name || '';
            if (p) p.value = phone ? String(phone).split('@')[0].replace(/\D/g, '') : '';
            loadPipelines(null, 'nw-new-stage');
        } else {
            nwLog('[ZapWay][Sidebar] Contato encontrado — renderizando');
            renderContact(response.data, avatarUrl);
        }
    } catch (e) {
        nwLog('[ZapWay][Sidebar] Erro ao atualizar sidebar', e);
        // Em caso de exceção, mantemos o phone atual e mostramos estado offline
        const connEl = getEl('nw-connection-status');
        if (connEl) connEl.className = 'status-dot disconnected';
        showState('new');
        const collapsedEl = getEl('nw-new-collapsed');
        const formEl = getEl('nw-new-form');
        if (collapsedEl) collapsedEl.classList.remove('hidden');
        if (formEl) formEl.classList.add('hidden');
    }
}

function renderContact(data, freshAvatarUrl = null) {
    NWState.currentLeadId = data.id;
    showState('contact');
    getEl('nw-contact-name').textContent = data.name;
    getEl('nw-contact-phone').textContent = data.phone;
    getEl('nw-contact-status').textContent = data.status || 'Contato';
    getEl('nw-input-notes').value = data.notes || '';

    const tagsContainer = getEl('nw-contact-tags');
    if (tagsContainer) {
        tagsContainer.innerHTML = '';
        (data.tags || []).forEach(tag => {
            const t = document.createElement('span');
            t.textContent = tag;
            t.className = 'nw-tag-chip'; // Assume predefined styles or inline
            tagsContainer.appendChild(t);
        });
    }

    const img = getEl('nw-contact-img');
    const initialsEl = getEl('nw-contact-initials');
    const finalAvatar = freshAvatarUrl || data.avatar_url;

    if (finalAvatar) {
        img.src = finalAvatar;
        img.classList.remove('hidden');
        initialsEl.classList.add('hidden');
    } else {
        const initials = data.name ? data.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'NW';
        initialsEl.textContent = initials;
        img.classList.add('hidden');
        initialsEl.classList.remove('hidden');
    }

    loadPipelines(data.pipeline_stage_id);
}

async function loadPipelines(currentStageId, targetId = 'nw-input-stage') {
    const response = await sendMsg({ action: "GET_PIPELINES" });
    const select = getEl(targetId);
    if (!select || !response) return;
    
    select.innerHTML = '';
    response.forEach(pipeline => {
        const grp = document.createElement('optgroup');
        grp.label = pipeline.name;
        pipeline.stages.forEach(stage => {
            const opt = document.createElement('option');
            opt.value = stage.id;
            opt.textContent = stage.name;
            if (stage.id == currentStageId) opt.selected = true;
            grp.appendChild(opt);
        });
        select.appendChild(grp);
    });
}

async function loadTemplates() {
    try {
        const response = await sendMsg({ action: "GET_TEMPLATES" });
        const section = NWState.shadowRoot.querySelector('.nw-templates-section');
        if (!section || !response) return;

        response.forEach(tpl => {
            const card = document.createElement('div');
            card.className = 'nw-template-card';
            card.style.position = 'relative';
            card.innerHTML = `
                <div class="nw-template-icon" style="background: rgba(99,102,241,0.1); color: #818cf8;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                </div>
                <div class="nw-template-info">
                    <strong>${tpl.title}</strong>
                    <p>${tpl.content.substring(0, 60)}${tpl.content.length > 60 ? '...' : ''}</p>
                </div>
                <button class="nw-btn-direct-send-tpl" title="Disparo Direto" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); width: 28px; height: 28px; border-radius: 6px; border: none; background: rgba(0, 230, 153, 0.1); color: var(--nw-accent); cursor: pointer; display: flex; align-items: center; justify-content: center; z-index: 10;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            `;
            
            // Fill textarea
            card.onclick = (e) => {
                if (e.target.closest('.nw-btn-direct-send-tpl')) return;
                const ta = getEl('nw-broadcast-template') || getEl('nw-input-notes') || getEl('nw-new-notes');
                if (ta) {
                    ta.value = tpl.content;
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            };

            // Direct Send
            const btn = card.querySelector('.nw-btn-direct-send-tpl');
            btn.onclick = (e) => {
                e.stopPropagation();
                sendSingleMessage(NWState.currentPhone, tpl.content);
            };

            section.appendChild(card);
        });
    } catch (e) {
        nwLog("Template load error", e);
    }
}

/**
 * Handle Single Message Send (Direct Send)
 */
async function sendSingleMessage(contactId, message, mediaKey = null) {
    if (!contactId) {
        toast("Selecione um contato primeiro", "warning");
        return;
    }
    if (!message || message.trim() === '') {
        toast("Digite uma mensagem primeiro", "warning");
        return;
    }

    try {
        toast("Enviando mensagem direta...", "info", 2000);
        
        // Use active media if specified (from state)
        let media = null;
        if (mediaKey) media = await NWDB.getFile(mediaKey);
        
        const success = await BroadcastEngine.sendDirectMessage(contactId, message, media);
        
        if (success) {
            toast("Mensagem enviada com sucesso!", "success");
            sendMsg({ action: "INCREMENT_SENT" });
        } else {
            toast("Falha ao enviar mensagem direta.", "error");
        }
    } catch (e) {
        nwLog("Direct send failed", e);
        toast("Erro ao processar envio direto.", "error");
    }
}
