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
const tabs = document.querySelectorAll('.tabs li');

tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
        const currentTabs = tab.parentNode.querySelectorAll('li');
        currentTabs.forEach(item => item.classList.remove('is-active'))
        tab.classList.add('is-active');

        const target = tab.dataset.target;
        const tabContent = tab.closest('.box').querySelectorAll(':scope > .tab-content > div');
        tabContent.forEach(content => {
            if (content.getAttribute('id') === target) {
                content.classList.remove('is-hidden');
            } else {
                content.classList.add('is-hidden');
            }
        });
    });
});


//
// Update to the current year in the footer
//
window.onload = function () {
    document.getElementById("this-year").innerHTML = (new Date().getFullYear());
};

// 
// dropdown menu navigation
//
const tabsdd = document.querySelectorAll('.dropdown-item');

tabsdd.forEach((tab) => {
    tab.addEventListener('click', () => {
        const currentTabsdd = tab.parentNode.querySelectorAll('.dropdown-item');
        currentTabsdd.forEach(item => item.classList.remove('is-active'))
        tab.classList.add('is-active');

        const target = tab.dataset.target;
        const tabContent = tab.closest('.box').querySelectorAll(':scope > .tab-content > div');
        tabContent.forEach(content => {
            if (content.getAttribute('id') === target) {
                content.classList.remove('is-hidden');
            } else {
                content.classList.add('is-hidden');
            }
        });
    });
});


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
        document.getElementById('historyContent').innerHTML = originalHistoryContent;
    }
}

function closeAllModals() {
    (document.querySelectorAll('.modal') || []).forEach(($modal) => {
        closeModal($modal);
    });
}


function fetchHistoryData(projectId) {
    const appWs = document.getElementById('appWs').href;
    fetch(`${appWs}history/${projectId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                // Store the original content before updating
                originalHistoryContent = document.getElementById('historyContent').innerHTML;
                // Update content
                document.getElementById('historyContent').innerHTML = data.html;
            }
        })
        .catch(error => console.error('Error fetching history:', error));
}

// Add a click event on buttons to open a specific modal
(document.querySelectorAll('.js-modal-trigger') || []).forEach(($trigger) => {
    const user = document.getElementById('user-name').textContent
    const list = ['modal-delete', 'modal-validate', 'modal-agree', 'modal-devalidate', 'modal-history'];
    const modal = $trigger.dataset.target;
    const $target = document.getElementById(modal);

    $trigger.addEventListener('click', () => {
        if (list.includes(modal)) {
            const projectTitle = $trigger.dataset.projectTitle;
            $target.querySelector('h5').textContent = projectTitle;

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
            }

            const spans = $target.querySelectorAll('span');
            spans.forEach(span => {
                // Check if the text content includes 'user'
                if (span.textContent.includes('user')) {
                    // Replace 'user' with current_user name
                    span.textContent = span.textContent.replace(/user/g, user);
                }
            });
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


// Event listener for visibility change
// to re-enable disabled buttons
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        // Get all buttons with the disabled attribute
        const disabledButtons = document.querySelectorAll('button[disabled]');
        // Re-enable the button when the page becomes visible
        disabledButtons.forEach(button => {
            button.removeAttribute('disabled');
            // console.log(button);
        });
    }
});


// Filter projects with search field input
function filterProjects() {
    const searchInput = document.getElementById('search').value.toLowerCase();
    const projectBoxes = document.querySelectorAll('#projects .box');

    projectBoxes.forEach(box => {
        // Get all text content from the details element within the box
        const projectText = box.textContent.toLowerCase();

        // Check if the search input is included in the project text
        if (projectText.includes(searchInput)) {
            box.classList.remove('is-hidden');
        } else {
            box.classList.add('is-hidden');
        }
    });
}

// Submit form programmatically (school year, department)
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
        // add the "disabled" attribute to the select element
        selectElement.disabled = true;
    }


}