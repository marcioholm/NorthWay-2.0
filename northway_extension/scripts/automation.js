/**
 * ZapWay Automation Engine
 * Polls CRM for pending WhatsApp actions.
 */

const AutomationEngine = {
    queue: [],
    intervalId: null,

    startPolling: function () {
        if (this.intervalId) clearInterval(this.intervalId);
        this.intervalId = setInterval(() => this.poll(), 30000);
        this.poll();
    },

    poll: async function () {
        nwLog("Polling automation queue...");
        try {
            const response = await sendMsg({ action: "GET_WHATSAPP_QUEUE" });
            if (response && Array.isArray(response)) {
                this.queue = response;
                this.updateBadge();
                this.render();
            }
        } catch (err) {
            nwLog("Poll failed", err);
        }
    },

    updateBadge: function () {
        const badge = getEl('nw-automation-badge');
        if (badge) {
            if (this.queue.length > 0) {
                badge.textContent = this.queue.length;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    },

    render: function () {
        const list = getEl('nw-automation-list');
        if (!list) return;
        
        if (this.queue.length === 0) {
            list.innerHTML = `<div class="nw-empty-state">Tudo em dia!</div>`;
            return;
        }

        list.innerHTML = '';
        this.queue.forEach(item => {
            const card = document.createElement('div');
            card.className = 'nw-card';
            card.style.marginBottom = '12px';
            card.style.borderLeft = '4px solid var(--nw-primary)';
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <strong>${item.phone}</strong>
                    <button class="nw-btn-send-auto" style="padding:4px 8px; font-size:11px; background:var(--nw-primary); color:white; border:none; border-radius:4px; cursor:pointer;">Enviar</button>
                </div>
                <div style="font-size:12px; white-space:pre-wrap; background:rgba(255,255,255,0.03); padding:8px;">${item.content}</div>
            `;
            card.querySelector('.nw-btn-send-auto').onclick = (e) => this.send(item, e.target);
            list.appendChild(card);
        });
    },

    send: async function (item, btn) {
        if (btn) {
            btn.disabled = true;
            btn.textContent = "...";
        }

        const success = await BroadcastEngine.sendDirectMessage(item.phone, item.content);
        if (success) {
            const res = await sendMsg({ action: "UPDATE_QUEUE_STATUS", data: { id: item.id, status: 'sent' } });
            if (res) {
                this.queue = this.queue.filter(i => i.id !== item.id);
                this.updateBadge();
                this.render();
                toast("Mensagem enviada!", "success");
            }
        } else {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Enviar";
            }
            toast("Erro ao enviar.", "error");
        }
    }
};
