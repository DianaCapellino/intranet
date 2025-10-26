document.addEventListener('DOMContentLoaded', async () => {
    // ✅ Detectar si estamos en la página de presentación
    if (window.location.pathname.startsWith("/stats/entries/")) {
        console.log("📊 Modo presentación detectado");

        const params = new URLSearchParams(window.location.search);
        const filters = Object.fromEntries(params.entries());

        if (filters.filter === "monthly") {
            const reportPeriod = filters.period;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        } else if (filters.filter === "weekly") {
            const reportPeriod = filters.period;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        } else {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        };

        // Llamar a la función que obtiene los datos del backend
        await generatePresentationEntriesData(filters);

        // Mostrar contenido cuando los datos llegan
        const loadingEl = document.getElementById('loading');
        const contentEl = document.getElementById('report-content');
        if (loadingEl) loadingEl.classList.remove('show');
        if (contentEl) contentEl.style.display = 'block';

        // Buttons listeners
        const exportPdf = document.querySelector('.btn-export'); 
        if (exportPdf) {
            exportPdf.addEventListener('click', (e) => {
                console.log("🟢 Listener de exportación activado por clase.");
                exportToPDF(e);
            });
        };

        // 🛑 IMPORTANTE: no ejecutar el resto del JS (DataTables, formularios, etc.)
        return;
    }

    // Display functionality of the btn
    stats_btn_display();



    const startPresentation = document.getElementById('start-presentation');
    if (startPresentation) {
        startPresentation.addEventListener('click', () => {

        });
    };

    var calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: '/holidays/json',
        });
        calendar.render();
    };
})

// ==================== DATOS Y ESTADO ====================
let vendorData = {};
let reportPeriod = '';
let charts = {};

// extraer helper
function toDateOnly(raw) {
    if (!raw) return "";
    // si viene con 'T' (datetime-local) tomar la parte antes de la T
    if (raw.includes("T")) return raw.split("T")[0];
    // si viene con espacio (posible), tomar primer token
    if (raw.includes(" ")) return raw.split(" ")[0];
    // si ya es YYYY-MM-DD, devolver tal cual
    return raw;
}

async function generatePresentationEntriesData(filters = {}) {
    try {
        // Construir query string (para filtros personalizados)
        const params = new URLSearchParams(filters);
        const response = await fetch(`/stats/data/entries/presentation/?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();

        // Guardamos el objeto global vendorData para reutilizarlo
        window.vendorData = result.vendors || {};

        // ⚠️ Asignar a la variable que usa renderReport (no a window.vendorData)
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalized = {};
        const raw = result.vendors || result || {};
        Object.entries(raw).forEach(([vendor, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const a = parseInt(vals.a || 0, 10) || 0;
            const total = parseInt(vals.total || 0, 10) || 0;
            const audleyA = parseInt(vals.audleyA || vals.audleyA || 0, 10) || 0;
            const montoA = parseFloat(vals.montoA || 0) || 0;
            const color = vals.color;
            normalized[vendor] = {
                total,
                a,
                audleyA,
                montoA,
                color
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorData = normalized;

        console.log("📊 Datos recibidos y normalizados:", vendorData);

        // Mostrar el contenido y ocultar loading si existen
        const loadingEl = document.getElementById('loading');
        const contentEl = document.getElementById('report-content');
        if (loadingEl) loadingEl.classList.remove('show');
        if (contentEl) contentEl.style.display = 'block';

        // Llamar al renderer (tabla, charts, insights)
        if (typeof renderReport === "function") {
            renderReport();
        } else {
            console.warn("renderReport() no está definida");
        }

    } catch (error) {
        console.error("Error al cargar datos de vendedores:", error);
        // opcional: mostrar mensaje al usuario en el DOM
        const contentEl = document.getElementById('report-content');
        if (contentEl) {
            contentEl.innerHTML = `<div class="alert alert-danger">Error al cargar datos: ${error.message}</div>`;
            contentEl.style.display = 'block';
        }
    }
}

// ==================== FUNCIÓN: Renderizar reporte ====================
function renderReport() {
    renderVendorTable();
    renderCharts();
    renderInsights();
}

// ==================== FUNCIÓN: Renderizar tabla ====================
function renderVendorTable() {

    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#vendor-table")) {
        $("#vendor-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('vendor-tbody');
    const tfoot = document.getElementById('vendor-tfoot'); // ⚠️ nuevo
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }
    const totalMontoA = Object.values(vendorData).reduce((acc, v) => acc + v.montoA, 0);
    
    tbody.innerHTML = '';
    tfoot.innerHTML = '';
    
    Object.entries(vendorData).forEach(([vendor, vals]) => {
        const perc = totalMontoA > 0 ? ((vals.montoA / totalMontoA) * 100).toFixed(2) : 0;

        // Determinar color de fondo para el nombre del vendedor
        const color = vals.color || '#FFFFFF'; // Usar color del dato, default blanco
        
        // Determinar color de texto (para asegurar contraste legible)
        // Si el fondo es muy claro, usar texto negro; si es oscuro, usar blanco.
        // Aquí simplificamos, asumiendo que los colores son generalmente pasteles y claros, 
        // por lo que el texto oscuro (#333) funciona bien. Si no es así, necesitarías una función de contraste.
        const textColor = '#333333';

        const row = document.createElement('tr');
        
        // Esto cubre cualquier estilo general de la fila (ej. hover)
        const rowStyle = `background-color: ${color} !important; color: ${textColor};`;
        row.setAttribute('style', rowStyle);
        
        // 2. Definir el estilo de celda (background-color con !important)
        // Esto es necesario para vencer a las reglas de DataTables/Bootstrap en las celdas <td>.
        const cellStyle = `background-color: ${color} !important; color: ${textColor};`;

        row.innerHTML = `
            <td style="${cellStyle}">${vendor}</td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">${vals.a}</td>
            <td style="${cellStyle}">${vals.audleyA}</td>
            <td style="${cellStyle}">USD ${vals.montoA.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${perc}%</td>
        `;
        tbody.appendChild(row);
    });
    
    // 🔹 Agregar fila total al TFOOT
    const totalCotizaciones = Object.values(vendorData).reduce((acc, v) => acc + v.total, 0);
    const totalA = Object.values(vendorData).reduce((acc, v) => acc + v.a, 0);
    const totalAudleyA = Object.values(vendorData).reduce((acc, v) => acc + v.audleyA, 0);

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>${totalCotizaciones}</td>
        <td>${totalA}</td>
        <td>${totalAudleyA}</td>
        <td>USD ${totalMontoA.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
    `;
    tfoot.appendChild(totalRow);
    
    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("vendor-table");
    
}

// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderCharts() {
    const vendors = Object.keys(vendorData);
    const cotizacionesA = vendors.map(v => vendorData[v].a);
    const montosA = vendors.map(v => vendorData[v].montoA);
    
    // ✅ CORRECTO: Acceder al color dentro de cada vendedor
    const colors = vendors.map(vendor => vendorData[vendor].color || '#999999');
    
    // Destruir gráficos anteriores
    if (charts.cantidad) charts.cantidad.destroy();
    if (charts.monto) charts.monto.destroy();

    // Gráfico de Cantidad
    const ctxCantidad = document.getElementById('chartCantidadCanvas').getContext('2d');
    charts.cantidad = new Chart(ctxCantidad, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: cotizacionesA,
                backgroundColor: colors,
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'Arial', size: 12 },
                        padding: 15
                    }
                }
            }
        }
    });

    // Gráfico de Monto
    const ctxMonto = document.getElementById('chartMontoCanvas').getContext('2d');
    charts.monto = new Chart(ctxMonto, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: montosA,
                backgroundColor: colors,
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: 'Arial', size: 12 },
                        padding: 15
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'USD ' + context.parsed.toLocaleString('en-US', {minimumFractionDigits: 0});
                        }
                    }
                }
            }
        }
    });
}

// ==================== FUNCIÓN: Renderizar insights ====================
function renderInsights() {
    const vendors = Object.keys(vendorData);
    const topVendor = vendors.reduce((max, vendor) => 
        vendorData[vendor].montoA > vendorData[max].montoA ? vendor : max
    );
    
    const totalMonto = Object.values(vendorData).reduce((acc, v) => acc + v.montoA, 0);
    const totalCotizaciones = Object.values(vendorData).reduce((acc, v) => acc + v.a, 0);
    const promedio = totalMonto / vendors.length;

    const insights = `
        <ul>
            <li><strong>🏆 Top Vendedor:</strong> ${topVendor} con USD ${vendorData[topVendor].montoA.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>💰 Facturación Total:</strong> USD ${totalMonto.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>📊 Total Cotizaciones A:</strong> ${totalCotizaciones} cotizaciones</li>
            <li><strong>📈 Promedio por Vendedor:</strong> USD ${promedio.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>👥 Vendedores Activos:</strong> ${vendors.length}</li>
        </ul>
    `;

    document.getElementById('insights-content').innerHTML = insights;
}

// ==================== FUNCIÓN: Exportar a PDF ====================
async function exportToPDF(event) {
    console.log("🟢 FUNCIÓN EXPORTAR A PDF INICIADA");
    const pdf = new window.jspdf.jsPDF('p', 'mm', 'a4');
    
    // Mostrar loading
    const btnPDF = event.target.closest('.btn-export');
    const originalText = btnPDF.innerHTML;
    btnPDF.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    btnPDF.disabled = true;

    try {
        // Título
        pdf.setFontSize(20);
        pdf.setTextColor(102, 126, 234);
        pdf.text('Reporte de Estadísticas', 15, 20);
        
        // Período
        pdf.setFontSize(12);
        pdf.setTextColor(100);
        pdf.text(`Período: ${reportPeriod}`, 15, 30);
        pdf.text(`Fecha: ${new Date().toLocaleDateString('es-AR')}`, 15, 37);
        
        // Línea divisoria
        pdf.setDrawColor(102, 126, 234);
        pdf.line(15, 42, 195, 42);
        
        let yPosition = 50;
        
        // 1. OBTENER ELEMENTOS ESTRUCTURALES
        const table = document.getElementById('vendor-table');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        const tfoot = table.querySelector('tfoot'); // La fila de totales va aquí

        // 2. EXTRAER DATOS
        
        // A. HEAD (Extraer la primera fila del thead)
        let headRows = [];
        if (thead) {
            thead.querySelectorAll('tr').forEach(tr => {
                headRows.push(Array.from(tr.querySelectorAll('th')).map(th => th.textContent.trim()));
            });
        }

        // B. BODY (Extraer todas las filas del tbody)
        let bodyRows = [];
        if (tbody) {
            tbody.querySelectorAll('tr').forEach(tr => {
                bodyRows.push(Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim()));
            });
        }
        
        // C. FOOT (Extraer la fila de totales del tfoot)
        let footRows = [];
        if (tfoot) {
             tfoot.querySelectorAll('tr').forEach(tr => {
                // Puede que sean <td> o <th> en el tfoot
                footRows.push(Array.from(tr.querySelectorAll('td, th')).map(cell => cell.textContent.trim()));
            });
        }

        // 3. GENERAR AUTO-TABLA
        pdf.autoTable({
            head: headRows.length > 0 ? headRows : [],
            body: bodyRows, // Solo las filas de datos
            foot: footRows.length > 0 ? footRows : [], // La fila de totales va aquí
            
            startY: yPosition,
            margin: 15,
            didDrawPage: function(data) {
                const pageSize = pdf.internal.pageSize;
                const pageHeight = pageSize.getHeight();
                const pageWidth = pageSize.getWidth();
                pdf.setFontSize(10);
                pdf.setTextColor(150);
                pdf.text(`Página ${data.pageNumber}`, pageWidth / 2, pageHeight - 10, { align: 'center' });
            }
        });

        yPosition = pdf.lastAutoTable.finalY + 15;

        // Gráficos como imágenes
        const chartCantidadCanvas = document.getElementById('chartCantidadCanvas');
        const chartMontoCanvas = document.getElementById('chartMontoCanvas');
        
        if (yPosition + 80 > pdf.internal.pageSize.getHeight()) {
            pdf.addPage();
            yPosition = 15;
        }

        pdf.setFontSize(14);
        pdf.setTextColor(102, 126, 234);
        pdf.text('Gráficos', 15, yPosition);
        yPosition += 10;

        // Capturar gráficos
        const imgCantidad = await html2canvas(chartCantidadCanvas).then(canvas => canvas.toDataURL('image/png'));
        const imgMonto = await html2canvas(chartMontoCanvas).then(canvas => canvas.toDataURL('image/png'));

        pdf.addImage(imgCantidad, 'PNG', 15, yPosition, 85, 60);
        pdf.addImage(imgMonto, 'PNG', 105, yPosition, 85, 60);

        // Descargar
        pdf.save(`Reporte-Estadisticas-${new Date().toISOString().split('T')[0]}.pdf`);

    } catch (error) {
        console.error('Error generando PDF:', error);
        alert('Error al generar el PDF');
    } finally {
        btnPDF.innerHTML = originalText;
        btnPDF.disabled = false;
    }
}

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
            event.preventDefault();

            // reset tabla
            document.getElementById('report_results').innerHTML = `
                <table id="stats-table" class="table table-hover" style="width:100%"></table>`;

            // filtros adicionales
            let extraData = {};
            if (btn_id == "2") {
                extraData.month = document.getElementById("month-select").value;
                extraData.year = document.getElementById("year-select").value;
            } else if (btn_id == "4") {
                let rawFrom = document.getElementById("date-from").value;
                let rawTo = document.getElementById("date-to").value;
                extraData.date_from = rawFrom ? rawFrom.split("T")[0] : "";
                extraData.date_to = rawTo ? rawTo.split("T")[0] : "";
            }

            // 🚩 leer tipo de reporte (entries o trips) según select del form activo
            const typeSelect = stats_form.querySelector('select[id^="type-select"]');
            let reportType = "entries"; // default
            if (typeSelect) {
                reportType = typeSelect.value;
            }
            extraData.type = reportType;

            // 🚩 definir columnas distintas para cada tipo
            let columnsDef = [];
            if (reportType === "entries") {
                columnsDef = [
                    { title: "Fecha Pedido", data: "starting_date" },
                    { title: "Fecha Respuesta", data: "closing_date" },
                    { title: "Viaje", data: "trip" },
                    { title: "Status", data: "status" },
                    { title: "Version", data: "version" },
                    { title: "Version Quote", data: "version_quote"},
                    { title: "Monto", data: "amount" },
                    { title: "Cliente", data: "client" },
                    { title: "Vendedor", data: "contact" },
                    { title: "Cot. por", data: "user_creator" },
                    { title: "Trab. por", data: "user_working" },
                    { title: "Dificultad", data: "difficulty" },
                    { title: "Fecha Viaje", data: "travelling_date" },
                ];
            } else if (reportType === "trips") {
                columnsDef = [
                    { title: "Viaje", data: "name" },
                    { title: "Cliente", data: "client" },
                    { title: "Contacto", data: "contact" },
                    { title: "Referencia", data: "reference" },
                    { title: "Fecha Viaje", data: "travelling_date" },
                    { title: "Monto Total", data: "amount" },
                    { title: "Dificultad", data: "difficulty"},
                    { title: "VR", data: "responsable_user"},
                    { title: "OP", data: "operations_user"}
                ];
            }

            // 🚩 inicializar DataTable
            let table = new DataTable("#stats-table", {
                processing: true,
                serverSide: true,
                ajax: {
                    url: "/stats/data/",
                    type: "GET",
                    data: function (d) {
                        Object.assign(d, extraData);
                    }
                },
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
                columns: columnsDef,
                language: {
                    url: "https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json"
                },
                lengthMenu: [[50, 100, -1], [50, 100, "Todos"]],
                order: [[0, "asc"]]
            });

            table.on('xhr', function() {
                let json = table.ajax.json();
                if (json && json.summary) {
                    update_summary(json.summary, reportType);
                }
            });

            // Creates the table with the sum info or update it
            function update_summary(summary, reportType) {
                const table = document.getElementById('stats-totals');
                if (reportType === "entries") {
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
                } else {
                    table.innerHTML = `
                        <thead>
                            <tr>
                                <th>Cantidad Audley</th>
                                <th>Suma Audley</th>
                                <th>Cantidad Otros</th>
                                <th>Suma Otros</th>
                                <th>Cantidad TOTAL</th>
                                <th>Suma TOTAL</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>${summary.audley_count}</td>
                                <td>${summary.audley_amount}</td>
                                <td>${summary.others_count}</td>
                                <td>${summary.others_amount}</td>
                                <td>${summary.all_count}</td>
                                <td>${summary.all_amount}</td>
                            </tr>
                        </tbody>
                    `;
                };

                // Show the sum info and the slide buttons
                document.getElementById('stats-sum').classList.remove('d-none');
                document.getElementById('presentation-buttons').classList.remove('d-none');
                inicialize_presentations(reportType);
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

function inicialize_presentations(reportType) {
    const button = document.getElementById('stats-presentation-1');
    if (!button) return;

    if (!button.dataset.listenerAdded) {
        button.addEventListener("click", () => {
            // Capturar los parámetros del formulario actual
            const formId = document.querySelector('.stats-form:not(.d-none)').id;
            let queryParams = new URLSearchParams();
            
            // Determinar período y parámetros según qué forma esté visible
            if (formId === '1-stats-form') {
                // Semanal
                const week = document.getElementById('week-select').value;
                queryParams.append('period', `Semana ${week}`);
                queryParams.append('filter', 'weekly');

                const typeReport = document.getElementById('type-select-1').value;
                
                // Redirigir a la página de reporte
                window.location.href = `/stats/${typeReport}/?${queryParams.toString()}`;
            } else if (formId === '2-stats-form') {
                // Mensual
                const month = document.getElementById('month-select').value;
                const year = document.getElementById('year-select').value;
                queryParams.append('period', `${month} ${year}`);
                queryParams.append('filter', 'monthly');
                const typeReport = document.getElementById('type-select-2').value;
                
                // Redirigir a la página de reporte
                window.location.href = `/stats/${typeReport}/?${queryParams.toString()}`;
            } else if (formId === '4-stats-form') {
                // Personalizado
                const rawFrom = document.getElementById('date-from').value;
                const rawTo   = document.getElementById('date-to').value;

                // Normalizamos a YYYY-MM-DD
                const dateFrom = toDateOnly(rawFrom);
                const dateTo   = toDateOnly(rawTo);

                queryParams.append('date_from', `${dateFrom}`);
                queryParams.append('date_to', `${dateTo}`);
                queryParams.append('filter', 'custom');
                const typeReport = document.getElementById('type-select-4').value;
                                
                // Redirigir a la página de reporte
                window.location.href = `/stats/${typeReport}/?${queryParams.toString()}`;
            }
        });
        
        button.dataset.listenerAdded = "true";
    }
}

function create_datatable_stats(id) {

    // Create new DataTable
    new DataTable(`#${id}`, {
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
        paging: false,
        order: [[1, "desc"]],
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });
}