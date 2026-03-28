/**
 * ZapWay Main Entry Point
 */

let chatObserver = null;
let intervalLayout = null;

async function bootstrap() {
    nwLog("Bootstrapping... Checking Auth.");
    try {
        const response = await sendMsg({ action: "CHECK_AUTH" });
        if (response && response.token) {
            nwLog("Authenticated. Initializing Sidebar.");
            init();
        } else {
            nwLog("Not authenticated. Sidebar will not load.");
            unmount();
        }
    } catch (e) {
        nwLog("Auth check failed", e);
    }

    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.authToken) {
            if (changes.authToken.newValue) {
                if (!document.getElementById('northway-sidebar-host')) init();
            } else {
                unmount();
            }
        }
    });
}

async function init() {
    nwLog("NW: Initializing...");
    
    let sidebarContainer = document.getElementById('northway-sidebar-host') || document.createElement('div');
    sidebarContainer.id = 'northway-sidebar-host';
    sidebarContainer.style.cssText = `
        position: fixed; top: 0; right: 0; width: ${SIDEBAR_WIDTH}px; height: 100%;
        z-index: 99999; pointer-events: none; background: transparent;
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: -2px 0 5px rgba(0,0,0,0.1);
    `;
    
    if (!sidebarContainer.parentElement) document.body.appendChild(sidebarContainer);
    if (!NWState.shadowRoot) NWState.shadowRoot = sidebarContainer.attachShadow({ mode: 'open' });

    const ts = Date.now();
    const [html, css] = await Promise.all([
        fetch(chrome.runtime.getURL(`scripts/sidebar.html?t=${ts}`)).then(r => r.text()),
        fetch(chrome.runtime.getURL(`scripts/sidebar.css?t=${ts}`)).then(r => r.text())
    ]);

    NWState.shadowRoot.innerHTML = `<style>${css}</style>${html.replace(/__MSG_@@extension_id__/g, chrome.runtime.id)}`;
    sidebarContainer.style.pointerEvents = 'auto';

    bindEvents();
    startObserver();
    adjustLayout();
    
    BroadcastEngine.init();
    AutomationEngine.startPolling();
    loadTemplates();

    createToggleButton();
    intervalLayout = setInterval(adjustLayout, 2000);

    // Initial check
    setTimeout(checkActiveChat, 1000);
}

function startObserver() {
    nwLog("Starting App Observer...");
    const appEl = document.getElementById('app');
    if (!appEl) {
        // Retry logic: wait for #app to appear
        const bodyObs = new MutationObserver(() => {
            if (document.getElementById('app')) {
                bodyObs.disconnect();
                startObserver();
            }
        });
        bodyObs.observe(document.body, { childList: true });
        return;
    }

    if (chatObserver) chatObserver.disconnect();
    
    let debounceTimer = null;
    chatObserver = new MutationObserver(() => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(checkActiveChat, 300);
    });

    chatObserver.observe(appEl, {
        childList: true, subtree: true, attributes: true,
        attributeFilter: ['class', 'data-id', 'aria-label']
    });
}

function createToggleButton() {
    if (document.getElementById('nw-toggle-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'nw-toggle-btn';
    btn.innerHTML = '‹';
    btn.style.cssText = `
        position: fixed; top: 50%; right: ${SIDEBAR_WIDTH}px; transform: translateY(-50%);
        z-index: 100000; width: 22px; height: 56px; background: #1a0b0e; color: #ff1f4b;
        border: 1px solid rgba(255,255,255,0.1); border-right: none; border-radius: 8px 0 0 8px;
        cursor: pointer; display: flex; align-items: center; justify-content: center;
        transition: transform 0.3s ease, right 0.3s ease; box-shadow: -3px 0 10px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(btn);

    btn.onclick = () => {
        NWState.isSidebarCollapsed = !NWState.isSidebarCollapsed;
        const host = document.getElementById('northway-sidebar-host');
        const app = document.getElementById('app');
        if (NWState.isSidebarCollapsed) {
            host.style.transform = `translateX(${SIDEBAR_WIDTH}px)`;
            btn.style.right = '0';
            btn.innerHTML = '›';
            if (app) app.style.width = '100%';
        } else {
            host.style.transform = 'translateX(0)';
            btn.style.right = `${SIDEBAR_WIDTH}px`;
            btn.innerHTML = '‹';
            adjustLayout();
        }
    };
}

function adjustLayout() {
    if (NWState.isSidebarCollapsed) return;
    const app = document.getElementById('app');
    if (app) {
        app.style.width = `calc(100% - ${SIDEBAR_WIDTH}px)`;
        app.style.transition = 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    }
}

function unmount() {
    nwLog("Unmounting Sidebar...");
    const host = document.getElementById('northway-sidebar-host');
    if (host) host.remove();
    const btn = document.getElementById('nw-toggle-btn');
    if (btn) btn.remove();

    if (chatObserver) chatObserver.disconnect();
    if (intervalLayout) clearInterval(intervalLayout);
    NWState.reset();
    NWState.shadowRoot = null;

    const app = document.getElementById('app');
    if (app) app.style.width = '100%';
}

/**
 * Robust chrome.runtime.sendMessage Wrapper
 */
function sendMsg(payload) {
    if (!chrome.runtime?.id) {
        nwLog("CRITICAL: Extension context invalidated.");
        return Promise.resolve(null);
    }
    return chrome.runtime.sendMessage(payload)
        .catch(err => {
            nwLog("SendMsg failed", err);
            return null;
        });
}

function bindEvents() {
    const root = NWState.shadowRoot;
    if (!root) return;

    // Nav
    getEl('nw-btn-nav-broadcast').onclick = () => showState('broadcast');
    getEl('nw-btn-close-broadcast').onclick = () => showState('idle');
    getEl('nw-btn-nav-automation').onclick = () => showState('automation');
    getEl('nw-btn-close-automation').onclick = () => showState('idle');

    // Broadcast setup
    getEl('nw-btn-start-broadcast').onclick = () => BroadcastEngine.start();
    getEl('nw-btn-bc-stop').onclick = () => BroadcastEngine.stop();
    getEl('nw-btn-bc-pause').onclick = () => BroadcastEngine.togglePause();
    getEl('nw-btn-bc-confirm').onclick = () => BroadcastEngine.confirmSend();
    
    // Group
    getEl('nw-btn-export').onclick = () => GroupExtractor.toggle();

    // CRM Lead
    getEl('nw-btn-open-form').onclick = () => {
        getEl('nw-new-collapsed').classList.add('hidden');
        getEl('nw-new-form').classList.remove('hidden');
    };
    
    getEl('nw-btn-create').onclick = async () => {
        const data = {
            name: getEl('nw-new-name').value,
            phone: getEl('nw-new-phone').value,
            notes: getEl('nw-new-notes').value,
            pipeline_stage_id: getEl('nw-new-stage').value
        };
        const res = await sendMsg({ action: "CREATE_LEAD", data });
        if (res?.success) toast("Criado!", "success");
    };

    // Message bridge from MAIN world
    window.addEventListener('message', (e) => {
        if (e.data.source === 'NW_PAGE' && e.data.type === 'NW_TOAST') {
            toast(e.data.message, e.data.toastType);
        }
    });

    const btnDirectSend = getEl('nw-btn-direct-send');
    if (btnDirectSend) {
        btnDirectSend.onclick = () => {
            const message = getEl('nw-input-notes').value || "";
            sendSingleMessage(NWState.currentPhone, message);
        };
    }

    nwLog("Events bound.");
}

// Global Keyboard Shortcut
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === 'KeyZ') {
        const root = document.getElementById('northway-sidebar-host');
        if (root) root.style.transform = root.style.transform.includes('100%') ? 'translateX(0)' : 'translateX(100%)';
    }
});

// Start
setTimeout(bootstrap, 2000);
