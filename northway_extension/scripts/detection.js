/**
 * ZapWay Contact Detection
 * Strategy Pattern for identifying WhatsApp contacts.
 */

class FiberDetectionStrategy {
    detect() {
        const mainPanel = getRobustElement(SELECTORS.MAIN_PANEL);
        if (mainPanel) {
            const fiber = getReactInstance(mainPanel);
            if (fiber) {
                const jid = findJidInFiber(fiber);
                if (jid) return { phone: jid, isGroup: jid.includes('@g.us') };
            }
        }
        return null;
    }
}

class DomDetectionStrategy {
    detect() {
        const header = getRobustElement(SELECTORS.HEADER);
        if (header) {
            const nameEl = getRobustElement(SELECTORS.CONTACT_NAME, header);
            let name = nameEl ? (nameEl.title || nameEl.innerText) : null;
            if (name) name = name.trim();

            const img = header.querySelector('img');
            let avatarUrl = img ? img.src : null;
            let phone = null;
            let isGroup = false;

            if (img) {
                const fiber = getReactInstance(img);
                if (fiber) {
                    const jid = findJidInFiber(fiber);
                    if (jid) {
                        phone = jid;
                        isGroup = jid.includes('@g.us');
                    }
                }
            }

            // Failsafe for phone
            if (!phone && name && name.match(/\+?\d[\d\s-]{10,}/)) {
                phone = name.replace(/\D/g, '') + "@c.us";
            }

            if (phone || name) return { phone, name, avatarUrl, isGroup };
        }
        return null;
    }
}

class OfflineFallbackStrategy {
    detect() {
        // Try title (e.g. "(1) WhatsApp - User Name")
        const title = document.title;
        const match = title.match(/^(?:\(\d+\) )?WhatsApp\s*[–-]\s*(.+)$/);
        if (match && match[1]) {
            return { name: match[1], offline: true };
        }

        // Try URL
        const url = new URL(window.location.href);
        const phoneParam = url.searchParams.get('phone');
        if (phoneParam) {
            return { phone: phoneParam.replace(/\D/g, '') + "@c.us", offline: true };
        }

        return null;
    }
}

class ContactDetector {
    constructor() {
        this.strategies = [
            new FiberDetectionStrategy(),
            new DomDetectionStrategy(),
            new OfflineFallbackStrategy()
        ];
    }

    detect() {
        for (const strategy of this.strategies) {
            const result = strategy.detect();
            if (result && (result.phone || result.name)) {
                nwLog(`Detection Strategy Used: ${strategy.constructor.name}`, result);
                return result;
            }
        }
        return null;
    }
}

const contactDetector = new ContactDetector();

/**
 * React Fiber Helpers
 */
function getReactInstance(dom) {
    if (!dom) return null;
    for (const key in dom) {
        if (key.startsWith("__reactFiber") || 
            key.startsWith("__reactInternalInstance") || 
            key.startsWith("__reactProps") ||
            key.startsWith("__reactEvents")) return dom[key];
    }
    return null;
}

/**
 * BFS Traversal for JID identification.
 * Optimized: Node recursion limits and parent avoidance.
 */
function findJidInFiber(fiber) {
    if (!fiber) return null;
    let queue = [{ node: fiber, depth: 0 }];
    let visited = new Set();
    
    // Parent return search (only once at the beginning to avoid loops)
    if (fiber.return) {
        const parentProps = fiber.return.memoizedProps || fiber.return.pendingProps;
        if (parentProps?.jid) return parentProps.jid;
    }

    while (queue.length > 0) {
        const { node, depth } = queue.shift();
        if (!node || depth > 50 || visited.has(node)) continue;
        visited.add(node);

        const props = node.memoizedProps || node.props || node.pendingProps;
        if (props) {
            if (props.jid && typeof props.jid === 'string') return props.jid;
            if (props.id && typeof props.id === 'object' && props.id.user && props.id.server) return `${props.id.user}@${props.id.server}`;
            if (props.id && typeof props.id === 'string' && (props.id.includes('@c.us') || props.id.includes('@g.us'))) return props.id;
            if (props.id && props.id._serialized) return props.id._serialized; 
            if (props.chatId && typeof props.chatId === 'string' && props.chatId.includes('@')) return props.chatId;
            if (props.__x_id) return props.__x_id;
            if (props.key && props.key.remoteJid) return props.key.remoteJid;
            if (props.remoteJid) return props.remoteJid;

            if (props.chat && (props.chat.id || props.chat.jid || props.chat.__x_id)) {
                return props.chat.id || props.chat.jid || props.chat.__x_id;
            }
            if (props.contact && (props.contact.id || props.contact.jid || props.contact.remoteJid)) {
                 return props.contact.id || props.contact.jid || props.contact.remoteJid;
            }
            if (props.msg && (props.msg.to || props.msg.id?.remote)) return props.msg.to || props.msg.id?.remote;
            if (props.searchResult && props.searchResult.id) return props.searchResult.id;
        }

        if (node.child) queue.push({ node: node.child, depth: depth + 1 });
        if (node.sibling) queue.push({ node: node.sibling, depth: depth + 1 });
        // node.return is NOT included in BFS queue to prevent exponential growth/cycles
    }
    return null;
}

function getRobustElement(selectors, parent = document) {
    if (!selectors) return null;
    for (const sel of selectors) {
        const el = parent.querySelector(sel);
        if (el && el.offsetParent !== null) return el;
    }
    return null;
}

function checkActiveChat() {
    try {
        const result = contactDetector.detect();
        
        if (!result) {
            if (NWState.currentPhone !== null) {
                NWState.reset();
                showState('idle');
            }
            return;
        }

        const { phone, name, avatarUrl, isGroup, offline } = result;

        if (offline) {
            nwLog("WhatsApp is offline/syncing. Using fallback identification.");
            // UI could show "Syncing" status if needed.
        }

        const isBcActive = BroadcastEngine.currentIndex >= 0;
        if (isBcActive) return;

        const isSystemChat = name === "WhatsApp" || name === "Contato";
        if (isSystemChat) return;

        const chatId = isGroup ? `GROUP:${name}` : (phone || name);

        if (!chatId) {
            if (NWState.currentPhone !== null) {
                NWState.reset();
                showState('idle');
            }
            return;
        }

        if (chatId !== NWState.currentPhone) {
            NWState.currentPhone = chatId;
            NWState.contactName = name;
            NWState.contactPhone = phone;

            if (isGroup) {
                showState('group');
                const el = getEl('nw-group-name');
                if (el) el.textContent = name || "Grupo";
            } else {
                updateSidebar(name || phone, phone, name, avatarUrl);
            }
        }
    } catch (err) {
        nwLog("Detection Error", err);
    }
}
