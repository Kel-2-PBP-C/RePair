(() => {
    'use strict';

    const containers = document.querySelectorAll('[data-account-deleted-notifications]');
    if (!containers.length) return;

    if (window.location.hash === '#account-status') {
        window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
    }

    containers.forEach((container) => {
        const notification = container.querySelector('[data-notification]');
        const close = container.querySelector('[data-notification-close]');
        if (!notification || !close) return;

        let timer;
        let dismissed = false;
        const pause = () => window.clearTimeout(timer);
        const dismiss = () => {
            dismissed = true;
            pause();
            document.removeEventListener('visibilitychange', schedule);
            container.remove();
        };
        function schedule() {
            pause();
            if (!dismissed && !document.hidden && !notification.matches(':hover') && !notification.contains(document.activeElement)) {
                timer = window.setTimeout(dismiss, 8000);
            }
        }

        close.hidden = false;
        close.addEventListener('click', dismiss);
        notification.addEventListener('mouseenter', pause);
        notification.addEventListener('mouseleave', schedule);
        notification.addEventListener('focusin', pause);
        notification.addEventListener('focusout', () => window.queueMicrotask(schedule));
        document.addEventListener('visibilitychange', schedule);
        schedule();
    });
})();
