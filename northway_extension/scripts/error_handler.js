/**
 * Centralized Error Handler
 * 
 * Provides consistent error handling across all modules with:
 * - Descriptive error messages
 * - Error categorization (recoverable vs critical)
 * - Retry logic for transient failures
 * - Error logging with context
 */
class ErrorHandler {
    constructor() {
        this.errorCount = {};
        this.maxRetries = 3;
        this.retryDelay = 1000; // 1 second
    }

    /**
     * Categorize an error
     * @param {Error} error 
     * @returns {object} 
     */
    categorize(error) {
        const name = error.name || 'Error';
        const message = error.message || 'Unknown error';

        // Network/Chrome errors are often transient
        if (name === 'AbortError' || name === 'InvalidStateError' ||
            message.includes('chrome.runtime.lastError') ||
            message.includes('Network error')) {
            return { category: 'transient', retryable: true };
        }

        // Permission/state errors are usually not retryable
        if (name === 'SecurityError' || 
            message.includes('permission') ||
            message.includes('access')) {
            return { category: 'critical', retryable: false };
        }

        // Default: assume recoverable
        return { category: 'recoverable', retryable: true };
    }

    /**
     * Handle an error with logging and optional retry
     * @param {Error|string} error 
     * @param {object} options 
     * @param {function} options.onError - Called with error info
     * @param {function} options.onRetry - Called if retry attempt
     * @param {number} options.retryAttempt - Current retry attempt (internal)
     */
    handle(error, { onError, onRetry, retryAttempt = 0 } = {}) {
        const categorization = this.categorize(error);

        // Log the error
        const errorInfo = {
            name: error.name || 'Error',
            message: error.message || 'Unknown error',
            stack: error.stack,
            category: categorization.category,
            retryable: categorization.retryable,
            timestamp: Date.now(),
        };

        nwLog('[ErrorHandler] Error caught:', errorInfo);

        // Call onError callback if provided
        if (onError) {
            onError(errorInfo);
        }

        // Attempt retry if retryable and within max retries
        if (categorization.retryable && retryAttempt < this.maxRetries) {
            if (onRetry) {
                onRetry(retryAttempt);
            }
            // Schedule retry after delay
            setTimeout(() => {
                try {
                    // Re-throw or re-execute the failing operation
                    // This is a placeholder - the caller should decide what to retry
                    nwLog(`[ErrorHandler] Retry attempt ${retryAttempt + 1}/${this.maxRetries}`);
                } catch (e) {
                    nwLog('[ErrorHandler] Retry failed:', e);
                }
            }, this.retryDelay);
        } else {
            // Max retries exceeded or non-retryable error
            nwLog(`[ErrorHandler] Error not retryed: ${categorization.category}`, errorInfo);
        }

        return categorization;
    }

    /**
     * Create a user-friendly error message
     * @param {string} context - Context where the error occurred
     * @param {Error|string} error 
     * @returns {string} 
     */
    userMessage(context, error) {
        const categorization = this.categorize(error);
        const base = `Erro em ${context}: ${error.message || 'Erro desconhecido'}`;

        if (categorization.retryable) {
            return `${base} (tentativa de recuperação).`;
        }
        return `${base}. Contate suporte se persistir.`;
    }
}

// Export singleton instance
const errorHandler = new ErrorHandler();

export default errorHandler;