document.addEventListener('DOMContentLoaded', async () => {
    const getEl = (id) => document.getElementById(id);

    // --- NAVIGATION / VIEW LOGIC ---
    const showState = (state) => {
        const authView = getEl('nw-view-auth');
        const settingsView = getEl('nw-view-settings');

        if (state === 'settings') {
            settingsView.classList.remove('hidden');
        } else {
            settingsView.classList.add('hidden');
            authView.classList.remove('hidden');
        }
    };

    getEl('nw-btn-settings-toggle').addEventListener('click', () => showState('settings'));
    getEl('nw-btn-settings-back').addEventListener('click', () => showState('auth'));

    // --- SSO JUMP LOGIC ---
    const adminLink = document.querySelector('a[href*="crm.northwaycompany.com.br/home"]');
    if (adminLink) {
        adminLink.addEventListener('click', async (e) => {
            e.preventDefault();
            const storage = await chrome.storage.local.get('authToken');
            if (storage.authToken) {
                const ssoUrl = `https://crm.northwaycompany.com.br/api/ext/sso-jump?token=${storage.authToken}`;
                window.open(ssoUrl, '_blank');
            } else {
                window.open('https://crm.northwaycompany.com.br/login', '_blank');
            }
        });
    }

    // --- AUTH & INIT ---
    const checkAuth = async () => {
        const res = await chrome.runtime.sendMessage({ action: "CHECK_AUTH" });
        if (res.token) {
            chrome.storage.local.get('user', (data) => {
                if (data.user) renderProfile(data.user);
            });
        } else {
            getEl('nw-login-form').classList.remove('hidden');
            getEl('nw-profile-view').classList.add('hidden');
        }
    };

    const renderProfile = (user) => {
        getEl('nw-login-form').classList.add('hidden');
        getEl('nw-profile-view').classList.remove('hidden');

        getEl('nw-user-name').textContent = user.name;
        getEl('nw-user-email').textContent = user.email;

        // Avatar Logic
        const img = getEl('nw-user-img');
        const initialsEl = getEl('nw-user-initials');

        if (user.avatar_url) {
            img.src = user.avatar_url;
            img.classList.remove('hidden');
            initialsEl.classList.add('hidden');

            // Handle image load error
            img.onerror = () => {
                img.classList.add('hidden');
                initialsEl.classList.remove('hidden');
            };
        } else {
            const initials = user.name ? user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'NW';
            initialsEl.textContent = initials;
            img.classList.add('hidden');
            initialsEl.classList.remove('hidden');
        }
    };

    // Load Live Settings
    chrome.storage.local.get(['minDelay', 'maxDelay', 'dailyLimit'], (data) => {
        if (data.minDelay) getEl('nw-setting-min').value = data.minDelay;
        if (data.maxDelay) getEl('nw-setting-max').value = data.maxDelay;
        if (data.dailyLimit) getEl('nw-setting-limit').value = data.dailyLimit;
    });

    // --- ACTIONS ---
    getEl('nw-btn-login').addEventListener('click', async () => {
        const email = getEl('nw-email').value;
        const password = getEl('nw-password').value;
        const errorEl = getEl('nw-error-msg');
        const btn = getEl('nw-btn-login');

        errorEl.classList.add('hidden');
        btn.textContent = "Autenticando...";
        btn.disabled = true;

        try {
            const response = await chrome.runtime.sendMessage({
                action: "LOGIN",
                email,
                password
            });

            if (response.success) {
                renderProfile(response.user);
            } else {
                errorEl.textContent = response.error || "Erro ao conectar";
                errorEl.classList.remove('hidden');
                btn.textContent = "Acessar Plataforma";
                btn.disabled = false;
            }
        } catch (err) {
            errorEl.textContent = "Servidor indisponível";
            errorEl.classList.remove('hidden');
            btn.textContent = "Acessar Plataforma";
            btn.disabled = false;
        }
    });

    getEl('nw-btn-logout').addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ action: "LOGOUT" });
        location.reload();
    });

    getEl('nw-btn-save-settings').addEventListener('click', () => {
        const minDelay = parseInt(getEl('nw-setting-min').value);
        const maxDelay = parseInt(getEl('nw-setting-max').value);
        const dailyLimit = parseInt(getEl('nw-setting-limit').value);

        if (minDelay < 1 || maxDelay <= minDelay) {
            alert("Intervalos de segurança inválidos!");
            return;
        }

        chrome.storage.local.set({
            minDelay,
            maxDelay,
            dailyLimit
        }, () => {
            const msg = getEl('nw-settings-msg');
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 2500);

            // Notify background
            chrome.runtime.sendMessage({ action: "UPDATE_SETTINGS" });
        });
    });

    // Init
    checkAuth();
});
