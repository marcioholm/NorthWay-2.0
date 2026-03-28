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
    nwLog(`Updating sidebar for ${name} (${phone})`);
    showState('loading');
    
    const initials = name ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'NW';
    getEl('nw-contact-name').textContent = name || "Desconhecido";
    getEl('nw-contact-initials').textContent = initials;

    const img = getEl('nw-contact-img');
    const initialsEl = getEl('nw-contact-initials');
    if (avatarUrl) {
        img.src = avatarUrl;
        img.classList.remove('hidden');
        initialsEl.classList.add('hidden');
    } else {
        img.classList.add('hidden');
        initialsEl.classList.remove('hidden');
    }

    try {
        const response = await sendMsg({ action: "GET_CONTACT", phone, name: searchName });
        if (!response || response.error) {
            getEl('nw-connection-status').className = 'status-dot disconnected';
            showState('idle');
            return;
        }

        getEl('nw-connection-status').className = 'status-dot connected';

        if (response.found === false) {
            NWState.currentLeadId = null;
            showState('new');
            getEl('nw-new-collapsed').classList.remove('hidden');
            getEl('nw-new-form').classList.add('hidden');
            getEl('nw-new-name').value = name;
            getEl('nw-new-phone').value = phone ? phone.split('@')[0].replace(/\D/g, '') : "";
            loadPipelines(null, 'nw-new-stage');
        } else {
            renderContact(response.data, avatarUrl);
        }
    } catch (e) {
        nwLog("Sidebar update failed", e);
        showState('idle');
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

        section.querySelectorAll('.nw-template-card').forEach(c => c.remove());

        response.forEach(tpl => {
            const card = document.createElement('div');
            card.className = 'nw-template-card';
            card.innerHTML = `
                <div class="nw-template-icon"><svg>...</svg></div>
                <div class="nw-template-info">
                    <strong>${tpl.title}</strong>
                    <p>${tpl.content}</p>
                </div>
            `;
            card.onclick = () => {
                const ta = getEl('nw-broadcast-template') || getEl('nw-input-notes') || getEl('nw-new-notes');
                if (ta) ta.value = tpl.content;
                else toast("Copiado para área de transferência", "success");
            };
            section.appendChild(card);
        });
    } catch (e) {
        nwLog("Template load error", e);
    }
}
