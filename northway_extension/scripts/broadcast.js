/**
 * ZapWay Broadcast Engine
 * Handles messaging in bulk and single direct messages.
 */

const BroadcastEngine = {
    queue: [],
    currentIndex: -1,
    isPaused: false,
    isActive: false, // Core state for pause/resume logic
    templates: { A: "", B: "", C: "" },
    currentTab: "A",
    autoSend: false,
    batchCount: 0,
    media: null,
    mediaCaption: "",
    currentMessage: "",
    currentMediaCaption: "",
    currentStep: 1, // 1: Text, 2: Media
    config: { min: 10, max: 20, batchSize: 10, batchWait: 60 },

    init: async function () {
        nwLog("Initializing BroadcastEngine...");
        const res = await chrome.storage.local.get([
            'bc_queue', 'bc_index', 'bc_active', 'bc_templates', 
            'bc_auto', 'bc_config', 'bc_batch_count', 'bc_current_message', 
            'bc_media_caption', 'bc_current_step', 'bc_media_name', 'bc_media_type'
        ]);

        if (res.bc_queue) this.queue = res.bc_queue;
        if (res.bc_index !== undefined) this.currentIndex = res.bc_index;
        if (res.bc_templates) this.templates = res.bc_templates;
        this.autoSend = res.bc_auto || false;
        if (res.bc_config) this.config = res.bc_config;

        if (res.bc_current_message) this.currentMessage = res.bc_current_message;
        if (res.bc_media_caption) this.mediaCaption = res.bc_media_caption;
        if (res.bc_current_step) this.currentStep = res.bc_current_step;

        // UI Initialization
        this.syncUI();

        if (res.bc_active) {
            this.isActive = true;
            await this.restoreMedia(res);
            this.toggleView(true);
            this.renderQueue();
            this.updateStats();
            this.renderCurrent();

            if (this.media && this.currentStep === 2) {
                await this.attachMedia();
            }

            if (this.autoSend) this.attemptAutoSend();
        }
    },

    syncUI: function() {
        const autoCheck = getEl('nw-broadcast-auto');
        if (autoCheck) autoCheck.checked = this.autoSend;

        const iMin = getEl('nw-delay-min');
        const iMax = getEl('nw-delay-max');
        const iBatchSize = getEl('nw-batch-size');
        const iBatchWait = getEl('nw-batch-wait');

        if (iMin) iMin.value = this.config.min;
        if (iMax) iMax.value = this.config.max;
        if (iBatchSize) iBatchSize.value = this.config.batchSize;
        if (iBatchWait) iBatchWait.value = this.config.batchWait;

        const tplArea = getEl('nw-broadcast-template');
        if (tplArea) tplArea.value = this.templates[this.currentTab] || "";
    },

    restoreMedia: async function(res) {
        const savedMedia = await NWDB.getFile("bc_media");
        if (savedMedia) {
            const fileName = res.bc_media_name || savedMedia.name || "arquivo";
            const ext = fileName.split('.').pop().toLowerCase();
            let fileType = MIME_MAP[ext] || res.bc_media_type || savedMedia.type || "application/octet-stream";

            this.media = new File([savedMedia], fileName, { type: fileType, lastModified: Date.now() });
            
            const prev = getEl('nw-media-preview-container');
            const pName = getEl('nw-media-filename');
            const pCap = getEl('nw-media-caption');
            if (prev) prev.classList.remove('hidden');
            if (pName) pName.textContent = this.media.name;
            if (pCap) pCap.value = this.mediaCaption;
        }
    },

    toggleView: function(active) {
        if (active) {
            showState('broadcast');
            getEl('nw-broadcast-setup').classList.add('hidden');
            getEl('nw-broadcast-active').classList.remove('hidden');
        } else {
            getEl('nw-broadcast-active').classList.add('hidden');
            getEl('nw-broadcast-setup').classList.remove('hidden');
        }
    },

    /**
     * Implement missing sendDirectMessage logic.
     * Navigates to the contact and prepares the input.
     */
    sendDirectMessage: async function(phone, content) {
        nwLog(`Direct Message request for ${phone}`);
        try {
            // Open chat with phone and message
            const targetUrl = `https://web.whatsapp.com/send?phone=${phone.replace(/\D/g, '')}&text=${encodeURIComponent(content)}`;
            
            const link = document.createElement('a');
            link.href = targetUrl;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Wait for input to be ready
            let attempts = 0;
            while (attempts < 20) {
                const sendBtn = this.findSendButton();
                if (sendBtn) {
                    nwLog("Direct message input ready. Triggering send...");
                    sendBtn.click();
                    return true;
                }
                await new Promise(r => setTimeout(r, 1000));
                attempts++;
            }
            return false;
        } catch (e) {
            nwLog("sendDirectMessage error", e);
            return false;
        }
    },

    start: function () {
        if (this.queue.length === 0) {
            toast("⚠️ Importe contatos primeiro!", "warning");
            return;
        }

        const autoCheck = getEl('nw-broadcast-auto');
        this.autoSend = autoCheck ? autoCheck.checked : false;

        this.isActive = true;
        this.toggleView(true);
        this.currentIndex = -1;
        this.next();
    },

    stop: async function () {
        nwLog("Stopping Broadcast");
        if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);

        this.isPaused = false;
        this.isActive = false;
        
        this.currentIndex = -1;
        this.queue = [];
        this.batchCount = 0;
        this.media = null;
        
        await NWDB.clear();
        await this.save();

        const btn = getEl('nw-btn-bc-confirm');
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Confirmar Envio";
        }

        const progressSection = getEl('nw-progress-section');
        if (progressSection) progressSection.classList.add('hidden');
        
        this.updateStats();
        this.toggleView(false);
    },

    save: async function () {
        await chrome.storage.local.set({
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
    },

    renderQueue: function (searchTerm = '') {
        const list = getEl('nw-bc-queue-list');
        if (!list) return;

        const counterEl = getEl('nw-bc-queue-counter');
        if (counterEl) counterEl.innerHTML = `<span class="nw-chip">${this.queue.length} contatos</span>`;

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
            div.innerHTML = `
                <div style="display: flex; flex-direction: column;">
                    <span>${item.name}</span>
                    <span style="font-size: 10px; color: var(--nw-text-secondary);">${item.phone}</span>
                </div>
                <div style="display: flex; gap: 6px; align-items: center;">
                    <span class="nw-q-status ${item.status}">${item.status}</span>
                </div>
            `;
            list.appendChild(div);
        });
    },

    findSendButton: function (onlyOverlay = false) {
        const allPossible = Array.from(document.querySelectorAll(SELECTORS.SEND_BUTTON.join(',')));
        
        const candidates = allPossible.filter(el => {
            if (el.closest('#side')) return false;
            return true;
        });

        if (onlyOverlay || document.querySelector('div[role="dialog"]')) {
            const overlayBtn = candidates.find(el => el.closest('div[role="dialog"]') || el.closest('div[role="region"]'));
            if (overlayBtn) return overlayBtn;
            if (onlyOverlay) return null;
        }

        return candidates.find(el => el.closest('footer')) || candidates[0] || null;
    },

    attachMedia: async function () {
        if (!this.media) return true;
        nwLog(`Attaching media: ${this.media.name}`);

        try {
            const arrayBuffer = await this.media.arrayBuffer();
            const data = Array.from(new Uint8Array(arrayBuffer));
            const isImageOrVideo = this.media.type.startsWith('image/') || this.media.type.startsWith('video/');
            const kind = isImageOrVideo ? 'media' : 'document';

            window.postMessage({
                source: "NW_EXTENSION",
                type: "NW_ATTACH_FILE",
                payload: { kind, name: this.media.name, mime: this.media.type, data }
            }, "*");

            // Wait for preview (30s)
            for (let i = 0; i < 60; i++) {
                await new Promise(r => setTimeout(r, 500));
                const previewSend = this.findSendButton(true);

                if (previewSend) {
                    const isDisabled = previewSend.disabled || previewSend.getAttribute('aria-disabled') === 'true';
                    if (!isDisabled) return true;
                }
            }
            return true;
        } catch (e) {
            nwLog("attachMedia error", e);
            return false;
        }
    },

    next: async function () {
        this.currentIndex++;
        if (this.currentIndex >= this.queue.length) {
            toast("Disparo finalizado! Todos os contatos concluídos.", "success");
            await this.stop();
            return;
        }

        const item = this.queue[this.currentIndex];
        if (item.status !== 'PENDENTE') return this.next();

        this.renderQueue();
        this.renderCurrent();
        this.currentStep = 1;
        await this.save();

        const phoneNum = item.phone.replace(/\D/g, '');
        const targetUrl = `https://web.whatsapp.com/send?phone=${phoneNum}&text=${encodeURIComponent(this.currentMessage)}`;
        
        if (!window.location.search.includes(phoneNum)) {
            const link = document.createElement('a');
            link.href = targetUrl;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    },

    confirmSend: async function () {
        if (this.currentIndex < 0) return;

        if (this.media && this.currentStep === 1) {
            this.currentStep = 2;
            await this.save();
            setTimeout(async () => {
                await this.attachMedia();
                if (this.autoSend) this.attemptAutoSend();
            }, 1500);
            return;
        }

        this.queue[this.currentIndex].status = 'ENVIADO';
        chrome.runtime.sendMessage({ action: "INCREMENT_SENT" });
        this.updateStats();

        this.batchCount++;
        this.currentStep = 1;
        await this.save();

        const btn = getEl('nw-btn-bc-confirm');
        if (btn) btn.disabled = true;

        let delay = 0;
        let isBatchPause = false;

        if (this.config.batchSize > 0 && this.batchCount >= this.config.batchSize) {
            delay = this.config.batchWait * 1000;
            isBatchPause = true;
            this.batchCount = 0;
        } else {
            const min = this.config.min || 10;
            const max = this.config.max || 20;
            delay = Math.floor(Math.random() * (max - min + 1) + min) * 1000;
        }

        this.startCountdown(delay, isBatchPause);
    },

    startCountdown: function(delay, isBatchPause) {
        let totalTime = delay / 1000;
        let remaining = totalTime;
        const msgPrefix = isBatchPause ? "🛡️ Pausa Longa: " : "Aguardando ";
        
        const btn = getEl('nw-btn-bc-confirm');
        const progressSection = getEl('nw-progress-section');
        const countdownText = getEl('nw-countdown-text');
        const progressFill = getEl('nw-progress-fill');

        if (progressSection) progressSection.classList.remove('hidden');

        const tickRate = 100;
        const interval = setInterval(() => {
            remaining -= 0.1;
            const currentWidth = ((totalTime - remaining) / totalTime) * 100;

            if (btn) btn.textContent = `${msgPrefix}${Math.ceil(remaining)}s...`;
            if (countdownText) countdownText.textContent = `${Math.ceil(remaining)}s`;
            if (progressFill) progressFill.style.width = `${Math.min(currentWidth, 100)}%`;

            if (remaining <= 0) {
                clearInterval(interval);
                if (btn) {
                    btn.textContent = "Confirmar Envio";
                    btn.disabled = false;
                }
                if (progressSection) progressSection.classList.add('hidden');
                this.next();
            }
        }, tickRate);

        this.currentDelayInterval = interval;
    },

    togglePause: function () {
        if (!this.isActive) return;

        const btnPause = getEl('nw-btn-bc-pause');
        const btnConfirm = getEl('nw-btn-bc-confirm');

        if (this.isPaused) {
            this.isPaused = false;
            if (btnPause) btnPause.textContent = "⏸ Pausar Lote";
            if (btnConfirm) btnConfirm.disabled = true;
            if (this.autoSend) this.attemptAutoSend();
        } else {
            this.isPaused = true;
            if (this.currentDelayInterval) clearInterval(this.currentDelayInterval);
            if (btnPause) btnPause.textContent = "▶ Retomar";
            if (btnConfirm) {
                btnConfirm.textContent = "Pausado (Retomar)";
                btnConfirm.disabled = false;
            }
            toast("Disparo pausado.", "info");
        }
    },

    updateStats: function () {
        const pending = this.queue.filter(i => i.status === 'PENDENTE').length;
        const sent = this.queue.filter(i => i.status === 'ENVIADO').length;
        const failed = this.queue.filter(i => i.status === 'FALHOU').length;

        const p = getEl('nw-stat-pending'); if (p) p.textContent = pending;
        const s = getEl('nw-stat-sent'); if (s) s.textContent = sent;
        const f = getEl('nw-stat-failed'); if (f) f.textContent = failed;
        
        const etaEl = getEl('nw-stat-eta');
        if (etaEl) etaEl.textContent = pending === 0 ? "Finalizado" : this.calculateETA(pending);
    },

    calculateETA: function(pending) {
        const min = this.config.min || 10;
        const max = this.config.max || 20;
        const avgDelay = (min + max) / 2;
        const attachmentBuffer = this.media ? 10 : 0;
        const batchSize = this.config.batchSize || 10;
        const batchWait = this.config.batchWait || 60;
        const batchesLeft = Math.floor(pending / batchSize);
        const totalBatchWait = batchesLeft * batchWait;
        
        const totalSeconds = (pending * (avgDelay + attachmentBuffer)) + totalBatchWait;
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const sec = Math.floor(totalSeconds % 60);
        
        const parts = [];
        if (h > 0) parts.push(`${h} h`);
        parts.push(`${m} m`);
        parts.push(`${sec} s`);
        
        return parts.join(' ');
    },

    renderCurrent: function() {
        if (this.currentIndex < 0 || this.currentIndex >= this.queue.length) return;
        const item = this.queue[this.currentIndex];
        
        const nameEl = getEl('nw-bc-current-name'); if (nameEl) nameEl.textContent = item.name;
        const phoneEl = getEl('nw-bc-current-phone'); if (phoneEl) phoneEl.textContent = item.phone.split('@')[0];

        const variantKeys = ['A', 'B', 'C'];
        const variant = variantKeys[this.currentIndex % 3];
        const template = this.templates[variant] || this.templates['A'] || "";

        this.currentMessage = this.interpolate(template, item);
        this.currentMediaCaption = this.interpolate(this.mediaCaption, item);

        const previewEl = getEl('nw-bc-message-preview');
        const mediaTag = this.media ? `\n\n📎[ANEXO: ${this.media.name}]` : "";
        if (previewEl) previewEl.textContent = `[Mod ${variant}] ${this.currentMessage}${mediaTag}`;
    },

    interpolate: function(text, data) {
        if (!text) return "";
        return text.replace(/{nome}/gi, data.name || "")
            .replace(/{telefone}/gi, data.phone || "")
            .replace(/{email}/gi, data.email || "")
            .replace(/{origem}/gi, data.origem || "")
            .replace(/{interesse}/gi, data.interesse || "")
            .replace(/{observacao}/gi, data.observacao || "")
            .replace(/{variavel}/gi, data.variable || "");
    },
    
    attemptAutoSend: function() {
        nwLog("Attempting auto-send...");
        let attempts = 0;
        const interval = setInterval(() => {
            attempts++;
            const btn = this.findSendButton();
            if (btn) {
                clearInterval(interval);
                btn.click();
                setTimeout(() => this.confirmSend(), 3000);
            }
            if (attempts >= 30) {
                clearInterval(interval);
                nwLog("Auto-send timeout.");
            }
        }, 1000);
    },

    importContacts: function (text) {
        nwLog("Importing CSV/Text...");
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
        
        nwLog(`Imported ${this.queue.length} contacts.`);
        this.save();
        this.renderQueue();
        this.updateStats();
    },
};
