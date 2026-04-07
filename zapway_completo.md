# ZapWay Extension v4.0.7

## Description
WhatsApp Web CRM Integration with Adaptive Scraping.

## Architecture & Directory Structure
```text
northway_extension/
    manifest.json
    popup/
        popup.html
        popup.js
        styles.css
    scripts/
        automation.js
        background.js
        broadcast.js
        constants.js
        detection.js
        group_extractor.js
        main.js
        page_injected.js
        selectors.js
        sidebar.css
        sidebar.html
        sidebar_ui.js
        state.js
```

---

## 📂 Files Source Code

### `manifest.json`

```json
{
  "manifest_version": 3,
  "name": "ZapWay",
  "version": "4.0.7",
  "description": "WhatsApp Web CRM Integration with Adaptive Scraping.",
  "permissions": [
    "storage",
    "scripting"
  ],
  "host_permissions": [
    "https://web.whatsapp.com/*",
    "http://127.0.0.1:5001/*",
    "https://north-way-2-0.vercel.app/*",
    "https://crm.northwaycompany.com.br/*"
  ],
  "background": {
    "service_worker": "scripts/background.js"
  },
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "128": "icons/icon128.png"
    }
  },
  "content_scripts": [
    {
      "matches": [
        "https://web.whatsapp.com/*"
      ],
      "js": [
        "scripts/constants.js",
        "scripts/selectors.js",
        "scripts/state.js",
        "scripts/detection.js",
        "scripts/broadcast.js",
        "scripts/automation.js",
        "scripts/group_extractor.js",
        "scripts/sidebar_ui.js",
        "scripts/main.js"
      ],
      "css": [
        "scripts/sidebar.css"
      ],
      "run_at": "document_idle"
    },
    {
      "matches": [
        "https://web.whatsapp.com/*"
      ],
      "js": [
        "scripts/page_injected.js"
      ],
      "world": "MAIN",
      "run_at": "document_start"
    }
  ],
  "web_accessible_resources": [
    {
      "resources": [
        "scripts/sidebar.html",
        "scripts/sidebar.css",
        "scripts/page_injected.js",
        "assets/*"
      ],
      "matches": [
        "https://web.whatsapp.com/*"
      ]
    }
  ],
  "icons": {
    "128": "icons/icon128.png"
  }
}
```

### `popup/popup.html`

```html
<!DOCTYPE html>
<html>

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="styles.css">
</head>

<body>
    <div class="nw-popup">
        <!-- HEADER -->
        <div class="nw-popup-header">
            <div class="nw-header-row">
                <div class="nw-logo-icon-small">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"
                        stroke-linecap="round" stroke-linejoin="round">
                        <path d="M13 3L21 11M21 11L13 19M21 11H3"></path>
                    </svg>
                </div>
                <span class="nw-header-title">NorthWay Assistant</span>
                <div class="nw-connection-status offline" title="Desconectado"></div>
            </div>

            <!-- Navbar REMOVED (No navigation needed) -->
        </div>

        <!-- AUTH VIEW (Login) -->
        <div id="nw-view-auth">
            <div class="nw-hero">
                <h1>Acesse sua <br><span>Operação</span></h1>
                <p>ZapWay Extension v3.0.4</p>
            </div>

            <div id="nw-login-form" class="nw-auth-card">
                <div id="nw-error-msg" class="nw-error-box hidden"></div>
                <div class="nw-input-group">
                    <input type="email" id="nw-email" placeholder="E-mail Corporativo">
                </div>
                <div class="nw-input-group">
                    <input type="password" id="nw-password" placeholder="Senha de Acesso">
                </div>
                <button id="nw-btn-login" class="nw-btn primary">Conectar</button>
            </div>
        </div>

        <!-- ACTIVE VIEW (Logged In) -->
        <div id="nw-view-active" class="nw-view hidden" style="padding-top: 20px;">
            <div class="nw-auth-card" style="text-align: center; margin-bottom: 20px;">
                <div class="nw-user-avatar" style="margin: 0 auto 10px;">
                    <img id="nw-user-img" src="" class="hidden">
                    <span id="nw-user-initials">AD</span>
                </div>
                <strong id="nw-user-name" style="display: block; font-size: 16px; margin-bottom: 2px;">Usuário</strong>
                <span id="nw-user-email"
                    style="display: block; color: var(--nw-text-muted); font-size: 12px;">email@northway.com</span>
            </div>

            <!-- Stats (Bug 13) -->
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <div
                    style="flex: 1; background: rgba(var(--nw-primary-rgb), 0.1); border: 1px solid rgba(var(--nw-primary-rgb), 0.2); padding: 12px; border-radius: 8px; text-align: center;">
                    <div id="nw-popup-sent"
                        style="font-size: 20px; font-weight: bold; color: var(--nw-primary); margin-bottom: 4px;">0
                    </div>
                    <div style="font-size: 10px; color: var(--nw-text-muted); text-transform: uppercase;">Disparos</div>
                </div>
                <div
                    style="flex: 1; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); padding: 12px; border-radius: 8px; text-align: center;">
                    <div id="nw-popup-crm"
                        style="font-size: 20px; font-weight: bold; color: #10b981; margin-bottom: 4px;">0</div>
                    <div style="font-size: 10px; color: var(--nw-text-muted); text-transform: uppercase;">Leads</div>
                </div>
            </div>

            <div
                style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 10px; font-size: 11px; color: #ccc; margin-bottom: 20px; text-align: center;">
                🚀 Use a barra lateral no <b>WhatsApp Web</b> para realizar disparos.
            </div>

            <a href="https://web.whatsapp.com" target="_blank" class="nw-btn primary"
                style="text-decoration: none; width: 100%; justify-content: center; margin-bottom: 8px;">
                Abrir WhatsApp Web
            </a>

            <button id="nw-btn-logout" class="nw-btn"
                style="width: 100%; justify-content: center; background: rgba(255,255,255,0.05);">
                Desconectar
            </button>
        </div>

        <!-- FOOTER -->
        <div class="nw-popup-footer">
            <span class="nw-version">v3.0.4</span>
            <div class="nw-footer-stats hidden" id="nw-footer-stats">
                Enviados hoje: <span id="nw-today-count">0</span>
            </div>
        </div>
    </div>

    <script src="popup.js"></script>
</body>

</html>
```

### `popup/popup.js`

```js
document.addEventListener('DOMContentLoaded', async () => {
    // === GLOBALS ===
    const state = {
        user: null,
        token: null
    };

    const els = {
        views: {
            auth: document.getElementById('nw-view-auth'),
            active: document.getElementById('nw-view-active')
        },
        inputs: {
            email: document.getElementById('nw-email'),
            password: document.getElementById('nw-password')
        },
        btns: {
            login: document.getElementById('nw-btn-login'),
            logout: document.getElementById('nw-btn-logout')
        },
        msg: document.getElementById('nw-error-msg'),
        status: document.querySelector('.nw-connection-status')
    };

    // === HELPERS ===
    const showView = (viewName) => {
        Object.values(els.views).forEach(el => el.classList.add('hidden'));
        if (els.views[viewName]) els.views[viewName].classList.remove('hidden');
    };

    const showError = (msg) => {
        els.msg.textContent = msg;
        els.msg.classList.remove('hidden');
        setTimeout(() => els.msg.classList.add('hidden'), 5000);
    };

    // === LISTENERS ===

    // Login
    els.btns.login.addEventListener('click', async () => {
        const email = els.inputs.email.value;
        const password = els.inputs.password.value;

        if (!email || !password) return showError("Preencha todos os campos.");

        els.btns.login.textContent = "Conectando...";
        els.btns.login.disabled = true;

        const response = await chrome.runtime.sendMessage({ action: "LOGIN", email, password });

        if (response.success) {
            state.user = response.user;
            state.token = response.token;
            initAuthenticated();
        } else {
            els.btns.login.textContent = "Conectar";
            els.btns.login.disabled = false;
            showError("Erro: " + (response.error || "Credenciais inválidas"));
        }
    });

    // Logout
    els.btns.logout.addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ action: "LOGOUT" });
        location.reload();
    });

    // === INIT ===
    const initAuthenticated = async () => {
        els.views.auth.classList.add('hidden');
        els.status.classList.add('online');
        els.status.title = "Conectado";

        // Setup User Card
        if (state.user) {
            document.getElementById('nw-user-name').textContent = state.user.name;
            document.getElementById('nw-user-email').textContent = state.user.email;

            if (state.user.avatar_url) {
                const img = document.getElementById('nw-user-img');
                img.src = state.user.avatar_url;
                img.classList.remove('hidden');
                document.getElementById('nw-user-initials').classList.add('hidden');
            }
        }

        // Fetch Daily Stats (Bug 13)
        chrome.runtime.sendMessage({ action: "GET_TODAY_STATS" }, (stats) => {
            if (stats) {
                const elSent = document.getElementById('nw-popup-sent');
                const elCrm = document.getElementById('nw-popup-crm');
                if (elSent) elSent.textContent = stats.sent || 0;
                if (elCrm) elCrm.textContent = stats.crm || 0;
            }
        });

        showView('active');
    };

    // Check Auth on Load
    const res = await chrome.runtime.sendMessage({ action: "CHECK_AUTH" });
    if (res.token) {
        state.token = res.token;
        chrome.storage.local.get('user', (d) => {
            state.user = d.user;
            initAuthenticated();
        });
    } else {
        showView('auth');
    }
});

```

### `popup/styles.css`

```css
:root {
    --nw-bg: #030304;
    /* Ultra Dark */
    --nw-bg-card: rgba(18, 18, 24, 0.7);
    --nw-primary: #ff1f4b;
    --nw-primary-hover: #ff3d63;
    --nw-accent: #00e699;
    /* Vibrant Mint */
    --nw-text: #ffffff;
    --nw-text-muted: #8b8b95;
    --nw-border: rgba(255, 255, 255, 0.06);
    --nw-border-hover: rgba(255, 255, 255, 0.15);

    /* Glass Effect */
    --glass-bg: rgba(255, 255, 255, 0.03);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-blur: blur(20px);

    /* Shadows */
    --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.3);
    --shadow-glow: 0 0 25px rgba(255, 31, 75, 0.15);

    /* Dimensions */
    --rad-sm: 8px;
    --rad-md: 14px;
    --rad-full: 99px;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
}

body {
    width: 340px;
    height: 520px;
    background: radial-gradient(circle at top right, #1a0b0e 0%, #030304 60%);
    color: var(--nw-text);
    overflow: hidden;
    position: relative;
}

.nw-popup {
    padding: 24px;
    height: 100%;
    display: flex;
    flex-direction: column;
}

/* === HEADER === */
.nw-popup-header {
    margin-bottom: 24px;
}

.nw-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.nw-logo-icon-small {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--nw-primary), #ff4d6d);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(255, 31, 75, 0.25);
}

.nw-header-title {
    font-weight: 700;
    font-size: 14px;
    letter-spacing: -0.2px;
}

.nw-connection-status {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #444;
    transition: all 0.3s ease;
}

.nw-connection-status.online {
    background: var(--nw-accent);
    box-shadow: 0 0 8px var(--nw-accent);
}

/* === NAVBAR === */
.nw-navbar {
    display: flex;
    background: rgba(255, 255, 255, 0.04);
    padding: 4px;
    border-radius: 10px;
    margin-top: 16px;
    position: relative;
}

.nw-nav-btn {
    flex: 1;
    background: transparent;
    border: none;
    padding: 8px;
    color: var(--nw-text-muted);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    border-radius: 7px;
    transition: all 0.2s;
}

.nw-nav-btn:hover {
    color: var(--nw-text);
}

.nw-nav-btn.active {
    background: rgba(255, 255, 255, 0.08);
    color: var(--nw-text);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* === AUTH VIEW === */
.nw-hero {
    text-align: center;
    margin: 30px 0 35px;
}

.nw-hero h1 {
    font-size: 24px;
    font-weight: 800;
    line-height: 1.2;
    background: linear-gradient(to right, #fff, #aaa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.nw-hero h1 span {
    background: linear-gradient(to right, var(--nw-primary), #ff6b8b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.nw-hero p {
    font-size: 11px;
    color: var(--nw-text-muted);
    margin-top: 8px;
    letter-spacing: 1px;
    text-transform: uppercase;
    font-weight: 600;
}

.nw-auth-card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 24px;
    box-shadow: var(--shadow-sm);
}

/* === INPUTS & FORMS === */
input,
select,
textarea {
    width: 100%;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--nw-border);
    border-radius: var(--rad-sm);
    padding: 12px 14px;
    color: var(--nw-text);
    font-size: 13px;
    outline: none;
    transition: all 0.2s;
}

input:hover,
select:hover,
textarea:hover {
    border-color: var(--nw-border-hover);
    background: rgba(0, 0, 0, 0.4);
}

input:focus,
select:focus,
textarea:focus {
    border-color: var(--nw-primary);
    background: rgba(0, 0, 0, 0.5);
    box-shadow: 0 0 0 3px rgba(255, 31, 75, 0.1);
}

.nw-input-group {
    margin-bottom: 12px;
}

/* === BUTTONS === */
.nw-btn {
    width: 100%;
    border: none;
    padding: 12px;
    border-radius: var(--rad-sm);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.nw-btn.primary {
    background: linear-gradient(135deg, var(--nw-primary), #d6133a);
    color: white;
    box-shadow: 0 8px 20px rgba(255, 31, 75, 0.25);
}

.nw-btn.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 25px rgba(255, 31, 75, 0.35);
}

.nw-btn.primary:active {
    transform: translateY(0);
}

.nw-btn.secondary {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--nw-border);
    color: var(--nw-text);
}

.nw-btn.secondary:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: var(--nw-border-hover);
}

.nw-btn.big {
    padding: 16px;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
    border-radius: 12px;
}

/* === SECTIONS & CARDS === */
.nw-section {
    padding: 16px 0;
    border-bottom: 1px solid var(--nw-border);
}

.nw-section:last-child {
    border-bottom: none;
}

.nw-label-caps {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--nw-primary);
    font-weight: 700;
    letter-spacing: 0.8px;
    margin-bottom: 10px;
    display: block;
}

.nw-card-flat {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--nw-border);
    border-radius: var(--rad-md);
    padding: 16px;
    margin-bottom: 16px;
}

/* === TAGS & UPLOAD === */
.nw-tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

.nw-tag {
    font-size: 10px;
    background: rgba(255, 31, 75, 0.1);
    color: #ff8fa5;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid rgba(255, 31, 75, 0.15);
    transition: all 0.2s;
}

.nw-tag:hover {
    background: rgba(255, 31, 75, 0.2);
    color: white;
}

.nw-upload-area {
    border: 1px dashed var(--nw-border);
    border-radius: var(--rad-sm);
    padding: 16px;
    text-align: center;
    color: var(--nw-text-muted);
    font-size: 12px;
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
    transition: all 0.2s;
}

.nw-upload-area:hover {
    border-color: var(--nw-primary);
    color: white;
    background: rgba(255, 31, 75, 0.05);
}

/* === ATTACHMENT ITEMS === */
.nw-attachment-item {
    background: #111;
    border: 1px solid var(--nw-border);
    padding: 8px 12px;
    border-radius: 6px;
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    align-items: center;
}

.nw-attachment-remove {
    color: #ff4d6d;
    cursor: pointer;
    font-weight: bold;
    padding: 4px;
}

.nw-attachment-remove:hover {
    color: #ff1f4b;
}


/* === FOOTER === */
.nw-popup-footer {
    display: flex;
    justify-content: center;
    margin-top: auto;
    padding-top: 20px;
}

.nw-version {
    font-size: 10px;
    color: var(--nw-text-muted);
    background: rgba(255, 255, 255, 0.03);
    padding: 4px 10px;
    border-radius: 20px;
}

/* === UTILS === */
.hidden {
    display: none !important;
}

.nw-view {
    flex: 1;
    overflow-y: auto;
    padding-right: 4px;
    animation: fadeScale 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}

@keyframes fadeScale {
    from {
        opacity: 0;
        transform: scale(0.98);
    }

    to {
        opacity: 1;
        transform: scale(1);
    }
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 4px;
}

::-webkit-scrollbar-thumb {
    background: #333;
    border-radius: 4px;
}
```

### `scripts/automation.js`

```js
/**
 * ZapWay Automation Engine
 * Polls CRM for pending WhatsApp actions.
 */

const AutomationEngine = {
    queue: [],
    intervalId: null,

    startPolling: function () {
        if (this.intervalId) clearInterval(this.intervalId);
        this.intervalId = setInterval(() => this.poll(), 30000);
        this.poll();
    },

    poll: async function () {
        nwLog("Polling automation queue...");
        try {
            const response = await sendMsg({ action: "GET_WHATSAPP_QUEUE" });
            if (response && Array.isArray(response)) {
                this.queue = response;
                this.updateBadge();
                this.render();
            }
        } catch (err) {
            nwLog("Poll failed", err);
        }
    },

    updateBadge: function () {
        const badge = getEl('nw-automation-badge');
        if (badge) {
            if (this.queue.length > 0) {
                badge.textContent = this.queue.length;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    },

    render: function () {
        const list = getEl('nw-automation-list');
        if (!list) return;
        
        if (this.queue.length === 0) {
            list.innerHTML = `<div class="nw-empty-state">Tudo em dia!</div>`;
            return;
        }

        list.innerHTML = '';
        this.queue.forEach(item => {
            const card = document.createElement('div');
            card.className = 'nw-card';
            card.style.marginBottom = '12px';
            card.style.borderLeft = '4px solid var(--nw-primary)';
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <strong>${item.phone}</strong>
                    <button class="nw-btn-send-auto" style="padding:4px 8px; font-size:11px; background:var(--nw-primary); color:white; border:none; border-radius:4px; cursor:pointer;">Enviar</button>
                </div>
                <div style="font-size:12px; white-space:pre-wrap; background:rgba(255,255,255,0.03); padding:8px;">${item.content}</div>
            `;
            card.querySelector('.nw-btn-send-auto').onclick = (e) => this.send(item, e.target);
            list.appendChild(card);
        });
    },

    send: async function (item, btn) {
        if (btn) {
            btn.disabled = true;
            btn.textContent = "...";
        }

        const success = await BroadcastEngine.sendDirectMessage(item.phone, item.content);
        if (success) {
            const res = await sendMsg({ action: "UPDATE_QUEUE_STATUS", data: { id: item.id, status: 'sent' } });
            if (res) {
                this.queue = this.queue.filter(i => i.id !== item.id);
                this.updateBadge();
                this.render();
                toast("Mensagem enviada!", "success");
            }
        } else {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Enviar";
            }
            toast("Erro ao enviar.", "error");
        }
    }
};

```

### `scripts/background.js`

```js
// Background Service Worker
// Handles API requests to avoid CORS issues in content scripts if possible, 
// and manages Auth Token.

const API_BASE = "https://crm.northwaycompany.com.br/api/ext";
// const API_BASE = "http://127.0.0.1:5001/api/ext"; // Dev Mode

// Queue & Rate Limit State
let messageQueue = [];
let isProcessingQueue = false;
let config = {
    minDelay: 5,
    maxDelay: 15,
    dailyLimit: 100,
    sentToday: 0
};

// Initialize Settings
chrome.storage.local.get(['minDelay', 'maxDelay', 'dailyLimit', 'sentToday', 'crmToday', 'lastResetDate'], (data) => {
    if (data.minDelay) config.minDelay = data.minDelay;
    if (data.maxDelay) config.maxDelay = data.maxDelay;
    if (data.dailyLimit) config.dailyLimit = data.dailyLimit;

    // Daily Limit Reset Logic
    const today = new Date().toDateString();
    if (data.lastResetDate !== today) {
        config.sentToday = 0;
        config.crmToday = 0;
        chrome.storage.local.set({ sentToday: 0, crmToday: 0, lastResetDate: today });
    } else {
        config.sentToday = data.sentToday || 0;
        config.crmToday = data.crmToday || 0;
    }
});

// Listen for messages from Content Script or Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    if (request.action === "LOGIN") {
        login(request.email, request.password).then(sendResponse);
        return true;
    }

    if (request.action === "LOGOUT") {
        chrome.storage.local.remove(['authToken', 'user'], () => {
            sendResponse({ success: true });
        });
        return true;
    }

    if (request.action === "UPDATE_SETTINGS") {
        // Refresh config from storage
        chrome.storage.local.get(['minDelay', 'maxDelay', 'dailyLimit'], (data) => {
            if (data.minDelay) config.minDelay = data.minDelay;
            if (data.maxDelay) config.maxDelay = data.maxDelay;
            if (data.dailyLimit) config.dailyLimit = data.dailyLimit;
            console.log("ZapWay Config Updated:", config);
        });
        return false;
    }

    // --- DAILY COUNTERS ---
    if (request.action === "INCREMENT_SENT") {
        config.sentToday++;
        chrome.storage.local.set({ sentToday: config.sentToday });
        sendResponse({ success: true, count: config.sentToday });
        return false;
    }

    if (request.action === "INCREMENT_CRM") {
        config.crmToday++;
        chrome.storage.local.set({ crmToday: config.crmToday });
        sendResponse({ success: true, count: config.crmToday });
        return false;
    }

    if (request.action === "GET_TODAY_STATS") {
        sendResponse({ sent: config.sentToday, crm: config.crmToday });
        return false;
    }

    // --- CRM API PROXIES ---
    // Content Script NEVER calls API directly. It asks Background to do it.

    if (request.action === "GET_CONTACT") {
        let qs = `phone=${encodeURIComponent(request.phone || '')}`;
        if (request.name) qs += `&name=${encodeURIComponent(request.name)}`;
        apiCall(`/contact/search?${qs}`, 'GET').then(sendResponse);
        return true;
    }

    if (request.action === "CREATE_LEAD") {
        apiCall('/leads', 'POST', request.data).then(sendResponse);
        return true;
    }

    if (request.action === "UPDATE_LEAD") {
        apiCall(`/leads/${request.id}`, 'PUT', request.data).then(sendResponse);
        return true;
    }

    if (request.action === "GET_PIPELINES") {
        apiCall('/pipelines', 'GET').then(sendResponse);
        return true;
    }

    if (request.action === "CHECK_AUTH") {
        getToken().then(token => sendResponse({ token: token }));
        return true;
    }

    if (request.action === "GET_CONFIG") {
        apiCall('/config', 'GET').then(sendResponse);
        return true;
    }

    if (request.action === "GET_TEMPLATES") {
        apiCall('/templates', 'GET').then(sendResponse);
        return true;
    }

    if (request.action === "GET_WHATSAPP_QUEUE") {
        apiCall('/whatsapp/queue', 'GET').then(sendResponse);
        return true;
    }

    if (request.action === "UPDATE_QUEUE_STATUS") {
        apiCall('/whatsapp/queue/update', 'POST', request.data).then(sendResponse);
        return true;
    }

    // Future: "ENQUEUE_MESSAGE" action for automated sending
});

async function getToken() {
    const data = await chrome.storage.local.get("authToken");
    return data.authToken;
}

async function login(email, password) {
    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();

        if (response.ok && data.token) {
            await chrome.storage.local.set({
                authToken: data.token,
                user: data.user
            });
            return { success: true, user: data.user };
        } else {
            return { success: false, error: data.error || "Login Failed" };
        }
    } catch (e) {
        return { success: false, error: e.message };
    }
}

async function apiCall(endpoint, method, body = null) {
    let token = null;
    try {
        token = await getToken();
    } catch (e) {
        console.error("NW: Token retrieval failed", e);
        return { error: "Token error" };
    }

    if (!token) {
        console.warn("NW: No auth token found");
        return { error: "Unauthorized", needsLogin: true };
    }

    try {
        const options = {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(`${API_BASE}${endpoint}`, options);

        if (response.status === 401 || response.status === 403) {
            return { error: "Unauthorized", needsLogin: true };
        }

        if (response.status === 404) return { found: false };

        if (!response.ok) {
            return { error: `Server error: ${response.status}` };
        }

        return await response.json();
    } catch (e) {
        console.error("NW: API Call Exception", e);
        return { error: e.message || "Connection failed" };
    }
}

```

### `scripts/broadcast.js`

```js
/**
 * ZapWay Broadcast Engine
 * Handles messaging in bulk and single direct messages.
 */

const BroadcastEngine = {
    queue: [],
    currentIndex: -1,
    isPaused: false,
    isActive: false, // Core state for pause/resume logic
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
        nwLog("Initializing BroadcastEngine...");
        const res = await chrome.storage.local.get([
            'bc_queue', 'bc_index', 'bc_active', 'bc_templates', 
            'bc_auto', 'bc_config', 'bc_batch_count', 'bc_current_message', 
            'bc_media_caption', 'bc_current_step', 'bc_media_name', 'bc_media_type'
        ]);

        if (res.bc_queue) this.queue = res.bc_queue;
        if (res.bc_index !== undefined) this.currentIndex = res.bc_index;
        if (res.bc_templates) this.templates = res.bc_templates;
        this.autoSend = res.bc_auto || false;
        if (res.bc_config) this.config = res.bc_config;

        if (res.bc_current_message) this.currentMessage = res.bc_current_message;
        if (res.bc_media_caption) this.mediaCaption = res.bc_media_caption;
        if (res.bc_current_step) this.currentStep = res.bc_current_step;

        // UI Initialization
        this.syncUI();

        if (res.bc_active) {
            this.isActive = true;
            await this.restoreMedia(res);
            this.toggleView(true);
            this.renderQueue();
            this.updateStats();
            this.renderCurrent();

            if (this.media && this.currentStep === 2) {
                await this.attachMedia();
            }

            if (this.autoSend) this.attemptAutoSend();
        }
    },

    syncUI: function() {
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

        const tplArea = getEl('nw-broadcast-template');
        if (tplArea) tplArea.value = this.templates[this.currentTab] || "";
    },

    restoreMedia: async function(res) {
        const savedMedia = await NWDB.getFile("bc_media");
        if (savedMedia) {
            const fileName = res.bc_media_name || savedMedia.name || "arquivo";
            const ext = fileName.split('.').pop().toLowerCase();
            let fileType = MIME_MAP[ext] || res.bc_media_type || savedMedia.type || "application/octet-stream";

            this.media = new File([savedMedia], fileName, { type: fileType, lastModified: Date.now() });
            
            const prev = getEl('nw-media-preview-container');
            const pName = getEl('nw-media-filename');
            const pCap = getEl('nw-media-caption');
            if (prev) prev.classList.remove('hidden');
            if (pName) pName.textContent = this.media.name;
            if (pCap) pCap.value = this.mediaCaption;
        }
    },

    toggleView: function(active) {
        if (active) {
            showState('broadcast');
            getEl('nw-broadcast-setup').classList.add('hidden');
            getEl('nw-broadcast-active').classList.remove('hidden');
        } else {
            getEl('nw-broadcast-active').classList.add('hidden');
            getEl('nw-broadcast-setup').classList.remove('hidden');
        }
    },

    /**
     * Implement missing sendDirectMessage logic.
     * Navigates to the contact and prepares the input.
     */
    sendDirectMessage: async function(phone, content) {
        nwLog(`Direct Message request for ${phone}`);
        try {
            // Open chat with phone and message
            const targetUrl = `https://web.whatsapp.com/send?phone=${phone.replace(/\D/g, '')}&text=${encodeURIComponent(content)}`;
            
            const link = document.createElement('a');
            link.href = targetUrl;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Wait for input to be ready
            let attempts = 0;
            while (attempts < 20) {
                const sendBtn = this.findSendButton();
                if (sendBtn) {
                    nwLog("Direct message input ready. Triggering send...");
                    sendBtn.click();
                    return true;
                }
                await new Promise(r => setTimeout(r, 1000));
                attempts++;
            }
            return false;
        } catch (e) {
            nwLog("sendDirectMessage error", e);
            return false;
        }
    },

    start: function () {
        if (this.queue.length === 0) {
            toast("⚠️ Importe contatos primeiro!", "warning");
            return;
        }

        const autoCheck = getEl('nw-broadcast-auto');
        this.autoSend = autoCheck ? autoCheck.checked : false;

        this.isActive = true;
        this.toggleView(true);
        this.currentIndex = -1;
        this.next();
    },

    stop: async function () {
        nwLog("Stopping Broadcast");
        if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);

        this.isPaused = false;
        this.isActive = false;
        
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

        const progressSection = getEl('nw-progress-section');
        if (progressSection) progressSection.classList.add('hidden');
        
        this.updateStats();
        this.toggleView(false);
    },

    save: async function () {
        await chrome.storage.local.set({
            bc_queue: this.queue,
            bc_index: this.currentIndex,
            bc_active: this.isActive,
            bc_templates: this.templates,
            bc_auto: this.autoSend,
            bc_config: this.config,
            bc_batch_count: this.batchCount,
            bc_current_message: this.currentMessage,
            bc_media_caption: this.mediaCaption,
            bc_current_step: this.currentStep
        });
    },

    renderQueue: function (searchTerm = '') {
        const list = getEl('nw-bc-queue-list');
        if (!list) return;

        const counterEl = getEl('nw-bc-queue-counter');
        if (counterEl) counterEl.innerHTML = `<span class="nw-chip">${this.queue.length} contatos</span>`;

        let filteredQueue = this.queue;
        if (searchTerm && searchTerm.trim() !== '') {
            const lowerTerm = searchTerm.toLowerCase();
            filteredQueue = this.queue.filter(c =>
                (c.name && c.name.toLowerCase().includes(lowerTerm)) ||
                (c.phone && c.phone.includes(lowerTerm))
            );
        }

        list.innerHTML = '';
        filteredQueue.forEach((item) => {
            const originalIndex = this.queue.indexOf(item);
            const isActive = originalIndex === this.currentIndex ? 'active' : '';

            const div = document.createElement('div');
            div.className = `nw-q-item ${isActive}`;
            div.innerHTML = `
                <div style="display: flex; flex-direction: column;">
                    <span>${item.name}</span>
                    <span style="font-size: 10px; color: var(--nw-text-secondary);">${item.phone}</span>
                </div>
                <div style="display: flex; gap: 6px; align-items: center;">
                    <span class="nw-q-status ${item.status}">${item.status}</span>
                </div>
            `;
            list.appendChild(div);
        });
    },

    findSendButton: function (onlyOverlay = false) {
        const allPossible = Array.from(document.querySelectorAll(SELECTORS.SEND_BUTTON.join(',')));
        
        const candidates = allPossible.filter(el => {
            if (el.closest('#side')) return false;
            return true;
        });

        if (onlyOverlay || document.querySelector('div[role="dialog"]')) {
            const overlayBtn = candidates.find(el => el.closest('div[role="dialog"]') || el.closest('div[role="region"]'));
            if (overlayBtn) return overlayBtn;
            if (onlyOverlay) return null;
        }

        return candidates.find(el => el.closest('footer')) || candidates[0] || null;
    },

    attachMedia: async function () {
        if (!this.media) return true;
        nwLog(`Attaching media: ${this.media.name}`);

        try {
            const arrayBuffer = await this.media.arrayBuffer();
            const data = Array.from(new Uint8Array(arrayBuffer));
            const isImageOrVideo = this.media.type.startsWith('image/') || this.media.type.startsWith('video/');
            const kind = isImageOrVideo ? 'media' : 'document';

            window.postMessage({
                source: "NW_EXTENSION",
                type: "NW_ATTACH_FILE",
                payload: { kind, name: this.media.name, mime: this.media.type, data }
            }, "*");

            // Wait for preview (30s)
            for (let i = 0; i < 60; i++) {
                await new Promise(r => setTimeout(r, 500));
                const previewSend = this.findSendButton(true);

                if (previewSend) {
                    const isDisabled = previewSend.disabled || previewSend.getAttribute('aria-disabled') === 'true';
                    if (!isDisabled) return true;
                }
            }
            return true;
        } catch (e) {
            nwLog("attachMedia error", e);
            return false;
        }
    },

    next: async function () {
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            toast("Disparo finalizado! Todos os contatos concluídos.", "success");
            await this.stop();
            return;
        }

        const item = this.queue[this.currentIndex];
        if (item.status !== 'PENDENTE') return this.next();

        this.renderQueue();
        this.renderCurrent();
        this.currentStep = 1;
        await this.save();

        const phoneNum = item.phone.replace(/\D/g, '');
        const targetUrl = `https://web.whatsapp.com/send?phone=${phoneNum}&text=${encodeURIComponent(this.currentMessage)}`;
        
        if (!window.location.search.includes(phoneNum)) {
            const link = document.createElement('a');
            link.href = targetUrl;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    },

    confirmSend: async function () {
        if (this.currentIndex < 0) return;

        if (this.media && this.currentStep === 1) {
            this.currentStep = 2;
            await this.save();
            setTimeout(async () => {
                await this.attachMedia();
                if (this.autoSend) this.attemptAutoSend();
            }, 1500);
            return;
        }

        this.queue[this.currentIndex].status = 'ENVIADO';
        chrome.runtime.sendMessage({ action: "INCREMENT_SENT" });
        this.updateStats();

        this.batchCount++;
        this.currentStep = 1;
        await this.save();

        const btn = getEl('nw-btn-bc-confirm');
        if (btn) btn.disabled = true;

        let delay = 0;
        let isBatchPause = false;

        if (this.config.batchSize > 0 && this.batchCount >= this.config.batchSize) {
            delay = this.config.batchWait * 1000;
            isBatchPause = true;
            this.batchCount = 0;
        } else {
            const min = this.config.min || 10;
            const max = this.config.max || 20;
            delay = Math.floor(Math.random() * (max - min + 1) + min) * 1000;
        }

        this.startCountdown(delay, isBatchPause);
    },

    startCountdown: function(delay, isBatchPause) {
        let totalTime = delay / 1000;
        let remaining = totalTime;
        const msgPrefix = isBatchPause ? "🛡️ Pausa Longa: " : "Aguardando ";
        
        const btn = getEl('nw-btn-bc-confirm');
        const progressSection = getEl('nw-progress-section');
        const countdownText = getEl('nw-countdown-text');
        const progressFill = getEl('nw-progress-fill');

        if (progressSection) progressSection.classList.remove('hidden');

        const tickRate = 100;
        const interval = setInterval(() => {
            remaining -= 0.1;
            const currentWidth = ((totalTime - remaining) / totalTime) * 100;

            if (btn) btn.textContent = `${msgPrefix}${Math.ceil(remaining)}s...`;
            if (countdownText) countdownText.textContent = `${Math.ceil(remaining)}s`;
            if (progressFill) progressFill.style.width = `${Math.min(currentWidth, 100)}%`;

            if (remaining <= 0) {
                clearInterval(interval);
                if (btn) {
                    btn.textContent = "Confirmar Envio";
                    btn.disabled = false;
                }
                if (progressSection) progressSection.classList.add('hidden');
                this.next();
            }
        }, tickRate);

        this.currentDelayInterval = interval;
    },

    togglePause: function () {
        if (!this.isActive) return;

        const btnPause = getEl('nw-btn-bc-pause');
        const btnConfirm = getEl('nw-btn-bc-confirm');

        if (this.isPaused) {
            this.isPaused = false;
            if (btnPause) btnPause.textContent = "⏸ Pausar Lote";
            if (btnConfirm) btnConfirm.disabled = true;
            if (this.autoSend) this.attemptAutoSend();
        } else {
            this.isPaused = true;
            if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);
            if (btnPause) btnPause.textContent = "▶ Retomar";
            if (btnConfirm) {
                btnConfirm.textContent = "Pausado (Retomar)";
                btnConfirm.disabled = false;
            }
            toast("Disparo pausado.", "info");
        }
    },

    updateStats: function () {
        const pending = this.queue.filter(i => i.status === 'PENDENTE').length;
        const sent = this.queue.filter(i => i.status === 'ENVIADO').length;
        const failed = this.queue.filter(i => i.status === 'FALHOU').length;

        const p = getEl('nw-stat-pending'); if (p) p.textContent = pending;
        const s = getEl('nw-stat-sent'); if (s) s.textContent = sent;
        const f = getEl('nw-stat-failed'); if (f) f.textContent = failed;
        
        const etaEl = getEl('nw-stat-eta');
        if (etaEl) etaEl.textContent = pending === 0 ? "Finalizado" : this.calculateETA(pending);
    },

    calculateETA: function(pending) {
        const min = this.config.min || 10;
        const max = this.config.max || 20;
        const avgDelay = (min + max) / 2;
        const attachmentBuffer = this.media ? 10 : 0;
        const batchSize = this.config.batchSize || 10;
        const batchWait = this.config.batchWait || 60;
        const batchesLeft = Math.floor(pending / batchSize);
        const totalBatchWait = batchesLeft * batchWait;
        
        const totalSeconds = (pending * (avgDelay + attachmentBuffer)) + totalBatchWait;
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const sec = Math.floor(totalSeconds % 60);
        
        const parts = [];
        if (h > 0) parts.push(`${h} h`);
        parts.push(`${m} m`);
        parts.push(`${sec} s`);
        
        return parts.join(' ');
    },

    renderCurrent: function() {
        if (this.currentIndex < 0 || this.currentIndex >= this.queue.length) return;
        const item = this.queue[this.currentIndex];
        
        const nameEl = getEl('nw-bc-current-name'); if (nameEl) nameEl.textContent = item.name;
        const phoneEl = getEl('nw-bc-current-phone'); if (phoneEl) phoneEl.textContent = item.phone.split('@')[0];

        const variantKeys = ['A', 'B', 'C'];
        const variant = variantKeys[this.currentIndex % 3];
        const template = this.templates[variant] || this.templates['A'] || "";

        this.currentMessage = this.interpolate(template, item);
        this.currentMediaCaption = this.interpolate(this.mediaCaption, item);

        const previewEl = getEl('nw-bc-message-preview');
        const mediaTag = this.media ? `\n\n📎[ANEXO: ${this.media.name}]` : "";
        if (previewEl) previewEl.textContent = `[Mod ${variant}] ${this.currentMessage}${mediaTag}`;
    },

    interpolate: function(text, data) {
        if (!text) return "";
        return text.replace(/{nome}/gi, data.name || "")
            .replace(/{telefone}/gi, data.phone || "")
            .replace(/{email}/gi, data.email || "")
            .replace(/{origem}/gi, data.origem || "")
            .replace(/{interesse}/gi, data.interesse || "")
            .replace(/{observacao}/gi, data.observacao || "")
            .replace(/{variavel}/gi, data.variable || "");
    },
    
    attemptAutoSend: function() {
        nwLog("Attempting auto-send...");
        let attempts = 0;
        const interval = setInterval(() => {
            attempts++;
            const btn = this.findSendButton();
            if (btn) {
                clearInterval(interval);
                btn.click();
                setTimeout(() => this.confirmSend(), 3000);
            }
            if (attempts >= 30) {
                clearInterval(interval);
                nwLog("Auto-send timeout.");
            }
        }, 1000);
    },

    importContacts: function (text) {
        nwLog("Importing CSV/Text...");
        const rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
        this.queue = [];

        let delimiter = ';';
        const sample = rawLines.slice(0, 5).join('\n');
        const counts = { ';': (sample.match(/;/g) || []).length, ',': (sample.match(/,/g) || []).length, '\t': (sample.match(/\t/g) || []).length };
        if (counts[','] > counts[';'] && counts[','] > counts['\t']) delimiter = ',';
        else if (counts['\t'] > counts[';']) delimiter = '\t';

        rawLines.forEach((line, index) => {
            const lowerLine = line.toLowerCase();
            if (index === 0 && (lowerLine.includes('nome') || lowerLine.includes('fone'))) return;

            const parts = line.split(delimiter).map(p => p.trim().replace(/^["']|["']$/g, ''));
            if (parts.length >= 2) {
                let name = parts[0];
                let phone = "";
                let extra = { email: "", origem: "", interesse: "", observacao: "", variable: "" };

                for (let i = 1; i < parts.length; i++) {
                    const clean = parts[i].replace(/\D/g, '');
                    if (clean.length >= 8 && clean.length <= 15) {
                        phone = clean;
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
                    if (phone.length === 10 || phone.length === 11) phone = '55' + phone;
                    this.queue.push({ name, phone, status: "PENDENTE", ...extra });
                }
            }
        });
        
        nwLog(`Imported ${this.queue.length} contacts.`);
        this.save();
        this.renderQueue();
        this.updateStats();
    },
};

```

### `scripts/constants.js`

```js
/**
 * ZapWay Extension Constants
 */

const SIDEBAR_WIDTH = 380;
const NW_DEBUG = false; // Set to true to enable logs

/**
 * Enhanced Logging Helper
 * @param {string} msg 
 * @param  {...any} args 
 */
const nwLog = (msg, ...args) => {
    if (NW_DEBUG) {
        console.log(`%c[NW] ${msg}`, "color: #ff1f4b; font-weight: bold;", ...args);
    }
};

/**
 * MIME Type Map for robust file handling
 */
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

```

### `scripts/detection.js`

```js
/**
 * ZapWay Contact Detection
 * Strategy Pattern for identifying WhatsApp contacts.
 */

class FiberDetectionStrategy {
    detect() {
        const candidates = [
            getRobustElement(SELECTORS.MAIN_PANEL),
            getRobustElement(SELECTORS.HEADER),
            getRobustElement(SELECTORS.DRAWER),
            document.querySelector('#main')
        ];

        for (const el of candidates) {
            if (!el) continue;
            const fiber = getReactInstance(el);
            if (fiber) {
                const jid = findJidInFiber(fiber);
                if (jid) return { phone: jid, isGroup: jid.includes('@g.us') };
            }
        }
        return null;
    }
}

class DomDetectionStrategy {
    detect() {
        const header = getRobustElement(SELECTORS.HEADER);
        if (header) {
            const nameEl = getRobustElement(SELECTORS.CONTACT_NAME, header);
            let name = nameEl ? (nameEl.title || nameEl.innerText) : null;
            if (name) name = name.trim();

            const img = header.querySelector('img');
            let avatarUrl = img ? img.src : null;
            let phone = null;
            let isGroup = false;

            if (img) {
                const fiber = getReactInstance(img);
                if (fiber) {
                    const jid = findJidInFiber(fiber);
                    if (jid) {
                        phone = jid;
                        isGroup = jid.includes('@g.us');
                    }
                }
            }

            // Failsafe for phone
            if (!phone && name && name.match(/\+?\d[\d\s-]{10,}/)) {
                phone = name.replace(/\D/g, '') + "@c.us";
            }

            if (phone || name) return { phone, name, avatarUrl, isGroup };
        }
        
        // Final fallback: Title scan
        const title = document.title || "";
        const titleMatch = title.match(/^(?:\(\d+\) )?WhatsApp\s*[–-]\s*(.+)$/);
        if (titleMatch && titleMatch[1]) {
            return { name: titleMatch[1].trim(), offline: true };
        }

        return null;
    }
}

class OfflineFallbackStrategy {
    detect() {
        // Try URL
        const url = new URL(window.location.href);
        const phoneParam = url.searchParams.get('phone');
        if (phoneParam) {
            return { phone: phoneParam.replace(/\D/g, '') + "@c.us", offline: true };
        }
        return null;
    }
}

class ContactDetector {
    constructor() {
        this.strategies = [
            new FiberDetectionStrategy(),
            new DomDetectionStrategy(),
            new OfflineFallbackStrategy()
        ];
    }

    detect() {
        for (const strategy of this.strategies) {
            const result = strategy.detect();
            if (result && (result.phone || result.name)) {
                nwLog(`Detection Strategy Used: ${strategy.constructor.name}`, result);
                return result;
            }
        }
        return null;
    }
}

const contactDetector = new ContactDetector();

/**
 * React Fiber Helpers
 */
function getReactInstance(dom) {
    if (!dom) return null;
    for (const key in dom) {
        if (key.startsWith("__reactFiber") || 
            key.startsWith("__reactInternalInstance") || 
            key.startsWith("__reactProps") ||
            key.startsWith("__reactEvents")) return dom[key];
    }
    return null;
}

/**
 * BFS Traversal for JID identification.
 */
function findJidInFiber(fiber) {
    if (!fiber) return null;
    let queue = [{ node: fiber, depth: 0 }];
    let visited = new Set();

    while (queue.length > 0) {
        const { node, depth } = queue.shift();
        if (!node || depth > 25 || visited.has(node)) continue;
        visited.add(node);

        const props = node.memoizedProps || node.props || node.pendingProps;
        if (props) {
            // Case 1: Simple JID string or object
            const jid = props.jid || props.chatId || props.__x_id || props.chatJid || props.remoteJid;
            if (typeof jid === 'string' && jid.includes('@')) return jid;
            
            // Case 2: ID Object 
            if (props.id && typeof props.id === 'object') {
                if (props.id.user && props.id.server) return `${props.id.user}@${props.id.server}`;
                if (props.id._serialized) return props.id._serialized;
            }

            // Case 3: Nested Objects
            const sub = props.chat || props.contact || props.msg || props.item;
            if (sub) {
                const sj = sub.id || sub.jid || sub.remoteJid || (sub.id && sub.id._serialized);
                if (typeof sj === 'string' && sj.includes('@')) return sj;
            }
        }

        if (node.child) queue.push({ node: node.child, depth: depth + 1 });
        if (node.sibling) queue.push({ node: node.sibling, depth: depth + 1 });
        if (depth < 2 && node.return) queue.push({ node: node.return, depth: depth + 1 });
    }
    return null;
}

function getRobustElement(selectors, parent = document) {
    if (!selectors) return null;
    for (const sel of selectors) {
        const el = parent.querySelector(sel);
        if (el && el.offsetParent !== null) return el;
    }
    return null;
}

function checkActiveChat() {
    try {
        const result = contactDetector.detect();
        
        if (!result) {
            if (NWState.currentPhone !== null) {
                NWState.reset();
                showState('idle');
            }
            return;
        }

        const { phone, name, avatarUrl, isGroup, offline } = result;

        const isBcActive = BroadcastEngine.currentIndex >= 0;
        if (isBcActive) return;

        const isSystemChat = name === "WhatsApp" || name === "Contato";
        if (isSystemChat) return;

        const chatId = isGroup ? `GROUP:${name}` : (phone || name);

        if (!chatId) {
            if (NWState.currentPhone !== null) {
                NWState.reset();
                showState('idle');
            }
            return;
        }

        if (chatId !== NWState.currentPhone) {
            nwLog(`Switching to chat: ${chatId}`);
            NWState.currentPhone = chatId;
            NWState.contactName = name;
            NWState.contactPhone = phone;

            if (isGroup) {
                showState('group');
                const el = getEl('nw-group-name');
                if (el) el.textContent = name || "Grupo";
            } else {
                updateSidebar(name || phone, phone, name, avatarUrl);
            }
        }
    } catch (err) {
        nwLog("Detection Error", err);
    }
}

```

### `scripts/group_extractor.js`

```js
/**
 * ZapWay Group Extractor
 * Passive scraping of group members.
 */

const GroupExtractor = {
    isExtracting: false,
    contacts: new Map(),
    observer: null,
    container: null,
    groupName: "",

    toggle: async function () {
        if (this.isExtracting) this.stop();
        else await this.start();
    },

    start: async function () {
        nwLog("Starting group extraction...");
        const progressSection = getEl('nw-export-progress');
        const progressText = getEl('nw-export-status');
        const btn = getEl('nw-btn-export');

        // Detect list container
        const sections = Array.from(document.querySelectorAll('section, div[role="region"], div[role="dialog"], div[data-testid="drawer-right"]'));
        this.container = sections.find(s => {
            if (s.offsetParent === null) return false;
            const t = s.innerText.toLowerCase();
            return t.includes('membros') || t.includes('participantes') || t.includes('participants') || t.includes('dados do grupo');
        });

        if (!this.container) {
            const drawer = getRobustElement(SELECTORS.DRAWER);
            if (drawer?.innerText.match(/membros|participantes/i)) this.container = drawer;
        }

        if (!this.container) {
            toast("⚠️ Abra a lista de participantes do grupo primeiro.", "warning");
            return;
        }

        this.isExtracting = true;
        this.contacts.clear();
        this.groupName = getEl('nw-group-name').textContent || "Grupo";

        if (btn) {
            btn.textContent = "Finalizar e Baixar";
            btn.style.backgroundColor = "#dc3545";
        }
        if (progressSection) progressSection.classList.remove('hidden');
        if (progressText) progressText.innerText = "Extração Ativa! Role a lista manualmente...";

        this.scrapeVisible();

        this.observer = new MutationObserver(() => {
            if (this.checkForSecurityPopup()) return;
            this.scrapeVisible();
        });

        this.observer.observe(this.container, { childList: true, subtree: true });
    },

    stop: function () {
        nwLog("Stopping group extraction...");
        this.isExtracting = false;
        if (this.observer) this.observer.disconnect();

        this.downloadCSV();

        const btn = getEl('nw-btn-export');
        const progressText = getEl('nw-export-status');
        if (btn) {
            btn.textContent = "Extrair Participantes";
            btn.style.backgroundColor = "";
        }
        if (progressText) progressText.innerText = `Finalizado! ${this.contacts.size} contatos exportados.`;

        setTimeout(() => getEl('nw-export-progress').classList.add('hidden'), 5000);
    },

    scrapeVisible: function () {
        if (!this.isExtracting || !this.container) return;

        const items = this.container.querySelectorAll('[data-testid="member-list-item"]') || 
                      this.container.querySelectorAll('[role="listitem"]');

        items.forEach(item => {
            const text = item.innerText || "";
            if (!text) return;

            const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            if (lines.length < 1) return;

            let name = "Usuário sem nome";
            let phone = "";

            const phoneMatch = text.match(/\+?\d[\d\s-]{10,}/);
            if (phoneMatch) {
                phone = phoneMatch[0].replace(/\D/g, '');
                const nameMatch = text.match(/~([^ \n]+)/);
                if (nameMatch) name = nameMatch[1].trim();
                else if (!lines[0].match(/\+?\d[\d\s-]{10,}/)) name = lines[0];
            } else {
                name = lines[0];
            }

            if (name === "Você" || name === "You") return;
            if (phone && !phone.startsWith('55') && phone.length <= 11) phone = '55' + phone;

            const key = phone || name;
            if (!this.contacts.has(key)) {
                this.contacts.set(key, {
                    name: name.replace(/"/g, ''),
                    phone,
                    origin: `Grupo: ${this.groupName}`,
                    date: new Date().toLocaleDateString()
                });
                
                const p = getEl('nw-export-status');
                if (p) p.innerText = `Capturando... ${this.contacts.size} detectados`;
            }
        });
    },

    checkForSecurityPopup: function () {
        const dialogs = document.querySelectorAll('div[role="dialog"]');
        const securityAlert = Array.from(dialogs).find(d => d.innerText.match(/criptografia|encryption|segurança/i));

        if (securityAlert) {
            this.observer.disconnect();
            const p = getEl('nw-export-status');
            if (p) p.innerText = "⏸ PAUSADO: Alerta de Segurança";
            toast("⚠️ Alerta de criptografia detectado. Extração pausada.", "warning");
            return true;
        }
        return false;
    },

    downloadCSV: function () {
        if (this.contacts.size === 0) return;
        const csvHeader = ["Nome", "Email", "Telefone", "Origem", "Interesse", "Observações"];
        const toCSV = (text) => `"${String(text || "").replace(/"/g, '""')}"`;

        const csvRows = Array.from(this.contacts.values()).map(c => {
            return [
                toCSV(c.name), toCSV(""), toCSV(c.phone),
                toCSV(c.origin), toCSV("A definir"),
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

```

### `scripts/main.js`

```js
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

```

### `scripts/page_injected.js`

```js
/**
 * WhatsApp Attachment Engine (Refactored)
 * Handles file injection into WhatsApp Web DOM.
 */

class WhatsAppAttachmentManager {
    constructor() {
        this.moduleName = "NW_ATTACH";
        this.setupListener();
    }

    log(msg, data = null) {
        // Only log if specifically needed, otherwise keep it quiet
        if (data) console.log(`[${this.moduleName}] ${msg}`, data);
        else console.log(`[${this.moduleName}] ${msg}`);
    }

    toast(message, type = 'info') {
        window.postMessage({
            source: 'NW_PAGE',
            type: 'NW_TOAST',
            message,
            toastType: type
        }, '*');
    }

    setupListener() {
        window.addEventListener('message', async (event) => {
            if (event.data.source !== 'NW_EXTENSION') return;

            if (event.data.type === 'NW_PING') return;
            if (event.data.type !== 'NW_ATTACH_FILE') return;

            const { kind, name, mime, data } = event.data.payload;
            
            try {
                const u8 = new Uint8Array(data);
                const blob = new Blob([u8], { type: mime });
                const file = new File([blob], name, { type: mime, lastModified: Date.now() });

                await this.performAttachment(file, kind);
            } catch (err) {
                console.error(`[${this.moduleName}] Attachment Workflow Failed`, err);
            }
        });
    }

    async performAttachment(file, kind) {
        try {
            const mainButton = await this.findMainAttachButton();
            if (!mainButton) {
                this.toast("Não encontrei o botão de anexo. Clique manualmente no clip (📎).", "warning");
            } else {
                const clickableMain = mainButton.closest('div[role="button"]') || mainButton.closest('button') || mainButton;
                this.forceClick(clickableMain);
            }

            const menuSelector = 'ul, div[role="dialog"] ul, div[data-animate-modal-popup="true"] ul';
            const menu = await this.waitForElement([menuSelector], 5000);

            if (menu) {
                const targetButton = this.findMenuItemInMenu(menu, kind);
                if (targetButton) {
                    const originalClick = HTMLInputElement.prototype.click;
                    let hijackedInput = null;
                    
                    const inputCapturedPromise = new Promise(resolve => {
                        HTMLInputElement.prototype.click = function () {
                            if (this.type === 'file') {
                                hijackedInput = this;
                                resolve(this);
                            } else {
                                originalClick.apply(this);
                            }
                        };
                    });

                    setTimeout(() => {
                        if (HTMLInputElement.prototype.click !== originalClick) HTMLInputElement.prototype.click = originalClick;
                    }, 2000);

                    this.forceClick(targetButton);
                    
                    const capturedInput = await Promise.race([
                        inputCapturedPromise,
                        new Promise(r => setTimeout(() => r(null), 1500))
                    ]);

                    HTMLInputElement.prototype.click = originalClick;

                    if (capturedInput) {
                        await this.injectFile(capturedInput, file);
                        return;
                    }
                }
            }
            
            // Fallback
            const fallbackInput = this.findBestInputByAttributes(kind);
            if (fallbackInput) {
                await this.injectFile(fallbackInput, file);
            } else {
                this.toast("Falha ao anexar arquivo automaticamente.", "error");
            }
        } catch (e) {
            console.error("Attachment flow error", e);
        }
    }

    async findMainAttachButton() {
        const exactIcon = document.querySelector('span[data-icon="plus-rounded"]');
        if (exactIcon) return exactIcon.closest('div[role="button"]') || exactIcon.closest('button');

        const selectors = [
            'div[title="Anexar"]', 'div[aria-label="Anexar"]',
            'div[title="Attach"]', 'div[aria-label="Attach"]',
            '[data-icon="clip"]', '[data-icon="plus"]',
            'span[data-testid="clip"]', 'span[data-testid="attach-menu-plus"]'
        ];
        return document.querySelector(selectors.join(','));
    }

    findMenuItemInMenu(menuElement, kind) {
        const items = Array.from(menuElement.querySelectorAll('li, div[role="button"]'));
        return items.find(el => {
            const label = (el.innerText || el.getAttribute('aria-label') || "").toLowerCase();
            const icon = el.querySelector('span[data-icon]');
            const iconData = icon ? icon.getAttribute('data-icon') : "";
            const testId = el.getAttribute('data-testid') || "";

            if (kind === 'document') {
                return testId === 'attach-document' || iconData === 'attach-document' || label.includes('doc');
            } else {
                return testId === 'attach-image' || iconData === 'attach-image' || label.includes('foto') || label.includes('photo') || label.includes('vid');
            }
        });
    }

    findBestInputByAttributes(kind) {
        const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
        if (kind === 'document') {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc === "" || acc === "*" || acc.includes("application");
            });
        } else {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc.includes('image') || acc.includes('video');
            });
        }
    }

    waitForElement(selectors, timeout) {
        return new Promise(resolve => {
            const start = Date.now();
            const interval = setInterval(() => {
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) { clearInterval(interval); resolve(el); return; }
                }
                if (Date.now() - start > timeout) { clearInterval(interval); resolve(null); }
            }, 200);
        });
    }

    async injectFile(inputElement, file) {
        await new Promise(r => setTimeout(r, 100));
        
        const dt = new DataTransfer();
        dt.items.add(file);

        try {
            const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'files').set;
            inputElement.value = '';
            nativeSetter.call(inputElement, dt.files);
        } catch (e) {
            inputElement.files = dt.files;
        }

        const opts = { bubbles: true, cancelable: true, view: window };
        inputElement.dispatchEvent(new Event('input', opts));
        await new Promise(r => setTimeout(r, 50));
        inputElement.dispatchEvent(new Event('change', opts));
    }

    forceClick(el) {
        const opts = { bubbles: true, cancelable: true, view: window };
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
    }
}

new WhatsAppAttachmentManager();

```

### `scripts/selectors.js`

```js
/**
 * ZapWay Extension Selectors
 * Centralized for easy maintenance.
 * Stable selectors for WhatsApp Web.
 */

const SELECTORS = {
    MAIN_PANEL: [
        '[data-testid="conversation-panel-wrapper"]',
        'main#main',
        'div[role="main"]',
        'section:has(header[data-testid="conversation-header"])'
    ],
    HEADER: [
        '[data-testid="conversation-panel-header"]',
        '[data-testid="conversation-info-header"]',
        '[data-testid="conversation-header"]',
        '#main > header',
        'header'
    ],
    CONTACT_NAME: [
        '[data-testid="conversation-info-header-name"]',
        'span[title]',
        'span[dir="auto"]',
        'h1',
        'div[role="button"] span'
    ],
    IMAGE: [
        'img',
        '[data-testid="contact-image"]',
        '[data-testid="group-image"]'
    ],
    DRAWER: [
        '[data-testid="drawer-left"]',
        '[data-testid="drawer-right"]',
        'div[role="navigation"]',
        'div[data-testid="contact-info-drawer"]'
    ],
    CHAT_ITEM: [
        '[role="listitem"]',
        '[data-testid="cell-frame-container"]'
    ],
    TEXT_INPUT: [
        'div[contenteditable="true"][role="textbox"]',
        'footer div[contenteditable="true"]',
        '#main footer div[role="textbox"]'
    ],
    SEND_BUTTON: [
        '[data-testid="compose-btn-send"]',
        '[data-testid="send"]',
        'span[data-icon*="send"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="Enviar"]'
    ],
    ATTACH_BUTTON: [
        '[data-testid="clip"]',
        '[data-testid="attach-menu-plus"]',
        'div[title="Anexar"]',
        'div[aria-label="Anexar"]'
    ],
    MENU_ITEMS: {
        DOCUMENT: [
            '[data-testid="attach-document"]',
            'span[data-icon="attach-document"]'
        ],
        IMAGE: [
            '[data-testid="attach-image"]',
            'span[data-icon="attach-image"]'
        ]
    }
};

```

### `scripts/sidebar.css`

```css
:root {
    --nw-bg-dark: #030304;
    --nw-bg-card: rgba(18, 18, 24, 0.6);
    --nw-primary: #ff1f4b;
    --nw-primary-hover: #ff3d63;
    --nw-accent: #00e699;
    --nw-text: #ffffff;
    --nw-text-muted: #8b8b95;

    --nw-border: rgba(255, 255, 255, 0.08);
    --nw-border-hover: rgba(255, 255, 255, 0.15);

    /* Glass */
    --glass-bg: rgba(20, 20, 25, 0.7);
    --glass-blur: blur(20px);

    /* Dimensions */
    --rad-sm: 8px;
    --rad-md: 14px;
    --rad-lg: 20px;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    background: transparent;
    font-family: 'Inter', -apple-system, sans-serif;
    color: var(--nw-text);
}

.hidden {
    display: none !important;
}

/* === TYPOGRAPHY RESET (FORCE VISIBILITY) === */
.nw-container h1,
.nw-container h2,
.nw-container h3,
.nw-container h4,
.nw-container h5,
.nw-container h6,
.nw-container p,
.nw-container span,
.nw-container div,
.nw-container strong,
.nw-container label,
.nw-container li {
    color: var(--nw-text);
}

.nw-card h1,
.nw-card h2,
.nw-card h3,
.nw-card h4,
.nw-card h5,
.nw-card h6 {
    color: #ffffff !important;
}

.nw-card p,
.nw-card span,
.nw-card div {
    color: var(--nw-text);
}


/* === MAIN CONTAINER === */
.nw-container {
    width: 380px;
    /* Slightly wider for better breathing room */
    height: 100vh;
    background: radial-gradient(circle at top right, #1a0b0e 0%, #030304 60%);
    border-left: 1px solid var(--nw-border);
    display: flex;
    flex-direction: column;
    box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
    transition: transform 0.3s ease;
}

/* === HEADER === */
.nw-header {
    height: 70px;
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--nw-border);
    z-index: 50;
}

.nw-logo {
    display: flex;
    align-items: center;
    gap: 12px;
}

.nw-logo-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--nw-primary), #ff4d6d);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 15px rgba(255, 31, 75, 0.3);
}

.nw-logo-text {
    font-weight: 700;
    font-size: 15px;
    letter-spacing: -0.3px;
}

.nw-header-actions {
    display: flex;
    gap: 8px;
}

/* === SCROLL CONTENT === */
.nw-scroll-area {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
}

/* === CARDS & SECTIONS === */
.nw-card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--nw-border);
    border-radius: var(--rad-lg);
    padding: 20px;
    margin-bottom: 24px;
}

.nw-section {
    margin-bottom: 24px;
}

.nw-label-caps {
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    color: var(--nw-primary);
    margin-bottom: 12px;
    display: block;
    letter-spacing: 1px;
}

/* === INPUTS === */
input,
select,
textarea {
    width: 100%;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--nw-border);
    border-radius: var(--rad-sm);
    padding: 12px 14px;
    color: var(--nw-text);
    font-size: 13px;
    outline: none;
    transition: all 0.2s;
    font-family: inherit;
}

input:hover,
select:hover,
textarea:hover {
    border-color: var(--nw-border-hover);
    background: rgba(0, 0, 0, 0.4);
}

input:focus,
select:focus,
textarea:focus {
    border-color: var(--nw-primary);
    background: rgba(0, 0, 0, 0.5);
    box-shadow: 0 0 0 3px rgba(255, 31, 75, 0.1);
}

/* === BUTTONS === */
.nw-btn {
    width: 100%;
    border: none;
    padding: 10px;
    border-radius: var(--rad-sm);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.nw-btn.primary {
    background: linear-gradient(135deg, var(--nw-primary), #d6133a);
    color: white;
    box-shadow: 0 8px 20px rgba(255, 31, 75, 0.2);
}

.nw-btn.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 25px rgba(255, 31, 75, 0.3);
}

.nw-icon-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.05);
    color: var(--nw-text-muted);
    border: 1px solid var(--nw-border);
    cursor: pointer;
    transition: all 0.2s;
}

.nw-icon-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
}

/* === TABS === */
.nw-tabs {
    display: flex;
    gap: 6px;
    background: rgba(0, 0, 0, 0.3);
    padding: 4px;
    border-radius: 12px;
    margin-bottom: 20px;
    border: 1px solid var(--nw-border);
}

.nw-tab-btn {
    flex: 1;
    padding: 8px;
    background: transparent;
    border: none;
    color: var(--nw-text-muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.nw-tab-btn.active {
    background: var(--nw-bg-card);
    color: var(--nw-primary);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* === STATS & ETA === */
.nw-stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin-bottom: 15px;
}

.nw-stat-item {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--nw-border);
    border-radius: var(--rad-sm);
    padding: 10px;
    text-align: center;
    display: flex;
    flex-direction: column;
}

.nw-stat-item span {
    font-size: 18px;
    font-weight: 800;
}

.nw-stat-item label {
    font-size: 9px;
    text-transform: uppercase;
    color: var(--nw-text-muted);
    margin-top: 4px;
}

.nw-stat-item.green {
    color: var(--nw-accent);
    border-color: rgba(0, 230, 153, 0.2);
}

.nw-stat-item.red {
    color: #ff5252;
    border-color: rgba(255, 82, 82, 0.2);
}

/* === MEDIA & CHIPS === */
.nw-variable-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 10px 0;
}

.nw-chip {
    font-size: 10px;
    padding: 4px 8px;
    background: rgba(255, 31, 75, 0.08);
    color: #ff8fa5;
    border: 1px solid rgba(255, 31, 75, 0.15);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.nw-chip:hover {
    background: rgba(255, 31, 75, 0.2);
    color: white;
}

.nw-media-item {
    background: rgba(0, 0, 0, 0.2);
    border: 1px dashed var(--nw-border);
    padding: 8px;
    border-radius: 8px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
}

.nw-media-item:hover {
    border-color: var(--nw-primary);
    background: rgba(255, 31, 75, 0.05);
}

/* === UTILS === */
::-webkit-scrollbar {
    width: 5px;
}

::-webkit-scrollbar-thumb {
    background: #333;
    border-radius: 5px;
}

/* === SKELETONS === */
.skeleton-header {
    height: 30px;
    width: 60%;
    background: linear-gradient(90deg, #1a1a20 25%, #2a2a35 50%, #1a1a20 75%);
    background-size: 200% 100%;
    animation: loading 1.5s infinite;
    border-radius: 8px;
    margin-bottom: 20px;
}

.skeleton-line {
    height: 12px;
    width: 100%;
    background: linear-gradient(90deg, #1a1a20 25%, #2a2a35 50%, #1a1a20 75%);
    background-size: 200% 100%;
    animation: loading 1.5s infinite;
    border-radius: 4px;
    margin-bottom: 12px;
}

@keyframes loading {
    0% {
        background-position: 200% 0;
    }

    100% {
        background-position: -200% 0;
    }
}

/* === AUTOMATION QUEUE === */
.nw-badge-counter {
    position: absolute;
    top: -5px;
    right: -5px;
    background: var(--nw-primary);
    color: white;
    font-size: 10px;
    font-weight: 800;
    min-width: 16px;
    height: 16px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    box-shadow: 0 2px 5px rgba(255, 31, 75, 0.4);
    border: 2px solid #000;
}

.nw-badge-counter.hidden {
    display: none;
}

.automation-item {
    transition: transform 0.2s;
}

.automation-item:hover {
    transform: scale(1.02);
}

.nw-empty-state {
    text-align: center;
    padding: 30px 0;
    opacity: 0.5;
    font-size: 13px;
}

/* === TOAST ANIMATIONS === */
@keyframes nw-slide-in {
    from { transform: translateX(120%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

@keyframes nw-slide-out {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(120%); opacity: 0; }
}

/* === QUEUE LIST STYLES === */
.nw-q-item {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: transparent;
    transition: background 0.2s;
    cursor: default;
}

.nw-q-item:hover {
    background: rgba(255,255,255,0.02);
}

.nw-q-item.active {
    background: rgba(255, 31, 75, 0.05);
    border-left: 2px solid var(--nw-primary);
}

.nw-q-status {
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255,255,255,0.05);
}

.nw-q-status.PENDENTE { color: var(--nw-text-muted); }
.nw-q-status.ENVIADO { color: var(--nw-accent); background: rgba(0, 230, 153, 0.1); }
.nw-q-status.FALHOU { color: var(--nw-primary); background: rgba(255, 31, 75, 0.1); }

/* === TAG CHIPS === */
.nw-tag-chip {
    font-size: 10px;
    padding: 2px 8px;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--nw-border);
    border-radius: 10px;
    color: var(--nw-text-secondary);
}
```

### `scripts/sidebar.html`

```html
<div class="nw-container">
    <!-- Premium Header -->
    <div class="nw-header">
        <div class="nw-logo">
            <div class="nw-logo-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M13 3L21 11M21 11L13 19M21 11H3" stroke="white" stroke-width="3" stroke-linecap="round"
                        stroke-linejoin="round" />
                </svg>
            </div>
            <span>NorthWay <b>CRM</b></span>
        </div>
        <div class="nw-header-actions">
            <div class="nw-status-badge">
                <span id="nw-connection-status" class="status-dot connected"></span>
                <span>Online</span>
            </div>
            <button id="nw-btn-nav-broadcast" class="nw-icon-btn" title="Disparo Assistido">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
            </button>
            <button id="nw-btn-nav-automation" class="nw-icon-btn" title="Automações Pendentes">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <span id="nw-automation-badge" class="nw-badge-counter hidden">0</span>
            </button>
            <button id="nw-btn-settings" class="nw-icon-btn" title="Configurações">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path
                        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
            </button>
        </div>
    </div>

    <!-- Scrollable content area -->
    <div class="nw-scroll-area">
        <!-- Content State: Idle -->
        <div id="nw-state-idle" class="nw-state">
            <div style="text-align: center; margin-bottom: 24px; padding-top: 20px;">
                <h2 style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">Bem-vindo ao ZapWay</h2>
                <p style="color: var(--nw-text-muted); font-size: 13px;">Selecione um contato para começar ou utilize os
                    atalhos abaixo.</p>
            </div>

            <!-- Dashboard Stats -->
            <div class="nw-card" style="margin-bottom: 24px;">
                <h3
                    style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--nw-text-secondary); margin-bottom: 12px; letter-spacing: 0.5px;">
                    Seu Desempenho Hoje</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div
                        style="background: rgba(var(--nw-primary-rgb), 0.1); padding: 12px; border-radius: 8px; border: 1px solid rgba(var(--nw-primary-rgb), 0.2);">
                        <div style="font-size: 24px; font-weight: 700; color: var(--nw-primary); margin-bottom: 4px;"
                            id="nw-idle-stat-sent">0</div>
                        <div style="font-size: 11px; color: var(--nw-text-muted);">Mensagens de Disparo</div>
                    </div>
                    <div
                        style="background: rgba(16, 185, 129, 0.1); padding: 12px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.2);">
                        <div style="font-size: 24px; font-weight: 700; color: #10b981; margin-bottom: 4px;"
                            id="nw-idle-stat-crm">0</div>
                        <div style="font-size: 11px; color: var(--nw-text-muted);">Adicionados ao CRM</div>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="nw-card">
                <h3
                    style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--nw-text-secondary); margin-bottom: 12px; letter-spacing: 0.5px;">
                    Ações Rápidas</h3>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="nw-btn primary" onclick="document.getElementById('nw-btn-nav-broadcast').click()"
                        style="width: 100%; justify-content: center;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" style="margin-right: 8px;">
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                        Novo Disparo Assistido
                    </button>
                    <button class="nw-btn" onclick="document.getElementById('nw-btn-settings').click()"
                        style="width: 100%; justify-content: center; background: rgba(255,255,255,0.05);">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" style="margin-right: 8px;">
                            <circle cx="12" cy="12" r="3" />
                            <path
                                d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                        </svg>
                        Configurações do CRM
                    </button>
                </div>
            </div>
        </div>

        <!-- Content State: Loading -->
        <div id="nw-state-loading" class="nw-state hidden">
            <div class="skeleton-header"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line" style="width: 70%"></div>
        </div>

        <!-- Content State: New Lead (COLAPSADO POR PADRÃO) -->
        <div id="nw-state-new" class="nw-state hidden">
            <div class="nw-profile">
                <div class="nw-avatar" id="nw-contact-avatar">
                    <img id="nw-contact-img" src="" class="hidden" alt="Avatar">
                    <span id="nw-contact-initials">NW</span>
                </div>
                <h2 id="nw-contact-name-new">Nome do Contato</h2>
                <p id="nw-contact-phone-new" style="font-size: 12px; color: var(--nw-text-muted);"></p>
                <span class="badge"
                    style="background: rgba(255,193,7,0.15); color: #ffc107; border: 1px solid rgba(255,193,7,0.2);">
                    Não cadastrado
                </span>
            </div>

            <!-- Card colapsado: só botão de ação -->
            <div id="nw-new-collapsed" class="nw-card">
                <p style="font-size: 12px; color: var(--nw-text-muted); margin-bottom: 14px; line-height: 1.5;">
                    Este contato ainda não está no CRM.
                </p>
                <button id="nw-btn-open-form" class="nw-btn primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        stroke-width="2.5">
                        <path d="M12 5v14M5 12h14" />
                    </svg>
                    Adicionar ao CRM
                </button>
            </div>

            <!-- Formulário expandido (hidden por padrão) -->
            <div id="nw-new-form" class="hidden">
                <div class="nw-card">
                    <div class="nw-field">
                        <label>Nome do Contato</label>
                        <input type="text" id="nw-new-name" placeholder="Nome Completo">
                    </div>
                    <div class="nw-field-row">
                        <div class="nw-field">
                            <label>Telefone</label>
                            <input type="text" id="nw-new-phone" placeholder="Detectado automaticamente">
                        </div>
                        <div class="nw-field">
                            <label>Etapa</label>
                            <select id="nw-new-stage">
                                <option>Carregando...</option>
                            </select>
                        </div>
                    </div>
                    <div class="nw-field">
                        <label>E-mail</label>
                        <input type="email" id="nw-new-email" placeholder="cliente@exemplo.com">
                    </div>
                    <!-- Origem do lead -->
                    <div class="nw-field">
                        <label>Origem</label>
                        <select id="nw-new-source">
                            <option value="">Selecione...</option>
                            <option value="whatsapp">WhatsApp Orgânico</option>
                            <option value="google_ads">Google Ads</option>
                            <option value="meta_ads">Meta Ads</option>
                            <option value="instagram">Instagram Orgânico</option>
                            <option value="indicacao">Indicação</option>
                            <option value="site">Site</option>
                            <option value="outro">Outro</option>
                        </select>
                    </div>
                    <div class="nw-field">
                        <label>Observações</label>
                        <textarea id="nw-new-notes" rows="3" placeholder="Notas sobre o atendimento..."></textarea>
                    </div>

                    <button id="nw-btn-create" class="nw-btn primary">
                        Cadastrar no CRM
                    </button>
                    <button id="nw-btn-cancel-form" class="nw-btn"
                        style="margin-top: 8px; background: rgba(255,255,255,0.04); border: 1px solid var(--nw-border);">
                        Cancelar
                    </button>
                </div>
            </div>
        </div>

        <!-- Content State: Existing Contact -->
        <div id="nw-state-contact" class="nw-state hidden">
            <div class="nw-profile">
                <div class="nw-avatar" id="nw-contact-avatar">
                    <img id="nw-contact-img" src="" class="hidden" alt="Avatar">
                    <span id="nw-contact-initials">NW</span>
                </div>
                <h2 id="nw-contact-name">Nome do Contato</h2>
                <p id="nw-contact-phone">+55 11 99999-9999</p>
                <div style="min-height: 18px; margin-top: 4px;">
                    <span id="nw-contact-online-status"
                        style="font-size: 11px; color: var(--nw-success); font-weight: 500; display: none;">Online</span>
                </div>
                <div id="nw-contact-tags"
                    style="display: flex; gap: 4px; flex-wrap: wrap; margin-top: 8px; justify-content: center;">
                    <!-- Tags injetadas aqui -->
                </div>
                <span id="nw-contact-status" class="badge">Novo</span>
            </div>

            <div class="nw-card">
                <div class="nw-field">
                    <label>Etapa do Funil</label>
                    <select id="nw-input-stage">
                        <option value="">Carregando...</option>
                    </select>
                </div>

                <div class="nw-field">
                    <label>Observações</label>
                    <textarea id="nw-input-notes" rows="4"></textarea>
                </div>

                <div class="nw-field" style="margin-top: -10px; margin-bottom: 15px;">
                    <label style="font-size: 10px; opacity: 0.8;">Nota Rápida</label>
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="nw-quick-note" placeholder="Adicionar nota..."
                            style="flex: 1; padding: 6px; font-size: 12px;">
                        <button id="nw-btn-quick-note" class="nw-btn primary" style="padding: 6px 10px;">
                            Add
                        </button>
                    </div>
                </div>

                    <button id="nw-btn-save" class="nw-btn primary">Salvar Alterações</button>
                    <div style="display: flex; gap: 8px; margin-top: 10px;">
                        <button id="nw-btn-direct-send" class="nw-btn" style="flex: 1; background: rgba(0, 230, 153, 0.1); color: var(--nw-accent); border: 1px solid rgba(0, 230, 153, 0.2); text-transform: none;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px;">
                                <line x1="22" y1="2" x2="11" y2="13"></line>
                                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                            </svg>
                            Enviar Direto
                        </button>
                        <a href="#" id="nw-link-crm" target="_blank" class="nw-btn" style="flex: 1; background: rgba(255,255,255,0.05); color: #fff; text-transform: none; border: 1px solid var(--nw-border);">Ver no CRM ↗</a>
                    </div>
            </div>
        </div>

        <!-- Content State: Group Export -->
        <div id="nw-state-group" class="nw-state hidden">
            <div class="nw-card">
                <h3>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                        stroke-linecap="round" stroke-linejoin="round" style="color: var(--nw-primary);">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                    </svg>
                    Grupo Detectado
                </h3>
                <h2 id="nw-group-name" style="font-size: 18px; font-weight: 800; margin: 10px 0 20px;">Nome do Grupo
                </h2>

                <div id="nw-export-progress" class="hidden" style="margin-bottom: 20px;">
                    <p id="nw-export-status"
                        style="font-size: 11px; color: var(--nw-text-secondary); margin-bottom: 8px;">
                        Extraindo... 0/0
                    </p>
                    <div class="nw-progress-track">
                        <div id="nw-progress-fill" style="width: 0%" class="nw-progress-fill"></div>
                    </div>
                </div>

                <button id="nw-btn-export" class="nw-btn primary">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                        stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Exportar Participantes
                </button>
            </div>
        </div>

        <!-- Premium Templates Section (Unified) -->
        <div id="nw-templates-container" class="hidden" style="padding: 0 20px; margin-bottom: 20px;">
            <div class="nw-templates-section">
                <div class="nw-section-header">
                    <h4>Modelos de Mensagem</h4>
                    <a href="#" class="nw-link-all">Ver Todos</a>
                </div>

                <div class="nw-template-card">
                    <div class="nw-template-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                        </svg>
                    </div>
                    <div class="nw-template-info">
                        <strong>Saudação Inicial Premium</strong>
                        <p>Olá! Seja bem-vindo à NorthWay...</p>
                    </div>
                    <span class="nw-template-badge">12</span>
                </div>

                <div class="nw-template-card">
                    <div class="nw-template-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                        </svg>
                    </div>
                    <div class="nw-template-info">
                        <strong>Envio de Orçamento</strong>
                        <p>Segue anexo a proposta detalhada...</p>
                    </div>
                    <span class="nw-template-badge">8</span>
                </div>
            </div>
        </div>

        <!-- Content State: Broadcast Dashboard -->
        <div id="nw-state-broadcast" class="nw-state hidden">
            <div class="nw-broadcast-header">
                <h3>Disparo Assistido</h3>
                <button id="nw-btn-close-broadcast" class="nw-icon-btn">✕</button>
            </div>

            <div id="nw-broadcast-setup">
                <!-- Step 1: Import -->
                <div class="nw-card">
                    <label class="nw-label-caps">1. Importar Contatos</label>
                    <textarea id="nw-broadcast-import-text" rows="3" style="margin-top: 10px; font-size: 11px;"
                        placeholder="Nome;Telefone;Variavel"></textarea>
                    <label for="nw-broadcast-import-file" class="nw-btn"
                        style="background: rgba(255,255,255,0.05); margin-top: 10px; border: 1px solid var(--nw-border); text-transform: none; cursor: pointer; padding: 10px; font-size: 11px;">
                        📁 Carregar CSV (Importação em Massa)
                    </label>
                    <input type="file" id="nw-broadcast-import-file" accept=".csv" class="hidden">
                </div>

                <!-- Step 2: Safety Controls -->
                <div class="nw-card">
                    <label class="nw-label-caps">2. Controles de Segurança (Anti-Ban)</label>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                        <div class="nw-field">
                            <label style="font-size: 10px; opacity: 0.7;">Delay Mín (s)</label>
                            <input type="number" id="nw-delay-min" value="10" min="1">
                        </div>
                        <div class="nw-field">
                            <label style="font-size: 10px; opacity: 0.7;">Delay Máx (s)</label>
                            <input type="number" id="nw-delay-max" value="20" min="2">
                        </div>
                        <div class="nw-field">
                            <label style="font-size: 10px; opacity: 0.7;">Lote (msgs)</label>
                            <input type="number" id="nw-batch-size" value="10" min="0">
                        </div>
                        <div class="nw-field">
                            <label style="font-size: 10px; opacity: 0.7;">Pausa Lote (s)</label>
                            <input type="number" id="nw-batch-wait" value="60" min="0">
                        </div>
                    </div>
                </div>

                <!-- Step 3: Message Models (A/B/C) -->
                <div class="nw-card">
                    <label class="nw-label-caps" style="margin-bottom: 12px;">3. Modelos de Mensagem (Rotação)</label>

                    <div class="nw-tabs">
                        <button class="nw-tab-btn active" data-tab="A">Modelo A</button>
                        <button class="nw-tab-btn" data-tab="B">Modelo B</button>
                        <button class="nw-tab-btn" data-tab="C">Modelo C</button>
                    </div>

                    <div class="nw-variable-chips" style="margin-bottom: 10px">
                        <button class="nw-chip" data-var="{nome}">{nome}</button>
                        <button class="nw-chip" data-var="{telefone}">{tel}</button>
                        <button class="nw-chip" data-var="{email}">{email}</button>
                        <button class="nw-chip" data-var="{interesse}">{interesse}</button>
                        <button class="nw-chip" data-var="{variavel}">{variavel}</button>
                    </div>

                    <textarea id="nw-broadcast-template" rows="5" placeholder="Olá {nome}, tudo bem?"
                        style="margin-top: 5px; font-size: 12px; line-height: 1.5;"></textarea>

                    <p class="nw-hint">A extensão irá rotacionar as mensagens (A -> B -> C) para cada contato da fila.
                    </p>

                    <!-- Media/Attachments Section -->
                    <div class="nw-media-section">
                        <label class="nw-label-caps">Anexar Mídia (Opcional)</label>
                        <div class="nw-media-grid">
                            <div class="nw-media-item" id="nw-btn-attach-img">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                    <circle cx="8.5" cy="8.5" r="1.5" />
                                    <polyline points="21 15 16 10 5 21" />
                                </svg>
                                <span>Imagem</span>
                                <input type="file" id="nw-attach-img" accept="image/*" class="hidden">
                            </div>
                            <div class="nw-media-item" id="nw-btn-attach-video">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polygon points="23 7 16 12 23 17 23 7" />
                                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                                </svg>
                                <span>Vídeo</span>
                                <input type="file" id="nw-attach-video" accept="video/*" class="hidden">
                            </div>
                            <div class="nw-media-item" id="nw-btn-attach-doc">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                    <polyline points="14 2 14 8 20 8" />
                                </svg>
                                <span>Documento</span>
                                <input type="file" id="nw-attach-doc" accept=".pdf,.doc,.docx,.xls,.xlsx"
                                    class="hidden">
                            </div>
                            <div class="nw-media-item" id="nw-media-clear"
                                style="border-style: solid; color: var(--nw-danger); opacity: 0.5;">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M3 6h18" />
                                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                                </svg>
                                <span>Limpar</span>
                            </div>
                        </div>
                        <div id="nw-media-preview-container" class="nw-hint hidden"
                            style="margin-top: 10px; color: var(--nw-accent);">
                            📎 Arquivo selecionado: <span id="nw-media-filename">...</span>
                            <div style="margin-top: 8px;">
                                <label class="nw-label-caps"
                                    style="font-size: 10px; opacity: 0.8; display: block; margin-bottom: 4px;">Legenda
                                    do Anexo</label>
                                <textarea id="nw-media-caption" class="nw-input"
                                    placeholder="Opcional: Digite uma legenda exclusiva para o arquivo..."
                                    style="height: 60px; font-size: 11px; width: 100%; box-sizing: border-box;"></textarea>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Final Actions -->
                <div class="nw-card">
                    <div class="nw-warning-box">
                        <input type="checkbox" id="nw-broadcast-auto">
                        <label for="nw-broadcast-auto">Envio Automático (Disparo em Massa)</label>
                    </div>

                    <button id="nw-btn-start-broadcast" class="nw-btn primary">
                        🚀 Iniciar Disparo
                    </button>
                    <p class="nw-hint" style="text-align: center; margin-top: 10px;">Lembre-se de não abusar da
                        velocidade para evitar banimentos.</p>
                </div>
            </div>

            <div id="nw-broadcast-active" class="hidden">
                <div class="nw-stats-grid">
                    <div class="nw-stat-item">
                        <span id="nw-stat-pending">0</span>
                        <label>Fila</label>
                    </div>
                    <div class="nw-stat-item green">
                        <span id="nw-stat-sent">0</span>
                        <label>Enviados</label>
                    </div>
                    <div class="nw-stat-item red">
                        <span id="nw-stat-failed">0</span>
                        <label>Falhas</label>
                    </div>
                    <div class="nw-stat-item"
                        style="grid-column: span 3; margin-top: 10px; background: rgba(255, 193, 7, 0.15); border: 1px solid rgba(255, 193, 7, 0.4); padding: 10px; flex-direction: row; gap: 10px; justify-content: center; border-radius: 8px;">
                        <label style="font-size: 13px; margin: 0; color: #ffecb3;">⏱️ Tempo Estimado:</label>
                        <span id="nw-stat-eta"
                            style="font-size: 16px; font-weight: 800; color: #ffeb3b; text-shadow: 0 0 8px rgba(255, 193, 7, 0.3);">--:--</span>
                    </div>
                </div>

                <!-- Progress Bar Section -->
                <div id="nw-progress-section" class="hidden" style="margin: 15px 0;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                        <span style="font-size: 11px; color: var(--nw-text-secondary);">Próximo envio em...</span>
                        <span id="nw-countdown-text" style="font-size: 11px; font-weight: 700; color: var(--nw-primary);">0s</span>
                    </div>
                    <div class="nw-progress-track" style="height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                        <div id="nw-progress-fill" style="width: 0%; height: 100%; background: var(--nw-primary); transition: width 0.1s linear;"></div>
                    </div>
                </div>

                <div class="nw-card">
                    <strong id="nw-bc-current-name">...</strong>
                    <span id="nw-bc-current-phone"
                        style="display: block; font-size: 11px; color: #6b7280; margin: 4px 0 12px;"></span>
                    <div class="nw-message-preview" id="nw-bc-message-preview">Carregando...</div>
                </div>

                <!-- Queue List Section -->
                <div class="nw-card" style="padding: 0; overflow: hidden; display: flex; flex-direction: column; max-height: 300px;">
                    <div style="padding: 12px; border-bottom: 1px solid var(--nw-border); display: flex; justify-content: space-between; align-items: center;">
                        <span id="nw-bc-queue-counter" style="font-size: 11px; font-weight: 600;">0 contatos</span>
                        <input type="text" id="nw-bc-search" placeholder="Buscar na fila..." style="width: 120px; font-size: 10px; padding: 4px 8px; background: rgba(255,255,255,0.05); border: 1px solid var(--nw-border); border-radius: 4px; color: white;">
                    </div>
                    <div id="nw-bc-queue-list" style="overflow-y: auto; flex: 1;">
                        <!-- List items added by JS -->
                    </div>
                </div>

                <div class="nw-broadcast-controls" style="margin-top: 15px;">
                    <button id="nw-btn-bc-stop" class="nw-btn"
                        style="background: rgba(255, 31, 75, 0.1); color: var(--nw-primary); border: 1px solid rgba(255, 31, 75, 0.2); text-transform: none; margin-bottom: 10px; width: 100%;">
                        Parar Disparo
                    </button>
                    <div style="display: flex; gap: 10px; width: 100%; margin-bottom: 10px;">
                        <button id="nw-btn-bc-pause" class="nw-btn"
                            style="flex: 1; background: rgba(255, 193, 7, 0.15); color: #ffeb3b; border: 1px solid rgba(255, 193, 7, 0.4); text-transform: none;">
                            ⏸ Pausar Lote
                        </button>
                    </div>
                    <div style="display: flex; gap: 10px; width: 100%;">
                        <button id="nw-btn-bc-skip" class="nw-btn"
                            style="flex: 1; background: rgba(255,255,255,0.05); text-transform: none;">Pular</button>
                        <button id="nw-btn-bc-confirm" class="nw-btn primary" style="flex: 2;">Enviar Agora</button>
                    </div>
                </div>
            </div>
        </div>
        <!-- Content State: Automation Queue -->
        <div id="nw-state-automation" class="nw-state hidden">
            <div class="nw-broadcast-header">
                <h3>Automações Pendentes</h3>
                <button id="nw-btn-close-automation" class="nw-icon-btn">✕</button>
            </div>

            <div style="padding: 15px;">
                <p style="font-size: 12px; color: var(--nw-text-muted); margin-bottom: 15px;">
                    As mensagens abaixo foram geradas automaticamente baseadas no funil do CRM.
                    Revise e envie manualmente para manter o atendimento pessoal.
                </p>

                <div id="nw-automation-list" style="display: flex; flex-direction: column; gap: 12px;">
                    <!-- Items will be injected here -->
                    <div class="nw-empty-state" style="text-align: center; padding: 40px 20px;">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="1" style="opacity: 0.3; margin-bottom: 15px;">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                        <p style="font-size: 13px; color: var(--nw-text-muted);">Tudo em dia! Nenhuma automação
                            pendente.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

### `scripts/sidebar_ui.js`

```js
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

        response.forEach(tpl => {
            const card = document.createElement('div');
            card.className = 'nw-template-card';
            card.style.position = 'relative';
            card.innerHTML = `
                <div class="nw-template-icon" style="background: rgba(99,102,241,0.1); color: #818cf8;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                </div>
                <div class="nw-template-info">
                    <strong>${tpl.title}</strong>
                    <p>${tpl.content.substring(0, 60)}${tpl.content.length > 60 ? '...' : ''}</p>
                </div>
                <button class="nw-btn-direct-send-tpl" title="Disparo Direto" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); width: 28px; height: 28px; border-radius: 6px; border: none; background: rgba(0, 230, 153, 0.1); color: var(--nw-accent); cursor: pointer; display: flex; align-items: center; justify-content: center; z-index: 10;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            `;
            
            // Fill textarea
            card.onclick = (e) => {
                if (e.target.closest('.nw-btn-direct-send-tpl')) return;
                const ta = getEl('nw-broadcast-template') || getEl('nw-input-notes') || getEl('nw-new-notes');
                if (ta) {
                    ta.value = tpl.content;
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            };

            // Direct Send
            const btn = card.querySelector('.nw-btn-direct-send-tpl');
            btn.onclick = (e) => {
                e.stopPropagation();
                sendSingleMessage(NWState.currentPhone, tpl.content);
            };

            section.appendChild(card);
        });
    } catch (e) {
        nwLog("Template load error", e);
    }
}

/**
 * Handle Single Message Send (Direct Send)
 */
async function sendSingleMessage(contactId, message, mediaKey = null) {
    if (!contactId) {
        toast("Selecione um contato primeiro", "warning");
        return;
    }
    if (!message || message.trim() === '') {
        toast("Digite uma mensagem primeiro", "warning");
        return;
    }

    try {
        toast("Enviando mensagem direta...", "info", 2000);
        
        // Use active media if specified (from state)
        let media = null;
        if (mediaKey) media = await NWDB.getFile(mediaKey);
        
        const success = await BroadcastEngine.sendDirectMessage(contactId, message, media);
        
        if (success) {
            toast("Mensagem enviada com sucesso!", "success");
            sendMsg({ action: "INCREMENT_SENT" });
        } else {
            toast("Falha ao enviar mensagem direta.", "error");
        }
    } catch (e) {
        nwLog("Direct send failed", e);
        toast("Erro ao processar envio direto.", "error");
    }
}

```

### `scripts/state.js`

```js
/**
 * ZapWay Global State & Persistence
 */

const NWState = {
    shadowRoot: null,
    currentPhone: null,
    currentLeadId: null,
    isSidebarCollapsed: false,
    contactName: null,
    contactPhone: null,
    reset() {
        this.currentPhone = null;
        this.currentLeadId = null;
        this.contactName = null;
        this.contactPhone = null;
    }
};

/**
 * Persistence Helper (NWDB)
 */
const NWDB = {
    name: "NorthWayDB", 
    store: "files", 
    db: null,
    async init() {
        if (this.db) return this.db;
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(this.name, 1);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(this.store)) {
                    db.createObjectStore(this.store);
                }
            };
            req.onsuccess = (e) => { 
                this.db = e.target.result; 
                resolve(this.db); 
            };
            req.onerror = (e) => reject(e);
        });
    },
    async saveFile(key, file) {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const req = tx.objectStore(this.store).put(file, key);
            req.onsuccess = () => r();
            req.onerror = () => j();
        });
    },
    async getFile(key) {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readonly");
            const req = tx.objectStore(this.store).get(key);
            req.onsuccess = (e) => r(e.target.result);
            req.onerror = () => j();
        });
    },
    async clear() {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const req = tx.objectStore(this.store).clear();
            req.onsuccess = () => r();
            req.onerror = () => j();
        });
    }
};

```

