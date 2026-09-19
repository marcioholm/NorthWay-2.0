/**
 * Queue Manager - Handles broadcast queue operations
 * Responsible for: import, render, next, status management
 */
class QueueManager {
    constructor() {
        this.queue = [];
        this.currentIndex = -1;
        this.isPaused = false;
        this.isActive = false;
        this.batchCount = 0;
        this.currentStep = 1; // 1: Text, 2: Media
        this.config = { min: 10, max: 20, batchSize: 10, batchWait: 60 };
        this.currentMessage = "";
        this.currentMediaCaption = "";
        this.media = null;
    }

    /**
     * Import contacts from CSV/text
     * @param {string} text 
     */
    importContacts(text) {
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

        this.save();
        this.renderQueue();
        this.updateStats();
    }

    /**
     * Save queue state to storage
     */
    save() {
        return chrome.storage.local.set({
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
    }

    /**
     * Render the queue list
     * @param {string} searchTerm 
     */
    renderQueue(searchTerm = '') {
        const list = document.getElementById('nw-bc-queue-list');
        if (!list) return;

        const counterEl = document.getElementById('nw-bc-queue-counter');
        if (counterEl) counterEl.textContent = `${this.queue.length} contatos`;

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
            const nameSpan = document.createElement('span');
            nameSpan.textContent = item.name;
            const phoneSpan = document.createElement('span');
            phoneSpan.style.fontSize = '10px';
            phoneSpan.style.color = 'var(--nw-text-secondary)';
            phoneSpan.textContent = item.phone;
            const statusSpan = document.createElement('span');
            statusSpan.className = `nw-q-status ${item.status}`;
            statusSpan.textContent = item.status;

            const detailsDiv = document.createElement('div');
            detailsDiv.style.display = 'flex';
            detailsDiv.style.flexDirection = 'column';
            detailsDiv.appendChild(nameSpan);
            detailsDiv.appendChild(phoneSpan);

            const statusDiv = document.createElement('div');
            statusDiv.style.display = 'flex';
            statusDiv.style.gap = '6px';
            statusDiv.style.alignItems = 'center';
            statusDiv.appendChild(statusSpan);

            div.appendChild(detailsDiv);
            div.appendChild(statusDiv);
            list.appendChild(div);
        });
    }

    /**
     * Render current item being sent
     */
    renderCurrent() {
        if (this.currentIndex < 0 || this.currentIndex >= this.queue.length) return;
        const item = this.queue[this.currentIndex];

        const nameEl = document.getElementById('nw-bc-current-name');
        const phoneEl = document.getElementById('nw-bc-current-phone');
        const previewEl = document.getElementById('nw-bc-message-preview');

        if (nameEl) nameEl.textContent = item.name;
        if (phoneEl) phoneEl.textContent = item.phone.split('@')[0];

        const variantKeys = ['A', 'B', 'C'];
        const variant = variantKeys[this.currentIndex % 3];
        const template = this.templates[variant] || this.templates['A'] || "";

        this.currentMessage = this.interpolate(template, item);
        this.currentMediaCaption = this.interpolate(this.mediaCaption, item);

        if (previewEl) previewEl.textContent = `[Mod ${variant}] ${this.currentMessage}`;
    }

    /**
     * Interpolate template variables with contact data
     * @param {string} text 
     * @param {object} data 
     * @returns {string} 
     */
    interpolate(text, data) {
        if (!text) return "";
        return text.replace(/{nome}/gi, data.name || "")
            .replace(/{telefone}/gi, data.phone || "")
            .replace(/{email}/gi, data.email || "")
            .replace(/{origem}/gi, data.origem || "")
            .replace(/{interesse}/gi, data.interesse || "")
            .replace(/{observacao}/gi, data.observacao || "")
            .replace(/{variavel}/gi, data.variable || "");
    }

    /**
     * Start the broadcast process
     */
    start() {
        if (this.queue.length === 0) {
            // toast("⚠️ Importe contatos primeiro!", "warning"); // Would be called by UI
            return;
        }

        this.isActive = true;
        this.currentIndex = -1;
        this.next();
    }

    /**
     * Move to next item in queue
     */
    next() {
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            // toast("Disparo finalizado! Todos os contatos concluídos.", "success");
            this.stop();
            return;
        }

        const item = this.queue[this.currentIndex];
        if (item.status !== 'PENDENTE') return this.next();

        this.renderQueue();
        this.renderCurrent();
        this.currentStep = 1;
        this.save();

        const phoneNum = item.phone.replace(/\D/g, '');
        const targetUrl = `https://web.whatsapp.com/send?phone=${phoneNum}&text=${encodeURIComponent(this.currentMessage)}`;

        if (!window.location.search.includes(phoneNum)) {
            const link = document.createElement('a');
            link.href = targetUrl;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    /**
     * Toggle pause/resume
     */
    togglePause() {
        if (!this.isActive) return;

        this.isPaused = !this.isPaused;

        if (this.isPaused) {
            if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);
            // Would update UI elements here
            // toast("Disparo pausado.", "info");
        } else {
            if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);
            // Would start countdown here
            // this.startCountdown();
            // toast("Disparo retomado.", "info");
        }
    }

    /**
     * Attempt auto-send
     */
    attemptAutoSend() {
        // Would implement auto-send logic
        // const interval = setInterval(() => { ... }, 1000);
    }
}

export default QueueManager;