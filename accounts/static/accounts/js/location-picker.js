(() => {
    'use strict';

    document.querySelectorAll('[data-location-picker]').forEach((picker) => {
        const input = picker.querySelector('.brand-location-control input');
        const codeInput = picker.querySelector('input[type="hidden"]');
        const toggle = picker.querySelector('.brand-location-toggle');
        const popup = picker.querySelector('.brand-location-popup');
        const list = picker.querySelector('[role="listbox"]');
        const status = picker.querySelector('[role="status"]');
        const endpoint = picker.dataset.locationUrl;
        if (!input || !codeInput || !toggle || !popup || !list || !status || !endpoint) return;

        let isOpen = false;
        let results = [];
        let activeIndex = -1;
        let revision = 0;
        let timer = null;
        let controller = null;
        const cachedResults = new Map();

        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-haspopup', 'listbox');
        input.setAttribute('aria-controls', list.id);
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('spellcheck', 'false');
        toggle.hidden = false;
        picker.classList.add('brand-location-picker--enhanced');

        function cancelSearch() {
            revision += 1;
            window.clearTimeout(timer);
            timer = null;
            if (controller) controller.abort();
            controller = null;
        }

        function setActive(index, scrollIntoView = true) {
            activeIndex = index;
            Array.from(list.children).forEach((option, optionIndex) => {
                option.setAttribute('aria-selected', String(optionIndex === index));
            });
            const activeOption = list.children[index];
            if (activeOption) {
                input.setAttribute('aria-activedescendant', activeOption.id);
                if (scrollIntoView) activeOption.scrollIntoView({ block: 'nearest' });
            } else {
                input.removeAttribute('aria-activedescendant');
            }
        }

        function resizePopup() {
            if (!isOpen) return;
            const viewport = window.visualViewport;
            const viewportHeight = viewport ? viewport.height : window.innerHeight;
            const viewportBottom = viewportHeight + (viewport ? viewport.offsetTop : 0);
            const availableHeight = viewportBottom - input.getBoundingClientRect().bottom - 14;
            popup.style.maxHeight = `${Math.max(80, Math.min(260, viewportHeight * .4, availableHeight))}px`;
        }

        function setOpen(open) {
            isOpen = open;
            popup.hidden = !open;
            picker.classList.toggle('brand-location-picker--open', open);
            input.setAttribute('aria-expanded', String(open));
            toggle.setAttribute('aria-expanded', String(open));
            toggle.setAttribute('aria-label', open ? 'Tutup pilihan kota' : 'Tampilkan pilihan kota');
            if (open) resizePopup();
            else {
                cancelSearch();
                setActive(-1);
                list.removeAttribute('aria-busy');
            }
        }

        function clearOptions(message, busy = false) {
            results = [];
            list.replaceChildren();
            setActive(-1);
            list.setAttribute('aria-busy', String(busy));
            status.textContent = message;
            status.hidden = !message;
        }

        function selectResult(index) {
            const result = results[index];
            if (!result) return;
            input.value = result.label;
            codeInput.value = result.code;
            setOpen(false);
            input.focus();
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function showResults(payload) {
            clearOptions('');
            results = payload.results.filter((result) => (
                result && typeof result.code === 'string' && typeof result.label === 'string'
            ));
            if (!results.length) {
                status.textContent = 'Kota tidak ditemukan. Kamu tetap bisa mengetik lokasi sendiri.';
                status.hidden = false;
                return;
            }
            const fragment = document.createDocumentFragment();
            results.forEach((result, index) => {
                const option = document.createElement('li');
                option.id = `${list.id}-${index}`;
                option.className = 'brand-location-option';
                option.setAttribute('role', 'option');
                option.setAttribute('aria-selected', 'false');
                option.textContent = result.label;
                option.addEventListener('pointerdown', (event) => event.preventDefault());
                option.addEventListener('click', () => selectResult(index));
                option.addEventListener('pointermove', () => setActive(index, false));
                fragment.appendChild(option);
            });
            list.appendChild(fragment);
            if (payload.has_more) {
                status.textContent = 'Ketik nama kota untuk mempersempit pilihan.';
                status.hidden = false;
            }
        }

        async function search(query) {
            cancelSearch();
            const requestRevision = revision;
            if (cachedResults.has(query)) {
                showResults(cachedResults.get(query));
                return;
            }
            clearOptions('Mencari kota…', true);
            controller = new AbortController();
            try {
                const url = new URL(endpoint, window.location.origin);
                url.searchParams.set('q', query);
                const response = await fetch(url, {
                    credentials: 'same-origin',
                    headers: { Accept: 'application/json' },
                    signal: controller.signal,
                });
                const payload = await response.json();
                if (requestRevision !== revision || !isOpen) return;
                if (!response.ok || !Array.isArray(payload.results)) {
                    const message = typeof payload.error === 'string' ? payload.error : 'Pilihan kota belum tersedia.';
                    throw new Error(message);
                }
                cachedResults.set(query, payload);
                showResults(payload);
            } catch (error) {
                if (requestRevision !== revision || !isOpen || error.name === 'AbortError') return;
                const message = error instanceof SyntaxError || error instanceof TypeError
                    ? 'Pilihan kota belum tersedia.' : error.message;
                clearOptions(`${message} Kamu tetap bisa mengetik lokasi sendiri.`);
            } finally {
                if (requestRevision === revision) {
                    list.removeAttribute('aria-busy');
                    controller = null;
                }
            }
        }

        function openWithResults() {
            if (input.readOnly || input.disabled) return;
            setOpen(true);
            search(codeInput.value ? '' : input.value.trim());
        }

        toggle.addEventListener('pointerdown', (event) => event.preventDefault());
        toggle.addEventListener('click', () => {
            if (isOpen) setOpen(false);
            else openWithResults();
            input.focus();
        });
        input.addEventListener('click', () => {
            if (!isOpen) openWithResults();
        });
        input.addEventListener('input', () => {
            if (input.readOnly || input.disabled) return;
            codeInput.value = '';
            cancelSearch();
            setOpen(true);
            clearOptions('Mencari kota…', true);
            const query = input.value.trim();
            timer = window.setTimeout(() => search(query), 300);
        });
        input.addEventListener('keydown', (event) => {
            if ((input.readOnly || input.disabled) && event.key !== 'Escape') return;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (!isOpen) {
                    openWithResults();
                    return;
                }
                if (results.length) {
                    const direction = event.key === 'ArrowDown' ? 1 : -1;
                    const nextIndex = activeIndex < 0
                        ? (direction > 0 ? 0 : results.length - 1)
                        : (activeIndex + direction + results.length) % results.length;
                    setActive(nextIndex);
                }
            } else if (event.key === 'Enter' && isOpen && activeIndex >= 0) {
                event.preventDefault();
                selectResult(activeIndex);
            } else if (event.key === 'Escape' && isOpen) {
                event.preventDefault();
                setOpen(false);
            } else if (event.key === 'Tab') {
                setOpen(false);
            }
        });
        document.addEventListener('pointerdown', (event) => {
            if (!picker.contains(event.target)) setOpen(false);
        });
        picker.addEventListener('focusout', (event) => {
            if (!picker.contains(event.relatedTarget)) setOpen(false);
        });
        input.form?.addEventListener('submit', () => setOpen(false));
        window.addEventListener('resize', resizePopup, { passive: true });
        window.addEventListener('scroll', resizePopup, { passive: true });
        window.visualViewport?.addEventListener('resize', resizePopup, { passive: true });
        window.visualViewport?.addEventListener('scroll', resizePopup, { passive: true });
    });
})();
