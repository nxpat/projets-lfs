// ==========================================
// 1. INITIALIZATION (The Bootstrapper)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // UI & Navigation
    initNavbarBurger();
    initTabsNavigation();
    initFooterYear();
    
    // Core Features
    initThemeSwitcher();
    initProjectAccordions();
    initFloatingScrollButtons();
    initSearchBar();
    
    // Components
    initModals();
    initNotifications();
    initTextAreas();
    
    // Global Event Listeners
    initSubmitButton();
    initClickOnceButton();
    initFocusEvent();
});

// Global variable to hold modal history state
let originalHistoryContent = '';

// Variable to hold the debounce timer for the Search Bar Filter
let searchTimeout;


// ==========================================
// 2. FEATURE FUNCTIONS
// ==========================================

// --- Navigation ---
function initNavbarBurger() {
    const burger = document.querySelector('.navbar-burger');
    const menu = document.querySelector('.navbar-menu');
    
    if (!burger || !menu) return;

    burger.addEventListener('click', () => {
        burger.classList.toggle('is-active');
        menu.classList.toggle('is-active');
    });
}

// --- Tabs ---
function initTabsNavigation() {
    const tabs = document.querySelectorAll('.tabs li');
    if (tabs.length === 0) return;

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            // Set the active tab
            const currentTabs = tab.parentNode.querySelectorAll('li');
            currentTabs.forEach(item => item.classList.remove('is-active'));
            tab.classList.add('is-active');

            const target = tab.dataset.target;
            // Get the tab content
            const tabContent = tab.closest('.tabs').parentNode.querySelectorAll(':scope > .tab-content > div');
            // Show the selected tab
            handleTabVisibility(tabContent, target);
        });
    });
}

// --- Footer ---
function initFooterYear() {
    const yearSpan = document.getElementById("this-year");
    if (yearSpan) {
        yearSpan.textContent = new Date().getFullYear();
    }
}

// --- Theme Switcher ---
function initThemeSwitcher() {
    const themeSwitches = document.querySelectorAll('.theme-switch');
    if (themeSwitches.length === 0) return;

    const htmlElement = document.documentElement;
    const appWrapper = document.getElementById('app-wrapper');
    const mainLogo = document.getElementById('main-logo');
    const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');

    const applyThemeDOM = (themeName) => {
        if (themeName === 'legacy') {
            htmlElement.setAttribute('data-theme', 'light');
            htmlElement.classList.remove('lfs-palette');
            if (appWrapper) {
                appWrapper.classList.remove('is-info', 'has-background-black-bis');
                appWrapper.classList.add('is-primary');
            }
            if (mainLogo) mainLogo.src = mainLogo.dataset.logoLight;
        } else if (themeName === 'dark') {
            htmlElement.setAttribute('data-theme', 'dark');
            htmlElement.classList.add('lfs-palette');
            if (appWrapper) {
                appWrapper.classList.remove('is-info', 'is-primary');
                appWrapper.classList.add('has-background-black-bis');
            }
            if (mainLogo) mainLogo.src = mainLogo.dataset.logoDark;
        } else {
            // Default: light
            htmlElement.setAttribute('data-theme', 'light');
            htmlElement.classList.add('lfs-palette');
            if (appWrapper) {
                appWrapper.classList.remove('is-primary', 'has-background-black-bis');
                appWrapper.classList.add('is-info');
            }
            if (mainLogo) mainLogo.src = mainLogo.dataset.logoLight;
        }
    };

    themeSwitches.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTheme = button.getAttribute('data-target-theme');
            
            // Instantly update the UI
            applyThemeDOM(targetTheme);
            
            // Send asynchronous POST request to Flask
            if (csrfTokenMeta) {
                fetch('/set_theme', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfTokenMeta.getAttribute('content')
                    },
                    body: JSON.stringify({ theme: targetTheme })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status !== 'success') console.error('Failed to save theme to session.');
                })
                .catch(error => console.error('Error:', error));
            }
        });
    });
}

// --- Project Accordions ---
function initProjectAccordions() {
    const cardHeaders = document.querySelectorAll('.card-header');
    if (cardHeaders.length === 0) return;

    cardHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const currentCard = header.closest('.card');
            const currentContent = currentCard.querySelector('.toggle-project');
            const currentIcon = header.querySelector('.chevron-icon');
            
            if (!currentContent) return;

            const isCurrentlyOpen = !currentContent.classList.contains('is-hidden');

            // Close ALL cards (Exclusive accordion behavior)
            document.querySelectorAll('.card').forEach(card => {
                const content = card.querySelector('.toggle-project');
                const icon = card.querySelector('.chevron-icon');
                if (content) content.classList.add('is-hidden');
                if (icon) icon.style.transform = 'rotate(0deg)';
            });

            // If the clicked card was CLOSED, open it up
            if (!isCurrentlyOpen) {
                currentContent.classList.remove('is-hidden');
                if (currentIcon) currentIcon.style.transform = 'rotate(180deg)';
            }
        });
    });
}

// --- Floating Scroll Buttons ---
function initFloatingScrollButtons() {
    const btnScrollTop = document.getElementById('btn-scroll-top');
    const btnScrollBottom = document.getElementById('btn-scroll-bottom');

    if (!btnScrollTop || !btnScrollBottom) return;
        
    btnScrollTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    btnScrollBottom.addEventListener('click', () => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));

    const toggleScrollButtons = () => {
        const scrollY = window.scrollY;
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        
        let isTopVisible = scrollY > 200;
        let isBottomVisible = scrollY < maxScroll - 200;

        // Toggle Top Button
        if (isTopVisible) btnScrollTop.classList.add('is-visible');
        else btnScrollTop.classList.remove('is-visible');
        
        // Toggle Bottom Button
        if (isBottomVisible) btnScrollBottom.classList.add('is-visible');
        else btnScrollBottom.classList.remove('is-visible');
    };

    window.addEventListener('scroll', toggleScrollButtons);
    toggleScrollButtons(); 
}

// --- Search Bar Filter ---
function initSearchBar() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;

    searchInput.addEventListener('input', function () {
        const rawInput = this.value;
        const lowerInput = rawInput.toLowerCase();
        
        clearTimeout(searchTimeout);
        
        searchTimeout = setTimeout(() => {
            const projectCards = document.querySelectorAll('.card');
            if (projectCards.length === 0) return;

            let visibleCount = 0;

            // 1. FILTERING BY EXPLICIT CLASS
            projectCards.forEach(card => {
                // Grab the title and anything explicitly marked as searchable
                const targetElements = card.querySelectorAll('.card-header-title, .is-searchable');
                
                const projectText = Array.from(targetElements)
                                         .map(el => el.textContent)
                                         .join(' ')
                                         .toLowerCase();

                if (projectText.includes(lowerInput)) {
                    card.classList.remove('is-hidden');
                    visibleCount++;
                } else {
                    card.classList.add('is-hidden');
                }
            });

            // 2. NO RESULTS STATE
            handleNoResults(visibleCount, rawInput);

            // 3. TARGETED HIGHLIGHTING
            if (typeof Mark !== 'undefined') {
                // Only highlight inside the title and explicit search zones
                const highlightAreas = document.querySelectorAll('.card .card-header-title, .card .is-searchable');
                
                const instance = new Mark(highlightAreas);
                instance.unmark({
                    done: function () {
                        if (rawInput) {
                            instance.mark(rawInput, {
                                exclude: [".si"]
                            });
                        }
                    }
                });
            }
        }, 250);  // The 250 millisecond delay
    });
}

// Helper function for the empty state
function handleNoResults(visibleCount, query) {
    let noResultsMsg = document.getElementById('no-results-message');
    
    if (visibleCount === 0) {
        // If it doesn't exist yet, create it
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('div');
            noResultsMsg.id = 'no-results-message';
            noResultsMsg.className = 'notification is-primary-soft has-text-centered mt-4 fadeOut';
            
            // Safely inject it at the top of the #projects container!
            const projectsContainer = document.getElementById('projects');
            if (projectsContainer) {
                projectsContainer.prepend(noResultsMsg);
            }
        }
        // French translation
        noResultsMsg.innerHTML = `Aucun projet trouvé pour "<strong>${query}</strong>".`;
        noResultsMsg.style.display = 'block';
    } else if (noResultsMsg) {
        // Hide it if there are results
        noResultsMsg.style.display = 'none';
    }
}

// --- Notifications (Dismiss) ---
function initNotifications() {
    // Listen for a click ANYWHERE on the page
    document.addEventListener('click', () => {
        // Find all notifications that have a delete button and remove them
        document.querySelectorAll('.notification .delete').forEach(($delete) => {
            const notif = $delete.closest('.notification');
            if (notif) notif.remove();
        });
    });
}

// --- Text Areas ---
function initTextAreas() {
    const textareas = document.querySelectorAll('textarea');
    if (textareas.length === 0) return;

    textareas.forEach(textarea => {
        textarea.addEventListener('input', () => adjustHeight(textarea));
        adjustHeight(textarea); // Adjust on load
    });
}

// --- Submit Once Event ---
function initSubmitButton() {
    const submitButtons = document.querySelectorAll('.submit-once');

    submitButtons.forEach(function (submitButton) {
        submitButton.addEventListener("click", function (event) {
            // check if the form is valid
            if (!this.form.checkValidity()) return; // If not valid, exit

            // send the form if valid
            // this.form.submit();  // The submit button should not be named 'submit' for this line to work!
            HTMLFormElement.prototype.submit.call(this.form)

            this.disabled = true;
            this.classList.add('is-loading');
        });
    });
}

// --- Click Once Event ---
function initClickOnceButton() {
    const buttons = document.querySelectorAll('.click-once');

    buttons.forEach(function (button) {
        button.addEventListener("click", function (event) {
            this.disabled = true;
            this.classList.add('is-loading');
        });
    });
}

// --- Focus Event ---
function initFocusEvent() {
    // Re-enable disabled buttons and hide working modal when window regains focus
    window.addEventListener('focus', () => { 
        document.querySelectorAll('button[disabled]').forEach(button => {
            button.removeAttribute('disabled');
            button.classList.remove('is-loading');
        });
        
        const modalWorking = document.getElementById('modal-working');
        if (modalWorking) modalWorking.classList.remove('is-active');
    });
}

// --- Modals ---
function initModals() {
    const triggers = document.querySelectorAll('.js-modal-trigger');
    const closeElements = document.querySelectorAll('.modal-background, .modal-close, .modal-card-head .delete, .modal-card-foot .button');

    // Open Modal Triggers
    triggers.forEach(($trigger) => {
        $trigger.addEventListener('click', () => {
            const list = ['modal-delete', 'modal-validate', 'modal-approve', 'modal-devalidate', 'modal-history', 'modal-reject'];
            const list2 = ['modal-working'];

            const modalId = $trigger.dataset.target;
            const $target = document.getElementById(modalId);
            if (!$target) return;

            if (list.includes(modalId)) {
                const projectTitle = $trigger.dataset.projectTitle;
                const titleSpan = $target.querySelector('h3 span.project-title');
                if (titleSpan) titleSpan.textContent = projectTitle;

                const projectId = $trigger.dataset.projectId;
                const form = $target.querySelector('form');

                switch (modalId) {
                    case 'modal-history':
                        fetchHistoryData(projectId);
                        break;
                    case 'modal-delete':
                        if (form) form.action = '/project/delete/' + projectId;
                        break;
                    case 'modal-approve':
                    case 'modal-validate':
                        if (form) form.action = '/project/validation/' + projectId;
                        break;
                    case 'modal-devalidate':
                        if (form) form.action = '/project/devalidation/' + projectId;
                        break;
                    case 'modal-reject':
                        if (form) form.action = '/project/reject/' + projectId;
                        break;
                    default:
                        console.warn('Unknown modal ID:', modalId);
                }

                $target.querySelectorAll('span.current-user').forEach(span => {
                    if (typeof user !== 'undefined') span.textContent = user;
                });
            } else if (list2.includes(modalId)) {
                const message = $trigger.dataset.message;
                const btnSpan = $target.querySelector('button span');
                if (btnSpan) btnSpan.textContent = message;
            }
            
            openModal($target);
        });
    });

    // Close Modal Triggers
    closeElements.forEach(($close) => {
        $close.addEventListener('click', () => {
            const targetModal = $close.closest('.modal');
        
            // Prevent closing if the modal is the loading overlay
            if (targetModal && targetModal.id === 'modal-working') {
                return; 
            }
            
            closeModal(targetModal);
        });
    });

    // Keyboard Escape
    document.addEventListener('keydown', (event) => {
        if (event.key === "Escape") closeAllModals();
    });
}


// ==========================================
// 3. UTILITY FUNCTIONS (Callable globally)
// ==========================================

function openModal($el) {
    if (!$el) return;
    
    $el.classList.add('is-active');

    // Scroll Locking: Freeze the background page
    document.documentElement.classList.add('is-clipped');

    // Auto-Focusing: Focus the first input field smoothly
    setTimeout(() => {
        const firstInput = $el.querySelector('input:not([type="hidden"]), textarea, select');
        if (firstInput) firstInput.focus();
    }, 100); // 100ms delay ensures the modal is fully visible before focusing
}

function closeModal($el) {
    if (!$el) return;
    
    $el.classList.remove('is-active');

    // Scroll Locking: Unfreeze the background page 
    if (document.querySelectorAll('.modal.is-active').length === 0) {
        document.documentElement.classList.remove('is-clipped');
    }

    // Restore original content if closing history modal
    if ($el.id === 'modal-history' && originalHistoryContent) {
        const historyContent = document.getElementById('historyContent');
        if (historyContent) historyContent.innerHTML = originalHistoryContent;
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal.is-active').forEach(($modal) => closeModal($modal));
}


function handleTabVisibility(tabContent, target) {
    tabContent.forEach(content => {
        if (content.getAttribute('id') === target) {
            content.classList.remove('is-hidden');
        } else {
            content.classList.add('is-hidden');
        }
    });
}

function tabSelector(selectElement) {
    const target = selectElement.value;
    const tabContent = selectElement.closest('.tabs-dropdown').parentNode.querySelectorAll(':scope > .tab-content > div');
    handleTabVisibility(tabContent, target);
}

function submitForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    if (typeof form.submit === 'function') {
        form.submit();
    } else {
        HTMLFormElement.prototype.submit.call(form);
    }

    const selectElement = form.querySelector('select');
    if (selectElement) {
        selectElement.disabled = true;
        const parentDiv = selectElement.parentElement;
        if (parentDiv && parentDiv.tagName === 'DIV') {
            parentDiv.classList.add('is-loading');
        }
    }
}

// --- Text Area Utilities ---
function getVisibleLines(textarea) {
    const style = window.getComputedStyle(textarea);
    const mirror = document.createElement('div');
    
    const stylesToCopy = [
        'border', 'boxSizing', 'fontFamily', 'fontSize', 'fontWeight',
        'letterSpacing', 'lineHeight', 'padding', 'textDecoration',
        'textTransform', 'width', 'wordSpacing', 'wordWrap', 
        'whiteSpace', 'paddingLeft', 'paddingRight'
    ];

    stylesToCopy.forEach(prop => mirror.style[prop] = style[prop]);

    mirror.style.position = 'absolute';
    mirror.style.visibility = 'hidden';
    mirror.style.height = 'auto';
    mirror.style.overflow = 'hidden';
    mirror.textContent = textarea.value.replace(/\n$/, '\n\u00A0');

    document.body.appendChild(mirror);
    const totalHeight = mirror.clientHeight;
    
    let lineHeight = parseFloat(style.lineHeight);
    if (isNaN(lineHeight)) lineHeight = parseFloat(style.fontSize) * 1.2; 

    const lineCount = Math.floor(totalHeight / lineHeight);
    document.body.removeChild(mirror);

    return lineCount;
}

function adjustHeight(textarea) {
    const minRows = parseInt(textarea.dataset.rows) || 2; // Default to 2 if missing
    const maxRows = 37;
    textarea.rows = Math.min(Math.max(minRows, getVisibleLines(textarea)), maxRows);
}

// --- Async Fetch Utilities ---
async function fetchHistoryData(projectId) {
    const urlRootEl = document.getElementById('url-root');
    if (!urlRootEl) return;
    
    const url = `${urlRootEl.href}history/${projectId}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Response status: ${response.status}`);

        const data = await response.json();
        const historyContent = document.getElementById('historyContent');
        
        if (historyContent) {
            originalHistoryContent = historyContent.innerHTML;
            historyContent.innerHTML = data.html;
        }
    } catch (error) {
        console.error('Error fetching history:', error.message);
    }
}

async function asyncQueuedAction(actionId) {
    const notification_overlay = document.querySelector(".notification-overlay ul");
    const urlRootEl = document.getElementById('url-root');
    if (!notification_overlay || !urlRootEl) return;

    const url = `${urlRootEl.href}action/${actionId}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Response status: ${response.status}`);

        const data = await response.json();
        const newNotification = document.createElement('div');
        
        if (data.html === "Done!") {
            newNotification.setAttribute("class", "fadeOut");
            newNotification.innerHTML = `<li class="notification is-success mb-3" onclick="this.parentElement.style.display='none';">
            <button class="delete"></button>
            <article class="media is-align-items-center">
                <div class="media-left">
                    <figure class="image is-24x24">
                        <span class="si si-24px mdi--success-circle-outline has-text-primary-20" aria-hidden="true"></span>
                    </figure>
                </div>
                <div class="media-content">
                    <div class="content pr-5">
                        <p class="mb-0">Notification envoyée avec succès !</p>
                    </div>
                </div>
            </article></li>`;
        } else if (data.html === "Failed!") {
            newNotification.innerHTML = `<li class="notification is-warning mb-3" onclick="this.parentElement.style.display='none';">
            <button class="delete"></button>
            <article class="media is-align-items-center">
                <div class="media-left">
                    <figure class="image is-24x24">
                        <span class="si si-24px mdi--warning-circle-outline has-text-danger has-text-weight-bold" aria-hidden="true"></span>
                    </figure>
                </div>
                <div class="media-content">
                    <div class="content pr-5">
                        <p class="mb-0">Erreur : aucune notification n'a pu être envoyée.</p>
                    </div>
                </div>
            </article></li>`;
        }

        if (data.html === "Done!" || data.html === "Failed!") {
            notification_overlay.insertAdjacentElement('beforeend', newNotification);
        }
    } catch (error) {
        console.error('Error executing action:', error.message);
    }
}