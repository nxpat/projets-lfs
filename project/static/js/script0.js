// 
// secure submit once button
//
document.addEventListener('DOMContentLoaded', function () {
    // get all elements with class submit-once
    const submitButtons = document.querySelectorAll('.submit-once');

    submitButtons.forEach(function (submitButton) {
        // add click event listener
        submitButton.addEventListener("click", function (event) {
            // check if the form is valid
            if (!this.form.checkValidity()) return; // If not valid, exit

            // send the form if valid
            this.form.submit();

            // disable the submit button to prevent multiple submissions
            this.disabled = true;
        });
    });
});


// 
// secure submit once button with confirmation dialog
//
function confirmAction(button, message) {
    if (confirm(message)) {
        // if form not valid, exit
        if (!button.form.checkValidity()) return;

        // submit the form
        button.form.submit();

        // disable the submit button to prevent multiple submissions
        button.disabled = true;
    } else {
        return false;
    }
}
