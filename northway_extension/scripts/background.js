// Background Service Worker
// Handles API requests to avoid CORS issues in content scripts if possible, 
// and manages Auth Token.

// const API_BASE = "https://north-way-2-0.vercel.app/api/ext";
const API_BASE = "http://127.0.0.1:5001/api/ext"; // Dev Mode

// Listen for messages from Content Script or Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    if (request.action === "LOGIN") {
        login(request.email, request.password).then(sendResponse);
        return true; // Keep channel open for async response
    }

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
    const token = await getToken();
    if (!token) return { error: "Unauthorized" };

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

        // Handle 404 cleanly
        if (response.status === 404) return { found: false };

        if (!response.ok) {
            return { error: `Server error: ${response.status}` };
        }

        return await response.json();
    } catch (e) {
        return { error: e.message };
    }
}
