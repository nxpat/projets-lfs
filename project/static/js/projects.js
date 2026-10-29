document.addEventListener('DOMContentLoaded', () => {
    const ajaxSearchInput = document.getElementById('ajax-search-input');
    const container = document.getElementById('projects');
    let debounceTimeout = null;
    let activeSearchController = null;

    if (ajaxSearchInput && container) {
        ajaxSearchInput.addEventListener('input', (e) => {
            const query = e.target.value;
            clearTimeout(debounceTimeout);

            debounceTimeout = setTimeout(() => {
                const url = new URL(window.location.href);
                url.searchParams.set('q', query);
                url.searchParams.set('page', 1);

                if (!query) url.searchParams.delete('q');

                if (activeSearchController) {
                    activeSearchController.abort();
                }
                activeSearchController = new AbortController();

                container.style.opacity = '0.5';

                fetch(url.toString(), {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    signal: activeSearchController.signal
                })
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newContainer = doc.getElementById('projects');

                    if (newContainer) {
                        container.innerHTML = newContainer.innerHTML;
                        container.style.opacity = '1';
                    }

                    window.history.pushState({}, '', url);

                    if (typeof Mark !== 'undefined' && query) {
                        const instance = new Mark(container);
                        instance.mark(query, { exclude: [".si", ".is-uppercase"] });
                    }
                })
                .catch(error => {
                    if (error.name === 'AbortError') return;
                    console.error('AJAX Search Error:', error);
                    container.style.opacity = '1';
                });
            }, 300);
        });
    }
});