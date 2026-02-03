// NorthWay Content Script - Robust Version
let shadowRoot = null;
let currentPhone = null;
let currentLeadId = null;
let intervalChat = null;
let intervalLayout = null;

// --- INDEXEDDB HELPER FOR FILE PERSISTENCE ---
const NWDB = {
    name: "NorthWayDB",
    version: 1,
    store: "files",
    db: null,
    init: function () {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.name, this.version);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(this.store)) {
                    db.createObjectStore(this.store);
                }
            };
            request.onsuccess = (e) => {
                this.db = e.target.result;
                resolve(this.db);
            };
            request.onerror = (e) => reject(e);
        });
    },
    saveFile: async function (key, file) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const store = tx.objectStore(this.store);
            const request = store.put(file, key);
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e);
        });
    },
    getFile: async function (key) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.store, "readonly");
            const store = tx.objectStore(this.store);
            const request = store.get(key);
            request.onsuccess = () => resolve(request.result);
            request.onerror = (e) => reject(e);
        });
    },
    clear: async function () {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const store = tx.objectStore(this.store);
            const request = store.clear();
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e);
        });
    }
};

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
        sidebarContainer.style.background = 'transparent'; // FIX: Was #f0f2f5, causing "white bar" effect

        bindEvents();
        startObserver();
        adjustLayout(); // User requested resizing back

        // --- BRIDGE CHECK ---
        setTimeout(() => {
            console.log("NW: Sending PING to Main World...");
            window.postMessage({ source: "NW_EXTENSION", type: "NW_PING" }, "*");
        }, 3000);
        // --------------------

        if (intervalChat) clearInterval(intervalChat);
        if (intervalLayout) clearInterval(intervalLayout);

        intervalChat = setInterval(checkActiveChat, 1000);
        intervalLayout = setInterval(adjustLayout, 2000);

    } catch (e) {
        console.log("NW: Init failed", e);
    }
}

// (Page Script is now injected via manifest.json with world: "MAIN")

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

        // If a broadcast is active, don't reset to idle just because we switched contacts
        const isBcActive = BroadcastEngine.currentIndex >= 0;

        if (drawerTitle) {
            const container = drawerTitle.closest('div._aigv') || drawerTitle.closest('section');
            if (drawerTitle.innerText.match(/group|grupo/i)) {
                isGroup = true;
                if (container) {
                    const h2 = container.querySelector('h2') || container.querySelector('span[dir="auto"]');
                    if (h2) {
                        let rawName = h2.innerText;
                        // Safety: If name is too long, it's likely the participant list dump. Truncate it.
                        if (rawName.length > 50) {
                            rawName = rawName.substring(0, 47) + "...";
                        }
                        name = rawName;
                    }
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
        if (isBcActive) {
            // During broadcast, we stay in the broadcast view
            return;
        }

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
        } else if (!name && !phone && currentPhone !== null && !isBcActive) {
            // Reset if no chat is active AND no broadcast is running
            currentPhone = null;
            showState('idle');
        }

    } catch (err) {
        console.log("NW: Detection Error", err);
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
    media: null,
    mediaCaption: "",
    currentMessage: "",
    currentMediaCaption: "",
    currentStep: 1, // 1: Text, 2: Media
    config: { min: 10, max: 20, batchSize: 10, batchWait: 60 },

    init: async function () {
        // Load state from storage
        const result = await chrome.storage.local.get(['bc_queue', 'bc_index', 'bc_active', 'bc_templates', 'bc_auto', 'bc_config', 'bc_batch_count', 'bc_current_message', 'bc_media_caption', 'bc_current_step', 'bc_media_name', 'bc_media_type']);
        if (result.bc_queue) this.queue = result.bc_queue;
        if (result.bc_index !== undefined) this.currentIndex = result.bc_index;
        if (result.bc_templates) this.templates = result.bc_templates;
        this.autoSend = result.bc_auto || false;
        if (result.bc_config) this.config = result.bc_config;
        this.batchCount = result.bc_batch_count || 0;
        if (result.bc_current_message) this.currentMessage = result.bc_current_message;
        if (result.bc_media_caption) this.mediaCaption = result.bc_media_caption;
        if (result.bc_current_step) this.currentStep = result.bc_current_step;
        if (result.bc_media_name) this.mediaName = result.bc_media_name;
        if (result.bc_media_type) this.mediaType = result.bc_media_type;

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
            // Restore Media from IndexedDB
            // Restore Media from IndexedDB
            const savedMedia = await NWDB.getFile("bc_media");
            console.log("NW: [DEBUG] Init - Metadata from storage:", { name: result.bc_media_name, type: result.bc_media_type });
            console.log("NW: [DEBUG] Init - Raw savedMedia from DB:", savedMedia);

            if (savedMedia) {
                // Re-wrap to ensure it's a valid File object with preserved metadata
                const fileName = result.bc_media_name || savedMedia.name || "arquivo";

                // MIME Map for robust fallback
                const ext = fileName.split('.').pop().toLowerCase();
                const MIME_MAP = {
                    'pdf': 'application/pdf',
                    'png': 'image/png',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'webp': 'image/webp',
                    'mp4': 'video/mp4',
                    'doc': 'application/msword',
                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'xls': 'application/vnd.ms-excel',
                    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'txt': 'text/plain'
                };

                // FORCE SANITIZATION: Rely on MIME_MAP for known extensions significantly more than stored type
                // This fixes "corrupted" state from previous bad saves.
                let fileType = MIME_MAP[ext];

                if (!fileType) {
                    fileType = result.bc_media_type || savedMedia.type || "application/octet-stream";
                }

                console.log(`NW: Restoring File. Name: ${fileName}, Ext: ${ext}, Forced Type: ${fileType}`);

                this.media = new File([savedMedia], fileName, {
                    type: fileType,
                    lastModified: Date.now()
                });
                console.log("NW: [DEBUG] Init - Reconstructed File:", this.media, "Size:", this.media.size, "Type:", this.media.type);
                const prev = getEl('nw-media-preview-container');
                const pName = getEl('nw-media-filename');
                const pCap = getEl('nw-media-caption');
                if (prev) prev.classList.remove('hidden');
                if (pName) pName.textContent = this.media.name;
                if (pCap) pCap.value = this.mediaCaption;
            }

            showState('broadcast');
            getEl('nw-broadcast-setup').classList.add('hidden');
            getEl('nw-broadcast-active').classList.remove('hidden');
            this.renderQueue();
            this.updateStats();
            this.renderCurrent();

            // If we are on step 2 (Media), we need to attach it
            if (this.media && this.currentStep === 2) {
                await this.attachMedia();
            }

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

    attachMedia: async function () {
        if (!this.media) return true;

        console.log("NW: Starting attachment process for:", this.media.name);

        // --- PAGE CONTEXT INJECTION BRIDGE ---
        try {
            // 1. Prepare Data
            const arrayBuffer = await this.media.arrayBuffer();
            const data = Array.from(new Uint8Array(arrayBuffer)); // Serialize for postMessage

            // 2. Determine Kind
            // kind: "document" or "media"
            const isImageOrVideo = this.media.type.startsWith('image/') || this.media.type.startsWith('video/');
            const kind = isImageOrVideo ? 'media' : 'document';

            console.log(`NW: Sending Attach Request to Page. Kind: ${kind}, Type: ${this.media.type}`);

            // 3. Send Message to Page Script
            window.postMessage({
                source: "NW_EXTENSION",
                type: "NW_ATTACH_FILE",
                payload: {
                    kind: kind,
                    name: this.media.name,
                    mime: this.media.type,
                    data: data
                }
            }, "*");

            // 4. Wait for Preview (Standard Logic)
            console.log("NW: Request sent. Waiting for page script to execute and preview to appear...");

            // Wait for preview to appear (up to 30s)
            for (let i = 0; i < 60; i++) {
                await new Promise(r => setTimeout(r, 500));

                const previewSend = this.findSendButton(true);

                // Handle Caption if preview is visible
                const allInputs = Array.from(document.querySelectorAll('div[contenteditable="true"]'));
                const caption = allInputs.find(el => {
                    const isSide = el.closest('#side');
                    const isFooter = el.closest('footer');
                    return !isSide && !isFooter && (el.innerText.trim() === "" || el.innerText.toLowerCase().includes("legenda") || el.innerText.toLowerCase().includes("caption"));
                });

                if (caption && this.currentMediaCaption) {
                    const txt = caption.innerText.trim();
                    if (txt === "" || txt.toLowerCase().includes("legenda") || txt.toLowerCase().includes("caption") || txt.toLowerCase().includes("digite")) {
                        try {
                            caption.focus();
                            document.execCommand('selectAll', false, null);
                            document.execCommand('insertText', false, this.currentMediaCaption);
                            caption.dispatchEvent(new Event('input', { bubbles: true }));
                        } catch (e) {
                            console.warn("Caption error", e);
                        }
                    }
                }

                if (previewSend) {
                    // Wait for Upload Completion (Loading Spinner or Disabled Send)
                    const isDiasbled = previewSend.disabled || previewSend.getAttribute('aria-disabled') === 'true';
                    const hasSpinner = document.querySelector('[data-icon="msg-status-sending"]') || document.querySelector('div[role="progressbar"]');

                    if (!isDiasbled && !hasSpinner) {
                        console.log("NW: Preview ready and upload complete.");
                        return true;
                    } else {
                        console.log("NW: Waiting for upload...");
                    }
                }
            }

            console.log("NW: Timeout waiting for upload, proceeding anyway.");
            return true;

        } catch (e) {
            console.log("NW: Injection failed", e);
            return false;
        }
    },

    save: async function () {
        await chrome.storage.local.set({
            bc_queue: this.queue,
            bc_index: this.currentIndex,
            bc_active: this.currentIndex >= 0,
            bc_templates: this.templates,
            bc_auto: this.autoSend,
            bc_config: this.config,
            bc_batch_count: this.batchCount,
            bc_current_message: this.currentMessage,
            bc_media_caption: this.mediaCaption,
            bc_current_step: this.currentStep
        });
    },

    attemptAutoSend: function () {
        const btnConfirm = getEl('nw-btn-bc-confirm');
        if (btnConfirm) btnConfirm.textContent = "⏳ Auto: Procurando botão...";

        let attempts = 0;
        const maxAttempts = 30; // 30 seconds max

        const interval = setInterval(() => {
            attempts++;
            let sendBtn = this.findSendButton();

            if (sendBtn) {
                const clickable = sendBtn.closest('div[role="button"]') || sendBtn.closest('button') || sendBtn;
                console.log("NW: Send button found!", clickable);
                clearInterval(interval);

                // --- ULTRA-FORCEFUL REACT CLICK SIMULATION ---
                clickable.focus();
                const eventOpts = { bubbles: true, cancelable: true, view: window, isTrusted: true };

                // Mouse Events
                clickable.dispatchEvent(new MouseEvent('mousedown', eventOpts));
                clickable.dispatchEvent(new MouseEvent('mouseup', eventOpts));
                clickable.dispatchEvent(new MouseEvent('click', eventOpts));

                // Pointer Events (Modern React)
                clickable.dispatchEvent(new PointerEvent('pointerdown', eventOpts));
                clickable.dispatchEvent(new PointerEvent('pointerup', eventOpts));

                // Backup native click 
                setTimeout(() => {
                    try { clickable.click(); } catch (e) { }
                }, 50);

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

    findSendButton: function (onlyOverlay = false) {
        // Priority 1: Search for any element with "send" in data-icon OR aria-label
        const allPossible = Array.from(document.querySelectorAll('span[data-icon*="send"], button[aria-label*="Send"], button[aria-label*="Enviar"], div[role="button"][aria-label*="Send"], div[role="button"][aria-label*="Enviar"], [data-testid="send"], [data-testid="compose-btn-send"]'));

        // Priority 1.5: SVG Path detection (Fallback for buttons without clear attributes)
        const svgs = Array.from(document.querySelectorAll('svg'));
        svgs.forEach(svg => {
            const inner = svg.innerHTML.toLowerCase();
            // Paths for various WhatsApp send icons (normal, business, PDF preview)
            if (inner.includes('m1.1,2.1') ||
                inner.includes('m12 4l0 16') ||
                inner.includes('m15.003 12') ||
                inner.includes('m12 2l4.5 20.29')) {
                const btn = svg.closest('button') || svg.closest('div[role="button"]');
                if (btn && !allPossible.includes(btn)) allPossible.push(btn);
            }
        });

        // Filter out sidebar and other irrelevant stuff
        const candidates = allPossible.filter(el => {
            const side = el.closest('#side');
            if (side) return false;
            return true;
        });

        // If we are looking for overlay (Media Preview)
        if (onlyOverlay || document.querySelector('div[role="dialog"]') || document.querySelector('div[role="presentation"]') || document.querySelector('div[role="region"] canvas')) {
            // Prefer buttons inside dialogs/regions/overlays/canvas-previews (PDFs)
            const overlayBtn = candidates.find(el =>
                el.closest('div[role="dialog"]') ||
                el.closest('div[role="region"]') ||
                el.closest('div[role="presentation"]') ||
                el.closest('main') // Some PDF previews are in a main region
            );
            if (overlayBtn) return overlayBtn;

            // If we MUST have an overlay but found none, return null
            if (onlyOverlay) return null;
        }

        // Priority 2: Prefer footer button for regular chat
        const footerBtn = candidates.find(el => el.closest('footer'));
        if (footerBtn) return footerBtn;

        // Final fallback: the first candidate that isn't in side
        return candidates[0] || null;
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
        const pending = this.queue.filter(i => i.status === 'PENDENTE').length;
        const sent = this.queue.filter(i => i.status === 'ENVIADO').length;
        const failed = this.queue.filter(i => i.status === 'FALHOU').length;

        const p = getEl('nw-stat-pending');
        if (p) p.textContent = pending;
        const s = getEl('nw-stat-sent');
        if (s) s.textContent = sent;
        const f = getEl('nw-stat-failed');
        if (f) f.textContent = failed;

        // --- ETA CALCULATION ---
        const etaEl = getEl('nw-stat-eta');
        if (etaEl && pending > 0) {
            // Config values
            const min = this.config.min || 10;
            const max = this.config.max || 20;
            const avgDelay = (min + max) / 2;

            // Add extra buffer for attachments (roughly +10s per msg if media attached)
            const attachmentBuffer = this.media ? 10 : 0;

            // Add batch waiting time
            const batchSize = this.config.batchSize || 10;
            const batchWait = this.config.batchWait || 60;
            const batchesLeft = Math.floor(pending / batchSize);
            const totalBatchWait = batchesLeft * batchWait;

            // Total Seconds
            const totalSeconds = (pending * (avgDelay + attachmentBuffer)) + totalBatchWait;

            // Format HH:MM:SS
            const h = Math.floor(totalSeconds / 3600);
            const m = Math.floor((totalSeconds % 3600) / 60);
            const sec = Math.floor(totalSeconds % 60);

            const parts = [];
            if (h > 0) parts.push(`${h}h`);
            parts.push(`${m}m`);
            parts.push(`${sec}s`);

            etaEl.textContent = parts.join(' ');
        } else if (etaEl) {
            etaEl.textContent = pending === 0 ? "Finalizado" : "--:--";
        }
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

        const caption = this.mediaCaption
            .replace(/{nome}/gi, item.name || "")
            .replace(/{telefone}/gi, item.phone || "")
            .replace(/{email}/gi, item.email || "")
            .replace(/{origem}/gi, item.origem || "")
            .replace(/{interesse}/gi, item.interesse || "")
            .replace(/{observacao}/gi, item.observacao || "")
            .replace(/{variavel}/gi, item.variable || "");

        this.currentMessage = message;
        this.currentMediaCaption = caption;

        const previewEl = getEl('nw-bc-message-preview');
        const mediaTag = this.media ? `\n\n📎 [ANEXO: ${this.media.name}]\n📝 [LEGENDA: ${caption}]` : "";
        if (previewEl) previewEl.textContent = `[Variação ${currentVariant}] ${message}${mediaTag}`;
        return message;
    },

    next: async function () {
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            alert("✅ Disparo finalizado!");
            await this.stop();
            return;
        }

        const item = this.queue[this.currentIndex];
        if (item.status !== 'PENDENTE') return this.next();

        this.renderQueue();
        this.renderCurrent(); // Updates this.currentMessage and this.currentMediaCaption
        this.currentStep = 1; // Always start with text
        await this.save();

        // Open Chat using a safer method that won't infinite loop
        const currentUrl = new URL(window.location.href);
        const targetUrl = `https://web.whatsapp.com/send?phone=${item.phone}&text=${encodeURIComponent(this.currentMessage)}`;

        if (!currentUrl.search.includes(item.phone)) {
            window.location.href = targetUrl;
        }
    },

    confirmSend: async function () {
        if (this.currentIndex < 0) return;

        // --- STEP TRANSITION ---
        if (this.media && this.currentStep === 1) {
            console.log("NW: Text step confirmed, moving to media step in 1.5s...");
            this.currentStep = 2;
            await this.save();

            setTimeout(async () => {
                await this.attachMedia();
                if (this.autoSend) this.attemptAutoSend();
            }, 1500);
            return;
        }

        this.queue[this.currentIndex].status = 'ENVIADO';
        this.updateStats();

        // Batch Counting
        this.batchCount++;
        this.currentStep = 1; // Reset for next contact
        await this.save();

        const btn = getEl('nw-btn-bc-confirm');
        if (btn) btn.disabled = true;

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
        this.media = null;
        await NWDB.clear();
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

    // Media Attachments
    const handleMediaSelect = async (e) => {
        let file = e.target.files[0];
        if (!file) return;

        // --- WEBP CONVERSION FIX ---
        // Convert WEBP to PNG to prevent it from becoming a Sticker automatically
        if (file.type === 'image/webp' || file.name.toLowerCase().endsWith('.webp')) {
            console.log("NW: WEBP detected. Converting to PNG...");
            try {
                const convertWebPToPNG = (webmFile) => {
                    return new Promise((resolve, reject) => {
                        const img = new Image();
                        img.onload = () => {
                            const canvas = document.createElement('canvas');
                            canvas.width = img.width;
                            canvas.height = img.height;
                            canvas.getContext('2d').drawImage(img, 0, 0);
                            canvas.toBlob((blob) => resolve(blob), 'image/png');
                        };
                        img.onerror = reject;
                        img.src = URL.createObjectURL(webmFile);
                    });
                };

                const pngBlob = await convertWebPToPNG(file);
                const newName = file.name.replace(/\.webp$/i, '.png');
                file = new File([pngBlob], newName, { type: 'image/png' });
                console.log("NW: Conversion successful:", file);
            } catch (err) {
                console.log("NW: WEBP Conversion failed", err);
            }
        }
        // ---------------------------

        // --- MIME SANITIZATION ---
        const MIME_MAP = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain'
        };
        const ext = file.name.split('.').pop().toLowerCase();
        const correctType = MIME_MAP[ext] || file.type || "application/octet-stream";

        console.log(`NW: Selected file ${file.name}, Detected Type: ${file.type}, Corrected Type: ${correctType}`);

        // --- FIX A: Reconstruct File with Correct MIME Type ---
        // This ensures the blob saved to DB has the right type metadata
        if (file.type !== correctType) {
            try {
                const buffer = await file.arrayBuffer();
                file = new File([buffer], file.name, { type: correctType, lastModified: Date.now() });
                console.log("NW: File reconstructed with forced MIME:", file.type);
            } catch (e) {
                console.error("NW: Failed to reconstruct file", e);
            }
        }
        // -----------------------------------------------------

        BroadcastEngine.media = file;
        await NWDB.saveFile("bc_media", file);
        // Save metadata separately to ensure recovery after reload
        await chrome.storage.local.set({
            bc_media_name: file.name,
            bc_media_type: correctType
        });

        getEl('nw-media-preview-container').classList.remove('hidden');
        getEl('nw-media-filename').textContent = file.name;
    };

    if (getEl('nw-btn-attach-img')) getEl('nw-btn-attach-img').addEventListener('click', () => getEl('nw-attach-img').click());
    if (getEl('nw-btn-attach-video')) getEl('nw-btn-attach-video').addEventListener('click', () => getEl('nw-attach-video').click());
    if (getEl('nw-btn-attach-doc')) getEl('nw-btn-attach-doc').addEventListener('click', () => getEl('nw-attach-doc').click());

    if (getEl('nw-attach-img')) getEl('nw-attach-img').addEventListener('change', handleMediaSelect);
    if (getEl('nw-attach-video')) getEl('nw-attach-video').addEventListener('change', handleMediaSelect);
    if (getEl('nw-attach-doc')) getEl('nw-attach-doc').addEventListener('change', handleMediaSelect);

    if (getEl('nw-media-clear')) {
        getEl('nw-media-clear').addEventListener('click', async () => {
            BroadcastEngine.media = null;
            BroadcastEngine.mediaCaption = "";
            await NWDB.clear();
            getEl('nw-media-preview-container').classList.add('hidden');
            getEl('nw-media-caption').value = '';
            // Reset file inputs
            getEl('nw-attach-img').value = '';
            getEl('nw-attach-video').value = '';
            getEl('nw-attach-doc').value = '';
        });
    }

    if (getEl('nw-media-caption')) {
        getEl('nw-media-caption').addEventListener('input', (e) => {
            BroadcastEngine.mediaCaption = e.target.value;
            BroadcastEngine.save();
        });
    }

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


// --- AUTH GATING & LIFECYCLE ---
async function bootstrap() {
    console.log("NW: Bootstrapping... Checking Auth.");

    // 1. Check Initial State
    // We send a message to background to check if we have a valid token
    try {
        const response = await chrome.runtime.sendMessage({ action: "CHECK_AUTH" });
        if (response && response.token) {
            console.log("NW: Authenticated. Initializing Sidebar.");
            init();
        } else {
            console.log("NW: Not authenticated. Sidebar will not load.");
            unmount();
        }
    } catch (e) {
        console.warn("NW: Auth check failed (Background might be sleeping)", e);
    }

    // 2. Listen for Auth Changes (Login/Logout)
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local') {
            // Watch for 'authToken' used by ZapWay
            if (changes.authToken) {
                const newToken = changes.authToken.newValue;
                if (newToken) {
                    console.log("NW: Login detected! Mounting Sidebar...");
                    // Only init if not already present
                    if (!document.getElementById('northway-sidebar-host')) {
                        init();
                    }
                } else {
                    console.log("NW: Logout detected. Unmounting Sidebar...");
                    unmount();
                }
            }
        }
    });

    // 3. Listen for direct messages from Popup (optional backup)
    chrome.runtime.onMessage.addListener((req) => {
        if (req.action === "LOGIN_SUCCESS") {
            if (!document.getElementById('northway-sidebar-host')) init();
        }
        if (req.action === "LOGOUT_SUCCESS") {
            unmount();
        }
    });
}

function unmount() {
    // 1. Remove Sidebar
    const el = document.getElementById('northway-sidebar-host');
    if (el) el.remove();

    // 2. Stop Interval Loops
    if (intervalChat) {
        clearInterval(intervalChat);
        intervalChat = null;
    }
    if (intervalLayout) {
        clearInterval(intervalLayout);
        intervalLayout = null;
    }

    // 3. Reset State
    currentPhone = null;
    currentLeadId = null;
    shadowRoot = null;

    // 4. Reset Layout
    const appWrapper = document.getElementById('app');
    if (appWrapper && appWrapper.firstElementChild) {
        appWrapper.firstElementChild.style.width = '';
        appWrapper.firstElementChild.style.minWidth = '';
    }

    console.log("NW: Unmounted successfully.");
}

// Start Lifecycle
setTimeout(bootstrap, 2000);
