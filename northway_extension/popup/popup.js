
document.addEventListener('DOMContentLoaded', async () => {
    // === GLOBALS ===
    const state = {
        user: null,
        token: null,
        pipelines: [],
        selectedFiles: [] // Array of { name, type, content (base64) }
    };

    const els = {
        views: {
            auth: document.getElementById('nw-view-auth'),
            broadcast: document.getElementById('nw-view-broadcast'),
            settings: document.getElementById('nw-view-settings'),
            profile: document.getElementById('nw-view-profile')
        },
        nav: document.getElementById('nw-navbar'),
        inputs: {
            email: document.getElementById('nw-email'),
            password: document.getElementById('nw-password'),
            funnel: document.getElementById('nw-funnel-select'),
            stage: document.getElementById('nw-stage-select'),
            msg: document.getElementById('nw-msg-input'),
            file: document.getElementById('nw-file-input')
        },
        btns: {
            login: document.getElementById('nw-btn-login'),
            start: document.getElementById('nw-btn-start'),
            navs: document.querySelectorAll('.nw-nav-btn')
        },
        lists: {
            attachments: document.getElementById('nw-attachments-list')
        },
        uploadArea: document.getElementById('nw-upload-area')
    };

    // === HELPERS ===
    const showView = (viewName) => {
        Object.values(els.views).forEach(el => el.classList.add('hidden'));
        if (els.views[viewName]) els.views[viewName].classList.remove('hidden');
        
        // Update Nav
        els.btns.navs.forEach(btn => {
            if (btn.dataset.tab === viewName) btn.classList.add('active');
            else btn.classList.remove('active');
        });
    };

    const renderAttachments = () => {
        els.lists.attachments.innerHTML = '';
        state.selectedFiles.forEach((file, idx) => {
            const div = document.createElement('div');
            div.className = 'nw-attachment-item';
            div.innerHTML = `
                <span class="nw-attachment-name">📄 ${file.name}</span>
                <span class="nw-attachment-remove" data-idx="${idx}">✕</span>
            `;
            els.lists.attachments.appendChild(div);
        });
        
        // Re-bind delete
        document.querySelectorAll('.nw-attachment-remove').forEach(el => {
            el.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                state.selectedFiles.splice(idx, 1);
                renderAttachments();
            });
        });
    };
    
    const fileToBase64 = (file) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });

    // === CRM DATA ===
    const loadPipelines = async () => {
        // In a real app, fetch from CRM API. Mocking for MVP based on models.py structure.
        // We can ask background to fetch or fetch directly if CORS allows.
        // Assuming background handles API calls.
        const res = await chrome.runtime.sendMessage({ action: "GET_PIPELINES", token: state.token });
        if (res && res.pipelines) {
            state.pipelines = res.pipelines;
            
            // Render Funnels
            els.inputs.funnel.innerHTML = '<option value="">Selecione um Funil...</option>';
            state.pipelines.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                els.inputs.funnel.appendChild(opt);
            });
        }
    };

    // === LISTENERS ===
    
    // Navigation
    els.btns.navs.forEach(btn => {
        btn.addEventListener('click', () => showView(btn.dataset.tab));
    });

    // Login
    els.btns.login.addEventListener('click', async () => {
        els.btns.login.textContent = "Conectando...";
        const email = els.inputs.email.value;
        const password = els.inputs.password.value;
        
        const response = await chrome.runtime.sendMessage({ action: "LOGIN", email, password });
        
        if (response.success) {
            state.user = response.user;
            state.token = response.token;
            initAuthenticated();
        } else {
            els.btns.login.textContent = "Conectar";
            alert("Erro de login: " + (response.error || "Desconhecido"));
        }
    });

    // Logout
    document.getElementById('nw-btn-logout').addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ action: "LOGOUT" });
        location.reload();
    });

    // Funnel Change
    els.inputs.funnel.addEventListener('change', (e) => {
        const pipelineId = parseInt(e.target.value);
        const pipeline = state.pipelines.find(p => p.id === pipelineId);
        
        els.inputs.stage.innerHTML = '<option value="">Etapa...</option>';
        els.inputs.stage.disabled = true;
        
        if (pipeline && pipeline.stages) {
            pipeline.stages.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                els.inputs.stage.appendChild(opt);
            });
            els.inputs.stage.disabled = false;
        }
    });
    
    // Stage Change -> Count Targets (Mock)
    els.inputs.stage.addEventListener('change', async (e) => {
        const stageId = e.target.value;
        if(stageId) {
             const res = await chrome.runtime.sendMessage({ action: "COUNT_LEADS", stageId, token: state.token });
             document.getElementById('nw-target-info').classList.remove('hidden');
             document.getElementById('nw-target-count').textContent = res.count || 0;
        }
    });

    // Attachments
    els.uploadArea.addEventListener('click', () => els.inputs.file.click());
    
    els.inputs.file.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        for (const f of files) {
            if (f.size > 5 * 1024 * 1024) { // 5MB limit check
                alert(`Arquivo ${f.name} muito grande (Máx 5MB)`);
                continue;
            }
            try {
                const b64 = await fileToBase64(f);
                state.selectedFiles.push({
                    name: f.name,
                    type: f.type,
                    content: b64 // Sending base64 to background
                });
            } catch (err) {
                console.error(err);
            }
        }
        renderAttachments();
        els.inputs.file.value = ''; // Reset
    });

    // Tags Injection
    document.querySelectorAll('.nw-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const val = tag.dataset.var;
            const start = els.inputs.msg.selectionStart;
            const end = els.inputs.msg.selectionEnd;
            const text = els.inputs.msg.value;
            els.inputs.msg.value = text.substring(0, start) + val + text.substring(end);
            els.inputs.msg.focus();
        });
    });

    // START BROADCAST
    els.btns.start.addEventListener('click', async () => {
        const stageId = els.inputs.stage.value;
        const msg = els.inputs.msg.value;
        const minDelay = parseInt(document.getElementById('nw-delay-min').value);
        const maxDelay = parseInt(document.getElementById('nw-delay-max').value);
        
        if (!stageId) return alert('Selecione uma etapa do funil!');
        if (!msg && state.selectedFiles.length === 0) return alert('Defina uma mensagem ou anexo!');

        els.btns.start.textContent = "Iniciando...";
        els.btns.start.disabled = true;

        // Send to Background to start processing
        const campaignData = {
            stageId,
            message: msg,
            files: state.selectedFiles,
            config: { minDelay, maxDelay }
        };

        const res = await chrome.runtime.sendMessage({ 
            action: "START_CAMPAIGN", 
            data: campaignData,
            token: state.token
        });

        if (res.success) {
            alert('Campanha iniciada! Abra o WhatsApp Web e aguarde o assistente.');
            window.close(); // Close popup
        } else {
            alert('Erro ao iniciar: ' + res.error);
            els.btns.start.textContent = "INICIAR DISPARO 🚀";
            els.btns.start.disabled = false;
        }
    });

    // === INIT ===
    const initAuthenticated = async () => {
        els.views.auth.classList.add('hidden');
        els.nav.classList.remove('hidden');
        
        // Setup Profile
        if (state.user) {
            document.getElementById('nw-user-name').textContent = state.user.name;
            document.getElementById('nw-user-email').textContent = state.user.email;
            
            if (state.user.avatar_url) {
                document.getElementById('nw-user-img').src = state.user.avatar_url;
                document.getElementById('nw-user-img').classList.remove('hidden');
                document.getElementById('nw-user-initials').classList.add('hidden');
            }
        }

        showView('broadcast');
        loadPipelines();
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
