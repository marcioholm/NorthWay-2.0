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

    // Cache buster to force visual updates
    const ts = Date.now();
    const htmlUrl = chrome.runtime.getURL(`scripts/sidebar.html?t=${ts}`);
    const cssUrl = chrome.runtime.getURL(`scripts/sidebar.css?t=${ts}`);

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
        let avatarUrl = null;
        let isGroup = false;

        // 1. Find the Main Chat Panel (Multiple Fallbacks)
        const mainPanel = document.getElementById('main') ||
            document.querySelector('div[role="main"]') ||
            document.querySelector('._aigv._aigz') || // Common WA classes
            document.querySelector('.x1c4vz4f');

        if (mainPanel) {
            // 2. Find the Header (Multiple Fallbacks)
            const header = mainPanel.querySelector('header') ||
                mainPanel.querySelector('div[role="button"]') || // Header is often a button
                mainPanel.querySelector('._aigw');

            if (header) {
                // 3. Extract Avatar & JID via Fiber
                const img = header.querySelector('img');
                if (img) {
                    avatarUrl = img.src;
                    const fiber = getReactInstance(img);
                    if (fiber) {
                        const jid = findJidInFiber(fiber);
                        if (jid) {
                            if (jid.includes('@g.us')) isGroup = true;
                            else {
                                const clean = jid.replace(/\D/g, '');
                                if (clean.length >= 10) phone = clean;
                            }
                        }
                    }
                }

                // 4. Extract Name
                // Search for title or specific spans in header
                const nameEl = header.querySelector('span[title]') ||
                    header.querySelector('span[dir="auto"]') ||
                    header.querySelector('._aacl'); // Name class

                if (nameEl) {
                    name = nameEl.title || nameEl.innerText;
                } else {
                    // Final fallback for name (search for anything that looks like a name in header title area)
                    const fallbackName = header.querySelector('h1') || header.querySelector('div[title]');
                    if (fallbackName) name = fallbackName.innerText || fallbackName.title;
                }

                if (name) name = name.trim();

                if (name || phone) {
                    console.log("NW: Potential Chat Found", { name, phone, jid: phone });
                }

                // 5. Group Refinement (Check for subtitle indicators)
                const subtitleEl = header.querySelector('span[title*=","]') ||
                    header.querySelector('._aa-y'); // Subtitle area
                if (subtitleEl) {
                    const subText = subtitleEl.innerText.toLowerCase();
                    if (subText.includes(',') || subText.includes('participan') || subText.includes('clique')) {
                        isGroup = true;
                    }
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
            updateSidebar(name || phone, phone, null, avatarUrl);
        } else if (name && name !== currentPhone && !name.includes("WhatsApp") && name !== "Contato") {
            currentPhone = name;
            updateSidebar(name, null, name, avatarUrl);
        } else if (!name && !phone && currentPhone !== null) {
            // Reset if no chat is active
            currentPhone = null;
            showState('idle');
        }

    } catch (err) {
        console.error("NW: Detection Error", err);
    }
}

// --- SIDEBAR UI ---
const getEl = (id) => shadowRoot.getElementById(id);

function showState(state) {
    const states = ['idle', 'loading', 'new', 'contact', 'group', 'broadcast'];
    states.forEach(s => {
        const el = getEl(`nw-state-${s}`);
        if (el) el.classList.add('hidden');
    });

    const active = getEl(`nw-state-${state}`);
    if (active) active.classList.remove('hidden');

    // Show/Hide Templates Section
    const templates = getEl('nw-templates-container');
    if (templates) {
        if (state === 'new' || state === 'contact') {
            templates.classList.remove('hidden');
        } else {
            templates.classList.add('hidden');
        }
    }

    // Hide broadcast if not needed
    if (state !== 'broadcast') {
        const bc = getEl('nw-state-broadcast');
        if (bc) bc.classList.add('hidden');
    }
}

async function updateSidebar(name, phone, searchName = null, avatarUrl = null) {
    showState('loading');
    getEl('nw-contact-name').textContent = name || "Desconhecido";

    // Set placeholder initials
    const initials = name ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'NW';
    getEl('nw-contact-initials').textContent = initials;

    // Handle Avatar Preview
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
            renderContact(response.data, avatarUrl);
        }
    } catch (e) {
        console.log("NW Error", e);
    }
}

function renderContact(data, freshAvatarUrl = null) {
    currentLeadId = data.id;
    showState('contact');
    getEl('nw-contact-name').textContent = data.name;
    getEl('nw-contact-phone').textContent = data.phone;
    getEl('nw-contact-status').textContent = data.status || 'Contato';
    getEl('nw-input-notes').value = data.notes || '';

    // Avatar Logic
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
    autoSend: false,
    batchCount: 0,
    config: { min: 10, max: 20, batchSize: 10, batchWait: 60 },

    init: async function () {
        // Load state from storage
        const result = await chrome.storage.local.get(['bc_queue', 'bc_index', 'bc_active', 'bc_templates', 'bc_auto', 'bc_config', 'bc_batch_count']);
        if (result.bc_queue) this.queue = result.bc_queue;
        if (result.bc_index !== undefined) this.currentIndex = result.bc_index;
        if (result.bc_templates) this.templates = result.bc_templates;
        this.autoSend = result.bc_auto || false;
        if (result.bc_config) this.config = result.bc_config;
        this.batchCount = result.bc_batch_count || 0;

        // UI Sync
        const autoCheck = getEl('nw-broadcast-auto');
        if (autoCheck) autoCheck.checked = this.autoSend;

        const iMin = getEl('nw-delay-min');
        const iMax = getEl('nw-delay-max');
        const iBatchSize = getEl('nw-batch-size');
        const iBatchWait = getEl('nw-batch-wait');

        if (iMin) iMin.value = this.config.min;
        if (iMax) iMax.value = this.config.max;
        if (iBatchSize) iBatchSize.value = this.config.batchSize;
        if (iBatchWait) iBatchWait.value = this.config.batchWait;

        // Listen for config changes
        [iMin, iMax, iBatchSize, iBatchWait].forEach(el => {
            if (el) el.addEventListener('change', () => this.updateConfig());
        });

        // Restore Template A in textarea if we are just starting or A is active
        getEl('nw-broadcast-template').value = this.templates[this.currentTab] || "";

        if (result.bc_active) {
            showState('broadcast');
            getEl('nw-broadcast-setup').classList.add('hidden');
            getEl('nw-broadcast-active').classList.remove('hidden');
            this.renderQueue();
            this.updateStats();
            this.renderCurrent();

            if (this.autoSend) this.attemptAutoSend();
        }
    },

    updateConfig: function () {
        this.config.min = parseInt(getEl('nw-delay-min').value) || 10;
        this.config.max = parseInt(getEl('nw-delay-max').value) || 20;
        this.config.batchSize = parseInt(getEl('nw-batch-size').value) || 10;
        this.config.batchWait = parseInt(getEl('nw-batch-wait').value) || 60;
        this.save();
    },

    save: async function () {
        await chrome.storage.local.set({
            bc_queue: this.queue,
            bc_index: this.currentIndex,
            bc_active: this.currentIndex >= 0,
            bc_templates: this.templates,
            bc_auto: this.autoSend,
            bc_config: this.config,
            bc_batch_count: this.batchCount
        });
    },

    attemptAutoSend: function () {
        const btnConfirm = getEl('nw-btn-bc-confirm');
        if (btnConfirm) btnConfirm.textContent = "⏳ Auto: Procurando botão...";

        let attempts = 0;
        const maxAttempts = 30; // 30 seconds max

        const interval = setInterval(() => {
            attempts++;
            // Enhanced Selector Strategy
            const footer = document.querySelector('footer');
            let sendBtn = null;

            if (footer) {
                // Try finding inside footer first (most reliable)
                sendBtn = footer.querySelector('span[data-icon="send"]');
                if (!sendBtn) sendBtn = footer.querySelector('span[data-icon="send-light"]');
                if (!sendBtn) sendBtn = footer.querySelector('button[aria-label="Send"]');
                if (!sendBtn) sendBtn = footer.querySelector('button[aria-label="Enviar"]');
            }

            if (!sendBtn) {
                // Fallback to global search
                sendBtn = document.querySelector('span[data-icon="send"]');
            }

            if (sendBtn) {
                const clickable = sendBtn.closest('button') || sendBtn;
                console.log("NW: Send button found!", clickable);
                clearInterval(interval);

                // Forceful React Click Simulation
                const eventOpts = { bubbles: true, cancelable: true, view: window };
                clickable.dispatchEvent(new MouseEvent('mousedown', eventOpts));
                clickable.dispatchEvent(new MouseEvent('mouseup', eventOpts));
                clickable.dispatchEvent(new MouseEvent('click', eventOpts));

                // Backup native click 
                setTimeout(() => clickable.click(), 50);

                if (btnConfirm) btnConfirm.textContent = "✅ Auto: Disparado!";

                // Wait before moving to next
                setTimeout(() => {
                    this.confirmSend();
                }, 3000);
            } else {
                if (btnConfirm) btnConfirm.textContent = `⏳ Buscando... (${attempts}s)`;
            }

            if (attempts >= maxAttempts) {
                clearInterval(interval);
                console.log("NW: Auto-send timed out.");
                if (btnConfirm) {
                    btnConfirm.textContent = "⚠️ Botão sumiu? Envie manual e clique aqui.";
                    btnConfirm.disabled = false;
                    // Play a notification sound? (Optional)
                }
            }
        }, 1000);
    },

    importContacts: function (text) {
        console.log("NW: Importing text...", text.substring(0, 100));
        const rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
        this.queue = [];

        // Detect most common delimiter
        let delimiter = ';';
        const sample = rawLines.slice(0, 5).join('\n');
        const counts = { ';': (sample.match(/;/g) || []).length, ',': (sample.match(/,/g) || []).length, '\t': (sample.match(/\t/g) || []).length };
        if (counts[','] > counts[';'] && counts[','] > counts['\t']) delimiter = ',';
        else if (counts['\t'] > counts[';']) delimiter = '\t';

        console.log("NW: Detected delimiter:", delimiter);

        rawLines.forEach((line, index) => {
            const lowerLine = line.toLowerCase();
            // Skip header
            if (index === 0 && (lowerLine.includes('nome') || lowerLine.includes('name')) && (lowerLine.includes('fone') || lowerLine.includes('tel'))) {
                return;
            }

            // Clean parts and remove quotes
            const parts = line.split(delimiter).map(p => p.trim().replace(/^["']|["']$/g, ''));
            if (parts.length >= 2) {
                let name = parts[0];
                let phone = "";
                let extra = { email: "", origem: "", interesse: "", observacao: "", variable: "" };

                // Find first "phone-like" field after the name
                for (let i = 1; i < parts.length; i++) {
                    const clean = parts[i].replace(/\D/g, '');
                    if (clean.length >= 8 && clean.length <= 15) {
                        phone = clean;
                        // Map Standard Format (6 cols) if phone is at index 2
                        if (i === 2 && parts.length >= 4) {
                            extra.email = parts[1] || "";
                            extra.origem = parts[3] || "";
                            extra.interesse = parts[4] || "";
                            extra.observacao = parts[5] || "";
                            extra.variable = extra.interesse;
                        } else {
                            extra.variable = parts[i + 1] || "";
                        }
                        break;
                    }
                }

                if (phone) {
                    // Brazil Fix: If 10-11 digits, add 55
                    if (phone.length === 10 || phone.length === 11) {
                        phone = '55' + phone;
                    }

                    this.queue.push({
                        name: name,
                        phone: phone,
                        status: "PENDENTE",
                        ...extra
                    });
                }
            }
        });
        console.log(`NW: Successfully imported ${this.queue.length} contacts.`);
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

        // Check Auto Send
        const autoCheck = getEl('nw-broadcast-auto');
        this.autoSend = autoCheck ? autoCheck.checked : false;

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
            .replace(/{nome}/gi, item.name || "")
            .replace(/{telefone}/gi, item.phone || "")
            .replace(/{email}/gi, item.email || "")
            .replace(/{origem}/gi, item.origem || "")
            .replace(/{interesse}/gi, item.interesse || "")
            .replace(/{observacao}/gi, item.observacao || "")
            .replace(/{variavel}/gi, item.variable || "");

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

        // Batch Counting
        this.batchCount++;
        this.save();

        const btn = getEl('nw-btn-bc-confirm');
        btn.disabled = true;

        let delay = 0;
        let isBatchPause = false;

        // Check for batch pause
        if (this.config.batchSize > 0 && this.batchCount >= this.config.batchSize) {
            delay = this.config.batchWait * 1000;
            isBatchPause = true;
            this.batchCount = 0; // Reset batch
        } else {
            // Normal Random Delay
            const min = this.config.min || 10;
            const max = this.config.max || 20;
            delay = Math.floor(Math.random() * (max - min + 1) + min) * 1000;
        }

        // Countdown Timer
        let totalTime = delay / 1000;
        let remaining = totalTime;
        const msgPrefix = isBatchPause ? "🛡️ Pausa Longa: " : "Aguardando ";

        btn.textContent = `${msgPrefix}${Math.ceil(remaining)}s...`;

        // UI Progress Elements
        const progressSection = getEl('nw-progress-section');
        const countdownText = getEl('nw-countdown-text');
        const progressFill = getEl('nw-progress-fill');

        if (progressSection) progressSection.classList.remove('hidden');

        // Animation Loop
        const tickRate = 100; // Update every 100ms for smoothness
        const step = 100 / (totalTime * 10); // Percentage step per tick
        let currentWidth = 0;

        const interval = setInterval(() => {
            remaining -= 0.1;
            currentWidth += step;

            // Text Updates
            if (Math.ceil(remaining) !== Math.ceil(remaining + 0.1)) {
                btn.textContent = `${msgPrefix}${Math.ceil(remaining)}s...`;
                if (countdownText) countdownText.textContent = `${Math.ceil(remaining)}s`;
            }

            // Bar Update
            if (progressFill) progressFill.style.width = `${Math.min(currentWidth, 100)}%`;

            if (remaining <= 0) {
                clearInterval(interval);
                if (btn) {
                    btn.textContent = "Confirmar Envio";
                    btn.disabled = false;
                }

                if (progressSection) progressSection.classList.add('hidden');
                if (progressFill) progressFill.style.width = '0%';

                this.next();
            }
        }, tickRate);

        // Store interval ID to allow stopping
        this.currentDelayInterval = interval;
    },

    stop: async function () {
        console.log("NW: Stopping Broadcast");

        // Clear Intervals
        if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);

        this.isPaused = false;
        this.currentIndex = -1;
        this.queue = [];
        this.batchCount = 0;
        await this.save();

        const btn = getEl('nw-btn-bc-confirm');
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Confirmar Envio";
        }

        // Reset Progress UI
        const progressSection = getEl('nw-progress-section');
        const progressFill = getEl('nw-progress-fill');
        if (progressSection) progressSection.classList.add('hidden');
        if (progressFill) progressFill.style.width = '0%';

        this.updateStats();

        // Reset View
        const preview = getEl('nw-bc-message-preview');
        if (preview) preview.textContent = 'Toque em "Próximo" para carregar...';

        getEl('nw-bc-current-name').textContent = "Aguardando...";
        getEl('nw-bc-current-phone').textContent = "";

        getEl('nw-broadcast-active').classList.add('hidden');
        getEl('nw-broadcast-setup').classList.remove('hidden');
    },
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

    shadowRoot.querySelectorAll('.nw-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const textarea = getEl('nw-broadcast-template');
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = textarea.value;
            const variable = chip.dataset.var;

            textarea.value = text.substring(0, start) + variable + text.substring(end);
            textarea.focus();
            textarea.selectionStart = textarea.selectionEnd = start + variable.length;

            // Sync with engine
            BroadcastEngine.templates[BroadcastEngine.currentTab] = textarea.value;
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
    if (getEl('nw-btn-bc-confirm')) getEl('nw-btn-bc-confirm').addEventListener('click', () => BroadcastEngine.confirmSend());
    if (getEl('nw-btn-bc-skip')) getEl('nw-btn-bc-skip').addEventListener('click', () => {
        BroadcastEngine.queue[BroadcastEngine.currentIndex].status = 'PULADO';
        BroadcastEngine.next();
    });
    if (getEl('nw-btn-bc-stop')) getEl('nw-btn-bc-stop').addEventListener('click', () => BroadcastEngine.stop());

    // Legacy Binds
    if (getEl('nw-btn-create')) {
        getEl('nw-btn-create').addEventListener('click', async () => {
            const name = getEl('nw-new-name')?.value;
            const phone = getEl('nw-new-phone')?.value;
            const email = getEl('nw-new-email')?.value;
            const notes = getEl('nw-new-notes')?.value;
            const stageId = getEl('nw-new-stage')?.value;
            const avatarUrl = getEl('nw-contact-img')?.classList.contains('hidden') ? null : getEl('nw-contact-img')?.src;
            const res = await chrome.runtime.sendMessage({
                action: "CREATE_LEAD",
                data: { name, phone, email, notes, pipeline_stage_id: stageId, avatar_url: avatarUrl }
            });
            if (res.success) renderContact(res.lead);
            else alert(res.error);
        });
    }

    if (getEl('nw-btn-save')) {
        getEl('nw-btn-save').addEventListener('click', async () => {
            if (!currentLeadId) return;
            const notes = getEl('nw-input-notes')?.value;
            const stageId = getEl('nw-input-stage')?.value;
            const avatarUrl = getEl('nw-contact-img')?.classList.contains('hidden') ? null : getEl('nw-contact-img')?.src;
            await chrome.runtime.sendMessage({
                action: "UPDATE_LEAD",
                id: currentLeadId,
                data: { notes, pipeline_stage_id: stageId, avatar_url: avatarUrl }
            });
            const btn = getEl('nw-btn-save');
            btn.textContent = "Salvo!";
            setTimeout(() => btn.textContent = "Salvar Alterações", 2000);
        });
    }

    if (getEl('nw-link-crm')) {
        getEl('nw-link-crm').addEventListener('click', (e) => {
            if (currentLeadId) e.target.href = `https://crm.northwaycompany.com.br/leads/${currentLeadId}`;
        });

        const exportBtn = getEl('nw-btn-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                // Use the toggle method primarily
                GroupExtractor.toggle();
            });
        }
    }
}

setTimeout(init, 3000);
