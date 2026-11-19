(() => {
    'use strict';

    const container = document.getElementById('toast-container');
    if (!container) return;

    const variants = {
        success: { title: 'Berhasil', icon: 'M20 6 9 17l-5-5' },
        info: { title: 'Informasi', icon: 'M12 16v-4m0-4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z' },
        warning: { title: 'Perlu diperhatikan', icon: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18.1A2 2 0 0 0 3.5 21h17a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0Z' },
        error: { title: 'Terjadi kesalahan', icon: 'M18 6 6 18M6 6l12 12' },
    };

    function normalizeType(type) {
        const value = String(type || 'info').toLowerCase().split(/\s+/);
        if (value.some((tag) => ['error', 'danger'].includes(tag))) return 'error';
        if (value.includes('warning')) return 'warning';
        if (value.some((tag) => ['success', 'add', 'delete', 'created', 'updated'].includes(tag))) return 'success';
        return 'info';
    }

    function createIcon(pathData) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('aria-hidden', 'true');
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', pathData);
        svg.appendChild(path);
        return svg;
    }

    function showToast(messageOrOptions, type = 'info', duration = 3600) {
        const options = typeof messageOrOptions === 'object' && messageOrOptions !== null
            ? messageOrOptions
            : { message: messageOrOptions, type, duration };
        const variant = normalizeType(options.type);
        const config = variants[variant];
        const title = String(options.title || config.title);
        const message = String(options.message || '');
        const timeout = Number.isFinite(Number(options.duration))
            ? Math.max(0, Number(options.duration))
            : 3600;

        const toast = document.createElement('div');
        toast.className = `toast-card toast-card--${variant}`;
        toast.setAttribute('role', variant === 'error' ? 'alert' : 'status');
        toast.style.setProperty('--toast-duration', `${timeout}ms`);

        const icon = document.createElement('span');
        icon.className = 'toast-icon-wrap';
        icon.appendChild(createIcon(config.icon));

        const copy = document.createElement('div');
        copy.className = 'toast-copy';
        const heading = document.createElement('p');
        heading.className = 'toast-title';
        heading.textContent = title;
        copy.appendChild(heading);
        if (message) {
            const body = document.createElement('p');
            body.className = 'toast-message';
            body.textContent = message;
            copy.appendChild(body);
        }

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'toast-close';
        close.setAttribute('aria-label', 'Tutup notifikasi');
        close.appendChild(createIcon('M18 6 6 18M6 6l12 12'));

        const progress = document.createElement('span');
        progress.className = 'toast-progress-bar';
        progress.setAttribute('aria-hidden', 'true');
        toast.append(icon, copy, close, progress);

        let remaining = timeout;
        let startedAt = 0;
        let timer = null;
        let removed = false;
        let isHovered = false;
        let hasFocus = false;

        function dismiss() {
            if (removed) return;
            removed = true;
            window.clearTimeout(timer);
            toast.classList.remove('is-visible');
            toast.classList.add('is-leaving');
            window.setTimeout(() => {
                toast.remove();
                if (!container.childElementCount && container.matches(':popover-open')) {
                    container.hidePopover();
                }
            }, 200);
        }

        function startTimer() {
            if (removed || isHovered || hasFocus) return;
            if (remaining <= 0) {
                dismiss();
                return;
            }
            startedAt = performance.now();
            timer = window.setTimeout(dismiss, remaining);
        }

        function pauseTimer() {
            toast.classList.add('is-paused');
            if (timer === null || removed) return;
            window.clearTimeout(timer);
            timer = null;
            remaining = Math.max(0, remaining - (performance.now() - startedAt));
        }

        function resumeTimer() {
            if (isHovered || hasFocus || !toast.classList.contains('is-paused') || removed) return;
            toast.classList.remove('is-paused');
            startTimer();
        }

        toast.addEventListener('pointerenter', () => {
            isHovered = true;
            pauseTimer();
        });
        toast.addEventListener('pointerleave', () => {
            isHovered = false;
            resumeTimer();
        });
        toast.addEventListener('focusin', () => {
            hasFocus = true;
            pauseTimer();
        });
        toast.addEventListener('focusout', (event) => {
            if (!toast.contains(event.relatedTarget)) {
                hasFocus = false;
                resumeTimer();
            }
        });
        close.addEventListener('click', dismiss);

        container.appendChild(toast);
        if (typeof container.showPopover === 'function' && !container.matches(':popover-open')) {
            container.showPopover();
        }
        window.requestAnimationFrame(() => {
            if (removed) return;
            toast.classList.add('is-visible');
            startTimer();
        });
        return toast;
    }

    window.showToast = showToast;

    function showQueuedMessages() {
        document.querySelectorAll('[data-toast-message]').forEach((message) => {
            if (message.dataset.accountDeleted && window.location.hash === '#account-status') {
                window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
            }
            showToast({
                type: message.dataset.type,
                message: message.textContent.trim(),
                duration: message.dataset.duration,
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', showQueuedMessages, { once: true });
    } else {
        showQueuedMessages();
    }
})();