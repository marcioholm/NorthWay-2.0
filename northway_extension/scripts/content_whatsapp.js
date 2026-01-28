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

// --- GROUP EXPORT LOGIC ---
// --- GROUP EXPORT LOGIC ---
async function scrapeGroupContacts(groupName) {
    const progressText = getEl('nw-export-status');
    const progressBar = getEl('nw-export-progress');

    if (progressBar) progressBar.classList.remove('hidden');
    if (progressText) progressText.textContent = "Localizando painel...";

    // 1. Helper: Robust Container Finder
    const findContainer = () => {
        // Strategy A: Look for the Side Panel (usually a <section>)
        const sections = Array.from(document.querySelectorAll('section, div[role="dialog"]'));

        for (const section of sections) {
            // Check visibility
            if (section.offsetParent === null) continue;

            const text = section.innerText.toLowerCase();
            // Keywords that indicate a Group Info panel or Participant List
            const hasKeyword = text.includes('dados do grupo') ||
                text.includes('group info') ||
                text.match(/\d+ membros/) ||
                text.match(/\d+ participants/) ||
                text.match(/\d+ participantes/);

            if (hasKeyword) {
                // Return this section as the container
                return section;
            }
        }
        return null;
    };

    let container = findContainer();

    // 2. Open Panel if NOT found
    if (!container) {
        if (progressText) progressText.textContent = "Abrindo painel do grupo...";
        const header = document.querySelector('header');
        if (header) {
            // Click title to open
            const titleClick = header.querySelector('div[role="button"]') || header.querySelector('span[dir="auto"]');
            if (titleClick) titleClick.click();
            else header.click();
        }

        // Polling wait
        for (let i = 0; i < 25; i++) {
            await new Promise(r => setTimeout(r, 400));
            container = findContainer();
            if (container) break;
        }
    }

    if (!container) {
        if (progressBar) progressBar.classList.add('hidden');
        return alert("Não foi possível detectar a lista de participantes.\n\nPor favor, ABRA A LISTA DE MEMBROS manualmente e tente novamente.");
    }

    // 3. Drill down to the Participant List
    if (progressText) progressText.textContent = "Acessando lista de membros...";

    // Sometimes the container is the main info panel, but the list is hidden behind "Check All"
    // Check for "View All" / "Ver tudo" button
    const viewAllBtn = Array.from(container.querySelectorAll('div[role="button"]'))
        .find(b => b.innerText.match(/ver tudo|view all|mais|more/i));

    if (viewAllBtn) {
        viewAllBtn.click();
        await new Promise(r => setTimeout(r, 1500));
        // Re-detect container as it might have switched to a modal
        container = document.querySelector('div[role="dialog"]') || container;
    }

    // 4. Find the Scrollable Area
    // The list is always in a div with overflow-y: auto/scroll
    let scroller = Array.from(container.querySelectorAll('div')).find(div => {
        const style = window.getComputedStyle(div);
        return (style.overflowY === 'auto' || style.overflowY === 'scroll') && div.scrollHeight > 50;
    });

    if (!scroller) {
        // Fallback: The container itself might be the scroller
        const style = window.getComputedStyle(container);
        if (style.overflowY === 'auto' || style.overflowY === 'scroll') scroller = container;
    }

    if (!scroller) return alert("Erro: Lista de rolagem não encontrada. Abra a lista completa de membros.");

    // 5. Scrape Logic
    const uniqueContacts = new Map();
    let noChangeCount = 0;
    let prevHeight = 0;

    // Scroll top first
    scroller.scrollTop = 0;

    while (noChangeCount < 3) {
        // Scroll down
        scroller.scrollTop = scroller.scrollHeight;
        await new Promise(r => setTimeout(r, 1200)); // Wait for lazy load

        // Scrape visible items
        // WhatsApp list items usually have role="listitem" or specific structure
        const items = container.querySelectorAll('div[role="listitem"]');

        // If no listitems found, try generic divs with text
        const rows = items.length > 0 ? items : container.querySelectorAll('div._Aigv'); // Fallback class if needed, or query direct children

        items.forEach(item => {
            const lines = item.innerText.split('\n');
            if (lines.length < 1) return;

            let name = lines[0];
            let secondary = lines[1] || "";
            let phone = "";

            // Extract phone info
            if (name.match(/^\+?\d[\d\s-]{8,}$/)) {
                // Name IS phone
                phone = name.replace(/\D/g, '');
                name = "Contato WhatsApp"; // Placeholder for unsaved
                // Try to grab nickname from secondary line (~Nick)
                if (secondary.includes('~')) name = secondary.replace(/[~]/g, '').trim();
            } else {
                // Name is likely a contact name
                // Phone is usually NOT visible for saved contacts in the list unless clicked
                // BUT, user requires phone. 
                // We will save what we have. If secondary looks like phone, grab it.
                if (secondary.match(/^\+?\d[\d\s-]{8,}$/)) phone = secondary.replace(/\D/g, '');
            }

            if (name === "Você" || name === "You") return;
            if (phone && !phone.startsWith('55') && phone.length <= 11) phone = '55' + phone;

            const key = phone || name;

            if (!uniqueContacts.has(key)) {
                uniqueContacts.set(key, {
                    name: name.replace(/"/g, ''),
                    phone: phone,
                    origin: `Grupo: ${groupName}`,
                    date: new Date().toLocaleDateString()
                });
                if (progressText) progressText.innerText = `Extraindo... ${uniqueContacts.size}`;
            }
        });

        if (scroller.scrollHeight === prevHeight) noChangeCount++;
        else {
            prevHeight = scroller.scrollHeight;
            noChangeCount = 0;
        }
    }

    // 6. Generate & Download CSV
    const csvHeader = ["Nome", "Email", "Telefone", "Origem", "Interesse", "Observações"];
    const csvRows = Array.from(uniqueContacts.values()).map(c => {
        return [
            `"${c.name}"`,
            `""`,
            `"${c.phone}"`,
            `"${c.origin}"`,
            `"A definir"`,
            `"Extraído em ${c.date}"`
        ].join(',');
    });

    const csvContent = "\uFEFF" + csvHeader.join(',') + "\n" + csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `grupo_${groupName.replace(/\s/g, '_')}_${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (progressText) progressText.textContent = `Sucesso! ${uniqueContacts.size} contatos baixados.`;
    setTimeout(() => { if (progressBar) progressBar.classList.add('hidden'); }, 4000);
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
