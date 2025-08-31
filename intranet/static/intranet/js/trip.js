document.addEventListener('DOMContentLoaded', () => {

    // Modifies the date format to be shown in the forms
    modify_date_and_datetime();

    // Display forms when clicking button
    btn_display("trip");
    btn_display("entry");
    btn_display("user");

    // Creates the functionality when pressing the eye
    eye_functionality();

    // Creates the listeners when opening and closing modals
    modal_functionality();

    // Creates the listeners when selecting the user when creating entry and filtering
    user_working_functionality();
    user_filter_functionality();

    create_entry_from_pendings();

    // Creates the listeners for deleting elements
    deleting_functionality("countries");
    deleting_functionality("clients");
    deleting_functionality("contacts");
    deleting_functionality("users");
    deleting_functionality("trips");
    deleting_functionality("entries");

    create_chart("pendings_chart");

    // Gets the datatable format to the tables with the spanish language activated
    create_datatable("trips");
    create_datatable("entries");
    create_datatable("countries");
    create_datatable("contacts");
    create_datatable("clients");
    create_datatable("users");
    create_datatable("entries-creating");
    create_datatable("tariff-table");
    create_datatable("entries-index");

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
            lengthMenu: [ [30, 20, -1], [30, 20, "Todos"] ],
            columnDefs: [
                { orderable: false, targets: -1 },
                { width: '20%', target: 2 },
                { visible: false, targets: [4, 7, 12]}
            ],
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
            },
            order: [[0, 'desc']],
        });       

    } else if (type == ("trips")){
        new DataTable(`#${type}`, {
            layout: {
                topStart: {
                    buttons: [
                        {
                          extend: 'excelHtml5',
                          text: '<i class="fas fa-file-excel"></i>',
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
            columnDefs: [
                { orderable: false, targets: -1 },
                { visible: false, targets: [2, 9, 10, 11, 12, 13, 14, 15]}
            ],
            language: {
                url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
            },
        });
    } else {
        new DataTable(`#${type}`, {
            layout: {
                topStart: {
                    buttons: [
                        {
                          extend: 'excelHtml5',
                          text: '<i class="fas fa-file-excel"></i>',
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

    const new_entry_from_trip = document.querySelectorAll('.creating-entry-from-trip');
    if (new_entry_from_trip) {
        new_entry_from_trip.forEach((item) => {
            $(item).on('shown.bs.modal', function() {
                let user_id_string = item.id.match(/\d+/);
                let user_id = parseInt(user_id_string[0]);
                let trips = []
                let trip_id;
                fetch(`/trips/json`)
                .then(response => response.json())
                .then(list => {
                    list.forEach(element => {
                        if (element.creation_user_id === user_id) {
                            trips.push(element.id);
                        };
                    });
                    trip_id = trips[0];
                    document.getElementById(`link-create-entry${user_id}`).setAttribute("href", `/create_entry/${trip_id}`);
                });
            })
        });
    };

    const edit_entry_when_creating = document.querySelectorAll('.editing-entry');
    if (edit_entry_when_creating) {
        edit_entry_when_creating.forEach((item) => {
            $(item).on('shown.bs.modal', function() {
                let user_id_string = item.id.match(/\d+/);
                let user_id = parseInt(user_id_string[0]);
                fetch(`/entries/json/last_entry`)
                .then(response => response.json())
                .then(element => {
                    const entry_id = element.id;
                    document.getElementById(`link-edit-entry${user_id}`).setAttribute("href", `/modify_entry/${entry_id}`);
                });
            })
        });
    };
    const my_pendings = document.getElementById('my-pendings');
    if (my_pendings) {
        const my_pendings_modal = new bootstrap.Modal(my_pendings);
        const close_my_pendings = document.getElementById('close-my-pendings');
        close_my_pendings.addEventListener('click', () => {
            my_pendings_modal.hide();
        });
    };
}

function create_entry_from_pendings() {
    const trip_entry = document.getElementById('trip_entry');
    if (trip_entry != null) {
        trip_entry.addEventListener('change', function() {
            const selectedValue = this.value;
            document.getElementById('new-entries-link').setAttribute("href", `/create_entry/${selectedValue}`);
        });
    };
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

function user_filter_functionality() {
    const user_filter_select = document.getElementById('user_filter_select');
    if (user_filter_select != null) {
        user_filter_select.addEventListener('change', function() {
            const selectedValue = this.value;
            let entries = $('#entries').DataTable();
            entries.column(9).search(selectedValue).draw();
        });
    };
}

function deleting_functionality(type) {
    const all_delete_btns = document.querySelectorAll(`.delete-${type}-btn`);
    if (all_delete_btns != null) {
        all_delete_btns.forEach((item) => {
            if (item != null) {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                item.addEventListener('click', () => {

                    // Gets the item id
                    const id_string = item.id.match(/\d+/);
                    const id = parseInt(id_string[0]);

                    // Gets the complete row
                    const row = document.getElementById(`row-${type}-${id}`);
                    
                    // Makes the request to the server to delete
                    fetch(`${type}/json/${id}`, {
                        method: 'DELETE',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                    })
                    .then(response => response.json)

                    // Close the modal
                    .then(document.getElementById(`btn-close-${type}-${id}`).click())

                    // Start animation and remove row
                    .then(row.classList.add('row-delete'))
                    .then(row.onanimationend = () => {
                        row.remove();
                    });
                });
            };
        });
    }    
}


function display_entries(trip_id) {

    fetch(`/entries_trip/json/${trip_id}`)
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
        head.innerHTML = '<th>Fecha Pedido</th><th>Fecha Respuesta</th><th>Status</th><th>Versión</th><th>Monto</th><th>Trabajado por</th><th>Progreso</th><th>Valoración</th><th>Acciones</th>';
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
    const user_working = document.createElement("td");
    const progress = document.createElement("td");
    const importance = document.createElement("td");
    const actions = document.createElement("td");


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

    if (element.isClosed == false) {
        closing_date.innerHTML = 'n/a';
    } else {
        closing_date.innerHTML = `${element.closing_date}`;
    };
    
    status.innerHTML = `${element.status}`;
    user_working.innerHTML = `${element.user_working}`;
    progress.innerHTML = `${element.progress}`;
    importance.innerHTML = `${element.importance}`;
    
    const pencil = document.createElement("i");
    const link_pencil = document.createElement("a");

    pencil.className = 'fa-solid fa-pencil align-top'
    link_pencil.setAttribute("href", `/modify_entry/${element.id}`);
    link_pencil.setAttribute("id", 'pencil-edit-entry');

    link_pencil.appendChild(pencil);
    actions.appendChild(link_pencil);


    entry_row.appendChild(starting_date);
    entry_row.appendChild(closing_date);
    entry_row.appendChild(status);
    entry_row.appendChild(version);
    entry_row.appendChild(amount);
    entry_row.appendChild(user_working);
    entry_row.appendChild(progress);
    entry_row.appendChild(importance);
    entry_row.appendChild(actions);
    
    return entry_row;
}


function create_json_element_by_type(type, item, id) {
    let data;
    let values = [];
    let keys = [];

    if (type == "countries") {
        // Creates the json with the data from the inputs
        for (let key in item) {
            if (item.hasOwnProperty(key)) {
                if (key != 'id') {

                    const td_content = document.querySelector(`#value-${type}-${key}-${id}`).value;
                    values.push(td_content);
                    keys.push(key);
                }
            };
        };
    
        data = {
            id: id,
            [keys[0]]: `${values[0]}`,
            [keys[1]]: `${values[1]}`,
        };
    } else if(type == "clients") {
        
        for (let key in item) {
            if (item.hasOwnProperty(key)) {
                if (key != 'id') {
                    if(key == 'name') {
                        const input_content = document.querySelector(`#value-${type}-${key}-${id}`).value;
                        values.push(input_content);
                        keys.push(key);
                    } else {
                        const select = document.querySelector(`#value-${type}-${key}-${id}`);

                        // Gets the option selected of the list and pushes the value
                        const index = select.selectedIndex;
                        const selectedOption = select.options[index];
                        values.push(selectedOption.value);
                        keys.push(key);                        
                    };
                };
            };
        };
        data = {
            id: id,
            [keys[0]]: `${values[0]}`,
            [keys[1]]: `${values[1]}`,
            [keys[2]]: `${values[2]}`,
            [keys[3]]: `${values[3]}`,
        };
    } else if(type == "contacts") {
        
        for (let key in item) {
            if (item.hasOwnProperty(key)) {
                if (key != 'id') {
                    if(key == 'name') {
                        const input_content = document.querySelector(`#value-${type}-${key}-${id}`).value;
                        values.push(input_content);
                        keys.push(key);
                    } else if(key == 'email') {
                        const input_content = document.querySelector(`#value-${type}-${key}-${id}`).value;
                        values.push(input_content);
                        keys.push(key);
                    } else {
                        const select = document.querySelector(`#value-${type}-${key}-${id}`);

                        // Gets the option selected of the list and pushes the value
                        const index = select.selectedIndex;
                        const selectedOption = select.options[index];
                        values.push(selectedOption.value);
                        keys.push(key);                        
                    };
                };
            };
        };
        data = {
            id: id,
            [keys[0]]: `${values[0]}`,
            [keys[1]]: `${values[1]}`,
            [keys[2]]: `${values[2]}`,
            [keys[3]]: `${values[3]}`,
        };
    };
    return data
}


function create_chart(id) {
    let data;
    
    fetch(`/entries/json/pendings`)
    .then(response => response.json())
    .then(list => {
        data = [];
        let labels = [];
        let quotes = [];
        let bookings = [];
        let finals = [];
        let others = [];
        let row_order = 0;
        list.forEach(row => {
            let order = 0;
            row.forEach(element => {
                if (row_order != 0) {
                    if (order == 0) {
                        labels.push(element);
                    } else if (order == 1) {
                        quotes.push(element);
                    } else if (order == 2) {
                        bookings.push(element);
                    } else if (order == 3) {
                        finals.push(element);
                    } else {
                        others.push(element);
                    };
                    order++;
                } else {
                    order++;
                };
            });
            row_order++;
        });
        data.push(labels, quotes, bookings, finals, others);

        const ctx = document.getElementById(id);
        Chart.defaults.font.size = 8;
        if (ctx != null) {
            new Chart(ctx, {
                type: 'bar',
                data: {
                labels: labels,
                datasets: [{
                    label: 'Quotes',
                    data: quotes,
                    borderWidth: 1    
                },
                {
                    label: 'Bookings',
                    data: bookings,
                    borderWidth: 1
                },
                {
                    label: 'Final Itinerary',
                    data: finals,
                    borderWidth: 1
                },
                {
                    label: 'Otros',
                    data: others,
                    borderWidth: 1
                }]
                },
                options: {
                indexAxis: 'y',
                elements: {
                    bar: {
                        borderWidth: 2,
                    }
                },
                responsive: true,
                plugins: {
                    legend: {
                    position: 'right',
                    }
                }
                }
            });
        };    
    });
}