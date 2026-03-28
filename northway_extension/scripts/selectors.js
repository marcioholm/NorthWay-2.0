/**
 * ZapWay Extension Selectors
 * Centralized for easy maintenance.
 */

const SELECTORS = {
    MAIN_PANEL: [
        '[data-testid="conversation-panel-wrapper"]',
        'div[role="main"]',
        '#main',
        'section._aigv',
        '._aigv._aigz',
        'div._aigv',
        'section._aigw'
    ],
    HEADER: [
        '[data-testid="conversation-info-header"]',
        '[data-testid="conversation-header"]',
        'header',
        'div[role="button"]._amie',
        'div[role="button"]'
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
        'div._aigv._aigz',
        'div[data-testid="contact-info-drawer"]'
    ],
    CHAT_ITEM: [
        '[role="listitem"]',
        'div._ak8j'
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
        'button[aria-label*="Enviar"]',
        'div[role="button"][aria-label*="Send"]',
        'div[role="button"][aria-label*="Enviar"]'
    ],
    ATTACH_BUTTON: [
        'span[data-icon="plus-rounded"]',
        '[data-icon="clip"]',
        '[data-icon="plus"]',
        'span[data-testid="clip"]',
        'span[data-testid="attach-menu-plus"]',
        'div[title="Anexar"]',
        'div[aria-label="Anexar"]',
        'div[title="Attach"]',
        'div[aria-label="Attach"]'
    ],
    MENU_ITEMS: {
        DOCUMENT: [
            '[data-testid="attach-document"]',
            'span[data-icon="attach-document"]',
            'li:has(span[data-icon="attach-document"])'
        ],
        IMAGE: [
            '[data-testid="attach-image"]',
            'span[data-icon="attach-image"]',
            'li:has(span[data-icon="attach-image"])'
        ]
    }
};
