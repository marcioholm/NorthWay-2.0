// Scraper for WhatsApp Web & LinkedIn

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCAN_PAGE") {
        const url = window.location.href;
        let data = {};

        if (url.includes("web.whatsapp.com")) {
            // WhatsApp Web Scraper Logic
            // Try to find the header title (Contact Name)
            const headerTitle = document.querySelector('header ._amcf ._amig'); // Selectors change often, this is example
            // Fallback or generic selectors
            const spanTitles = Array.from(document.querySelectorAll('header span[title]'));

            if (spanTitles.length > 0) {
                data.name = spanTitles[0].getAttribute('title');
            }

            // Try to get phone from subtitle or heuristic
            data.phone = "Não identificado (Abra o perfil)";

        } else if (url.includes("linkedin.com/in/")) {
            // LinkedIn Profile Scraper
            const nameHeader = document.querySelector('.text-heading-xlarge');
            if (nameHeader) data.name = nameHeader.innerText;

            const jobTitle = document.querySelector('.text-body-medium');
            if (jobTitle) data.company = jobTitle.innerText; // Rough heuristic
        }

        sendResponse(data);
    }
    return true;
});
