/**
 * Request deduplication cache
 * 
 * Prevents duplicate requests within TTL and deduplicates in-flight requests.
 * 
 * Usage:
 *   // Check cache first
 *   const cached = requestCache.get('GET_CONTACT', { phone, name });
 *   if (cached) return cached;
 *   
 *   // Check if request already pending (deduplicate)
 *   const pending = requestCache.getPending('GET_CONTACT', { phone, name });
 *   if (pending) return pending;
 *   
 *   // Make new request - cache will auto-store on success
 *   const result = await apiClient.getContact(phone, name);
 *   
 *   // Or use the unified apiClient which integrates requestCache
 */

class RequestCache {
    constructor(defaultTTL = 5000) {  // 5 seconds default TTL
        this.cache = new Map();
        this.defaultTTL = defaultTTL;
        this.pendingRequests = new Map();
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
     * Get from cache if valid and not expired
     * @param {string} action 
     * @param {object} payload 
     * @returns {any|null} 
     */
    get(action, payload) {
        const key = this.getCacheKey(action, payload);
        const cached = this.cache.get(key);
        
        if (!cached) return null;
        
        // Check if expired
        if (Date.now() - cached.timestamp > cached.ttl || Date.now() - cached.timestamp > this.defaultTTL) {
            this.cache.delete(key);
            return null;
        }
        
        console.log(`[Cache] Hit: ${action} (TTL: ${cached.ttl}ms)`);
        return cached.data;
    }

    /**
     * Set cache value with TTL
     * @param {string} action 
     * @param {object} payload 
     * @param {any} data 
     * @param {number} ttl 
     */
    set(action, payload, data, ttl = this.defaultTTL) {
        const key = this.getCacheKey(action, payload);
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            ttl
        });
        console.log(`[Cache] Set: ${action} (TTL: ${ttl}ms)`);
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
     * Clear all cache and pending requests
     */
    clear() {
        this.cache.clear();
        this.pendingRequests.clear();
    }
}

const requestCache = new RequestCache(defaultTTL = 5000);

export default requestCache;