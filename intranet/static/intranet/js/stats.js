document.addEventListener('DOMContentLoaded', () => {

    // Display functionality of the btn
    stats_btn_display();

    // Display presentations
    //inicialize_presentations();

    var calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: '/holidays/json',
        });
        calendar.render();
    };
})

function stats_btn_display() {
    const all_stats_btn = document.querySelectorAll('.stats-btn');
    if (all_stats_btn) {
        all_stats_btn.forEach((btn) => {
            btn.addEventListener('click', () => {
                const btn_int = btn.id.match(/\d+/); // saca el número del id
                show_form(btn_int);
            });
        });
    }
}

function show_form(btn_id) {
    const stats_form = document.getElementById(`${btn_id}-stats-form`);

    if (stats_form != null) {
        hide_all_forms();
        stats_form.classList.remove("d-none");

        stats_form.addEventListener('submit', function (event) {
            event.preventDefault();  // prevent page to refresh
            
            // Create the table head
            document.getElementById('report_results').innerHTML = `
                <table id="stats-table" class="table table-hover" style="width:100%">
                    <thead>
                        <tr>
                            <th>Fecha Pedido</th>
                            <th>Fecha Respuesta</th>
                            <th>Viaje</th>
                            <th>Status</th>
                            <th>Monto</th>
                            <th>Cliente</th>
                            <th>Vendedor</th>
                            <th>Referencia</th>
                            <th>Cot. por</th>
                            <th>Trab. por</th>
                            <th>Progreso</th>
                            <th>Valoración</th>
                            <th>Observación</th>
                            <th>Fecha Viaje</th>
                        </tr>
                    </thead>
                </table>`;

            // Additional filters
            let extraData = {};

            // Form month
            if (btn_id == "2") {
                // Get the info of the form
                extraData.month = document.getElementById("month-select").value;
                extraData.year = document.getElementById("year-select").value;

            // Form Personalized
            } else if (btn_id == "4") {
                // Get the info of the form
                let rawFrom = document.getElementById("date-from").value;
                let rawTo = document.getElementById("date-to").value;

                // Convert to ISO
                let dateFrom = rawFrom ? rawFrom.split("T")[0] : "";
                let dateTo = rawTo ? rawTo.split("T")[0] : "";

                extraData.date_from = dateFrom;
                extraData.date_to = dateTo;
            }

            // Create DataTable bringing information fron server
            let table = new DataTable("#stats-table", {
                processing: true,
                serverSide: true,
                ajax: {
                    url: "/stats/data/",
                    type: "GET",
                    data: function (d) {
                        Object.assign(d, extraData);
                        d.type = "entries"; // por ahora solo entries
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
                ],
                language: {
                    url: "https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json"
                },
                lengthMenu: [[50, 100, -1], [50, 100, "Todos"]],
                order: [[0, "desc"]]
            });

            // When DataTable gets new data, update the sum info
            table.on('xhr', function() {
                let json = table.ajax.json();
                if (json && json.summary) {
                    update_summary(json.summary);
                }
                if (json && json.data) {
                    generateVendorSlides(json.data);
                }
            }); 

            // Creates the table with the sum info or update it
            function update_summary(summary) {
                const table = document.getElementById('stats-totals');
                table.innerHTML = `
                    <thead>
                        <tr>
                            <th>Cantidad Quotes A</th>
                            <th>Cantidad Quotes Todas</th>
                            <th>Suma Quotes A</th>
                            <th>Suma Quotes Todas</th>
                            <th>Cantidad Booking 1</th>
                            <th>Cantidad Booking Todas</th>
                            <th>Suma Booking 1</th>
                            <th>Suma Booking Todas</th>
                            <th>Cantidad otros</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${summary.quotesA_count}</td>
                            <td>${summary.quotes_all_count}</td>
                            <td>${summary.quotesA_sum}</td>
                            <td>${summary.quotes_all_sum}</td>
                            <td>${summary.bookings1_count}</td>
                            <td>${summary.bookings_all_count}</td>
                            <td>${summary.bookings1_sum}</td>
                            <td>${summary.bookings_all_sum}</td>
                            <td>${summary.others_count}</td>
                        </tr>
                    </tbody>
                `;

                // Show the sum info and the slide buttons
                document.getElementById('stats-sum').classList.remove('d-none');
                //document.getElementById('presentation-buttons').classList.remove('d-none');
                //inicialize_presentations();
            }
        });
    }
}

// Function that hides all the information before generating new request
function hide_all_forms() {
    const all_forms = document.querySelectorAll('.stats-form');
    if (all_forms) {
        all_forms.forEach((form) => {
            form.classList.add("d-none");
        });
    }
    // Hide the sum
    const results_sum = document.getElementById('stats-sum');
    if (results_sum) {
        results_sum.classList.add("d-none");
        document.getElementById('stats-totals').innerHTML = "";
    }
    
    // Destroy DataTable if exists
    if ($.fn.DataTable.isDataTable("#stats-table")) {
        $("#stats-table").DataTable().destroy();
        $("#stats-table").remove();  // elimina la tabla entera
    }
}

/* 🚀 Nuevo: generar slides Reveal + gráficos Chart.js */
function generateVendorSlides(entries) {

    const vendorData = {};

    entries.forEach(entry => {
        const vendor = entry.user_working || "Sin asignar";
        if (!vendorData[vendor]) {
            vendorData[vendor] = { total: 0, a: 0, audleyA: 0, montoA: 0 };
        }
        vendorData[vendor].total += 1;

        if (entry.status === "Quote" && entry.version_quote === "A") {
            vendorData[vendor].a += 1;
            let monto = parseFloat(entry.amount || 0);
            vendorData[vendor].montoA += monto;
            if (entry.client === "Audley Travel") {
                vendorData[vendor].audleyA += 1;
            }
        }
    });

    const totalMontoA = Object.values(vendorData).reduce((acc, v) => acc + v.montoA, 0);

    // Insertar tabla en slide 1
    const tbody = document.getElementById("vendor-summary-body");
    if (tbody) {
        tbody.innerHTML = "";
        Object.entries(vendorData).forEach(([vendor, vals]) => {
            const perc = totalMontoA > 0 ? ((vals.montoA / totalMontoA) * 100).toFixed(2) : 0;
            tbody.innerHTML += `
              <tr>
                <td>${vendor}</td>
                <td>${vals.total}</td>
                <td>${vals.a}</td>
                <td>${vals.audleyA}</td>
                <td>USD ${vals.montoA.toLocaleString()}</td>
                <td>${perc}%</td>
              </tr>
            `;
        });
    }

    const vendors = Object.keys(vendorData);
    const cotizacionesA = vendors.map(v => vendorData[v].a);
    const montosA = vendors.map(v => vendorData[v].montoA);

    // Limpiar gráficos viejos si existen
    if (Chart.getChart("chartCotizacionesCantidad")) {
        Chart.getChart("chartCotizacionesCantidad").destroy();
    }
    if (Chart.getChart("chartCotizacionesMonto")) {
        Chart.getChart("chartCotizacionesMonto").destroy();
    }

    // Gráfico Cantidad
    new Chart(document.getElementById("chartCotizacionesCantidad"), {
        type: "pie",
        data: {
            labels: vendors,
            datasets: [{
                data: cotizacionesA,
                backgroundColor: ["#4e79a7","#f28e2b","#e15759","#76b7b2",
                                  "#59a14f","#edc948","#b07aa1","#ff9da7",
                                  "#9c755f","#bab0ab"]
            }]
        }
    });

    // Gráfico Monto
    new Chart(document.getElementById("chartCotizacionesMonto"), {
        type: "pie",
        data: {
            labels: vendors,
            datasets: [{
                data: montosA,
                backgroundColor: ["#4e79a7","#f28e2b","#e15759","#76b7b2",
                                  "#59a14f","#edc948","#b07aa1","#ff9da7",
                                  "#9c755f","#bab0ab"]
            }]
        }
    });
}

function inicialize_presentations() {

    const button = document.getElementById('stats-presentation-1');
    if (!button) return;

    // para no duplicar listener
    if (!button.dataset.listenerAdded) {
        button.addEventListener("click", () => {
            const container = document.getElementById("presentation-container");

            // mostrar Reveal
            container.classList.remove("d-none")

            if (!window.revealInitialized) {
                Reveal.initialize({
                    embedded: true,
                    controls: true,
                    progress: true,
                    slideNumber: true,
                    width: "100%",
                    height: 600,
                });
                window.revealInitialized = true;
                console.log(window.Reveal)
            } else {
                Reveal.sync();
            }
        });
        button.dataset.listenerAdded = "true"; // flag para no duplicar
    }
}