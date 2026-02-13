// Variable global para trackear el bloque en edición
let currentEditingBlock = null;

// Al inicio del archivo, agregar variable global para rastrear vínculos
let linkedCostsByBlock = new Map(); // key: blockId, value: boolean

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
    copyBlocks();

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
                // Si ya hay otro bloque en edición, cancelarlo primero
                if (currentEditingBlock && currentEditingBlock !== blockId) {
                    cancelBlockEdit(currentEditingBlock);
                }
                
                // EDITAR
                currentEditingBlock = blockId;
                
                // Por defecto, costos están vinculados
                if (!linkedCostsByBlock.has(blockId)) {
                    linkedCostsByBlock.set(blockId, true);
                }
                
                const rows = document.querySelectorAll(
                    `.row-rateline[data-block="${blockId}"]`
                );
                
                // ✅ Crear toggle ANTES de habilitar edición
                createBlockCostToggle(blockId);
                
                rows.forEach(row => {
                    enableEdit(row, blockId);
                });

                // Mostrar input de season
                const seasonDisplay = document.querySelector(`.season-display[data-block="${blockId}"]`);
                const seasonInput = document.querySelector(`.season-input[data-block="${blockId}"]`);
                
                if (seasonDisplay && seasonInput) {
                    seasonInput.dataset.originalValue = seasonInput.value;
                    seasonDisplay.classList.add("d-none");
                    seasonInput.classList.remove("d-none");
                }

                // Cambiar el botón a modo "guardar"
                this.innerHTML = '<i class="fa-solid fa-save"></i>';
                this.classList.remove("btn-dark");
                this.classList.add("btn-success");
                this.dataset.editing = "true";
                
                // Mostrar botón cancelar
                const cancelBtn = document.querySelector(`.cancel-block[data-block="${blockId}"]`);
                if (cancelBtn) {
                    cancelBtn.classList.remove("d-none");
                }
                
                // Ocultar botón eliminar mientras edita
                const deleteBtn = document.querySelector(`.delete-block[data-block="${blockId}"]`);
                if (deleteBtn) {
                    deleteBtn.classList.add("d-none");
                }
                
                const marginDisplay = document.querySelector(`.margin-display[data-block="${blockId}"]`);
                const marginInput = document.querySelector(`.margin-input[data-block="${blockId}"]`);

                if (marginDisplay && marginInput) {
                    marginInput.dataset.originalValue = marginInput.value;
                    marginDisplay.classList.add("d-none");
                    marginInput.classList.remove("d-none");

                    // Escuchar cambios en el margen para actualizar ventas del bloque
                    marginInput.addEventListener('input', function() {
                        const newMargin = parseFloat(this.value) || 0;
                        const rows = document.querySelectorAll(`.row-rateline[data-block="${blockId}"]`);
                        
                        rows.forEach(row => {
                            // Actualizar SGL y DBL con el nuevo margen global del bloque
                            ['SGL', 'DBL', 'one', 'two'].forEach(type => {
                                const costInput = row.querySelector(`.rate-input[data-field="cost"][data-rate-type="${type}"]`);
                                if (costInput) {
                                    const costValue = parseFloat(costInput.value) || 0;
                                    // Llamamos a la función de cálculo (ver paso 2)
                                    updateSellPriceFromMargin(row, type, costValue, newMargin);
                                }
                            });
                        });
                    });
                }
            }
        });
    });

}

// ✅ Nueva función para crear el toggle a nivel de bloque
function createBlockCostToggle(blockId) {
    // Buscar el header del bloque
    const blockHeader = document.querySelector(`tr.table-secondary td[colspan="11"]`);
    
    if (!blockHeader) return;
    
    // Verificar si ya existe el toggle
    if (document.getElementById(`linkCostBlock_${blockId}`)) return;
    
    const toggleContainer = document.createElement('div');
    toggleContainer.className = 'cost-link-toggle-block d-inline-flex ms-3';
    toggleContainer.innerHTML = `
        <div class="form-check form-switch d-inline-flex align-items-center" style="font-size: 0.875rem;">
            <input class="form-check-input me-2" type="checkbox" 
                   id="linkCostBlock_${blockId}" 
                   ${linkedCostsByBlock.get(blockId) ? 'checked' : ''}>
            <label class="form-check-label text-info fw-bold" for="linkCostBlock_${blockId}">
                <i class="fa-solid fa-link"></i> Vincular costos SGL/DBL
            </label>
        </div>
    `;
    
    // Insertar después del botón de copiar
    const copyBtn = blockHeader.querySelector('.copy-block');
    if (copyBtn) {
        copyBtn.parentElement.appendChild(toggleContainer);
    } else {
        blockHeader.querySelector('.d-flex').appendChild(toggleContainer);
    }
    
    // Event listener para el toggle
    const toggleInput = toggleContainer.querySelector('input');
    toggleInput.addEventListener('change', function() {
        linkedCostsByBlock.set(blockId, this.checked);
        
        if (this.checked) {
            // Sincronizar todos los costos del bloque
            syncAllCostsInBlock(blockId);
        }
    });
}

// ✅ Función para sincronizar todos los costos cuando se activa el toggle
function syncAllCostsInBlock(blockId) {
    const rows = document.querySelectorAll(`.row-rateline[data-block="${blockId}"]`);
    
    rows.forEach(row => {
        const sglCostInput = row.querySelector('.rate-input[data-field="cost"][data-rate-type="SGL"]');
        const dblCostInput = row.querySelector('.rate-input[data-field="cost"][data-rate-type="DBL"]');
        
        if (sglCostInput && dblCostInput) {
            dblCostInput.value = sglCostInput.value;
            // Disparar evento para recalcular venta
            dblCostInput.dispatchEvent(new Event('input'));
        }
    });
}

function copyBlocks() {
    document.querySelectorAll(".copy-block").forEach(button => {
        button.addEventListener("click", function(e) {
            e.stopPropagation();
            const blockId = this.dataset.block;
            const dateFrom = this.dataset.from;
            const dateTo = this.dataset.to;
            
            // Calcular diferencia de días del bloque original
            const originalFrom = new Date(dateFrom);
            const originalTo = new Date(dateTo);
            const diffDays = Math.ceil((originalTo - originalFrom) / (1000 * 60 * 60 * 24));
            
            // Calcular nuevas fechas sugeridas (un día después del date_to original)
            const suggestedFrom = new Date(originalTo);
            suggestedFrom.setDate(suggestedFrom.getDate() + 1);
            
            const suggestedTo = new Date(suggestedFrom);
            suggestedTo.setDate(suggestedTo.getDate() + diffDays);
            
            // Formatear fechas para input type="date" (YYYY-MM-DD)
            const formatDate = (date) => {
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            };
            
            const suggestedFromStr = formatDate(suggestedFrom);
            const suggestedToStr = formatDate(suggestedTo);
            
            console.log("Fechas sugeridas:", {
                original: { from: dateFrom, to: dateTo },
                diffDays: diffDays,
                suggested: { from: suggestedFromStr, to: suggestedToStr }
            });
            
            // Mostrar modal para ingresar nuevas fechas
            const modal = document.createElement('div');
            modal.innerHTML = `
                <div class="modal fade" id="copyBlockModal${blockId}" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Copiar Bloque de Tarifas</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="alert alert-info">
                                    <small>
                                        <i class="fa-solid fa-info-circle"></i>
                                        Bloque original: <strong>${dateFrom}</strong> a <strong>${dateTo}</strong> (${diffDays} días)
                                    </small>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Fecha Desde</label>
                                    <input type="date" 
                                        class="form-control" 
                                        id="newDateFrom${blockId}" 
                                        value="${suggestedFromStr}"
                                        required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Fecha Hasta</label>
                                    <input type="date" 
                                        class="form-control" 
                                        id="newDateTo${blockId}" 
                                        value="${suggestedToStr}"
                                        required>
                                    <small class="text-muted">Duración sugerida: ${diffDays} días</small>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Nombre Vigencia</label>
                                    <input type="text" 
                                        class="form-control" 
                                        id="newSeason${blockId}" 
                                        value="${this.dataset.season}" 
                                        required>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                                <button type="button" class="btn btn-primary" onclick="confirmCopyBlock('${blockId}')">
                                    <i class="fa-solid fa-copy"></i> Copiar Bloque
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const modalInstance = new bootstrap.Modal(document.getElementById(`copyBlockModal${blockId}`));
            modalInstance.show();
            
            // Auto-ajustar fecha_to cuando cambia fecha_from
            const newDateFromInput = document.getElementById(`newDateFrom${blockId}`);
            const newDateToInput = document.getElementById(`newDateTo${blockId}`);
            
            newDateFromInput.addEventListener('change', function() {
                const selectedFrom = new Date(this.value);
                const calculatedTo = new Date(selectedFrom);
                calculatedTo.setDate(calculatedTo.getDate() + diffDays);
                newDateToInput.value = formatDate(calculatedTo);
            });
            
            newDateToInput.addEventListener('change', function() {
                const selectedFrom = new Date(newDateFromInput.value);
                const selectedTo = new Date(this.value);
                const actualDiff = Math.ceil((selectedTo - selectedFrom) / (1000 * 60 * 60 * 24));
                
                // Mostrar advertencia si la duración es diferente
                const existingWarning = document.getElementById(`durationWarning${blockId}`);
                if (existingWarning) {
                    existingWarning.remove();
                }
                
                if (actualDiff !== diffDays) {
                    const warning = document.createElement('div');
                    warning.id = `durationWarning${blockId}`;
                    warning.className = 'alert alert-warning mt-2';
                    warning.innerHTML = `
                        <small>
                            <i class="fa-solid fa-exclamation-triangle"></i>
                            La duración es de <strong>${actualDiff} días</strong>, diferente a los <strong>${diffDays} días</strong> del bloque original.
                        </small>
                    `;
                    this.parentElement.appendChild(warning);
                }
            });

            // Limpiar modal al cerrar
            document.getElementById(`copyBlockModal${blockId}`).addEventListener('hidden.bs.modal', function () {
                modal.remove();
            });
        });
    });
}


function saveBlock(blockId, rows, button) {
    const rateData = [];
    const groupData = [];

    rows.forEach(row => {
        // Recolectar datos de rates
        row.querySelectorAll(".rate-cell").forEach(cell => {
            const input = cell.querySelector("input");
            if (!input) return;
            
            const rateId = cell.dataset.rate;
            
            if (!rateId || rateId === "None" || rateId === "undefined") {
                return;
            }

            rateData.push({
                rate_id: rateId,
                field: cell.dataset.field,
                value: input.value
            });
        });
        
        // ✅ Recolectar datos de grupos (nombre actualizado)
        const groupCell = row.querySelector(".group-cell");
        if (groupCell) {
            const groupInput = groupCell.querySelector(".group-name-input");
            const groupId = groupCell.dataset.groupId;
            
            if (groupInput && groupId) {
                const newGroupName = groupInput.value.trim();
                const originalGroupName = groupInput.dataset.originalValue;
                
                // Solo enviar si cambió
                if (newGroupName !== originalGroupName && newGroupName !== "") {
                    groupData.push({
                        group_id: groupId,
                        new_name: newGroupName
                    });
                }
            }
        }
    });
    
    // Obtener el nuevo valor de season
    const seasonInput = document.querySelector(`.season-input[data-block="${blockId}"]`);
    const newSeason = seasonInput ? seasonInput.value : null;

    fetch("/tariff/modify/update-rate-block/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            rates: rateData,
            groups: groupData,  // ✅ Enviar cambios de nombre de grupo
            season: newSeason,
            block_id: blockId
        })
    })
    .then(r => r.json())
    .then(resp => {
        if (resp.ok) {
            restoreBlock(blockId, button);
            alert(resp.message);
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
        // Restaurar celdas de rates
        row.querySelectorAll(".rate-cell").forEach(cell => {
            const input = cell.querySelector("input");
            if (input) {
                cell.innerText = input.value || "N/A";
            }
        });
        
        // ✅ Restaurar celda de grupo
        const groupCell = row.querySelector(".group-cell");
        if (groupCell) {
            const groupDisplay = groupCell.querySelector(".group-name-display");
            const groupInput = groupCell.querySelector(".group-name-input");
            
            if (groupDisplay && groupInput) {
                // Actualizar el display con el nuevo valor
                groupDisplay.textContent = groupInput.value;
                
                groupDisplay.classList.remove("d-none");
                groupInput.classList.add("d-none");
            }
        }
    });
    
    // Restaurar season display
    const seasonDisplay = document.querySelector(`.season-display[data-block="${blockId}"]`);
    const seasonInput = document.querySelector(`.season-input[data-block="${blockId}"]`);
    
    if (seasonDisplay && seasonInput) {
        seasonDisplay.textContent = seasonInput.value;
        seasonDisplay.classList.remove("d-none");
        seasonInput.classList.add("d-none");
    }

    // Restaurar el botón
    button.innerHTML = '<i class="fa-solid fa-pencil"></i>';
    button.classList.remove("btn-success");
    button.classList.add("btn-dark");
    button.dataset.editing = "false";
    
    // Ocultar botón cancelar
    const cancelBtn = document.querySelector(`.cancel-block[data-block="${blockId}"]`);
    if (cancelBtn) {
        cancelBtn.classList.add("d-none");
    }
    
    // Mostrar botón eliminar de nuevo
    const deleteBtn = document.querySelector(`.delete-block[data-block="${blockId}"]`);
    if (deleteBtn) {
        deleteBtn.classList.remove("d-none");
    }

    const marginDisplay = document.querySelector(`.margin-display[data-block="${blockId}"]`);
    const marginInput = document.querySelector(`.margin-input[data-block="${blockId}"]`);
    if (marginDisplay && marginInput) {
        marginDisplay.textContent = marginInput.value;
        marginDisplay.classList.remove("d-none");
        marginInput.classList.add("d-none");
    }
    
    // Limpiar variable global
    currentEditingBlock = null;
}

function enableEdit(row, blockId) {
    // Editar celdas de rates
    row.querySelectorAll(".rate-cell").forEach(cell => {
        if (cell.querySelector("input")) return;

        const value = cell.innerText.trim();
        const cleanValue = value === "N/A" ? "" : value;
        const rateId = cell.dataset.rate;
        const field = cell.dataset.field;
        const rateType = cell.dataset.rateType;

        cell.innerHTML = `
            <input type="number"
                   step="0.01"
                   class="form-control form-control-sm rate-input"
                   value="${cleanValue}"
                   data-original-value="${cleanValue}"
                   data-rate="${rateId}"
                   data-field="${field}"
                   data-rate-type="${rateType}"
                   placeholder="${cleanValue}">
        `;
        
        const input = cell.querySelector('.rate-input');
        
        input.addEventListener('input', function() {
            handleRateInputChange(row, this, blockId);
        });
    
    });
    
    // Editar celda de grupo
    const groupCell = row.querySelector(".group-cell");
    if (groupCell && !groupCell.querySelector("input.group-name-input:not(.d-none)")) {
        const groupDisplay = groupCell.querySelector(".group-name-display");
        const groupInput = groupCell.querySelector(".group-name-input");
        
        if (groupDisplay && groupInput) {
            groupInput.dataset.originalValue = groupInput.value;
            groupDisplay.classList.add("d-none");
            groupInput.classList.remove("d-none");
        }
    }
}

function handleRateInputChange(row, changedInput, blockId) {
    const field = changedInput.dataset.field;
    const rateType = changedInput.dataset.rateType;
    const isLinked = linkedCostsByBlock.get(blockId);
    
    // Si cambia el costo
    if (field === 'cost') {
        const costValue = parseFloat(changedInput.value) || 0;

        // Si están vinculados, actualizar el "otro" input de costo primero
        if (isLinked) {
            const otherType = rateType === 'SGL' ? 'DBL' : 'SGL';
            const otherCostInput = row.querySelector(`.rate-input[data-field="cost"][data-rate-type="${otherType}"]`);
            
            if (otherCostInput && otherCostInput.value !== changedInput.value) {
                otherCostInput.value = changedInput.value;
                // Actualizar la venta del tipo vinculado
                updateSellPriceFromMargin(row, otherType, costValue);
            }
        }
        
        // Actualizar la venta del tipo actual
        updateSellPriceFromMargin(row, rateType, costValue);
    }
    
    // Si el usuario modifica la venta manualmente, recalculamos el margen mostrado
    if (field === 'sell') {
        updateMarginForRow(row, changedInput);
    }
}

function updateSellPriceFromMargin(row, rateType, costValue) {
    const blockId = row.dataset.block;
    const marginInput = document.querySelector(`.margin-input[data-block="${blockId}"]`);
    
    // Si no hay input de margen o el costo es 0, no hacemos nada
    if (!marginInput || costValue <= 0) return;

    const currentMargin = parseFloat(marginInput.value);
    
    // Validar margen para evitar división por cero o resultados negativos
    if (isNaN(currentMargin) || currentMargin >= 100 || currentMargin <= 0) return;

    // FÓRMULA: Venta = Costo / (1 - Margen/100)
    const rawSell = costValue / currentMargin;
    
    const sellInput = row.querySelector(`.rate-input[data-field="sell"][data-rate-type="${rateType}"]`);
    if (sellInput) {
        sellInput.value = Math.ceil(rawSell); // Redondeo para arriba (125.01 -> 126)
    }
}

function updateMarginForRow(row, changedInput) {
    const rateType = changedInput.dataset.rateType;
    
    // Buscar cost y sell del mismo tipo de rate
    const costInput = row.querySelector(`.rate-input[data-field="cost"][data-rate-type="${rateType}"]`);
    const sellInput = row.querySelector(`.rate-input[data-field="sell"][data-rate-type="${rateType}"]`);
    
    if (!costInput || !sellInput) {
        console.warn(`No se encontraron inputs para ${rateType}`);
        return;
    }
    
    const cost = parseFloat(costInput.value) || 0;
    const sell = parseFloat(sellInput.value) || 0;
    
    // Buscar la celda de margen
    const marginCell = row.querySelector(`td:has(> .margin-value[data-rate-type="${rateType}"])`);
    
    if (!marginCell) return;
    
    if (cost > 0 && sell > 0) {
        const margin = ((sell - cost) / sell) * 100;
        marginCell.innerHTML = `<span class="margin-value" data-rate-type="${rateType}">${margin.toFixed(1)}%</span>`;
        
        const marginSpan = marginCell.querySelector('.margin-value');
        if (margin < 11) {
            marginSpan.classList.add('text-danger', 'fw-bold');
            marginSpan.classList.remove('text-warning', 'text-success');
        } else if (margin < 15) {
            marginSpan.classList.add('text-warning', 'fw-bold');
            marginSpan.classList.remove('text-danger', 'text-success');
        } else {
            marginSpan.classList.add('text-success', 'fw-bold');
            marginSpan.classList.remove('text-danger', 'text-warning');
        }
    } else {
        marginCell.innerHTML = '<span class="margin-value" data-rate-type="' + rateType + '">N/A</span>';
    }
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

function confirmCopyBlock(blockId) {
    const newDateFrom = document.getElementById(`newDateFrom${blockId}`).value;
    const newDateTo = document.getElementById(`newDateTo${blockId}`).value;
    const newSeason = document.getElementById(`newSeason${blockId}`).value;
    
    if (!newDateFrom || !newDateTo || !newSeason) {
        alert("Todos los campos son obligatorios");
        return;
    }
    
    // Recolectar todas las líneas del bloque original
    const rows = document.querySelectorAll(`.row-rateline[data-block="${blockId}"]`);
    const lines = [];
    
    rows.forEach(row => {
        const ratelineId = row.dataset.ratelineId;
        const rategroupId = row.dataset.rategroupId;
        
        console.log("Processing row:", {
            ratelineId,
            rategroupId
        });
        
        if (!ratelineId || !rategroupId) {
            console.warn("Fila sin IDs válidos:", row);
            return;
        }
        
        lines.push({
            rateline_id: ratelineId,
            rategroup_id: rategroupId
        });
    });
    
    console.log("Datos a enviar:", {
        date_from: newDateFrom,
        date_to: newDateTo,
        season: newSeason,
        lines: lines
    });
    
    if (lines.length === 0) {
        alert("No hay líneas válidas para copiar");
        return;
    }
    
    // Enviar al servidor
    fetch("/tariff/modify/copy-rate-block/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            date_from: newDateFrom,
            date_to: newDateTo,
            season: newSeason,
            lines: lines
        })
    })
    .then(r => r.json())
    .then(resp => {
        console.log("Respuesta del servidor:", resp);
        if (resp.ok) {
            alert(resp.message || "Bloque copiado exitosamente");
            // Cerrar modal
            const modalElement = document.getElementById(`copyBlockModal${blockId}`);
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) {
                modalInstance.hide();
            }
            // Recargar página después de un breve delay
            setTimeout(() => location.reload(), 300);
        } else {
            alert("Error al copiar: " + (resp.error || "Desconocido"));
        }
    })
    .catch(err => {
        alert("Error de conexión: " + err.message);
        console.error("Error completo:", err);
    });
}

// ========================================
// ELIMINAR BLOQUE
// ========================================
document.querySelectorAll(".delete-block").forEach(button => {
    button.addEventListener("click", function(e) {
        e.stopPropagation();
        const blockId = this.dataset.block;
        const dateFrom = this.dataset.from;
        const dateTo = this.dataset.to;
        const season = this.dataset.season;
        
        // Mostrar modal de confirmación
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="deleteBlockModal${blockId}" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title">
                                <i class="fa-solid fa-exclamation-triangle"></i>
                                Eliminar Bloque de Tarifas
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-3">¿Está seguro que desea eliminar el bloque completo?</p>
                            <div class="alert alert-warning">
                                <strong>Vigencia:</strong> ${dateFrom} a ${dateTo}<br>
                                <strong>Temporada:</strong> ${season}<br>
                                <strong>Esta acción no se puede deshacer.</strong>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-danger" onclick="confirmDeleteBlock('${blockId}')">
                                <i class="fa-solid fa-trash"></i> Eliminar Bloque
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const modalInstance = new bootstrap.Modal(document.getElementById(`deleteBlockModal${blockId}`));
        modalInstance.show();
        
        // Limpiar modal al cerrar
        document.getElementById(`deleteBlockModal${blockId}`).addEventListener('hidden.bs.modal', function () {
            modal.remove();
        });
    });
});

function confirmDeleteBlock(blockId) {
    // Recolectar todos los IDs de RateLine del bloque
    const rows = document.querySelectorAll(`.row-rateline[data-block="${blockId}"]`);
    const ratelineIds = [];
    
    rows.forEach(row => {
        const ratelineId = row.dataset.ratelineId;
        if (ratelineId) {
            ratelineIds.push(ratelineId);
        }
    });
    
    if (ratelineIds.length === 0) {
        alert("No hay líneas para eliminar");
        return;
    }
    
    console.log("Eliminando RateLines:", ratelineIds);
    
    fetch("/tariff/modify/delete-rate-block/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            rateline_ids: ratelineIds
        })
    })
    .then(r => r.json())
    .then(resp => {
        console.log("Respuesta del servidor:", resp);
        if (resp.ok) {
            alert(resp.message || "Bloque eliminado exitosamente");
            // Cerrar modal
            const modalElement = document.getElementById(`deleteBlockModal${blockId}`);
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) {
                modalInstance.hide();
            }
            // Recargar página
            setTimeout(() => location.reload(), 300);
        } else {
            alert("Error al eliminar: " + (resp.error || "Desconocido"));
        }
    })
    .catch(err => {
        alert("Error de conexión: " + err.message);
        console.error("Error completo:", err);
    });
}

// ========================================
// CREAR NUEVO BLOQUE
// ========================================
document.getElementById("new_block_btn").addEventListener("click", function() {
    // Obtener todos los productos del supplier
    const productSelect = document.getElementById("product_filter_select");
    const products = [];
    
    for (let i = 1; i < productSelect.options.length; i++) {
        const option = productSelect.options[i];
        products.push({
            id: option.value,
            name: option.text
        });
    }
    
    if (products.length === 0) {
        alert("No hay productos disponibles para crear tarifas");
        return;
    }
    
    // Crear lista de checkboxes para productos
    const productCheckboxes = products.map(p => `
        <div class="form-check">
            <input class="form-check-input product-checkbox" 
                   type="checkbox" 
                   value="${p.id}" 
                   id="product_${p.id}"
                   checked>
            <label class="form-check-label" for="product_${p.id}">
                ${p.name}
            </label>
        </div>
    `).join('');
    
    const modal = document.createElement('div');
    modal.innerHTML = `
        <div class="modal fade" id="newBlockModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fa-solid fa-plus"></i>
                            Crear Nuevo Bloque de Tarifas
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Fecha Desde *</label>
                                    <input type="date" class="form-control" id="blockDateFrom" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Fecha Hasta *</label>
                                    <input type="date" class="form-control" id="blockDateTo" required>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Nombre Vigencia/Temporada *</label>
                            <input type="text" class="form-control" id="blockSeason" 
                                   placeholder="Ej: Temporada Alta 2026" required>
                        </div>
                        
                        <hr>
                        
                        <div class="mb-3">
                            <label class="form-label d-flex justify-content-between align-items-center">
                                <span>Productos a incluir *</span>
                                <div>
                                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="selectAllProducts(true)">
                                        Seleccionar todos
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="selectAllProducts(false)">
                                        Deseleccionar todos
                                    </button>
                                </div>
                            </label>
                            <div class="border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                ${productCheckboxes}
                            </div>
                        </div>
                        
                        <hr>
                        
                        <h6 class="mb-3">Configuración de Tarifas</h6>
                        
                        <div class="row">
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">Status *</label>
                                    <select class="form-select" id="blockStatus" required>
                                        <option value="Confirmed">Confirmed</option>
                                        <option value="Provisional" selected>Provisional</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">Increase (%)</label>
                                    <input type="number" step="0.01" class="form-control" 
                                           id="blockIncrease" placeholder="0.00">
                                    <small class="text-muted">Opcional: incremento porcentual</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">Margin *</label>
                                    <select class="form-select" id="blockMargin" required>
                                        <option value="Low">Low</option>
                                        <option value="Regular" selected>Regular</option>
                                        <option value="High">High</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <hr>
                                                
                        <small class="text-muted">
                            <i class="fa-solid fa-info-circle"></i>
                            Los costos base serán 0 por defecto. La configuración de status, increase y margin se aplicará a todas las tarifas del bloque.
                        </small>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-primary" onclick="confirmCreateBlock()">
                            <i class="fa-solid fa-check"></i> Crear Bloque
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const modalInstance = new bootstrap.Modal(document.getElementById('newBlockModal'));
    modalInstance.show();
    
    // Limpiar modal al cerrar
    document.getElementById('newBlockModal').addEventListener('hidden.bs.modal', function () {
        modal.remove();
    });
});

function selectAllProducts(checked) {
    document.querySelectorAll('.product-checkbox').forEach(checkbox => {
        checkbox.checked = checked;
    });
}

function confirmCreateBlock() {
    const dateFrom = document.getElementById('blockDateFrom').value;
    const dateTo = document.getElementById('blockDateTo').value;
    const season = document.getElementById('blockSeason').value;
    const status = document.getElementById('blockStatus').value;
    const increase = document.getElementById('blockIncrease').value;
    const margin = document.getElementById('blockMargin').value;
      
    // Validaciones
    if (!dateFrom || !dateTo || !season) {
        alert("Por favor completa todos los campos obligatorios");
        return;
    }
    
    if (!status || !margin) {
        alert("Por favor selecciona el status y el margin");
        return;
    }
    
    if (new Date(dateFrom) > new Date(dateTo)) {
        alert("La fecha desde no puede ser posterior a la fecha hasta");
        return;
    }
    
    // Obtener productos seleccionados
    const selectedProducts = [];
    document.querySelectorAll('.product-checkbox:checked').forEach(checkbox => {
        selectedProducts.push(checkbox.value);
    });
    
    if (selectedProducts.length === 0) {
        alert("Debes seleccionar al menos un producto");
        return;
    }
    
    console.log("Creando nuevo bloque:", {
        dateFrom,
        dateTo,
        season,
        status,
        increase: increase || null,
        margin,
        products: selectedProducts,
    });
    
    fetch("/tariff/modify/create-rate-block/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            date_from: dateFrom,
            date_to: dateTo,
            season: season,
            status: status,
            increase: increase ? parseFloat(increase) : null,
            margin: margin,
            product_ids: selectedProducts,
        })
    })
    .then(r => r.json())
    .then(resp => {
        console.log("Respuesta del servidor:", resp);
        if (resp.ok) {
            alert(resp.message || "Bloque creado exitosamente");
            // Cerrar modal
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('newBlockModal'));
            if (modalInstance) {
                modalInstance.hide();
            }
            // Recargar página
            setTimeout(() => location.reload(), 300);
        } else {
            alert("Error al crear: " + (resp.error || "Desconocido"));
        }
    })
    .catch(err => {
        alert("Error de conexión: " + err.message);
        console.error("Error completo:", err);
    });
}

// Event listener para botones de cancelar
document.querySelectorAll(".cancel-block").forEach(button => {
    button.addEventListener("click", function() {
        const blockId = this.dataset.block;
        cancelBlockEdit(blockId);
    });
});

// Event listener para ESC key
document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && currentEditingBlock) {
        cancelBlockEdit(currentEditingBlock);
    }
});

function cancelBlockEdit(blockId) {
    const rows = document.querySelectorAll(`.row-rateline[data-block="${blockId}"]`);
    
    // 1. Resetear variables de control
    linkedCostsByBlock.delete(blockId);
    currentEditingBlock = null;

    // 2. Limpiar UI de bloque (Toggle de vinculación)
    const toggle = document.getElementById(`linkCostBlock_${blockId}`);
    if (toggle) {
        toggle.closest('.cost-link-toggle-block').remove();
    }

    // 3. Revertir MARGEN y TEMPORADA (Input -> Span)
    const displays = ['margin', 'season'];
    displays.forEach(type => {
        const display = document.querySelector(`.${type}-display[data-block="${blockId}"]`);
        const input = document.querySelector(`.${type}-input[data-block="${blockId}"]`);
        if (display && input) {
            input.value = input.dataset.originalValue || input.value;
            display.textContent = input.value; // Volver al texto original
            display.classList.remove("d-none");
            input.classList.add("d-none");
        }
    });

    // 4. Revertir CELDAS DE TARIFAS (Venta, Costo, etc.)
    rows.forEach(row => {
        row.querySelectorAll(".rate-cell").forEach(cell => {
            const input = cell.querySelector("input");
            if (input) {
                // ✅ CLAVE: Restaurar el texto original guardado en el dataset
                const original = input.dataset.originalValue;
                cell.innerText = (original === "" || original === undefined) ? "N/A" : original;
            }
        });

        // Revertir Nombre de Grupo
        const groupCell = row.querySelector(".group-cell");
        if (groupCell) {
            const gDisplay = groupCell.querySelector(".group-name-display");
            const gInput = groupCell.querySelector(".group-name-input");
            if (gDisplay && gInput) {
                gInput.value = gInput.dataset.originalValue || gInput.value;
                gDisplay.textContent = gInput.value;
                gDisplay.classList.remove("d-none");
                gInput.classList.add("d-none");
            }
        }
        
        // Opcional: Si tienes una función que refresca los colores de los márgenes estáticos, 
        // podrías llamarla aquí para que los colores vuelvan a su estado original.
    });

    // 5. Restaurar botones de acción
    const editBtn = document.querySelector(`.edit-block[data-block="${blockId}"]`);
    if (editBtn) {
        editBtn.innerHTML = '<i class="fa-solid fa-pencil"></i>';
        editBtn.classList.replace("btn-success", "btn-dark");
        editBtn.dataset.editing = "false";
    }

    document.querySelector(`.cancel-block[data-block="${blockId}"]`)?.classList.add("d-none");
    document.querySelector(`.delete-block[data-block="${blockId}"]`)?.classList.remove("d-none");
}

// ========================================
// APLICAR CONFIGURACIÓN GLOBAL DEL BLOQUE
// ========================================
function applyBlockConfig(blockId) {
    const blockElement = document.querySelector(`[data-block-id="${blockId}"]`);
    
    const status = blockElement.querySelector('.block-status').value;
    const increase = blockElement.querySelector('.block-increase').value;
    const margin = blockElement.querySelector('.block-margin').value;
    
    if (!status || !margin) {
        alert("Por favor selecciona el status y el margin");
        return;
    }
    
    if (!confirm("¿Estás seguro de aplicar esta configuración a TODAS las tarifas de este bloque?")) {
        return;
    }
    
    const data = {
        block_id: blockId,
        status: status,
        increase: increase ? parseFloat(increase) : null,
        margin: margin
    };
    
    console.log("Aplicando configuración global:", data);
    
    fetch("/tariff/modify/apply-block-config/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(resp => {
        console.log("Respuesta del servidor:", resp);
        if (resp.ok) {
            alert(resp.message || "Configuración aplicada exitosamente");
            // Actualizar visualmente las celdas de la tabla si es necesario
            updateBlockRatesDisplay(blockId, status, increase, margin);
            // O recargar la página
            setTimeout(() => location.reload(), 500);
        } else {
            alert("Error al aplicar configuración: " + (resp.error || "Desconocido"));
        }
    })
    .catch(err => {
        alert("Error de conexión: " + err.message);
        console.error("Error completo:", err);
    });
}

// Función auxiliar para actualizar visualmente (opcional)
function updateBlockRatesDisplay(blockId, status, increase, margin) {
    const blockElement = document.querySelector(`[data-block-id="${blockId}"]`);
    const rateRows = blockElement.querySelectorAll('.rate-row');
    
    rateRows.forEach(row => {
        // Actualizar celdas visibles si las tienes en la tabla
        const statusCell = row.querySelector('.rate-status');
        const increaseCell = row.querySelector('.rate-increase');
        const marginCell = row.querySelector('.rate-margin');
        
        if (statusCell) statusCell.textContent = status;
        if (increaseCell) increaseCell.textContent = increase || '-';
        if (marginCell) marginCell.textContent = margin;
    });
}

// ========================================
// CARGAR VALORES ACTUALES DEL BLOQUE
// ========================================
function loadBlockConfig(blockId) {
    // Esta función carga los valores actuales del bloque
    // (asumiendo que el primer rate del bloque tiene la config)
    fetch(`/tariff/modify/get-block-config/${blockId}/`)
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            const blockElement = document.querySelector(`[data-block-id="${blockId}"]`);
            blockElement.querySelector('.block-status').value = data.status;
            blockElement.querySelector('.block-increase').value = data.increase || '';
            blockElement.querySelector('.block-margin').value = data.margin;
        }
    })
    .catch(err => console.error("Error cargando config del bloque:", err));
}