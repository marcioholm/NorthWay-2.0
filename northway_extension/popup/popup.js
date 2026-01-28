document.addEventListener('DOMContentLoaded', async () => {
    // --- TABS LOGIC ---
    const tabLogin = document.getElementById('tab-login');
    const tabSettings = document.getElementById('tab-settings');
    const viewLogin = document.getElementById('view-login');
    const viewSettings = document.getElementById('view-settings');

    tabLogin.addEventListener('click', () => {
        viewLogin.classList.remove('hidden');
        viewSettings.classList.add('hidden');
        tabLogin.style.fontWeight = 'bold';
        tabLogin.style.color = '#000';
        tabSettings.style.fontWeight = 'normal';
        tabSettings.style.color = '#666';
    });

    tabSettings.addEventListener('click', () => {
        viewLogin.classList.add('hidden');
        viewSettings.classList.remove('hidden');
        tabSettings.style.fontWeight = 'bold';
        tabSettings.style.color = '#000';
        tabLogin.style.fontWeight = 'normal';
        tabLogin.style.color = '#666';
    });

    // --- AUTH & INIT ---
    // Check Auth
    const res = await chrome.runtime.sendMessage({ action: "CHECK_AUTH" });
    if (res.token) {
        chrome.storage.local.get('user', (data) => {
            if (data.user) showProfile(data.user);
        });
    }

    // Load Settings
    chrome.storage.local.get(['minDelay', 'maxDelay', 'dailyLimit'], (data) => {
        if (data.minDelay) document.getElementById('setting-min-delay').value = data.minDelay;
        if (data.maxDelay) document.getElementById('setting-max-delay').value = data.maxDelay;
        if (data.dailyLimit) document.getElementById('setting-daily-limit').value = data.dailyLimit;
    });

    // --- ACTIONS ---
    document.getElementById('btn-login').addEventListener('click', async () => {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const errorEl = document.getElementById('error-msg');

        errorEl.classList.add('hidden');
        document.getElementById('btn-login').textContent = "Entrando...";

        const response = await chrome.runtime.sendMessage({
            action: "LOGIN",
            email,
            password
        });

        if (response.success) {
            showProfile(response.user);
        } else {
            errorEl.textContent = response.error;
            errorEl.classList.remove('hidden');
            document.getElementById('btn-login').textContent = "Entrar";
        }
    });

    document.getElementById('btn-logout').addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ action: "LOGOUT" });
        location.reload();
    });

    document.getElementById('btn-save-settings').addEventListener('click', () => {
        const minDelay = parseInt(document.getElementById('setting-min-delay').value);
        const maxDelay = parseInt(document.getElementById('setting-max-delay').value);
        const dailyLimit = parseInt(document.getElementById('setting-daily-limit').value);

        if (minDelay < 1 || maxDelay < minDelay) {
            alert("Intervalos inválidos!");
            return;
        }

        chrome.storage.local.set({
            minDelay,
            maxDelay,
            dailyLimit
        }, () => {
            const msg = document.getElementById('settings-msg');
            msg.style.display = 'block';
            setTimeout(() => msg.style.display = 'none', 2000);

            // Notify background to update live settings
            chrome.runtime.sendMessage({ action: "UPDATE_SETTINGS" });
        });
    });
});

function showProfile(user) {
    document.getElementById('login-form').classList.add('hidden');
    document.getElementById('profile-view').classList.remove('hidden');
    document.getElementById('user-name').textContent = user.name;
    document.getElementById('user-email').textContent = user.email;
}
