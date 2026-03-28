/**
 * ZapWay Global State & Persistence
 */

const NWState = {
    shadowRoot: null,
    currentPhone: null,
    currentLeadId: null,
    isSidebarCollapsed: false,
    contactName: null,
    contactPhone: null,
    reset() {
        this.currentPhone = null;
        this.currentLeadId = null;
        this.contactName = null;
        this.contactPhone = null;
    }
};

/**
 * Persistence Helper (NWDB)
 */
const NWDB = {
    name: "NorthWayDB", 
    store: "files", 
    db: null,
    async init() {
        if (this.db) return this.db;
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(this.name, 1);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(this.store)) {
                    db.createObjectStore(this.store);
                }
            };
            req.onsuccess = (e) => { 
                this.db = e.target.result; 
                resolve(this.db); 
            };
            req.onerror = (e) => reject(e);
        });
    },
    async saveFile(key, file) {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const req = tx.objectStore(this.store).put(file, key);
            req.onsuccess = () => r();
            req.onerror = () => j();
        });
    },
    async getFile(key) {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readonly");
            const req = tx.objectStore(this.store).get(key);
            req.onsuccess = (e) => r(e.target.result);
            req.onerror = () => j();
        });
    },
    async clear() {
        await this.init();
        return new Promise((r, j) => {
            const tx = this.db.transaction(this.store, "readwrite");
            const req = tx.objectStore(this.store).clear();
            req.onsuccess = () => r();
            req.onerror = () => j();
        });
    }
};
