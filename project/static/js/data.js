// ==========================================
// DATA & STATISTICS UTILITIES
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    initTableSorting();
});

// --- 1. Table Sorting ---
function initTableSorting() {
    const tables = document.querySelectorAll('table');

    tables.forEach(table => {
        // ONLY target headers explicitly marked with data-sortable
        const headers = table.querySelectorAll('th[data-sortable]');
        
        headers.forEach(header => {
            // 1. Create the Bulma alignment wrapper
            const wrapper = document.createElement('span');
            wrapper.className = 'icon-text is-flex-wrap-nowrap';

            while (header.firstChild) {
                wrapper.appendChild(header.firstChild);
            }

            // 3. Create the icon container
            const sortSpan = document.createElement('span');
            sortSpan.className = 'icon'; 
            wrapper.appendChild(sortSpan);

            // 4. Put the assembled wrapper back into the header
            header.appendChild(wrapper);
            
            // Initialize state to 'none' and set the default double-sided icon
            header.setAttribute('data-sort', 'none');
            sortSpan.innerHTML = '<i class="si mdi--swap-vertical has-text-grey-light" aria-hidden="true"></i>';

            header.addEventListener('click', function () {
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const cellIndex = this.cellIndex;

                // Reset ALL other sortable headers back to 'unsorted'
                headers.forEach(otherHeader => {
                    if (otherHeader !== header) {
                        otherHeader.setAttribute('data-sort', 'none');
                        // CRITICAL: We now target '.icon' specifically!
                        const otherIcon = otherHeader.querySelector('.icon');
                        if (otherIcon) {
                            otherIcon.innerHTML = '<i class="si mdi--swap-vertical has-text-grey-light" aria-hidden="true"></i>';
                        }
                    }
                });

                // Determine new sorting direction for the clicked header
                const currentSort = this.getAttribute('data-sort');
                const newSort = currentSort === 'asc' ? 'desc' : 'asc';
                this.setAttribute('data-sort', newSort);

                // Update the icon for the clicked header
                const isAscending = newSort === 'asc';
                sortSpan.innerHTML = isAscending 
                    ? '<i class="si mdi--arrow-down-thin" aria-hidden="true"></i>' 
                    : '<i class="si mdi--arrow-up-thin" aria-hidden="true"></i>';

                const sortMultiplier = isAscending ? 1 : -1;

                // Sort the rows array directly
                rows.sort((a, b) => {
                    let valA = getCellValue(a, cellIndex);
                    let valB = getCellValue(b, cellIndex);

                    // Push empty values to the bottom
                    if (!valA) return 1;
                    if (!valB) return -1;

                    // Handle numeric vs string sorting safely
                    const numA = parseFloat(valA.replace(/,/g, '.'));
                    const numB = parseFloat(valB.replace(/,/g, '.'));

                    if (!isNaN(numA) && !isNaN(numB)) {
                        return (numA - numB) * sortMultiplier;
                    }
                    return valA.localeCompare(valB) * sortMultiplier;
                });

                // Re-append the sorted DOM elements
                tbody.append(...rows);
            });
        });
    });
}

function getCellValue(row, index) {
    const cell = row.children[index];
    if (cell.hasAttribute('data-timestamp')) {
        return cell.getAttribute('data-timestamp');
    }
    let text = cell.textContent.trim().toUpperCase();
    
    // Remove spaces only if it's a number
    if (text.replace(/\s/g, '').match(/^-?[0-9,.]*$/)) {
        text = text.replace(/\s/g, '');
    }
    return text;
}

// --- 2. Copy Table to Clipboard ---
function copyTable(button, tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    let tableContent = '';

    for (let row of table.rows) {
        let rowText = Array.from(row.cells).map(cell => {
            // Grab text and span even if it has 'display: none'
            let cellText = cell.textContent;
            
            // Clean up raw HTML line breaks and extra whitespace
            cellText = cellText.replace(/\s+/g, ' ').trim();
            
            // Remove spacing in numbers (e.g., 1 000 -> 1000)
            cellText = cellText.replace(/(\d)\s+(?=\d)/g, '$1');
            
            // Strip the sorting arrows (both native and unicode)
            cellText = cellText.replace(/↑|↓|\u2191|\u2193/g, '').trim();
            
            return cellText;
        }).join('\t');
        
        tableContent += rowText + '\n';
    }

    if (navigator.clipboard) {
        navigator.clipboard.writeText(tableContent)
            .then(() => showCopySuccess(button))
            .catch(() => fallbackCopyTable(table, button));
    } else {
        fallbackCopyTable(table, button);
    }
}

function fallbackCopyTable(table, button) {
    const range = document.createRange();
    range.selectNode(table);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    
    try {
        document.execCommand('copy');
        showCopySuccess(button);
    } catch (err) {
        alert("Le navigateur n'est pas compatible ou bloque le presse-papiers.");
    }
    window.getSelection().removeAllRanges();
}

function showCopySuccess(button) {
    const tooltipEl = button.nextElementSibling;
    if (!tooltipEl) return;

    const originalHTML = tooltipEl.innerHTML;
    tooltipEl.innerHTML = 'Le tableau a été copié dans le presse-papiers avec succès !';

    setTimeout(() => {
        tooltipEl.innerHTML = originalHTML;
    }, 5000);
}