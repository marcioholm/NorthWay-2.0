/**
 * ZapWay Broadcast Engine - Orchestrates broadcast operations
 * Uses smaller focused classes for queue management, rendering, interpolation, etc.
 */
import QueueManager from './queue_manager.js';
import QueueRenderer from './queue_renderer.js';
import MessageInterpolator from './message_interpolator.js';
import MediaUploader from './media_uploader.js';
import CountdownTimer from './countdown_timer.js';

export default class BroadcastEngine {
    constructor() {
        this.queue = [];
        this.currentIndex = -1;
        this.isPaused = false;
        this.isActive = false;
        this.templates = { A: "", B: "", C: "" };
        this.currentTab = "A";
        this.autoSend = false;
        this.batchCount = 0;
        this.media = null;
        this.currentMessage = "";
        this.currentMediaCaption = "";
        this.currentStep = 1; // 1: Text, 2: Media
        this.config = { min: 10, max: 20, batchSize: 10, batchWait: 60 };

        // Initialize helper classes
        this.queueManager = new QueueManager();
        this.queueRenderer = new QueueRenderer();
        this.messageInterpolator = new MessageInterpolator();
        this.mediaUploader = new MediaUploader();
        this.countdownTimer = new CountdownTimer();

        // Copy initial state from engine for backward compatibility
        this._syncState();
    }

    /**
     * Sync state from engine properties to helper classes
     */
    _syncState() {
        this.queueManager.queue = this.queue;
        this.queueManager.currentIndex = this.currentIndex;
        this.queueManager.isActive = this.isActive;
        this.queueManager.templates = this.templates;
        this.queueManager.autoSend = this.autoSend;
        this.batchCount = this.batchCount;
        this.media = this.media;
        this.currentMessage = this.currentMessage;
    }

    /**
     * Import contacts from CSV/text
     * @param {string} text 
     */
    importContacts(text) {
        this.queueManager.importContacts(text);
        // Sync state after import
        this._syncState();
    }

    /**
     * Render the queue list
     * @param {string} searchTerm 
     */
    renderQueue(searchTerm = '') {
        this.queueRenderer.renderQueue(searchTerm);
    }

    /**
     * Render current item preview
     */
    renderCurrent() {
        this.queueRenderer.renderCurrent(this);
        this.queueRenderer.renderStats(this);
    }

    /**
     * Start the broadcast process
     */
    start() {
        this.queueManager.start();
    }

    /**
     * Move to next item in queue
     */
    next() {
        this.queueManager.next();
    }

    /**
     * Toggle pause/resume
     */
    togglePause() {
        this.queueManager.togglePause();
    }

    /**
     * Attempt auto-send
     */
    attemptAutoSend() {
        this.queueManager.attemptAutoSend();
    }

    /**
     * Save queue state
     */
    save() {
        this.queueManager.save();
    }

    /**
     * Interpolate template with contact data
     * @param {string} text 
     * @param {object} data 
     * @returns {string} 
     */
    interpolate(text, data) {
        return this.messageInterpolator.interpolate(text, data);
    }

    /**
     * Get template by variant
     * @param {string} variant 
     * @returns {string} 
     */
    getTemplate(variant) {
        return this.templates[variant] || this.templates['A'] || "";
    }
}