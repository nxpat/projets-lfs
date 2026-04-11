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
        
        // --- THE NEW MAGIC PART: Click to toggle without Ctrl! ---
        teacherSelect.addEventListener('mousedown', function(e) {
            // Check if the user clicked an actual <option> (and not the scrollbar)
            if (e.target.tagName === 'OPTION') {
                e.preventDefault(); // Stop the browser from wiping the other selections!
                
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
        
        // 'is-pulled-right' makes it float to the right side!
        // We removed 'mb-3' so it doesn't push your other help text down.
        counter.className = 'help is-italic is-pulled-right has-text-grey-light';
        
        // THE FIX: Find the parent .control wrapper and insert the counter AFTER it
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