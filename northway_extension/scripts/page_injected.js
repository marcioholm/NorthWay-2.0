/**
 * WhatsApp Attachment Engine
 * Handles file injection into WhatsApp Web DOM.
 * No prototype monkey-patching — uses MutationObserver + direct injection.
 */

const NW_PAGE_DEBUG = false;

class WhatsAppAttachmentManager {
    constructor() {
        this.moduleName = "NW_ATTACH";
        this.setupListener();
    }

    log(msg, data = null) {
        if (!NW_PAGE_DEBUG) return;
        if (data) console.log(`[${this.moduleName}] ${msg}`, data);
        else console.log(`[${this.moduleName}] ${msg}`);
    }

    toast(message, type = 'info') {
        window.postMessage({
            source: 'NW_PAGE',
            type: 'NW_TOAST',
            message,
            toastType: type
        }, '*');
    }

    setupListener() {
        window.addEventListener('message', async (event) => {
            if (event.data.source !== 'NW_EXTENSION') return;
            if (event.data.type === 'NW_PING') return;
            if (event.data.type !== 'NW_ATTACH_FILE') return;

            const { kind, name, mime, data } = event.data.payload;

            try {
                const u8 = new Uint8Array(data);
                const blob = new Blob([u8], { type: mime });
                const file = new File([blob], name, { type: mime, lastModified: Date.now() });

                await this.performAttachment(file, kind);
            } catch (err) {
                this.log('Attachment Workflow Failed', err);
            }
        });
    }

    async performAttachment(file, kind) {
        try {
            // Strategy 1 — Direct injection into pre-existing hidden input (no menu needed)
            const directInput = this.findBestInputByAttributes(kind);
            if (directInput) {
                this.log(`Direct injection into existing input (${kind})`);
                await this.injectFile(directInput, file);
                return;
            }

            // Strategy 2 — Open attach menu, then capture new input via MutationObserver
            const mainButton = await this.findMainAttachButton();
            if (!mainButton) {
                this.toast("Não encontrei o botão de anexo. Clique manualmente no clip (📎).", "warning");
                return;
            }

            const clickableMain = mainButton.closest('div[role="button"]') || mainButton.closest('button') || mainButton;
            this.forceClick(clickableMain);

            const menuSelector = 'ul, div[role="dialog"] ul, div[data-animate-modal-popup="true"] ul';
            const menu = await this.waitForElement([menuSelector], 5000);

            if (menu) {
                const targetButton = this.findMenuItemInMenu(menu, kind);
                if (targetButton) {
                    // Snapshot existing inputs before triggering menu item
                    const existingInputs = new Set(Array.from(document.querySelectorAll('input[type="file"]')));

                    this.forceClick(targetButton);

                    // Wait for a NEW input element to appear in the DOM
                    const newInput = await this.waitForNewFileInput(existingInputs, 2000);

                    if (newInput) {
                        this.log('New file input captured via MutationObserver');
                        await this.injectFile(newInput, file);
                        return;
                    }
                }
            }

            // Strategy 3 — Final fallback: re-query after short wait
            await new Promise(r => setTimeout(r, 400));
            const fallbackInput = this.findBestInputByAttributes(kind);
            if (fallbackInput) {
                this.log('Fallback input found after delay');
                await this.injectFile(fallbackInput, file);
            } else {
                this.toast("Falha ao anexar arquivo automaticamente.", "error");
            }
        } catch (e) {
            this.log('Attachment flow error', e);
        }
    }

    /**
     * Watches for a NEW input[type="file"] element to appear in the DOM.
     * Does NOT touch any prototype.
     */
    waitForNewFileInput(existingInputs, timeout) {
        return new Promise(resolve => {
            const observer = new MutationObserver(() => {
                const newInput = Array.from(document.querySelectorAll('input[type="file"]'))
                    .find(i => !existingInputs.has(i));
                if (newInput) {
                    observer.disconnect();
                    resolve(newInput);
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });

            setTimeout(() => {
                observer.disconnect();
                resolve(null);
            }, timeout);
        });
    }

    async findMainAttachButton() {
        const exactIcon = document.querySelector('span[data-icon="plus-rounded"]');
        if (exactIcon) return exactIcon.closest('div[role="button"]') || exactIcon.closest('button');

        const selectors = [
            'div[title="Anexar"]', 'div[aria-label="Anexar"]',
            'div[title="Attach"]', 'div[aria-label="Attach"]',
            '[data-icon="clip"]', '[data-icon="plus"]',
            'span[data-testid="clip"]', 'span[data-testid="attach-menu-plus"]'
        ];
        return document.querySelector(selectors.join(','));
    }

    findMenuItemInMenu(menuElement, kind) {
        const items = Array.from(menuElement.querySelectorAll('li, div[role="button"]'));
        return items.find(el => {
            const label = (el.innerText || el.getAttribute('aria-label') || "").toLowerCase();
            const icon = el.querySelector('span[data-icon]');
            const iconData = icon ? icon.getAttribute('data-icon') : "";
            const testId = el.getAttribute('data-testid') || "";

            if (kind === 'document') {
                return testId === 'attach-document' || iconData === 'attach-document' || label.includes('doc');
            } else {
                return testId === 'attach-image' || iconData === 'attach-image' || label.includes('foto') || label.includes('photo') || label.includes('vid');
            }
        });
    }

    findBestInputByAttributes(kind) {
        const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
        if (kind === 'document') {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc === "" || acc === "*" || acc.includes("application");
            });
        } else {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc.includes('image') || acc.includes('video');
            });
        }
    }

    waitForElement(selectors, timeout) {
        return new Promise(resolve => {
            const start = Date.now();
            const interval = setInterval(() => {
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) { clearInterval(interval); resolve(el); return; }
                }
                if (Date.now() - start > timeout) { clearInterval(interval); resolve(null); }
            }, 200);
        });
    }

    async injectFile(inputElement, file) {
        await new Promise(r => setTimeout(r, 100));

        const dt = new DataTransfer();
        dt.items.add(file);

        try {
            const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'files').set;
            inputElement.value = '';
            nativeSetter.call(inputElement, dt.files);
        } catch (e) {
            inputElement.files = dt.files;
        }

        const opts = { bubbles: true, cancelable: true, view: window };
        inputElement.dispatchEvent(new Event('input', opts));
        await new Promise(r => setTimeout(r, 50));
        inputElement.dispatchEvent(new Event('change', opts));
    }

    forceClick(el) {
        const opts = { bubbles: true, cancelable: true, view: window };
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
    }
}

new WhatsAppAttachmentManager();
