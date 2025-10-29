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
let vendorQuoteData = {};
let vendorBookingData = {};
let reportPeriod = '';
let chartsQuotes = {};
let chartsBookings = {};

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
        window.vendorQuoteData = result.vendors_quote || {};
        window.vendorBookingData = result.vendors_bookings || {};

        window.summaryTableQuotes = result.summary_table_quotes || {};
        window.summaryTableBookings = result.summary_table_bookings || {};

        // ⚠️ Asignar a la variable que usa renderReport Quotes
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedQuotes = {};
        const raw = result.vendors_quote || result || {};
        Object.entries(raw).forEach(([vendor, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const a = parseInt(vals.a || 0, 10) || 0;
            const workingDays = parseInt(vals.workingDays || 0, 10) || 0;
            const total = parseInt(vals.total || 0, 10) || 0;
            const audleyA = parseInt(vals.audleyA || vals.audleyA || 0, 10) || 0;
            const montoA = parseFloat(vals.montoA || 0) || 0;
            const color = vals.color;
            normalizedQuotes[vendor] = {
                workingDays,
                total,
                a,
                audleyA,
                montoA,
                color
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorQuoteData = normalizedQuotes;

        console.log("📊 Datos recibidos y normalizados Quotes:", vendorQuoteData);

        // ⚠️ Asignar a la variable que usa renderReport Quotes
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedBookings = {};
        const rawB = result.vendors_bookings || result || {};
        Object.entries(rawB).forEach(([vendor, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const first = parseInt(vals.first || 0, 10) || 0;
            const workingDays = parseInt(vals.workingDays || 0, 10) || 0;
            const total = parseInt(vals.total || 0, 10) || 0;
            const audleyFirst = parseInt(vals.audleyFirst || vals.audleyFirst || 0, 10) || 0;
            const amountFirst = parseFloat(vals.amountFirst || 0) || 0;
            const color = vals.color;
            normalizedBookings[vendor] = {
                workingDays,
                total,
                first,
                audleyFirst,
                amountFirst,
                color
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorBookingData = normalizedBookings;

        console.log("📊 Datos recibidos y normalizados Bookings:", vendorBookingData);

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
    renderVendorTableQuote();
    renderVendorTableBooking();
    renderChartsQuotes();
    renderChartsBookings();
    renderInsightsQuotes();
    renderInsightsBookings();
    renderSummaryTables();
}


function renderSummaryTables() {
    const data = window.summaryTableQuotes;
    if (!data || !Object.keys(data).length) return;

    const tbody = document.getElementById("summary-quotes-tbody");
    if (!tbody) return;

    tbody.innerHTML = `
        <tr>
            <td>Promedio x día:</td>
            <td>${data.average_quotes_quantity}</td>
            <td>USD ${data.average_quotes_amount.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>-</td>
        </tr>
        <tr>
            <td>Audley:</td>
            <td>${data.audley_count_quotes}</td>
            <td>USD ${data.audley_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.audley_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Individuales:</td>
            <td>${data.individual_count_quotes}</td>
            <td>USD ${data.individual_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.individual_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Grupos:</td>
            <td>${data.group_count_quotes}</td>
            <td>USD ${data.group_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.group_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>FAM clientes:</td>
            <td>${data.fam_count_quotes}</td>
            <td>USD ${data.fam_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.fam_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>${data.this_season_str}</td>
            <td>${data.this_season_count_quotes}</td>
            <td>USD ${data.this_season_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.this_season_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>${data.next_season_str}</td>
            <td>${data.next_season_count_quotes}</td>
            <td>USD ${data.next_season_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${data.next_season_perc_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Cambios:</td>
            <td>${data.total_changes_quotes}</td>
            <td>-</td>
            <td>-</td>
        </tr>
        <tr>
            <td><strong>TOTAL</strong></td>
            <td><strong>${data.total_count_quotes}</strong></td>
            <td><strong>USD ${data.total_amount_quotes.toLocaleString('es-AR', {minimumFractionDigits: 2})}</strong></td>
            <td>-</td>
        </tr>
    `;

    const dataB = window.summaryTableBookings;
    if (!dataB || !Object.keys(dataB).length) return;

    const tbody_bookings = document.getElementById("summary-bookings-tbody");
    if (!tbody_bookings) return;

    tbody_bookings.innerHTML = `
        <tr>
            <td>Promedio x día:</td>
            <td>${dataB.average_bookings_quantity}</td>
            <td>USD ${dataB.average_bookings_amount.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>-</td>
        </tr>
        <tr>
            <td>Audley:</td>
            <td>${dataB.audley_count_bookings}</td>
            <td>USD ${dataB.audley_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.audley_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Individuales:</td>
            <td>${dataB.individual_count_bookings}</td>
            <td>USD ${dataB.individual_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.individual_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Grupos:</td>
            <td>${dataB.group_count_bookings}</td>
            <td>USD ${dataB.group_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.group_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>FAM clientes:</td>
            <td>${dataB.fam_count_bookings}</td>
            <td>USD ${dataB.fam_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.fam_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>${data.this_season_str}</td>
            <td>${dataB.this_season_count_bookings}</td>
            <td>USD ${dataB.this_season_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.this_season_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>${data.next_season_str}</td>
            <td>${dataB.next_season_count_bookings}</td>
            <td>USD ${dataB.next_season_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
            <td>% ${dataB.next_season_perc_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
        </tr>
        <tr>
            <td>Cambios:</td>
            <td>${dataB.total_changes_bookings}</td>
            <td>-</td>
            <td>-</td>
        </tr>
        <tr>
            <td><strong>TOTAL</strong></td>
            <td><strong>${dataB.total_count_bookings}</strong></td>
            <td><strong>USD ${dataB.total_amount_bookings.toLocaleString('es-AR', {minimumFractionDigits: 2})}</strong></td>
            <td>-</td>
        </tr>
    `;
    const working_days = document.getElementById('working-days');
    working_days.innerHTML = `Días Laborables: ${data.working_days}`;

    const average_difficulty = document.getElementById('average-difficulty');
    average_difficulty.innerHTML = `Promedio: ${data.average_difficulty.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;

    const difficulty_1 = document.getElementById('difficulty-1');
    difficulty_1.innerHTML = `Muy fácil: ${data.difficulty_1}`;

    const difficulty_2 = document.getElementById('difficulty-2');
    difficulty_2.innerHTML = `Fácil: ${data.difficulty_2}`;

    const difficulty_3 = document.getElementById('difficulty-3');
    difficulty_3.innerHTML = `Moderado: ${data.difficulty_3}`;

    const difficulty_4 = document.getElementById('difficulty-4');
    difficulty_4.innerHTML = `Complejo: ${data.difficulty_4}`;

    const difficulty_5 = document.getElementById('difficulty-5');
    difficulty_5.innerHTML = `Muy complejo: ${data.difficulty_5}`;

    const cancellations_count = document.getElementById('cancellations-count');
    cancellations_count.innerHTML = `Cantidad: ${dataB.cancellations_count}`;

    const cancellations_amount = document.getElementById('cancellations-amount');
    cancellations_amount.innerHTML = `Monto: - USD ${dataB.cancellations_amount.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;

    const conversion_perc = document.getElementById('conversion-perc');
    conversion_perc.innerHTML = `General: % ${dataB.conversion_perc.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;

    const conversion_perc_audley = document.getElementById('conversion-perc-audley');
    conversion_perc_audley.innerHTML = `General: % ${dataB.conversion_perc_audley.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
}


// ==================== FUNCIÓN: Renderizar tabla ====================
function renderVendorTableQuote() {

    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#vendor-quote-table")) {
        $("#vendor-quote-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('vendor-quote-tbody');
    const tfoot = document.getElementById('vendor-quote-tfoot'); // ⚠️ nuevo
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }
    const totalMontoA = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.montoA, 0);
    
    tbody.innerHTML = '';
    tfoot.innerHTML = '';
    
    Object.entries(vendorQuoteData).forEach(([vendor, vals]) => {
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
            <td style="${cellStyle}">${vals.workingDays}</td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">${vals.a}</td>
            <td style="${cellStyle}">${vals.audleyA}</td>
            <td style="${cellStyle}">USD ${vals.montoA.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${perc}%</td>
        `;
        tbody.appendChild(row);
    });
    
    // 🔹 Agregar fila total al TFOOT
    const totalCotizaciones = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.total, 0);
    const totalA = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.a, 0);
    const totalAudleyA = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.audleyA, 0);

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>-</td>
        <td>${totalCotizaciones}</td>
        <td>${totalA}</td>
        <td>${totalAudleyA}</td>
        <td>USD ${totalMontoA.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
    `;
    tfoot.appendChild(totalRow);
    
    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("vendor-quote-table");
    
}

// ==================== FUNCIÓN: Renderizar tabla ====================
function renderVendorTableBooking() {

    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#vendor-booking-table")) {
        $("#vendor-booking-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('vendor-booking-tbody');
    const tfoot = document.getElementById('vendor-booking-tfoot'); // ⚠️ nuevo
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }
    const totalAmountFirst = Object.values(vendorBookingData).reduce((acc, v) => acc + v.amountFirst, 0);
    
    tbody.innerHTML = '';
    tfoot.innerHTML = '';
    
    Object.entries(vendorBookingData).forEach(([vendor, vals]) => {
        const perc = totalAmountFirst > 0 ? ((vals.amountFirst / totalAmountFirst) * 100).toFixed(2) : 0;

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
            <td style="${cellStyle}">${vals.workingDays}</td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">${vals.first}</td>
            <td style="${cellStyle}">${vals.audleyFirst}</td>
            <td style="${cellStyle}">USD ${vals.amountFirst.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${perc}%</td>
        `;
        tbody.appendChild(row);
    });
    
    // 🔹 Agregar fila total al TFOOT
    const totalBookings = Object.values(vendorBookingData).reduce((acc, v) => acc + v.total, 0);
    const totalFirst = Object.values(vendorBookingData).reduce((acc, v) => acc + v.first, 0);
    const totalAudleyFirst = Object.values(vendorBookingData).reduce((acc, v) => acc + v.audleyFirst, 0);

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>-</td>
        <td>${totalBookings}</td>
        <td>${totalFirst}</td>
        <td>${totalAudleyFirst}</td>
        <td>USD ${totalAmountFirst.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
    `;
    tfoot.appendChild(totalRow);
    
    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("vendor-booking-table");
    
}

// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderChartsQuotes() {
    const vendors = Object.keys(vendorQuoteData);
    const cotizacionesA = vendors.map(v => vendorQuoteData[v].a);
    const montosA = vendors.map(v => vendorQuoteData[v].montoA);
    
    // ✅ CORRECTO: Acceder al color dentro de cada vendedor
    const colors = vendors.map(vendor => vendorQuoteData[vendor].color || '#999999');
    
    // Destruir gráficos anteriores
    if (chartsQuotes.cantidad) chartsQuotes.cantidad.destroy();
    if (chartsQuotes.monto) chartsQuotes.monto.destroy();

    // Gráfico de Cantidad
    const ctxCantidad = document.getElementById('chartCantidadCanvas').getContext('2d');
    chartsQuotes.cantidad = new Chart(ctxCantidad, {
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
    chartsQuotes.monto = new Chart(ctxMonto, {
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

// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderChartsBookings() {
    const vendors = Object.keys(vendorBookingData);
    const bookingsFirst = vendors.map(v => vendorBookingData[v].first);
    const amountFirst = vendors.map(v => vendorBookingData[v].amountFirst);
    
    // ✅ CORRECTO: Acceder al color dentro de cada vendedor
    const colors = vendors.map(vendor => vendorBookingData[vendor].color || '#999999');
    
    // Destruir gráficos anteriores
    if (chartsBookings.cantidad) chartsBookings.cantidad.destroy();
    if (chartsBookings.monto) chartsBookings.monto.destroy();

    // Gráfico de Cantidad
    const ctxCantidad = document.getElementById('chartCantidadBookingsCanvas').getContext('2d');
    chartsBookings.cantidad = new Chart(ctxCantidad, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: bookingsFirst,
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
    const ctxMonto = document.getElementById('chartMontoBookingsCanvas').getContext('2d');
    chartsBookings.monto = new Chart(ctxMonto, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: amountFirst,
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
function renderInsightsQuotes() {
    const vendors = Object.keys(vendorQuoteData);
    const topVendor = vendors.reduce((max, vendor) => 
        vendorQuoteData[vendor].montoA > vendorQuoteData[max].montoA ? vendor : max
    );
    
    const totalMonto = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.montoA, 0);
    const totalCotizaciones = Object.values(vendorQuoteData).reduce((acc, v) => acc + v.a, 0);
    const promedio = totalMonto / vendors.length;

    const insights = `
        <ul>
            <li><strong>🏆 Top Vendedor:</strong> ${topVendor} con USD ${vendorQuoteData[topVendor].montoA.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>💰 Facturación Total:</strong> USD ${totalMonto.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>📊 Total Cotizaciones A:</strong> ${totalCotizaciones} cotizaciones</li>
            <li><strong>📈 Promedio por Vendedor:</strong> USD ${promedio.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>👥 Vendedores Activos:</strong> ${vendors.length}</li>
        </ul>
    `;

    document.getElementById('insights-content-quotes').innerHTML = insights;
}

// ==================== FUNCIÓN: Renderizar insights ====================
function renderInsightsBookings() {
    const vendors = Object.keys(vendorBookingData);
    const topVendor = vendors.reduce((max, vendor) => 
        vendorBookingData[vendor].amountFirst > vendorBookingData[max].amountFirst ? vendor : max
    );
    
    const totalMonto = Object.values(vendorBookingData).reduce((acc, v) => acc + v.amountFirst, 0);
    const totalBookings = Object.values(vendorBookingData).reduce((acc, v) => acc + v.first, 0);
    const promedio = totalMonto / vendors.length;

    const insights = `
        <ul>
            <li><strong>🏆 Top Vendedor:</strong> ${topVendor} con USD ${vendorBookingData[topVendor].amountFirst.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>💰 Facturación Total:</strong> USD ${totalMonto.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>📊 Total Bookings 1:</strong> ${totalBookings} bookings</li>
            <li><strong>📈 Promedio por Vendedor:</strong> USD ${promedio.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>👥 Vendedores Activos:</strong> ${vendors.length}</li>
        </ul>
    `;

    document.getElementById('insights-content-bookings').innerHTML = insights;
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