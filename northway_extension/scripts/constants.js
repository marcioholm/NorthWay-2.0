/**
 * ZapWay Extension Constants
 */

const SIDEBAR_WIDTH = 380;
const NW_DEBUG = false; // Set to true to enable logs

/**
 * Enhanced Logging Helper
 * @param {string} msg 
 * @param  {...any} args 
 */
const nwLog = (msg, ...args) => {
    if (NW_DEBUG) {
        console.log(`%c[NW] ${msg}`, "color: #ff1f4b; font-weight: bold;", ...args);
    }
};

/**
 * MIME Type Map for robust file handling
 */
const MIME_MAP = {
    'pdf': 'application/pdf',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
    'mp4': 'video/mp4',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'txt': 'text/plain'
};
