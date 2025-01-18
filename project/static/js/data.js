//
// sort tables
// https://github.com/VFDouglas/HTML-Order-Table-By-Column/blob/main/index.html
//
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


//
// toggle project data in budget tables
//
// Function to toggle "is-hidden" class for all divs in the clicked row
function toggleHiddenClass(row) {
    const divs = row.querySelectorAll('div'); // Select all divs in the row
    divs.forEach(div => {
        div.classList.toggle('is-hidden'); // Toggle the "is-hidden" class
    });
}

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


//
// button to copy a table
//
function copytable(el) {
    var budgetTable = document.getElementById(el);
    var range = document.createRange();
    range.selectNode(budgetTable);
    console.log(range);
    window.getSelection().addRange(range);
    document.execCommand('copy');
}

function copyTable(button, el) {
    if (!navigator.clipboard) {
        copytable(el);
    } else {
        var table = document.getElementById(el);
        // Convert the table to a string
        let tableContent = '';
        for (let row of table.rows) {
            let rowText = Array.from(row.cells).map(cell => {
                // Get the text content of the cell
                let cellText = cell.innerText;

                // Check for span elements and include their text
                const spans = cell.getElementsByTagName('span');
                for (let span of spans) {
                    cellText += span.innerText; // Append the text from the span
                }

                // Remove spaces from numbers
                cellText = cellText.replace(/(\d)\s+(?=\d)/g, '$1');

                return cellText;
            }).join('\t');
            tableContent += rowText + '\n';
        }

        // Remove up arrow character
        tableContent = tableContent.replace(/\u2191/g, '');

        // Use the Clipboard API to copy the text
        navigator.clipboard.writeText(tableContent)
            .then(() => {
                // console.log('Table copied to clipboard successfully!');
                //const originalTitle = button.getAttribute('title');
                const originalTooltip = button.nextElementSibling.innerHTML;
                const successMessage = 'Le tableau a été copié dans le presse-papiers avec succès !';

                //button.setAttribute('title', successMessage);
                button.nextElementSibling.innerHTML = successMessage;

                // Revert back to the original tooltip after 5 seconds
                setTimeout(() => {
                    //button.setAttribute('title', originalTitle);
                    button.nextElementSibling.innerHTML = originalTooltip;
                }, 5000);
            })
            .catch(err => {
                // console.error('Failed to copy table: ', err);
                alert("Le navigateur n'est pas compatible ou est paramétré pour bloquer l'utilisation du presse-papiers. ", err);
            });
    }
}