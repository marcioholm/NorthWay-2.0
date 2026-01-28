// NorthWay Content Script
let shadowRoot = null;
let currentPhone = null;
let currentLeadId = null;

// --- INITIALIZATION ---
async function init() {
    console.log("NW: Initializing...");

    // Custom container to hold the sidebar
    const sidebarContainer = document.createElement('div');
    sidebarContainer.id = 'northway-sidebar-host';

    // Fixed positioning to float on top right
    sidebarContainer.style.position = 'fixed';
    sidebarContainer.style.top = '0';
    sidebarContainer.style.right = '0';
    sidebarContainer.style.width = '350px';
    sidebarContainer.style.height = '100%';
    sidebarContainer.style.zIndex = '99999'; // High Z-Index to stay on top
    sidebarContainer.style.pointerEvents = 'none'; // Passthrough initially
    sidebarContainer.style.boxShadow = '-2px 0 5px rgba(0,0,0,0.1)';

    document.body.appendChild(sidebarContainer);

    // Create Shadow DOM
    shadowRoot = sidebarContainer.attachShadow({ mode: 'open' });

    // Load HTML & CSS
    const htmlUrl = chrome.runtime.getURL('scripts/sidebar.html');
    const cssUrl = chrome.runtime.getURL('scripts/sidebar.css');

    const [html, css] = await Promise.all([
        fetch(htmlUrl).then(r => r.text()),
        fetch(cssUrl).then(r => r.text())
    ]);

    // Handle missing logo gracefully/cleanly
    const finalHtml = html.replace(/__MSG_@@extension_id__/g, chrome.runtime.id);
    shadowRoot.innerHTML = `<style>${css}</style>${finalHtml}`;

    // Enable events for the sidebar content
    sidebarContainer.style.pointerEvents = 'auto';
    sidebarContainer.style.background = '#f0f2f5'; // WhatsApp logic bg color

    // Adjust WhatsApp Layout (Robust Resizing)
    function adjustLayout() {
        const appWrapper = document.getElementById('app');
        if (appWrapper) {
            // Target the main container. Usually the direct child of #app 
            // or the element with class .app-wrapper-web
            const mainContent = appWrapper.firstElementChild;
            if (mainContent) {
                mainContent.style.width = 'calc(100% - 350px)';
                mainContent.style.minWidth = 'auto'; // Prevent min-width issues
                mainContent.style.transition = 'width 0.3s ease';
            }
        }
    }

    // Run initially
    adjustLayout();

    // Keep enforcing it in case WhatsApp resets it (SPA navigation)
    setInterval(adjustLayout, 2000);

    // Bind Actions
    bindEvents();

    // Start Observer
    startObserver();

    // Force Initial Check
    setTimeout(checkActiveChat, 1000);
}

// --- DOM OBSERVER ---
function startObserver() {
    const observer = new MutationObserver((mutations) => {
        checkActiveChat();
    });
    // Observer robustly
    const main = document.getElementById('main') || document.body;
    observer.observe(main, { childList: true, subtree: true });

    setInterval(checkActiveChat, 2000);
}

// Helper to extract React Fiber Data
function getReactInstance(dom) {
    for (const key in dom) {
        if (key.startsWith("__reactFiber")) {
            return dom[key];
        }
    }
    return null;
}

function findJidInFiber(fiber) {
    // DFS traversal to find 'jid' or 'id' looking like '12345@c.us'
    // Depth limit to avoid infinite loops
    let queue = [{ node: fiber, depth: 0 }];
    let visited = new Set();

    while (queue.length > 0) {
        const { node, depth } = queue.shift();
        if (!node || depth > 25 || visited.has(node)) continue;
        visited.add(node);

        const props = node.memoizedProps;
        if (props) {
            // Check common patterns for chat/contact objects
            if (props.jid && typeof props.jid === 'string') return props.jid; // Direct jid
            if (props.id && typeof props.id === 'object' && props.id.user) return props.id.user; // {user: "5511...", server: "c.us"}

            // Check formattedUser or similar
            // if (props.data && props.data.id && props.data.id.user) return props.data.id.user;
        }

        if (node.child) queue.push({ node: node.child, depth: depth + 1 });
        if (node.sibling) queue.push({ node: node.sibling, depth: depth + 1 });
    }
    return null;
}

function checkActiveChat() {
    try {
        // Robust Main Panel Detection
        const mainPanel = document.getElementById('main') || document.querySelector('div[role="main"]');
        if (!mainPanel) {
            if (currentPhone || currentLeadId) {
                // Wait a bit before clearing to handle quick reloads/transitions
            }
            return;
        }

        const mainHeader = mainPanel.querySelector('header');
        if (!mainHeader) return;

        let name = null;
        let phone = null;
        let detectionMethod = null;

        // Helper for text validation
        const isInvalidText = (t) => {
            if (!t) return true;
            const lower = t.toLowerCase();
            return (lower.includes('online') ||
                lower.includes('digitando') ||
                lower.includes('gravando') ||
                lower.includes('visto por') ||
                lower.includes('clique aqui') ||
                lower.includes('clique para') ||
                lower.includes('conta comercial') ||
                lower.includes('business account') ||
                lower.includes('dados do contato') ||
                lower.includes('grupo') ||
                t.length < 2);
        };

        // --- LAYER 1: JID (React Fiber) ---
        const roots = [
            mainHeader,
            mainHeader.querySelector('img'),
            mainHeader.querySelector('div[role="button"]')
        ];

        for (const root of roots) {
            if (!root) continue;
            const fiber = getReactInstance(root);
            if (fiber) {
                const jid = findJidInFiber(fiber);
                if (jid) {
                    const clean = jid.replace('@c.us', '').replace('@g.us', '');
                    if (clean.match(/^\d+$/) && clean.length >= 10) {
                        phone = clean;
                        detectionMethod = 'JID';
                        break;
                    }
                }
            }
        }

        // --- LAYER 2: WA.ME Link (Fallback) ---
        if (!phone) {
            const links = mainHeader.querySelectorAll('a[href*="wa.me"]');
            for (const link of links) {
                const href = link.getAttribute('href');
                const match = href.match(/wa\.me\/(\d+)/);
                if (match && match[1]) {
                    phone = match[1];
                    detectionMethod = 'WA.ME';
                    break;
                }
            }
        }

        // --- LAYER 3: Name & Visual Scraping (Last Resort) ---

        // 1. Get Name via Title
        const titleSpan = mainHeader.querySelector('span[title]');
        if (titleSpan) {
            const possibleName = titleSpan.getAttribute('title');
            if (!isInvalidText(possibleName)) {
                name = possibleName;
            }
        }

        // 2. Fallback: Scan all spans
        if (!name) {
            const infoBlock = mainHeader.querySelector('div[role="button"]');
            if (infoBlock) {
                const spans = infoBlock.querySelectorAll('span');
                for (const span of spans) {
                    const text = span.innerText;
                    if (isInvalidText(text)) continue;

                    name = text;
                    break;
                }
            }
        }

        // 3. Try to extract phone from detected name
        if (!phone && name && name.match(/^\+?\d[\d\s-]{8,}$/)) {
            const p = name.replace(/\D/g, '');
            if (p.length >= 10) {
                phone = p;
                detectionMethod = 'NAME_PARSE';
            }
        }

        // --- UX Updates ---
        if (isInvalidText(name) || name === "WhatsApp") name = null;

        // Dispatch
        if (phone && phone !== currentPhone) {
            currentPhone = phone;
            console.log(`NW: Identified via ${detectionMethod}: ${phone}`);
            updateSidebar(name || phone, phone);
        } else if (name && !phone && name !== "Contato") {
            if (currentPhone !== name) {
                currentPhone = name;
                console.log(`NW: Name identified (No Phone): ${name}`);
                updateSidebar(name, null, name);
            }
        }

    } catch (err) {
        console.error("NW: checkActiveChat error", err);
    }
}

// --- SIDEBAR UI LOGIC ---
const getEl = (id) => shadowRoot.getElementById(id);

async function updateSidebar(name, phone, searchName = null) {
    showState('loading');
    getEl('nw-contact-name').textContent = name || "Desconhecido";

    if (!phone && !searchName) return;

    const mysend = {
        action: "GET_CONTACT",
        phone: phone,
        name: searchName // Pass name for fallback search
    };

    const response = await chrome.runtime.sendMessage(mysend);

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
        getEl('nw-new-phone').value = phone || ""; // Allow empty phone if not found
        loadPipelines(null, 'nw-new-stage');

        // UX: Show identification status (maybe in placeholder or helper text)
        getEl('nw-new-phone').placeholder = phone ? "Detectado" : "Digite o telefone (Obrigatório)";
        if (!phone) getEl('nw-new-phone').focus();
    } else {
        // Existing Contact
        const data = response.data;
        currentLeadId = data.id;

        showState('contact');
        getEl('nw-contact-name').textContent = data.name;
        getEl('nw-contact-phone').textContent = data.phone;
        getEl('nw-contact-status').textContent = data.status;
        getEl('nw-input-notes').value = data.notes || '';
        getEl('nw-input-tags').value = data.bant_need || '';

        loadPipelines(data.pipeline_stage_id);
    }
}

function showState(state) {
    ['idle', 'loading', 'new', 'contact'].forEach(s => {
        const el = getEl(`nw-state-${s}`);
        if (el) el.classList.add('hidden');
    });
    const active = getEl(`nw-state-${state}`);
    if (active) active.classList.remove('hidden');
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

function bindEvents() {
    // Create Lead
    getEl('nw-btn-create').addEventListener('click', async () => {
        showState('loading');
        const name = getEl('nw-new-name').value;
        const phone = getEl('nw-new-phone').value;
        const stageId = getEl('nw-new-stage').value;

        const res = await chrome.runtime.sendMessage({
            action: "CREATE_LEAD",
            data: { name, phone, stage_id: stageId || null }
        });

        if (res.success) {
            updateSidebar(name, phone);
        } else {
            alert("Erro ao criar lead: " + (res.error || 'Unknown'));
            showState('new');
        }
    });

    // Save Changes
    getEl('nw-btn-save').addEventListener('click', async () => {
        if (!currentLeadId) return;

        const btn = getEl('nw-btn-save');
        const originalText = btn.textContent;
        btn.textContent = "Salvando...";

        const notes = getEl('nw-input-notes').value;
        const tags = getEl('nw-input-tags').value;
        const stageId = getEl('nw-input-stage').value;

        const res = await chrome.runtime.sendMessage({
            action: "UPDATE_LEAD",
            id: currentLeadId,
            data: {
                notes: notes,
                bant_need: tags, // Using bant_need as tags for now
                pipeline_stage_id: stageId
            }
        });

        if (res.success) {
            btn.textContent = "Salvo!";
            setTimeout(() => btn.textContent = originalText, 2000);
        } else {
            btn.textContent = "Erro";
            alert("Erro ao salvar: " + res.error);
        }
    });

    // CRM Link
    getEl('nw-link-crm').addEventListener('click', (e) => {
        if (currentLeadId) {
            e.target.href = `https://north-way-2-0.vercel.app/leads/${currentLeadId}`;
        }
    });
}


// Start
setTimeout(init, 3000);
