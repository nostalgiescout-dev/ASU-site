// Main JavaScript for the website

function toggleMenu(menuId) {
    const menu = document.getElementById(menuId);
    if (menu) {
        menu.classList.toggle('hidden');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('[data-mobile-menu-button]');
    const menu = document.querySelector('[data-mobile-menu]');
    if (!button || !menu) return;

    const setExpanded = (value) => button.setAttribute('aria-expanded', String(value));

    const close = () => {
        menu.classList.add('hidden');
        setExpanded(false);
    };

    const toggle = () => {
        const willOpen = menu.classList.contains('hidden');
        menu.classList.toggle('hidden', !willOpen);
        setExpanded(willOpen);
    };

    button.addEventListener('click', (event) => {
        event.preventDefault();
        toggle();
    });

    menu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => close());
    });

    document.addEventListener('click', (event) => {
        if (!menu.contains(event.target) && !button.contains(event.target)) close();
    });

    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') close();
    });

    window.addEventListener('resize', () => {
        if (window.matchMedia('(min-width: 1024px)').matches) close();
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const menus = Array.from(document.querySelectorAll('.lang-menu'));
    if (menus.length === 0) return;

    const closeAll = () => {
        menus.forEach((menu) => {
            menu.classList.remove('is-open');
            const button = menu.querySelector('.lang-button');
            if (button) button.setAttribute('aria-expanded', 'false');
        });
    };

    menus.forEach((menu) => {
        const button = menu.querySelector('.lang-button');
        if (!button) return;

        button.addEventListener('click', (event) => {
            event.preventDefault();
            const willOpen = !menu.classList.contains('is-open');
            closeAll();
            menu.classList.toggle('is-open', willOpen);
            button.setAttribute('aria-expanded', String(willOpen));
        });
    });

    document.addEventListener('click', (event) => {
        const clickedInsideAny = menus.some((menu) => menu.contains(event.target));
        if (!clickedInsideAny) closeAll();
    });

    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeAll();
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-newsletter-form]');
    const input = document.querySelector('[data-newsletter-input]');
    const feedback = document.querySelector('[data-newsletter-feedback]');

    if (!form || !input || !feedback) return;

    const setFeedback = (message, state) => {
        feedback.textContent = message;
        feedback.classList.remove('is-error', 'is-success');
        if (state) feedback.classList.add(state);
    };

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const value = input.value.trim();
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (!value) {
            setFeedback('Please enter your email address.', 'is-error');
            input.focus();
            return;
        }

        if (!emailPattern.test(value)) {
            setFeedback('Please enter a valid email address.', 'is-error');
            input.focus();
            return;
        }

        setFeedback('Thanks for subscribing. We will keep you inspired.', 'is-success');
        form.reset();
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const imageInput = document.querySelector('[data-image-preview-input]');
    const preview = document.querySelector('[data-image-preview-target]');
    const previewWrapperSelector = imageInput?.dataset.imagePreviewWrapperSelector;
    const previewWrapper = previewWrapperSelector ? document.querySelector(previewWrapperSelector) : preview?.parentElement;

    if (!imageInput || !preview) return;

    imageInput.addEventListener('change', () => {
        const [file] = imageInput.files || [];
        if (!file || !file.type.startsWith('image/')) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            preview.src = event.target?.result || '';
            if (previewWrapper) previewWrapper.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const dateInput = document.querySelector('[data-activity-date]');
    const statusSuggestion = document.querySelector('[data-status-suggestion]');

    if (!dateInput || !statusSuggestion) return;

    const labels = {
        upcoming: statusSuggestion.dataset.labelUpcoming || 'Upcoming',
        ongoing: statusSuggestion.dataset.labelOngoing || 'Ongoing',
        completed: statusSuggestion.dataset.labelCompleted || 'Completed'
    };
    const referenceDate = new Date('2026-08-21T00:00:00');

    const getSuggestedStatus = (value) => {
        if (!value) return 'upcoming';
        const selectedDate = new Date(value);
        if (Number.isNaN(selectedDate.getTime())) return 'upcoming';

        const selectedDay = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate());
        if (selectedDay.getTime() < referenceDate.getTime()) return 'completed';
        if (selectedDay.getTime() === referenceDate.getTime()) return 'ongoing';
        return 'upcoming';
    };

    const updateSuggestion = () => {
        const label = labels[getSuggestedStatus(dateInput.value)] || labels.upcoming;
        statusSuggestion.innerHTML = `الحالة المقترحة حاليًا: <span class="font-black text-primary">${label}</span>`;
    };

    updateSuggestion();
    dateInput.addEventListener('change', updateSuggestion);
    dateInput.addEventListener('input', updateSuggestion);
});
