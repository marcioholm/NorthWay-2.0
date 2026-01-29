// NorthWay Content Script - Robust Version
let shadowRoot = null;
let currentPhone = null;
let currentLeadId = null;

// --- INITIALIZATION ---
async function init() {
    console.log("NW: Initializing... v2.1 - Syntax Fixed");

    let sidebarContainer = document.getElementById('northway-sidebar-host');
    if (!sidebarContainer) {
        sidebarContainer = document.createElement('div');
        sidebarContainer.id = 'northway-sidebar-host';
        document.body.appendChild(sidebarContainer);
    }

    sidebarContainer.style.position = 'fixed';
    sidebarContainer.style.top = '0';
    sidebarContainer.style.right = '0';
    sidebarContainer.style.width = '350px';
    sidebarContainer.style.height = '100%';
    sidebarContainer.style.zIndex = '99999';
    sidebarContainer.style.pointerEvents = 'none';
    sidebarContainer.style.boxShadow = '-2px 0 5px rgba(0,0,0,0.1)';

    if (!shadowRoot) {
        shadowRoot = sidebarContainer.attachShadow({ mode: 'open' });
    }

    const htmlUrl = chrome.runtime.getURL('scripts/sidebar.html');
    const cssUrl = chrome.runtime.getURL('scripts/sidebar.css');

    try {
        const [html, css] = await Promise.all([
            fetch(htmlUrl).then(r => r.text()),
            fetch(cssUrl).then(r => r.text())
        ]);

        const finalHtml = html.replace(/__MSG_@@extension_id__/g, chrome.runtime.id);
        shadowRoot.innerHTML = `<style>${css}</style>${finalHtml}`;

        sidebarContainer.style.pointerEvents = 'auto';
        sidebarContainer.style.background = '#f0f2f5';

        bindEvents();
        startObserver();
        adjustLayout();

        setInterval(checkActiveChat, 1000);
        setInterval(adjustLayout, 2000);

    } catch (e) {
        console.error("NW: Init failed", e);
    }
}

function adjustLayout() {
    const appWrapper = document.getElementById('app');
    if (appWrapper) {
        const mainContent = appWrapper.firstElementChild;
        if (mainContent) {
            mainContent.style.width = 'calc(100% - 350px)';
            mainContent.style.minWidth = 'auto';
            mainContent.style.transition = 'width 0.3s ease';
        }
    }
}

function startObserver() {
    const observer = new MutationObserver(() => {
        checkActiveChat();
    });
    const main = document.getElementById('main') || document.body;
    observer.observe(main, { childList: true, subtree: true });
}

// --- REACT FIBER HELPERS ---
function getReactInstance(dom) {
    for (const key in dom) {
        if (key.startsWith("__reactFiber")) return dom[key];
    }
    return null;
}

function findJidInFiber(fiber) {
    let queue = [{ node: fiber, depth: 0 }];
    let visited = new Set();
    while (queue.length > 0) {
        const { node, depth } = queue.shift();
        if (!node || depth > 25 || visited.has(node)) continue;
        visited.add(node);

        const props = node.memoizedProps;
        if (props) {
            if (props.jid && typeof props.jid === 'string') return props.jid;
            if (props.id && typeof props.id === 'object' && props.id.user) return props.id.user;
        }

        if (node.child) queue.push({ node: node.child, depth: depth + 1 });
        if (node.sibling) queue.push({ node: node.sibling, depth: depth + 1 });
    }
    return null;
}

// --- DETECTION LOGIC (Simplified) ---
function checkActiveChat() {
    try {
        let name = null;
        let phone = null;
        let isGroup = false;

        const mainPanel = document.getElementById('main') || document.querySelector('div[role="main"]');

        if (mainPanel) {
            const header = mainPanel.querySelector('header');
            if (header) {
                // 1. Fiber Analysis (Primary for ID)
                const img = header.querySelector('img');
                if (img) {
                    const fiber = getReactInstance(img);
                    if (fiber) {
                        const jid = findJidInFiber(fiber);
                        if (jid) {
                            if (jid.includes('@g.us')) {
                                isGroup = true;
                            } else if (jid.includes('@c.us') || jid.includes('@s.whatsapp.net')) {
                                const clean = jid.replace(/@.+/, '');
                                if (clean.match(/^\d+$/) && clean.length >= 10) phone = clean;
                            }
                        }
                    }
                }

                // 2. Name Extraction
                const titleSpan = header.querySelector('span[dir="auto"]');
                if (titleSpan) {
                    name = titleSpan.innerText;

                    // 3. Group Heuristics (Subtitle Analysis)
                    const infoButton = titleSpan.closest('div[role="button"]');
                    if (infoButton) {
                        const fullText = infoButton.innerText;
                        const subtitle = fullText.replace(name, '').trim().toLowerCase();

                        // Check for group indicators in subtitle
                        if (subtitle.includes(',') && subtitle.length > 15) isGroup = true;
                        if (subtitle.includes('participan') || subtitle.includes('group') || subtitle.includes('clique')) isGroup = true; // PT/EN loose match
                    }
                }

                // 4. Fallback Detection
                if (name && name.includes(',') && name.length > 50) {
                    isGroup = true;
                    name = "Grupo Detectado";
                }

                if (!phone && name && name.match(/^\+?\d[\d\s-]{10,}$/)) {
                    const clean = name.replace(/\D/g, '');
                    if (clean.length >= 10) phone = clean;
                }
            }
        }

        // --- DRAWER OVERRIDE ---
        const drawerTitle = Array.from(document.querySelectorAll('span')).find(el =>
            el.innerText.match(/Dados do|Contact info|Group info|Business info/i)
        );

        if (drawerTitle) {
            const container = drawerTitle.closest('div._aigv') || drawerTitle.closest('section');
            if (drawerTitle.innerText.match(/group|grupo/i)) {
                isGroup = true;
                if (container) {
                    const h2 = container.querySelector('h2') || container.querySelector('span[dir="auto"]');
                    if (h2) name = h2.innerText;
                }
            } else {
                // Contact Drawer - Try to recover phone
                if (container && !phone) {
                    // Try Fiber
                    const dImg = container.querySelector('img');
                    if (dImg) {
                        const f = getReactInstance(dImg);
                        if (f) {
                            const j = findJidInFiber(f);
                            if (j) phone = j.replace(/\D/g, '');
                        }
                    }
                    // Try visual scan
                    if (!phone) {
                        const spans = container.querySelectorAll('span');
                        for (const s of spans) {
                            if (s.innerText.match(/^\+?\d[\d\s-]{12,}$/)) {
                                phone = s.innerText.replace(/\D/g, '');
                                break;
                            }
                        }
                    }
                }
            }
        }

        if (name === "WhatsApp") name = null;

        // --- DISPATCH ---
        if (isGroup) {
            const key = `GROUP:${name}`;
            if (currentPhone !== key) {
                currentPhone = key;
                showState('group');
                const el = shadowRoot.getElementById('nw-group-name');
                if (el) el.textContent = name || "Grupo";
            }
        } else if (phone && phone !== currentPhone) {
            currentPhone = phone;
            updateSidebar(name || phone, phone);
        } else if (name && !phone && !name.includes("WhatsApp") && name !== "Contato") {
            if (currentPhone !== name) {
                currentPhone = name;
                console.log("NW: Saved Contact (No Phone)", name);
                updateSidebar(name, null, name);
            }
        }

    } catch (err) {
        console.error("NW: Detection Error", err);
    }
}

// --- SIDEBAR UI ---
const getEl = (id) => shadowRoot.getElementById(id);

function showState(state) {
    ['idle', 'loading', 'new', 'contact', 'group'].forEach(s => {
        const el = getEl(`nw-state-${s}`);
        if (el) el.classList.add('hidden');
    });
    const active = getEl(`nw-state-${state}`);
    if (active) active.classList.remove('hidden');
}

async function updateSidebar(name, phone, searchName = null) {
    showState('loading');
    getEl('nw-contact-name').textContent = name || "Desconhecido";

    if (!phone && !searchName) return;

    try {
        const response = await chrome.runtime.sendMessage({
            action: "GET_CONTACT",
            phone: phone,
            name: searchName
        });

        if (response.error) {
            getEl('nw-connection-status').className = 'status-dot disconnected';
            return;
        }

        getEl('nw-connection-status').className = 'status-dot connected';

        if (response.found === false) {
            // New Lead
            currentLeadId = null;
            showState('new');
            getEl('nw-new-name').value = name;
            getEl('nw-new-phone').value = phone || "";
            getEl('nw-new-phone').placeholder = phone ? "Detectado" : "Digite o telefone";
            loadPipelines(null, 'nw-new-stage');
        } else {
            // Existing Contact
            renderContact(response.data);
        }
    } catch (e) {
        console.log("NW Error", e);
    }
}

function renderContact(data) {
    currentLeadId = data.id;
    showState('contact');
    getEl('nw-contact-name').textContent = data.name;
    getEl('nw-contact-phone').textContent = data.phone;
    getEl('nw-contact-status').textContent = data.status;
    getEl('nw-input-notes').value = data.notes || '';
    getEl('nw-input-tags').value = data.bant_need || '';
    loadPipelines(data.pipeline_stage_id);
}

async function loadPipelines(currentStageId, targetId = 'nw-input-stage') {
    const response = await chrome.runtime.sendMessage({ action: "GET_PIPELINES" });
    const select = getEl(targetId);
    if (!select) return;
    select.innerHTML = '';
    if (response && Array.isArray(response)) {
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
}

// --- GROUP EXPORT LOGIC (PASSIVE MODE) ---
const GroupExtractor = {
    isExtracting: false,
    contacts: new Map(),
    observer: null,
    container: null,
    groupName: "",

    toggle: async function () {
        if (this.isExtracting) {
            this.stop();
        } else {
            await this.start();
        }
    },

    start: async function () {
        const progressText = getEl('nw-export-status');
        const btn = getEl('nw-btn-export');

        // 1. Passive Container Detection
        // User MUST have the list open. We do not click anything.
        const sections = Array.from(document.querySelectorAll('section, div._aigv, div[role="dialog"]'));
        this.container = sections.find(s => {
            if (s.offsetParent === null) return false; // Hidden
            const t = s.innerText.toLowerCase();
            return t.match(/membros|participantes|participants|dados do grupo/);
        });

        // Specific check for small lists (no separate container, just inside drawer)
        if (!this.container) {
            const drawer = document.querySelector('div[role="navigation"]') || document.querySelector('div._aigv'); // Fallback
            if (drawer && drawer.innerText.match(/membros|participantes/i)) this.container = drawer;
        }

        if (!this.container) {
            alert("⚠️ Ação Manual Necessária:\n\n1. Abra o grupo.\n2. Clique no topo para ver os dados.\n3. Role até ver a LISTA DE PARTICIPANTES.\n\nDepois clique em 'Iniciar' novamente.");
            return;
        }

        // 2. Initialize
        this.isExtracting = true;
        this.contacts.clear();
        this.groupName = getEl('nw-group-name').textContent || "Grupo";

        // 3. UI Feedback
        if (btn) btn.textContent = "Finalizar e Baixar";
        if (btn) btn.style.backgroundColor = "#dc3545"; // Red for stop
        getEl('nw-export-progress').classList.remove('hidden');
        if (progressText) progressText.innerText = "Extração Ativa! Role a lista manualmente...";

        // 4. Initial Scrape (Visible items)
        this.scrapeVisible();

        // 5. Start Observer (Watch for Scroll/New Items)
        this.observer = new MutationObserver(() => {
            if (this.checkForSecurityPopup()) return;
            this.scrapeVisible();
        });

        this.observer.observe(this.container, { childList: true, subtree: true });
    },

    stop: function () {
        this.isExtracting = false;
        if (this.observer) this.observer.disconnect();

        // Generate CSV
        this.downloadCSV();

        // Reset UI
        const btn = getEl('nw-btn-export');
        const progressText = getEl('nw-export-status');
        if (btn) {
            btn.textContent = "Extrair Participantes";
            btn.style.backgroundColor = ""; // Reset color
        }
        if (progressText) progressText.innerText = `Finalizado! ${this.contacts.size} contatos exportados.`;

        setTimeout(() => getEl('nw-export-progress').classList.add('hidden'), 5000);
    },

    scrapeVisible: function () {
        if (!this.isExtracting || !this.container) return;

        // Broad selector for contacts
        const items = this.container.querySelectorAll('div[role="listitem"]');

        items.forEach(item => {
            const lines = item.innerText.split('\n');
            if (lines.length < 1) return;

            let name = lines[0];
            let secondary = lines[1] || "";
            let phone = "";

            // Phone Extraction Logic
            if (name.match(/^\+?\d[\d\s-]{8,}$/)) {
                phone = name.replace(/\D/g, '');
                name = "Contato WhatsApp";
                if (secondary.includes('~')) name = secondary.replace(/[~]/g, '').trim();
            } else {
                if (secondary.match(/^\+?\d[\d\s-]{8,}$/)) phone = secondary.replace(/\D/g, '');
            }

            if (name === "Você" || name === "You") return;
            if (phone && !phone.startsWith('55') && phone.length <= 11) phone = '55' + phone;

            const key = phone || name;

            if (!this.contacts.has(key)) {
                this.contacts.set(key, {
                    name: name.replace(/"/g, ''),
                    phone: phone,
                    origin: `Grupo: ${this.groupName}`,
                    date: new Date().toLocaleDateString()
                });
                // Live Update
                const p = getEl('nw-export-status');
                if (p) p.innerText = `Capturando... ${this.contacts.size} detetados`;
            }
        });
    },

    checkForSecurityPopup: function () {
        const dialogs = document.querySelectorAll('div[role="dialog"]');
        const securityAlert = Array.from(dialogs).find(d => d.innerText.match(/criptografia|encryption|segurança/i));

        if (securityAlert) {
            this.observer.disconnect(); // Pause observation
            getEl('nw-export-status').innerText = "⏸ PAUSADO: Alerta de Segurança do WhatsApp";
            alert("⚠️ AVISO DE SEGURANÇA:\n\nO WhatsApp exibiu um alerta de criptografia.\n\nA extração foi PAUSADA automaticamente por segurança.\nConfirme o aviso no WhatsApp e clique em 'Finalizar' para salvar o que já foi pego.");
            return true;
        }
        return false;
    },

    downloadCSV: function () {
        const csvHeader = ["Nome", "Email", "Telefone", "Origem", "Interesse", "Observações"];

        const toCSV = (text) => {
            if (!text) return '""';
            const safe = String(text).replace(/"/g, '""');
            return `"${safe}"`;
        };

        const csvRows = Array.from(this.contacts.values()).map(c => {
            return [
                toCSV(c.name),
                toCSV(""),
                toCSV(c.phone),
                toCSV(c.origin),
                toCSV("A definir"),
                toCSV(`Extraído em ${c.date}`)
            ].join(';');
        });

        const csvContent = "\uFEFF" + csvHeader.join(';') + "\n" + csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `grupo_${this.groupName.replace(/\s/g, '_')}_${Date.now()}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
};

// --- BROADCAST ENGINE ---
const BroadcastEngine = {
    queue: [],
    currentIndex: -1,
    isPaused: false,
    templates: { A: "", B: "", C: "" },
    currentTab: "A",

    init: async function () {
        // Load state from storage
        const result = await chrome.storage.local.get(['bc_queue', 'bc_index', 'bc_active']);
        if (result.bc_queue) this.queue = result.bc_queue;
        if (result.bc_index !== undefined) this.currentIndex = result.bc_index;

        if (result.bc_active) {
            showState('broadcast');
            getEl('nw-broadcast-setup').classList.add('hidden');
            getEl('nw-broadcast-active').classList.remove('hidden');
            this.renderQueue();
            this.updateStats();
            this.renderCurrent();
        }
    },

    save: async function () {
        await chrome.storage.local.set({
            bc_queue: this.queue,
            bc_index: this.currentIndex,
            bc_active: this.currentIndex >= 0
        });
    },

    importContacts: function (text) {
        const lines = text.split('\n');
        this.queue = [];
        lines.forEach(line => {
            const parts = line.split(';');
            if (parts.length >= 2) {
                const phone = parts[1].replace(/\D/g, '');
                if (phone.length >= 10) {
                    this.queue.push({
                        name: parts[0].trim(),
                        phone: phone,
                        variable: parts[2] ? parts[2].trim() : "",
                        status: "PENDENTE"
                    });
                }
            }
        });
        this.save();
        this.renderQueue();
        this.updateStats();
    },

    renderQueue: function () {
        const list = getEl('nw-bc-queue-list');
        if (!list) return;
        list.innerHTML = '';
        this.queue.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = `nw-q-item ${index === this.currentIndex ? 'active' : ''}`;
            div.innerHTML = `
                <span>${item.name}</span>
                <span class="nw-q-status ${item.status}">${item.status}</span>
            `;
            list.appendChild(div);
        });
    },

    updateStats: function () {
        const p = getEl('nw-stat-pending');
        if (p) p.textContent = this.queue.filter(i => i.status === 'PENDENTE').length;
        const s = getEl('nw-stat-sent');
        if (s) s.textContent = this.queue.filter(i => i.status === 'ENVIADO').length;
        const f = getEl('nw-stat-failed');
        if (f) f.textContent = this.queue.filter(i => i.status === 'FALHOU').length;
    },

    start: function () {
        if (this.queue.length === 0) {
            alert("⚠️ Importe contatos primeiro!");
            return;
        }
        getEl('nw-broadcast-setup').classList.add('hidden');
        getEl('nw-broadcast-active').classList.remove('hidden');
        this.currentIndex = -1;
        this.next();
    },

    renderCurrent: function () {
        if (this.currentIndex < 0 || this.currentIndex >= this.queue.length) return "";
        const item = this.queue[this.currentIndex];
        const currentNameEl = getEl('nw-bc-current-name');
        if (currentNameEl) currentNameEl.textContent = item.name;
        const currentPhoneEl = getEl('nw-bc-current-phone');
        if (currentPhoneEl) currentPhoneEl.textContent = item.phone;

        // Rotation A/B/C
        const variantKeys = ['A', 'B', 'C'];
        const currentVariant = variantKeys[this.currentIndex % 3];
        const template = this.templates[currentVariant] || this.templates['A'] || getEl('nw-broadcast-template').value;

        const message = template
            .replace(/{nome}/gi, item.name)
            .replace(/{variavel}/gi, item.variable)
            .replace(/{telefone}/gi, item.phone);

        const previewEl = getEl('nw-bc-message-preview');
        if (previewEl) previewEl.textContent = `[Variação ${currentVariant}] ${message}`;
        return message;
    },

    next: async function () {
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            alert("✅ Disparo finalizado!");
            this.stop();
            return;
        }

        const item = this.queue[this.currentIndex];
        if (item.status !== 'PENDENTE') return this.next();

        this.renderQueue();
        const message = this.renderCurrent();
        this.save();

        // Open Chat using a safer method that won't infinite loop
        const currentUrl = new URL(window.location.href);
        const targetUrl = `https://web.whatsapp.com/send?phone=${item.phone}&text=${encodeURIComponent(message)}`;

        if (!currentUrl.search.includes(item.phone)) {
            window.location.href = targetUrl;
        }
    },

    confirmSend: function () {
        if (this.currentIndex < 0) return;
        this.queue[this.currentIndex].status = 'ENVIADO';
        this.updateStats();
        this.save();

        const min = 5, max = 15;
        const delay = Math.floor(Math.random() * (max - min + 1) + min) * 1000;

        const btn = getEl('nw-btn-bc-confirm');
        btn.textContent = `Aguardando ${delay / 1000}s...`;
        btn.disabled = true;

        setTimeout(() => {
            btn.textContent = "Confirmar Envio";
            btn.disabled = false;
            this.next();
        }, delay);
    },

    stop: async function () {
        this.currentIndex = -1;
        await chrome.storage.local.remove(['bc_queue', 'bc_index', 'bc_active']);
        getEl('nw-broadcast-setup').classList.remove('hidden');
        getEl('nw-broadcast-active').classList.add('hidden');
        showState('broadcast');
    }
};

function bindEvents() {
    BroadcastEngine.init();
    // Nav
    getEl('nw-btn-nav-broadcast').addEventListener('click', () => showState('broadcast'));
    getEl('nw-btn-close-broadcast').addEventListener('click', () => showState('idle'));

    // Tabs
    shadowRoot.querySelectorAll('.nw-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            shadowRoot.querySelectorAll('.nw-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            BroadcastEngine.currentTab = btn.dataset.tab;
            // Update textarea with chosen template variation (if stored)
            getEl('nw-broadcast-template').value = BroadcastEngine.templates[BroadcastEngine.currentTab] || "";
        });
    });

    getEl('nw-broadcast-template').addEventListener('input', (e) => {
        BroadcastEngine.templates[BroadcastEngine.currentTab] = e.target.value;
    });

    // Import
    getEl('nw-broadcast-import-text').addEventListener('input', (e) => {
        BroadcastEngine.importContacts(e.target.value);
    });

    getEl('nw-broadcast-import-file').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (f) => {
            BroadcastEngine.importContacts(f.target.result);
            getEl('nw-broadcast-import-text').value = f.target.result;
        };
        reader.readAsText(file);
    });

    getEl('nw-btn-start-broadcast').addEventListener('click', () => BroadcastEngine.start());

    // Controls
    getEl('nw-btn-bc-confirm').addEventListener('click', () => BroadcastEngine.confirmSend());
    getEl('nw-btn-bc-skip').addEventListener('click', () => {
        BroadcastEngine.queue[BroadcastEngine.currentIndex].status = 'PULADO';
        BroadcastEngine.next();
    });
    getEl('nw-btn-bc-stop').addEventListener('click', () => BroadcastEngine.stop());

    // Legacy Binds
    getEl('nw-btn-create').addEventListener('click', async () => {
        const name = getEl('nw-new-name').value;
        const phone = getEl('nw-new-phone').value;
        const email = getEl('nw-new-email').value;
        const interest = getEl('nw-new-interest').value;
        const notes = getEl('nw-new-notes').value;
        const stageId = getEl('nw-new-stage').value;
        const res = await chrome.runtime.sendMessage({
            action: "CREATE_LEAD",
            data: { name, phone, email, notes, bant_need: interest, pipeline_stage_id: stageId }
        });
        if (res.success) renderContact(res.lead);
        else alert(res.error);
    });

    getEl('nw-btn-save').addEventListener('click', async () => {
        if (!currentLeadId) return;
        const notes = getEl('nw-input-notes').value;
        const tags = getEl('nw-input-tags').value;
        const stageId = getEl('nw-input-stage').value;
        await chrome.runtime.sendMessage({
            action: "UPDATE_LEAD",
            id: currentLeadId,
            data: { notes, bant_need: tags, pipeline_stage_id: stageId }
        });
        const btn = getEl('nw-btn-save');
        btn.textContent = "Salvo!";
        setTimeout(() => btn.textContent = "Salvar Alterações", 2000);
    });

    getEl('nw-link-crm').addEventListener('click', (e) => {
        if (currentLeadId) e.target.href = `https://north-way-2-0.vercel.app/leads/${currentLeadId}`;
    });

    const exportBtn = getEl('nw-btn-export');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            // Use the toggle method primarily
            GroupExtractor.toggle();
        });
    }
}

setTimeout(init, 3000);
