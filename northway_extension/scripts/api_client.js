/**
 * Centralized API client - breaks circular dependencies
 * 
 * All modules use this singleton instead of direct sendMsg calls.
 * This eliminates circular imports: main ↔ sidebar_ui ↔ broadcast.
 * 
 * Uses RequestCache for caching and request deduplication.
 * 
 * Example:
 *   // Antes: const response = await sendMsg({ action: "GET_CONTACT", phone, name });
 *   // Depois: const response = await apiClient.getContact(phone, name);
 */
import requestCache from './request_cache.js';

class ApiClient {
    constructor() {
        // Use the shared request cache for caching and dedup
        this.cache = requestCache;
    }

    /**
     * Generate a cache key from action + payload
     * @param {string} action 
     * @param {object} payload 
     * @returns {string} 
     */
    getCacheKey(action, payload) {
        return JSON.stringify({ action, payload });
    }

    /**
     * Check cache for a previous successful response
     * @param {string} action 
     * @param {object} payload 
     * @returns {any|null} 
     */
    get(action, payload) {
        const key = this.getCacheKey(action, payload);
        const cached = this.cache.get(key);
        
        if (!cached) return null;
        
        // Check if expired (simple cache, no TTL for now)
        // Could add TTL logic here if needed
        return cached.data;
    }

    /**
     * Set a value in the cache
     * @param {string} action 
     * @param {object} payload 
     * @param {any} data 
     */
    set(action, payload, data) {
        const key = this.getCacheKey(action, payload);
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }

    /**
     * Get a pending in-flight request promise
     * @param {string} action 
     * @param {object} payload 
     * @returns {Promise|null} 
     */
    getPending(action, payload) {
        const key = this.getCacheKey(action, payload);
        return this.pendingRequests.get(key);
    }

    /**
     * Set a pending in-flight request and remove it after resolution
     * @param {string} action 
     * @param {object} payload 
     * @param {Promise} promise 
     */
    setPending(action, payload, promise) {
        const key = this.getCacheKey(action, payload);
        this.pendingRequests.set(key, promise);
        
        // Remove after promise settles (both success and error)
        promise.then(
            () => this.pendingRequests.delete(key),
            () => this.pendingRequests.delete(key)
        );
    }

    /**
     * Make a chrome.runtime.sendMessage request with caching and dedup
     * @param {string} action 
     * @param {object} payload 
     * @returns {Promise} 
     */
    async request(action, payload = {}) {
        // 1. Check cache first
        const cached = this.get(action, payload);
        if (cached) return cached;

        // 2. Check if request already pending (deduplicate)
        const pending = this.getPending(action, payload);
        if (pending) {
            console.log(`[Dedup] Reusing pending request: ${action}`);
            return pending;
        }

        // 3. Make new request
        const promise = new Promise((resolve, reject) => {
            chrome.runtime.sendMessage(
                { action, ...payload },
                (response) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else if (response?.error) {
                        reject(new Error(response.error));
                    } else {
                        // Cache successful response
                        this.set(action, payload, response);
                        resolve(response);
                    }
                }
            );
        });

        // Track in-flight request
        this.setPending(action, payload, promise);
        return promise;
    }

    // Auth
    async checkAuth() {
        return this.request('CHECK_AUTH');
    }

    // Contacts
    async getContact(phone, name) {
        return this.request('GET_CONTACT', { phone, name });
    }

    async getContacts(query) {
        return this.request('GET_CONTACTS', { query });
    }

    // Pipelines
    async getPipelines() {
        return this.request('GET_PIPELINES');
    }

    // Templates
    async getTemplates() {
        return this.request('GET_TEMPLATES');
    }

    // Queue
    async getWhatsAppQueue() {
        return this.request('GET_WHATSAPP_QUEUE');
    }

    async updateQueueStatus(itemId, status) {
        return this.request('UPDATE_QUEUE_STATUS', { itemId, status });
    }

    // Messages
    async sendDirectMessage(phone, message, media) {
        return this.request('SEND_MESSAGE', { phone, message, media });
    }

    // System
    async getSystemStatus() {
        return this.request('GET_SYSTEM_STATUS');
    }
}

// Export singleton instance
const apiClient = new ApiClient();

export default apiClient;