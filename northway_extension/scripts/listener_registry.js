/**
 * Centralized listener management to prevent memory leaks
 * 
 * This singleton tracks ALL event listeners (chrome.storage.onChanged, 
 * chrome.runtime.onMessage, window.message, DOM addEventListener) and 
 * provides proper cleanup on unmount to prevent ghost listeners accumulation.
 */
class ListenerRegistry {
    constructor() {
        this.chromeListeners = [];     // Storage for chrome event listeners
        this.domListeners = [];        // Storage for DOM event listeners
        this.targetHandlerMap = new WeakMap(); // Maps target -> {event, handler}
    }

    /**
     * Register a chrome.storage.onChanged listener
     * @param {Function} handler - The handler function
     * @returns {Object} - Metadata object for later cleanup
     */
    addChromeStorageListener(handler) {
        const wrappedHandler = (changes, namespace) => {
            if (namespace === 'local') {
                handler(changes, namespace);
            }
        };
        chrome.storage.onChanged.addListener(wrappedHandler);
        this.chromeListeners.push({ type: 'storage', handler: wrappedHandler });
        return { type: 'storage', handler: wrappedHandler };
    }

    /**
     * Register a chrome.runtime.onMessage listener
     * @param {Function} handler - The handler function
     * @returns {Object} - Metadata object for later cleanup
     */
    addChromeRuntimeMessageListener(handler) {
        const wrappedHandler = (message, sender, sendResponse) => {
            handler(message, sender, sendResponse);
        };
        chrome.runtime.onMessage.addListener(wrappedHandler);
        this.chromeListeners.push({ type: 'runtimeMessage', handler: wrappedHandler });
        return { type: 'runtimeMessage', handler: wrappedHandler };
    }

    /**
     * Register a window.addEventListener('message') listener
     * @param {Function} handler - The handler function
     * @param {boolean} useCapture - Whether to use capture phase
     * @returns {Object} - Metadata object for later cleanup
     */
    addWindowMessageListener(handler, useCapture = false) {
        const wrappedHandler = (event) => {
            // Default safety check - modules should validate source/data themselves
            handler(event);
        };
        window.addEventListener('message', wrappedHandler, useCapture);
        this.domListeners.push({ type: 'windowMessage', handler: wrappedHandler, element: window });
        return { type: 'windowMessage', handler: wrappedHandler, element: window };
    }

    /**
     * Register a DOM element addEventListener
     * @param {Element} element - The DOM element
     * @param {string} event - The event name (e.g., 'click', 'keydown')
     * @param {Function} handler - The handler function
     * @param {boolean} useCapture - Whether to use capture phase
     * @returns {Object} - Metadata object for later cleanup
     */
    addDOMListener(element, event, handler, useCapture = false) {
        if (!element) {
            nwLog('[ListenerRegistry] Attempted to add DOM listener to null element');
            return null;
        }
        const wrappedHandler = (e) => handler(e);
        element.addEventListener(event, wrappedHandler, useCapture);
        this.domListeners.push({ type: 'dom', handler: wrappedHandler, element, event });
        return { type: 'dom', handler: wrappedHandler, element, event };
    }

    /**
     * Remove ALL registered listeners (call on unmount)
     * This properly cleans up all accumulated listeners to prevent memory leaks.
     */
    removeAll() {
        // 1. Remove chrome.storage.onChanged listeners
        this.chromeListeners
            .filter(l => l.type === 'storage')
            .forEach(({ handler }) => {
                try {
                    chrome.storage.onChanged.removeListener(handler);
                } catch (e) {
                    nwLog('[ListenerRegistry] Error removing storage listener:', e);
                }
            });

        // 2. Remove chrome.runtime.onMessage listeners
        this.chromeListeners
            .filter(l => l.type === 'runtimeMessage')
            .forEach(({ handler }) => {
                try {
                    chrome.runtime.onMessage.removeListener(handler);
                } catch (e) {
                    nwLog('[ListenerRegistry] Error removing runtime message listener:', e);
                }
            });

        // 3. Remove all DOM event listeners
        this.domListeners.forEach(({ element, event, handler }) => {
            try {
                element.removeEventListener(event, handler, false);
            } catch (e) {
                nwLog('[ListenerRegistry] Error removing DOM listener:', e);
            }
        });

        // 4. Clear all arrays
        this.chromeListeners = [];
        this.domListeners = [];

        console.log('[ListenerRegistry] ✅ All listeners cleaned up - memory leak prevented');
    }

    /**
     * Get current listener count for debugging
     * @returns {Object} - Counts by type
     */
    getStats() {
        return {
            chromeStorage: this.chromeListeners.filter(l => l.type === 'storage').length,
            chromeRuntimeMessage: this.chromeListeners.filter(l => l.type === 'runtimeMessage').length,
            domListeners: this.domListeners.length,
            total: this.chromeListeners.length + this.domListeners.length
        };
    }
}

// Export singleton instance
const listenerRegistry = new ListenerRegistry();

export default listenerRegistry;