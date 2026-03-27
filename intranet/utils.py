from datetime import datetime, date, timedelta
from .models import Entry, Holidays, Trip, Absence
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models
from tariff.models import Change, User

def update_entries():

    # All entries
    entries = Entry.objects.all()

    for entry in entries:
        update_timingStatus(entry)


def update_timingStatus(entry):

    # Today
    today = date.today()

    difference = get_working_days(entry.starting_date, today)

    # Prepare the colors if it is quote
    if entry.status == "Quote":
        if difference == 0:
            entry.timingStatus = "light"
        elif difference == 1:
            entry.timingStatus = "warning"
        elif difference >= 2 and difference < 6:
            entry.timingStatus = "info"
        elif difference >= 6:
            entry.timingStatus = "danger"
    elif entry.status == "Booking" or entry.status == "Final Itinerary":
        if difference <= 2:
            entry.timingStatus = "light"
        elif difference == 3:
            entry.timingStatus = "warning"
        elif difference >= 4 and difference < 7:
            entry.timingStatus = "info"
        elif difference >= 8:
            entry.timingStatus = "danger"
    else:
        if difference <= 3:
            entry.timingStatus = "light"
        elif difference == 4:
            entry.timingStatus = "warning"
        elif difference >= 5 and difference < 10:
            entry.timingStatus = "info"
        elif difference >= 11:
            entry.timingStatus = "danger"

    entry.save()


def get_working_days(from_date, to_date):

    # Normalize the dates
    if hasattr(from_date, "date"):
        from_date = from_date.date()
    if hasattr(to_date, "date"):
        to_date = to_date.date()

    # Check if the order is correct
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Get the quantity of holidays
    n_holidays = Holidays.objects.filter(
        workable=False,
        date_from__range=(from_date, to_date)
    ).count()

    working_days = (to_date - from_date).days - n_holidays
    return working_days


def get_working_days_worker(from_date, to_date, worker):

    working_days = get_working_days(from_date, to_date)

    holidays_worker = Holidays.objects.filter(working_user=worker).filter(date_from__range=(from_date, to_date)).count()

    absence_worker = Absence.objects.filter(absence_user=worker).filter(date_from__range=(from_date, to_date)).count()

    return working_days + holidays_worker - absence_worker


def check_duplicate_trips(date_from, date_to):
    duplicated_files = []

    filtered_trips = Trip.objects.filter(travelling_date__range=(date_from, date_to))
    for trip in filtered_trips:
        for trip_compared in filtered_trips:
            if trip.tourplanId:
                if trip.tourplanId == trip_compared.tourplanId and trip.id != trip_compared.id:
                    duplicated_files.append((trip))

    return duplicated_files


def check_missing_amounts(date_from, date_to):
    missing_amounts_entries = []

    for entry in Entry.objects.filter(starting_date__range=(date_from, date_to)):
        if (entry.amount == 0 or entry.amount is None) and (entry.status == "Quote" and entry.version_quote == "A" or entry.status == "Booking" and entry.version == "1"):
            missing_amounts_entries.append(entry)

    return missing_amounts_entries


def check_incongruent_trip_dates(date_from, date_to):
    incongruent_trips = []

    for trip in Trip.objects.filter(travelling_date__range=(date_from, date_to)):
        if trip.starting_date == trip.travelling_date or trip.travelling_date < trip.starting_date:
            incongruent_trips.append(trip)

    return incongruent_trips


def check_incongruent_entry_dates(date_from, date_to):
    incongruent_entries = []

    for entry in Entry.objects.filter(starting_date__range=(date_from, date_to)):
        difference = (entry.closing_date - entry.starting_date).days
        if entry.starting_date == entry.trip.travelling_date or entry.starting_date > entry.closing_date or difference < 0 or difference > 30:
            incongruent_entries.append(entry)

    return incongruent_entries


def send_templated_email(subject, to_emails, template_name, context):
    html_content = render_to_string(template_name, context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body="Este email requiere HTML.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_emails,
    )

    msg.attach_alternative(html_content, "text/html")
    msg.send()


def build_margin_warning_context(user):
    """
    Build context for margin_warning.html for a single sales user.

    Includes all their trips travelling in the next 12 months
    where rent_perc > 0.35 or rent_perc < 0.15.

    Returns (subject, to_emails, template, context) tuple.
    """
    today = date.today()
    date_limit = today + timedelta(days=365)

    trips_qs = Trip.objects.select_related(
        "client", "operations_user"
    ).filter(
        responsable_user=user,
        status="Booking",
        travelling_date__range=(today, date_limit),
        ignore_margin_warning=False,
        margin_reviewed=False,
    ).filter(
        models.Q(rent_perc__gt=0.35) | models.Q(rent_perc__lt=0.15)
    ).order_by("travelling_date")

    def _first_name(u):
        if not u:
            return ""
        full = getattr(u, "other_name", None) or u.get_full_name() or u.username
        return full.split()[0] if full else ""

    trips = [
        {
            "name": t.name,
            "tourplanId": t.tourplanId,
            "travelling_date": t.travelling_date,
            "quantity_pax": t.quantity_pax,
            "rent_perc_display": round(t.rent_perc * 100, 1),
            "rent_perc_low": t.rent_perc < 0.15,
            "operations_user_name": t.operations_user.username if t.operations_user else "",
            "client_name": t.client.name if t.client else "",
        }
        for t in trips_qs
    ]

    _site_url = getattr(settings, "SITE_URL", "https://sayaliwen.pythonanywhere.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    subject = "⚠️ Aliwen – Advertencias de Rentabilidad"
    to_emails = [user.email]
    template = "emails/margin_warning.html"
    context = {
        "user_name": _first_name(user),
        "today": today.strftime("%B %d, %Y"),
        "trips": trips,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
        "site_url": site_url,
    }

    return subject, to_emails, template, context


def send_margin_warnings():
    """
    Send margin warning emails to all Ventas users that have out-of-range trips.

    Usage from Django shell:
        from intranet.utils import send_margin_warnings
        send_margin_warnings()
    """
    from .models import User as IntranetUser
    sales_users = IntranetUser.objects.filter(userType="Ventas").exclude(email="")

    import time

    sent = 0
    skipped = 0
    for user in sales_users:
        subject, to_emails, template, context = build_margin_warning_context(user)
        if not context["trips"]:
            skipped += 1
            continue
        send_templated_email(subject, to_emails, template, context)
        print(f"  Sent to {user.email} — {len(context['trips'])} trip(s)")
        sent += 1
        time.sleep(10)

    print(f"\nEmails sent: {sent} | Skipped (no flagged trips): {skipped}")



def build_margin_warning_manager_context():
    """
    Build context for margin_warning_manager.html for the department head (Victoria, username "VA").

    Includes all Aliwen-department trips travelling in the next 2 months
    with status "Booking" and rent_perc > 0.35 or rent_perc < 0.15,
    grouped by seller (responsable_user) and ordered by travelling_date within each group.

    Returns (subject, to_emails, template, context) tuple.
    """
    from .models import User as IntranetUser

    today = date.today()
    date_limit = today + timedelta(days=60)

    trips_qs = Trip.objects.select_related(
        "client", "operations_user", "responsable_user"
    ).filter(
        department="AI",
        status="Booking",
        travelling_date__range=(today, date_limit),
        ignore_margin_warning=False,
        margin_reviewed=False,
    ).filter(
        models.Q(rent_perc__gt=0.35) | models.Q(rent_perc__lt=0.15)
    ).order_by("responsable_user__username", "travelling_date")

    def _first_name(u):
        if not u:
            return ""
        full = getattr(u, "other_name", None) or u.get_full_name() or u.username
        return full.split()[0] if full else ""

    # Group trips by seller
    from itertools import groupby
    seller_groups = []
    for seller, seller_trips in groupby(trips_qs, key=lambda t: t.responsable_user):
        trips_list = [
            {
                "name": t.name,
                "tourplanId": t.tourplanId,
                "travelling_date": t.travelling_date,
                "quantity_pax": t.quantity_pax,
                "rent_perc_display": round(t.rent_perc * 100, 1),
                "rent_perc_low": t.rent_perc < 0.15,
                "operations_user_name": t.operations_user.username if t.operations_user else "",
                "client_name": t.client.name if t.client else "",
            }
            for t in seller_trips
        ]
        seller_name = _first_name(seller) if seller else "Sin vendedor"
        seller_groups.append({"seller_name": seller_name, "trips": trips_list})

    _site_url = getattr(settings, "SITE_URL", "https://sayaliwen.pythonanywhere.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    manager_name = "Vic"

    subject = "⚠️ Aliwen Intranet – Advertencias de Rentabilidad (Aliwen)"
    to_emails = ["va@aliwenincoming.com.ar"]
    template = "emails/margin_warning_manager.html"
    context = {
        "user_name": manager_name,
        "today": today.strftime("%B %d, %Y"),
        "seller_groups": seller_groups,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
        "site_url": site_url,
    }

    return subject, to_emails, template, context


def send_margin_warning_manager():
    """
    Send the department-level margin warning email to Victoria (username "VA").

    Usage from Django shell:
        from intranet.utils import send_margin_warning_manager
        send_margin_warning_manager()
    """
    subject, to_emails, template, context = build_margin_warning_manager_context()
    total_trips = sum(len(g["trips"]) for g in context["seller_groups"])
    if not total_trips:
        print("No flagged trips in the next 2 months for Aliwen department. Email not sent.")
        return
    send_templated_email(subject, to_emails, template, context)
    print(f"Sent to {to_emails[0]} — {len(context['seller_groups'])} seller(s), {total_trips} trip(s)")


def report_tariff_error_hotel(user, supplier_obj, note):

    supplier = supplier_obj.name
    user_name = user.other_name

    subject = f"INTRANET - Error en el tarifario - Hotel {supplier}"
    email = ["diana@aliwenincoming.com.ar"]
    template = "emails/tariff_error.html"

    context = {
        "user_name": user_name,
        "supplier": supplier,
        "note": note,
        }

    return subject, email, template, context


def build_tariff_client_news_context(client, date_from=None):
    """
    Build the context for tariff_client_news.html.

    Groups Change objects by location, then separates AC (accommodation)
    from NA (services) changes. AC changes are further grouped by supplier.

    Args:
        client: Client instance
        date_from: optional date to filter Changes from (inclusive)
    Returns:
        (subject, to_emails, template, context) tuple
    """
    changes_qs = Change.objects.select_related(
        "rate_line__group__product__supplier",
        "rate_line__group__product__group__location",
    )
    if date_from:
        changes_qs = changes_qs.filter(date__gte=date_from)

    # Build a dict keyed by location id to preserve ordering
    locations_map = {}  # location_id -> {"name": ..., "ac": {supplier_id: {...}}, "na": [...]}

    for change in changes_qs:
        product = change.rate_line.group.product
        location = product.group.location
        supplier = product.supplier

        if location.id not in locations_map:
            locations_map[location.id] = {
                "name": location.name,
                "_order": location.order,
                "ac": {},   # supplier_id -> {"name": ..., "changes": [...]}
                "na": [],
            }

        loc = locations_map[location.id]
        change_entry = {"type": change.type, "product": change.rate_line.group.product.name, "from": change.rate_line.date_from, "to": change.rate_line.date_to}

        if product.type_service == "AC":
            if supplier.id not in loc["ac"]:
                loc["ac"][supplier.id] = {"name": supplier.name, "changes": []}
            loc["ac"][supplier.id]["changes"].append(change_entry)
        else:
            loc["na"].append(change_entry)

    # Sort locations by their order field and flatten to list
    sorted_locations = sorted(locations_map.values(), key=lambda l: l["_order"])
    locations = []
    for loc in sorted_locations:
        ac_changes = list(loc["ac"].values()) if loc["ac"] else None
        na_changes = loc["na"] if loc["na"] else None
        if ac_changes or na_changes:
            locations.append({
                "name": loc["name"],
                "ac_changes": ac_changes,
                "na_changes": na_changes,
            })

    to_emails = client.email

    _site_url = getattr(settings, "SITE_URL", "https://sayaliwen.pythonanywhere.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    subject = f"Aliwen Incoming – Rate Update"
    template = "emails/tariff_client_news.html"
    context = {
        "client_name": client.other_name,
        "today": date.today().strftime("%B %d, %Y"),
        "locations": locations,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
    }

    return subject, to_emails, template, context


def build_tariff_team_news_context(date_from=None):
    """
    Build the context for tariff_team_news.html (internal team email).

    Covers changes from the Monday of the current week up to today.
    Sends to all non-Cliente users that have an email address.

    Args:
        date_from: optional date override (defaults to Monday of current week)
    Returns:
        (subject, to_emails, template, context) tuple
    """
    today = date.today()

    if date_from is None:
        date_from = today - timedelta(days=today.weekday())  # Monday of current week

    changes_qs = Change.objects.select_related(
        "rate_line__group__product__supplier",
        "rate_line__group__product__group__location",
    ).filter(date__gte=date_from)

    locations_map = {}

    for change in changes_qs:
        product = change.rate_line.group.product
        location = product.group.location
        supplier = product.supplier

        if location.id not in locations_map:
            locations_map[location.id] = {
                "name": location.name,
                "_order": location.order,
                "ac": {},
                "na": [],
            }

        loc = locations_map[location.id]
        change_entry = {
            "type": change.type,
            "product": change.rate_line.group.product.name,
            "from": change.rate_line.date_from,
            "to": change.rate_line.date_to,
        }

        if product.type_service == "AC":
            if supplier.id not in loc["ac"]:
                loc["ac"][supplier.id] = {"name": supplier.name, "changes": []}
            loc["ac"][supplier.id]["changes"].append(change_entry)
        else:
            loc["na"].append(change_entry)

    sorted_locations = sorted(locations_map.values(), key=lambda l: l["_order"])
    locations = []
    for loc in sorted_locations:
        ac_changes = list(loc["ac"].values()) if loc["ac"] else None
        na_changes = loc["na"] if loc["na"] else None
        if ac_changes or na_changes:
            locations.append({
                "name": loc["name"],
                "ac_changes": ac_changes,
                "na_changes": na_changes,
            })

    internal_users = User.objects.filter(
        userType__in=["Admin", "Regular"]
    ).exclude(email="").values_list("email", flat=True)
    to_emails = list(internal_users)

    _site_url = getattr(settings, "SITE_URL", "https://sayaliwen.pythonanywhere.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    subject = "Aliwen – Actualización Tarifario Semanal"
    template = "emails/tariff_team_news.html"
    context = {
        "today": today.strftime("%B %d, %Y"),
        "week_from": date_from.strftime("%-d/%-m/%Y"),
        "week_to": today.strftime("%-d/%-m/%Y"),
        "locations": locations,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
    }

    return subject, to_emails, template, context


def report_tariff_error_service(user, product_obj, note):

    product = product_obj.name
    user_name = user.other_name
    location = product_obj.group.location.name

    subject = f"INTRANET - Error en el tarifario - Servicio {product} - {location}"
    email = ["diana@aliwenincoming.com.ar"]
    template = "emails/tariff_error.html"

    context = {
        "user_name": user_name,
        "supplier": supplier,
        "note": note,
        }

    return subject, email, template, context


# ---------------------------------------------------------------------------
# Tourplan DB sync
# ---------------------------------------------------------------------------

_TOURPLAN_SYNC_QUERY = """
SELECT DISTINCT
    BHD.FULL_REFERENCE    AS tourplan_id,
    BHD.TRAVELDATE        AS travelling_date,
    BHD.LAST_SERVICE_DATE AS out_date,
    BHD.STATUS            AS status,
    BHD.NAME              AS pax_name,
    BHD.UDTEXT3           AS dh_type,
    BHD.UDTEXT2           AS dh_name,
    BHD.SALE4             AS responsable_code,
    BHD.CONSULTANT        AS operations_code,
    DRM.NAME              AS agent_name,
    BHD.AGENT_REFERENCE   AS client_reference,
    ISNULL(RTRIM(LTRIM((
        SELECT STUFF((
            SELECT ', ' + RTRIM(LTRIM(CRM.NAME))
            FROM CRM
            JOIN OPT ON OPT.SUPPLIER = CRM.CODE
            JOIN BSL ON BSL.OPT_ID = OPT.OPT_ID
            WHERE BSL.BHD_ID = BHD.BHD_ID
              AND OPT.SERVICE = 'GU'
              AND OPT.LOCATION = 'BUE'
            GROUP BY CRM.NAME
            FOR XML PATH ('')
        ), 1, 1, '')
    ))), '') AS guide,
    CASE BHD.STATUS
        WHEN 'HL' THEN 0 WHEN 'XC' THEN 0 WHEN 'XX' THEN 0
        ELSE BSD.PAX
    END AS num_pax,
    CASE BHD.STATUS
        WHEN 'HL' THEN 0
        ELSE (BSD.AGENT - BSD.COST) / CASE BSD.AGENT WHEN 0 THEN 1 ELSE BSD.AGENT END
    END AS rent_perc,
    CASE BHD.STATUS WHEN 'HL' THEN 0 ELSE BSD.AGENT END AS amount
FROM BHD
JOIN DRM ON DRM.CODE = BHD.AGENT
JOIN BSD ON BSD.BHD_ID = BHD.BHD_ID AND BSD.BSL_ID = 0
WHERE BHD.BRANCH = 'AL'
  AND BHD.TRAVELDATE >= ?
  AND BHD.TRAVELDATE <= ?
"""

_BOOKING_STATUSES  = {"OK", "FI", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
_CANCELLED_STATUSES = {"RX", "XC", "XX"}


def get_tourplan_connection():
    import pyodbc
    tp = settings.TOURPLAN_DB
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={tp['SERVER']};"
        f"DATABASE={tp['DATABASE']};"
        f"UID={tp['UID']};"
        f"PWD={tp['PWD']};"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def sync_from_tourplan_db():
    """
    Connects directly to the Tourplan SQL Server DB and updates Trip records
    using the same logic as upload_data() but without a CSV file.
    Returns (updated_count, not_found_count).
    """
    from difflib import SequenceMatcher

    today = date.today()
    date_from = today.replace(year=today.year - 2).strftime("%Y%m%d")
    date_to   = today.replace(year=today.year + 3).strftime("%Y%m%d")

    # Pre-fetch lookups
    users_by_other_tp = {u.other_tp: u for u in User.objects.all() if u.other_tp}

    trips_by_tourplan = {
        t.tourplanId: t
        for t in Trip.objects.select_related("responsable_user", "operations_user")
        .exclude(tourplanId="").exclude(tourplanId__isnull=True)
    }

    entry_tp_ids = set(
        Entry.objects.exclude(tourplanId="").exclude(tourplanId__isnull=True)
        .values_list("tourplanId", flat=True)
    )

    client_ref_set = set()
    for ref in (Trip.objects
                .exclude(client_reference="").exclude(client_reference__isnull=True)
                .values_list("client_reference", flat=True)):
        if ref:
            r = str(ref).strip()
            client_ref_set.add(r)
            if "/" in r:
                client_ref_set.add(r.split("/")[0])

    # Fetch rows from Tourplan
    conn = get_tourplan_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_TOURPLAN_SYNC_QUERY, date_from, date_to)
        rows = cursor.fetchall()
    finally:
        conn.close()

    updated_count  = 0
    not_found_count = 0
    trips_to_update = []
    csv_quote_tp_ids    = set()
    csv_client_ref_to_tp = {}

    for row in rows:
        tp_id = str(row.tourplan_id).strip() if row.tourplan_id else ""
        if not tp_id:
            continue

        raw_status       = str(row.status).strip() if row.status else ""
        is_booking_row   = raw_status in _BOOKING_STATUSES
        is_cancelled_row = raw_status in _CANCELLED_STATUSES

        csv_client_ref   = str(row.client_reference).strip() if row.client_reference else ""
        client_ref_prefix = csv_client_ref.split("/")[0].strip() if "/" in csv_client_ref else csv_client_ref
        agent_name       = str(row.agent_name).strip() if row.agent_name else ""
        is_consumidor_final = agent_name.lower().startswith("consumidor final")

        if not is_booking_row and not is_cancelled_row:
            csv_quote_tp_ids.add(tp_id)

        if client_ref_prefix and not is_consumidor_final and is_booking_row:
            pax_name = str(row.pax_name).strip() if row.pax_name else ""
            if client_ref_prefix not in csv_client_ref_to_tp:
                csv_client_ref_to_tp[client_ref_prefix] = {"tp_id": tp_id, "name": pax_name}

        if tp_id not in trips_by_tourplan:
            if tp_id in entry_tp_ids:
                continue
            if not is_consumidor_final and client_ref_prefix and client_ref_prefix in client_ref_set:
                continue
            if is_booking_row or is_cancelled_row:
                not_found_count += 1
            continue

        trip = trips_by_tourplan[tp_id]
        updated_count += 1

        # travelling_date — pyodbc returns datetime/date objects directly
        if row.travelling_date:
            trip.travelling_date = row.travelling_date

        # out_date
        if row.out_date:
            trip.out_date = row.out_date

        # dh_type (S / B / F)
        dh_type_val = str(row.dh_type).strip() if row.dh_type else ""
        if dh_type_val in ("S", "B", "F"):
            trip.dh_type = dh_type_val

        # responsable_user
        responsable_code = str(row.responsable_code).strip() if row.responsable_code else ""
        if responsable_code in users_by_other_tp:
            trip.responsable_user = users_by_other_tp[responsable_code]

        # operations_user
        operations_code = str(row.operations_code).strip() if row.operations_code else ""
        if operations_code in users_by_other_tp:
            trip.operations_user = users_by_other_tp[operations_code]

        # dh name (strip "DH " prefix if present)
        dh_name_val = str(row.dh_name).strip() if row.dh_name else ""
        if dh_name_val.upper().startswith("DH "):
            dh_name_val = dh_name_val[3:].strip()
        if dh_name_val:
            trip.dh = dh_name_val

        # guide
        trip.guide = str(row.guide).strip() if row.guide else ""

        # rent_perc — SQL already returns decimal (e.g. 0.35), no /100 needed
        if row.rent_perc is not None:
            try:
                trip.rent_perc = float(row.rent_perc)
            except (ValueError, TypeError):
                pass

        # amount
        if row.amount:
            try:
                trip.amount = int(float(row.amount))
            except (ValueError, TypeError):
                pass

        trips_to_update.append(trip)

    if trips_to_update:
        Trip.objects.bulk_update(trips_to_update, [
            "travelling_date", "out_date", "dh_type",
            "responsable_user", "operations_user", "dh",
            "guide", "rent_perc", "amount",
        ])
        for trip in trips_to_update:
            if trip.amount:
                tp_entry = Entry.objects.filter(tourplanId=trip.tourplanId).first()
                if tp_entry:
                    tp_entry.amount = trip.amount
                    tp_entry.save()

    return updated_count, not_found_count

    return subject, email, template, context