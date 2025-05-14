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
    btn_display("user");

    // Creates the functionality when pressing the eye
    eye_functionality();

    // Creates the listeners when opening and closing modals
    modal_functionality();

    // Creates the listeners when selecting the user when creating entry
    user_working_functionality();

    // Creates the listeners when clicking the plus button
    //plus_btn_functionality();

    // Creates the listeners for deleting elements
    deleting_functionality("countries");
    deleting_functionality("clients");
    deleting_functionality("contacts");
    deleting_functionality("users");
    deleting_functionality("trips");
    deleting_functionality("entries");

    // Creates the listeners for modifying elements
    modifying_functionality("countries");
    modifying_functionality("clients");
    modifying_functionality("contacts");

    create_chart("pendings_chart");

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

function plus_btn_functionality() {
    //const plus_btn = document.getElementById('new_trip_plus');
    //const new_trip_btn = document.getElementById('new_trip_btn');

    //plus_btn.addEventListener('click', () => {
    //    window.location = '../trips';
    //    document.addEventListener('DOMContentLoaded', function() {
    //        btn_display("trip");
    //    });
    //});

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
                let trip_id_string = item.id.match(/\d+/);
                let trip_id = parseInt(trip_id_string[0]);
                let entries = []
                let entry_id;
                fetch(`/entries/json`)
                .then(response => response.json())
                .then(list => {
                    list.forEach(element => {
                        if (element.trip_id === trip_id) {
                            entries.push(element.id);
                        };
                    });
                    console.log(entries);
                    entry_id = entries[0];
                    console.log(entries[0]);
                    console.log(trip_id);
                    console.log(entry_id);
                    document.getElementById(`link-edit-entry${trip_id}`).setAttribute("href", `/modify_entry/${entry_id}`);
                });
            })
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

function deleting_functionality(type) {
    const all_delete_btns = document.querySelectorAll(`.delete-${type}-btn`);
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

function modifying_functionality(type) {
    const all_pencil_btns = document.querySelectorAll(`.pencil-${type}`);
    all_pencil_btns.forEach((item) => {
        if (item != null) {

            item.addEventListener('click', () => {

                // Gets the item id
                const id_string = item.id.match(/\d+/);
                const id = parseInt(id_string[0]);

                // Gets the save button, pencil and trash for this type and id
                const save_btn = document.querySelector(`#save-btn-${type}-${id}`);
                const pencil = document.querySelector(`#pencil-${type}-${id}`);
                const trash = document.querySelector(`#trash-${type}-${id}`);

                // Hides pencial and trash and shows the save button
                pencil.classList.add('d-none');
                trash.classList.add('d-none');
                save_btn.classList.remove('d-none');

                // Get the current information and the keys
                fetch(`/${type}/json/${id}`)
                .then(response => response.json())
                .then(item => {
                    for (let key in item) {
                        if (item.hasOwnProperty(key)) {
                            if (key != 'id') {

                                // Uses the current info to create the input to edit
                                input_specifications_by_type(type, item, key, id);
                            };
                        };
                    };
                    modify_item(type, item, id, pencil, trash);
                })
            });
        };
    });
}

function input_specifications_by_type(type, item, key, id) {
    const td = document.getElementById(`${type}-${key}-${id}`);
    if (type == "countries") {
        if (key == "code") {
            td.innerHTML = `<input type="text" minlength="2" maxlength="2" id="value-${type}-${key}-${id}" value="${item[key]}">`;
        } else {
            td.innerHTML = `<input type="text" id="value-${type}-${key}-${id}" value="${item[key]}">`;
        };
        
    } else if (type == "clients") {
        if (key == "country") {
            const original_text = td.innerHTML;
            td.innerHTML = `<select id="value-${type}-${key}-${id}">`;
            const select = document.querySelector(`#value-${type}-${key}-${id}`);

            fetch(`/countries/json`)
            .then(response => response.json())
            .then(list => {
                list.forEach(element => {
                    if (element.name == original_text) {
                        const current_option = document.createElement('option');
                        current_option.text = `${element.name}`;
                        current_option.defaultSelected = true;
                        current_option.value = `${element.id}`;
                        select.appendChild(current_option);
                    } else {
                        const option = document.createElement('option');
                        option.value = `${element.id}`;
                        option.text = `${element.code} - ${element.name}`;
                        select.appendChild(option);
                    };
                    
                });
            });
        } else if (key == "department") {
            td.innerHTML = `<select id="value-${type}-${key}-${id}">`;
            const select = document.querySelector(`#value-${type}-${key}-${id}`);
            const current_option = document.createElement('option');
            const option = document.createElement('option');

            if (item[key] == "AI") {
                current_option.text = "AI";
                current_option.value = "AI";
                current_option.defaultSelected = true;
                option.text = "SH";
                option.value = "SH";
            } else {
                current_option.text = "SH";
                current_option.value = "SH";
                option.text = "AI";
                option.value = "AI";
                
            };
            select.appendChild(current_option);
            select.appendChild(option);
            
        } else if (key == "isActivated") {
            boolean_options (td, type, item, key, id);

        } else {
            td.innerHTML = `<input type="text" id="value-${type}-${key}-${id}" value="${item[key]}">`;
        };
    } else if (type == "contacts") {
        if (key == "client") {
            const original_text = td.innerHTML;
            td.innerHTML = `<select id="value-${type}-${key}-${id}">`;
            const select = document.querySelector(`#value-${type}-${key}-${id}`);

            fetch(`/clients/json`)
            .then(response => response.json())
            .then(list => {
                list.forEach(element => {
                    if (element.name == original_text) {
                        const current_option = document.createElement('option');
                        current_option.text = `${element.name}`;
                        current_option.defaultSelected = true;
                        current_option.value = `${element.id}`;
                        select.appendChild(current_option);
                    } else {
                        const option = document.createElement('option');
                        option.value = `${element.id}`;
                        option.text = `${element.name}`;
                        select.appendChild(option);
                    };
                });
            });
        } else if (key == "isActivated") {
            boolean_options (td, type, item, key, id);
        } else if (key == "email") {
            td.innerHTML = `<input type="email" id="value-${type}-${key}-${id}" value="${item[key]}">`;
        } else if (key == "name") {
            td.innerHTML = `<input type="text" id="value-${type}-${key}-${id}" value="${item[key]}">`;
        };
    };
}

function boolean_options (td, type, item, key, id) {
    td.innerHTML = `<select id="value-${type}-${key}-${id}">`;
    const select = document.querySelector(`#value-${type}-${key}-${id}`);
    const current_option = document.createElement('option');
    const option = document.createElement('option');

    if (item[key] == "True") {
        current_option.text = "Sí";
        current_option.value = "True";
        current_option.defaultSelected = true;
        option.text = "No";
        option.value = "False";
    } else {
        current_option.text = "No";
        current_option.value = "False";
        current_option.defaultSelected = true;
        option.text = "Sí";
        option.value = "True";
        
    };
    select.appendChild(current_option);
    select.appendChild(option);
}

function modify_item(type, item, id, pencil, trash) {
    const save_btn = document.getElementById(`save-btn-${type}-${id}`);
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  
    save_btn.addEventListener('click', () => {

        const data = create_json_element_by_type(type, item, id);

        console.log(data);

        // Update information in the server
        fetch(`/${type}/json/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
        });

        // Update HTML new content
        for (let key in item) {
            if (item.hasOwnProperty(key)) {
                if (key != 'id') {
                    const td = document.getElementById(`${type}-${key}-${id}`);
                    const td_content = document.querySelector(`#value-${type}-${key}-${id}`);
                    if (td_content.tagName === "SELECT") {
                        const value = td_content.options[td_content.selectedIndex].text;
                        td.innerHTML = value;
                    } else {
                        td.innerHTML = td_content.value;
                    };
                };
            };
        };

        // Hides input and save button and display pencil and trash again
        save_btn.classList.add('d-none');
        pencil.classList.remove('d-none');
        trash.classList.remove('d-none');
    });

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
        head.innerHTML = '<th>Fecha Pedido</th><th>Fecha Respuesta</th><th>Status</th><th>Versión</th><th>Monto</th><th>Trabajado por</th><th>Progreso</th><th>Valoración</th>';
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
    //const user_creator = document.createElement("td");
    const user_working = document.createElement("td");
    const progress = document.createElement("td");
    const importance = document.createElement("td");
    //const actions = document.createElement("td");

    
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

    if (element.starting_date == element.closing_date) {
        closing_date.innerHTML = 'n/a';
    } else {
        closing_date.innerHTML = `${element.closing_date}`;
    };
    
    status.innerHTML = `${element.status}`;
    //user_creator.innerHTML = `${element.user_creator}`;
    user_working.innerHTML = `${element.user_creator}`;
    progress.innerHTML = `${element.progress}`;
    importance.innerHTML = `${element.importance}`;


    entry_row.appendChild(starting_date);
    entry_row.appendChild(closing_date);
    entry_row.appendChild(status);
    entry_row.appendChild(version);
    entry_row.appendChild(amount);
    //entry_row.appendChild(user_creator);
    entry_row.appendChild(user_working);
    entry_row.appendChild(progress);
    entry_row.appendChild(importance);
    
    return entry_row;
}

function create_chart(id) {
    const ctx = document.getElementById(id);
    if (ctx != null) {
        new Chart(ctx, {
            type: 'bar',
            data: {
              //labels: users_labels.map(row => row),
              labels: ['DC', 'LP', 'MLV', 'AA', 'LT', 'PA'],
              datasets: [{
                label: 'Quotes',
                //data: data.map(row => row[1]),
                data: ['1', '3', '5', '3', '0', '4'],
                borderWidth: 1    
              },
              {
                  label: 'Bookings',
                  //data: data.map(row => row[1]),
                  data: ['3', '0', '1', '1', '2', '0'],
                  borderWidth: 1
              },
              {
                  label: 'Otros',
                  //data: data.map(row => row[1]),
                  data: ['0', '1', '2', '0', '4', '5'],
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
}

function get_data() {
    // Creates the empty tables
    var users_labels = [];
    var data = [];
    var columns = [];
    var values = [];

    fetch(`/entries/json`)
    .then(response => response.json())
    .then(list => {

        // Creates all the rows
        if (Array.isArray(list)) {
            list.forEach(element => {
                if (element.isClosed === "false") {
                    let column = 0;
                    let user_label = 0;
                    if (element.status === "Quote" || element.status === "Booking" || element.status === "Final Itinerary") {
                        const isInColumn = look_label(columns, element.status);
                        if (isInColumn === false) {
                            columns.push(element.status);
                            column = column + 1;
                        };
                        const isInUserLabels = look_label(users_labels, element.user_working);
                        if (isInUserLabels === false) {
                            users_labels.push(element.user_working);
                            user_label = user_label + 1;
                        };
                    } else {
                        const isInColumn = look_label(columns, "Otros");
                        if (isInColumn === false) {
                            columns.push("Otros");
                            column = column + 1;
                        };
                        const isInUserLabels = look_label(users_labels, element.user_working);
                        if (isInUserLabels === false) {
                            users_labels.push(element.user_working);
                            user_label = user_label + 1;
                        };
                    };
                };
            });
        };
    });
}

function look_label(list, label) {
    if (list) {
        list.forEach(i => {
            if (list[i] === label) {
                return true
            };
        });
        return false
    } else {
        return false
    };
}