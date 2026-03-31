/**
 * ZapWay Contact Detection
 *
 * Prioridade:
 *  1. Painel "Dados do contato" / drawer lateral  (dom_contact_panel)
 *  2. Header da conversa dentro de #main           (dom_header)
 *  3. Item selecionado na lista de chats           (dom_list_item)
 *  4. Parâmetro ?phone= na URL                     (url_param)
 *
 * React Fiber é helper opcional (extração de JID em imgs).
 */

// ─── Normalização ──────────────────────────────────────────────────────────

function normalizePhone(raw) {
    if (!raw) return null;
    const digits = raw.replace(/\D/g, '');
    return digits.length >= 8 ? digits : null;
}

function buildResult(source, { name, phone, jid, isGroup, avatarUrl, offline } = {}) {
    let normalizedPhone = null;

    if (phone) {
        normalizedPhone = normalizePhone(phone);
    } else if (jid && !isGroup) {
        const jidPhone = jid.replace(/@c\.us|@s\.whatsapp\.net/g, '');
        if (/^\d+$/.test(jidPhone)) normalizedPhone = jidPhone;
    }

    let chatId = null;
    if (isGroup) {
        chatId = jid || (name ? `GROUP:${name}` : null);
    } else {
        chatId = normalizedPhone
            ? `${normalizedPhone}@c.us`
            : (jid || name || null);
    }

    return {
        ok:        !!(chatId || name),
        source,
        chatId:    chatId    || null,
        phone:     isGroup   ? null : normalizedPhone,
        name:      name      || null,
        avatarUrl: avatarUrl || null,
        isGroup:   !!isGroup,
        offline:   !!offline
    };
}

// ─── Estratégia 1 — Painel "Dados do contato" ──────────────────────────────
// Funciona tanto para contato simples quanto conta comercial.

function getLeadFromContactPanel() {
    let panel = null;

    for (const sel of SELECTORS.CONTACT_INFO_PANEL) {
        const el = document.querySelector(sel);
        // Aceita mesmo durante animação — verifica offsetHeight ao invés de offsetParent
        if (el && el.offsetHeight > 50) {
            panel = el;
            break;
        }
    }
    if (!panel) return null;

    const panelText = panel.innerText || '';

    // Confirma que é painel de info (contato ou grupo)
    const isInfoPanel = /dados do contato|contact info|info do grupo|group info|participantes|members|telefone|phone|sobre|about/i.test(panelText);
    if (!isInfoPanel) return null;

    const isGroup = /participantes|members/i.test(panelText);

    // ── Nome ──
    const nameSelectors = [
        '[data-testid="contact-info-name"]',
        '[data-testid="conversation-info-header-chat-title-name"]',
        'h1[dir="auto"]',
        'span[dir="auto"][title]',
        '[data-testid="conversation-info-header-name"]',
        'h1'
    ];
    let name = null;
    for (const sel of nameSelectors) {
        const el = panel.querySelector(sel);
        if (el) {
            const t = (el.title || el.innerText || '').trim();
            if (t && t.length > 0 && t.length < 100) { name = t; break; }
        }
    }

    // ── Telefone (contatos individuais e contas comerciais) ──
    let phone = null;
    if (!isGroup) {
        // 1. Tenta seção dedicada de telefone (ícone phone ou label)
        const phoneIconEl = panel.querySelector('[data-icon="phone"], [data-testid*="phone"]');
        const phoneSection = phoneIconEl ? phoneIconEl.closest('div[role="button"], div[tabindex]') : null;
        if (phoneSection) {
            const t = phoneSection.innerText || '';
            const m = t.match(/\+?[\d][\d\s\-\(\)]{9,}/);
            if (m) phone = m[0].trim();
        }

        // 2. Fallback: regex em todo o texto do painel
        if (!phone) {
            // Ignora possíveis números em endereços (CEP, números de rua)
            // Prioriza números que parecem telefone brasileiro/internacional
            const phoneRegex = /(?:\+55|55)?[\s\-]?\(?[1-9]{2}\)?[\s\-]?(?:9[\d]{4}|[2-8][\d]{3})[\s\-]?[\d]{4}/g;
            const matches = panelText.match(phoneRegex);
            if (matches && matches.length > 0) {
                phone = matches[0].trim();
            } else {
                // Regex genérica como último recurso
                const genericMatches = panelText.match(/\+?[\d][\d\s\-\(\)]{10,}/g);
                if (genericMatches) {
                    for (const m of genericMatches) {
                        const digits = m.replace(/\D/g, '');
                        if (digits.length >= 10 && digits.length <= 15) { phone = m.trim(); break; }
                    }
                }
            }
        }
    }

    // ── JID via React Fiber na imagem do painel ──
    let jid = null;
    const img = panel.querySelector('img');
    if (img) {
        const fiber = getReactInstance(img);
        if (fiber) jid = findJidInFiber(fiber);
    }

    if (!name && !phone && !jid) return null;

    nwLog('[ZapWay][Lead] dom_contact_panel →', { name, phone, jid, isGroup });
    return buildResult('dom_contact_panel', { name, phone, jid, isGroup });
}

// ─── Estratégia 2 — Header da conversa em #main ────────────────────────────

function getLeadFromHeaderDOM() {
    const main = document.querySelector('#main');
    if (!main) return null;

    // Localiza o header da conversa excluindo drawers e diálogos
    const header = _findConversationHeader(main);
    if (!header) return null;

    // ── Nome ──
    const nameSelectors = [
        '[data-testid="conversation-info-header-chat-title-name"]',
        '[data-testid="conversation-info-header-name"]',
        'span[title][dir="auto"]',
        'span[dir="auto"][title]',
        'h1[dir="auto"]',
        'h1',
        'span[dir="auto"]'
    ];
    let name = null;
    for (const sel of nameSelectors) {
        const el = header.querySelector(sel);
        if (el) {
            const t = (el.title || el.innerText || '').trim();
            if (t && t.length > 0 && t.length < 100) { name = t; break; }
        }
    }

    // ── JID + avatar via Fiber ──
    let jid = null;
    let avatarUrl = null;
    const img = header.querySelector('img');
    if (img) {
        avatarUrl = img.src || null;
        const fiber = getReactInstance(img);
        if (fiber) jid = findJidInFiber(fiber);
    }

    const isGroup = jid ? jid.includes('@g.us') : false;

    if (!name && !jid) return null;

    nwLog('[ZapWay][Lead] dom_header →', { name, jid, isGroup });
    return buildResult('dom_header', { name, jid, isGroup, avatarUrl });
}

/**
 * Localiza o header da conversa dentro de #main,
 * excluindo headers dentro de drawers ou dialogs.
 */
function _findConversationHeader(main) {
    // Seletores diretos com data-testid (mais confiável)
    const exactSelectors = [
        '[data-testid="conversation-panel-header"]',
        '[data-testid="conversation-header"]',
        '[data-testid="conversation-info-header"]'
    ];
    for (const sel of exactSelectors) {
        const el = main.querySelector(sel);
        if (el && !_insideDrawerOrDialog(el)) return el;
    }

    // Fallback: qualquer <header> dentro de #main que não esteja em drawer/dialog
    const headers = main.querySelectorAll('header');
    for (const h of headers) {
        if (!_insideDrawerOrDialog(h)) return h;
    }

    return null;
}

function _insideDrawerOrDialog(el) {
    return !!(
        el.closest('[data-testid="drawer-right"]') ||
        el.closest('[data-testid="drawer-left"]') ||
        el.closest('[role="dialog"]') ||
        el.closest('[data-animate-drawer-right]') ||
        el.closest('[data-testid="contact-info-drawer"]')
    );
}

// ─── Estratégia 3 — Item selecionado na lista de chats ─────────────────────

function getLeadFromActiveListItem() {
    const activeItem =
        document.querySelector('div[aria-selected="true"][role="listitem"]') ||
        document.querySelector('[data-testid="cell-frame-container"][aria-selected="true"]') ||
        document.querySelector('[role="listitem"][aria-selected="true"]');

    if (!activeItem) return null;

    const lines = (activeItem.innerText || '')
        .split('\n').map(l => l.trim()).filter(Boolean);
    const name = lines[0] || null;

    if (!name || name === 'Você' || name === 'You') return null;

    let jid = null;
    const img = activeItem.querySelector('img');
    if (img) {
        const fiber = getReactInstance(img);
        if (fiber) jid = findJidInFiber(fiber);
    }

    const isGroup = jid ? jid.includes('@g.us') : false;

    nwLog('[ZapWay][Lead] dom_list_item →', { name, jid, isGroup });
    return buildResult('dom_list_item', { name, jid, isGroup });
}

// ─── Estratégia 4 — URL ?phone= ────────────────────────────────────────────

function getLeadFromUrl() {
    const url = new URL(window.location.href);
    const phoneParam = url.searchParams.get('phone');
    if (!phoneParam) return null;
    const digits = phoneParam.replace(/\D/g, '');
    if (!digits || digits.length < 8) return null;
    nwLog('[ZapWay][Lead] url_param →', { digits });
    return buildResult('url_param', { phone: digits, offline: true });
}

// ─── Orquestrador ──────────────────────────────────────────────────────────

function getActiveLeadContext() {
    const strategies = [
        getLeadFromContactPanel,
        getLeadFromHeaderDOM,
        getLeadFromActiveListItem,
        getLeadFromUrl
    ];

    for (const fn of strategies) {
        try {
            const result = fn();
            if (result && result.ok) return result;
        } catch (e) {
            nwLog(`[ZapWay][Lead] Erro em ${fn.name}:`, e);
        }
    }
    return { ok: false };
}

async function retryLeadDetection(maxRetries = 3, delayMs = 400) {
    for (let i = 0; i < maxRetries; i++) {
        if (i > 0) await new Promise(r => setTimeout(r, delayMs));
        const result = getActiveLeadContext();
        if (result.ok) return result;
    }
    return { ok: false };
}

// ─── checkActiveChat ───────────────────────────────────────────────────────
// Chamado pelo MutationObserver (debounce 700ms) e no bootstrap.

async function checkActiveChat() {
    if (isDetecting) return;
    isDetecting = true;
    try {
        nwLog('[ZapWay][Lead] detection start');
        const result = await retryLeadDetection();
        nwLog('[ZapWay][Lead] detection result', result);

        if (!result.ok) {
            const isIntroVisible = document.querySelector(
                '[data-testid="intro-text"], [data-testid="whatsapp-intro-icon"], ' +
                'canvas, [data-testid="intro-md-beta-logo"]'
            ) !== null;

            if (isIntroVisible && NWState.currentPhone !== null) {
                nwLog('[ZapWay][Main] Intro screen — resetando state');
                NWState.reset();
                showState('idle');
            }
            return;
        }

        const { chatId, phone, name, avatarUrl, isGroup } = result;

        // Não interrompe broadcast em andamento
        if (BroadcastEngine.currentIndex >= 0) return;

        // Ignora chats de sistema
        if (name === 'WhatsApp' || name === 'Contato') return;

        if (!chatId) {
            if (NWState.currentPhone !== null) { NWState.reset(); showState('idle'); }
            return;
        }

        // Atualiza se:
        // (a) chat mudou — novo chatId
        // (b) mesmo chat mas sidebar travada em idle (sync anterior falhou)
        const sidebarIdle = !!(getEl('nw-state-idle') && !getEl('nw-state-idle').classList.contains('hidden'));
        const shouldUpdate = chatId !== NWState.currentPhone || sidebarIdle;

        if (shouldUpdate) {
            nwLog(`[ZapWay][State] updating active lead → ${chatId} (source: ${result.source})`);
            NWState.currentPhone  = chatId;
            NWState.contactName   = name;
            NWState.contactPhone  = phone;

            if (isGroup) {
                showState('group');
                const el = getEl('nw-group-name');
                if (el) el.textContent = name || 'Grupo';
            } else {
                await updateSidebar(name || phone, phone, name, avatarUrl);
            }
        }
    } catch (err) {
        nwLog('[ZapWay][Main] Detection Error', err);
    } finally {
        isDetecting = false;
    }
}

// ─── React Fiber Helpers ───────────────────────────────────────────────────

function getReactInstance(dom) {
    if (!dom) return null;
    for (const key in dom) {
        if (
            key.startsWith('__reactFiber') ||
            key.startsWith('__reactInternalInstance') ||
            key.startsWith('__reactProps') ||
            key.startsWith('__reactEvents')
        ) return dom[key];
    }
    return null;
}

function findJidInFiber(fiber) {
    if (!fiber) return null;
    const queue = [{ node: fiber, depth: 0 }];
    const visited = new Set();

    while (queue.length > 0) {
        const { node, depth } = queue.shift();
        if (!node || depth > 25 || visited.has(node)) continue;
        visited.add(node);

        const props = node.memoizedProps || node.props || node.pendingProps;
        if (props) {
            const jid = props.jid || props.chatId || props.__x_id || props.chatJid || props.remoteJid;
            if (typeof jid === 'string' && jid.includes('@')) return jid;

            if (props.id && typeof props.id === 'object') {
                if (props.id.user && props.id.server) return `${props.id.user}@${props.id.server}`;
                if (props.id._serialized) return props.id._serialized;
            }

            const sub = props.chat || props.contact || props.msg || props.item;
            if (sub) {
                const sj = sub.id || sub.jid || sub.remoteJid || (sub.id && sub.id._serialized);
                if (typeof sj === 'string' && sj.includes('@')) return sj;
            }
        }

        if (node.child)               queue.push({ node: node.child,   depth: depth + 1 });
        if (node.sibling)             queue.push({ node: node.sibling, depth: depth + 1 });
        if (depth < 2 && node.return) queue.push({ node: node.return,  depth: depth + 1 });
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
