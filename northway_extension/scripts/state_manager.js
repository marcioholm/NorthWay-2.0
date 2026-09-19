/**
 * Centralized State Management
 * 
 * Provides a single source of truth for application state,
 * replacing scattered storage.local.get/set calls and
 * enabling better state tracking and debugging.
 */
class StateManager {
    constructor() {
        this.state = {
            // Lead detection state
            currentPhone: null,
            contactName: null,
            contactPhone: null,
            contactAvatar: null,
            isGroup: false,
            currentLeadContext: null,

            // Broadcast state
            isBroadcastActive: false,
            currentBroadcastIndex: -1,
            broadcastAutoSend: false,
            broadcastConfig: { min: 10, max: 20, batchSize: 10, batchWait: 60 },

            // UI state
            sidebarCollapsed: false,
            sidebarVisible: true,

            // Template state
            currentTemplate: null,
            templates: {},

            // Detection state
            isDetecting: false,
            detectionRetryCount: 0,
        };

        this.subscribers = new Map();
    }

    /**
     * Get current state value
     * @param {string} key 
     * @returns {any} 
     */
    get(key) {
        const keys = key.split('.');
        let value = this.state;
        for (const k of keys) {
            if (!value[k]) return null;
            value = value[k];
        }
        return value;
    }

    /**
     * Set state value and notify subscribers
     * @param {string} key 
     * @param {any} value 
     */
    set(key, value) {
        const keys = key.split('.');
        let obj = this.state;
        for (let i = 0; i < keys.length - 1; i++) {
            if (!obj[keys[i]]) obj[keys[i]] = {};
            obj = obj[keys[i]];
        }
        obj[keys[keys.length - 1]] = value;
        this.notify(key, value);
    }

    /**
     * Subscribe to state changes
     * @param {string} key 
     * @param {function} callback 
     * @returns {function} 
     */
    subscribe(key, callback) {
        if (!this.subscribers.has(key)) this.subscribers.set(key, []);
        this.subscribers.get(key).push(callback);
        
        // Return unsubscribe function
        return () => {
            this.subscribers.get(key) = this.subscribers.get(key).filter(cb => cb !== callback);
        };
    }

    /**
     * Notify all subscribers of a state change
     * @param {string} key 
     * @param {any} value 
     */
    notify(key, value) {
        this.subscribers.get(key)?.forEach(callback => callback(value));
    }

    /**
     * Reset state to initial values
     */
    reset() {
        this.state = {
            currentPhone: null,
            contactName: null,
            contactPhone: null,
            contactAvatar: null,
            isGroup: false,
            currentLeadContext: null,
            isBroadcastActive: false,
            currentBroadcastIndex: -1,
            broadcastAutoSend: false,
            broadcastConfig: { min: 10, max: 20, batchSize: 10, batchWait: 60 },
            sidebarCollapsed: false,
            sidebarVisible: true,
            currentTemplate: null,
            templates: {},
            isDetecting: false,
            detectionRetryCount: 0,
        };
        this.subscribers = new Map();
    }
}

// Export singleton instance
const stateManager = new StateManager();

export default stateManager;