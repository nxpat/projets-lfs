// ==========================================
// DASHBOARD LOGIC
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    initSchoolYearForm();
    initDownloadFormToggle();
});

function initSchoolYearForm() {
    const startDate = document.getElementById('sy_start');
    const endDate = document.getElementById('sy_end');
    const checkbox = document.getElementById('sy_auto');
    if (!startDate && !endDate && !checkbox) return;

    const today = new Date();
    const defaultStartDate = new Date(Date.UTC(today.getFullYear() - (today.getMonth() < 8 ? 1 : 0), 8, 1));
    const defaultEndDate = new Date(Date.UTC(today.getFullYear() + (today.getMonth() < 8 ? 0 : 1), 7, 31));

    const toYMD = (d) => d.toISOString().split('T')[0];

    if (checkbox) {
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                if (startDate) startDate.value = toYMD(defaultStartDate);
                if (endDate) endDate.value = toYMD(defaultEndDate);
            }
        });
    }

    const uncheckAuto = () => { if (checkbox?.checked) checkbox.checked = false; };
    if (startDate) startDate.addEventListener('change', uncheckAuto);
    if (endDate) endDate.addEventListener('change', uncheckAuto);
}

function initDownloadFormToggle() {
    const radioButtons = document.querySelectorAll('input[name="selection_mode"]');
    if (radioButtons.length === 0) return;

    const schoolDiv = document.getElementById('sy-container');
    const fiscalDiv = document.getElementById('fy-container');

    const toggleFields = () => {
        const checked = document.querySelector('input[name="selection_mode"]:checked');
        const selectedValue = checked ? checked.value : null;

        if (schoolDiv) schoolDiv.style.display = selectedValue === 'sy' ? 'block' : 'none';
        if (fiscalDiv) fiscalDiv.style.display = selectedValue === 'fy' ? 'block' : 'none';
    };

    radioButtons.forEach(radio => radio.addEventListener('change', toggleFields));
    toggleFields(); // Initial state
}