/**
 * ZapWay Automation Engine
 * Polls CRM for pending WhatsApp actions with caching and adaptive backoff.
 */

class WhatsAppQueuePoller {
    constructor() {
        this.cache = null;
        this.cacheTimestamp = 0;
        this.cacheTTL = 5000; // 5 seconds cache TTL
        this.pollInterval = 30000; // 30 seconds default
        this.pollingActive = false;
        this.intervalId = null;
        this.consecutiveEmptyPolls = 0;
        this.maxEmptyPolls = 6; // Se 6 polls vazios, aumenta intervalo
    }
    
    async getQueue(useCache = true) {
        const now = Date.now();
        
        // Se cache válido, usa (evita requisição desnecessária)
        if (useCache && this.cache && now - this.cacheTimestamp < this.cacheTTL) {
            console.log('[Queue] Cache hit, economizando requisição');
            return this.cache;
        }
        
        try {
            console.log('[Queue] Consultando servidor...');
            const response = await sendMsg({ action: "GET_WHATSAPP_QUEUE" });
            
            // Atualiza cache
            this.cache = response;
            this.cacheTimestamp = now;
            
            // Tracked mudanças
            if (response && response.items && response.items.length > 0) {
                this.consecutiveEmptyPolls = 0; // Reset counter
                console.log(`[Queue] ${response.items.length} itens encontrados`);
            } else {
                this.consecutiveEmptyPolls++;
                console.log(`[Queue] Vazio (${this.consecutiveEmptyPolls}/${this.maxEmptyPolls})`);
            }
            
            return response;
        } catch (error) {
            console.error('[Queue] Erro ao consultar:', error);
            return this.cache || { items: [] };
        }
    }
    
    renderQueue() {
        const fragment = document.createDocumentFragment();
        
        // Construir tudo no fragment (sem reflow)
        const items = this.cache?.items || [];
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'automation-card';
            card.innerHTML = `
                <h3>${item.name || 'Item'}</h3>
                <p>${item.content || ''}</p>
                <span class="status">${item.status || ''}</span>
            `;
            fragment.appendChild(card);  // Sem reflow ainda
        });
        
        // Atualizar DOM uma vez (REFLOW acontece aqui)
        const list = document.querySelector('.nw-automation-list');
        if (list) {
            list.innerHTML = '';
            list.appendChild(fragment);  // Reflow único
        }
        return items;
    }
    
    startPolling() {
        if (this.pollingActive) return;
        this.pollingActive = true;
        
        // Poll imediato
        this.getQueue(false);
        
        // Polling contínuo com adaptive backoff
        this.intervalId = setInterval(async () => {
            await this.getQueue(false);
            
            // Se muitos polls vazios, aumenta intervalo (economia de bateria/CPU)
            if (this.consecutiveEmptyPolls > this.maxEmptyPolls) {
                console.log('[Queue] Muitos polls vazios, aumentando intervalo');
                this.stopPolling();
                this.pollInterval = 60000; // 1 minuto
                this.startPolling();
            }
        }, this.pollInterval);
    }
    
    stopPolling() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.pollingActive = false;
    }
}

// Instância global
const queuePoller = new WhatsAppQueuePoller();

// Ouvir atualizações do server para atualizar proativamente
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "QUEUE_UPDATED") {
        queuePoller.cache = msg.queue;
        queuePoller.cacheTimestamp = Date.now();
        // updateQueueUI(msg.queue); // Chamado se houver função de UI
    }
});

// Substituir o AutomationEngine original pelo novo poller
// O AutomationEngine.startPolling() agora usa o cache adaptativo
