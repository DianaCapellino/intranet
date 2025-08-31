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

            const table = document.getElementById('table-stats-results');
            if (table) {
                clear_old_table_stats();
            };

            document.getElementById('4-stats').innerHTML = "";
            
            // Avoid the default to load the page again
            event.preventDefault();

            // Get the info for month stats
            if (btn_id == "2" ) {
                const month_select = document.getElementById("month-select");
                const year_select = document.getElementById("year-select");
                const type_select = document.getElementById("type-select-month");

                const month_value = month_select.value;
                const year_value = year_select.value;
                const type_value = type_select.value;

                get_results(btn_id, month_value, year_value, type_value);

            } else if (btn_id == "4") {
                const date_from_select = document.getElementById("date-from");
                const date_to_select = document.getElementById("date-to");
                const type_select = document.getElementById("type-select-personalized");

                const date_from_value = date_from_select.value;
                const date_to_value = date_to_select.value;
                const type_value = type_select.value;

                const date_from = new Date(date_from_value);
                const date_to = new Date(date_to_value);

                get_results(btn_id, date_from, date_to, type_value);
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

    // Hide the table with the sum of the results
    const results_sum = document.getElementById('stats-sum');
    if (results_sum) {
        results_sum.classList.add("d-none");
        document.getElementById('4-stats').innerHTML = "";
    };

    const table = document.getElementById('table-stats-results');
    if (table) {
        clear_old_table_stats();
    };
}

function get_results(btn_id, value1, value2, type) {

    // Empty labels
    let labels = [];

    // According to the info, display the entries/trips
    fetch(`${type}/json`)
    .then(response => response.json())
    .then(list => {
        labels = Object.keys(list[0]);

        // Create the empty table
        const table_body = create_stats_table(labels);
        let items = [];

        list.forEach(item => {

            // Option entries and MONTH
            if (type == "entries") {

                // All the entries
                

                if (btn_id == "2") {

                    // Get the date from the entry starting date
                    const month_string = item["starting_date"].slice(5,7);
                    const month = parseInt(month_string);
                    const year = item["starting_date"].slice(0,4);
                    
                    // Check if the month and year matches the required
                    if (month == value1 && year == value2) {
                        
                        // Add new row to the table
                        const entry_row = create_row_stats(labels, item);                   
                        table_body.appendChild(entry_row);

                    };
                } else if (btn_id == "4") {
                    const date_string = item["starting_date"].slice(0,10);
                    const date = new Date(date_string);
                
                    if (date >= value1 && date <= value2) {
                        items.push(item);
                        console.log(value1, value2, date);
                        console.log(item["starting_date"], date)
                        // Add new row to the table
                        const entry_row = create_row_stats(labels, item);                   
                        table_body.appendChild(entry_row);
                    };
                };
                
            };            
        });
        get_table_sum(items, type);
    });

}

function create_stats_table (labels) {

    // Get the div where the table will be displayed
    const div = document.querySelector('#report_results');

    // Creates the table inside the modal
    const table = document.createElement('table');
    const head = document.createElement('thead');
    const body = document.createElement('tbody');

    table.id = 'table-stats-results';
    table.classList.add('table');
    table.classList.add('table-hover');

    // Creates table head
    labels.forEach(label => {
        const th = document.createElement('th');
        th.innerHTML = label;
        head.appendChild(th);
    });
    
    // Add the content to the table created
    table.appendChild(body);
    table.appendChild(head);
    div.appendChild(table);
    
    // Gets the datatable format with the spanish language activated
    new DataTable(table, {
        layout: {
            topStart: {
                buttons: [
                    {
                        extend: 'excelHtml5',
                        text: '<i class="fa fa-file-excel"></i>',
                        titleAttr: 'Exportar a Excel',
                        className: 'btn btn-dark m-1',
                        exportOptions: {
                            columns: ':visible'
                        }
                    },
                    {
                        extend: 'print',
                        text: '<i class="fa fa-print"></i>',
                        titleAttr: 'Imprimir',
                        className: 'btn btn-dark m-1',
                        exportOptions: {
                            columns: ':visible'
                        }
                    },
                    {
                        extend: 'colvis',
                        text: 'Gestionar Columnas',
                        titleAttr: 'Columnas',
                        className: 'btn btn-dark m-1',
                        exportOptions: {
                            columns: ':visible'
                        }
                    }
                ]
            }
        },
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
        lengthMenu: [ [100, 50, -1], [100, 50, "Todos"] ],
        order: [[7, 'desc']],
    });
    return body;

}

function create_row_stats (labels, item) {
    // Create the row
    const entry_row = document.createElement('tr');

    // Create every value according to the label
    labels.forEach(label => {
        const td = document.createElement('td');
        td.innerHTML = item[label];
        entry_row.appendChild(td);
    });

    return entry_row;

}

function clear_old_table_stats () {
    const table_datatable = $('report_results').DataTable();
    if (table_datatable) {
        table_datatable.destroy();
    };

    const table_wrapper = document.getElementById('table-stats-results_wrapper');
    if (table_wrapper) {
        table_wrapper.remove();
    };

    const table = document.getElementById('table-stats-results');
    if (table) {
        table.remove();
    };
}

function get_table_sum (items, type) {
    let labels = [
        "Cantidad Quotes A",
        "Cantidad Quotes Todas",
        "Suma Quotes A",
        "Suma Quotes Todas",
        "Cantidad Booking 1",
        "Cantidad Booking Todas",
        "Suma Booking 1",
        "Suma Booking Todas",
        "Cantidad otros"
    ];

    quotesA = 0;
    all_quotes = 0;
    sum_quotesA = 0;
    sum_all_quotes = 0;
    bookings1 = 0;
    all_bookings = 0;
    sum_bookings1 = 0;
    sum_all_bookings = 0;
    others = 0;

    if (type == "entries") {
        items.forEach(item => {
            if (item.status == "Quote") {
                all_quotes++;
                sum_all_quotes += item.amount;
                if (item.version_quote == "A") {
                    quotesA++;
                    sum_quotesA += item.amount;
                };
            } else if (item.status == "Booking") {
                all_bookings++;
                sum_all_bookings += item.amount;
                if (item.version == "1") {
                    bookings1++;
                    sum_bookings1 += item.amount;
                };
            } else {
                others++;
            };
        });
    };

    const table = document.getElementById('4-stats');
    document.getElementById('stats-sum').classList.remove('d-none');
    const thead = document.createElement('thead');
    const tbody = document.createElement('tbody');

    labels.forEach(label => {
        const th = document.createElement('th');
        th.innerHTML = label;
        thead.appendChild(th);
    });

    const td1 = document.createElement('td');
    const td2 = document.createElement('td');
    const td3 = document.createElement('td');
    const td4 = document.createElement('td');
    const td5 = document.createElement('td');
    const td6 = document.createElement('td');
    const td7 = document.createElement('td');
    const td8 = document.createElement('td');
    const td9 = document.createElement('td');

    td1.innerHTML = quotesA;
    td2.innerHTML = all_quotes;
    td3.innerHTML = sum_quotesA;
    td4.innerHTML = sum_all_quotes;
    td5.innerHTML = bookings1;
    td6.innerHTML = all_bookings;
    td7.innerHTML = sum_bookings1;
    td8.innerHTML = sum_all_bookings;
    td9.innerHTML = others;

    tbody.appendChild(td1);
    tbody.appendChild(td2);
    tbody.appendChild(td3);
    tbody.appendChild(td4);
    tbody.appendChild(td5);
    tbody.appendChild(td6);
    tbody.appendChild(td7);
    tbody.appendChild(td8);
    tbody.appendChild(td9);

    table.appendChild(thead);
    table.appendChild(tbody);

}