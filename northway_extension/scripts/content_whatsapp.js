// NorthWay Content Script
let shadowRoot = null;
let currentPhone = null;
let currentLeadId = null;

// --- INITIALIZATION ---
async function init() {
    console.log("NW: Initializing...");

    // Custom container to hold the sidebar
    let sidebarContainer = document.getElementById('northway-sidebar-host');
    if (!sidebarContainer) {
        sidebarContainer = document.createElement('div');
        sidebarContainer.id = 'northway-sidebar-host';
        document.body.appendChild(sidebarContainer);
    }

    // Fixed positioning to float on top right
    sidebarContainer.style.position = 'fixed';
    sidebarContainer.style.top = '0';
    sidebarContainer.style.right = '0';
    sidebarContainer.style.width = '350px';
    sidebarContainer.style.height = '100%';
    sidebarContainer.style.zIndex = '99999'; // High Z-Index to stay on top
    sidebarContainer.style.pointerEvents = 'none'; // Passthrough initially
    sidebarContainer.style.boxShadow = '-2px 0 5px rgba(0,0,0,0.1)';

    // Create Shadow DOM if not exists
    if (!shadowRoot) {
        shadowRoot = sidebarContainer.attachShadow({ mode: 'open' });
    }

    // Load HTML & CSS
    const htmlUrl = chrome.runtime.getURL('scripts/sidebar.html');
    const cssUrl = chrome.runtime.getURL('scripts/sidebar.css');

    try {
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

        // Bind Actions
        bindEvents();

        // Start Observer
        startObserver();
        adjustLayout();

        // Force Initial Check
        setTimeout(checkActiveChat, 1000);
        setInterval(adjustLayout, 2000);

    } catch (e) {
        console.error("NW: Init failed", e);
    }
}

// Adjust WhatsApp Layout (Robust Resizing)
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

// --- DOM OBSERVER ---
function startObserver() {
    const observer = new MutationObserver((mutations) => {
        checkActiveChat();
    });
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

// --- DETECTION LOGIC ---
function checkActiveChat() {
    try {
        let name = null;
        let phone = null;
        let isGroup = false;

        const mainPanel = document.getElementById('main') || document.querySelector('div[role="main"]');

        if (mainPanel) {
            const header = mainPanel.querySelector('header');
            if (header) {
                // 1. Fiber Analysis (Primary Source of Truth for ID)
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

                // 2. Precise Name Extraction (Targeting Title Only)
                // The header usually contains a clickable info div. Inside, Title is first, Subtitle is second.
                const infoButton = header.querySelector('div[role="button"]');
                if (infoButton) {
                    // Get all text containers that might be title/subtitle
                    // Title usually has [dir="auto"] and is the first significant text element
                    // Subtitle (participants) is usually the second one
                    const textElements = Array.from(infoButton.querySelectorAll('span[dir="auto"]'));

                    if (textElements.length > 0) {
                        // First element is usually the Name
                        name = textElements[0].innerText;

                        // Check second element (Subtitle) for Group Indicators
                        if (textElements.length > 1) {
                            const subtitle = textElements[1].innerText;
                            // Strong heuristic: If subtitle contains multiple commas, it's a participant list -> Group
                            if (subtitle.includes(',') && subtitle.length > 15) {
                                isGroup = true;
                            }
                            // Or specific keywords
                            if (subtitle.toLowerCase().includes('participante') || subtitle.toLowerCase().includes('group') || subtitle.toLowerCase().includes('clique para dados')) {
                                isGroup = true;
                            }
                        }
                    }
                }

                // 3. Fallback: If Name looks like a giant list of names (commas), we grabbed the wrong thing or it's a group without title?
                if (name && name.includes(',') && name.length > 50) {
                    // This is likely the participant list mistakenly grabbed as name
                    // Trigger group mode but try to find a better name if possible, or default to "Grupo"
                    isGroup = true;
                    name = "Grupo (Nome não detectado)";
                }

                // 4. Fallback Phone via Regex (Unsaved Contact)
                if (!phone && name && name.match(/^\+?\d[\d\s-]{10,}$/)) {
                    const clean = name.replace(/\D/g, '');
                    if (clean.length >= 10) phone = clean;
                }
            }
        }

        // --- DRAWER OVERRIDE ---
        const drawerTitle = Array.from(document.querySelectorAll('span')).find(el =>
            ['Dados do contato', 'Contact info', 'Dados da empresa', 'Business info', 'Dados do grupo', 'Group info'].includes(el.innerText)
        );

        if (drawerTitle) {
            const container = drawerTitle.closest('div._aigv') || drawerTitle.closest('section');
            if (drawerTitle.innerText.match(/group|grupo/i)) {
                isGroup = true;
                if (container) {
                    const h2 = container.querySelector('h2') || container.querySelector('span[dir="auto"]'); // h2 is safer in drawer
                    if (h2) name = h2.innerText;
                }
            } else {
                // Contact Drawer
                // Try to recover phone from drawer image if header failed (Saved Contact case)
                if (!phone && container) {
                    const dImg = container.querySelector('img');
                    if (dImg) {
                        const f = getReactInstance(dImg);
                        if (f) {
                            const j = findJidInFiber(f);
                            if (j) {
                                const clean = j.replace(/@.+/, '');
                                if (clean.match(/^\d+$/) && clean.length >= 10) phone = clean;
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
                console.log("NW: Group Detected", name);
                showState('group');
                getEl('nw-group-name').textContent = name || "Grupo";
            }
        } else if (phone && phone !== currentPhone) {
            currentPhone = phone;
            console.log(`NW: Phone Detected: ${phone}`);
            updateSidebar(name || phone, phone);
        } else if (name && !phone && !name.includes("WhatsApp") && name !== "Contato") {
            if (currentPhone !== name) {
                currentPhone = name;
                console.log(`NW: Saved Contact Detected (No Phone): ${name}`);
                updateSidebar(name, null, name);
            }
        }

    } catch (err) {
        console.error("NW: checkActiveChat error", err);
    }
}

// --- SIDEBAR UI LOGIC ---
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

    const mysend = {
        action: "GET_CONTACT",
        phone: phone,
        name: searchName
    };

    try {
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
            getEl('nw-new-phone').value = phone || "";
            loadPipelines(null, 'nw-new-stage');

            getEl('nw-new-phone').placeholder = phone ? "Detectado" : "Digite o telefone";
        } else {
            // Existing Contact
            renderContact(response.data);
        }
    } catch (e) {
        console.log("Error updating sidebar", e);
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

// --- GROUP EXPORT LOGIC ---
async function scrapeGroupContacts(groupName) {
    // 1. Open Group Info
    const header = document.querySelector('header');
    if (!header) return alert("Erro: Cabeçalho não encontrado.");
    header.click();

    await new Promise(r => setTimeout(r, 1000));

    // 2. Find List
    const drawer = document.querySelector('div._aigv') || document.querySelector('section');
    if (!drawer) return alert("Erro: Painel lateral não abriu.");

    const spans = Array.from(drawer.querySelectorAll('span'));
    const participantHeader = spans.find(s => s.innerText.match(/\d+ participantes/i) || s.innerText.match(/\d+ participants/i));

    if (!participantHeader) return alert("Erro: Lista de participantes não encontrada.");

    const clickableBlock = participantHeader.closest('div[role="button"]');
    if (clickableBlock) clickableBlock.click();

    await new Promise(r => setTimeout(r, 1500));

    // Find Scroller
    const scrollers = Array.from(document.querySelectorAll('div')).filter(d => d.scrollHeight > 500 && (d.style.overflowY === 'auto' || d.classList.contains('overflow-y-auto')));
    const scroller = scrollers[scrollers.length - 1];

    if (!scroller) return alert("Erro: Área de rolagem não detectada.");

    // 3. Scrape
    const uniqueContacts = new Map();
    const progressText = getEl('nw-export-status');
    getEl('nw-export-progress').classList.remove('hidden');

    let previousHeight = 0;
    let attempts = 0;
    let stats = { total: 0, withPhone: 0, withoutPhone: 0 };

    while (attempts < 5) {
        scroller.scrollTop = scroller.scrollHeight;
        await new Promise(r => setTimeout(r, 800));

        const rows = scroller.querySelectorAll('div[role="listitem"]');
        rows.forEach(row => {
            const text = row.innerText.split('\n');
            let rawName = text[0];
            let rawPhone = "";
            let screenName = "";
            let isAdmin = row.innerText.toLowerCase().includes('admin') || row.innerText.toLowerCase().includes('administrador');

            if (rawName.match(/^\+?\d[\d\s-]{8,}$/)) {
                rawPhone = rawName.replace(/\D/g, '');
                screenName = "Contato WhatsApp";
            } else {
                screenName = rawName;
            }

            if (screenName === "Você" || screenName === "You") return;

            const key = rawPhone || screenName;
            if (!uniqueContacts.has(key)) {
                if (rawPhone) stats.withPhone++; else stats.withoutPhone++;
                uniqueContacts.set(key, { name: screenName, phone: rawPhone, group: groupName, isAdmin });
            }
        });

        if (scroller.scrollHeight === previousHeight) attempts++;
        else {
            previousHeight = scroller.scrollHeight;
            attempts = 0;
        }

        stats.total = uniqueContacts.size;
        progressText.innerHTML = `Extraindo... <b>${stats.total}</b> (📱 ${stats.withPhone} | 👤 ${stats.withoutPhone})`;
    }

    downloadCSV(Array.from(uniqueContacts.values()));
    getEl('nw-export-progress').classList.add('hidden');
}

function downloadCSV(contacts) {
    const header = ['Nome', 'Email', 'Telefone', 'Origem', 'Interesse', 'Admin', 'Observações'];
    const rows = contacts.map(c => {
        let p = c.phone || c.name.replace(/\D/g, '');
        if (p.startsWith('55') && p.length > 10) p = p.substring(2);
        let fmtPhone = p;
        if (p.length >= 10) fmtPhone = `(${p.substring(0, 2)}) ${p.substring(2, 7)}-${p.substring(7)}`;

        const obs = `Contato extraído do grupo '${c.group}' em ${new Date().toLocaleDateString()}`;

        return [
            c.name || "Contato WhatsApp",
            "",
            fmtPhone,
            `Grupo WhatsApp - ${c.group}`,
            "A definir",
            c.isAdmin ? "Sim" : "Não",
            obs
        ].map(f => `"${f || ''}"`).join(';');
    });

    const csvContent = "\uFEFF" + [header.join(';'), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `contatos_grupo_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}


function bindEvents() {
    // Create Lead
    getEl('nw-btn-create').addEventListener('click', async () => {
        showState('loading');
        const name = getEl('nw-new-name').value;
        const phone = getEl('nw-new-phone').value;
        const email = getEl('nw-new-email').value;
        const interest = getEl('nw-new-interest').value;
        const notes = getEl('nw-new-notes').value;
        const stageId = getEl('nw-new-stage').value;

        const res = await chrome.runtime.sendMessage({
            action: "CREATE_LEAD",
            data: { name, phone, email, notes, bant_need: interest, pipeline_stage_id: stageId || null }
        });

        if (res.success) renderContact(res.lead);
        else { alert("Erro: " + res.error); showState('new'); }
    });

    // Save Changes
    getEl('nw-btn-save').addEventListener('click', async () => {
        if (!currentLeadId) return;
        const btn = getEl('nw-btn-save');
        btn.textContent = "Salvando...";
        const notes = getEl('nw-input-notes').value;
        const tags = getEl('nw-input-tags').value;
        const stageId = getEl('nw-input-stage').value;

        const res = await chrome.runtime.sendMessage({
            action: "UPDATE_LEAD",
            id: currentLeadId,
            data: { notes, bant_need: tags, pipeline_stage_id: stageId }
        });

        if (res.success) { btn.textContent = "Salvo!"; setTimeout(() => btn.textContent = "Salvar Alterações", 2000); }
        else { btn.textContent = "Erro"; alert("Erro: " + res.error); }
    });

    // CRM Link
    getEl('nw-link-crm').addEventListener('click', (e) => {
        if (currentLeadId) e.target.href = `https://north-way-2-0.vercel.app/leads/${currentLeadId}`;
    });

    // Group Export
    const exportBtn = getEl('nw-btn-export');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            const groupName = getEl('nw-group-name').textContent;
            scrapeGroupContacts(groupName);
        });
    }
}

// Start
setTimeout(init, 3000);
