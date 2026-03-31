/**
 * ZapWay Extension Selectors
 * Centralized for easy maintenance.
 * Stable selectors for WhatsApp Web.
 */

const SELECTORS = {
    MAIN_PANEL: [
        '[data-testid="conversation-panel-wrapper"]',
        'main#main',
        'div[role="main"]',
        'section:has(header[data-testid="conversation-header"])'
    ],
    HEADER: [
        '[data-testid="conversation-panel-header"]',
        '[data-testid="conversation-info-header"]',
        '[data-testid="conversation-header"]',
        '#main > header',
        'header'
    ],
    CONTACT_NAME: [
        '[data-testid="conversation-info-header-name"]',
        'span[title]',
        'span[dir="auto"]',
        'h1',
        'div[role="button"] span'
    ],
    IMAGE: [
        'img',
        '[data-testid="contact-image"]',
        '[data-testid="group-image"]'
    ],
    DRAWER: [
        '[data-testid="drawer-left"]',
        '[data-testid="drawer-right"]',
        'div[role="navigation"]',
        'div[data-testid="contact-info-drawer"]'
    ],
    CHAT_ITEM: [
        '[role="listitem"]',
        '[data-testid="cell-frame-container"]'
    ],
    TEXT_INPUT: [
        'div[contenteditable="true"][role="textbox"]',
        'footer div[contenteditable="true"]',
        '#main footer div[role="textbox"]'
    ],
    SEND_BUTTON: [
        '[data-testid="compose-btn-send"]',
        '[data-testid="send"]',
        'span[data-icon*="send"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="Enviar"]'
    ],
    ATTACH_BUTTON: [
        '[data-testid="clip"]',
        '[data-testid="attach-menu-plus"]',
        'div[title="Anexar"]',
        'div[aria-label="Anexar"]'
    ],
    MENU_ITEMS: {
        DOCUMENT: [
            '[data-testid="attach-document"]',
            'span[data-icon="attach-document"]'
        ],
        IMAGE: [
            '[data-testid="attach-image"]',
            'span[data-icon="attach-image"]'
        ]
    },

    // Contact / Group info panel (right drawer)
    CONTACT_INFO_PANEL: [
        '[data-testid="contact-info-drawer"]',
        '[data-testid="drawer-right"]',
        'div[data-animate-drawer-right="true"]'
    ],

    // Participant list inside group info panel
    PARTICIPANT_LIST: [
        '[data-testid="participant-list-container"]',
        'div[role="list"]',
        'ul[role="list"]',
        'div[aria-label*="participantes" i]',
        'div[aria-label*="members" i]'
    ],

    // Individual participant item
    PARTICIPANT_ITEM: [
        '[data-testid="member-list-item"]',
        '[role="listitem"]',
        '[data-testid="cell-frame-container"]'
    ]
};
