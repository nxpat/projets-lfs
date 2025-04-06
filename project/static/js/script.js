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
}

function closeAllModals() {
    (document.querySelectorAll('.modal') || []).forEach(($modal) => {
        closeModal($modal);
    });
}

// Add a click event on buttons to open a specific modal
(document.querySelectorAll('.js-modal-trigger') || []).forEach(($trigger) => {
    const user = document.getElementById('user-name').textContent
    const list = ['modal-delete', 'modal-validation', 'modal-agreement', 'modal-devalidation'];
    const modal = $trigger.dataset.target;
    const $target = document.getElementById(modal);

    $trigger.addEventListener('click', () => {
        if (list.includes(modal)) {
            const projectTitle = $trigger.dataset.projectTitle;
            $target.querySelector('h5').textContent = projectTitle;

            const projectId = $trigger.dataset.projectId;
            switch (modal) {
                case 'modal-delete':
                    $target.querySelector('form').action = '/project/delete/' + projectId;
                    break;
                case 'modal-agreement':
                case 'modal-validation':
                    $target.querySelector('form').action = '/project/validation/' + projectId;
                    break;
                case 'modal-devalidation':
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
        console.log(modal, $target);
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