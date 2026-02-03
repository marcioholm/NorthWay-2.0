// NorthWay Compass - Robust Maps Scraper

console.log('NW Compass: Scraper Loaded');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCRAPE_GMB") {
        const data = safeScrape();
        console.log("NW Compass: Scrapped Data", data);
        sendResponse(data);
    }
});

function safeScrape() {
    try {
        // --- 1. NAME ---
        // Usually the only H1 on the sidebar
        let name = getText('h1.DUwDvf') || getText('h1');
        if (!name) return { error: "Nome da empresa não encontrado. Selecione um local no mapa." };

        // --- 2. RATING & REVIEWS ---
        // Strategy A: Look for the big rating number (e.g. "4.8")
        let rating = 0.0;
        let reviews = 0;

        // Try getting via Aria Labels which are more stable
        // Example aria-label: "4.8 estrelas de 5 com base em 120 avaliações"
        const starElement = document.querySelector('[role="img"][aria-label*="estrelas"], [role="img"][aria-label*="stars"]');

        if (starElement) {
            const label = starElement.getAttribute('aria-label');
            // Extract "4.8"
            const ratingMatch = label.match(/(\d+[.,]\d+)/);
            if (ratingMatch) rating = parseFloat(ratingMatch[0].replace(',', '.'));

            // Extract "120"
            // Look for number preceding "reviews", "avaliações", "avis"
            // Matches: "120 avaliações", "1.200 reviews"
            const reviewMatch = label.match(/(\d{1,3}(?:\.\d{3})*|\d+)\s+(avaliações|reviews|avis)/i);

            if (reviewMatch) {
                reviews = parseInt(reviewMatch[1].replace(/\./g, ''));
            } else {
                // Heuristic Fallback: 
                // If regex fails (e.g. strange format), assume the largest integer in the string > 5 is the review count.
                // UNLESS the rating count is small (like 2).
                const nums = label.match(/\d+/g);
                if (nums) {
                    const integers = nums.map(n => parseInt(n));
                    // If we have "5,0 stars" and "2 reviews", integers might be [5, 0, 5, 2]
                    // If max is 5, it might be the stars. 
                    // But if we have [4, 8, 5, 120], 120 is clearly reviews.

                    // Safe logic: If we have a number > 5, take the max.
                    const bigs = integers.filter(n => n > 5);
                    if (bigs.length > 0) {
                        reviews = Math.max(...bigs);
                    } else {
                        // If all numbers are <= 5 (e.g. [5, 0, 5, 2]), the non-5 one is likely reviews IF it's not the rating parts.
                        // Ideally we stick to the specific Regex above.
                        // If regex fails, we leave reviews as 0 to try the button fallback below.
                    }
                }
            }
        }

        // Strategy B: Fallback to text content if aria fails for rating
        if (rating === 0) {
            const ratingSpan = document.querySelector('span.ceNzKf'); // Common class for rating
            if (ratingSpan && ratingSpan.getAttribute('aria-hidden') === "true") {
                rating = parseFloat(ratingSpan.textContent.replace(',', '.'));
            }
        }

        // Strategy C: Fallback for Reviews (The Button Method)
        if (reviews === 0) {
            // Find button with EXACT format "(103)" which acts as the review count button in many views
            const buttons = Array.from(document.querySelectorAll('button'));

            // Stricter finder: Text must fully match `(123)` or `(1.234)` or `(2)`
            const strictReviewBtn = buttons.find(b => /^\([\d.]+\)$/.test(b.textContent.trim()));

            if (strictReviewBtn) {
                reviews = parseInt(strictReviewBtn.textContent.replace(/\D/g, ''));
            } else {
                // Looser fallback: Button containing "avaliações" or "reviews"
                const textBtn = buttons.find(b => {
                    const t = b.textContent.toLowerCase();
                    return t.includes('avaliações') || (t.includes('reviews') && t.includes('('));
                });

                if (textBtn) {
                    const match = textBtn.textContent.match(/(\d{1,3}(?:\.\d{3})*|\d+)/);
                    if (match) reviews = parseInt(match[0].replace(/\./g, ''));
                }
            }
        }

        // --- 3. CATEGORY ---
        // Usually a button right under the title with specific category text
        let category = "Geral";
        const catBtn = document.querySelector('button[jsaction*="category"]');
        if (catBtn) {
            category = catBtn.textContent.trim();
        } else {
            // Fallback: Look for gray text near rating
            // Usually the secondary text in the header section
            const potentialCats = Array.from(document.querySelectorAll('button.DkEaL'));
            if (potentialCats.length > 0) category = potentialCats[0].textContent.trim();
        }

        // --- 4. PHOTOS ---
        // Look for buttons mentioning "Photos" or try to find image count
        let photos = 0;
        // This is hard to get accurately without clicking. We will estimate based on visible thumbnails or check if "Add photo" exists
        const photoButton = document.querySelector('button[aria-label*="Photo"], button[aria-label*="foto"]');
        if (photoButton) {
            // Sometimes the label says "See 150 photos"
            const label = photoButton.getAttribute('aria-label');
            const match = label.match(/(\d+)/);
            if (match) photos = parseInt(match[0]);
            else photos = 5; // Default "some" photos
        }

        // --- 5. EXTRA DATA (For "Details" Tab) ---
        let address = getText('button[data-item-id="address"] div.fontBodyMedium') || "";
        if (!address) {
            // Fallback: looking for icons/text
            const addrEl = document.querySelector('button[data-tooltip="Copy address"]');
            if (addrEl) address = addrEl.ariaLabel.replace('Copy address', '').replace('Copiar endereço', '').trim();
        }

        let phone = getText('button[data-item-id*="phone"] div.fontBodyMedium') || "";
        if (!phone) {
            const phoneEl = document.querySelector('button[aria-label*="Phone"]');
            if (phoneEl) phone = phoneEl.getAttribute('aria-label').replace('Phone:', '').replace('Telefone:', '').trim();
        }

        let website = "";
        const webBtn = document.querySelector('a[data-item-id="authority"]');
        if (webBtn) website = webBtn.href;

        let hours = getText('div.t39EBf') || "Horário não disponível";

        // --- 6. BENCHMARKING (New v2.0) ---
        const competitors = scrapeCompetitors();

        // --- 7. AUDIT (New v2.0)
        const audit = scrapeResponseAudit();

        return {
            name,
            rating: rating || 0,
            reviews: reviews || 0,
            category: category || "Local",
            photos: photos || 0,
            address,
            phone,
            website,
            hours,
            url: window.location.href,
            success: true,
            // New V2 Data
            competitors,
            audit
        };

    } catch (e) {
        console.error("NW Compass Error:", e);
        return { error: e.toString() };
    }
}

function scrapeCompetitors() {
    try {
        // Strategy C: Text Search (Most Robust)
        // Find visible section headers with "Também pesquisados"
        let container = null;

        // 1. Try standard Aria Labels (often used by screen readers)
        container = document.querySelector('div[aria-label*="Também pesquisam"], div[aria-label*="Also search"], div[aria-label*="Lugares também pesquisados"]');

        // 2. If fail, find by Heading Text
        if (!container) {
            const headings = Array.from(document.querySelectorAll('h2, div[role="heading"], span.fontTitleLarge'));
            const targetHeading = headings.find(h => {
                const txt = h.innerText.toLowerCase();
                return txt.includes('também pesquisad') || txt.includes('also search');
            });

            if (targetHeading) {
                // The list is usually in the parent or next sibling of the container holding the heading
                // Use closest to find the section wrapper
                // Often the structure is: [Section [Header] [Carousel/Grid]]
                // We go up a few levels and query 'div.UaQhfb' (Item Card Class)
                const wrapper = targetHeading.closest('div.m6QErb') || targetHeading.parentElement.parentElement;
                if (wrapper) container = wrapper;
            }
        }

        if (!container) return { avgRating: 0, count: 0, list: [] };

        // 3. Extract Items
        // 'div.UaQhfb' is the common card container class in Maps
        const items = Array.from(container.querySelectorAll('div.UaQhfb'));

        let sum = 0;
        let count = 0;
        let list = [];

        items.slice(0, 5).forEach(item => {
            // Rating is usually in 'span.MW4etd' (e.g. "4.8")
            const ratingEl = item.querySelector('span.MW4etd');

            // Name extraction
            let name = "Concorrente";
            // Try aria-label first (most accurate on cards)
            const linkElement = item.closest('a') || item.querySelector('a');
            if (linkElement && linkElement.ariaLabel) {
                name = linkElement.ariaLabel;
            } else {
                // Fallback: fontBodyMedium
                const nameEl = item.querySelector('div.fontBodyMedium') || item.querySelector('span.osL8y');
                if (nameEl) name = nameEl.textContent.trim();
            }

            if (ratingEl) {
                const r = parseFloat(ratingEl.textContent.replace(',', '.'));
                if (!isNaN(r)) {
                    sum += r;
                    count++;
                    list.push({ name, rating: r });
                }
            }
        });

        if (count === 0) return { avgRating: 0, count: 0, list: [] };

        // Sort: Highest rating first
        list.sort((a, b) => b.rating - a.rating);

        return { avgRating: (sum / count).toFixed(1), count, list };

    } catch (e) {
        console.error("Competitor Scrape Error:", e);
        return { avgRating: 0, count: 0, list: [], error: e.message };
    }
}

function scrapeResponseAudit() {
    try {
        // Check for "Owner Response" in visible reviews
        // We look for text "Resposta do proprietário"

        // We need to find the Review Containers.
        // Usually class 'jftiEf' are the review cards
        const reviews = Array.from(document.querySelectorAll('div.jftiEf'));
        if (reviews.length === 0) return { reviewCount: 0, responseCount: 0, lastReviewDays: 999 };

        let responseCount = 0;
        let daysSinceLast = 999;
        const now = new Date();

        // Check top 5 reviews
        const top5 = reviews.slice(0, 5);
        top5.forEach((card, index) => {
            // Check for response block
            const responseText = card.innerText;
            if (responseText.includes("Resposta do proprietário") || responseText.includes("Owner response")) {
                responseCount++;
            }

            // Try to extract date
            if (index === 0) {
                const dateEl = card.querySelector('span.rsqaWe');
                if (dateEl) {
                    daysSinceLast = parseRelativeDate(dateEl.textContent);
                }
            }
        });

        return {
            reviewCount: top5.length,
            responseCount,
            responseRate: Math.round((responseCount / top5.length) * 100),
            lastReviewDays: daysSinceLast
        };

    } catch (e) {
        return { error: e.message, responseRate: 0, lastReviewDays: 999 };
    }
}

function parseRelativeDate(text) {
    // "2 dias atrás", "che há 3 semanas", "a year ago"
    text = text.toLowerCase();
    const num = parseInt(text.match(/\d+/) || [0]);

    if (text.includes('dia') || text.includes('day')) return num;
    if (text.includes('semana') || text.includes('week')) return num * 7;
    if (text.includes('mês') || text.includes('mes') || text.includes('month')) return num * 30;
    if (text.includes('ano') || text.includes('year')) return num * 365;
    if (text.includes('hora') || text.includes('hour')) return 0; // Today

    return 999; // Unknown
}

function getText(selector) {
    const el = document.querySelector(selector);
    return el ? el.textContent.trim() : null;
}
