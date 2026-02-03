document.addEventListener('DOMContentLoaded', async () => {

    // === CONFIG ===
    const API_URL = "https://crm.northwaycompany.com.br/api/ext";
    // const API_URL = "http://127.0.0.1:5001/api/ext"; // Local Dev Mode (Port 5001)

    // === STATE ===
    const state = {
        token: null,
        user: null,
        scrapedData: null,
        scoreData: null,
        filter: 'todo'
    };

    // === UI ELEMENTS ===
    const els = {
        // Views
        auth: document.getElementById('view-auth'),
        loading: document.getElementById('view-loading'),
        error: document.getElementById('view-error'),
        result: document.getElementById('view-result'),

        // Auth Inputs
        email: document.getElementById('nw-email'),
        pass: document.getElementById('nw-password'),
        btnLogin: document.getElementById('btn-login'),
        authError: document.getElementById('auth-error'),

        // Result Data
        score: document.getElementById('score-circle'),
        name: document.getElementById('company-name'),
        cat: document.getElementById('company-cat'),
        rating: document.getElementById('val-rating'),
        reviews: document.getElementById('val-reviews'),
        photos: document.getElementById('val-photos'),
        list: document.getElementById('problems-list'),

        // Filter Buttons
        btnTodo: document.getElementById('btn-filter-todo'),
        btnDone: document.getElementById('btn-filter-done'),
        countTodo: document.getElementById('count-todo'),
        countDone: document.getElementById('count-done'),

        // Actions
        btnMaps: document.getElementById('btn-open-maps'),
        btnCopy: document.getElementById('btn-copy'),
        btnCRM: document.getElementById('btn-crm')
    };

    // === INIT FLOW ===
    checkAuth().then(isAuth => {
        if (!isAuth) {
            showView('auth');
        } else {
            startScraping();
        }
    });

    // === EVENT LISTENERS ===

    // Filter Logic
    function toggleFilter(newFilter) {
        state.filter = newFilter;

        // Update Buttons
        if (state.filter === 'todo') {
            if (els.btnTodo) els.btnTodo.classList.add('active');
            if (els.btnDone) els.btnDone.classList.remove('active');
        } else {
            if (els.btnTodo) els.btnTodo.classList.remove('active');
            if (els.btnDone) els.btnDone.classList.add('active');
        }

        renderDiagnosis();
    }

    if (els.btnTodo) els.btnTodo.onclick = () => toggleFilter('todo');
    if (els.btnDone) els.btnDone.onclick = () => toggleFilter('done');

    // Login
    els.btnLogin.onclick = async () => {
        const email = els.email.value;
        const password = els.pass.value;

        if (!email || !password) return showAuthError("Preencha todos os campos.");

        els.btnLogin.textContent = "Conectando...";
        els.btnLogin.disabled = true;

        try {
            const res = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();

            if (res.ok && data.token) {
                // Save Token
                await chrome.storage.local.set({
                    'nw_token': data.token,
                    'nw_user': data.user
                });
                state.token = data.token;
                state.user = data.user;

                // Proceed
                startScraping();
            } else {
                throw new Error(data.error || "Erro ao conectar");
            }
        } catch (e) {
            console.error(e);
            let msg = e.message;
            if (e.message.includes("Failed to fetch")) {
                msg = "Erro: Servidor Offline ou CORS Block (Verifique console)";
            }
            showAuthError(msg);
            els.btnLogin.textContent = "Entrar no CRM";
            els.btnLogin.disabled = false;
        }
    };

    // Actions
    els.btnMaps.onclick = () => chrome.tabs.create({ url: "https://www.google.com/maps" });

    els.btnCopy.onclick = () => {
        if (!state.scrapedData) return;
        const d = state.scrapedData;
        const text = `Empresa: ${d.name}\nNota: ${d.rating} (${d.reviews})\nLink: ${d.url}`;
        navigator.clipboard.writeText(text);
        els.btnCopy.textContent = "Copiado!";
        setTimeout(() => els.btnCopy.textContent = "Copiar Dados", 2000);
    };


    // === CRM ACTIONS ===
    els.btnCRM.onclick = async () => {
        if (!state.scrapedData) return;

        // 1. Prepare Data
        const diagnosis = state.scoreData.problems.length > 0
            ? state.scoreData.problems.join('\n- ')
            : "Perfil Otimizado!";

        const noteContent = `[NorthWay Compass]
Score: ${state.scoreData.total}/100
Categoria: ${state.scrapedData.category}
Google Maps: ${state.scrapedData.url}

 DIAGNÓSTICO:
- ${diagnosis}
`;

        const basePayload = {
            name: state.scrapedData.name,
            phone: state.scrapedData.phone || "0000",
            email: null,
            address: state.scrapedData.address,
            website: state.scrapedData.website,
            notes: noteContent,
            source: "Compass Extension",

            // GMB Structured Data
            gmb_link: state.scrapedData.url,
            gmb_rating: state.scrapedData.rating,
            gmb_reviews: state.scrapedData.reviews,
            gmb_photos: state.scrapedData.photos
        };

        els.btnCRM.textContent = "Verificando CRM...";
        els.btnCRM.disabled = true;

        try {
            // 2. CHECK EXISTING
            const searchParams = new URLSearchParams({
                name: state.scrapedData.name,
                phone: state.scrapedData.phone
            });

            const searchRes = await fetch(`${API_URL}/contact/search?${searchParams}`, {
                headers: { 'Authorization': `Bearer ${state.token}` }
            });

            if (searchRes.ok) {
                const searchData = await searchRes.json();

                // LEAD FOUND
                if (searchData.type === 'lead') {
                    if (confirm(`Lead encontrado: "${searchData.data.name}". Deseja atualizar com o novo diagnóstico?\n(Isso adicionará uma nota e atualizará dados de contato)`)) {
                        await updateLead(searchData.data.id, basePayload);
                    } else {
                        if (confirm("Deseja criar um NOVO lead duplicado?")) {
                            await createLead(basePayload);
                        } else {
                            resetBtn();
                        }
                    }
                }
                // CLIENT FOUND
                else if (searchData.type === 'client') {
                    alert(`Cliente encontrado: "${searchData.data.name}". A atualização de Clientes via extensão ainda não está ativada. Use o CRM.`);
                    resetBtn();
                }

            } else {
                // NOT FOUND -> CREATE NEW
                await createLead(basePayload);
            }

        } catch (e) {
            console.error(e);
            els.btnCRM.textContent = "Erro na Busca";
            setTimeout(resetBtn, 2000);
        }
    };

    async function createLead(payload) {
        els.btnCRM.textContent = "Criando Lead...";
        try {
            const res = await fetch(`${API_URL}/leads`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${state.token}`
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                els.btnCRM.textContent = "Sucesso! (Novo)";
                els.btnCRM.style.background = "#10b981";
                setTimeout(resetBtn, 3000);
            } else {
                throw new Error(data.error);
            }
        } catch (e) {
            alert("Erro ao criar: " + e.message);
            resetBtn();
        }
    }

    async function updateLead(id, payload) {
        els.btnCRM.textContent = "Vinculando...";
        try {
            const res = await fetch(`${API_URL}/leads/${id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${state.token}`
                },
                body: JSON.stringify({
                    ...payload,
                    append_notes: true // Important flag
                })
            });
            if (res.ok) {
                els.btnCRM.textContent = "Sucesso! (Vinculado)";
                els.btnCRM.style.background = "#8b5cf6"; // Purple for update
                setTimeout(resetBtn, 3000);
            } else {
                throw new Error("Falha no update");
            }
        } catch (e) {
            alert("Erro ao atualizar: " + e.message);
            resetBtn();
        }
    }

    function resetBtn() {
        els.btnCRM.textContent = "Enviar p/ CRM";
        els.btnCRM.style.background = "";
        els.btnCRM.disabled = false;
    }

    // Tab Logic
    document.querySelectorAll('.nw-tab-btn').forEach(btn => {
        btn.onclick = () => {
            // Remove active
            document.querySelectorAll('.nw-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));

            // Add active
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.remove('hidden');
        };
    });

    // === FUNCTIONS ===

    async function checkAuth() {
        const stored = await chrome.storage.local.get(['nw_token', 'nw_user']);
        if (stored.nw_token) {
            state.token = stored.nw_token;
            state.user = stored.nw_user;
            return true;
        }
        return false;
    }

    function showView(name) {
        ['auth', 'loading', 'error', 'result'].forEach(v => els[v].classList.add('hidden'));
        if (els[name]) els[name].classList.remove('hidden');
    }

    function showAuthError(msg) {
        els.authError.textContent = msg;
        els.authError.classList.remove('hidden');
    }

    async function startScraping() {
        showView('loading');

        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab.url.includes("google.com/maps") && !tab.url.includes("instagram.com")) {
            showView('error');
            return;
        }

        // Try getting Result
        try {
            // Try injecting script first to be safe
            // Map based on URL
            const scriptFile = tab.url.includes("instagram.com") ? 'scripts/insta_scraper.js' : 'scripts/maps_scraper.js';

            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: [scriptFile]
            });

            // Wait a bit for script to init
            setTimeout(async () => {
                const results = await chrome.tabs.sendMessage(tab.id, { action: "SCRAPE_GMB" });
                if (results && results.name) {
                    state.scrapedData = results;
                    renderResult(results);
                } else {
                    showView('error');
                }
            }, 500);

        } catch (e) {
            console.error(e);
            showView('error');
        }
    }

    function renderResult(data) {
        showView('result');

        // Populate Basic Data
        els.name.textContent = data.name || "Sem Nome";
        els.cat.textContent = data.category || "Sem Categoria";
        els.rating.textContent = data.rating || "0.0";
        els.reviews.textContent = data.reviews || "0";
        els.photos.textContent = data.photos || "--";

        // Populate Details Tab
        if (document.getElementById('detail-address')) document.getElementById('detail-address').textContent = data.address || "--";
        if (document.getElementById('detail-phone')) document.getElementById('detail-phone').textContent = data.phone || "--";
        if (document.getElementById('detail-hours')) document.getElementById('detail-hours').textContent = data.hours || "--";

        const webLink = document.getElementById('detail-website');
        if (webLink) {
            if (data.website) {
                webLink.href = data.website;
                webLink.textContent = data.website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0];
            } else {
                webLink.textContent = "--";
                webLink.removeAttribute('href');
            }
        }

        // Calculate Score
        // Use new weighted function
        const scoreData = calculateNorthWayScore(data);
        state.scoreData = scoreData;

        // Render Score
        els.score.textContent = scoreData.total;
        els.score.className = `score-circle ${scoreData.color}`;

        // Render Stats
        if (els.rating) els.rating.textContent = data.rating;
        if (els.reviews) els.reviews.textContent = data.reviews;
        if (els.photos) els.photos.textContent = data.photos;

        // Render ROI & Benchmark
        renderROI(data, scoreData);

        // Update Counts
        const todoCount = scoreData.problems.length + scoreData.improvements.length;
        const doneCount = scoreData.positives.length;

        if (els.countTodo) els.countTodo.textContent = todoCount;
        if (els.countDone) els.countDone.textContent = doneCount;

        renderDiagnosis();
    }

    function renderDiagnosis() {
        if (!state.scoreData) return;
        const list = els.list;
        list.innerHTML = "";

        const filter = state.filter || 'todo';
        let items = [];

        if (filter === 'todo') {
            // Combine Problems and Improvements
            state.scoreData.problems.forEach(p => items.push({ type: 'problem', text: p }));
            state.scoreData.improvements.forEach(i => items.push({ type: 'improvement', text: i }));

            if (items.length === 0) {
                list.innerHTML = `
                    <div style="text-align:center; padding: 20px; color: var(--nw-text-muted); font-size:11px;">
                        Nenhuma pendência encontrada! 🎉
                    </div>
                `;
                return;
            }
        } else {
            // Positives
            state.scoreData.positives.forEach(p => items.push({ type: 'positive', text: p }));
            if (items.length === 0) {
                list.innerHTML = `
                    <div style="text-align:center; padding: 20px; color: var(--nw-text-muted); font-size:11px;">
                        Nenhum item optimizado ainda.
                    </div>
                `;
                return;
            }
        }

        items.forEach(item => {
            let icon, cls = "";
            if (item.type === 'problem') {
                icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
                cls = ""; // Default red
            } else if (item.type === 'improvement') {
                icon = '🚀';
                cls = "";
            } else {
                icon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
                cls = "positive";
            }

            const html = `
                <div class="pro-problem-item ${cls}">
                    ${item.type === 'improvement' ? `<span style="font-size:12px">${icon}</span>` : icon}
                    <span class="pro-problem-text">${item.text}</span>
                </div>
            `;
            list.innerHTML += html;
        });
    }

    // === ROI LOGIC ===

    function calculateBenchmarkGap(data, competitors) {
        if (!competitors || competitors.avgRating === 0) return { gap: 0, text: "Sem dados" };
        const myRating = parseFloat(data.rating) || 0;
        const compRating = parseFloat(competitors.avgRating);
        const gap = (myRating - compRating).toFixed(1);

        return {
            gap,
            compRating,
            myRating,
            win: gap >= 0
        };
    }

    function calculateLostOpportunity(score, category) {
        // Simple Estimation Model
        // Traffic base constant
        let baseTraffic = 1000;
        const catLower = (category || "").toLowerCase();

        if (catLower.includes('restaurante') || catLower.includes('bar')) baseTraffic = 3000;
        if (catLower.includes('dentista') || catLower.includes('clinica')) baseTraffic = 800;
        if (catLower.includes('loja')) baseTraffic = 1500;

        // Conversion Rate drops if score is low
        // If Score > 90, loss is 0.
        // If Score = 50, loss is high.

        if (score >= 90) return 0;

        const lossPercentage = (100 - score) / 100; // e.g. 0.5 for score 50
        // We assume 30% of traffic goes to top 3.
        // If we have low score, we lose a portion of our share.

        const lostClicks = Math.round(baseTraffic * 0.3 * lossPercentage);
        return lostClicks;
    }

    function calculateNorthWayScore(data) {
        // Weights
        const weights = { stars: 0.3, volume: 0.2, response: 0.2, recency: 0.15, photos: 0.15 };
        let problems = [];
        let improvements = [];
        let positives = [];

        // 1. Rating (30%)
        let r = parseFloat(data.rating) || 0;
        let sStars = (r / 5) * 100;
        if (r < 4.0) {
            sStars *= 0.5; // Severe penalty
            problems.push(`Nota Baixa (${r}) - Penalidade Alta`);
        } else if (r < 4.5) {
            sStars *= 0.8;
            improvements.push(`Elevar nota para 4.8 (+Impacto)`);
        } else {
            positives.push(`Nota Excelente (${r})`);
        }

        // 2. Volume (20%) - Meta: 100
        let v = parseInt(data.reviews) || 0;
        let sVolume = Math.min((v / 100) * 100, 100);
        if (v < 10) problems.push(`Volume Crítico (${v} reviews)`);
        else if (v < 50) improvements.push(`Meta: 100 reviews (Faltam ${100 - v})`);
        else positives.push(`Volume de reviews saudável`);

        // 3. Response Rate (20%) - From Audit
        let sResponse = 0;
        if (data.audit) {
            sResponse = data.audit.responseRate || 0;
            if (sResponse < 50) problems.push(`Taxa de Resposta Baixa (${sResponse}%)`);
            else if (sResponse < 90) improvements.push(`Responder todos os reviews recentres`);
            else positives.push(`Ótima taxa de resposta`);
        } else {
            // Fallback if no audit data (assume 50 for neutral)
            sResponse = 50;
        }

        // 4. Photos (15%) - Meta: 50
        let p = parseInt(data.photos) || 0;
        let sPhotos = Math.min((p / 50) * 100, 100);
        if (p < 10) problems.push(`Poucas fotos (${p})`);
        else if (p > 50) positives.push(`Álbum completo (${p}+ fotos)`);

        // 5. Recency (15%)
        let sRecency = 0;
        if (data.audit && data.audit.lastReviewDays !== 999) {
            const days = data.audit.lastReviewDays;
            if (days <= 7) { sRecency = 100; positives.push("Reviews recentes (essa semana)"); }
            else if (days <= 30) { sRecency = 50; improvements.push("Solicitar novos reviews (último > 7 dias)"); }
            else { sRecency = 0; problems.push("Perfil estagnado (sem reviews recentes)"); }
        } else if (data.daysSinceLastPost) {
            // Instagram Recency
            const days = data.daysSinceLastPost;
            if (days > 7) problems.push("Perfil Inativo (> 7 dias sem post)");
            else positives.push("Postagens recentes");
            sRecency = days <= 7 ? 100 : 20;
        } else {
            sRecency = 50; // Neutral
        }

        // Instagram Specifics
        if (data.hasLink === false) { // explicit false check
            problems.push("Sem Link na Bio (Risco de Conversão)");
        }

        // Final Calc
        const finalScore = Math.round(
            (sStars * weights.stars) +
            (sVolume * weights.volume) +
            (sResponse * weights.response) +
            (sRecency * weights.recency) +
            (sPhotos * weights.photos)
        );

        let color = 'red';
        if (finalScore >= 75) color = 'green';
        else if (finalScore >= 45) color = 'yellow';

        return { total: finalScore, problems, improvements, positives, color };
    }

    function renderROI(data, scoreData) {
        // 1. Lost Opportunity
        const clicks = calculateLostOpportunity(scoreData.total, data.category);
        const roiEl = document.getElementById('roi-lost-clicks');
        if (roiEl) roiEl.textContent = clicks > 0 ? `-${clicks}` : "0";

        // 2. Audit Response
        if (data.audit) {
            const bar = document.getElementById('bar-response');
            if (bar) bar.style.width = `${data.audit.responseRate}%`;

            const rateEl = document.getElementById('audit-rate');
            if (rateEl) rateEl.textContent = `${data.audit.responseRate}%`;

            const recEl = document.getElementById('audit-recency');
            if (recEl) {
                const d = data.audit.lastReviewDays;
                recEl.textContent = d === 999 ? "--" : (d === 0 ? "Hoje" : `${d}d atrás`);
            }
        }

        // 3. Benchmark
        if (data.competitors) {
            const compRating = parseFloat(data.competitors.avgRating) || 0;
            const myRating = parseFloat(data.rating) || 0;

            const barYou = document.getElementById('bar-you');
            const barComp = document.getElementById('bar-comp');

            // Normalize to 5 stars = 100% width
            if (barYou) barYou.style.width = `${(myRating / 5) * 100}%`;
            if (barComp) barComp.style.width = `${(compRating / 5) * 100}%`;

            document.getElementById('val-you').textContent = myRating.toFixed(1);
            document.getElementById('val-comp').textContent = compRating.toFixed(1);

            // Render List (New V2.1)
            const listEl = document.getElementById('competitor-list');
            if (listEl && data.competitors.list && data.competitors.list.length > 0) {
                let html = '<div style="margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px;">';
                data.competitors.list.forEach(c => {
                    const isBetter = c.rating > myRating;
                    const color = isBetter ? '#ff3333' : '#888'; // Red if they are winning, Gray if not

                    html += `
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="overflow:hidden; white-space:nowrap; text-overflow:ellipsis; max-width: 180px;">${c.name}</span>
                            <span style="color:${color}; font-weight:bold;">${c.rating.toFixed(1)}</span>
                        </div>
                    `;
                });
                html += '</div>';
                listEl.innerHTML = html;
            } else if (listEl) {
                listEl.innerHTML = "Sem dados detalhados.";
            }
        }
    }

    // Wrap renderResult to include ROI
    const originalRenderResult = renderResult; // Backup reference not needed as we redefine in full file context
    // Actually, I am replacing the calculateScore and render functions, but I need to make sure renderResult CALLS renderROI.

    // I will modify renderResult via regex replacement if possible, or just overwrite it if it's in the block.
    // The previous view showed renderResult is mostly static DOM updates.
    // I will rely on the fact that I can't easily modify renderResult without seeing it in the chunk.
    // Wait, I am replacing the WHOLE bottom logic.
    // I need to be careful.

    // I will redefine renderResult here to include renderROI call.
});
