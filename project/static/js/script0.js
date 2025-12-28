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

            // add the "is-loading" class to the button
            this.classList.add('is-loading');
        });
    });
});

// 
// secure click once button
//
document.addEventListener('DOMContentLoaded', function () {
    // get all elements with class click-once
    const buttons = document.querySelectorAll('.click-once');

    buttons.forEach(function (button) {
        // add click event listener
        button.addEventListener("click", function (event) {

        // disable the submit button to prevent multiple submissions
        this.disabled = true;

        // add the "is-loading" class to the button
        this.classList.add('is-loading');
        });
    });
});
