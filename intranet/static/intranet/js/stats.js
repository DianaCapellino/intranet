document.addEventListener('DOMContentLoaded', async () => {
    // ✅ Detectar si estamos en la página de entradas de estadísticas
    if (window.location.pathname.startsWith("/stats/entries/")) {

        const params = new URLSearchParams(window.location.search);
        const filters = Object.fromEntries(params.entries());

        if (filters.filter === "monthly") {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        } else if (filters.filter === "weekly") {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
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
        if (contentEl) {
            contentEl.style.display = 'block';
            loadingEl.classList.add('d-none');
        }

        // Drill-down DataTable (visible when user_filter or client_filter is in URL)
        const drillUser = filters.user_filter;
        const drillClient = filters.client_filter;
        if (drillUser || drillClient) {
            const drillSection = document.getElementById('section-drilldown');
            const drillTitle = document.getElementById('drilldown-title');
            if (drillSection && drillTitle) {
                drillSection.classList.remove('d-none');
                const label = drillUser ? `Entradas — ${drillUser}` : `Entradas — ${drillClient}`;
                drillTitle.textContent = `📋 Detalle: ${label}`;
                const dtParams = Object.assign({}, filters, { type: 'entries' });
                new DataTable('#drilldown-table', {
                    processing: true,
                    serverSide: true,
                    ajax: { url: '/stats/data/', type: 'GET', data: d => Object.assign(d, dtParams) },
                    columns: [
                        { title: 'Fecha', data: 'starting_date' },
                        { title: 'Respuesta', data: 'closing_date' },
                        { title: 'Viaje', data: 'trip' },
                        { title: 'Status', data: 'status' },
                        { title: 'Monto', data: 'amount' },
                        { title: 'Cliente', data: 'client' },
                        { title: 'Cot. por', data: 'user_creator' },
                        { title: 'Trab. por', data: 'user_working' },
                        { title: 'Fecha Viaje', data: 'travelling_date' },
                    ],
                    language: { url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json' },
                    lengthMenu: [[25, 50, -1], [25, 50, 'Todos']],
                    order: [[0, 'asc']]
                });
                drillSection.scrollIntoView({ behavior: 'smooth' });
            }
        }

        // Buttons listeners
        const exportPdf = document.querySelector('.btn-export');
        if (exportPdf) {
            exportPdf.addEventListener('click', (e) => {
                console.log("🟢 Listener de exportación activado por clase.");
                exportToPDF(e);
            });
        };

        const btnWarnings = document.querySelectorAll('.btn-warnings');
        if (btnWarnings) {
            btnWarnings.forEach((btn) => {
                btn.addEventListener('click', () => {
                    btn.parentNode.classList.add("d-none");
                });
            });
        }

        // 🛑 IMPORTANTE: no ejecutar el resto del JS (DataTables, formularios, etc.)
        return;
    }

    // ✅ Detectar si estamos en la página de viajes
    if (window.location.pathname.startsWith("/stats/trips/")) {

        const params = new URLSearchParams(window.location.search);
        const filters = Object.fromEntries(params.entries());

        if (filters.filter === "monthly") {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        } else if (filters.filter === "weekly") {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        } else {
            const reportPeriod = `${filters.date_from || ''} → ${filters.date_to || ''}`;
            const periodEl = document.getElementById('report-period');
            if (periodEl) periodEl.textContent = `Período: ${reportPeriod}`;
        };

        // Llamar a la función que obtiene los datos del backend
        await generatePresentationTripsData(filters);

        // Mostrar contenido cuando los datos llegan
        const loadingEl = document.getElementById('loading');
        const contentEl = document.getElementById('report-content');
        if (loadingEl) loadingEl.classList.remove('show');
        if (contentEl) {
            contentEl.style.display = 'block';
            loadingEl.classList.add('d-none');
        }

        // Drill-down DataTable (visible when vr_filter, op_filter or client_filter is in URL)
        const drillVR = filters.vr_filter;
        const drillOP = filters.op_filter;
        const drillClient = filters.client_filter;
        if (drillVR || drillOP || drillClient) {
            const drillSection = document.getElementById('section-drilldown');
            const drillTitle = document.getElementById('drilldown-title');
            if (drillSection && drillTitle) {
                drillSection.classList.remove('d-none');
                const label = drillVR ? `VR: ${drillVR}` : drillOP ? `OP: ${drillOP}` : `Cliente: ${drillClient}`;
                drillTitle.textContent = `📋 Detalle viajes — ${label}`;
                const dtParams = Object.assign({}, filters, { type: 'trips' });
                new DataTable('#drilldown-table', {
                    processing: true,
                    serverSide: true,
                    ajax: { url: '/stats/data/', type: 'GET', data: d => Object.assign(d, dtParams) },
                    columns: [
                        { title: 'Viaje', data: 'name' },
                        { title: 'Cliente', data: 'client' },
                        { title: 'Contacto', data: 'contact' },
                        { title: 'Referencia', data: 'reference' },
                        { title: 'Fecha Viaje', data: 'travelling_date' },
                        { title: 'Monto', data: 'amount' },
                        { title: 'Dificultad', data: 'difficulty' },
                        { title: 'VR', data: 'responsable_user' },
                        { title: 'OP', data: 'operations_user' },
                    ],
                    language: { url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json' },
                    lengthMenu: [[25, 50, -1], [25, 50, 'Todos']],
                    order: [[4, 'asc']]
                });
                drillSection.scrollIntoView({ behavior: 'smooth' });
            }
        }

        // Buttons listeners
        const exportPdf = document.querySelector('.btn-export');
        if (exportPdf) {
            exportPdf.addEventListener('click', (e) => {
                console.log("🟢 Listener de exportación activado por clase.");
                exportToPDF(e);
            });
        };

        const btnWarnings = document.querySelectorAll('.btn-warnings');
        if (btnWarnings) {
            btnWarnings.forEach((btn) => {
                btn.addEventListener('click', () => {
                    btn.parentNode.classList.add("d-none");
                });
            });
        }

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
            initialView: 'multiMonthYear',
            events: '/holidays/json',
            headerToolbar: {
              left: 'prev,next today',
              center: 'title',
              right: 'multiMonthYear,dayGridMonth,timeGridWeek'
            },
            multiMonthMaxColumns: 3,  // columnas de meses (3 = 4 filas de 3)
        });
        calendar.render();
    };

})

let reportPeriod = '';

// ==================== DATA ENTRIES ====================
let vendorQuoteData = {};
let vendorBookingData = {};
let chartsQuotes = {};
let chartsBookings = {};
let chartsTripsVendor = {};
let chartsTripsOperator = {};
let chartsClients = {};
let vendorSpeedData = {};
let summarySpeed = {};
let summaryClients = {};

// ==================== DATA TRIPS ====================
let vendorTripsData = {};
let operatorTripsData = {};
let clientTripsData = {};
let chartsClientsTrips = {};

// ==================== MONTHLY BREAKDOWN ====================
let monthlyBreakdownEntries = [];
let monthlyBreakdownTrips   = [];
let monthlyByVendorEntries  = {};
let monthlyByClientEntries  = {};
let monthlyByVrTrips        = {};
let monthlyByOperatorTrips  = {};
let monthlyByClientTrips    = {};


// drill-down link helper — builds URL with current period params + specific filter
// showAll: if true, appends show_all=1 (for entries page to include closed/sent entries)
// statusFilter: if set, appends status_filter=<value> (e.g. "Booking" for trips stats)
function buildDrillDownUrl(basePath, filterKey, filterValue, showAll = false, statusFilter = "") {
    const current = new URLSearchParams(window.location.search);
    const out = new URLSearchParams();
    ['date_from', 'date_to', 'month', 'year', 'week', 'season', 'filter'].forEach(k => {
        if (current.has(k)) out.set(k, current.get(k));
    });
    out.set(filterKey, filterValue);
    if (showAll) out.set('show_all', '1');
    if (statusFilter) out.set('status_filter', statusFilter);
    return `${basePath}?${out.toString()}`;
}

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
        window.byTypeQuotes = result.by_type_quotes || [];
        window.byTypeBookings = result.by_type_bookings || [];
        window.bySeasonQuotes = result.by_season_quotes || [];
        window.bySeasonBookings = result.by_season_bookings || [];

        window.vendorSpeedData = result.response_speed?.vendors || {};
        window.summarySpeed = result.summary_speed?.summary || {};

        window.summaryClients = result.clients || {};
        monthlyBreakdownEntries = result.monthly_breakdown || [];
        monthlyByVendorEntries  = result.monthly_by_vendor || {};
        monthlyByClientEntries  = result.monthly_by_client || {};

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

        // ⚠️ Asignar a la variable que usa renderReport Bookings
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
            const conversionCount = parseInt(vals.conversionCount|| 0, 10) || 0;
            const color = vals.color;
            normalizedBookings[vendor] = {
                workingDays,
                total,
                first,
                audleyFirst,
                amountFirst,
                conversionCount,
                color
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorBookingData = normalizedBookings;

        console.log("📊 Datos recibidos y normalizados Bookings:", vendorBookingData);

        // ⚠️ Asignar a la variable que usa renderReport Bookings
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedSpeed = {};
        const rawS = result.summary_speed.vendors || result || {};

        console.log(rawS);

        Object.entries(rawS).forEach(([vendor, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const totalTotal = parseInt(vals.total.total || 0, 10) || 0;
            const totalSameDay = parseInt(vals.total.same_day || 0, 10) || 0;
            const totalOneDay = parseInt(vals.total.one_day || 0, 10) || 0;
            const totalTwoDays = parseInt(vals.total.two_days || 0, 10) || 0;
            const totalThreeDays = parseInt(vals.total.three_days || 0, 10) || 0;
            const totalFourDays = parseInt(vals.total.four_days || 0, 10) || 0;
            const totalFiveDays = parseInt(vals.total.five_days || 0, 10) || 0;
            const totalMoreDays = parseInt(vals.total.more_days || 0, 10) || 0;
            const totalUnanswered = parseInt(vals.total.unanswered || 0, 10) || 0;
            const totalAverageDays = parseFloat(vals.total.average || 0, 10) || 0;

            const quotesTotal = parseInt(vals.quotes.total || 0, 10) || 0;
            const quotesSameDay = parseInt(vals.quotes.same_day || 0, 10) || 0;
            const quotesOneDay = parseInt(vals.quotes.one_day || 0, 10) || 0;
            const quotesTwoDays = parseInt(vals.quotes.two_days || 0, 10) || 0;
            const quotesThreeDays = parseInt(vals.quotes.three_days || 0, 10) || 0;
            const quotesFourDays = parseInt(vals.quotes.four_days || 0, 10) || 0;
            const quotesFiveDays = parseInt(vals.quotes.five_days || 0, 10) || 0;
            const quotesMoreDays = parseInt(vals.quotes.more_days || 0, 10) || 0;
            const quotesUnanswered = parseInt(vals.quotes.unanswered || 0, 10) || 0;
            const quotesAverageDays = parseFloat(vals.quotes.average || 0, 10) || 0;

            const bookingsTotal = parseInt(vals.bookings.total || 0, 10) || 0;
            const bookingsSameDay = parseInt(vals.bookings.same_day || 0, 10) || 0;
            const bookingsOneDay = parseInt(vals.bookings.one_day || 0, 10) || 0;
            const bookingsTwoDays = parseInt(vals.bookings.two_days || 0, 10) || 0;
            const bookingsThreeDays = parseInt(vals.bookings.three_days || 0, 10) || 0;
            const bookingsFourDays = parseInt(vals.bookings.four_days || 0, 10) || 0;
            const bookingsFiveDays = parseInt(vals.bookings.five_days || 0, 10) || 0;
            const bookingsMoreDays = parseInt(vals.bookings.more_days || 0, 10) || 0;
            const bookingsUnanswered = parseInt(vals.bookings.unanswered || 0, 10) || 0;
            const bookingsAverageDays = parseFloat(vals.bookings.average || 0, 10) || 0;

            const finalsTotal = parseInt(vals.finals.total || 0, 10) || 0;
            const finalsSameDay = parseInt(vals.finals.same_day || 0, 10) || 0;
            const finalsOneDay = parseInt(vals.finals.one_day || 0, 10) || 0;
            const finalsTwoDays = parseInt(vals.finals.two_days || 0, 10) || 0;
            const finalsThreeDays = parseInt(vals.finals.three_days || 0, 10) || 0;
            const finalsFourDays = parseInt(vals.finals.four_days || 0, 10) || 0;
            const finalsFiveDays = parseInt(vals.finals.five_days || 0, 10) || 0;
            const finalsMoreDays = parseInt(vals.finals.more_days || 0, 10) || 0;
            const finalsUnanswered = parseInt(vals.finals.unanswered || 0, 10) || 0;
            const finalsAverageDays = parseFloat(vals.finals.average || 0, 10) || 0;
            const color = vals.color;

            normalizedSpeed[vendor] = {
                color,
                totalTotal, totalSameDay, totalOneDay, totalTwoDays, totalThreeDays,
                totalFourDays, totalFiveDays, totalMoreDays, totalUnanswered, totalAverageDays,
                quotesTotal, quotesSameDay, quotesOneDay, quotesTwoDays, quotesThreeDays,
                quotesFourDays, quotesFiveDays, quotesMoreDays, quotesUnanswered, quotesAverageDays,
                bookingsTotal, bookingsSameDay, bookingsOneDay, bookingsTwoDays, bookingsThreeDays,
                bookingsFourDays, bookingsFiveDays, bookingsMoreDays, bookingsUnanswered, bookingsAverageDays,
                finalsTotal, finalsSameDay, finalsOneDay, finalsTwoDays, finalsThreeDays,
                finalsFourDays, finalsFiveDays, finalsMoreDays, finalsUnanswered, finalsAverageDays,
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorSpeedData = normalizedSpeed;

        console.log("📊 Datos recibidos y normalizados Rapidez:", vendorSpeedData);

        // ⚠️ Asignar a la variable que usa renderReport Bookings
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedClients = {};
        const rawC = result.clients || result || {};
        Object.entries(rawC).forEach(([client, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const quotesCount = parseInt(vals.quotesCount || 0, 10) || 0;
            const quotesAmount = parseFloat(vals.quotesAmount || 0) || 0;
            const bookingsCount = parseInt(vals.bookingsCount || 0, 10) || 0;
            const bookingsAmount = parseFloat(vals.bookingsAmount || 0) || 0;
            const others = parseInt(vals.others || 0, 10) || 0;

            normalizedClients[client] = {
                quotesCount,
                quotesAmount,
                bookingsCount,
                bookingsAmount,
                others,
            };
        });

        // Guardamos en la variable global que usan las funciones
        summaryClients = normalizedClients;

        console.log("📊 Datos recibidos y normalizados Clientes:", normalizedClients);

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

async function generatePresentationTripsData(filters = {}) {
    try {
        // Construir query string (para filtros personalizados)
        const params = new URLSearchParams(filters);
        const response = await fetch(`/stats/data/trips/presentation/?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();

        // Guardamos el objeto global para reutilizarlo
        window.summaryTableTrips = result.summary_table_trips || {};
        window.byTypeTrips       = result.by_type_trips       || [];
        window.vendorTripsData = result.trips_by_responsable || {};
        window.operatorTripsData = result.trips_by_operator || {};
        window.clientTripsData = result.clients || {};
        monthlyBreakdownTrips   = result.monthly_breakdown || [];
        monthlyByVrTrips        = result.monthly_by_vr || {};
        monthlyByOperatorTrips  = result.monthly_by_operator || {};
        monthlyByClientTrips    = result.monthly_by_client || {};

        // ⚠️ Asignar a la variable que usa renderReport Quotes
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedVendors = {};
        const raw = result.trips_by_responsable || result || {};
        Object.entries(raw).forEach(([vendor, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const total = parseInt(vals.total || 0, 10) || 0;
            const amountTotal = parseFloat(vals.amountTotal || 0) || 0;
            const audley = parseInt(vals.audley || vals.audley || 0, 10) || 0;
            const amountAudley = parseFloat(vals.amountAudley || 0) || 0;

            const color = vals.color;
            const workingDays = parseInt(vals.workingDays || 0, 10) || 0;

            normalizedVendors[vendor] = {
                total,
                amountTotal,
                audley,
                amountAudley,
                color,
                workingDays,
            };
        });

        // Guardamos en la variable global que usan las funciones
        vendorTripsData = normalizedVendors;

        console.log("📊 Datos recibidos y normalizados Viajes x Vendedor:", vendorTripsData);

        // ⚠️ Asignar a la variable que usa renderReport Bookings
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedOperators = {};
        const rawB = result.trips_by_operator || result || {};
        Object.entries(rawB).forEach(([operator, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar           
            const total = parseInt(vals.total || 0, 10) || 0;
            const amountTotal = parseFloat(vals.amountTotal || 0) || 0;
            const audley = parseInt(vals.audley || vals.audley || 0, 10) || 0;
            const amountAudley = parseFloat(vals.amountAudley || 0) || 0;

            const color = vals.color;
            const workingDays = parseInt(vals.workingDays || 0, 10) || 0;

            normalizedOperators[operator] = {
                total,
                amountTotal,
                audley,
                amountAudley,
                color,
                workingDays,
            };
        });

        // Guardamos en la variable global que usan las funciones
        operatorTripsData = normalizedOperators;

        console.log("📊 Datos recibidos y normalizados Viajes x Operador:", operatorTripsData);

        // ⚠️ Asignar a la variable que usa renderReport Quotes
        // Normalizar el objeto y asegurarnos que los montos sean números
        const normalizedClients = {};
        const rawC = result.clients || result || {};
        Object.entries(rawC).forEach(([client, vals]) => {
            // defensivo: si vals vino como string o faltan campos, normalizar
            const total = parseInt(vals.bookingsCount || 0, 10) || 0;
            const amountTotal = parseFloat(vals.bookingsAmount || 0) || 0;
            const cancelled = parseInt(vals.cancelled || 0, 10) || 0;
            const totalDifficulty = parseInt(vals.totalDifficulty || 0, 10) || 0;

            normalizedClients[client] = {
                total,
                amountTotal,
                cancelled,
                totalDifficulty,
            };
        });

        // Guardamos en la variable global que usan las funciones
        clientTripsData = normalizedClients;

        console.log("📊 Datos recibidos y normalizados Viajes x Cliente:", clientTripsData);


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

// Estado de carga de secciones
const sectionsLoaded = {
    general: false,
    vendor: false,
    speed: false,
    client: false
};

// ==================== Cargar sección específica Entries ====================
async function loadSection(sectionName) {
    // Si ya está cargada, no hacer nada
    if (sectionsLoaded[sectionName]) {
        console.log(`✅ Sección ${sectionName} ya estaba cargada`);
        return;
    }

    console.log(`🔄 Cargando sección: ${sectionName}`);

    try {
        switch(sectionName) {
            case 'general':
                renderSummaryTables();
                renderMonthlyBreakdown('entries');
                sectionsLoaded.general = true;
                break;
                
            case 'vendor':
                renderVendorTableQuote();
                renderVendorTableBooking();
                renderMonthlyByVendorEntries();
                renderChartsQuotes();
                renderChartsBookings();
                renderInsightsQuotes();
                renderInsightsBookings();
                sectionsLoaded.vendor = true;
                break;

            case 'speed':
                renderResponseSpeed();
                renderResponseSpeedVendor("speed-total");
                renderChartsSpeed();
                sectionsLoaded.speed = true;
                break;

            case 'client':
                renderClients();
                renderMonthlyByClientEntries();
                renderChartsClients();
                sectionsLoaded.client = true;
                break;
        }
        
        console.log(`✅ Sección ${sectionName} cargada correctamente`);
        
    } catch (error) {
        console.error(`❌ Error cargando sección ${sectionName}:`, error);
    }
}

// Estado de carga de secciones
const sectionsLoadedTrips = {
    general: false,
    user: false,
    client: false
};

// ==================== Cargar sección específica Trips ====================
async function loadSectionTrip(sectionName) {
    // Si ya está cargada, no hacer nada
    if (sectionsLoadedTrips[sectionName]) {
        console.log(`✅ Sección ${sectionName} ya estaba cargada`);
        return;
    }

    console.log(`🔄 Cargando sección: ${sectionName}`);

    try {
        switch(sectionName) {
            case 'general':
                renderSummaryTrips();
                renderMonthlyBreakdown('trips');
                sectionsLoadedTrips.general = true;
                break;
                
            case 'user':
                renderVendorTrips();
                renderOperatorTrips();
                renderMonthlyByVrTrips();
                renderMonthlyByOperatorTrips();
                renderChartsTripsVendors();
                renderChartsTripsOperators();
                renderInsightsTripsVendors();
                renderInsightsTripsOperators();
                sectionsLoadedTrips.user = true;
                break;

            case 'client':
                renderTripsClients();
                renderMonthlyByClientTrips();
                renderChartsTripsClients();
                sectionsLoadedTrips.client = true;
                break;
        }
        
        console.log(`✅ Sección ${sectionName} cargada correctamente`);
        
    } catch (error) {
        console.error(`❌ Error cargando sección ${sectionName}:`, error);
    }
}

// ==================== Exportar sección a PDF ====================
async function exportSectionToPDF(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) {
        alert('Sección no encontrada');
        return;
    }

    const { jsPDF } = window.jspdf;

    try {
        // ── Capture chart-box positions BEFORE html2canvas (layout is untouched here) ──
        const PAD_CSS = 12; // padding in CSS px around each protected block
        const sectionRectPre = section.getBoundingClientRect();
        const rawBlocks = [];
        section.querySelectorAll('.chart-box').forEach(el => {
            const r = el.getBoundingClientRect();
            rawBlocks.push({
                cssTop:    r.top    - sectionRectPre.top - PAD_CSS,
                cssBottom: r.bottom - sectionRectPre.top + PAD_CSS,
            });
        });

        const canvas = await html2canvas(section, {
            scale: 2,
            logging: false,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            windowWidth: section.scrollWidth,
            ignoreElements: (el) => {
                const cl = el.classList;
                if (cl.contains('dt-layout-row') && !cl.contains('dt-layout-table')) return true;
                if (cl.contains('dt-search') || cl.contains('dt-buttons') ||
                    cl.contains('dt-length') || cl.contains('dt-paging') ||
                    cl.contains('dt-info')) return true;
                if (el.tagName === 'DIV' && cl.contains('mb-3') &&
                    el.querySelector('[onclick*="exportSectionToPDF"],[onclick*="window.print"]')) return true;
                return false;
            },
        });

        const pdf = new jsPDF('p', 'mm', 'a4');
        const pageW = pdf.internal.pageSize.getWidth();   // 210
        const pageH = pdf.internal.pageSize.getHeight();  // 297
        const margin = 10;
        const contentW = pageW - 2 * margin;  // 190
        const contentH = pageH - 2 * margin;  // 277

        const pxPerMm  = canvas.width / contentW;
        const slicePx  = Math.floor(contentH * pxPerMm);

        // Convert pre-captured CSS positions → canvas pixels using actual rendered ratio
        const cssToCanvas  = canvas.height / section.scrollHeight;
        const protectedBlocks = rawBlocks.map(({ cssTop, cssBottom }) => ({
            top:    Math.max(0,            Math.floor(cssTop    * cssToCanvas)),
            bottom: Math.min(canvas.height, Math.ceil(cssBottom * cssToCanvas)),
        }));

        // ── Find a safe cut: avoid slicing inside any protected block ──
        function safeCut(prevY, ideal) {
            const MIN_PAGE = slicePx * 0.25;
            for (const { top, bottom } of protectedBlocks) {
                if (ideal > top && ideal < bottom) {
                    if (top > prevY && (top - prevY) >= MIN_PAGE) {
                        return top;    // cut just before the block
                    }
                    return bottom;     // block too close to page start → push past it
                }
            }
            return ideal;
        }

        // ── Build page slices ──
        const slices = [];
        let prevY = 0;
        while (prevY < canvas.height) {
            const ideal = prevY + slicePx;
            if (ideal >= canvas.height) {
                slices.push({ srcY: prevY, srcH: canvas.height - prevY });
                break;
            }
            const cutY = safeCut(prevY, ideal);
            slices.push({ srcY: prevY, srcH: cutY - prevY });
            prevY = cutY;
        }

        // ── Render one PDF page per slice ──
        for (let i = 0; i < slices.length; i++) {
            if (i > 0) pdf.addPage();
            const { srcY, srcH } = slices[i];

            const slice = document.createElement('canvas');
            slice.width  = canvas.width;
            slice.height = srcH;
            slice.getContext('2d').drawImage(
                canvas, 0, srcY, canvas.width, srcH, 0, 0, canvas.width, srcH
            );

            const sliceH_mm = srcH / pxPerMm;
            pdf.addImage(slice.toDataURL('image/png'), 'PNG', margin, margin, contentW, sliceH_mm);
        }

        pdf.save(`estadisticas-${sectionId}-${new Date().toISOString().split('T')[0]}.pdf`);

    } catch (error) {
        console.error('Error generando PDF:', error);
        alert('Error al generar el PDF');
    }
}


// ==================== MONTHLY BREAKDOWN ====================
function renderMonthlyBreakdown(type) {
    const data = type === 'trips' ? monthlyBreakdownTrips : monthlyBreakdownEntries;
    const containerId = type === 'trips' ? 'monthly-breakdown-trips' : 'monthly-breakdown-entries';
    const chartId     = type === 'trips' ? 'chartMonthlyTrips'       : 'chartMonthlyEntries';

    const container = document.getElementById(containerId);
    if (!container) return;

    if (!data || data.length < 2) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const labels  = data.map(r => r.label);
    const fmt     = v => `USD ${(+v || 0).toLocaleString('en-US', { minimumFractionDigits: 0 })}`;

    // ── Table ──
    const tbodyId = containerId + '-tbody';
    const tbody = document.getElementById(tbodyId);
    if (tbody) {
        tbody.innerHTML = '';
        data.forEach(r => {
            const tr = document.createElement('tr');
            if (type === 'entries') {
                tr.innerHTML = `
                    <td>${r.label}</td>
                    <td>${r.quotes_count}</td>
                    <td>${fmt(r.quotes_amount)}</td>
                    <td>${r.bookings_count}</td>
                    <td>${fmt(r.bookings_amount)}</td>
                    <td>${r.active_vendors}</td>
                `;
            } else {
                tr.innerHTML = `
                    <td>${r.label}</td>
                    <td>${r.bookings_count}</td>
                    <td>${fmt(r.bookings_amount)}</td>
                    <td>${(r.avg_rent || 0).toFixed(1)} %</td>
                    <td>${r.cancellations_count}</td>
                `;
            }
            tbody.appendChild(tr);
        });
    }

    // ── Chart ──
    const canvas = document.getElementById(chartId);
    if (!canvas) return;

    // destroy previous instance if exists
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();

    const datasets = type === 'entries'
        ? [
            { label: 'Quotes (cant.)',    data: data.map(r => r.quotes_count),    type: 'bar',  yAxisID: 'yCount', backgroundColor: 'rgba(99,179,237,0.6)' },
            { label: 'Bookings (cant.)',   data: data.map(r => r.bookings_count),  type: 'bar',  yAxisID: 'yCount', backgroundColor: 'rgba(72,187,120,0.6)' },
            { label: 'Fact. Bookings',     data: data.map(r => r.bookings_amount), type: 'line', yAxisID: 'yAmount', borderColor: 'rgba(237,137,54,1)', backgroundColor: 'transparent', tension: 0.3, pointRadius: 4 },
          ]
        : [
            { label: 'Bookings (cant.)',   data: data.map(r => r.bookings_count),  type: 'bar',  yAxisID: 'yCount', backgroundColor: 'rgba(72,187,120,0.6)' },
            { label: 'Facturación',        data: data.map(r => r.bookings_amount), type: 'line', yAxisID: 'yAmount', borderColor: 'rgba(237,137,54,1)', backgroundColor: 'transparent', tension: 0.3, pointRadius: 4 },
            { label: 'Cancelaciones',      data: data.map(r => r.cancellations_count), type: 'bar', yAxisID: 'yCount', backgroundColor: 'rgba(252,129,129,0.6)' },
          ];

    new Chart(canvas, {
        data: { labels, datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
                yCount:  { type: 'linear', position: 'left',  title: { display: true, text: 'Cantidad' }, beginAtZero: true },
                yAmount: { type: 'linear', position: 'right', title: { display: true, text: 'USD' },      beginAtZero: true, grid: { drawOnChartArea: false } },
            },
        },
    });
}


// ==================== MONTHLY BY VENDOR/CLIENT/VR/OPERATOR ====================

const PALETTE = [
    '#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f',
    '#edc948','#b07aa1','#ff9da7','#9c755f','#bab0ac',
    '#d37295','#fabfd2','#8cd17d','#b6992d','#499894',
];

function _buildMultiLineChart(canvasId, labels, datasets) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    new Chart(canvas, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { stacked: false },
                y: { beginAtZero: true, title: { display: true, text: 'Cantidad' } },
            },
        },
    });
}

function _buildMonthlyMultiDatasets(dataByKey, field, colorOffset) {
    const allMonths = new Set();
    Object.values(dataByKey).forEach(rows => rows.forEach(r => allMonths.add(r.month_key)));
    const sortedMonths = [...allMonths].sort();
    const labels = sortedMonths.map(mk => {
        const firstMatch = Object.values(dataByKey).flatMap(r => r).find(r => r.month_key === mk);
        return firstMatch ? firstMatch.label : mk;
    });
    const datasets = Object.entries(dataByKey).map(([name, rows], idx) => {
        const color = PALETTE[(idx + colorOffset) % PALETTE.length];
        return {
            label: name,
            data: sortedMonths.map(mk => {
                const row = rows.find(r => r.month_key === mk);
                return row ? (row[field] || 0) : 0;
            }),
            backgroundColor: color,
            borderColor: color,
            borderWidth: 1,
        };
    });
    return { labels, datasets };
}

function renderMonthlyByVendorEntries() {
    const container = document.getElementById('monthly-by-vendor-entries');
    if (!container) return;
    if (!monthlyByVendorEntries || !Object.keys(monthlyByVendorEntries).length) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const { labels, datasets: dsQ } = _buildMonthlyMultiDatasets(monthlyByVendorEntries, 'quotes_count', 0);
    const { datasets: dsB } = _buildMonthlyMultiDatasets(monthlyByVendorEntries, 'bookings_count', 0);
    _buildMultiLineChart('chartMonthlyVendorQuotes', labels, dsQ);
    _buildMultiLineChart('chartMonthlyVendorBookings', labels, dsB);
}

function renderMonthlyByClientEntries() {
    const container = document.getElementById('monthly-by-client-entries');
    if (!container) return;
    if (!monthlyByClientEntries || !Object.keys(monthlyByClientEntries).length) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const { labels, datasets: dsQ } = _buildMonthlyMultiDatasets(monthlyByClientEntries, 'quotes_count', 3);
    const { datasets: dsB } = _buildMonthlyMultiDatasets(monthlyByClientEntries, 'bookings_count', 3);
    _buildMultiLineChart('chartMonthlyClientQuotes', labels, dsQ);
    _buildMultiLineChart('chartMonthlyClientBookings', labels, dsB);
}

function renderMonthlyByVrTrips() {
    const container = document.getElementById('monthly-by-vr-trips');
    if (!container) return;
    if (!monthlyByVrTrips || !Object.keys(monthlyByVrTrips).length) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const { labels, datasets: dsCount } = _buildMonthlyMultiDatasets(monthlyByVrTrips, 'bookings_count', 0);
    const { datasets: dsAmount } = _buildMonthlyMultiDatasets(monthlyByVrTrips, 'bookings_amount', 0);
    _buildMultiLineChart('chartMonthlyVrCount', labels, dsCount);
    _buildMultiLineChart('chartMonthlyVrAmount', labels, dsAmount);
}

function renderMonthlyByOperatorTrips() {
    const container = document.getElementById('monthly-by-operator-trips');
    if (!container) return;
    if (!monthlyByOperatorTrips || !Object.keys(monthlyByOperatorTrips).length) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const { labels, datasets: dsCount } = _buildMonthlyMultiDatasets(monthlyByOperatorTrips, 'bookings_count', 5);
    const { datasets: dsAmount } = _buildMonthlyMultiDatasets(monthlyByOperatorTrips, 'bookings_amount', 5);
    _buildMultiLineChart('chartMonthlyOperatorCount', labels, dsCount);
    _buildMultiLineChart('chartMonthlyOperatorAmount', labels, dsAmount);
}

function renderMonthlyByClientTrips() {
    const container = document.getElementById('monthly-by-client-trips');
    if (!container) return;
    if (!monthlyByClientTrips || !Object.keys(monthlyByClientTrips).length) {
        container.classList.add('d-none');
        return;
    }
    container.classList.remove('d-none');

    const { labels, datasets: dsCount } = _buildMonthlyMultiDatasets(monthlyByClientTrips, 'bookings_count', 3);
    const { datasets: dsAmount } = _buildMonthlyMultiDatasets(monthlyByClientTrips, 'bookings_amount', 3);
    _buildMultiLineChart('chartMonthlyClientTripsCount', labels, dsCount);
    _buildMultiLineChart('chartMonthlyClientTripsAmount', labels, dsAmount);
}


function renderSummaryTables() {
    const data  = window.summaryTableQuotes;
    const dataB = window.summaryTableBookings;
    if (!data || !Object.keys(data).length) return;
    if (!dataB || !Object.keys(dataB).length) return;

    // ── KPI cards ─────────────────────────────────────────────────────────────
    document.getElementById('kpi-quotes').textContent        = data.total_count_quotes;
    document.getElementById('kpi-changes').textContent       = data.total_changes_quotes;
    document.getElementById('kpi-bookings').textContent      = dataB.total_count_bookings;
    document.getElementById('kpi-cancellations').textContent = dataB.cancellations_count;
    document.getElementById('kpi-difficulty').textContent    =
        data.average_difficulty.toLocaleString('es-AR', {minimumFractionDigits: 2}) + ' / 5';
    document.getElementById('kpi-conversion').textContent    =
        '% ' + dataB.conversion_perc.toLocaleString('es-AR', {minimumFractionDigits: 2});

    // ── Helper: render a breakdown table ────────────────────────────────────
    function renderBreakdownTable(tbodyId, rows) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        tbody.innerHTML = rows.map(r => {
            const isTotal = r.is_total;
            const amtFmt  = 'USD ' + r.amount.toLocaleString('es-AR', {minimumFractionDigits: 2});
            const percFmt = isTotal ? '—' : '% ' + r.perc.toLocaleString('es-AR', {minimumFractionDigits: 1});
            return `<tr class="${isTotal ? 'table-dark fw-bold' : ''}">
                <td>${r.label}</td>
                <td class="text-end">${r.count}</td>
                <td class="text-end">${amtFmt}</td>
                <td class="text-end">${percFmt}</td>
            </tr>`;
        }).join('');
    }

    // ── By trip type ─────────────────────────────────────────────────────────
    renderBreakdownTable('summary-quotes-tbody',   window.byTypeQuotes   || []);
    renderBreakdownTable('summary-bookings-tbody', window.byTypeBookings || []);

    // ── By travelling season ─────────────────────────────────────────────────
    renderBreakdownTable('summary-quotes-seasons-tbody',   window.bySeasonQuotes   || []);
    renderBreakdownTable('summary-bookings-seasons-tbody', window.bySeasonBookings || []);

    // ── Working days ─────────────────────────────────────────────────────────
    document.getElementById('working-days').innerHTML = `Días Laborables: ${data.working_days}`;

    // ── Difficulty breakdown ─────────────────────────────────────────────────
    document.getElementById('average-difficulty').innerHTML =
        `Promedio: ${data.average_difficulty.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
    document.getElementById('difficulty-1').innerHTML = `Muy fácil: ${data.difficulty_1}`;
    document.getElementById('difficulty-2').innerHTML = `Fácil: ${data.difficulty_2}`;
    document.getElementById('difficulty-3').innerHTML = `Moderado: ${data.difficulty_3}`;
    document.getElementById('difficulty-4').innerHTML = `Complejo: ${data.difficulty_4}`;
    document.getElementById('difficulty-5').innerHTML = `Muy complejo: ${data.difficulty_5}`;

    // ── Cancellations + Conversion ───────────────────────────────────────────
    document.getElementById('cancellations-count').innerHTML  =
        `Cantidad: ${dataB.cancellations_count}`;
    document.getElementById('cancellations-amount').innerHTML =
        `Monto: - USD ${dataB.cancellations_amount.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
    document.getElementById('conversion-perc').innerHTML      =
        `General: % ${dataB.conversion_perc.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
    document.getElementById('conversion-perc-audley').innerHTML =
        `Audley: % ${dataB.conversion_perc_audley.toLocaleString('es-AR', {minimumFractionDigits: 2})}`;
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
        const drillUrl = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true, 'Quote');

        row.innerHTML = `
            <td style="${cellStyle}">${vendor} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">${vals.a}</td>
            <td style="${cellStyle}">${vals.audleyA}</td>
            <td style="${cellStyle}">USD ${vals.montoA.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${perc}%</td>
            <td style="${cellStyle}">${vals.workingDays}</td>
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
        <td>${totalCotizaciones}</td>
        <td>${totalA}</td>
        <td>${totalAudleyA}</td>
        <td>USD ${totalMontoA.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>-</td>
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
        const drillUrl = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true, 'Booking');

        row.innerHTML = `
            <td style="${cellStyle}">${vendor} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">${vals.first}</td>
            <td style="${cellStyle}">${vals.audleyFirst}</td>
            <td style="${cellStyle}">USD ${vals.amountFirst.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${perc}%</td>
            <td style="${cellStyle}">${vals.conversionCount}</td>
            <td style="${cellStyle}">${vals.workingDays}</td>
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
        <td>${totalBookings}</td>
        <td>${totalFirst}</td>
        <td>${totalAudleyFirst}</td>
        <td>USD ${totalAmountFirst.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>-</td>
        <td>-</td>
    `;
    tfoot.appendChild(totalRow);

    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("vendor-booking-table");

}

function renderResponseSpeedVendor(speed_type) {

    if ($.fn.DataTable.isDataTable("#vendor-speed-table")) {
        $("#vendor-speed-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('vendor-speed-total-tbody');
    if (!tbody) { console.error("❌ No se encontró tbody."); return; }
    tbody.innerHTML = '';

    const SUB = 'border-left:3px solid #6c757d !important;border-right:3px solid #6c757d !important;';
    const scTh = `<th title="Sin contestar">SC</th>`;

    const theadRow = document.querySelector('#vendor-speed-table thead tr');
    if (theadRow) {
        if (speed_type === 'speed-quotes') {
            theadRow.innerHTML = `<th>Vendedor</th><th>Total</th><th>0</th><th>1</th><th title="Suma 0+1 días" style="${SUB}">≤1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>+5</th>${scTh}<th>Promedio</th>`;
        } else if (speed_type === 'speed-bookings') {
            theadRow.innerHTML = `<th>Vendedor</th><th>Total</th><th>0</th><th>1</th><th>2</th><th>3</th><th title="Suma 0+1+2+3 días" style="${SUB}">≤3</th><th>4</th><th>5</th><th>+5</th>${scTh}<th>Promedio</th>`;
        } else if (speed_type === 'speed-finals') {
            theadRow.innerHTML = `<th>Vendedor</th><th>Total</th><th>0</th><th>1</th><th>2</th><th>3</th><th>4</th><th title="Suma 0+1+2+3+4 días" style="${SUB}">≤4</th><th>5</th><th>+5</th>${scTh}<th>Promedio</th>`;
        } else {
            theadRow.innerHTML = `<th>Vendedor</th><th>Total</th><th>0</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>+5</th>${scTh}<th>Promedio</th>`;
        }
    }

    function pct(n, d) { return d > 0 ? ((n / d) * 100).toFixed(2) : '0.00'; }
    function showAvgCard(avg) {
        const el = document.getElementById('vendor-speed-average-display');
        if (!el) return;
        el.innerHTML = avg === '-' ? '' : `<div class="d-inline-flex align-items-center gap-2 border rounded px-3 py-2 bg-light mt-1"><span class="text-muted small">Promedio empresa:</span><span class="fs-3 fw-bold ms-2">${avg} días</span></div>`;
    }

    if (speed_type === 'speed-total') {
        const sum = {total:0,sd:0,od:0,td:0,th:0,fd:0,fv:0,md:0,un:0};
        let wSum = 0, wResp = 0;
        Object.entries(vendorSpeedData).forEach(([vendor, vals]) => {
            if (!vals.totalTotal) return;
            sum.total+=vals.totalTotal; sum.sd+=vals.totalSameDay; sum.od+=vals.totalOneDay;
            sum.td+=vals.totalTwoDays; sum.th+=vals.totalThreeDays; sum.fd+=vals.totalFourDays;
            sum.fv+=vals.totalFiveDays; sum.md+=vals.totalMoreDays; sum.un+=vals.totalUnanswered;
            const resp = vals.totalTotal - vals.totalUnanswered;
            if (resp > 0) { wSum += resp * vals.totalAverageDays; wResp += resp; }
            const cs = `background-color:${vals.color||'#FFF'} !important;color:#333;`;
            const row = document.createElement('tr');
            row.setAttribute('style', `background-color:${vals.color||'#FFF'} !important;color:#333;`);
            const url = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true);
            row.innerHTML = `<td style="${cs}">${vendor} <a href="${url}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
                <td style="${cs}">${vals.totalTotal}</td>
                <td style="${cs}">${pct(vals.totalSameDay,resp)}% (${vals.totalSameDay})</td>
                <td style="${cs}">${pct(vals.totalOneDay,resp)}% (${vals.totalOneDay})</td>
                <td style="${cs}">${pct(vals.totalTwoDays,resp)}% (${vals.totalTwoDays})</td>
                <td style="${cs}">${pct(vals.totalThreeDays,resp)}% (${vals.totalThreeDays})</td>
                <td style="${cs}">${pct(vals.totalFourDays,resp)}% (${vals.totalFourDays})</td>
                <td style="${cs}">${pct(vals.totalFiveDays,resp)}% (${vals.totalFiveDays})</td>
                <td style="${cs}">${pct(vals.totalMoreDays,resp)}% (${vals.totalMoreDays})</td>
                <td style="${cs}" title="Sin contestar">${pct(vals.totalUnanswered,vals.totalTotal)}% (${vals.totalUnanswered})</td>
                <td style="${cs}">${vals.totalAverageDays}</td>`;
            tbody.appendChild(row);
        });
        const res = sum.total - sum.un;
        const avg = wResp > 0 ? (wSum / wResp).toFixed(2) : '-';
        const totRow = document.createElement('tr');
        totRow.className = 'fw-bold table-dark';
        totRow.innerHTML = `<td>TOTAL</td><td>${sum.total}</td>
            <td>${pct(sum.sd,res)}% (${sum.sd})</td><td>${pct(sum.od,res)}% (${sum.od})</td>
            <td>${pct(sum.td,res)}% (${sum.td})</td><td>${pct(sum.th,res)}% (${sum.th})</td>
            <td>${pct(sum.fd,res)}% (${sum.fd})</td><td>${pct(sum.fv,res)}% (${sum.fv})</td>
            <td>${pct(sum.md,res)}% (${sum.md})</td>
            <td title="Sin contestar">${pct(sum.un,sum.total)}% (${sum.un})</td><td>${avg}</td>`;
        tbody.appendChild(totRow);
        showAvgCard(avg);

    } else if (speed_type === 'speed-quotes') {
        const sum = {total:0,sd:0,od:0,td:0,th:0,fd:0,fv:0,md:0,un:0};
        let wSum = 0, wResp = 0;
        Object.entries(vendorSpeedData).forEach(([vendor, vals]) => {
            if (!vals.quotesTotal) return;
            sum.total+=vals.quotesTotal; sum.sd+=vals.quotesSameDay; sum.od+=vals.quotesOneDay;
            sum.td+=vals.quotesTwoDays; sum.th+=vals.quotesThreeDays; sum.fd+=vals.quotesFourDays;
            sum.fv+=vals.quotesFiveDays; sum.md+=vals.quotesMoreDays; sum.un+=vals.quotesUnanswered;
            const resp = vals.quotesTotal - vals.quotesUnanswered;
            if (resp > 0) { wSum += resp * vals.quotesAverageDays; wResp += resp; }
            const cs = `background-color:${vals.color||'#FFF'} !important;color:#333;`;
            const row = document.createElement('tr');
            row.setAttribute('style', `background-color:${vals.color||'#FFF'} !important;color:#333;`);
            const url = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true, 'Quote');
            const sub1 = vals.quotesSameDay + vals.quotesOneDay;
            row.innerHTML = `<td style="${cs}">${vendor} <a href="${url}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
                <td style="${cs}">${vals.quotesTotal}</td>
                <td style="${cs}">${pct(vals.quotesSameDay,resp)}% (${vals.quotesSameDay})</td>
                <td style="${cs}">${pct(vals.quotesOneDay,resp)}% (${vals.quotesOneDay})</td>
                <td style="${cs};${SUB}" title="Suma 0+1 días"><strong>${pct(sub1,resp)}% (${sub1})</strong></td>
                <td style="${cs}">${pct(vals.quotesTwoDays,resp)}% (${vals.quotesTwoDays})</td>
                <td style="${cs}">${pct(vals.quotesThreeDays,resp)}% (${vals.quotesThreeDays})</td>
                <td style="${cs}">${pct(vals.quotesFourDays,resp)}% (${vals.quotesFourDays})</td>
                <td style="${cs}">${pct(vals.quotesFiveDays,resp)}% (${vals.quotesFiveDays})</td>
                <td style="${cs}">${pct(vals.quotesMoreDays,resp)}% (${vals.quotesMoreDays})</td>
                <td style="${cs}" title="Sin contestar">${pct(vals.quotesUnanswered,vals.quotesTotal)}% (${vals.quotesUnanswered})</td>
                <td style="${cs}">${vals.quotesAverageDays}</td>`;
            tbody.appendChild(row);
        });
        const res = sum.total - sum.un;
        const sub1Tot = sum.sd + sum.od;
        const avg = wResp > 0 ? (wSum / wResp).toFixed(2) : '-';
        const totRow = document.createElement('tr');
        totRow.className = 'fw-bold table-dark';
        totRow.innerHTML = `<td>TOTAL</td><td>${sum.total}</td>
            <td>${pct(sum.sd,res)}% (${sum.sd})</td><td>${pct(sum.od,res)}% (${sum.od})</td>
            <td style="${SUB}" title="Suma 0+1 días"><strong>${pct(sub1Tot,res)}% (${sub1Tot})</strong></td>
            <td>${pct(sum.td,res)}% (${sum.td})</td><td>${pct(sum.th,res)}% (${sum.th})</td>
            <td>${pct(sum.fd,res)}% (${sum.fd})</td><td>${pct(sum.fv,res)}% (${sum.fv})</td>
            <td>${pct(sum.md,res)}% (${sum.md})</td>
            <td title="Sin contestar">${pct(sum.un,sum.total)}% (${sum.un})</td><td>${avg}</td>`;
        tbody.appendChild(totRow);
        showAvgCard(avg);

    } else if (speed_type === 'speed-bookings') {
        const sum = {total:0,sd:0,od:0,td:0,th:0,fd:0,fv:0,md:0,un:0};
        let wSum = 0, wResp = 0;
        Object.entries(vendorSpeedData).forEach(([vendor, vals]) => {
            if (!vals.bookingsTotal) return;
            sum.total+=vals.bookingsTotal; sum.sd+=vals.bookingsSameDay; sum.od+=vals.bookingsOneDay;
            sum.td+=vals.bookingsTwoDays; sum.th+=vals.bookingsThreeDays; sum.fd+=vals.bookingsFourDays;
            sum.fv+=vals.bookingsFiveDays; sum.md+=vals.bookingsMoreDays; sum.un+=vals.bookingsUnanswered;
            const resp = vals.bookingsTotal - vals.bookingsUnanswered;
            if (resp > 0) { wSum += resp * vals.bookingsAverageDays; wResp += resp; }
            const cs = `background-color:${vals.color||'#FFF'} !important;color:#333;`;
            const row = document.createElement('tr');
            row.setAttribute('style', `background-color:${vals.color||'#FFF'} !important;color:#333;`);
            const url = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true, 'Booking');
            const sub3 = vals.bookingsSameDay + vals.bookingsOneDay + vals.bookingsTwoDays + vals.bookingsThreeDays;
            row.innerHTML = `<td style="${cs}">${vendor} <a href="${url}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
                <td style="${cs}">${vals.bookingsTotal}</td>
                <td style="${cs}">${pct(vals.bookingsSameDay,resp)}% (${vals.bookingsSameDay})</td>
                <td style="${cs}">${pct(vals.bookingsOneDay,resp)}% (${vals.bookingsOneDay})</td>
                <td style="${cs}">${pct(vals.bookingsTwoDays,resp)}% (${vals.bookingsTwoDays})</td>
                <td style="${cs}">${pct(vals.bookingsThreeDays,resp)}% (${vals.bookingsThreeDays})</td>
                <td style="${cs};${SUB}" title="Suma 0+1+2+3 días"><strong>${pct(sub3,resp)}% (${sub3})</strong></td>
                <td style="${cs}">${pct(vals.bookingsFourDays,resp)}% (${vals.bookingsFourDays})</td>
                <td style="${cs}">${pct(vals.bookingsFiveDays,resp)}% (${vals.bookingsFiveDays})</td>
                <td style="${cs}">${pct(vals.bookingsMoreDays,resp)}% (${vals.bookingsMoreDays})</td>
                <td style="${cs}" title="Sin contestar">${pct(vals.bookingsUnanswered,vals.bookingsTotal)}% (${vals.bookingsUnanswered})</td>
                <td style="${cs}">${vals.bookingsAverageDays}</td>`;
            tbody.appendChild(row);
        });
        const res = sum.total - sum.un;
        const sub3Tot = sum.sd + sum.od + sum.td + sum.th;
        const avg = wResp > 0 ? (wSum / wResp).toFixed(2) : '-';
        const totRow = document.createElement('tr');
        totRow.className = 'fw-bold table-dark';
        totRow.innerHTML = `<td>TOTAL</td><td>${sum.total}</td>
            <td>${pct(sum.sd,res)}% (${sum.sd})</td><td>${pct(sum.od,res)}% (${sum.od})</td>
            <td>${pct(sum.td,res)}% (${sum.td})</td><td>${pct(sum.th,res)}% (${sum.th})</td>
            <td style="${SUB}" title="Suma 0+1+2+3 días"><strong>${pct(sub3Tot,res)}% (${sub3Tot})</strong></td>
            <td>${pct(sum.fd,res)}% (${sum.fd})</td><td>${pct(sum.fv,res)}% (${sum.fv})</td>
            <td>${pct(sum.md,res)}% (${sum.md})</td>
            <td title="Sin contestar">${pct(sum.un,sum.total)}% (${sum.un})</td><td>${avg}</td>`;
        tbody.appendChild(totRow);
        showAvgCard(avg);

    } else {
        const sum = {total:0,sd:0,od:0,td:0,th:0,fd:0,fv:0,md:0,un:0};
        let wSum = 0, wResp = 0;
        Object.entries(vendorSpeedData).forEach(([vendor, vals]) => {
            if (!vals.finalsTotal) return;
            sum.total+=vals.finalsTotal; sum.sd+=vals.finalsSameDay; sum.od+=vals.finalsOneDay;
            sum.td+=vals.finalsTwoDays; sum.th+=vals.finalsThreeDays; sum.fd+=vals.finalsFourDays;
            sum.fv+=vals.finalsFiveDays; sum.md+=vals.finalsMoreDays; sum.un+=vals.finalsUnanswered;
            const resp = vals.finalsTotal - vals.finalsUnanswered;
            if (resp > 0) { wSum += resp * vals.finalsAverageDays; wResp += resp; }
            const cs = `background-color:${vals.color||'#FFF'} !important;color:#333;`;
            const row = document.createElement('tr');
            row.setAttribute('style', `background-color:${vals.color||'#FFF'} !important;color:#333;`);
            const url = buildDrillDownUrl('/entries', 'user_other_name_filter', vendor, true, 'Final');
            const sub4 = vals.finalsSameDay + vals.finalsOneDay + vals.finalsTwoDays + vals.finalsThreeDays + vals.finalsFourDays;
            row.innerHTML = `<td style="${cs}">${vendor} <a href="${url}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
                <td style="${cs}">${vals.finalsTotal}</td>
                <td style="${cs}">${pct(vals.finalsSameDay,resp)}% (${vals.finalsSameDay})</td>
                <td style="${cs}">${pct(vals.finalsOneDay,resp)}% (${vals.finalsOneDay})</td>
                <td style="${cs}">${pct(vals.finalsTwoDays,resp)}% (${vals.finalsTwoDays})</td>
                <td style="${cs}">${pct(vals.finalsThreeDays,resp)}% (${vals.finalsThreeDays})</td>
                <td style="${cs}">${pct(vals.finalsFourDays,resp)}% (${vals.finalsFourDays})</td>
                <td style="${cs};${SUB}" title="Suma 0+1+2+3+4 días"><strong>${pct(sub4,resp)}% (${sub4})</strong></td>
                <td style="${cs}">${pct(vals.finalsFiveDays,resp)}% (${vals.finalsFiveDays})</td>
                <td style="${cs}">${pct(vals.finalsMoreDays,resp)}% (${vals.finalsMoreDays})</td>
                <td style="${cs}" title="Sin contestar">${pct(vals.finalsUnanswered,vals.finalsTotal)}% (${vals.finalsUnanswered})</td>
                <td style="${cs}">${vals.finalsAverageDays}</td>`;
            tbody.appendChild(row);
        });
        const res = sum.total - sum.un;
        const sub4Tot = sum.sd + sum.od + sum.td + sum.th + sum.fd;
        const avg = wResp > 0 ? (wSum / wResp).toFixed(2) : '-';
        const totRow = document.createElement('tr');
        totRow.className = 'fw-bold table-dark';
        totRow.innerHTML = `<td>TOTAL</td><td>${sum.total}</td>
            <td>${pct(sum.sd,res)}% (${sum.sd})</td><td>${pct(sum.od,res)}% (${sum.od})</td>
            <td>${pct(sum.td,res)}% (${sum.td})</td><td>${pct(sum.th,res)}% (${sum.th})</td>
            <td>${pct(sum.fd,res)}% (${sum.fd})</td>
            <td style="${SUB}" title="Suma 0+1+2+3+4 días"><strong>${pct(sub4Tot,res)}% (${sub4Tot})</strong></td>
            <td>${pct(sum.fv,res)}% (${sum.fv})</td><td>${pct(sum.md,res)}% (${sum.md})</td>
            <td title="Sin contestar">${pct(sum.un,sum.total)}% (${sum.un})</td><td>${avg}</td>`;
        tbody.appendChild(totRow);
        showAvgCard(avg);
    }

    create_datatable_stats("vendor-speed-table");
}

function buildAllSpeedTablesHTML() {
    const data = vendorSpeedData;
    if (!data || !Object.keys(data).length) return '<p>No hay datos disponibles.</p>';

    const SUB = 'border-left:3px solid #6c757d;border-right:3px solid #6c757d;';
    function pct(n, d) { return d > 0 ? ((n / d) * 100).toFixed(2) : '0.00'; }
    function speedCell(n, resp, cs) { return `<td style="${cs}">${pct(n,resp)}% (${n})</td>`; }
    function subCell(n, resp, cs, title) { return `<td style="${cs}${SUB}" title="${title}"><strong>${pct(n,resp)}% (${n})</strong></td>`; }

    function buildSection(cfg) {
        const P = cfg.prefix;
        const sum = {total:0,sd:0,od:0,td:0,th:0,fd:0,fv:0,md:0,un:0};
        let wSum = 0, wResp = 0, rows = '';

        Object.entries(data).forEach(([vendor, vals]) => {
            const t=vals[`${P}Total`]||0;
            if (!t) return;
            const sd=vals[`${P}SameDay`]||0, od=vals[`${P}OneDay`]||0, td=vals[`${P}TwoDays`]||0;
            const th=vals[`${P}ThreeDays`]||0, fd=vals[`${P}FourDays`]||0, fv=vals[`${P}FiveDays`]||0;
            const md=vals[`${P}MoreDays`]||0, un=vals[`${P}Unanswered`]||0, avg=vals[`${P}AverageDays`]||0;
            const resp = t - un;
            sum.total+=t; sum.sd+=sd; sum.od+=od; sum.td+=td; sum.th+=th;
            sum.fd+=fd; sum.fv+=fv; sum.md+=md; sum.un+=un;
            if (resp > 0) { wSum += resp * avg; wResp += resp; }

            const color = vals.color || '#FFFFFF';
            const cs = `background-color:${color} !important;color:#333;`;
            let r = `<td style="${cs}">${vendor}</td><td style="${cs}">${t}</td>`;
            r += speedCell(sd, resp, cs);
            r += speedCell(od, resp, cs);
            if (cfg.sub === 'one') r += subCell(sd+od, resp, cs, 'Suma 0+1 días');
            r += speedCell(td, resp, cs);
            r += speedCell(th, resp, cs);
            if (cfg.sub === 'three') r += subCell(sd+od+td+th, resp, cs, 'Suma 0+1+2+3 días');
            r += speedCell(fd, resp, cs);
            if (cfg.sub === 'four') r += subCell(sd+od+td+th+fd, resp, cs, 'Suma 0+1+2+3+4 días');
            r += speedCell(fv, resp, cs);
            r += speedCell(md, resp, cs);
            r += `<td style="${cs}" title="Sin contestar">${pct(un,t)}% (${un})</td>`;
            r += `<td style="${cs}">${avg}</td>`;
            rows += `<tr style="background-color:${color} !important;">${r}</tr>`;
        });

        const res = sum.total - sum.un;
        const compAvg = wResp > 0 ? (wSum / wResp).toFixed(2) : '-';
        let th = '<th>Vendedor</th><th>Total</th><th>0</th><th>1</th>';
        if (cfg.sub === 'one')   th += `<th style="${SUB}" title="Suma 0+1 días">≤1</th>`;
        th += '<th>2</th><th>3</th>';
        if (cfg.sub === 'three') th += `<th style="${SUB}" title="Suma 0+1+2+3 días">≤3</th>`;
        th += '<th>4</th>';
        if (cfg.sub === 'four')  th += `<th style="${SUB}" title="Suma 0+1+2+3+4 días">≤4</th>`;
        th += '<th>5</th><th>+5</th><th title="Sin contestar">SC</th><th>Promedio</th>';

        let totCells = `<td>TOTAL</td><td>${sum.total}</td>`;
        totCells += `<td>${pct(sum.sd,res)}% (${sum.sd})</td><td>${pct(sum.od,res)}% (${sum.od})</td>`;
        if (cfg.sub === 'one')   totCells += subCell(sum.sd+sum.od, res, '', 'Suma 0+1 días');
        totCells += `<td>${pct(sum.td,res)}% (${sum.td})</td><td>${pct(sum.th,res)}% (${sum.th})</td>`;
        if (cfg.sub === 'three') totCells += subCell(sum.sd+sum.od+sum.td+sum.th, res, '', 'Suma 0+1+2+3 días');
        totCells += `<td>${pct(sum.fd,res)}% (${sum.fd})</td>`;
        if (cfg.sub === 'four')  totCells += subCell(sum.sd+sum.od+sum.td+sum.th+sum.fd, res, '', 'Suma 0+1+2+3+4 días');
        totCells += `<td>${pct(sum.fv,res)}% (${sum.fv})</td><td>${pct(sum.md,res)}% (${sum.md})</td>`;
        totCells += `<td title="Sin contestar">${pct(sum.un,sum.total)}% (${sum.un})</td><td>${compAvg}</td>`;

        const avgCard = compAvg !== '-'
            ? `<div style="display:inline-flex;align-items:center;gap:8px;border:1px solid #dee2e6;border-radius:6px;padding:6px 14px;background:#f8f9fa;margin-top:6px;">
                   <span style="color:#6c757d;font-size:0.85em;">Promedio empresa:</span>
                   <span style="font-size:1.4em;font-weight:700;">${compAvg} días</span>
               </div>` : '';

        return `<div class="chart-box mb-3" style="page-break-inside:avoid;break-inside:avoid;">
            <h4 class="mt-4 mb-2">${cfg.title}</h4>
            <table class="table table-bordered table-sm" style="font-size:0.8em;width:100%;">
                <thead class="table-dark"><tr>${th}</tr></thead>
                <tbody>${rows}</tbody>
                <tfoot><tr class="fw-bold table-dark">${totCells}</tr></tfoot>
            </table>
            ${avgCard}
        </div>`;
    }

    return [
        buildSection({ title: 'Total', prefix: 'total' }),
        buildSection({ title: 'Cotizaciones (FITs + Grupos)', prefix: 'quotes', sub: 'one' }),
        buildSection({ title: 'Reservas', prefix: 'bookings', sub: 'three' }),
        buildSection({ title: 'Final Itineraries', prefix: 'finals', sub: 'four' }),
    ].join('');
}

async function exportSpeedPDF() {
    if (!vendorSpeedData || !Object.keys(vendorSpeedData).length) {
        alert('No hay datos de rapidez cargados todavía.');
        return;
    }
    const buttonsRow = document.getElementById('speed-buttons-row');
    const tableWrap  = document.getElementById('vendor-speed-table-wrap');
    const allTables  = document.getElementById('speed-all-vendor-tables');

    if (buttonsRow) buttonsRow.style.display = 'none';
    if (tableWrap)  tableWrap.style.display  = 'none';
    allTables.innerHTML = buildAllSpeedTablesHTML();
    allTables.style.display = 'block';

    try {
        await exportSectionToPDF('section-speed');
    } finally {
        if (buttonsRow) buttonsRow.style.display = '';
        if (tableWrap)  tableWrap.style.display  = '';
        allTables.style.display = 'none';
        allTables.innerHTML = '';
    }
}

function renderResponseSpeed() {
    const data = window.summarySpeed;
    if (!data || !Object.keys(data).length) return;

    const tbody = document.getElementById("summary-speed-tbody");
    if (!tbody) return;

    // Render tabla de rapidez
    tbody.innerHTML = `
        <tr>
            <td>Mismo día:</td>
            <td>${data.total.same_day}</td>
            <td>${data.total.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.same_day}</td>
            <td>${data.individual_quotes.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.same_day}</td>
            <td>${data.audley_quotes.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.same_day}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.same_day}</td>
            <td>${data.bookings.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.same_day}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.same_day.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>1 día:</td>
            <td>${data.total.one_day}</td>
            <td>${data.total.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.one_day}</td>
            <td>${data.individual_quotes.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.one_day}</td>
            <td>${data.audley_quotes.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.one_day}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.one_day}</td>
            <td>${data.bookings.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.one_day}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.one_day.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>2 días:</td>
            <td>${data.total.two_days}</td>
            <td>${data.total.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.two_days}</td>
            <td>${data.individual_quotes.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.two_days}</td>
            <td>${data.audley_quotes.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.two_days}</td>
            <td>${data.group_quotes > 0 ? data.group_quotes.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.two_days}</td>
            <td>${data.bookings.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.two_days}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.two_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>3 días:</td>
            <td>${data.total.three_days}</td>
            <td>${data.total.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.three_days}</td>
            <td>${data.individual_quotes.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.three_days}</td>
            <td>${data.audley_quotes.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.three_days}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.three_days}</td>
            <td>${data.bookings.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.three_days}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.three_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>4 días:</td>
            <td>${data.total.four_days}</td>
            <td>${data.total.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.four_days}</td>
            <td>${data.individual_quotes.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.four_days}</td>
            <td>${data.audley_quotes.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.four_days}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2}): 0}%</td>
            <td>${data.bookings.four_days}</td>
            <td>${data.bookings.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.four_days}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.four_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>5 días:</td>
            <td>${data.total.five_days}</td>
            <td>${data.total.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.five_days}</td>
            <td>${data.individual_quotes.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.five_days}</td>
            <td>${data.audley_quotes.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.five_days}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.five_days}</td>
            <td>${data.bookings.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.five_days}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.five_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>Más de 5 días:</td>
            <td>${data.total.more_days}</td>
            <td>${data.total.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.more_days}</td>
            <td>${data.individual_quotes.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.more_days}</td>
            <td>${data.audley_quotes.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.more_days}</td>
            <td>${data.group_quotes.total > 0 ? data.group_quotes.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2}): 0}%</td>
            <td>${data.bookings.more_days}</td>
            <td>${data.bookings.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.more_days}</td>
            <td>${data.final_itineraries.total > 0 ? data.final_itineraries.percentages.more_days.toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr title="Sin contestar">
            <td>SC:</td>
            <td>${data.total.unanswered ?? 0}</td>
            <td>${(data.total.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.individual_quotes.unanswered ?? 0}</td>
            <td>${(data.individual_quotes.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.audley_quotes.unanswered ?? 0}</td>
            <td>${(data.audley_quotes.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.group_quotes.unanswered ?? 0}</td>
            <td>${data.group_quotes.total > 0 ? (data.group_quotes.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
            <td>${data.bookings.unanswered ?? 0}</td>
            <td>${(data.bookings.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}%</td>
            <td>${data.final_itineraries.unanswered ?? 0}</td>
            <td>${data.final_itineraries.total > 0 ? (data.final_itineraries.percentages.unanswered ?? 0).toLocaleString('es-AR', {minimumFractionDigits: 2}) : 0}%</td>
        </tr>
        <tr>
            <td>TOTAL:</td>
            <td class="fw-bold">${data.total.total}</td>
            <td>-</td>
            <td class="fw-bold">${data.individual_quotes.total}</td>
            <td>-</td>
            <td class="fw-bold">${data.audley_quotes.total}</td>
            <td>-</td>
            <td class="fw-bold">${data.group_quotes.total}</td>
            <td>-</td>
            <td class="fw-bold">${data.bookings.total}</td>
            <td>-</td>
            <td class="fw-bold">${data.final_itineraries.total}</td>
            <td>-</td>
        </tr>
        <tr>
            <td>Promedio:</td>
            <td class="fw-bold">${parseFloat(data.total.average || 0, 10) || "-"}</td>
            <td>-</td>
            <td class="fw-bold">${parseFloat(data.individual_quotes.average || 0, 10) || "-"}</td>
            <td>-</td>
            <td class="fw-bold">${parseFloat(data.audley_quotes.average || 0, 10) || "-"}</td>
            <td>-</td>
            <td class="fw-bold">${parseFloat(data.group_quotes.average || 0, 10) || "-"}</td>
            <td>-</td>
            <td class="fw-bold">${parseFloat(data.bookings.average || 0, 10) || "-"}</td>
            <td>-</td>
            <td class="fw-bold">${parseFloat(data.final_itineraries.average || 0, 10) || "-"}</td>
            <td>-</td>
        </tr>
    `;
    // Speed KPI cards
    const iqUnans = data.individual_quotes.unanswered ?? 0;
    const iqResp = data.individual_quotes.total - iqUnans;
    const iqSub1 = (data.individual_quotes.same_day || 0) + (data.individual_quotes.one_day || 0);
    const iqPct = iqResp > 0 ? ((iqSub1 / iqResp) * 100).toFixed(1) : 0;

    const bkUnans = data.bookings.unanswered ?? 0;
    const bkResp = data.bookings.total - bkUnans;
    const bkSub3 = (data.bookings.same_day || 0) + (data.bookings.one_day || 0) + (data.bookings.two_days || 0) + (data.bookings.three_days || 0);
    const bkPct = bkResp > 0 ? ((bkSub3 / bkResp) * 100).toFixed(1) : 0;

    const fiUnans = data.final_itineraries.unanswered ?? 0;
    const fiResp = data.final_itineraries.total - fiUnans;
    const fiSub4 = (data.final_itineraries.same_day || 0) + (data.final_itineraries.one_day || 0) + (data.final_itineraries.two_days || 0) + (data.final_itineraries.three_days || 0) + (data.final_itineraries.four_days || 0);
    const fiPct = fiResp > 0 ? ((fiSub4 / fiResp) * 100).toFixed(1) : 0;

    const elQPct = document.getElementById('kpi-speed-quotes-pct');
    const elQCnt = document.getElementById('kpi-speed-quotes-count');
    const elQAvg = document.getElementById('kpi-speed-quotes-avg');
    const elBPct = document.getElementById('kpi-speed-bookings-pct');
    const elBCnt = document.getElementById('kpi-speed-bookings-count');
    const elBAvg = document.getElementById('kpi-speed-bookings-avg');
    const elFPct = document.getElementById('kpi-speed-finals-pct');
    const elFCnt = document.getElementById('kpi-speed-finals-count');
    const elFAvg = document.getElementById('kpi-speed-finals-avg');
    if (elQPct) elQPct.textContent = `${iqPct}%`;
    if (elQCnt) elQCnt.textContent = `${iqSub1}/${iqResp}`;
    if (elQAvg) elQAvg.textContent = data.individual_quotes.average ?? '—';
    if (elBPct) elBPct.textContent = `${bkPct}%`;
    if (elBCnt) elBCnt.textContent = `${bkSub3}/${bkResp}`;
    if (elBAvg) elBAvg.textContent = data.bookings.average ?? '—';
    if (elFPct) elFPct.textContent = `${fiPct}%`;
    if (elFCnt) elFCnt.textContent = `${fiSub4}/${fiResp}`;
    if (elFAvg) elFAvg.textContent = data.final_itineraries.average ?? '—';

    const all_speed_btn = document.querySelectorAll('.speed-type');
    if (all_speed_btn) {
        all_speed_btn.forEach(btn => {
            btn.addEventListener('click', () => {
                const speed_type = btn.id
                changeSpeedTable(speed_type);
            });
        });
    };
}

function changeSpeedTable(speed_type) {
    // Delete previous tables
    const speed_title = document.getElementById('speed-title');
    speed_title.innerHTML = '';

    const speed_table = document.getElementById('vendor-speed-total-tbody');
    speed_table.innerHTML = ''

    // Get the new information and complete the table
    renderResponseSpeedVendor(speed_type);

    // Disable the current button and activate the rest
    const all_speed_btn = document.querySelectorAll('.speed-type');
    if (all_speed_btn) {
        all_speed_btn.forEach(btn => {
            if (btn.id == speed_type) {
                btn.className = "btn btn-lg btn-primary w-100 m-3 speed-type disabled";
            } else {
                btn.className = "btn btn-lg btn-primary w-100 m-3 speed-type";
            };
        });
    };

}

function renderClients() {
    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#summary-clients-table")) {
        $("#summary-clients-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('summary-clients-tbody');
    const tfoot = document.getElementById('summary-clients-tfoot');
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }

    const totalQuotesCount = Object.values(summaryClients).reduce((acc, c) => acc + c.quotesCount, 0);
    const totalBookingsCount = Object.values(summaryClients).reduce((acc, c) => acc + c.bookingsCount, 0);
    const totalQuotesAmount = Object.values(summaryClients).reduce((acc, c) => acc + c.quotesAmount, 0);
    const totalBookingsAmount = Object.values(summaryClients).reduce((acc, c) => acc + c.bookingsAmount, 0);

    tbody.innerHTML = '';
    tfoot.innerHTML = '';

    Object.entries(summaryClients).forEach(([client, vals]) => {
        const percQuotesCount = totalQuotesCount > 0 ? ((vals.quotesCount / totalQuotesCount) * 100).toFixed(2) : 0;
        const percBookingsCount = totalBookingsCount > 0 ? ((vals.bookingsCount / totalBookingsCount) * 100).toFixed(2) : 0;
        const percQuotesAmount = totalQuotesAmount > 0 ? ((vals.quotesAmount / totalQuotesAmount) * 100).toFixed(2) : 0;
        const percBookingsAmount = totalBookingsAmount > 0 ? ((vals.bookingsAmount / totalBookingsAmount) * 100).toFixed(2) : 0;
        const bookings = +vals.bookingsCount || 0;
        const quotes = +vals.quotesCount || 0;
        const conversion = quotes > 0
            ? ((bookings / quotes) * 100).toFixed(2)
            : "n/a";
        const row = document.createElement('tr');
        const drillUrl = buildDrillDownUrl('/entries', 'client_filter', client, true);

        row.innerHTML = `
            <td>${client} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td>${vals.quotesCount}</td>
            <td>${percQuotesCount}%</td>
            <td>USD ${vals.quotesAmount.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td>${percQuotesAmount}%</td>
            <td>${vals.bookingsCount}</td>
            <td>${percBookingsCount}%</td>
            <td>USD ${vals.bookingsAmount.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td>${percBookingsAmount}%</td>
            <td>${conversion}%</td>
        `;
        tbody.appendChild(row);
    });

    // 🔹 Agregar fila total al TFOOT

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>${totalQuotesCount}</td>
        <td>-</td>
        <td>USD ${totalQuotesAmount}</td>
        <td>-</td>
        <td>${totalBookingsCount}</td>
        <td>-</td>
        <td>USD ${totalBookingsAmount}</td>
        <td>-</td>
        <td>-</td>
    `;
    tfoot.appendChild(totalRow);

    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("summary-clients-table");
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

function renderChartsSpeed() {
    // Asegurarte de tener el bloque correcto
    const summary = window.summarySpeed;

    // Extraer las categorías y sus promedios
    const categories = [
        { key: 'total', label: 'Total' },
        { key: 'individual_quotes', label: 'Individuales' },
        { key: 'group_quotes', label: 'Grupos' },
        { key: 'audley_quotes', label: 'Audley' },
        { key: 'bookings', label: 'Bookings' },
        { key: 'final_itineraries', label: 'Final Itineraries' }
    ];

    // Crear los arrays para Chart.js
    const labels = [];
    const averages = [];

    categories.forEach(cat => {
        const avg = summary[cat.key]?.average;
        // Si es null o undefined, lo tratamos como 0
        labels.push(cat.label);
        averages.push(avg ?? 0);
    });

    // Si ya existe un gráfico anterior, lo destruimos
    if (window.speedChart) {
        window.speedChart.destroy();
    }

    console.log(summary);

    // Crear el gráfico de barras
    const ctx = document.getElementById('chartSpeedCanvas').getContext('2d');

    window.speedChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Promedio de días de respuesta',
                data: averages,
                backgroundColor: [
                    '#36a2eb', '#4bc0c0', '#9966ff', '#ff9f40',
                    '#ff6384', '#c9cbcf', '#82ca9d'
                ],
                borderColor: '#333',
                borderWidth: 1,
                borderRadius: 8,
            }]
        },
        options: {
            responsive: true,
            layout: {
                padding: {
                    top: 30
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Promedio de días de respuesta por categoría',
                    font: {
                        size: 20,
                        weight: 'bold'
                    },
                    padding: {
                        top: 10,
                        bottom: 20
                    }
                },
                tooltip: {
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: (context) => `${context.raw.toFixed(2)} días`
                    }
                },
                datalabels: {
                    color: '#000',
                    anchor: 'end', // apunta hacia arriba
                    align: 'top',  // ubica el texto por encima de la barra
                    offset: 4,     // separación de la barra
                    font: {
                        weight: 'bold',
                        size: 14
                    },
                    formatter: (value) => value ? value.toFixed(2) : ''
                }
            },
            scales: {
                x: {
                    ticks: {
                        font: { size: 14, weight: '500' },
                        color: '#222'
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        font: { size: 13 },
                        color: '#333'
                    },
                    title: {
                        display: true,
                        text: 'Días promedio',
                        font: { size: 16, weight: 'bold' }
                    }
                }
            }
        },
        plugins: [ChartDataLabels]
    });
}

// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderChartsClients() {
    const clients = Object.keys(summaryClients);
    const quotesAmount = clients.map(c => summaryClients[c].quotesAmount);
    const bookingsAmount = clients.map(c => summaryClients[c].bookingsAmount);

    // Destruir gráficos anteriores
    if (chartsClients.quotes) chartsClients.quotes.destroy();
    if (chartsClients.bookings) chartsClients.bookings.destroy();

    // Gráfico de Cantidad
    const ctxQuotes = document.getElementById('chartClientsQuotesCanvas').getContext('2d');
    chartsClients.quotes = new Chart(ctxQuotes, {
        type: 'pie',
        data: {
            labels: clients,
            datasets: [{
                data: quotesAmount,
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

    // Gráfico de Monto
    const ctxBookings = document.getElementById('chartClientsBookingsCanvas').getContext('2d');
    chartsClients.bookings = new Chart(ctxBookings, {
        type: 'pie',
        data: {
            labels: clients,
            datasets: [{
                data: bookingsAmount,
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

function renderSummaryTrips() {
    const data = window.summaryTableTrips;
    if (!data || !Object.keys(data).length) return;

    const fmt2  = v => v.toLocaleString('es-AR', {minimumFractionDigits: 2});
    const fmt1  = v => v.toLocaleString('es-AR', {minimumFractionDigits: 1});
    const totalRent = data.all_rent_average / 100 * data.total_amount_trips;

    // KPI cards
    document.getElementById('kpi-trips').textContent          = data.total_count_trips;
    document.getElementById('kpi-trips-cancel').textContent   = data.cancellations_count;
    document.getElementById('kpi-trips-rent').textContent     = 'USD ' + fmt2(totalRent);
    document.getElementById('kpi-trips-rent-perc').textContent = '% ' + fmt2(data.all_rent_average);
    document.getElementById('kpi-trips-difficulty').textContent = fmt2(data.average_difficulty) + ' / 5';

    // By-type table
    const tbody = document.getElementById('summary-trips-tbody');
    if (tbody) {
        tbody.innerHTML = (window.byTypeTrips || []).map(r => {
            const isTotal = r.is_total;
            return `<tr class="${isTotal ? 'table-dark fw-bold' : ''}">
                <td>${r.label}</td>
                <td class="text-end">${r.count}</td>
                <td class="text-end">USD ${fmt2(r.amount)}</td>
                <td class="text-end">${isTotal ? '—' : '% ' + fmt1(r.amount_perc)}</td>
                <td class="text-end">USD ${fmt2(r.rent_amount)}</td>
                <td class="text-end">% ${fmt2(r.avg_rent_perc)}</td>
            </tr>`;
        }).join('');
    }

    document.getElementById('average-difficulty').innerHTML   = `Promedio: ${fmt2(data.average_difficulty)}`;
    document.getElementById('difficulty-1').innerHTML         = `Muy fácil: ${data.difficulty_1}`;
    document.getElementById('difficulty-2').innerHTML         = `Fácil: ${data.difficulty_2}`;
    document.getElementById('difficulty-3').innerHTML         = `Moderado: ${data.difficulty_3}`;
    document.getElementById('difficulty-4').innerHTML         = `Complejo: ${data.difficulty_4}`;
    document.getElementById('difficulty-5').innerHTML         = `Muy complejo: ${data.difficulty_5}`;
    document.getElementById('cancellations-count').innerHTML  = `Cantidad: ${data.cancellations_count}`;
    document.getElementById('cancellations-amount').innerHTML = `Monto: - USD ${fmt2(data.cancellations_amount)}`;
}


// ==================== FUNCIÓN: Renderizar tabla ====================
function renderVendorTrips() {

    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#vr-booking-table")) {
        $("#vr-booking-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('vendor-vr-tbody');
    const tfoot = document.getElementById('vendor-vr-tfoot');
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }
    const totalAmounts = Object.values(vendorTripsData).reduce((acc, v) => acc + v.amountTotal, 0);
    const totalAudleyAmounts = Object.values(vendorTripsData).reduce((acc, v) => acc + v.amountAudley, 0);

    tbody.innerHTML = '';
    tfoot.innerHTML = '';

    Object.entries(vendorTripsData).forEach(([vendor, vals]) => {
        const percTotal = totalAmounts > 0 ? ((vals.amountTotal / totalAmounts) * 100).toFixed(2) : 0;
        const percAudley = totalAudleyAmounts > 0 ? ((vals.amountAudley / totalAudleyAmounts) * 100).toFixed(2) : 0;

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
        const drillUrl = buildDrillDownUrl('/trips', 'vr_filter', vendor, false, 'Booking');

        row.innerHTML = `
            <td style="${cellStyle}">${vendor} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">USD ${vals.amountTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${percTotal}%</td>
            <td style="${cellStyle}">${vals.audley}</td>
            <td style="${cellStyle}">USD ${vals.amountAudley.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${percAudley}%</td>
            <td style="${cellStyle}">${vals.workingDays}</td>
        `;
        tbody.appendChild(row);
    });

    // 🔹 Agregar fila total al TFOOT
    const totalCount = Object.values(vendorTripsData).reduce((acc, v) => acc + v.total, 0);
    const totalAudley = Object.values(vendorTripsData).reduce((acc, v) => acc + v.audley, 0);

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>${totalCount}</td>
        <td>USD ${totalAmounts.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>${totalAudley}</td>
        <td>USD ${totalAudleyAmounts.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>-</td>
    `;
    tfoot.appendChild(totalRow);

    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("vr-booking-table");

}


function renderOperatorTrips() {

    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#operations-booking-table")) {
        $("#operations-booking-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('operations-booking-tbody');
    const tfoot = document.getElementById('operations-booking-tfoot');
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }
    const totalAmounts = Object.values(operatorTripsData).reduce((acc, o) => acc + o.amountTotal, 0);
    const totalAudleyAmounts = Object.values(operatorTripsData).reduce((acc, o) => acc + o.amountAudley, 0);

    tbody.innerHTML = '';
    tfoot.innerHTML = '';

    Object.entries(operatorTripsData).forEach(([operator, vals]) => {
        const percTotal = totalAmounts > 0 ? ((vals.amountTotal / totalAmounts) * 100).toFixed(2) : 0;
        const percAudley = totalAudleyAmounts > 0 ? ((vals.amountAudley / totalAudleyAmounts) * 100).toFixed(2) : 0;

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
        const drillUrl = buildDrillDownUrl('/trips', 'op_filter', operator, false, 'Booking');

        row.innerHTML = `
            <td style="${cellStyle}">${operator} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="color:inherit;opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td style="${cellStyle}">${vals.total}</td>
            <td style="${cellStyle}">USD ${vals.amountTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${percTotal}%</td>
            <td style="${cellStyle}">${vals.audley}</td>
            <td style="${cellStyle}">USD ${vals.amountAudley.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td style="${cellStyle}">${percAudley}%</td>
            <td style="${cellStyle}">${vals.workingDays}</td>
        `;
        tbody.appendChild(row);
    });

    // 🔹 Agregar fila total al TFOOT
    const totalCount = Object.values(operatorTripsData).reduce((acc, o) => acc + o.total, 0);
    const totalAudley = Object.values(operatorTripsData).reduce((acc, o) => acc + o.audley, 0);

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>${totalCount}</td>
        <td>USD ${totalAmounts.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>${totalAudley}</td>
        <td>USD ${totalAudleyAmounts.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>100%</td>
        <td>-</td>
    `;
    tfoot.appendChild(totalRow);

    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("operations-booking-table");

}


// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderChartsTripsVendors() {
    const vendors = Object.keys(vendorTripsData);
    const count = vendors.map(v => vendorTripsData[v].total);
    const amount = vendors.map(v => vendorTripsData[v].amountTotal);

    // ✅ CORRECTO: Acceder al color dentro de cada vendedor
    const colors = vendors.map(vendor => vendorTripsData[vendor].color || '#999999');

    // Destruir gráficos anteriores
    if (chartsTripsVendor.cantidad) chartsTripsVendor.cantidad.destroy();
    if (chartsTripsVendor.monto) chartsTripsVendor.monto.destroy();

    // Gráfico de Cantidad
    const ctxCantidad = document.getElementById('chartCountVrCanvas').getContext('2d');
    chartsTripsVendor.cantidad = new Chart(ctxCantidad, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: count,
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
    const ctxMonto = document.getElementById('chartAmountVrCanvas').getContext('2d');
    chartsTripsVendor.monto = new Chart(ctxMonto, {
        type: 'pie',
        data: {
            labels: vendors,
            datasets: [{
                data: amount,
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
function renderChartsTripsOperators() {
    const operators = Object.keys(operatorTripsData);
    const count = operators.map(o => operatorTripsData[o].total);
    const amount = operators.map(o => operatorTripsData[o].amountTotal);

    // ✅ CORRECTO: Acceder al color dentro de cada vendedor
    const colors = operators.map(operator => operatorTripsData[operator].color || '#999999');

    // Destruir gráficos anteriores
    if (chartsTripsOperator.cantidad) chartsTripsOperator.cantidad.destroy();
    if (chartsTripsOperator.monto) chartsTripsOperator.monto.destroy();

    // Gráfico de Cantidad
    const ctxCantidad = document.getElementById('chartCantidadOperationsCanvas').getContext('2d');
    chartsTripsOperator.cantidad = new Chart(ctxCantidad, {
        type: 'pie',
        data: {
            labels: operators,
            datasets: [{
                data: count,
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
    const ctxMonto = document.getElementById('chartMontoOperationsCanvas').getContext('2d');
    chartsTripsOperator.monto = new Chart(ctxMonto, {
        type: 'pie',
        data: {
            labels: operators,
            datasets: [{
                data: amount,
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
function renderInsightsTripsVendors() {
    const vendors = Object.keys(vendorTripsData);
    const topVendorAmount = vendors.reduce((max, vendor) =>
        vendorTripsData[vendor].amountTotal > vendorTripsData[max].amountTotal ? vendor : max
    );

    const topVendorCount = vendors.reduce((max, vendor) =>
        vendorTripsData[vendor].total > vendorTripsData[max].total ? vendor : max
    );

    const totalMonto = Object.values(vendorTripsData).reduce((acc, v) => acc + v.amountTotal, 0);
    const totalCantidad = Object.values(vendorTripsData).reduce((acc, v) => acc + v.total, 0);
    const promedio = totalMonto / vendors.length;

    const insights = `
        <ul>
            <li><strong>🏆 Top Vendedor x monto:</strong> ${topVendorAmount} con USD ${vendorTripsData[topVendorAmount].amountTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>💰 Facturación Total:</strong> USD ${totalMonto.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>🏆 Top Vendedor x cantidad:</strong> ${topVendorCount} con ${vendorTripsData[topVendorCount].total}</li>
            <li><strong>📊 Total Reservas:</strong> ${totalCantidad} viajes confirmados</li>
            <li><strong>📈 Promedio por Vendedor:</strong> USD ${promedio.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>👥 Vendedores Activos:</strong> ${vendors.length}</li>
        </ul>
    `;

    document.getElementById('insights-content-vr').innerHTML = insights;
}


// ==================== FUNCIÓN: Renderizar insights ====================
function renderInsightsTripsOperators() {
    const operators = Object.keys(operatorTripsData);
    const topOperatorAmount = operators.reduce((max, vendor) =>
        operatorTripsData[vendor].amountTotal > operatorTripsData[max].amountTotal ? vendor : max
    );

    const topOperatorCount = operators.reduce((max, vendor) =>
        operatorTripsData[vendor].total > operatorTripsData[max].total ? vendor : max
    );

    const totalMonto = Object.values(operatorTripsData).reduce((acc, v) => acc + v.amountTotal, 0);
    const totalCantidad = Object.values(operatorTripsData).reduce((acc, v) => acc + v.total, 0);
    const promedio = totalMonto / operators.length;

    const insights = `
        <ul>
            <li><strong>🏆 Top Operador x monto:</strong> ${topOperatorAmount} con USD ${operatorTripsData[topOperatorAmount].amountTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>💰 Facturación Total:</strong> USD ${totalMonto.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>🏆 Top Operador x cantidad:</strong> ${topOperatorCount} con ${operatorTripsData[topOperatorCount].total}</li>
            <li><strong>📊 Total Reservas:</strong> ${totalCantidad} viajes confirmados</li>
            <li><strong>📈 Promedio por Operador:</strong> USD ${promedio.toLocaleString('en-US', {minimumFractionDigits: 2})}</li>
            <li><strong>👥 Operadores Activos:</strong> ${operators.length}</li>
        </ul>
    `;

    document.getElementById('insights-content-operations').innerHTML = insights;
}


function renderTripsClients() {
    // 🔹 Primero: destruir DataTable si ya existe (antes de tocar las filas)
    if ($.fn.DataTable.isDataTable("#summary-clients-trips-table")) {
        $("#summary-clients-trips-table").DataTable().clear().destroy();
    }

    const tbody = document.getElementById('summary-clients-trips-tbody');
    const tfoot = document.getElementById('summary-clients-trips-tfoot');
    if (!tbody || !tfoot) {
        console.error("❌ No se encontró tbody o tfoot en el HTML.");
        return;
    }

    const totalBookingsCount = Object.values(clientTripsData).reduce((acc, c) => acc + c.total, 0);
    const totalBookingsAmount = Object.values(clientTripsData).reduce((acc, c) => acc + c.amountTotal, 0);
    const totalCancelled = Object.values(clientTripsData).reduce((acc, c) => acc + c.cancelled, 0);
    const totalDifficulty = Object.values(clientTripsData).reduce((acc, c) => acc + c.totalDifficulty, 0);

    const totalAverageDifficulty = (totalDifficulty / totalBookingsCount).toFixed(2);
    const totalPerTrip = (totalBookingsAmount / totalBookingsCount).toFixed(2);
    
    tbody.innerHTML = '';
    tfoot.innerHTML = '';

    Object.entries(clientTripsData).forEach(([client, vals]) => {
        const percBookingsCount = totalBookingsCount > 0 ? ((vals.total / totalBookingsCount) * 100).toFixed(2) : 0;
        const percBookingsAmount = totalBookingsAmount > 0 ? ((vals.amountTotal / totalBookingsAmount) * 100).toFixed(2) : 0;
        const cancelled = +vals.cancelled || 0;
        const averageDifficulty = totalBookingsCount > 0 ? (vals.totalDifficulty / vals.total).toFixed(2) : 0;
        const averagePerTrip = totalBookingsCount > 0 ? (vals.amountTotal / vals.total).toFixed(2) : 0;

        const row = document.createElement('tr');
        const drillUrl = buildDrillDownUrl('/trips', 'client_filter', client, false, 'Booking');

        row.innerHTML = `
            <td>${client} <a href="${drillUrl}" target="_blank" title="Ver detalle" style="opacity:0.65;margin-left:4px;"><i class="fas fa-arrow-up-right-from-square" style="font-size:0.75em;"></i></a></td>
            <td>${vals.total}</td>
            <td>${percBookingsCount}%</td>
            <td>USD ${vals.amountTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td>${percBookingsAmount}%</td>
            <td>USD ${averagePerTrip.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
            <td>${averageDifficulty}</td>
            <td>${cancelled}</td>
        `;
        tbody.appendChild(row);
    });

    // 🔹 Agregar fila total al TFOOT

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row table-secondary fw-bold';
    totalRow.innerHTML = `
        <td><strong>TOTAL</strong></td>
        <td>${totalBookingsCount}</td>
        <td>-</td>
        <td>USD ${totalBookingsAmount}</td>
        <td>-</td>
        <td>${totalPerTrip}</td>
        <td>${totalAverageDifficulty}</td>
        <td>${totalCancelled}</td>
    `;
    tfoot.appendChild(totalRow);

    // volver a crear el datatable (o regenerar su contenido)
    create_datatable_stats("summary-clients-trips-table");
}


// ==================== FUNCIÓN: Renderizar gráficos ====================
function renderChartsTripsClients() {
    const clients = Object.keys(clientTripsData);
    const bookingsCount = clients.map(c => clientTripsData[c].total);
    const bookingsAmount = clients.map(c => clientTripsData[c].amountTotal);

    // Destruir gráficos anteriores
    if (chartsClientsTrips.count) chartsClients.count.destroy();
    if (chartsClientsTrips.amount) chartsClients.amount.destroy();

    // Gráfico de Cantidad
    const ctxCount = document.getElementById('chartClientsCountTripsCanvas').getContext('2d');
    chartsClientsTrips.count = new Chart(ctxCount, {
        type: 'pie',
        data: {
            labels: clients,
            datasets: [{
                data: bookingsCount,
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
            }
        }
    });

    // Gráfico de Monto
    const ctxAmount = document.getElementById('chartClientsAmountTripsCanvas').getContext('2d');
    chartsClientsTrips.amount = new Chart(ctxAmount, {
        type: 'pie',
        data: {
            labels: clients,
            datasets: [{
                data: bookingsAmount,
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
            if (btn_id == "1") {
                extraData.week = document.getElementById("week-select").value;
            } else if (btn_id == "2") {
                extraData.month = document.getElementById("month-select").value;
                extraData.year = document.getElementById("year-select").value;
            } else if (btn_id == "3") {
                extraData.season = document.getElementById("season-select").value;
            }else if (btn_id == "4") {
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

/**
 * Calcula las fechas de inicio (lunes) y fin (domingo) de una semana dada en el año actual.
 * @param {number} weekNumber - El número de semana ISO (1-53).
 * @param {number} year - El año.
 * @returns {{date_from: string, date_to: string}}
 */
function getWeekDates(weekNumber, year) {
    // 1. Crear una fecha que caiga en el día 4 de la primera semana del año (siempre en la semana 1)
    const date = new Date(year, 0, 1 + (weekNumber - 1) * 7);
    
    // 2. Establecer el lunes de la semana actual
    // getDay() devuelve 0 (domingo) a 6 (sábado). Queremos que 1 sea lunes y 0 sea domingo.
    // El cálculo 'day - 1' ajusta para que el lunes sea 0, pero necesitamos que la semana empiece en lunes.
    // Si es domingo (0), queremos movernos -6 días para el lunes anterior.
    let day = date.getDay(); 
    // Mueve la fecha al Lunes: Si es domingo (0), day - 1 da -1. 
    // Usamos el ajuste ISO: 1 (lunes) a 7 (domingo). (day + 6) % 7 da 0 para lunes, 6 para domingo.
    const dayOfWeek = (day === 0) ? 6 : day - 1; 

    // Mover la fecha al lunes de la semana
    date.setDate(date.getDate() - dayOfWeek);
    const date_from = date.toISOString().split('T')[0]; // Formato YYYY-MM-DD
    
    // Mover al domingo (6 días después)
    date.setDate(date.getDate() + 6);
    const date_to = date.toISOString().split('T')[0]; // Formato YYYY-MM-DD

    return { date_from, date_to };
}

/**
 * Función auxiliar para obtener el número de semana ISO 8601 de una fecha.
 * Esto es necesario para inicializar el select con la semana actual.
 * @param {Date} date 
 * @returns {number}
 */

function getWeekNumber(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}
/**
 * Calcula el primer y último día de un mes específico.
 * @param {number} year - El año seleccionado.
 * @param {number} month - El número del mes (1 = Enero, 12 = Diciembre).
 * @returns {{date_from: string, date_to: string}}
 */
function getMonthDates(year, month) {
    // El mes en el constructor de Date es base 0 (0 = Enero, 11 = Diciembre),
    // por eso usamos 'month - 1' para el mes de inicio.
    
    // Primer día del mes (date_from)
    const firstDay = new Date(year, month - 1, 1);

    // Último día del mes (date_to)
    // Usamos el mes siguiente (month) y el día 0. El día 0 de un mes es el último día del mes anterior.
    const lastDay = new Date(year, month, 0);

    // Formatear las fechas a YYYY-MM-DD
    const date_from = firstDay.toISOString().split('T')[0];
    const date_to = lastDay.toISOString().split('T')[0];

    return { date_from, date_to };
}

function inicialize_presentations() {
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
                const currentYear = new Date().getFullYear(); // Usamos el año actual

                // 1. Obtener las fechas de inicio y fin
                const { date_from, date_to } = getWeekDates(Number(week), currentYear);

                // 2. Subir las fechas a los parámetros
                queryParams.append('date_from', date_from);
                queryParams.append('date_to', date_to);

                queryParams.append('filter', 'weekly');

                const typeReport = document.getElementById('type-select-1').value;

                // Redirigir a la página de reporte
                window.location.href = `/stats/${typeReport}/?${queryParams.toString()}`;
            } else if (formId === '2-stats-form') {
                // Mensual
                const month = document.getElementById('month-select').value;
                const year = document.getElementById('year-select').value;

                // 1. Obtener las fechas de inicio y fin
                // Convertimos a Number() por seguridad, ya que los valores del select son strings
                const { date_from, date_to } = getMonthDates(Number(year), Number(month));
                
                // 2. Subir las fechas a los parámetros
                queryParams.append('date_from', date_from);
                queryParams.append('date_to', date_to);
                queryParams.append('filter', 'monthly');
                
                const typeReport = document.getElementById('type-select-2').value;

                // Redirigir a la página de reporte
                window.location.href = `/stats/${typeReport}/?${queryParams.toString()}`;
            } else if (formId === '3-stats-form') {
                // Temporada
                const season = document.getElementById('season-select').value;
                const season_to = Number(season) + 1
                
                const date_from_obj = new Date(Number(season), 5, 1);
                const date_from = date_from_obj.toISOString().split('T')[0];
                const date_to_obj = new Date(season_to, 4, 30)
                const date_to = date_to_obj.toISOString().split('T')[0];
                
                // 2. Subir las fechas a los parámetros
                queryParams.append('date_from', date_from);
                queryParams.append('date_to', date_to);
                queryParams.append('filter', 'season');
                
                const typeReport = document.getElementById('type-select-3').value;

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
        responsive: true,
        order: [[1, "desc"]],
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });
}