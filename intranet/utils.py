import re
from html import unescape
from datetime import datetime, date, timedelta
from .models import Entry, Holidays, Trip, Absence
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.db import models
from tariff.models import Change, User

def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    return ' '.join(text.split()).strip()


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

    # Normalize strings
    if isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date)
    if isinstance(to_date, str):
        to_date = datetime.fromisoformat(to_date)

    # Normalize datetime → date
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


_ABSENCE_TYPES_REDUCE_WORK = frozenset({
    'Vacaciones', 'Beneficio Vacaciones', 'Compensatorios',
    'Cumpleaños', 'Cumpleaños en baja', 'Exámenes/Día de Estudio',
    'Sin goce de sueldo', 'Viernes OFF alta',
})


def _days_overlap(records, from_date, to_date):
    """Sum actual calendar days (inclusive) covered by a queryset of date-range records."""
    total = 0
    for r in records:
        start = max(r.date_from, from_date)
        end = min(r.date_to, to_date)
        if start <= end:
            total += (end - start).days + 1
    return total


def get_working_days_worker(from_date, to_date, worker):
    # Normalize inputs (same logic as get_working_days)
    if isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date)
    if isinstance(to_date, str):
        to_date = datetime.fromisoformat(to_date)
    if hasattr(from_date, "date"):
        from_date = from_date.date()
    if hasattr(to_date, "date"):
        to_date = to_date.date()
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    working_days = get_working_days(from_date, to_date)

    # Days this person worked on a company holiday (Feriado trabajado absence type)
    worked_holiday_records = Absence.objects.filter(
        absence_user=worker,
        type_absence='Feriado trabajado',
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    worked_holiday_days = _days_overlap(worked_holiday_records, from_date, to_date)

    # Absence days that reduce working count
    absence_records = Absence.objects.filter(
        absence_user=worker,
        type_absence__in=_ABSENCE_TYPES_REDUCE_WORK,
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    absence_days = _days_overlap(absence_records, from_date, to_date)

    return working_days + worked_holiday_days - absence_days


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
    from django.db.models import Q
    return Entry.objects.filter(
        starting_date__range=(date_from, date_to)
    ).filter(
        Q(amount=0) | Q(amount__isnull=True)
    ).filter(
        Q(status="Quote", version_quote="A") | Q(status="Booking", version="1")
    ).select_related('trip')


def check_incongruent_trip_dates(date_from, date_to):
    incongruent_trips = []

    for trip in Trip.objects.filter(travelling_date__range=(date_from, date_to)):
        if trip.starting_date == trip.travelling_date or trip.travelling_date < trip.starting_date:
            incongruent_trips.append(trip)

    return incongruent_trips


def check_incongruent_entry_dates(date_from, date_to):
    from django.db.models import Q, F
    return Entry.objects.filter(
        starting_date__range=(date_from, date_to)
    ).select_related('trip').filter(
        Q(starting_date=F('trip__travelling_date')) |
        Q(starting_date__gt=F('closing_date')) |
        Q(closing_date__gt=F('starting_date') + timedelta(days=30))
    )


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
    ).exclude(
        amount__isnull=True
    ).exclude(
        amount=0
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
    ).exclude(
        amount__isnull=True
    ).exclude(
        amount=0
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
    BHD.UDTEXT2           AS dh_type,
    BHD.SALE3             AS dh_name,
    BHD.CONSULTANT        AS responsable_code,
    BHD.SALE1             AS operations_code,
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
    CASE BHD.STATUS WHEN 'HL' THEN 0 ELSE BSD.AGENT END AS amount,
    ISNULL((
        SELECT STUFF((
            SELECT ' | ' + RTRIM(LTRIM(CAST(N2.MESSAGE_TEXT AS NVARCHAR(MAX))))
            FROM NTS N2
            WHERE N2.BHD_ID = BHD.BHD_ID AND N2.CATEGORY = 'REN'
            FOR XML PATH (''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 3, '')
    ), '') AS tp_notes
FROM BHD
JOIN DRM ON DRM.CODE = BHD.AGENT
JOIN BSD ON BSD.BHD_ID = BHD.BHD_ID AND BSD.BSL_ID = 0
WHERE BHD.BRANCH = 'AL'
  AND BHD.TRAVELDATE >= %s
  AND BHD.TRAVELDATE <= %s
"""

_BOOKING_STATUSES  = {"OK", "FI", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
_CANCELLED_STATUSES = {"RX", "XC", "XX"}


def get_tourplan_connection():
    import pymssql
    tp = settings.TOURPLAN_DB
    return pymssql.connect(
        server=tp["SERVER"],
        port=tp.get("PORT", 1433),
        database=tp["DATABASE"],
        user=tp["UID"],
        password=tp["PWD"],
        login_timeout=30,
        as_dict=True,
    )


def sync_from_tourplan_db():
    """
    Connects directly to the Tourplan SQL Server DB and updates Trip records
    using the same logic as upload_data() but without a CSV file.
    Returns (updated_count, no_tp_group1, no_tp_group2, no_tp_group3, not_in_app).
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
        cursor.execute(_TOURPLAN_SYNC_QUERY, (date_from, date_to))
        rows = cursor.fetchall()
    finally:
        conn.close()

    updated_count  = 0
    trips_to_update = []
    csv_quote_tp_ids    = set()
    csv_client_ref_to_tp = {}
    not_in_app = []

    def _s(row, key):
        v = row.get(key)
        return str(v).strip() if v is not None else ""

    for row in rows:
        tp_id = _s(row, "tourplan_id")
        if not tp_id:
            continue

        raw_status       = _s(row, "status")
        is_booking_row   = raw_status in _BOOKING_STATUSES
        is_cancelled_row = raw_status in _CANCELLED_STATUSES

        csv_client_ref    = _s(row, "client_reference")
        client_ref_prefix = csv_client_ref.split("/")[0].strip() if "/" in csv_client_ref else csv_client_ref
        agent_name        = _s(row, "agent_name")
        is_consumidor_final = agent_name.lower().startswith("consumidor final")

        if not is_booking_row and not is_cancelled_row:
            csv_quote_tp_ids.add(tp_id)

        if client_ref_prefix and not is_consumidor_final and is_booking_row:
            pax_name = _s(row, "pax_name")
            if client_ref_prefix not in csv_client_ref_to_tp:
                csv_client_ref_to_tp[client_ref_prefix] = {"tp_id": tp_id, "name": pax_name}

        if tp_id not in trips_by_tourplan:
            if tp_id in entry_tp_ids:
                continue
            if not is_consumidor_final and client_ref_prefix and client_ref_prefix in client_ref_set:
                continue
            if is_booking_row or is_cancelled_row:
                trip_status = "Booking" if raw_status in _BOOKING_STATUSES else "Cancelado"
                num_pax = 2
                try:
                    num_pax = int(row.get("num_pax") or 2)
                except (ValueError, TypeError):
                    pass
                rent_perc_raw = ""
                rp = row.get("rent_perc")
                if rp is not None:
                    try:
                        rent_perc_raw = str(round(float(rp) * 100, 2)) + "%"
                    except (ValueError, TypeError):
                        pass
                amount_raw = ""
                am = row.get("amount")
                if am:
                    try:
                        amount_raw = str(int(float(am)))
                    except (ValueError, TypeError):
                        pass
                dh_name_raw = _s(row, "dh_name")
                if dh_name_raw.upper().startswith("DH "):
                    dh_name_raw = dh_name_raw[3:].strip()
                td = row.get("travelling_date")
                od = row.get("out_date")
                not_in_app.append({
                    "tp_id":            tp_id,
                    "name":             _s(row, "pax_name"),
                    "client_name":      agent_name,
                    "contact_name":     "",
                    "client_reference": csv_client_ref,
                    "travelling_date":  td.strftime("%d/%m/%Y") if td else "",
                    "out_date":         od.strftime("%d/%m/%Y") if od else "",
                    "dh_type":          _s(row, "dh_type"),
                    "vendedor_tp":      _s(row, "responsable_code"),
                    "operations_tp":    _s(row, "operations_code"),
                    "dh_name":          dh_name_raw,
                    "guide":            _s(row, "guide"),
                    "status":           trip_status,
                    "quantity_pax":     num_pax,
                    "rent_perc_raw":    rent_perc_raw,
                    "amount_raw":       amount_raw,
                })
            continue

        trip = trips_by_tourplan[tp_id]
        updated_count += 1

        td = row.get("travelling_date")
        if td:
            trip.travelling_date = td

        od = row.get("out_date")
        if od:
            trip.out_date = od

        dh_type_val = _s(row, "dh_type")
        if dh_type_val in ("S", "B", "F"):
            trip.dh_type = dh_type_val

        responsable_code = _s(row, "responsable_code")
        if responsable_code in users_by_other_tp:
            trip.responsable_user = users_by_other_tp[responsable_code]
        elif responsable_code:
            try:
                trip.responsable_user = User.objects.get(username=responsable_code)
            except User.DoesNotExist:
                pass

        operations_code = _s(row, "operations_code")
        if operations_code in users_by_other_tp:
            trip.operations_user = users_by_other_tp[operations_code]
        elif operations_code:
            try:
                trip.operations_user = User.objects.get(username=operations_code)
            except User.DoesNotExist:
                pass

        dh_name_val = _s(row, "dh_name")
        if dh_name_val.upper().startswith("DH "):
            dh_name_val = dh_name_val[3:].strip()
        trip.dh = dh_name_val

        trip.guide    = _s(row, "guide")
        trip.tp_notes = strip_html(row.get("tp_notes") or "")

        rp = row.get("rent_perc")
        if rp is not None:
            try:
                trip.rent_perc = float(rp)
            except (ValueError, TypeError):
                pass

        am = row.get("amount")
        if am:
            try:
                trip.amount = int(float(am))
            except (ValueError, TypeError):
                pass

        trips_to_update.append(trip)

    if trips_to_update:
        Trip.objects.bulk_update(trips_to_update, [
            "travelling_date", "out_date", "dh_type",
            "responsable_user", "operations_user", "dh",
            "guide", "rent_perc", "amount", "tp_notes",
        ])

    # Build the three "wrong TP" groups (same logic as upload_data)
    no_tp_group1 = []
    no_tp_group2 = []
    no_tp_group3 = []
    for t in (Trip.objects.filter(status="Booking")
              .select_related("responsable_user", "client")
              .order_by("travelling_date")):
        client_ref = str(t.client_reference).strip() if t.client_reference else ""
        cr_prefix = client_ref.split("/")[0] if "/" in client_ref else client_ref
        if sum(c.isdigit() for c in cr_prefix) < 6:
            continue
        match = csv_client_ref_to_tp.get(client_ref) or csv_client_ref_to_tp.get(cr_prefix)
        suggested = ""
        if match:
            ratio = SequenceMatcher(None, t.name.lower(), match["name"].lower()).ratio()
            if ratio >= 0.35:
                suggested = match["tp_id"]

        current_tp = t.tourplanId.strip() if t.tourplanId else ""
        has_no_tp    = not current_tp
        is_quote_tp  = bool(current_tp) and current_tp in csv_quote_tp_ids
        has_wrong_tp = bool(suggested) and bool(current_tp) and current_tp != suggested

        row_data = {
            "trip_id":          t.id,
            "name":             t.name,
            "client_reference": client_ref,
            "travelling_date":  t.travelling_date.strftime("%d/%m/%Y") if t.travelling_date else "",
            "vendedor":         t.responsable_user.other_tp if t.responsable_user else "",
            "client":           t.client.name if t.client else "",
            "suggested_tp":     suggested,
            "current_tp":       current_tp,
        }
        if has_no_tp:
            no_tp_group1.append(row_data)
        elif is_quote_tp:
            no_tp_group2.append(row_data)
        elif has_wrong_tp:
            no_tp_group3.append(row_data)

    return updated_count, no_tp_group1, no_tp_group2, no_tp_group3, not_in_app


def backfill_conversion_dates():
    """
    For every Trip with status "Booking" or "Cancelado" that lacks a conversion_date,
    find its oldest Entry with status="Booking" and version=1 and use that entry's
    starting_date as the conversion_date.

    Trips with no such entry are left untouched (booking pre-dates this feature).

    Usage from Django shell:
        from intranet.utils import backfill_conversion_dates
        updated, skipped = backfill_conversion_dates()
        print(f"Updated: {updated} | No booking entry found: {skipped}")
    """
    trips_qs = Trip.objects.filter(
        status__in=("Booking", "Cancelado"),
        conversion_date__isnull=True,
    )

    # Fetch the earliest Booking v1 entry per trip in one query
    from django.db.models import Min
    earliest = (
        Entry.objects
        .filter(status="Booking", version=1, trip__in=trips_qs)
        .values("trip_id")
        .annotate(first_date=Min("starting_date"))
    )
    date_by_trip = {row["trip_id"]: row["first_date"] for row in earliest}

    to_update = []
    skipped = 0
    for trip in trips_qs:
        first_date = date_by_trip.get(trip.id)
        if first_date:
            trip.conversion_date = first_date
            to_update.append(trip)
        else:
            skipped += 1

    if to_update:
        Trip.objects.bulk_update(to_update, ["conversion_date"])

    print(f"Updated: {len(to_update)} | No booking entry found: {skipped}")
    return len(to_update), skipped


def sync_trip_statuses_from_tourplan():
    """
    One-time utility: for every Trip that has a tourplanId, query Tourplan
    and update Trip.status using the same booking/cancelled mapping as the
    regular sync.

    Mapping:
        Tourplan OK/FI/B1-B8  →  "Booking"
        Tourplan RX/XC/XX     →  "Cancelado"
        anything else (HL…)   →  skipped (app status left unchanged)

    Usage from Django shell:
        from intranet.utils import sync_trip_statuses_from_tourplan
        updated, not_found, skipped = sync_trip_statuses_from_tourplan()
        for r in updated:
            print(r)

    Returns:
        updated   - list of dicts {trip_id, name, tourplanId, tp_raw_status,
                                   old_status, new_status}
        not_found - list of tourplanIds present in the app but absent in Tourplan
        skipped   - count of trips whose status already matched or whose
                    Tourplan status is not in the mapping (HL, etc.)
    """
    trips_qs = (
        Trip.objects
        .exclude(tourplanId="")
        .exclude(tourplanId__isnull=True)
        .only("id", "name", "tourplanId", "status")
    )

    trips_by_tp = {t.tourplanId.strip(): t for t in trips_qs if t.tourplanId}
    if not trips_by_tp:
        print("No trips with tourplanId found.")
        return [], [], 0

    all_tp_ids = list(trips_by_tp.keys())
    placeholders = ", ".join(["%s"] * len(all_tp_ids))
    query = (
        f"SELECT FULL_REFERENCE, STATUS FROM BHD "
        f"WHERE FULL_REFERENCE IN ({placeholders})"
    )

    conn = get_tourplan_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, all_tp_ids)
        rows = cursor.fetchall()
    finally:
        conn.close()

    # One row per FULL_REFERENCE; keep the first if duplicates exist
    tp_status_map = {}
    for row in rows:
        ref = (row.get("FULL_REFERENCE") or "").strip()
        if ref and ref not in tp_status_map:
            tp_status_map[ref] = (row.get("STATUS") or "").strip()

    updated    = []
    not_found  = []
    skipped    = 0
    to_update  = []

    for tp_id, trip in trips_by_tp.items():
        if tp_id not in tp_status_map:
            not_found.append(tp_id)
            continue

        raw = tp_status_map[tp_id]
        if raw in _BOOKING_STATUSES:
            new_status = "Booking"
        elif raw in _CANCELLED_STATUSES:
            new_status = "Cancelado"
        else:
            skipped += 1
            continue

        if trip.status == new_status:
            skipped += 1
            continue

        updated.append({
            "trip_id":       trip.id,
            "name":          trip.name,
            "tourplanId":    tp_id,
            "tp_raw_status": raw,
            "old_status":    trip.status,
            "new_status":    new_status,
        })
        trip.status = new_status
        to_update.append(trip)

    if to_update:
        Trip.objects.bulk_update(to_update, ["status"])

    print(f"Updated: {len(updated)} | Not found in Tourplan: {len(not_found)} | Skipped: {skipped}")
    return updated, not_found, skipped