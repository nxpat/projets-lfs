
//
// Set school year
//
document.addEventListener('DOMContentLoaded', function () {
    const checkbox = document.getElementById('sy_auto');
    const startDate = document.getElementById('sy_start');
    const endDate = document.getElementById('sy_end');

    // get today's date
    const today = new Date();

    // default start and end dates
    const defaultStartDate = new Date(today.getFullYear() - (today.getMonth() < 8 ? 1 : 0), 8, 1); // September 1st
    const defaultEndDate = new Date(today.getFullYear() + (today.getMonth() < 8 ? 0 : 1), 7, 31); // August 31st

    // Log the results to verify
    // console.log("Start Date:", defaultStartDate.toISOString().split('T')[0]); // format as YYYY-MM-DD
    // console.log("End Date:", defaultEndDate.toISOString().split('T')[0]); 

    // event listener for checkbox
    checkbox.addEventListener('change', function () {
        if (checkbox.checked) {
            // fill the dates if checkbox is checked
            startDate.value = defaultStartDate.toISOString().split('T')[0];
            endDate.value = defaultEndDate.toISOString().split('T')[0];
        }
    });

    // event listeners for date fields
    startDate.addEventListener('change', function () {
        if (checkbox.checked) {
            checkbox.checked = false; // deselect checkbox if date is modified
        }
    });

    endDate.addEventListener('change', function () {
        if (checkbox.checked) {
            checkbox.checked = false; // deselect checkbox if date is modified
        }
    });
});