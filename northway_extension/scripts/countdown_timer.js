/**
 * Countdown Timer - Handles countdown logic for batch pauses and delays
 * Responsible for: managing countdown timers, progress updates
 */
class CountdownTimer {
    /**
     * Start a countdown timer
     * @param {number} delay 
     * @param {boolean} isBatchPause 
     * @param {function} onTick 
     * @param {function} onComplete 
     * @returns {number} 
     */
    start(delay, isBatchPause, onTick, onComplete) {
        let totalTime = delay / 1000;
        let remaining = totalTime;
        const msgPrefix = isBatchPause ? "🛡️ Pausa Longa: " : "Aguardando ";

        const interval = setInterval(() => {
            remaining -= 0.1;
            const currentWidth = ((totalTime - remaining) / totalTime) * 100;

            if (onTick) onTick(remaining, currentWidth);

            if (remaining <= 0) {
                clearInterval(interval);
                if (onComplete) onComplete();
            }
        }, 100);

        return interval;
    }

    /**
     * Pause a countdown timer
     * @param {number} intervalId 
     */
    pause(intervalId) {
        clearInterval(intervalId);
    }
}

export default CountdownTimer;