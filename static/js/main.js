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
