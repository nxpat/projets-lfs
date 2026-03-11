
//
// Set school year form
//
document.addEventListener('DOMContentLoaded', function () {
  const startDate = document.getElementById('sy_start');
    const endDate = document.getElementById('sy_end');
    const checkbox = document.getElementById('sy_auto');

    // get today's date
    const today = new Date();

    // default start and end dates
    const defaultStartDate = new Date(
    Date.UTC(today.getFullYear() - (today.getMonth() < 8 ? 1 : 0), 8, 1, 0, 0, 0)
    ); // September is month 8
    const defaultEndDate = new Date(
    Date.UTC(today.getFullYear() + (today.getMonth() < 8 ? 0 : 1), 7, 31, 0, 0, 0)
    ); // August is month 7

    // helper to format YYYY-MM-DD
    const toYMD = (d) => d.toISOString().split('T')[0];

    // attach checkbox listener only if it exists
    if (checkbox) {
    checkbox.addEventListener('change', function () {
        if (checkbox.checked) {
        if (startDate) startDate.value = toYMD(defaultStartDate);
        if (endDate) endDate.value = toYMD(defaultEndDate);
        }
    });
    }

    // attach date field listeners only if they exist
    if (startDate) {
    startDate.addEventListener('change', function () {
        if (checkbox?.checked) checkbox.checked = false;
    });
    }

    if (endDate) {
    endDate.addEventListener('change', function () {
        if (checkbox?.checked) checkbox.checked = false;
    });
    }
});



//
// Toggle school years / fiscal years field for Download form
//
const radioButtons = document.querySelectorAll('input[name="selection_mode"]');
const schoolDiv = document.getElementById('sy-container');
const fiscalDiv = document.getElementById('fy-container');

function toggleFields() {
    // Get the value of the currently checked radio button
    const checked = document.querySelector('input[name="selection_mode"]:checked');
    const selectedValue = checked ? checked.value : null;

    if (selectedValue === 'sy') {
        if (schoolDiv) schoolDiv.style.display = 'block';
        if (fiscalDiv) fiscalDiv.style.display = 'none';
    } else if (selectedValue === 'fy') {
        if (schoolDiv) schoolDiv.style.display = 'none';
        if (fiscalDiv) fiscalDiv.style.display = 'block';
    } else {
        // no selection: hide both (safe default)
        if (schoolDiv) schoolDiv.style.display = 'none';
        if (fiscalDiv) fiscalDiv.style.display = 'none';
    }
}

// Attach the listener to every radio button (only if any exist)
if (radioButtons && radioButtons.length > 0) {
  radioButtons.forEach(radio => {
    radio.addEventListener('change', toggleFields);
  });
}

// Run once on page load to set the initial state
toggleFields();
