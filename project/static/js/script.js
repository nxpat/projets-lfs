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
// secure submit once button
//
document.addEventListener('DOMContentLoaded', function () {
    // get all elements with class submit-once
    const submitButtons = document.querySelectorAll('.submit-once');

    submitButtons.forEach(function (submitButton) {
        // add click event listener
        submitButton.addEventListener("click", function (event) {
            // check if the form is valid
            if (!this.form.checkValidity()) return; // If not valid, exit

            // send the form if valid
            this.form.submit();

            // disable the submit button to prevent multiple submissions
            this.disabled = true;
        });
    });
});


// 
// secure submit once button with confirmation dialog
//
function confirmAction(button, message) {
    if (confirm(message)) {
        // if form not valid, exit
        if (!button.form.checkValidity()) return;

        // submit the form
        button.form.submit();

        // disable the submit button to prevent multiple submissions
        button.disabled = true;
    } else {
        return false;
    }
}
