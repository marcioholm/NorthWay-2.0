
(function () {
    console.log("DEBUG DRIVE: Script loaded at " + new Date().toISOString());

    function forceShowDrive() {
        console.log("DEBUG DRIVE: Attempting to force show drive/archivos tab...");

        const driveContent = document.getElementById('content-client-archivos');
        const driveBtn = document.getElementById('tab-client-archivos');

        if (!driveContent) {
            console.error("DEBUG DRIVE: FATAL - #content-client-archivos NOT FOUND in DOM!");
            // Check if old ID exists
            const oldDrive = document.getElementById('content-client-drive');
            if (oldDrive) console.warn("DEBUG DRIVE: Found OLD #content-client-drive. HTML is cached!");
            return;
        }

        console.log("DEBUG DRIVE: Found container:", driveContent);

        // Force style
        driveContent.classList.remove('hidden');
        driveContent.classList.add('block');
        driveContent.style.display = 'block'; // Inline override
        driveContent.style.border = '5px solid blue'; // Visual confirm

        // Force button style
        if (driveBtn) {
            driveBtn.style.backgroundColor = 'red';
            driveBtn.style.color = 'white';
        }

        // Log parent visibility
        let parent = driveContent.parentElement;
        while (parent) {
            const style = window.getComputedStyle(parent);
            if (style.display === 'none') {
                console.error("DEBUG DRIVE: Parent is hidden!", parent);
            }
            parent = parent.parentElement;
            if (parent.tagName === 'BODY') break;
        }
    }

    // Expose to window
    window.debugDrive = forceShowDrive;

    // Auto-run if URL has ?tab=archivos
    if (window.location.search.includes('archivos') || window.location.hash.includes('archivos')) {
        setTimeout(forceShowDrive, 1000);
    }
})();
