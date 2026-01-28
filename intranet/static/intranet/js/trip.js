function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function getCSRFToken() {
    return getCookie("csrftoken");
}

document.addEventListener('DOMContentLoaded', () => {

    // Modifies the date format to be shown in the forms
    modify_date_and_datetime();

    // Display forms when clicking button
    btn_display("trip");
    btn_display("entry");
    btn_display("user");
    btn_display("location");
    btn_display("supplier");

    // Creates the listeners when opening and closing modals
    modal_functionality();

    // Creates the listeners when selecting the user when creating entry and filtering
    user_working_functionality();

    // Creates listener when selecting location in suppliers
    suppliers_location_functionality();

    // Creates listener when selecting product in ratelines
    lines_product_functionality();

    // Creates entry at the pendings page
    create_entry_from_pendings();

    editing_blocks();

    // Creates the listeners for deleting elements
    deleting_functionality("countries");
    deleting_functionality("clients");
    deleting_functionality("contacts");
    deleting_functionality("users");
    deleting_functionality("trips");
    deleting_functionality("entries");
    deleting_functionality("location");
    deleting_functionality("supplier-group");
    deleting_functionality("product-group");
    deleting_functionality("supplier");

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
    create_datatable("group_suppliers");
    create_datatable("group_products");
    create_datatable("locations");
    create_datatable("supplier");


    init_entry_edit_modal();
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
        let showAll = 0;
        let userFilter = "";
        let entriesTable = $('#entries').DataTable({
            processing: true,
            serverSide: true,
            ajax: {
                url: "/entries/data/",
                type: "GET",
                data: function (d) {
                    d.show_all = showAll;  // 👈 por defecto solo abiertas
                    d.user_filter = userFilter;
                }
            },
            columns: [
                { data: "starting_date" },
                { data: "closing_date" },
                { data: "trip" },
                { data: "status" },
                { data: "amount" },
                { data: "client" },
                { data: "contact" },
                { data: "client_reference" },
                { data: "user_creator" },
                { data: "user_working" },
                { data: "progress" },
                { data: "importance" },
                { data: "note" },
                { data: "travelling_date" },
                { data: "acciones", orderable: false }
            ],
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
                { visible: false, targets: [4, 7, 11, 12]}
            ],
            order: [[0, "desc"]],
              // callback que corre cada vez que DataTables crea un <tr>
            createdRow: function(row, data) {
                try {
                // data.id debe venir en el JSON (asegurate que tu entries_data incluya "id")
                row.id = `row-entries-${data.id}`;
                row.dataset.entryId = data.id;
                } catch (e) { console.warn("createdRow error", e); }
            },
            language: {
                url: "https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json"
            }
        });

        // Creates the functionality when pressing the eye
        const $eye = $("#pending-eye");
        // inicial: asegurar icono 'eye-slash' si showAll == 0
        if (showAll === 0) {
            $eye.removeClass("fa-eye").addClass("fa-eye-slash");
        } else {
            $eye.removeClass("fa-eye-slash").addClass("fa-eye");
        }

        $eye.on("click", function () {
            showAll = showAll === 0 ? 1 : 0;
            // cambio de ícono
            if (showAll === 1) {
                $eye.removeClass("fa-eye-slash").addClass("fa-eye");
            } else {
                $eye.removeClass("fa-eye").addClass("fa-eye-slash");
            }
            // recargo la tabla (manteniendo la página actual)
            entriesTable.ajax.reload(null, false);
        });

        $("#user_filter_select").on("change", function () {
            userFilter = $(this).val() || "";
            entriesTable.ajax.reload();
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

    // Get the trip form
    const tripForm = document.getElementById('trip-form');
    
    // Verificar que el formulario existe antes de continuar
    if (!tripForm) {
        console.log('Formulario de viaje no encontrado en esta página');
        return;
    }
    
    const submitButton = tripForm.querySelector('#save-new-trip');
    
    if (tripForm && submitButton) {
        // Remover el data-bs-toggle del HTML y manejarlo con JavaScript
        submitButton.removeAttribute('data-bs-toggle');
        submitButton.removeAttribute('data-bs-target');
        
        tripForm.addEventListener('submit', async function(e) {
            e.preventDefault(); // Prevenir submit normal
            
            // Deshabilitar botón y mostrar loading
            const originalText = submitButton.value;
            submitButton.value = 'GUARDANDO...';
            submitButton.disabled = true;
            
            try {
                // Crear FormData con los datos del formulario
                const formData = new FormData(tripForm);
                
                // Enviar request AJAX
                const response = await fetch(tripForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest', // Indicar que es AJAX
                    }
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Viaje creado exitosamente
                    const userId = result.user_id;
                    const tripId = result.trip_id;
                    
                    // Actualizar el enlace del modal con el ID del viaje recién creado
                    const linkElement = document.getElementById(`link-create-entry${userId}`);
                    if (linkElement) {
                        linkElement.setAttribute('href', `/create_entry/${tripId}`);
                    }
                    
                    // Ahora sí abrir el modal
                    const modal = new bootstrap.Modal(document.getElementById(`windowCreateEntry${userId}`));
                    modal.show();
                    
                } else {
                    // Mostrar errores de validación
                    if (result.errors) {
                        let errorMessage = 'Errores en el formulario:\n';
                        for (const [field, errors] of Object.entries(result.errors)) {
                            errorMessage += `${field}: ${errors.join(', ')}\n`;
                        }
                        alert(errorMessage);
                    } else {
                        alert(result.message || 'Error al crear el viaje');
                    }
                }
                
            } catch (error) {
                console.error('Error:', error);
                alert('Error de conexión. Por favor, intenta nuevamente.');
            } finally {
                // Rehabilitar botón
                submitButton.value = originalText;
                submitButton.disabled = false;
            }
        });
    }
    
    // Código para manejar el modal (ya no necesario el polling)
    const new_entry_from_trip = document.querySelectorAll('.creating-entry-from-trip');
    if (new_entry_from_trip) {
        new_entry_from_trip.forEach((item) => {
            $(item).on('shown.bs.modal', function() {
                // El enlace ya está configurado correctamente antes de abrir el modal
                console.log('Modal abierto con enlace ya configurado');
            });
        });
    }

    const my_pendings = document.getElementById('my-pendings');
    if (my_pendings) {
        const my_pendings_modal = new bootstrap.Modal(my_pendings);
        const close_my_pendings = document.getElementById('close-my-pendings');
        close_my_pendings.addEventListener('click', () => {
            my_pendings_modal.hide();
        });
    };
}

function init_entry_edit_modal() {
    const entryForm = document.querySelector('#modify_entry form');
    if (!entryForm) {
        console.log('[edit-entry] formulario #modify_entry no encontrado en esta página (no aplica)');
        return;
    }

    const submitButton = entryForm.querySelector('#save-new-entry');
    if (!submitButton) return;

    submitButton.removeAttribute('data-bs-toggle');
    submitButton.removeAttribute('data-bs-target');

    entryForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const originalText = submitButton.value;
        submitButton.value = 'GUARDANDO...';
        submitButton.disabled = true;

        try {
            const formData = new FormData(entryForm);
            const response = await fetch(entryForm.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (!response.ok) {
                alert('Error del servidor al crear la entrada');
                return;
            }

            const result = await response.json();
            console.log('[edit-entry] respuesta recibida:', result);

            if (result.success) {
                const userId = result.user_id;
                const entryId = result.entry_id;

                const link = document.getElementById(`link-edit-entry${userId}`);
                if (link) link.setAttribute('href', `/modify_entry/${entryId}`);

                const modalEl = document.getElementById(`windowEditEntry${userId}`);
                if (modalEl) {
                    const modal = new bootstrap.Modal(modalEl);
                    modal.show();
                }
            } else {
                alert('Error: no se pudo crear la entrada.');
                console.error(result);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error de red. Intenta nuevamente.');
        } finally {
            submitButton.value = originalText;
            submitButton.disabled = false;
        }
    });
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

function eye_functionality(entriesTable) {
    let showAll = 0;  // 0 = solo abiertas, 1 = todas

    $("#pending-eye").on("click", function() {
        // alternar estado
        showAll = showAll === 0 ? 1 : 0;

        // cambiar icono
        if (showAll === 1) {
            $(this).removeClass("fa-eye-slash").addClass("fa-eye");
        } else {
            $(this).removeClass("fa-eye").addClass("fa-eye-slash");
        }

        // actualizar el parámetro y recargar
        entriesTable.ajax.params = function (d) {
            d.show_all = showAll;
        };
        entriesTable.ajax.reload();
    });
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
    let csrfToken;
    const csrfTokenObj = document.querySelector('[name=csrfmiddlewaretoken]')
    if (csrfTokenObj) {
        csrfToken = csrfTokenObj.value;
    };

    document.addEventListener("click", (e) => {
        const btn = e.target.closest(`.delete-${type}-btn`);
        if (!btn) return; // no es botón de delete

        const id_string = btn.id.match(/\d+/);
        const id = parseInt(id_string[0]);
        console.log("Deleting", type, id);

        const row = document.getElementById(`row-${type}-${id}`);

        if (type === "supplier-group" || type === "location") {
            fetch(`${type}/json/${id}`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
            })
            .then(() => {
                // cerrar modal
                const closeBtn = document.getElementById(`btn-close-${type}-${id}`);
                if (closeBtn) closeBtn.click();

                // animar y eliminar fila
                if (row) {
                    row.classList.add("row-delete");
                    //row.onanimationend = () => row.remove();
                    row.remove();
                }
            })
            .catch(err => console.error("Error deleting:", err));
        } else {
            fetch(`${type}/json/${id}`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
            })
            .then(() => {
                // cerrar modal
                const closeBtn = document.getElementById(`btn-close-${type}-${id}`);
                if (closeBtn) closeBtn.click();

                // animar y eliminar fila
                if (row) {
                    row.classList.add("row-delete");
                    //row.onanimationend = () => row.remove();
                    row.remove();
                }
            })
            .catch(err => console.error("Error deleting:", err));
        };
    });
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

function create_entry_row(element) {
    
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

function suppliers_location_functionality() {
    
    const filter_select = document.getElementById("location_filter_select");

    if (filter_select) {
        filter_select.addEventListener("change", function () {
            const selectedLocation = this.value;
            const suppliers = document.querySelectorAll(".row-supplier");

            suppliers.forEach(option => {
                if (selectedLocation === "all") {
                    option.hidden = false;
                } else {
                    option.hidden = option.dataset.location !== selectedLocation;
                }
            });
        });
    }
}

function lines_product_functionality() {
    
    const filter = document.getElementById("product_filter_select");
    const rows = document.querySelectorAll(".row-rateline");

    if (!filter) return;

    function applyFilter() {
        const value = filter.value;

        rows.forEach(row => {
            if (value === "all") {
                row.hidden = false;
            } else {
                row.hidden = row.dataset.rateline !== value;
            }
        });
    }

    filter.addEventListener("change", applyFilter);

    // 👇 CLAVE: ejecutar al cargar
    applyFilter();
}

function editing_blocks() {
    document.querySelectorAll(".edit-block").forEach(button => {
        button.addEventListener("click", function () {
            const blockId = this.dataset.block;
            const isEditing = this.dataset.editing === "true";

            if (isEditing) {
                // GUARDAR
                const rows = document.querySelectorAll(
                    `.row-rateline[data-block="${blockId}"]`
                );
                saveBlock(blockId, rows, this);
            } else {
                // EDITAR
                const rows = document.querySelectorAll(
                    `.row-rateline[data-block="${blockId}"]`
                );
                
                rows.forEach(row => {
                    enableEdit(row);
                });

                // Cambiar el botón a modo "guardar"
                this.textContent = "Guardar bloque";
                this.classList.remove("btn-dark");
                this.classList.add("btn-success");
                this.dataset.editing = "true";
            }
        });
    });
}


function saveBlock(blockId, rows, button) {
    const data = [];

    rows.forEach(row => {
        row.querySelectorAll(".rate-cell").forEach(cell => {
            const input = cell.querySelector("input");
            if (!input) return;
            
            const rateId = cell.dataset.rate;
            
            // 👇 Validar que rate_id exista
            if (!rateId || rateId === "None" || rateId === "undefined") {
                console.warn("Celda sin rate_id válido", cell);
                return;
            }

            data.push({
                rate_id: rateId,
                field: cell.dataset.field,
                value: input.value
            });
        });
    });

    console.log("Datos a enviar:", data); // 👈 Debug

    fetch("/tariff/modify/update-rate-block/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            rates: data
        })
    })
    .then(r => r.json())
    .then(resp => {
        console.log("Respuesta:", resp); // 👈 Debug
        if (resp.ok) {
            restoreBlock(blockId, button);
        } else {
            alert("Error al guardar: " + (resp.error || "Desconocido"));
        }
    })
    .catch(err => {
        alert("Error de conexión");
        console.error(err);
    });
}

function restoreBlock(blockId, button) {
    const rows = document.querySelectorAll(
        `.row-rateline[data-block="${blockId}"]`
    );

    rows.forEach(row => {
        row.querySelectorAll(".rate-cell").forEach(cell => {
            const input = cell.querySelector("input");
            if (input) {
                cell.innerText = input.value || "N/A";
            }
        });
    });

    // Restaurar el botón
    button.innerText = "Editar bloque";
    button.classList.remove("btn-success");
    button.classList.add("btn-dark");
    button.dataset.editing = "false";
}

function enableEdit(row) {
    row.querySelectorAll(".rate-cell").forEach(cell => {
        // Evita convertir dos veces
        if (cell.querySelector("input")) return;

        const value = cell.innerText.trim() === "N/A" ? "" : cell.innerText.trim();
        const rateId = cell.dataset.rate;
        const field = cell.dataset.field;

        cell.innerHTML = `
            <input type="number"
                   step="0.01"
                   class="form-control form-control-sm"
                   value="${value}">
        `;
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}