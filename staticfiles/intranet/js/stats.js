document.addEventListener('DOMContentLoaded', () => {

    // Display functionality of the btn
    stats_btn_display();

})

function stats_btn_display() {

    // Add event listeners to all buttons
    const all_stats_btn = document.querySelectorAll('.stats-btn');
    if (all_stats_btn) {
        all_stats_btn.forEach((btn) => {
            btn.addEventListener('click', () => {

                // Get the number in the ID
                const btn_int = btn.id.match(/\d+/)

                // Show the form
                show_form(btn_int)
            });
        });
    };
}

function show_form(btn_id) {

    // Get the element from the form
    const stats_form = document.getElementById(`${btn_id}-stats-form`);

    // Show the correct form
    if (stats_form != null) {
        hide_all()
        stats_form.classList.remove("d-none");

        // Activate the button to generate the results
        stats_form.addEventListener('submit', function(event) {
            
            // Avoid the default to load the page again
            event.preventDefault();

            // Get the info for month stats
            if (btn_id == "2" ) {
                const month_select = document.getElementById("month-select");
                const year_select = document.getElementById("year-select");
                const type_select = document.getElementById("type-select");

                const month_value = month_select.value;
                const year_value = year_select.value;
                const type_value = type_select.value;

                get_results(btn_id, month_value, year_value, type_value);

            };

        })
    }
}

function hide_all() {
    // Get all the forms
    const all_forms = document.querySelectorAll('.stats-form');

    // Add the class to hide forms
    if (all_forms) {
        all_forms.forEach((form) => {
            form.classList.add("d-none");
        });
    };

    // Get all the results
    const all_results = document.querySelectorAll('.stats-results');

    // Add the class to hide results
    if (all_results) {
        all_results.forEach((result) => {
            result.classList.add("d-none");
        });
    };

}

function get_results(btn_id, value1, value2, value3) {

    // Getting the information if is MONTH
    if (btn_id == "2") {

        // According to the info, display the entries/trips
        fetch('entries/json')
        .then(response => response.json())
        .then(list => {
            list.forEach(entry => {
                
            });
        });
    };

}