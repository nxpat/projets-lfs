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
    const list = ['modal-delete', 'modal-validate', 'modal-approve', 'modal-devalidate', 'modal-history', 'modal-reject'];
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
                case 'modal-approve':
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
// Event listeners
// to re-enable disabled buttons and hide working modal
//
window.addEventListener('focus', () => { 
    // When the window regains focus
    // Get all buttons with the disabled attribute
    const disabledButtons = document.querySelectorAll('button[disabled]');

    // Re-enable the buttons
    disabledButtons.forEach(button => {
        button.removeAttribute('disabled');
        // remove the "is-loading" class to the button
        button.classList.remove('is-loading');
    });
    
    // hide working modal
    const modalWorking = document.getElementById('modal-working');
    if (modalWorking) {
        modalWorking.classList.remove('is-active');
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
            const message = `<li class="notification is-success mb-3" onclick="this.parentElement.style.display=\'none\';">
            <button class="delete"></button>
            <article class="media">
                <div class="media-left">
                    <figure class="image is-24x24">
                        <span class="si si-24px mdi--success-circle-outline has-text-primary-20" aria-hidden="true"></span>
                    </figure>
                </div>
                <div class="media-content">
                    <div class="content pt-1 pr-5">
                        <p>Notification envoyée avec succès !</p>
                    </div>
                </div>
            </article></li>`;
            newNotification.setAttribute("class", "fadeOut");
            newNotification.innerHTML = message;
            notification_overlay.insertAdjacentElement('beforeend', newNotification);
        }
        else if (data.html === "Failed!") {
            const message = `<li class="notification is-warning mb-3" onclick="this.parentElement.style.display=\'none\';">
            <button class="delete"></button>
            <article class="media">
                <div class="media-left">
                    <figure class="image is-24x24">
                        <span class="si si-24px mdi--warning-circle-outline has-text-danger has-text-weight-bold" aria-hidden="true"></span>
                    </figure>
                </div>
                <div class="media-content">
                    <div class="content pt-1 pr-5">
                        <p>Erreur : aucune notification n\'a pu être envoyée.</p>
                    </div>
                </div>
            </article></li>`;
            newNotification.innerHTML = message;
            notification_overlay.insertAdjacentElement('beforeend', newNotification);
        }


    } catch (error) {
        console.error('Error executing action:', error.message);
    }
}

//
// Sets the click handler for Bulma delete elements, anywhere on the page
//
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', () => {
    document.querySelectorAll('.notification .delete').forEach(($delete) => {
      const notif = $delete.parentNode;
      if (notif && notif.parentNode) notif.parentNode.removeChild(notif);
    });
  });
});


//
// This script manages the height of a textarea input field to fit the content
//
// Calculates the number of visible lines in a textarea based on its current content
function getVisibleLines(textarea) {
    const style = window.getComputedStyle(textarea);
    
    // 1. Create a mirror element
    const mirror = document.createElement('div');
    
    // 2. Copy essential styles that affect text wrapping and size
    const stylesToCopy = [
        'border', 'boxSizing', 'fontFamily', 'fontSize', 'fontWeight',
        'letterSpacing', 'lineHeight', 'padding', 'textDecoration',
        'textTransform', 'width', 'wordSpacing', 'wordWrap', 
        'whiteSpace', 'paddingLeft', 'paddingRight'
    ];

    stylesToCopy.forEach(prop => {
        mirror.style[prop] = style[prop];
    });

    // 3. Setup mirror positioning (hidden from view)
    mirror.style.position = 'absolute';
    mirror.style.visibility = 'hidden';
    mirror.style.height = 'auto';
    mirror.style.overflow = 'hidden';
    
    // 4. Handle the text content
    // Replace trailing newlines with a character to ensure they are measured
    mirror.textContent = textarea.value.replace(/\n$/, '\n\u00A0');

    document.body.appendChild(mirror);

    // 5. Calculate lines
    const totalHeight = mirror.clientHeight;
    
    // Get numeric line height. If 'normal', we estimate it as 1.2 * fontSize
    let lineHeight = parseFloat(style.lineHeight);
    if (isNaN(lineHeight)) {
        lineHeight = parseFloat(style.fontSize) * 1.2; 
    }

    const lineCount = Math.floor(totalHeight / lineHeight);

    // 6. Clean up
    document.body.removeChild(mirror);

    return lineCount;
}

// Adjusts the height of the textarea to fit its content dynamically
function adjustHeight(textarea) {
    const minRows = parseInt(textarea.dataset.rows);
    const maxRows = 37;

    // Calculate the new rows based on content and adjust rows attribute
    textarea.rows = Math.min(Math.max(minRows, getVisibleLines(textarea)), maxRows);
}

// Function to run the event listeners when the page loads
function initializeTextAreaListeners() {
    // Select all textarea elements on the page
    const textareas = document.querySelectorAll('textarea');

    // Add an input event listener to each textarea
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            adjustHeight(textarea);
        });
        // Adjust height for pre-filled textareas on load
        adjustHeight(textarea);
    });
}

// Run the function when the DOM has finished loading
document.addEventListener('DOMContentLoaded', initializeTextAreaListeners);


//
// This script makes the dropdown switch theme
// and save asynchrously to session
//
document.addEventListener('DOMContentLoaded', () => {
    // Theme Switcher Logic
    const themeSwitches = document.querySelectorAll('.theme-switch');
    const htmlElement = document.documentElement;
    const appWrapper = document.getElementById('app-wrapper');

    // Helper function to update the DOM with the selected theme immediately
    const applyThemeDOM = (themeName) => {
        if (themeName === 'legacy') {
            htmlElement.setAttribute('data-theme', 'light');
            htmlElement.classList.remove('lfs-palette'); // Remove LFS colors
            if (appWrapper) {
                appWrapper.classList.remove('is-info');
                appWrapper.classList.remove('has-background-black-bis');
                appWrapper.classList.add('is-primary');
            }
        } else if (themeName === 'lfs-dark') {
            htmlElement.setAttribute('data-theme', 'dark');
            htmlElement.classList.add('lfs-palette');    // Apply LFS colors
            if (appWrapper) {
                appWrapper.classList.remove('is-info');
                appWrapper.classList.remove('is-primary');
                appWrapper.classList.add('has-background-black-bis');
            }
        } else {
            // Default: lfs-light
            htmlElement.setAttribute('data-theme', 'light');
            htmlElement.classList.add('lfs-palette');    // Apply LFS colors
            if (appWrapper) {
                appWrapper.classList.remove('is-primary');
                appWrapper.classList.remove('has-background-black-bis');
                appWrapper.classList.add('is-info');
            }
        }
    };

    // Handle clicks on the theme dropdown
    themeSwitches.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTheme = button.getAttribute('data-target-theme');
            
            // Instantly update the UI
            applyThemeDOM(targetTheme);
            
            // 2. Send asynchronous POST request to Flask
            fetch('/set_theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ theme: targetTheme })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status !== 'success') {
                    console.error('Failed to save theme to session.');
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });
});

//
// This script manages card accordions for Projects
// similarly to the summary/details HTML element
//
document.addEventListener('DOMContentLoaded', () => {
    // --- Card Accordion Logic for Projects ---
    const cardHeaders = document.querySelectorAll('.card-header');

    cardHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const currentCard = header.closest('.card');
            const currentContent = currentCard.querySelector('.toggle-project');
            const currentIcon = header.querySelector('.chevron-icon');
            
            // Check if the card we just clicked is currently open
            const isCurrentlyOpen = !currentContent.classList.contains('is-hidden');

            // Close ALL cards (Exclusive accordion behavior)
            document.querySelectorAll('.card').forEach(card => {
                const content = card.querySelector('.toggle-project');
                const icon = card.querySelector('.chevron-icon');
                if (content) content.classList.add('is-hidden');
                if (icon) icon.style.transform = 'rotate(0deg)';
            });

            // If the clicked card was CLOSED, open it up and rotate icon
            if (!isCurrentlyOpen) {
                currentContent.classList.remove('is-hidden');
                currentIcon.style.transform = 'rotate(180deg)'; // Flips the chevron up
            }
        });
    });
});