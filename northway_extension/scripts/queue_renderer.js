/**
 * Queue Renderer - Handles user interface rendering for the broadcast queue
 * Responsible for: rendering queue list, current item, stats, etc.
 */
class QueueRenderer {
    constructor() {
        this.templates = { A: "", B: "", C: "" };
        this.currentTab = "A";
    }

    /**
     * Render current item preview
     * @param {object} engine 
     */
    renderCurrent(engine) {
        if (engine.currentIndex < 0 || engine.currentIndex >= engine.queue.length) return;
        const item = engine.queue[engine.currentIndex];

        const nameEl = document.getElementById('nw-bc-current-name');
        const phoneEl = document.getElementById('nw-bc-current-phone');
        const previewEl = document.getElementById('nw-bc-message-preview');

        if (nameEl) nameEl.textContent = item.name;
        if (phoneEl) phoneEl.textContent = item.phone.split('@')[0];

        const variantKeys = ['A', 'B', 'C'];
        const variant = variantKeys[engine.currentIndex % 3];
        const template = engine.templates[variant] || engine.templates['A'] || "";

        engine.currentMessage = engine.interpolate(template, item);
        const mediaTag = engine.media ? `\n\n📎[ANEXO: ${engine.media.name}]` : "";
        if (previewEl) previewEl.textContent = `[Mod ${variant}] ${engine.currentMessage}`;
    }

    /**
     * Render stats (pending, sent, failed)
     * @param {object} engine 
     */
    renderStats(engine) {
        const pending = engine.queue.filter(i => i.status === 'PENDENTE').length;
        const sent = engine.queue.filter(i => i.status === 'ENVIADO').length;
        const failed = engine.queue.filter(i => i.status === 'FALHOU').length;

        const p = document.getElementById('nw-stat-pending'); if (p) p.textContent = pending;
        const s = document.getElementById('nw-stat-sent'); if (s) s.textContent = sent;
        const f = document.getElementById('nw-stat-failed'); if (f) f.textContent = failed;

        const etaEl = document.getElementById('nw-stat-eta');
        if (etaEl) etaEl.textContent = pending === 0 ? "Finalizado" : engine.calculateETA(pending);
    }

    /**
     * Calculate ETA
     * @param {number} pending 
     * @returns {string} 
     */
    calculateETA(pending) {
        const min = 10;
        const max = 20;
        const avgDelay = (min + max) / 2;
        const attachmentBuffer = engine.media ? 10 : 0;
        const batchSize = engine.config.batchSize || 10;
        const batchWait = engine.config.batchWait || 60;
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
    }

    /**
     * Render countdown timer
     * @param {object} engine 
     * @param {number} delay 
     * @param {boolean} isBatchPause 
     */
    renderCountdown(engine, delay, isBatchPause) {
        const totalTime = delay / 1000;
        let remaining = totalTime;
        const msgPrefix = isBatchPause ? "🛡️ Pausa Longa: " : "Aguardando ";

        const btn = document.getElementById('nw-btn-bc-confirm');
        const progressSection = document.getElementById('nw-progress-section');
        const countdownText = document.getElementById('nw-countdown-text');
        const progressFill = document.getElementById('nw-progress-fill');

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
                engine.next();
            }
        }, tickRate);

        return interval;
    }
}

export default QueueRenderer;