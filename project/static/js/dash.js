
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
    // Start date = September 1st of the current school year
    const defaultStartDate = new Date(Date.UTC(today.getFullYear() - (today.getMonth() < 8 ? 1 : 0), 8, 1, 0, 0, 0));  // September is month 8
    // End date = August 31st of the current school year
    const defaultEndDate = new Date(Date.UTC(today.getFullYear() + (today.getMonth() < 8 ? 0 : 1), 7, 31, 0, 0, 0));  // August is month 7

    // debug
    // console.log("Start Date:", defaultStartDate.toISOString().split('T')[0]); // format as YYYY-MM-DD
    // console.log("End Date:", defaultEndDate.toISOString().split('T')[0]);

    // event listener for the checkbox
    checkbox.addEventListener('change', function () {
        if (checkbox.checked) {
            // fill default dates if checkbox is checked
            startDate.value = defaultStartDate.toISOString().split('T')[0];
            endDate.value = defaultEndDate.toISOString().split('T')[0];
        }
    });

    // event listeners for the date fields
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