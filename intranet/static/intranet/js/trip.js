document.addEventListener('DOMContentLoaded', () => {
    // Gets the datatable format to the tables with the spanish language activated
    create_datatable("trips");
    create_datatable("entries");
    create_datatable("countries");
    create_datatable("contacts");
    create_datatable("clients");
    create_datatable("users");
    create_datatable("entries-creating");

    // Modifies the date format to be shown in the forms
    modify_date_and_datetime();

    // Display forms when clicking button
    btn_display("trip");
    btn_display("entry");

    // Creates the functionality when pressing the eye
    eye_functionality();

    // Creates the listeners when opening and closing modals
    modal_functionality();

    // Creates the listeners when selecting the user when creating entry
    user_working_functionality();

    // Creates the listeners for deleting elements
    deleting_functionality("countries");
    deleting_functionality("clients");
    deleting_functionality("contacts");
    deleting_functionality("users");
})

function modify_date_and_datetime() {
    const now = new Date();
    const local_now = new Date(now.getTime() - 10800000);
    const local_ISO_datetime = local_now.toISOString().slice(0, 16);
    const allTimeDates = document.getElementsByClassName("datetime-input");
    const allDatetimesArray = [...allTimeDates];
    allDatetimesArray.forEach(date => {
        date.value = local_ISO_datetime;
    });

    const local_ISO_date = local_now.toISOString().slice(0, 10);
    const allDates = document.getElementsByClassName("date-input");
    const allDatesArray = [...allDates];
    allDatesArray.forEach(date => {
        date.value = local_ISO_date;
    });
}

function create_datatable (type) {
    if (type == ("entries")) {
        new DataTable(`#${type}`, {
            layout: {
                topStart: {
                    buttons: [
                        {
                          extend: 'excelHtml5',
                          text: '<i class="fas fa-file-excel"></i> ',
                          titleAttr: 'Exportar a Excel',
                          className: 'btn btn-success',
                        }
                    ]
                }
            },
            columnDefs: [{ orderable: false, targets: -1 }],
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
            },
            order: [[0, 'desc']],
        });       

    } else {
        new DataTable(`#${type}`, {
            layout: {
                topStart: {
                    buttons: [
                        {
                          extend: 'excelHtml5',
                          text: '<i class="fas fa-file-excel"></i> ',
                          titleAttr: 'Exportar a Excel',
                          className: 'btn btn-success',
                        }
                    ]
                }
            },
            columnDefs: [{ orderable: false, targets: -1 }],
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
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

function modal_functionality() {
    
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

function eye_functionality() {
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

function user_working_functionality() {
    const user_working_select = document.getElementById('user_working_select');
    if (user_working_select != null) {
        user_working_select.addEventListener('change', function() {
            const selectedValue = this.value;
            let entries_creating = $('#entries-creating').DataTable();
            entries_creating.column(7).search(selectedValue).draw();
        });
    };
}

function deleting_functionality(type) {
    const all_delete_btns = document.querySelectorAll(`.delete-${type}-btn`);
    all_delete_btns.forEach((item) => {
        if (item != null) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            item.addEventListener('click', () => {
                // Gets the item id
                let id_string = item.id.match(/\d+/);
                let id = parseInt(id_string[0]);
        
                // Makes the request to the server to delete
                fetch(`${type}/json/${id}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                })
                .then(response => response.json)
                .then(window.location = `../../${type}`)
            });
        };
    });
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
                const entry_row = create_entry_row(element, trip_id);
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
    table.classList.add('table');
    table.classList.add('table-hover');

    // Creates table head
    if (type == "entries") {
        head.innerHTML = '<th>Fecha Pedido</th><th>Fecha Respuesta</th><th>Status</th><th>Versión</th><th>Monto</th><th>Creado por</th><th>Trabajado por</th><th>Progreso</th><th>Valoración</th><th>Valoración</th>';
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
        order: [[0, 'desc']],
        lengthMenu: [ [5, 10, 20, -1], [5, 10, 20, "Todos"] ],
        columnDefs: [{ orderable: false, targets: -1 }]
    });
    return body;
}

function create_entry_row(element, trip_id) {
    
    // Creates table row
    const entry_row = document.createElement('tr');

    const starting_date = document.createElement("td");
    const closing_date = document.createElement("td");
    const status = document.createElement("td");
    const version = document.createElement("td");
    const amount = document.createElement("td");
    const user_creator = document.createElement("td");
    const user_working = document.createElement("td");
    const progress = document.createElement("td");
    const importance = document.createElement("td");
    const actions = document.createElement("td");

    
    if (element.isClosed == false) {
        closing_date.innerHTML = 'n/a';
    } else {
        closing_date.innerHTML = `${element.closing_date}`;
    };

    if (element.amount == null) {
        amount.innerHTML = `Pendiente`;
    } else {
        amount.innerHTML = `USD ${element.amount}.00`;
    };

    if (element.status == "Quote") {   
        version.innerHTML = `${element.version_quote}`;
    } else {
        version.innerHTML = `${element.version}`;
    };

    starting_date.innerHTML = `${element.starting_date}`;
    status.innerHTML = `${element.status}`;
    user_creator.innerHTML = `${element.user_creator}`;
    progress.innerHTML = `${element.progress}`;
    user_working.innerHTML = `${element.user_working}`;
    importance.innerHTML = `${element.importance}`;

    const div_actions = document.createElement('div');
    div_actions.classList.add('justify-content-around');
    div_actions.classList.add('d-flex');

    const pencil_icon = document.createElement('i');
    const trash_icon = document.createElement('i');

    pencil_icon.classList.add('fa-solid');
    pencil_icon.classList.add('fa-pencil');
    trash_icon.classList.add('fa-solid');
    trash_icon.classList.add('fa-trash');

    pencil_icon.setAttribute("id", `pencil-entry-${trip_id}`)
    trash_icon.setAttribute("id", `trash-entry-${trip_id}`)

    div_actions.appendChild(pencil_icon);
    div_actions.appendChild(trash_icon);
    actions.appendChild(div_actions);

    entry_row.appendChild(starting_date);
    entry_row.appendChild(closing_date);
    entry_row.appendChild(status);
    entry_row.appendChild(version);
    entry_row.appendChild(amount);
    entry_row.appendChild(user_creator);
    entry_row.appendChild(user_working);
    entry_row.appendChild(progress);
    entry_row.appendChild(importance);
    entry_row.appendChild(actions);
    
    return entry_row;
}