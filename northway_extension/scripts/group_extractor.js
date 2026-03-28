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
