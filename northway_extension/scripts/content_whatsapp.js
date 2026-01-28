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

// --- GROUP EXPORT LOGIC ---
async function scrapeGroupContacts(groupName) {
    const progressText = getEl('nw-export-status');
    const progressBar = getEl('nw-export-progress');
    const fill = getEl('nw-progress-fill');

    if (progressBar) progressBar.classList.remove('hidden');
    if (progressText) progressText.textContent = "Abrindo dados do grupo...";

    // 1. Open Group Info
    const header = document.querySelector('header');
    if (!header) return alert("Erro: Cabeçalho não encontrado.");

    // Try click specific clickable div in header first
    const titleClickable = header.querySelector('div[role="button"]');
    if (titleClickable) titleClickable.click();
    else header.click();

    await new Promise(r => setTimeout(r, 2000));

    // 2. Find Drawer
    // Flexible search for the side panel
    let drawer = null;
    const sidePanels = document.querySelectorAll('div._aigv, section');
    // Search reversed as the active one is usually last
    for (let i = sidePanels.length - 1; i >= 0; i--) {
        const p = sidePanels[i];
        if (p.innerText.match(/dados do grupo|group info|participa/i) && p.offsetHeight > 400) {
            drawer = p;
            break;
        }
    }

    if (!drawer) {
        if (progressBar) progressBar.classList.add('hidden');
        return alert("Erro: Painel não abriu. Desbloqueie popups e tente novamente.");
    }

    // 3. Find "Participants" Link/Section
    if (progressText) progressText.textContent = "Buscando lista de participantes...";

    // Scroll drawer slightly to ensure participants section is loaded
    const drawerScroller = drawer.querySelector('div[class*="overflow"]');
    if (drawerScroller) drawerScroller.scrollTop = 400;

    await new Promise(r => setTimeout(r, 1500));

    // Look for "View all" or clickable participant count header
    // The text varies: "123 participants", "123 participantes"
    const spans = Array.from(drawer.querySelectorAll('span'));
    const partHeader = spans.find(s => s.innerText.match(/\d+ participating|\d+ participantes/i));

    if (partHeader) {
        const btn = partHeader.closest('div[role="button"]');
        if (btn) {
            btn.click();
            await new Promise(r => setTimeout(r, 2000));
        }
    }

    // 4. Find the Modal/List Scroller
    // If a modal opened (View All), it's usually role=dialog
    const modal = document.querySelector('div[role="dialog"]');
    let scroller = null;

    if (modal) {
        scroller = Array.from(modal.querySelectorAll('div')).find(d => getComputedStyle(d).overflowY === 'auto' || d.style.overflowY === 'auto');
    }

    // If no modal, check inside drawer (for small groups)
    if (!scroller) {
        // Drawer internal list often matches specific classes or just overflow-y
        scroller = Array.from(drawer.querySelectorAll('div')).find(d => getComputedStyle(d).overflowY === 'auto' && d.scrollHeight > 300);
    }

    if (!scroller && drawerScroller) scroller = drawerScroller; // Fallback

    if (!scroller) return alert("Erro: Lista não encontrada.");

    // 5. Scrape Loop
    const uniqueContacts = new Map();
    let previousHeight = 0;
    let noChangeCount = 0;

    while (noChangeCount < 3) {
        scroller.scrollTop = scroller.scrollHeight;
        await new Promise(r => setTimeout(r, 1200));

        const items = document.querySelectorAll('div[role="listitem"]');
        items.forEach(row => {
            const text = row.innerText.split('\n');
            // WhatsApp rows: 
            // 1. Name (or Phone if unsaved)
            // 2. Status / Info (Optional)

            let name = text[0] || "Sem Nome";
            let phone = "";
            let extra = text[1] || "";

            // Heuristic: Check if 'name' is actually a phone
            if (name.match(/\d{4}.?\d{4}/) && name.length < 20) {
                // It's a phone number
                phone = name.replace(/\D/g, '');
                name = "Contato WhatsApp"; // Placeholder
                // Sometimes the 'status' is '~Notify_Name', we can grab that
                if (extra.includes('~')) name = extra.replace('~', '');
            } else {
                // It's a saved contact name
                // We CANNOT get the phone from saved contacts easily on Web unless we click them.
                // But for the export requirement, we leave blank or put name as fallback key?
                // Wait, user wants phone. If we abuse the "drag" trick or Fiber we could, but let's be safe.
                // For now, if no phone visible, we leave blank but add to list.
                // Actually, let's try to grab phone from 'extra' if it looks like one (rare)
            }

            // Ignore You
            if (name === "You" || name === "Você") return;

            // Clean phone (add country code if missing/guess)
            if (phone && !phone.startsWith('55') && phone.length <= 11) phone = '55' + phone;

            const key = phone || name;
            if (!uniqueContacts.has(key)) {
                uniqueContacts.set(key, {
                    name: name.replace(/"/g, ''), // Sanitize quotes
                    phone: phone,
                    origin: `Grupo WhatsApp - ${groupName}`,
                    interest: "A definir",
                    obs: `Extraído em ${new Date().toLocaleDateString()}`
                });

                if (progressText) progressText.innerText = `Extraindo... ${uniqueContacts.size}`;
            }
        });

        if (scroller.scrollHeight === previousHeight) {
            noChangeCount++;
        } else {
            previousHeight = scroller.scrollHeight;
            noChangeCount = 0;
        }
    }

    // 6. Download (Strict CSV Format)
    // Nome,Email,Telefone,Origem,Interesse,Observações
    const header = ["Nome", "Email", "Telefone", "Origem", "Interesse", "Observações"];
    const rows = Array.from(uniqueContacts.values()).map(c => {
        return [
            `"${c.name}"`,
            `""`, // Email empty
            `"${c.phone}"`,
            `"${c.origin}"`,
            `"${c.interest}"`,
            `"${c.obs}"`
        ].join(',');
    });

    const csvContent = "\uFEFF" + header.join(',') + "\n" + rows.join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `grupo_${groupName.replace(/\s/g, '_')}_${new Date().getTime()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (progressText) progressText.textContent = `Concluído! ${uniqueContacts.size} contatos.`;
    setTimeout(() => { if (progressBar) progressBar.classList.add('hidden'); }, 3000);
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
