trip_displayed = [];

document.addEventListener('DOMContentLoaded', () => {
    // Gets the datatable format with the spanish language activated
    new DataTable('#trips', {
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });

    new DataTable('#entries', {
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });

    // Modifies the date format to be shown in the form
    let today = new Date().toISOString().slice(0, 10);
    const allDates = document.getElementsByClassName("date-input");
    const allDatesArray = [...allDates];
    allDatesArray.forEach(date => {
        date.value = today;
    });

    // Display form when clicking button
    const new_trip_btn = document.querySelector('#new_trip_btn');
    if (new_trip_btn != null) {
        new_trip_btn.addEventListener("click", () => {
            document.querySelector('#new_trip').className = 'd-block';
            document.querySelector('#trip_list').className = 'd-none';
            document.querySelector('#new_trip_btn').className = 'd-none';
        });
    };

    // Display form when clicking button
    const new_entry_btn = document.querySelector('#new_entry_btn');
    if (new_entry_btn != null) {
        new_entry_btn.addEventListener("click", () => {
            document.querySelector('#new_entry').className = 'd-block';
            document.querySelector('#entry_list').className = 'd-none';
            document.querySelector('#new_entry_btn').className = 'd-none';
        });
    };

    // Creates the functionality when pressing the eye
    eye_funcionality();

    // Creates the listeners when opening and closing modals
    modal_funcionality();

})

function modal_funcionality() {
    
    // Display entries and notes when the modal is completely open
    const all_modal_trips = document.querySelectorAll('.modal-trip');
    all_modal_trips.forEach((item) => {
        $(item).on('shown.bs.modal', function() {
            let trip_id_string = item.id.match(/\d+/);
            let trip_id = parseInt(trip_id_string[0]);
            display_entries(trip_id);
        })
    });

    // Delete table when it is close
    all_modal_trips.forEach((item) => {
        $(item).on('hidden.bs.modal', function() {
            let trip_id_string = item.id.match(/\d+/);
            let trip_id = parseInt(trip_id_string[0]);
            
            // Clears the table and datatable for this trip if already exists
            clear_old_table("entries", trip_id);
        })
    });
}

function eye_funcionality() {
    const pending_eye = document.querySelector('#pending-eye');
    let eye_is_open = false;
    if (pending_eye != null) {
        pending_eye.addEventListener("click", () => {
            const all_pending_entries = document.querySelectorAll('.pending-entry');
            if (eye_is_open == false) {
                all_pending_entries.forEach(entry => {
                    entry.classList.remove("d-none");
                });
                pending_eye.classList.remove("fa-eye-slash");
                pending_eye.classList.add("fa-eye");
                eye_is_open = true;
            } else {
                all_pending_entries.forEach(entry => {
                    entry.classList.add("d-none");
                });
                eye_is_open = false;
                pending_eye.classList.remove("fa-eye");
                pending_eye.classList.add("fa-eye-slash");
            };

        });
    };
}

function display_entries(trip_id) {

    fetch(`/jsontrip_entries/${trip_id}`)
    .then(response => response.json())
    .then(list => {

        // If creates the empty table
        const table_body = create_table("entries", trip_id);

        // Creates all the rows
        list.forEach(element => {
            const entry_row = create_entry_row(element);
            table_body.appendChild(entry_row);
        });
    });
}

function clear_old_table (type, trip_id) {
    const table_datatable = $(`${type}-${trip_id}`).DataTable();
    if (table_datatable) {
        table_datatable.destroy();
    };

    const table_wrapper = document.getElementById(`${type}-table-${trip_id}_wrapper`);
    if (table_wrapper) {
        table_wrapper.remove();
    };

    const table = document.getElementById(`${type}-table-${trip_id}`);
    if (table) {
        table.remove();
    };
}

function create_table(type, reference) {
    // Get the entry div where the table will be displayed
    const div = document.querySelector(`#${type}-${reference}`);

    // Creates the table inside the modal
    const table = document.createElement('table');
    const head = document.createElement('thead');
    const body = document.createElement('tbody');

    table.id = `${type}-table-${reference}`;

    // Creates table head
    if (type == "entries") {
        head.innerHTML = '<th>Fecha Pedido</th><th>Fecha Respuesta</th><th>Status</th><th>Versión</th><th>Monto</th><th>Creado por</th><th>Trabajado por</th><th>Progreso</th><th>Valoración</th>';
    };
    
    // Add the content to the table created
    table.appendChild(body);
    table.appendChild(head);
    div.appendChild(table);
    
    // Gets the datatable format with the spanish language activated
    new DataTable(table, {
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });
    return body;
}

function create_entry_row(element) {
    
    // Creates table row
    const entry_row = document.createElement('tr');
    entry_row.innerHTML = `<td>${element.starting_date}</td><td>${element.closing_date}</td><td>${element.status}</td><td>${element.version}</td><td>${element.amount}</td><td>${element.user_creator_id}</td><td>${element.user_working_id}</td><td>${element.progress}</td><td>${element.importance}</td>`;
    return entry_row;
}