// 
// This script configures date input constraints 
// based on the selected school year (current or next).
//
function updateDateConstraints() {
    // Get the selected school year (current or next)
    const schoolYear = document.querySelector('input[name="school_year"]:checked');
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');

    // If the user selects the 'next' school year
    if (schoolYear.value === 'next') {
        // Retrieve and increment the current minimum and maximum dates for the next year
        const startMinDate = new Date(startDateInput.min);
        const endMaxDate = new Date(endDateInput.max);

        startMinDate.setFullYear(startMinDate.getFullYear() + 1);
        endMaxDate.setFullYear(endMaxDate.getFullYear() + 1);

         // Update the input fields with the new constraints
        startDateInput.min = startMinDate.toISOString().split('T')[0];
        startDateInput.max = endMaxDate.toISOString().split('T')[0];
        endDateInput.min = startMinDate.toISOString().split('T')[0];
        endDateInput.max = endMaxDate.toISOString().split('T')[0];

    // If the user selects the 'current' school year
    } else if (schoolYear.value === 'current') {
        // Reset to original constraints (one year earlier)
        const startMinDate = new Date(startDateInput.min);
        const endMaxDate = new Date(endDateInput.max);

        startMinDate.setFullYear(startMinDate.getFullYear() - 1);
        endMaxDate.setFullYear(endMaxDate.getFullYear() - 1);

        // Reset the input fields with the original constraints
        startDateInput.min = startMinDate.toISOString().split('T')[0];
        startDateInput.max = endMaxDate.toISOString().split('T')[0];
        endDateInput.min = startMinDate.toISOString().split('T')[0];
        endDateInput.max = endMaxDate.toISOString().split('T')[0];
    }
}

// Attach event listeners to the school year radio buttons 
// to trigger the date constraint update function upon change
const syRadioButtons = document.querySelectorAll('input[name="school_year"]');
syRadioButtons.forEach(radio => {
    radio.addEventListener('change', updateDateConstraints);
});


// 
// This script manages date input fields for a scheduling system,
// ensuring that the end date is appropriately set based on the start date.
// 

function ensureValidEndDate() {
    // Get the end date input element
    const endDateInput = document.getElementById('end_date');

    // Get the values of the start and end date inputs
    const startDate = document.getElementById('start_date').value;
    const endDate = endDateInput.value;

    // Get the minimum allowed start date
    const minStartDate = document.getElementById("start_date").min;

    // If a start date is specified
    if (startDate) {
        // If the end date is not set or is earlier than the start date, 
        // set it to the start date
        if (!endDate || endDate < startDate) {
            endDateInput.value = startDate;
        }

        // Set the minimum allowable end date to match the selected start date
        endDateInput.min = startDate;
    }
}

// Attach event listeners to the date fields 
// to validate and synchronize dates on user input
document.getElementById('start_date').addEventListener('change', ensureValidEndDate);
document.getElementById('end_date').addEventListener('change', ensureValidEndDate);
window.addEventListener("load", ensureValidEndDate);


// 
// This script manages the visibility of the "students" field 
// based on the selected requirement option.
// 

// Select all requirement radio buttons
const requirementRadios = document.querySelectorAll('input[name="requirement"]');

// Get the students list div
const studentsDiv = document.getElementById('students-list');

// Function to handle the visibility of the students list div
function updateStudentsDivVisibility() {
    // Check the currently selected requirement option
    if (document.querySelector('input[name="requirement"]:checked').value === 'no') {
        // If 'no' is selected, show the students list div
        studentsDiv.style.display = 'block';
    } else {
        // Otherwise, hide the students list div
        studentsDiv.style.display = 'none';
    }
}

// Attach event listeners to the requirement radio buttons 
// to update the students list visibility on change
requirementRadios.forEach(radio => {
    radio.addEventListener('change', updateStudentsDivVisibility);
});


// 
// This script manages the visibility of the "fieldtrip" fields 
// based on the selected location option ("outer" or "trip").
// 

// Select all location radio buttons
const locationRadios = document.querySelectorAll('input[name="location"]');

// Get the "fieldtrip" container div
const fieldtripDiv = document.getElementById('fieldtrip');

// Function to update the visibility of the "fieldtrip" container
function updateFieldtripDivVisibility(location) {
    // Check if the selected location is either 'outer' or 'trip'
    if (location && (location.value === 'outer' || location.value === 'trip')) {
        // Show the fieldtrip div
        fieldtripDiv.style.display = 'block';
    } else {
        // Hide the fieldtrip div
        fieldtripDiv.style.display = 'none';
    }
}

// Add event listeners to the location radio buttons 
// to trigger visibility update on selection change
locationRadios.forEach(radio => {
    radio.addEventListener('change', function() {
        updateFieldtripDivVisibility(this);
    });
});


// 
// This function manages the visibility of link fields,
// allowing users to add more link input fields dynamically.
// 
function addLinkField() {
    // Get the container div for link fields
    const linksDiv = document.getElementById('link-fields');
    const linkFields = linksDiv.getElementsByClassName('columns');
    let nextFieldIndex = -1;

    // Find the next hidden link field
    for (let i = 0; i < linkFields.length; i++) {
        if (linkFields[i].classList.contains('is-hidden')) {
            nextFieldIndex = i;  // Store the index of the next hidden field
            break;
        }
    }

    // If a hidden link field is found, unhide it
    if (nextFieldIndex !== -1) {
        linkFields[nextFieldIndex].classList.remove('is-hidden');
    }

    // Hide the "Add Link" button if no more hidden fields are available
    if (nextFieldIndex === linkFields.length - 1) {
        document.getElementById('add-link-button').style.display = 'none';
    }
}


// 
// This script manages the visibility of the budget details 
// section based on the selected budget option.
// 

// Select all budget radio buttons
const budgetRadios = document.querySelectorAll('input[name="budget"]');

// Get the budget details container div
const budgetDetailsDiv = document.getElementById('budget_details');

// Function to update the visibility of the budget details div
function updateBudgetDetailsDivVisibility() {
    // Check if the selected budget option is 'Oui'
    if (document.querySelector('input[name="budget"]:checked').value === 'Oui') {
         // Show the budget details div
        budgetDetailsDiv.style.display = 'block';
    } else {
        // Hide the budget details div
        budgetDetailsDiv.style.display = 'none';
    }
}


// Add event listeners to the budget radio buttons 
// to trigger visibility update on selection change
budgetRadios.forEach(radio => {
    radio.addEventListener('change', updateBudgetDetailsDivVisibility);
});


// 
// This script manages budget fields for one or two fiscal years.
// It toggles visibility and layout of budget columns based on selected 
// start and end dates.
// 

// Function to toggle a two-column layout (budget amount and description) 
// for budget fields when the project spans only one fiscal year. 
// If the project spans two fiscal years, it removes the columns and resets 
// to a single-column format.
function toggleColumns(action) {
    const columnsDivs = document.getElementsByClassName('budget-columns');
    const columnDivs = document.getElementsByClassName('budget-amount-column');
    const narrrowColDivs = document.getElementsByClassName('budget-comment-column');

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

// 
// This function copies values from budget fields associated with year1 
// to the corresponding fields for year2, if the target field is either 
// zero or empty. 
//
function copyBudgetValues(year1, year2) {
    // Select all input budget fields for year1
    const budgetFields1 = document.querySelectorAll('input[id^="budget_"][id$="_' + year1 + '"]');

    budgetFields1.forEach(field1 => {
        const value1 = field1.value; // Get the value for year1
        const field2Id = field1.id.replace('_' + year1, '_' + year2); // Find corresponding field for year2
        const field2 = document.getElementById(field2Id); // Get the value for year2

        // Copy only if field1 > 0 and field2 == 0
        if (parseInt(field2.value) === 0 && parseInt(value1) > 0) {
            field2.value = value1; // Copy integer value
        }
    });

    // Select all textarea budget comment fields for year1
    const budgetCommentFields1 = document.querySelectorAll('textarea[id^="budget_"][id$="_c_' + year1 + '"]');

    budgetCommentFields1.forEach(field1 => {
        const value1 = field1.value; // Get the value for year1
        const field2Id = field1.id.replace('_' + year1, '_' + year2); // Find corresponding field for year2
        const field2 = document.getElementById(field2Id); // Get the value for year2

        // Copy only if field1 != "" and field2 == ""
        if (!field2.value && value1) {
            field2.value = value1; // Copy string value
            const budgetCommentColumn = field2.closest('.budget-amount-column')
            budgetCommentColumn.style.display = 'block';  // display the comment field
        }
    });
}

// Function to display budget year fields based on the selected 
// start and end dates. If the project spans two fiscal years, 
// the function reveals fields for entering two separate budgets, 
// one for each fiscal year. If the project spans only one fiscal 
// year, it shows a single budget entry.
function displayBudgetFieldsForFiscalYears() {
    const startDate = document.getElementById('start_date').value;
    const minStartDate = document.getElementById("start_date").min;
    const endDate = document.getElementById('end_date').value;

    const div1 = document.getElementById('budget-year-1');
    const div2 = document.getElementById('budget-year-2');
    const div1Label = document.getElementById('budget-label-1');
    const div2Label = document.getElementById('budget-label-2');
    
    if (startDate) {
        const startYear = new Date(startDate).getFullYear();
        const endYear = new Date(endDate).getFullYear();
        const minStartYear = new Date(minStartDate).getFullYear();

        // toggle budget columns
        if (endDate && startYear !== endYear) {
            div1Label.textContent = 'Budget estimé ' + startYear;
            div2Label.textContent = 'Budget estimé ' + endYear;
            div1.style.display = 'block';
            div2.style.display = 'block';
            toggleColumns('remove');
        } else {
            if (startYear > minStartYear) {
                div2Label.textContent = 'Budget estimé ' + startYear;
                div2.style.display = 'block';
                div1.style.display = 'none';
                copyBudgetValues('1', '2');
            } else {
                div1Label.textContent = 'Budget estimé ' + startYear;
                div1.style.display = 'block';
                div2.style.display = 'none';
                toggleColumns('add');
                copyBudgetValues('2', '1');
            }
        }
    }
}

// Attach event listeners to the date fields to update the visibility of budget fields
document.getElementById('start_date').addEventListener('change', displayBudgetFieldsForFiscalYears);
document.getElementById('end_date').addEventListener('change', displayBudgetFieldsForFiscalYears);
window.addEventListener("load", displayBudgetFieldsForFiscalYears);


// 
// This script manages the visibility of budget comment fields 
// Comments will be visible only when a budget value is entered.
// 
document.addEventListener('DOMContentLoaded', function () {
    // Select all budget fields
    const budgetFields = document.querySelectorAll('input[id^="budget_"][id$="_1"], input[id^="budget_"][id$="_2"]');

    // Loop through each budget field to add input event listener
    budgetFields.forEach(field => {
        field.addEventListener('input', function () {
            // Get the corresponding budget comment field
            const budgetCommentField = field.closest('.budget-comment-column').nextElementSibling;

            // Toggle visibility of the budget comment field
            if (parseInt(field.value) > 0) {
                budgetCommentField.style.display = 'block';
            } else {
                budgetCommentField.style.display = 'none';
            }
        });
    });
});
