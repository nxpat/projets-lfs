// 
// burger navigation
//
const burger = document.querySelector('.navbar-burger');
const menu = document.querySelector('.navbar-menu');
burger.addEventListener('click', function () {
    burger.classList.toggle('is-active');
    menu.classList.toggle('is-active');
});


//
// tabs navigation
//

// Function to handle tab visibility
function handleTabVisibility(tabContent, target) {
    tabContent.forEach(content => {
        if (content.getAttribute('id') === target) {
            content.classList.remove('is-hidden');
        } else {
            content.classList.add('is-hidden');
        }
    });
}

// Event listener to handle tab selection from tab clicks
const tabs = document.querySelectorAll('.tabs li');

tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
        // set the active tab
        const currentTabs = tab.parentNode.querySelectorAll('li');
        currentTabs.forEach(item => item.classList.remove('is-active'))
        tab.classList.add('is-active');

        const target = tab.dataset.target;
        // get the tab content
        const tabContent = tab.closest('.tabs').parentNode.querySelectorAll(':scope > .tab-content > div');
        // show the selected tab (target) from tab content
        handleTabVisibility(tabContent, target);
    });
});

// Function to handle tab selection from dropdown
function tabSelector(selectElement) {
    // get the tab id to display
    const target = selectElement.value;

    // Get the tab content within the same box as the select dropdown
    const tabContent = selectElement.closest('.tabs-dropdown').parentNode.querySelectorAll(':scope > .tab-content > div');
    // show the selected tab (target) from tab content
    handleTabVisibility(tabContent, target);
}

//
// Update to the current year in the footer
//
window.onload = function () {
    document.getElementById("this-year").innerHTML = (new Date().getFullYear());
};


// 
// modals
//
// Functions to open and close a modal
function openModal($el) {
    $el.classList.add('is-active');
}

function closeModal($el) {
    $el.classList.remove('is-active');

    // Check if the modal being closed is the history modal
    if ($el.id === 'modal-history') {
        // Restore the original content
        if (originalHistoryContent) {
            document.getElementById('historyContent').innerHTML = originalHistoryContent;
        }
    }
}

function closeAllModals() {
    (document.querySelectorAll('.modal') || []).forEach(($modal) => {
        closeModal($modal);
    });
}

// Add a click event on buttons to open a specific modal
(document.querySelectorAll('.js-modal-trigger') || []).forEach(($trigger) => {
    const list = ['modal-delete', 'modal-validate', 'modal-agree', 'modal-devalidate', 'modal-history', 'modal-reject'];
    const list2 = ['modal-working'];

    const modal = $trigger.dataset.target;
    const $target = document.getElementById(modal);

    $trigger.addEventListener('click', () => {
        if (list.includes(modal)) {
            const projectTitle = $trigger.dataset.projectTitle;
            $target.querySelector('h3 span.project-title').textContent = projectTitle;

            const projectId = $trigger.dataset.projectId;
            switch (modal) {
                case 'modal-history':
                    fetchHistoryData(projectId);
                    break;
                case 'modal-delete':
                    $target.querySelector('form').action = '/project/delete/' + projectId;
                    break;
                case 'modal-agree':
                case 'modal-validate':
                    $target.querySelector('form').action = '/project/validation/' + projectId;
                    break;
                case 'modal-devalidate':
                    $target.querySelector('form').action = '/project/devalidation/' + projectId;
                    break;
                case 'modal-reject':
                    $target.querySelector('form').action = '/project/reject/' + projectId;
            }

            // Update the text content of all span elements with the class 'current-user' to the current_user name
            const spans = $target.querySelectorAll('span.current-user');
            spans.forEach(span => {
                span.textContent = user;
            });
        }
        else if (list2.includes(modal)) {
            const message = $trigger.dataset.message;
            $target.querySelector('button span').textContent = message;
        }
        openModal($target);
    });
});

// Add a click event on various child elements to close the parent modal
(document.querySelectorAll('.modal-background, .modal-close, .modal-card-head .delete, .modal-card-foot .button') || []).forEach(($close) => {
    const $target = $close.closest('.modal');

    $close.addEventListener('click', () => {
        closeModal($target);
    });
});

// Add a keyboard event to close all modals
document.addEventListener('keydown', (event) => {
    if (event.key === "Escape") {
        closeAllModals();
    }
});


// fetch data for history modal (project and projects pages)
async function fetchHistoryData(projectId) {
    const urlRoot = document.getElementById('url-root').href;
    const url = `${urlRoot}history/${projectId}`;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Response status: ${response.status}`);
        }

        const data = await response.json();
        // Store the original content before updating
        originalHistoryContent = document.getElementById('historyContent').innerHTML;
        // Update content
        document.getElementById('historyContent').innerHTML = data.html;
    } catch (error) {
        console.error('Error fetching history:', error.message);
    }
}


//
// Event listener for visibility change
// to re-enable disabled buttons
//
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        // Get all buttons with the disabled attribute
        const disabledButtons = document.querySelectorAll('button[disabled]');
        // Re-enable the button when the page becomes visible
        disabledButtons.forEach(button => {
            button.removeAttribute('disabled');
            // remove the "is-loading" class to the button
            button.classList.remove('is-loading');
        });
    } else {
        // hide working modal
        const modalWorking = document.getElementById('modal-working');
        if (modalWorking) {
            modalWorking.classList.remove('is-active');
        }
    }
});


//
// Filter projects with the search bar (projects page)
//
const searchInput = document.getElementById('searchInput');

if (searchInput) {
    searchInput.addEventListener('input', function () {
        const input = this.value;
        const projectBoxes = document.querySelectorAll('#projects .box');  // require a div with id="projects"

        projectBoxes.forEach(box => {
            // Get all text content from the details element within the box
            const projectText = box.textContent.toLowerCase();

            // Check if the search input is included in the project text
            if (projectText.includes(input.toLowerCase())) {
                box.classList.remove('is-hidden');
            } else {
                box.classList.add('is-hidden');
            }
        });

        // Clear previous highlights
        const instance = new Mark(projectBoxes);
        instance.unmark({
            done: function () {
                // Highlight the new input
                if (input) {
                    instance.mark(input);
                }
            }
        });
    });
}


function filterProjects() {
    const searchInput = document.getElementById('search').value.toLowerCase();
    const projectBoxes = document.querySelectorAll('#projects .box');  // require a div with id="projects"
    const instance = new Mark(projectBoxes); // Initialize mark.js

    projectBoxes.forEach(box => {
        // Get all text content from the details element within the box
        const projectText = box.textContent.toLowerCase();

        // Check if the search input is included in the project text
        if (projectText.includes(searchInput)) {
            box.classList.remove('is-hidden');
        } else {
            box.classList.add('is-hidden');
        }

        // Highlight text (mark.js)
        // Clear previous highlights
        instance.unmark({
            done: function () {
                // Highlight the new search term
                if (searchInput) {
                    instance.mark(searchInput);
                }
            }
        });
    });
}

// submit form automatically (select school year, department)
function submitForm(formId) {
    const form = document.getElementById(formId);

    if (typeof form.submit === 'function') {
        from.submit();
    } else {
        HTMLFormElement.prototype.submit.call(form);
    }

    // get the select element
    const selectElement = form.querySelector('select');
    if (selectElement) {
        // disable select element
        selectElement.disabled = true;
        // get the immediate parent div of the select element
        var parentDiv = selectElement.parentElement;

        // check if the parent is a div and add the loading class
        if (parentDiv && parentDiv.tagName === 'DIV') {
            parentDiv.classList.add('is-loading');
        }
    }
}

// send queued action execution request
async function asyncQueuedAction(actionId) {
    const notification_overlay = document.querySelector(".notification-overlay ul");
    const urlRoot = document.getElementById('url-root').href;
    const url = `${urlRoot}action/${actionId}`;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Response status: ${response.status}`);
        }

        const data = await response.json();
        // console.log(data.html);

        // flash response to user
        var newNotification = document.createElement('div');
        if (data.html === "Done!") {
            const message = '<li class="notification is-success mb-3" onclick="this.parentElement.style.display=\'none\';"><p class="pr-5">Notification envoyée avec succès !</p><button class="delete"></button></li>';
            newNotification.setAttribute("class", "fadeOut");
            newNotification.innerHTML = message;
            notification_overlay.insertAdjacentElement('beforeend', newNotification);
        }
        else if (data.html === "Failed!") {
            const message = '<li class="notification is-warning mb-3" onclick="this.parentElement.style.display=\'none\';"><p class="pr-5">Erreur : aucune notification n\'a pu être envoyée.</p><button class="delete"></button></li>';
            newNotification.innerHTML = message;
            notification_overlay.insertAdjacentElement('beforeend', newNotification);
        }


    } catch (error) {
        console.error('Error executing action:', error.message);
    }
}