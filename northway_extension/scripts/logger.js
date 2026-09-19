/**
 * Structured Logger - Improved logging system
 * 
 * Provides log levels, structured log entries, and context-aware logging
 * to replace the simple nwLog() function.
 */
class Logger {
    constructor() {
        this.level = 'info'; // debug, info, warn, error
        this.enabled = true;
        this.context = 'NW_EXT';
    }

    /**
     * Set log level
     * @param {'debug' | 'info' | 'warn' | 'error'} level 
     */
    setLevel(level) {
        this.level = level;
    }

    /**
     * Enable/disable logging
     * @param {boolean} enabled 
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }

    /**
     * Log at debug level (detailed debugging information)
     * @param {string} context - Component/context where log originates
     * @param {string} message - Log message
     * @param {any} data - Additional data/object to log
     */
    debug(context, message, data = null) {
        if (this.level !== 'debug' || !this.enabled) return;
        this._log('debug', context, message, data);
    }

    /**
     * Log at info level (general information)
     * @param {string} context - Component/context where log originates
     * @param {string} message - Log message
     * @param {any} data - Additional data/object to log
     */
    info(context, message, data = null) {
        if (this.level !== 'info' || !this.enabled) return;
        this._log('info', context, message, data);
    }

    /**
     * Log at warn level (warnings, non-critical issues)
     * @param {string} context - Component/context where log originates
     * @param {string} message - Log message
     * @param {any} data - Additional data/object to log
     */
    warn(context, message, data = null) {
        if (this.level !== 'warn' || !this.enabled) return;
        this._log('warn', context, message, data);
    }

    /**
     * Log at error level (critical errors)
     * @param {string} context - Component/context where log originates
     * @param {string} message - Log message
     * @param {any} data - Additional data/object to log
     */
    error(context, message, data = null) {
        if (this.level !== 'error' || !this.enabled) return;
        this._log('error', context, message, data);
    }

    /**
     * Internal log method that formats log entries
     * @param {string} level - Log level
     * @param {string} context - Component/context
     * @param {string} message - Log message
     * @param {any} data - Additional data
     * @returns {void} 
     */
    _log(level, context, message, data = null) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = {
            level,
            context: this.context,
            timestamp,
            message,
        };

        if (data !== null) {
            logEntry.data = data;
        }

        // Format and output the log
        const formatted = `[${level.toUpperCase()}] [${this.context}] ${timestamp} - ${context}: ${message}`;
        
        if (data !== null) {
            nwLog(formatted, data);
        } else {
            nwLog(formatted);
        }
    }
}

// Export singleton instance
const logger = new Logger();

export default logger;