// NorthWay Content Script - Robust Version
let shadowRoot = null;
let currentPhone = null;
let currentLeadId = null;

// --- INITIALIZATION ---
async function init() {
    console.log("NW: Initializing...");

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

async function scrapeGroupContacts(groupName) {
    // Basic scrape implementation specific to request
    alert("Iniciando extração...");
    // ... Implement logic similar to before if needed, keeping it simple for now to avoid errors ...
    // Re-adding previous logic briefly:
    const header = document.querySelector('header');
    if (header) header.click();
    await new Promise(r => setTimeout(r, 1000));

    // ... complete scrape logic ...
    // For now, let's just alert ensuring the button works, full scrape was in previous version
    // If user needs scrape, I will re-add the full function block to avoid file bloat in this quick fix
    // Actually, I should include the full scrape logic or the user will complain again.
    // Appending scrape logic below...

    // Scrape Logic Redux
    const drawer = document.querySelector('div._aigv') || document.querySelector('section');
    if (!drawer) return alert("Erro: Painel não abriu");

    // Click 'participants'
    const participantHeader = Array.from(drawer.querySelectorAll('span')).find(s => s.innerText.match(/participan/i));
    if (participantHeader) participantHeader.closest('div[role="button"]').click();

    await new Promise(r => setTimeout(r, 1000));

    // Scroller
    const scrollers = Array.from(document.querySelectorAll('div')).filter(d => d.scrollHeight > 500);
    const scroller = scrollers[scrollers.length - 1];
    if (!scroller) return alert("Erro rolagem");

    // Loop
    const unique = new Map();
    let prevH = 0;
    while (true) {
        scroller.scrollTop = scroller.scrollHeight;
        await new Promise(r => setTimeout(r, 800));
        const rows = scroller.querySelectorAll('div[role="listitem"]');
        rows.forEach(r => {
            const txt = r.innerText.split('\n');
            unique.set(txt[0], { name: txt[0], phone: txt[0].match(/\d/) ? txt[0].replace(/\D/g, '') : '' });
        });
        if (scroller.scrollHeight === prevH) break;
        prevH = scroller.scrollHeight;
    }

    // Download
    const csv = "Nome,Telefone\n" + Array.from(unique.values()).map(c => `${c.name},${c.phone}`).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = "group_contacts.csv";
    a.click();
}


function bindEvents() {
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
            const name = getEl('nw-group-name').textContent;
            scrapeGroupContacts(name);
        });
    }
}

setTimeout(init, 3000);
