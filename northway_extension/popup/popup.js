document.addEventListener('DOMContentLoaded', async () => {
    // Check Auth
    const res = await chrome.runtime.sendMessage({ action: "CHECK_AUTH" });
    if (res.token) {
        // Assume user data is stored too, or just fetch it
        chrome.storage.local.get('user', (data) => {
            if (data.user) showProfile(data.user);
        });
    }

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
});

function showProfile(user) {
    document.getElementById('login-form').classList.add('hidden');
    document.getElementById('profile-view').classList.remove('hidden');
    document.getElementById('user-name').textContent = user.name;
    document.getElementById('user-email').textContent = user.email;
}
