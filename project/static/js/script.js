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
// secure submit once buttons
//
document.addEventListener('DOMContentLoaded', function () {
    // Get all input elements of type submit
    const submitButtons = document.querySelectorAll('.submit-once');

    submitButtons.forEach(function (submitButton) {
        // Add click event listener
        submitButton.addEventListener("click", function (event) {
            // Check if the form is valid
            const form = this.form; // Get the parent form
            if (!form.checkValidity()) return; // If not valid, exit

            // Send the form if valid
            form.submit();

            // Disable the button after submission
            this.disabled = true;
        });
    });
});