// ==========================================
// PROJECT FORM LOGIC
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    initDateConstraints();
    initFieldVisibilityToggles();
    initBudgetLogic();
    initStatusVisibility();
    initTeacherTags();
    initKrwFormatting();
    initCharacterCounters();
});

// --- Date & Constraints ---
function initDateConstraints() {
    const syRadioButtons = document.querySelectorAll('input[name="school_year"]');
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');

    const updateDateConstraints = () => {
        const schoolYear = document.querySelector('input[name="school_year"]:checked');
        if (!schoolYear || !startDateInput || !endDateInput) return;

        let startMin, endMax;
        if (schoolYear.value === 'next') {
            startMin = new Date(SY_NEXT_MIN);
            endMax = new Date(SY_NEXT_MAX);
        } else {
            startMin = new Date(SY_MIN);
            endMax = new Date(SY_MAX);
        }

        const startMinStr = startMin.toISOString().split('T')[0];
        const endMaxStr = endMax.toISOString().split('T')[0];

        startDateInput.min = startMinStr;
        startDateInput.max = endMaxStr;
        endDateInput.min = startMinStr;
        endDateInput.max = endMaxStr;
    };

    const ensureValidEndDate = () => {
        if (!startDateInput || !endDateInput) return;
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        if (startDate) {
            if (!endDate || endDate < startDate) endDateInput.value = startDate;
            endDateInput.min = startDate;
        }
    };

    syRadioButtons.forEach(radio => radio.addEventListener('change', updateDateConstraints));
    
    if (startDateInput) startDateInput.addEventListener('change', ensureValidEndDate);
    if (endDateInput) endDateInput.addEventListener('change', ensureValidEndDate);
    
    updateDateConstraints();
    ensureValidEndDate();
}

// --- Dynamic Fields Visibility ---
function initFieldVisibilityToggles() {
    // Requirements
    const reqRadios = document.querySelectorAll('input[name="requirement"]');
    const studentsDiv = document.getElementById('students-list');
    const toggleStudents = () => {
        if (studentsDiv) {
            const checked = document.querySelector('input[name="requirement"]:checked');
            studentsDiv.style.display = (checked && checked.value === 'no') ? 'block' : 'none';
        }
    };
    reqRadios.forEach(radio => radio.addEventListener('change', toggleStudents));
    toggleStudents();

    // Location (Fieldtrips)
    const locRadios = document.querySelectorAll('input[name="location"]');
    const fieldtripDiv = document.getElementById('fieldtrip');
    const toggleFieldtrip = () => {
        if (fieldtripDiv) {
            const checked = document.querySelector('input[name="location"]:checked');
            fieldtripDiv.style.display = (checked && (checked.value === 'outer' || checked.value === 'trip')) ? 'block' : 'none';
        }
    };
    locRadios.forEach(radio => radio.addEventListener('change', toggleFieldtrip));
    toggleFieldtrip();

    // Budget Required Toggle
    const budgetRadios = document.querySelectorAll('input[name="budget"]');
    const budgetDetailsDiv = document.getElementById('budget_details');
    const toggleBudget = () => {
        if (budgetDetailsDiv) {
            const checked = document.querySelector('input[name="budget"]:checked');
            budgetDetailsDiv.style.display = (checked && checked.value === 'Oui') ? 'block' : 'none';
        }
    };
    budgetRadios.forEach(radio => radio.addEventListener('change', toggleBudget));
    toggleBudget();
}

// Global Link function (kept outside for inline HTML calls)
window.addLinkField = function() {
    const linksDiv = document.getElementById('link-fields');
    if (!linksDiv) return;
    const linkFields = linksDiv.getElementsByClassName('columns');
    
    let nextFieldIndex = Array.from(linkFields).findIndex(field => field.classList.contains('is-hidden'));

    if (nextFieldIndex !== -1) {
        linkFields[nextFieldIndex].classList.remove('is-hidden');
    }

    if (nextFieldIndex === linkFields.length - 1) {
        document.getElementById('add-link-button').style.display = 'none';
    }
};

// --- Budget Logic ---
function initBudgetLogic() {
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');

    const toggleColumns = (action) => {
        document.querySelectorAll('.budget-columns').forEach(el => el.classList[action]('columns'));
        document.querySelectorAll('.budget-amount-column').forEach(el => el.classList[action]('column'));
        document.querySelectorAll('.budget-comment-column').forEach(el => {
            el.classList[action]('column');
            el.classList[action]('is-narrow');
        });
    };

    const copyBudgetValues = (year1, year2) => {
        document.querySelectorAll(`input[id^="budget_"][id$="_${year1}"]`).forEach(field1 => {
            const field2 = document.getElementById(field1.id.replace(`_${year1}`, `_${year2}`));
            if (field2 && parseInt(field2.value) === 0 && parseInt(field1.value) > 0) {
                field2.value = field1.value;
            }
        });

        document.querySelectorAll(`textarea[id^="budget_"][id$="_c_${year1}"]`).forEach(field1 => {
            const field2 = document.getElementById(field1.id.replace(`_${year1}`, `_${year2}`));
            if (field2 && !field2.value && field1.value) {
                field2.value = field1.value;
                const column = field2.closest('.budget-amount-column');
                if (column) column.style.display = 'block';
            }
        });
    };

    const displayBudgetFields = () => {
        if (!startDateInput || !endDateInput) return;
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        const minStartDate = startDateInput.min;

        const div1 = document.getElementById('budget-year-1');
        const div2 = document.getElementById('budget-year-2');
        const div1Label = document.getElementById('budget-label-1');
        const div2Label = document.getElementById('budget-label-2');

        if (startDate && div1 && div2) {
            const startYear = new Date(startDate).getFullYear();
            const endYear = endDate ? new Date(endDate).getFullYear() : startYear;
            const minStartYear = new Date(minStartDate).getFullYear();

            if (endDate && startYear !== endYear) {
                div1Label.textContent = `Budget estimé ${startYear}`;
                div2Label.textContent = `Budget estimé ${endYear}`;
                div1.style.display = 'block';
                div2.style.display = 'block';
                toggleColumns('remove');
            } else {
                if (startYear > minStartYear) {
                    div2Label.textContent = `Budget estimé ${startYear}`;
                    div2.style.display = 'block';
                    div1.style.display = 'none';
                    copyBudgetValues('1', '2');
                } else {
                    div1Label.textContent = `Budget estimé ${startYear}`;
                    div1.style.display = 'block';
                    div2.style.display = 'none';
                    toggleColumns('add');
                    copyBudgetValues('2', '1');
                }
            }
        }
    };

    if (startDateInput) startDateInput.addEventListener('change', displayBudgetFields);
    if (endDateInput) endDateInput.addEventListener('change', displayBudgetFields);
    displayBudgetFields();

    // Budget Comment Fields Visibility
    document.querySelectorAll('input[id^="budget_"][id$="_1"], input[id^="budget_"][id$="_2"]').forEach(field => {
        field.addEventListener('input', () => {
            const commentField = field.closest('.budget-comment-column').nextElementSibling;
            if (commentField) {
                commentField.style.display = parseInt(field.value) > 0 ? 'block' : 'none';
            }
        });
    });
}

// --- Specific Edge Cases ---
function initStatusVisibility() {
    const schoolYearRadios = document.querySelectorAll('input[name="school_year"]');
    const statusRadios = document.querySelectorAll('input[name="status"]');
    const lastStatus = Array.from(statusRadios).filter(r => r.type === 'radio').pop();
    
    if (!lastStatus) return;

    const statusControl = document.querySelector('.control input[name="status"]')?.closest('.control');
    const statusDesc = statusControl ? (statusControl.nextElementSibling?.matches('p') ? statusControl.nextElementSibling : statusControl.nextElementSibling?.querySelector('p')) : null;
    const originalDesc = statusDesc ? statusDesc.textContent.trim() : '';

    const updateLastStatusVisibility = () => {
        const schoolYear = document.querySelector('input[name="school_year"]:checked');
        const label = lastStatus.closest('label');

        if (schoolYear && schoolYear.value === 'next') {
            if (label) label.classList.add('is-hidden');
            lastStatus.checked = false;
            lastStatus.disabled = true;
            if (statusDesc) {
                const idx = originalDesc.lastIndexOf(' ou ');
                statusDesc.textContent = idx !== -1 ? originalDesc.slice(0, idx).trim() : originalDesc;
            }
        } else {
            if (label) label.classList.remove('is-hidden');
            lastStatus.disabled = false;
            if (statusDesc) statusDesc.textContent = originalDesc;
        }
    };

    schoolYearRadios.forEach(r => r.addEventListener('change', updateLastStatusVisibility));
    updateLastStatusVisibility();
}

function initTeacherTags() {
    const teacherSelect = document.getElementById('teacher-select');
    const tagsContainer = document.getElementById('selected-teachers-tags');

    if (teacherSelect && tagsContainer) {
        teacherSelect.addEventListener('mousedown', function(e) {
            // Check if the user clicked an actual <option> (and not the scrollbar)
            if (e.target.tagName === 'OPTION') {
                e.preventDefault(); // Stop the browser from wiping the other selections
                
                // Toggle the clicked option's state
                e.target.selected = !e.target.selected;
                
                // Manually trigger the change event to update the tags
                teacherSelect.dispatchEvent(new Event('change'));
                
                // Keep focus on the select box for accessibility
                setTimeout(() => teacherSelect.focus(), 0);
            }
        });
        // ---------------------------------------------------------

        const renderTags = () => {
            tagsContainer.innerHTML = '';
            const selectedOptions = Array.from(teacherSelect.selectedOptions);

            if (selectedOptions.length === 0) {
                tagsContainer.innerHTML = '<span class="has-text-grey is-italic">Aucun enseignant sélectionné.</span>';
                return;
            }

            selectedOptions.forEach(option => {
                const controlDiv = document.createElement('div');
                controlDiv.className = 'control';

                const tagsDiv = document.createElement('div');
                tagsDiv.className = 'tags has-addons';

                const nameTag = document.createElement('span');
                nameTag.className = 'tag is-link is-light';
                nameTag.textContent = option.text;

                const deleteTag = document.createElement('a');
                deleteTag.className = 'tag is-delete';
                deleteTag.addEventListener('click', (e) => {
                    e.preventDefault();
                    option.selected = false;
                    teacherSelect.dispatchEvent(new Event('change'));
                });

                tagsDiv.appendChild(nameTag);
                tagsDiv.appendChild(deleteTag);
                controlDiv.appendChild(tagsDiv);
                tagsContainer.appendChild(controlDiv);
            });
        };

        teacherSelect.addEventListener('change', renderTags);
        renderTags();
    }
}

// --- KRW Live Formatting ---
function initKrwFormatting() {
    const krwInputs = document.querySelectorAll('.krw-live-format');

    krwInputs.forEach(helper => {
        // Navigate up to the field container, then find the input
        const input = helper.previousElementSibling.querySelector('input');
        if (!input) return;

        // Function to update the text
        const updateFormat = () => {
            const cleanValue = input.value.replace(/\s/g, '');  // Clean spaces
            const val = parseInt(cleanValue, 10);
            if (isNaN(val) || val === 0) {
                helper.textContent = ''; // Hide if empty or 0
            } else {
                helper.textContent = new Intl.NumberFormat('fr-FR').format(val) + ' ₩';
            }
        };

        // Listen for typing
        input.addEventListener('input', updateFormat);
        
        // Run once on load in case the form is pre-filled (editing a project)
        updateFormat(); 
    });
}

// --- Character Counters for StringFields (and textareas) ---
function initCharacterCounters() {
    const textFields = document.querySelectorAll('input[type="text"][maxlength], textarea[maxlength]');

    textFields.forEach(field => {
        const max = field.getAttribute('maxlength');
        
        // Create the counter element
        const counter = document.createElement('div');
        
        counter.className = 'help is-italic mt-0 is-pulled-right has-text-grey-light';
        
        const controlWrapper = field.closest('.control');
        
        if (controlWrapper) {
            // If wrapped in a .control, place it right after the wrapper
            controlWrapper.parentNode.insertBefore(counter, controlWrapper.nextSibling);
        } else {
            // Fallback just in case
            field.parentNode.insertBefore(counter, field.nextSibling);
        }

        const updateCounter = () => {
            const current = field.value.length;
            counter.textContent = `${current} / ${max}`;
            
            // Turn text warning color if they get within 10% of the limit
            if (current >= max * 0.9) {
                counter.classList.replace('has-text-grey-light', 'has-text-warning');
                counter.classList.add('has-text-weight-bold');
                field.classList.add('is-warning'); 
            } else {
                counter.classList.replace('has-text-warning', 'has-text-grey-light');
                counter.classList.remove('has-text-weight-bold');
                field.classList.remove('is-warning'); 
            }
        };

        // Listen for typing
        field.addEventListener('input', updateCounter);
        
        // Initialize on load
        updateCounter(); 
    });
}


function initStudentSpreadsheet(fieldName, defaultMinRows = 10) {
    const hiddenInput = document.getElementById(`${fieldName}_hidden`);
    const tbody = document.getElementById(`${fieldName}_tbody`);
    const addBtn = document.getElementById(`${fieldName}_add_btn`);
    const clearBtn = document.getElementById(`${fieldName}_clear_btn`);

    if (!hiddenInput || !tbody) return;

    // --- Helper: Recalculate row numbers ---
    function updateRowIndices() {
        const rows = tbody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            const indexCell = row.querySelector('.row-index');
            if (indexCell) {
                indexCell.textContent = index + 1;
            }
        });
    }

    // --- Helper: Create single row ---
    function createRow(classe = '', nom = '', prenom = '') {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="has-text-centered row-index"></td>
            <td><input type="text" class="input is-small grid-cell" data-col="0" value="${escapeHtml(classe)}" placeholder="6e A"></td>
            <td><input type="text" class="input is-small grid-cell" data-col="1" value="${escapeHtml(nom)}" placeholder="Dupont"></td>
            <td><input type="text" class="input is-small grid-cell" data-col="2" value="${escapeHtml(prenom)}" placeholder="Élodie"></td>
            <td class="has-text-centered">
                <button type="button" class="button is-small is-danger is-outlined delete-row-btn" title="Supprimer">
                    <span class="icon"><i class="si mdi--trash-can-outline"></i></span>
                </button>
            </td>
        `;
        return tr;
    }

    function escapeHtml(str) {
        return (str || '').replace(/"/g, '&quot;');
    }

    function syncToTextarea() {
        const rows = tbody.querySelectorAll('tr');
        const lines = [];

        rows.forEach(row => {
            const inputs = row.querySelectorAll('input.grid-cell');
            const classe = inputs[0].value.trim();
            const nom = inputs[1].value.trim();
            const prenom = inputs[2].value.trim();

            if (classe || nom || prenom) {
                lines.push(`${classe}, ${nom}, ${prenom}`);
            }
        });

        hiddenInput.value = lines.join('\n');
    }

    function addRow(classe = '', nom = '', prenom = '') {
        const tr = createRow(classe, nom, prenom);
        tbody.appendChild(tr);
        updateRowIndices();
        return tr;
    }

    function buildInitialGrid() {
        tbody.innerHTML = '';
        const existingData = hiddenInput.value.trim();

        if (existingData) {
            const lines = existingData.split(/\r?\n/);
            lines.forEach(line => {
                const parts = line.split(/,|\t|\s{2,}/).map(s => s.trim());
                addRow(parts[0] || '', parts[1] || '', parts[2] || '');
            });
        }

        while (tbody.children.length < defaultMinRows) {
            addRow();
        }
    }

    // --- Input Sync ---
    tbody.addEventListener('input', (e) => {
        if (e.target.classList.contains('grid-cell')) {
            syncToTextarea();
        }
    });

    // --- Event: Keyboard Navigation (Enter / Tab / Arrows) ---
    tbody.addEventListener('keydown', (e) => {
        const input = e.target;
        if (!input.classList.contains('grid-cell')) return;

        const cell = input.closest('td');
        const row = cell.closest('tr');
        const colIndex = parseInt(input.dataset.col, 10);
        const rowIndex = Array.from(tbody.children).indexOf(row);
        const key = e.key;

        // --- Enter Key: Move down (or add new row) ---
        if (key === 'Enter') {
            e.preventDefault();
            let nextRow = tbody.children[rowIndex + 1];
            if (!nextRow) nextRow = addRow();
            const targetInput = nextRow.querySelectorAll('input.grid-cell')[colIndex];
            targetInput.focus();
            targetInput.select();
        } 
        // --- Tab Key: Move right ---
        else if (key === 'Tab' && !e.shiftKey) {
            const isLastCol = colIndex === 2;
            const isLastRow = rowIndex === tbody.children.length - 1;

            if (isLastCol && isLastRow) {
                e.preventDefault();
                const newRow = addRow();
                const targetInput = newRow.querySelectorAll('input.grid-cell')[0];
                targetInput.focus();
                targetInput.select();
            }
        }
        // --- Arrow Up ---
        else if (key === 'ArrowUp') {
            if (rowIndex > 0) {
                e.preventDefault();
                const prevRow = tbody.children[rowIndex - 1];
                const targetInput = prevRow.querySelectorAll('input.grid-cell')[colIndex];
                targetInput.focus();
                targetInput.select();
            }
        }
        // --- Arrow Down ---
        else if (key === 'ArrowDown') {
            e.preventDefault();
            let nextRow = tbody.children[rowIndex + 1];
            if (!nextRow) nextRow = addRow();
            const targetInput = nextRow.querySelectorAll('input.grid-cell')[colIndex];
            targetInput.focus();
            targetInput.select();
        }
        // --- Arrow Left (Jumps left when caret is at start) ---
        else if (key === 'ArrowLeft') {
            if (input.selectionStart === 0 && input.selectionEnd === 0) {
                if (colIndex > 0) {
                    e.preventDefault();
                    const targetInput = row.querySelectorAll('input.grid-cell')[colIndex - 1];
                    targetInput.focus();
                    targetInput.select();
                }
            }
        }
        // --- Arrow Right (Jumps right when caret is at end) ---
        else if (key === 'ArrowRight') {
            if (input.selectionStart === input.value.length) {
                if (colIndex < 2) {
                    e.preventDefault();
                    const targetInput = row.querySelectorAll('input.grid-cell')[colIndex + 1];
                    targetInput.focus();
                    targetInput.select();
                }
            }
        }
    });

    // --- Paste Multi-line Data ---
    tbody.addEventListener('paste', (e) => {
        const input = e.target;
        if (!input.classList.contains('grid-cell')) return;

        e.preventDefault();
        const clipboardData = (e.clipboardData || window.clipboardData).getData('text');
        if (!clipboardData) return;

        const lines = clipboardData.split(/\r?\n/).filter(line => line.trim() !== '');
        const startCell = input.closest('td');
        const startRow = startCell.closest('tr');
        const startCol = parseInt(input.dataset.col, 10);
        const startRowIndex = Array.from(tbody.children).indexOf(startRow);

        lines.forEach((line, lineOffset) => {
            const targetRowIndex = startRowIndex + lineOffset;
            
            while (targetRowIndex >= tbody.children.length) {
                addRow();
            }

            const targetRow = tbody.children[targetRowIndex];
            const cells = line.split(/\t|,|\s{2,}/).map(s => s.trim());

            cells.forEach((cellVal, colOffset) => {
                const targetColIndex = startCol + colOffset;
                if (targetColIndex < 3) {
                    const targetInput = targetRow.querySelectorAll('input.grid-cell')[targetColIndex];
                    if (targetInput) targetInput.value = cellVal;
                }
            });
        });

        syncToTextarea();
        updateRowIndices();
    });

    // --- Delete Button ---
    tbody.addEventListener('click', (e) => {
        const btn = e.target.closest('.delete-row-btn');
        if (!btn) return;

        const row = btn.closest('tr');
        row.remove();

        if (tbody.children.length < defaultMinRows) {
            addRow();
        } else {
            updateRowIndices();
        }

        syncToTextarea();
    });

    // --- Action Buttons ---
    addBtn.addEventListener('click', () => {
        const newRow = addRow();
        newRow.querySelector('input').focus();
    });

    clearBtn.addEventListener('click', () => {
        tbody.innerHTML = '';
        for (let i = 0; i < defaultMinRows; i++) addRow();
        syncToTextarea();
    });

    buildInitialGrid();
}