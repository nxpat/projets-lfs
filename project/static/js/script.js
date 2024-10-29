// burger navigation
const burger = document.querySelector('.navbar-burger');
const menu = document.querySelector('.navbar-menu');
burger.addEventListener('click', function () {
    burger.classList.toggle('is-active');
    menu.classList.toggle('is-active');
});

// tabs navigation
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

// dropdown menu navigation
const tabsdd = document.querySelectorAll('.dropdown-item');

tabsdd.forEach((tab) => {
    tab.addEventListener('click', () => {
        tabsdd.forEach(item => item.classList.remove('is-active'))
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


// sort tables if is present in <th> header
// https://github.com/VFDouglas/HTML-Order-Table-By-Column/blob/main/index.html
document.querySelectorAll('th').forEach((element) => { // Table headers
    element.addEventListener('click', function () {
        let table = this.closest('table');

        // If the column is sortable
        if (this.querySelector('span')) {
            let order_icon = this.querySelector('span');
            let order = encodeURI(order_icon.innerHTML).includes('%E2%86%91') ? 'desc' : 'asc';
            let separator = '-----'; // Separate the value of it's index, so data keeps intact

            let value_list = {}; // <tr> Object
            let obj_key = []; // Values of selected column

            let string_count = 0;
            let number_count = 0;

            // <tbody> rows
            table.querySelectorAll('tbody tr').forEach((line, index_line) => {
                // Value of each field
                let key = line.children[element.cellIndex].textContent.toUpperCase();

                // remove leading and trailing linefeed and space
                key = key.replace(/^[\u{0000}-\u{0020}]+|[\u{0000}-\u{0020}]{2}.+$/gu, '');
                // remove spaces in numbers
                if (key.match(/^-?[0-9,. ]*$/g)) {
                    key = key.replace(/\u{0020}/gu, '');
                }

                // Check if value is date, numeric or string
                if (line.children[element.cellIndex].hasAttribute('data-timestamp')) {
                    // if value is date, we store it's timestamp, so we can sort like a number
                    key = line.children[element.cellIndex].getAttribute('data-timestamp');
                    number_count++;
                }
                else if (key.match(/^-?[0-9,.]*$/g)) {
                    number_count++;
                }
                else {
                    string_count++;
                }

                value_list[key + separator + index_line] = line.outerHTML.replace(/(\t)|(\n)/g, ''); // Adding <tr> to object
                obj_key.push(key + separator + index_line);
            });
            console.log(string_count, number_count);
            if (string_count === 0) { // If all values are numeric
                obj_key.sort(function (a, b) {
                    return a.split(separator)[0] - b.split(separator)[0];
                });
            }
            else {
                obj_key.sort();
            }

            if (order === 'desc') {
                obj_key.reverse();
                order_icon.innerHTML = '&darr;';
            }
            else {
                order_icon.innerHTML = '&uarr;';
            }

            let html = '';
            obj_key.forEach(function (chave) {
                html += value_list[chave];
            });
            table.getElementsByTagName('tbody')[0].innerHTML = html;
        }
    });
});

function formPrint() {
    // file is a File object, this will also take a blob
    const dataUrl = window.URL.createObjectURL("6s4-eva1.pdf");

    // Open the window
    const pdfWindow = window.open(dataUrl);

    // Call print on it
    pdfWindow.print();
};

// toggle project data in budget tables
//
// Function to toggle the "is-hidden" class for all divs in the clicked row
function toggleHiddenClass(row) {
    const divs = row.querySelectorAll('div'); // Select all divs in the row
    divs.forEach(div => {
        div.classList.toggle('is-hidden'); // Toggle the "is-hidden" class
    });
}
//
// Get the table and add a click event listener to it
// 'budget' is actually the id of the parent tab
const table = document.getElementById('budget');
table && table.addEventListener('click', function (event) {
    const target = event.target;

    // Check if the clicked element is a cell (td) and get the parent row
    if (target.parentNode.tagName === 'TD') {
        const row = target.parentNode.parentNode;
        toggleHiddenClass(row);
    }
});
