/**
 * WhatsApp Attachment Engine (Rebuilt from Scratch)
 * Handles the complexities of WhatsApp Web's DOM, "Isolated World" restrictions,
 * and Menu/Input navigation.
 */

class WhatsAppAttachmentManager {
    constructor() {
        this.moduleName = "NW_ATTACH";
        console.log("%c[NW_ATTACH] ENGINE STARTED (MAIN WORLD)", "font-size: 20px; color: yellow; background: red; padding: 10px;");
        this.setupListener();
    }

    log(msg, data = null) {
        const style = "background: #008000; color: #fff; padding: 2px 5px; border-radius: 3px; font-weight: bold;";
        if (data) console.log(`%c[${this.moduleName}] ${msg}`, style, data);
        else console.log(`%c[${this.moduleName}] ${msg}`, style);
    }

    error(msg, err = null) {
        const style = "background: #ff0000; color: #fff; padding: 2px 5px; border-radius: 3px; font-weight: bold;";
        console.error(`%c[${this.moduleName}] ERROR: ${msg}`, style, err);
    }

    setupListener() {
        window.addEventListener('message', async (event) => {
            if (event.data.source !== 'NW_EXTENSION') return;

            // --- DIAGNOSTIC PING ---
            if (event.data.type === 'NW_PING') {
                console.log("%c[NW_ATTACH] PONG! Listening.", "font-size:16px; color:white; background:green;");
                return;
            }

            if (event.data.type !== 'NW_ATTACH_FILE') return;

            const { kind, name, mime, data } = event.data.payload;
            this.log(`Received request: ${name} (${kind})`);

            try {
                // 1. Rehydrate File
                const file = this.createFileObject(data, name, mime);

                // --- DEBUG INTEGRITY ---
                await this.debugFile(file);
                // -----------------------

                // 2. Execute Attachment Flow
                await this.performAttachment(file, kind);

            } catch (err) {
                this.error("Attachment Workflow Failed", err);
            }
        });
    }

    async debugFile(file) {
        console.log(`[NW_DEBUG] Inspecting File: ${file.name} (${file.type}, ${file.size} bytes)`);

        try {
            const head = new Uint8Array(await file.slice(0, 16).arrayBuffer());
            const headStr = Array.from(head).map(b => String.fromCharCode(b)).join("");
            console.log("[NW_DEBUG] Head Bytes:", head);
            console.log("[NW_DEBUG] Head String:", JSON.stringify(headStr));

            if (file.name.toLowerCase().endsWith('.pdf')) {
                if (!headStr.startsWith("%PDF-")) {
                    this.error("CRITICAL: PDF Header Missing! File is likely corrupt or empty.", headStr);
                } else {
                    this.log("PDF Header Verified OK (%PDF-)");
                }
            }
        } catch (e) {
            console.warn("[NW_DEBUG] Failed to read file bytes:", e);
        }
    }

    createFileObject(dataArray, name, mime) {
        const u8 = new Uint8Array(dataArray);
        const blob = new Blob([u8], { type: mime });
        return new File([blob], name, { type: mime, lastModified: Date.now() });
    }

    async performAttachment(file, kind) {
        try {
            // Step A: Find and Click "Clip" or "Plus"
            this.log("Searching for Main Attach Button...");
            let mainButton = await this.findMainAttachButton();

            if (mainButton) {
                // --- VISUAL DEBUGGING ---
                // Highlight the button so the user can see what we found
                mainButton.style.border = "3px solid red";
                mainButton.style.boxShadow = "0 0 10px red";
                await this.sleep(300);
                setTimeout(() => { if (mainButton) { mainButton.style.border = ""; mainButton.style.boxShadow = ""; } }, 1500);
                // -----------------------

                const clickableMain = mainButton.closest('div[role="button"]') || mainButton.closest('button') || mainButton;
                this.forceClick(clickableMain);
                this.log("Clicked Main Attach Button (Border Highlighted)");
            } else {
                this.log("Main attach button not found. asking for MANUAL ASSIST.");
                // ALERT THE USER TO HELP
                alert("NorthWay: Não encontrei o botão de anexo.\n\nPor favor, CLIQUE NO CLIPS (📎) AGORA.\n\nEu vou esperar você abrir o menu e farei o resto!");
            }

            // Step B: Wait for Menu (Either auto-opened or manually opened)
            this.log("Waiting for Menu to appear...");
            const menuSelector = 'ul, div[role="dialog"] ul, div[data-animate-modal-popup="true"] ul';
            const menu = await this.waitForElement([menuSelector], 15000);

            if (menu) {
                const targetButton = this.findMenuItemInMenu(menu, kind);

                if (targetButton) {
                    // --- NEW STRATEGY: GLOBAL CAPTURE TRAP ---
                    // WhatsApp likely creates and clicks the input synchronously.
                    // MutationObserver is too slow (microtask).
                    // We catch the click event in the CAPTURE PHASE at the window level.

                    let trappedInput = null;
                    const trapHandler = (e) => {
                        if (e.target && e.target.tagName === 'INPUT' && e.target.type === 'file') {
                            this.log("TRAP: Caught click on input!", e.target);
                            e.preventDefault(); // Stop System Picker
                            e.stopPropagation();
                            e.stopImmediatePropagation();
                            trappedInput = e.target;
                        }
                    };

                    // Activate Trap
                    window.addEventListener('click', trapHandler, { capture: true });

                    // Also set up Observer as backup (in case trap misses strange bubbling)
                    const existingInputs = Array.from(document.querySelectorAll('input[type="file"]'));
                    const inputPromise = this.waitForNewInput(existingInputs, 3000);

                    // Click the button
                    this.forceClick(targetButton);
                    this.log(`Clicked Menu Item: ${kind}`);

                    // Wait for trap or observer
                    // We give the trap a tiny moment to fire
                    await this.sleep(50);
                    window.removeEventListener('click', trapHandler, { capture: true });

                    let finalInput = trappedInput;
                    if (!finalInput) {
                        this.log("Trap missed. Checking observer...");
                        finalInput = await inputPromise; // Fallback
                    }

                    if (finalInput) {
                        this.injectFile(finalInput, file);
                        return; // Success!
                    } else {
                        this.error("Failed to capture any input (Trap & Observer both failed).");
                        if (kind === 'document') {
                            alert("NorthWay: Não consegui capturar o campo de arquivo. O WhatsApp mudou algo.");
                        }
                    }
                } else {
                    this.log(`Menu item for ${kind} not found.`);
                    alert(`NorthWay: Menu abriu, mas não achei a opção '${kind}'.`);
                }
            } else {
                this.log("Attach menu did not open (timeout).");
                if (!mainButton) {
                    alert("NorthWay: Tempo esgotado. Você não abriu o menu a tempo.");
                }
            }

        } catch (e) {
            this.log("Standard flow failed (" + e.message + ").");
        }

        // --- STRICT FAIL-SAFE POLICY ---
        // If it's a DOCUMENT, we MUST NOT inject into an Image input.
        if (kind === 'document') {
            this.error("ABORTING: Could not properly attach Document. Strict safety enabled.");
            return;
        }

        // --- FAIL-SAFE MODE (Videos/Images ONLY) ---
        this.log("Executing Fail-Safe Injection (Media Only)...");
        const fallbackInput = this.findBestInputByAttributes(kind);
        if (fallbackInput) {
            this.injectFile(fallbackInput, file);
        } else {
            this.error("FATAL: No input found anywhere.");
        }
    }

    async findMainAttachButton() {
        // Strategy 1: The Exact Selector provided by User
        // <span aria-hidden="true" data-icon="plus-rounded">
        const exactIcon = document.querySelector('span[data-icon="plus-rounded"]');
        if (exactIcon) {
            this.log("Found button by data-icon='plus-rounded'");
            return exactIcon.closest('div[role="button"]') || exactIcon.closest('button');
        }

        // Strategy 2: Exact SVG Path (from User)
        const userPath = "M11 13H5.5C4.94772 13 4.5 12.5523 4.5 12C4.5 11.4477 4.94772 11 5.5 11H11V5.5C11 4.94772 11.4477 4.5 12 4.5C12.5523 4.5 13 4.94772 13 5.5V11H18.5C19.0523 11 19.5 11.4477 19.5 12C19.5 12.5523 19.0523 13 18.5 13H13V18.5C13 19.0523 12.5523 19.5 12 19.5C11.4477 19.5 11 19.0523 11 18.5V13Z";

        const buttons = Array.from(document.querySelectorAll('div[role="button"], button'));
        for (const btn of buttons) {
            if (btn.innerHTML.includes(userPath)) {
                this.log("Found button by Exact SVG Path");
                return btn;
            }
        }

        // Strategy 3: Sibling Navigation (Fallback)
        const textBox = document.querySelector('div[contenteditable="true"][role="textbox"]');
        if (textBox) {
            const footerRow = textBox.closest('footer') || textBox.closest('div[role="region"]')?.nextElementSibling || textBox.parentElement.parentElement;

            if (footerRow) {
                // Look for buttons *before* the text box
                const buttons = Array.from(footerRow.querySelectorAll('div[role="button"], button'));

                // Filter buttons that are physically to the LEFT of the textbox
                const textRect = textBox.getBoundingClientRect();
                const leftButtons = buttons.filter(b => {
                    const rect = b.getBoundingClientRect();
                    // Must be to the left, and visible
                    return rect.right <= textRect.left && rect.width > 0 && rect.height > 0;
                });

                // Sort right-to-left (closest to textbox first)
                leftButtons.sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right);

                // Usually: 1st left is Emoji, 2nd left is Attach.
                // Or: 1st left is Attach (if Emoji is inside textbox).

                // Try to identify "Attach" by exclusion (not emoji)
                for (const btn of leftButtons) {
                    const title = (btn.getAttribute('title') || btn.getAttribute('aria-label') || "").toLowerCase();
                    const testId = (btn.getAttribute('data-testid') || "").toLowerCase();

                    // Bingo keywords
                    if (title.includes('anex') || title.includes('attach') || title.includes('mais') || title.includes('plus')) return btn;
                    if (testId.includes('attach') || testId.includes('clip') || testId.includes('plus')) return btn;

                    // Exclude Emojis to find the "other" button
                    if (!title.includes('emoji') && !title.includes('smile') && !testId.includes('emoji')) {
                        // High probability this is it
                        return btn;
                    }
                }
            }
        }

        // Fallback to Scan
        this.log("Sibling strategy failed. Trying selectors...");
        const selectors = [
            'div[title="Anexar"]',
            'div[aria-label="Anexar"]',
            'div[title="Attach"]',
            'div[aria-label="Attach"]',
            '[data-icon="clip"]',
            '[data-icon="plus"]',
            'span[data-testid="clip"]',
            'span[data-testid="attach-menu-plus"]'
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
                return testId === 'attach-document' ||
                    iconData === 'attach-document' ||
                    label.includes('document') ||
                    label.includes('documento');
            } else { // media
                return testId === 'attach-image' ||
                    iconData === 'attach-image' ||
                    label.includes('foto') ||
                    label.includes('photo') ||
                    label.includes('imag') ||
                    label.includes('galeria') ||
                    label.includes('vid');
            }
        });
    }

    findBestInputByAttributes(kind) {
        const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
        if (kind === 'document') {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc === "" || acc === "*" || acc.includes("application") || (!acc.includes('image/') && !acc.includes('video/'));
            });
        } else {
            return inputs.find(i => {
                const acc = (i.getAttribute('accept') || "").toLowerCase();
                return acc.includes('image') || acc.includes('video');
            });
        }
    }

    waitForNewInput(oldList, timeout) {
        return new Promise(resolve => {
            this.log("Starting MutationObserver for new input...");

            // 1. Check immediately in case we missed it
            const current = Array.from(document.querySelectorAll('input[type="file"]'));
            const fresh = current.filter(x => !oldList.includes(x));
            if (fresh.length > 0) {
                const inp = fresh[fresh.length - 1];
                // Aggressively capture it
                inp.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    console.log("[NW] Blocked CLICK on Sync Input");
                }, { capture: true });
                resolve(inp);
                return;
            }

            // 2. Observer for DOM changes
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (node.tagName === 'INPUT' && node.type === 'file') {
                            this.log("Observer detected new FILE INPUT!");

                            // --- INSTANT CLICK BLOCKER ---
                            // We catch it the moment it touches the DOM.
                            node.addEventListener('click', (e) => {
                                e.stopPropagation();
                                e.preventDefault();
                                console.log("[NW] Blocked CLICK on Observed Input");
                            }, { capture: true });
                            // -----------------------------

                            observer.disconnect();
                            resolve(node);
                            return;
                        }
                        // Search inside added subtrees (divs, etc)
                        if (node.querySelectorAll) {
                            const nestedInput = node.querySelector('input[type="file"]');
                            if (nestedInput) {
                                nestedInput.addEventListener('click', (e) => {
                                    e.stopPropagation();
                                    e.preventDefault();
                                }, { capture: true });
                                observer.disconnect();
                                resolve(nestedInput);
                                return;
                            }
                        }
                    }
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });

            // 3. Timeout Fallback
            setTimeout(() => {
                observer.disconnect();
                this.log("Observer timed out. Checking one last time...");
                const finalCheck = Array.from(document.querySelectorAll('input[type="file"]'));
                const finalFresh = finalCheck.filter(x => !oldList.includes(x));
                resolve(finalFresh.length > 0 ? finalFresh[finalFresh.length - 1] : null);
            }, timeout);
        });
    }

    waitForElement(selectors, timeout) {
        return new Promise(resolve => {
            const start = Date.now();
            const interval = setInterval(() => {
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        clearInterval(interval);
                        resolve(el);
                        return;
                    }
                }
                if (Date.now() - start > timeout) {
                    clearInterval(interval);
                    resolve(null);
                }
            }, 200);
        });
    }

    async injectFile(inputElement, file) {
        // --- 0. PREVENT DIALOG (Best Effort) ---
        try {
            inputElement.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                console.log("[NW] Blocked native click on input.");
                return false;
            };
        } catch (e) { }

        // --- 1. WAIT FOR DOM TO SETTLE ---
        // Sometimes the input isn't fully "bound" yet.
        await this.sleep(100);

        // --- STRICT SAFETY VALIDATION ---
        const accept = (inputElement.getAttribute('accept') || "").toLowerCase();
        const isDocument = file.type.includes('pdf') ||
            file.type.includes('text') ||
            file.type.includes('word') ||
            file.type.includes('excel') ||
            file.type.includes('presentation');

        if (isDocument) {
            const isStrictMediaInput = (accept.includes('image') || accept.includes('video')) &&
                !accept.includes('*') &&
                !accept.includes('application');

            if (isStrictMediaInput) {
                this.error(`ABORTED: Attempted to inject Document (${file.type}) into Strict Media Input [accept="${accept}"].`);
                alert("NorthWay Error: O input encontrado é apenas para IMAGENS. Abortando para evitar erro.");
                return;
            }
        }

        this.log(`Injecting File '${file.name}' (${file.size} bytes) into:`, inputElement);
        if (file.size === 0) {
            this.error("FATAL: File size is 0 bytes.");
            alert("NorthWay Error: O arquivo parece estar vazio (0 bytes). Verifique se o PDF está correto.");
            return;
        }

        // DataTransfer Mock
        const dt = new DataTransfer();
        dt.items.add(file);

        // --- REACT HACK: FORCE STATE UPDATE ---
        try {
            const proto = HTMLInputElement.prototype;
            const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'files').set;
            // Clear first (important for some React versions)
            inputElement.value = '';
            nativeSetter.call(inputElement, dt.files);
        } catch (e) {
            console.warn("Native setter failed, falling back to standard assignment", e);
            inputElement.files = dt.files;
        }

        // --- VERIFY INJECTION ---
        if (inputElement.files.length === 0) {
            this.error("CRITICAL: Injection failed. Input.files is empty!");
            alert("NorthWay: Falha técnica ao inserir o arquivo no input.");
        } else {
            this.log("Success: Input now holds file:", inputElement.files[0].name);
        }

        // --- DISPATCH EVENTS (Robust Sequence) ---
        const eventOpts = { bubbles: true, cancelable: true, view: window };

        // 1. Input (notify value change)
        inputElement.dispatchEvent(new Event('input', eventOpts));

        // 2. Change (trigger upload)
        // Wait a tick
        await this.sleep(50);
        this.log("Dispatching CHANGE event...");
        inputElement.dispatchEvent(new Event('change', eventOpts));

        // 3. Blur/Focus (cleanup)
        inputElement.dispatchEvent(new Event('blur', eventOpts));
        inputElement.dispatchEvent(new Event('focus', eventOpts));

        this.log("Injection Sequence Complete.");
    }

    forceClick(el) {
        const opts = { bubbles: true, cancelable: true, view: window };
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
    }

    sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    }
}

// Initialize
const NW_Engine = new WhatsAppAttachmentManager();
