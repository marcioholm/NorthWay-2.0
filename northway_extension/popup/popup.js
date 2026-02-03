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
