// NorthWay Prospector - Insta Scraper

console.log('NW: Insta Scraper Loaded');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCRAPE_GMB") {
        // We reuse the same action name for simplicity, or handle "SCRAPE_INSTA"
        // But popup.js currently sends SCRAPE_GMB.
        // We will return data in a compatible format.

        const data = scrapeInsta();
        sendResponse(data);
    }
});

function scrapeInsta() {
    try {
        // Instagram structure is notoriously hard to scrape due to React classes.
        // We look for meta tags first.

        const title = document.querySelector('meta[property="og:title"]')?.content;
        const desc = document.querySelector('meta[property="og:description"]')?.content;

        // title format: "Name (@handle) • Instagram photos and videos"
        let name = "Instagram User";
        if (title) {
            const parts = title.split('(');
            if (parts.length > 0) name = parts[0].trim();
        }

        // Followers often in description: "100 Followers, 50 Following, 20 Posts..."
        let reviews = 0; // mapped to followers for scoring?
        let photos = 0; // mapped to posts

        if (desc) {
            const parts = desc.split(',');
            parts.forEach(p => {
                if (p.includes('Followers')) {
                    reviews = parseInt(p.replace(/[^0-9]/g, ''));
                }
                if (p.includes('Posts')) {
                    photos = parseInt(p.replace(/[^0-9]/g, ''));
                }
            });
        }

        // --- NEW v2.0 Checks ---

        // 1. Link in Bio Check
        // Usually <a href="..."> in the bio section
        // We look for any anchor in the header section that is external
        let hasLink = false;
        let linkUrl = "";

        // Strategy: Look for external links in header
        const externalLinks = Array.from(document.querySelectorAll('header section a')).filter(a => a.href && !a.href.includes('instagram.com'));
        if (externalLinks.length > 0) {
            hasLink = true;
            linkUrl = externalLinks[0].href;
        }

        // 2. Inactivity (Last Post Date)
        // This is hard on Insta as they obscure dates or load dynamically
        // We look for time elements <time datetime="..."> in the first few posts
        // Note: Posts might not be loaded in DOM yet if SSR
        let daysSinceLastPost = 999;

        // Try to find first post time
        const timeEl = document.querySelector('article time');
        if (timeEl) {
            const dateStr = timeEl.getAttribute('datetime');
            if (dateStr) {
                const postDate = new Date(dateStr);
                const diffTime = Math.abs(new Date() - postDate);
                daysSinceLastPost = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            }
        }

        return {
            name: name,
            category: "Instagram Business",
            rating: 5.0, // Mock rating for Insta
            reviews: reviews, // mapped from Followers
            photos: photos, // mapped from Posts
            url: window.location.href,
            success: true,
            // New V2 Data
            hasLink,
            daysSinceLastPost
        };

    } catch (e) {
        return { error: e.message };
    }
}
