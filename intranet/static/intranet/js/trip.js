document.addEventListener('DOMContentLoaded', () => {
    // Gets the datatable format to the tables with the spanish language activated
    create_datatable("trips");
    create_datatable("entries");
    create_datatable("countries");
    create_datatable("contacts");
    create_datatable("clients");
    create_datatable("users");

    // Modifies the date format to be shown in the form
    let today = new Date().toISOString().slice(0, 10);
    const allDates = document.getElementsByClassName("date-input");
    const allDatesArray = [...allDates];
    allDatesArray.forEach(date => {
        date.value = today;
    });

    // Display forms when clicking button
    btn_display("trip");
    btn_display("entry");

    // Creates the functionality when pressing the eye
    eye_funcionality();

    // Creates the listeners when opening and closing modals
    modal_funcionality();

})

function create_datatable (type) {
    if (type == "entries") {
        new DataTable(`#${type}`, {
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
            },
            responsive: true,
            order: [[0, 'desc']],
        });

    } else {
        new DataTable(`#${type}`, {
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
                responsive: true,
            },
        });
    };
}

function btn_display (type) {
    const new_btn = document.querySelector(`#new_${type}_btn`);
    if (new_btn != null) {
        new_btn.addEventListener("click", () => {
            document.querySelector(`#new_${type}`).className = 'd-block';
            document.querySelector(`#${type}_list`).className = 'd-none';
            document.querySelector(`#new_${type}_btn`).className = 'd-none';
        });
    };
}

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

    // Delete table when it is closed
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
        if (Array.isArray(list)) {
            list.forEach(element => {
                const entry_row = create_entry_row(element);
                table_body.appendChild(entry_row);
            });
        };
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
    // Get the div where the table will be displayed
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
    entry_row.innerHTML = `<td>${element.starting_date}</td><td>${element.closing_date}</td><td>${element.status}</td><td>${element.version}</td><td>${element.amount}</td><td>${element.user_creator}</td><td>${element.user_working}</td><td>${element.progress}</td><td>${element.importance}</td>`;
    return entry_row;
}