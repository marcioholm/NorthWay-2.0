document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    lucide.createIcons();

    // Mobile Menu Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');

            // Optional: Animate icon change (menu to x)
            const icon = mobileMenuBtn.querySelector('i');
            // This is a simple toggle, for more complex animations we might swap icons
        });
    }

    // Smooth scroll for anchor links (fallback for Safari if scroll-behavior: smooth isn't supported)
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();

            // Close mobile menu if open
            if (!mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.add('hidden');
            }

            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Form Submission Handling (Mock)
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();

            const btn = form.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;

            // Loading State
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader" class="w-5 h-5 animate-spin"></i> Enviando...';
            lucide.createIcons();

            // Simulate API call
            setTimeout(() => {
                btn.innerHTML = '<i data-lucide="check" class="w-5 h-5"></i> Recebido!';
                btn.classList.add('bg-green-600', 'hover:bg-green-700');
                btn.classList.remove('bg-northway-red', 'hover:bg-red-700');
                lucide.createIcons();

                // Construct WhatsApp Message
                const name = document.getElementById('name').value;
                const whatsapp = "5511999999999"; // Replace with actual number
                const message = `Olá, me chamo ${name} e gostaria de agendar um diagnóstico gratuito da NorthWay.`;
                const url = `https://wa.me/${whatsapp}?text=${encodeURIComponent(message)}`;

                // Redirect to WhatsApp after short delay
                setTimeout(() => {
                    window.open(url, '_blank');
                    // Reset form
                    form.reset();
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                    btn.classList.add('bg-northway-red', 'hover:bg-red-700');
                    lucide.createIcons();
                }, 1000);

            }, 1500);
        });
    }

    // Intersection Observer for Scroll Animations
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe elements that should animate on scroll
    document.querySelectorAll('section > div').forEach(section => {
        // Add a class to hide initially if no animation class is present
        // This is a simple implementation, ideally we'd add specific classes to specific elements
    });
});
