/**
 * WhatsApp Attachment Engine (Refactored)
 * Handles file injection into WhatsApp Web DOM.
 */

class WhatsAppAttachmentManager {
    constructor() {
        this.moduleName = "NW_ATTACH";
        this.setupListener();
    }

    log(msg, data = null) {
        // Only log if specifically needed, otherwise keep it quiet
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
                console.error(`[${this.moduleName}] Attachment Workflow Failed`, err);
            }
        });
    }

    async performAttachment(file, kind) {
        try {
            const mainButton = await this.findMainAttachButton();
            if (!mainButton) {
                this.toast("Não encontrei o botão de anexo. Clique manualmente no clip (📎).", "warning");
            } else {
                const clickableMain = mainButton.closest('div[role="button"]') || mainButton.closest('button') || mainButton;
                this.forceClick(clickableMain);
            }

            const menuSelector = 'ul, div[role="dialog"] ul, div[data-animate-modal-popup="true"] ul';
            const menu = await this.waitForElement([menuSelector], 5000);

            if (menu) {
                const targetButton = this.findMenuItemInMenu(menu, kind);
                if (targetButton) {
                    const originalClick = HTMLInputElement.prototype.click;
                    let hijackedInput = null;
                    
                    const inputCapturedPromise = new Promise(resolve => {
                        HTMLInputElement.prototype.click = function () {
                            if (this.type === 'file') {
                                hijackedInput = this;
                                resolve(this);
                            } else {
                                originalClick.apply(this);
                            }
                        };
                    });

                    setTimeout(() => {
                        if (HTMLInputElement.prototype.click !== originalClick) HTMLInputElement.prototype.click = originalClick;
                    }, 2000);

                    this.forceClick(targetButton);
                    
                    const capturedInput = await Promise.race([
                        inputCapturedPromise,
                        new Promise(r => setTimeout(() => r(null), 1500))
                    ]);

                    HTMLInputElement.prototype.click = originalClick;

                    if (capturedInput) {
                        await this.injectFile(capturedInput, file);
                        return;
                    }
                }
            }
            
            // Fallback
            const fallbackInput = this.findBestInputByAttributes(kind);
            if (fallbackInput) {
                await this.injectFile(fallbackInput, file);
            } else {
                this.toast("Falha ao anexar arquivo automaticamente.", "error");
            }
        } catch (e) {
            console.error("Attachment flow error", e);
        }
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
