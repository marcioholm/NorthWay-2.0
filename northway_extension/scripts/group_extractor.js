/**
 * ZapWay Group Extractor
 * Extração de participantes com auto-scroll e deduplicação.
 */

const GroupExtractor = {
    isExtracting:    false,
    contacts:        new Map(),
    scrollIntervalId: null,
    panel:           null,
    groupName:       '',

    toggle: async function () {
        if (this.isExtracting) this.stop();
        else await this.start();
    },

    // ── Localiza o painel de info do grupo (drawer lateral) ──────────────

    getGroupPanel: function () {
        for (const sel of SELECTORS.CONTACT_INFO_PANEL) {
            const el = document.querySelector(sel);
            if (!el || el.offsetParent === null || el.offsetHeight < 80) continue;
            const text = el.innerText || '';
            if (/participantes|membros|members|participants|dados do grupo|group info/i.test(text)) {
                return el;
            }
        }

        // Fallback: sections/regions visíveis com palavra-chave
        for (const s of document.querySelectorAll('section, div[role="region"]')) {
            if (s.offsetParent === null) continue;
            if (/participantes|membros|participants/i.test(s.innerText || '')) return s;
        }

        return null;
    },

    // ── Localiza o container rolável com a lista de participantes ─────────

    getParticipantsContainer: function (panel) {
        for (const sel of SELECTORS.PARTICIPANT_LIST) {
            const el = panel.querySelector(sel);
            if (el) return el;
        }

        // Fallback: div mais profunda que seja rolável
        let best = null;
        for (const d of panel.querySelectorAll('div')) {
            if (d.scrollHeight > d.clientHeight + 20) best = d;
        }
        return best || panel;
    },

    // ── Extrai participantes visíveis no painel ───────────────────────────

    extractVisibleParticipants: function () {
        if (!this.panel) return 0;
        const before = this.contacts.size;

        const selector = SELECTORS.PARTICIPANT_ITEM.join(', ');
        const items = this.panel.querySelectorAll(selector);
        items.forEach(item => this._parseItem(item));

        return this.contacts.size - before;
    },

    _parseItem: function (item) {
        const text = (item.innerText || '').trim();
        if (!text) return;

        const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length < 1) return;

        let name = lines[0] || 'Usuário sem nome';
        let phone = '';

        // Ignora contato próprio
        if (name === 'Você' || name === 'You') return;

        // Número de telefone no texto
        const phoneMatch = text.match(/\+?[\d][\d\s\-\(\)]{9,}/);
        if (phoneMatch) {
            phone = phoneMatch[0].replace(/\D/g, '');
            // Se a primeira linha é o número, tenta o alias (~Nome)
            if (lines[0].match(/^\+?\d/)) {
                const aliasMatch = text.match(/~([^\n]+)/);
                name = aliasMatch ? aliasMatch[1].trim() : 'Usuário sem nome';
            } else {
                name = lines[0];
            }
        }

        // Tenta JID via React Fiber na imagem do item
        const img = item.querySelector('img');
        if (img) {
            const fiber = getReactInstance(img);
            if (fiber) {
                const jid = findJidInFiber(fiber);
                if (jid && !jid.includes('@g.us')) {
                    const jidPhone = jid.replace(/@c\.us|@s\.whatsapp\.net/g, '');
                    if (/^\d{8,}$/.test(jidPhone)) phone = jidPhone;
                }
            }
        }

        // Adiciona DDI Brasil se ausente
        if (phone && !phone.startsWith('55') && phone.length <= 11) phone = '55' + phone;

        const key = phone || name;
        if (!this.contacts.has(key)) {
            this.contacts.set(key, {
                name:   name.replace(/"/g, ''),
                phone,
                origin: `Grupo: ${this.groupName}`,
                date:   new Date().toLocaleDateString('pt-BR')
            });
        }
    },

    // ── Auto-scroll com detecção de estagnação ────────────────────────────

    autoScrollGroupParticipants: function (progressText) {
        const SCROLL_STEP     = 600;
        const SCROLL_INTERVAL = 700;
        const MAX_STAGNANT    = 3;
        let stagnantRounds    = 0;

        const container = this.getParticipantsContainer(this.panel);

        this.scrollIntervalId = setInterval(() => {
            if (!this.isExtracting) {
                clearInterval(this.scrollIntervalId);
                return;
            }

            if (this.checkForSecurityPopup()) {
                clearInterval(this.scrollIntervalId);
                return;
            }

            const added = this.extractVisibleParticipants();
            if (container) container.scrollTop += SCROLL_STEP;

            stagnantRounds = added === 0 ? stagnantRounds + 1 : 0;

            nwLog(`[ZapWay][Group] +${added} novos | total: ${this.contacts.size} | estagnado: ${stagnantRounds}`);

            if (progressText) {
                progressText.innerText = `Capturando... ${this.contacts.size} detectados`;
            }

            if (stagnantRounds >= MAX_STAGNANT) {
                clearInterval(this.scrollIntervalId);
                nwLog(`[ZapWay][Group] Auto-scroll finalizado: ${this.contacts.size} participantes`);
                if (progressText) {
                    progressText.innerText =
                        `✅ Concluído. ${this.contacts.size} participantes. Clique em "Finalizar e Baixar".`;
                }
            }
        }, SCROLL_INTERVAL);
    },

    // ── Inicia extração ───────────────────────────────────────────────────

    start: async function () {
        nwLog('[ZapWay][Group] Iniciando extração...');

        const panel = this.getGroupPanel();
        if (!panel) {
            toast('⚠️ Abra a lista de participantes do grupo primeiro.', 'warning');
            return;
        }

        this.panel      = panel;
        this.isExtracting = true;
        this.contacts.clear();
        this.groupName = (getEl('nw-group-name')?.textContent || '').trim() || 'Grupo';

        const btn            = getEl('nw-btn-export');
        const progressSection = getEl('nw-export-progress');
        const progressText   = getEl('nw-export-status');

        if (btn)             { btn.textContent = 'Finalizar e Baixar'; btn.style.backgroundColor = '#dc3545'; }
        if (progressSection) progressSection.classList.remove('hidden');
        if (progressText)    progressText.innerText = 'Iniciando extração automática...';

        // Coleta o que já está visível antes do scroll
        this.extractVisibleParticipants();

        this.autoScrollGroupParticipants(progressText);
    },

    // ── Para extração e faz download ──────────────────────────────────────

    stop: function () {
        nwLog('[ZapWay][Group] Parando extração...');
        this.isExtracting = false;

        if (this.scrollIntervalId) {
            clearInterval(this.scrollIntervalId);
            this.scrollIntervalId = null;
        }

        this.downloadCSV();

        const btn            = getEl('nw-btn-export');
        const progressText   = getEl('nw-export-status');
        const progressSection = getEl('nw-export-progress');

        if (btn)           { btn.textContent = 'Extrair Participantes'; btn.style.backgroundColor = ''; }
        if (progressText)  progressText.innerText = `Finalizado! ${this.contacts.size} contatos exportados.`;

        if (progressSection) {
            setTimeout(() => {
                const el = getEl('nw-export-progress');
                if (el) el.classList.add('hidden');
            }, 5000);
        }
    },

    // ── Detecta popup de segurança do WhatsApp ────────────────────────────

    checkForSecurityPopup: function () {
        const dialogs = document.querySelectorAll('div[role="dialog"]');
        const found = Array.from(dialogs).find(d =>
            /criptografia|encryption|segurança/i.test(d.innerText || '')
        );
        if (!found) return false;

        if (this.scrollIntervalId) clearInterval(this.scrollIntervalId);
        const p = getEl('nw-export-status');
        if (p) p.innerText = '⏸ PAUSADO: Alerta de Segurança detectado';
        toast('⚠️ Alerta de criptografia detectado. Extração pausada.', 'warning');
        return true;
    },

    // ── Gera e baixa o CSV ────────────────────────────────────────────────

    downloadCSV: function () {
        if (this.contacts.size === 0) return;

        const csvHeader = ['Nome', 'Email', 'Telefone', 'Origem', 'Interesse', 'Observações'];
        const toCSV = (text) => `"${String(text || '').replace(/"/g, '""')}"`;

        const csvRows = Array.from(this.contacts.values()).map(c => [
            toCSV(c.name), toCSV(''), toCSV(c.phone),
            toCSV(c.origin), toCSV('A definir'),
            toCSV(`Extraído em ${c.date}`)
        ].join(';'));

        const csvContent = '\uFEFF' + csvHeader.join(';') + '\n' + csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url  = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href     = url;
        link.download = `grupo_${this.groupName.replace(/\s/g, '_')}_${Date.now()}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
};
