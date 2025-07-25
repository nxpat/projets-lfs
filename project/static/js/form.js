// 
// If "requirement" field is set to "no"
// toggle "students" field
//
const requirementRadios = document.querySelectorAll('input[name="requirement"]');

// Get the students list div
const studentsDiv = document.getElementById('students-list');

// Function to handle the visibility of the students list div
function toggleStudentsDivVisibility() {
    if (document.querySelector('input[name="requirement"]:checked').value === 'no') {
        studentsDiv.style.display = 'block';
    } else {
        studentsDiv.style.display = 'none';
    }
}

// Add event listeners to the "requirement" radio buttons
requirementRadios.forEach(radio => {
    radio.addEventListener('change', toggleStudentsDivVisibility);
});


// 
// If "sortie scolaire" field is set to "outer"
// toggle "fieldtrip" fields
//
const locationRadios = document.querySelectorAll('input[name="location"]');

// Get the "fieldtrip" div
const fieldtripDiv = document.getElementById('fieldtrip');

// Function to handle the visibility of the "fieldtrip" div
function toggleFieldtripVisibility() {
    if (document.querySelector('input[name="location"]:checked').value === 'outer') {
        fieldtripDiv.style.display = 'block';
    } else {
        fieldtripDiv.style.display = 'none';
    }
}

// Add event listeners to the "location" radio buttons
locationRadios.forEach(radio => {
    radio.addEventListener('change', toggleFieldtripVisibility);
});


// 
// budget fields
// for projects spanning two fiscal years
//
function toggleColumns(action) {
    const columnsDivs = document.getElementsByClassName('toggle-columns');
    const columnDivs = document.getElementsByClassName('toggle-column');
    const narrrowColDivs = document.getElementsByClassName('toggle-narrow-column');

    // Loop through all columns divs
    for (let i = 0; i < columnsDivs.length; i++) {
        if (action === 'add') {
            columnsDivs[i].classList.add('columns');
        } else if (action === 'remove') {
            columnsDivs[i].classList.remove('columns');
        }
    }

    // Loop through all column divs
    for (let i = 0; i < columnDivs.length; i++) {
        if (action === 'add') {
            columnDivs[i].classList.add('column');
        } else if (action === 'remove') {
            columnDivs[i].classList.remove('column');
        }
    }

    // Loop through all narrow column divs
    for (let i = 0; i < narrrowColDivs.length; i++) {
        if (action === 'add') {
            narrrowColDivs[i].classList.add('column', 'is-narrow');
        } else if (action === 'remove') {
            narrrowColDivs[i].classList.remove('column', 'is-narrow');
        }
    }
}

function checkDateYears() {
    const endDateInput = document.getElementById('end_date');

    const startDate = document.getElementById('start_date').value;
    const endDate = endDateInput.value;
    const minStartDate = document.getElementById("start_date").min;

    const div0 = document.getElementById('budget-text');
    const div1 = document.getElementById('budget-label-1');
    const div2 = document.getElementById('budget-label-2');
    const div1b = document.getElementById('budget-1');
    const div2b = document.getElementById('budget-2');

    if (startDate) {
        // check if end date is not set, then set it to start date
        if (!endDate || endDate < startDate) {
            endDateInput.value = startDate; // set end date to start date if not set
        }

        // set min end date to start date
        endDateInput.min = startDate;

        const startYear = new Date(startDate).getFullYear();
        const endYear = new Date(endDate).getFullYear();
        const minStartYear = new Date(minStartDate).getFullYear();

        // toggle budget columns
        if (endDate && startYear !== endYear) {
            div0.style.display = 'none';
            div1.textContent = 'Budget estimé ' + startYear;
            div2.textContent = 'Budget estimé ' + endYear;
            div1.style.display = 'block';
            div2.style.display = 'block';
            div1b.style.display = 'block';
            div2b.style.display = 'block';
            toggleColumns('remove');
        } else {
            div0.style.display = 'inline';
            if (startYear > minStartYear) {
                div1b.style.display = 'none';
                div2.textContent = 'Budget estimé ' + startYear;
                div2.style.display = 'block';
                div2b.style.display = 'block';
            } else {
                div1.textContent = 'Budget estimé ' + startYear;
                div1.style.display = 'block';
                div1b.style.display = 'block';
                div2b.style.display = 'none';
                toggleColumns('add');
            }
        }
    }
}

// attach event listeners to the date fields
document.getElementById('start_date').addEventListener('change', checkDateYears);
document.getElementById('end_date').addEventListener('change', checkDateYears);
document.getElementById('budget_details').addEventListener('toggle', checkDateYears);
window.addEventListener("load", checkDateYears);


// 
// project for next school year
// set start and end date constraints
//
function updateDateConstraints() {
    const schoolYear = document.querySelector('input[name="school_year"]:checked');
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');

    if (schoolYear.value === 'next') {
        // Add one year to the current min and max
        const startMinDate = new Date(startDateInput.min);
        const endMaxDate = new Date(endDateInput.max);

        startMinDate.setFullYear(startMinDate.getFullYear() + 1);
        endMaxDate.setFullYear(endMaxDate.getFullYear() + 1);

        startDateInput.min = startMinDate.toISOString().split('T')[0];
        startDateInput.max = endMaxDate.toISOString().split('T')[0];
        endDateInput.min = startMinDate.toISOString().split('T')[0];
        endDateInput.max = endMaxDate.toISOString().split('T')[0];
    } else if (schoolYear.value === 'current') {
        // Reset to original constraints (one year earlier)
        const startMinDate = new Date(startDateInput.min);
        const endMaxDate = new Date(endDateInput.max);

        startMinDate.setFullYear(startMinDate.getFullYear() - 1);
        endMaxDate.setFullYear(endMaxDate.getFullYear() - 1);

        startDateInput.min = startMinDate.toISOString().split('T')[0];
        startDateInput.max = endMaxDate.toISOString().split('T')[0];
        endDateInput.min = startMinDate.toISOString().split('T')[0];
        endDateInput.max = endMaxDate.toISOString().split('T')[0];
    }
}

// attach event listeners on school year radio input field
const syRadioButtons = document.querySelectorAll('input[name="school_year"]');
syRadioButtons.forEach(radio => {
    radio.addEventListener('change', updateDateConstraints);
});


//
// Add (visibility to) link fields
//
function addLinkField() {
    const linksDiv = document.getElementById('link-fields');
    const linkFields = linksDiv.getElementsByClassName('columns');
    let nextFieldIndex = -1;

    // Find the next hidden link field
    for (let i = 0; i < linkFields.length; i++) {
        if (linkFields[i].classList.contains('is-hidden')) {
            nextFieldIndex = i;
            break;
        }
    }

    // Unhide the next hidden link field if available
    if (nextFieldIndex !== -1) {
        linkFields[nextFieldIndex].classList.remove('is-hidden');
    }

    // Hide the button if all fields are visible
    if (nextFieldIndex === linkFields.length - 1) {
        document.getElementById('add-link-button').style.display = 'none';
    }
}


//
// Toggle visibility of budget comment fields
//
document.addEventListener('DOMContentLoaded', function () {
    // select all budget fields
    const budgetFields = document.querySelectorAll('input[id^="budget_"][id$="_1"], input[id^="budget_"][id$="_2"]');

    budgetFields.forEach(field => {
        field.addEventListener('input', function () {
            // get the budget comment element
            const budgetCommentField = field.closest('.toggle-narrow-column').nextElementSibling;

            if (parseInt(field.value) > 0) {
                budgetCommentField.style.display = 'block';
            } else {
                budgetCommentField.style.display = 'none';
            }
        });
    });
});
