import re
from html import unescape
from datetime import datetime, date, timedelta
from .models import Entry, Holidays, Trip, Absence, NotificationPreference
from django.urls import reverse
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


def strip_html_keep_newlines(text):
    """Strip HTML tags but convert block-level/break tags to newlines first."""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|li|tr|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Diferencia en días corridos menos feriados (uso: antigüedad de cotizaciones)
    n_holidays = Holidays.objects.filter(
        workable=False,
        date_from__range=(from_date, to_date)
    ).count()

    return (to_date - from_date).days - n_holidays


_ABSENCE_TYPES_REDUCE_WORK = frozenset({
    'Vacaciones', 'Beneficio Vacaciones', 'Compensatorios',
    'Enfermedad', 'Exámenes/Día de Estudio',
    'Sin goce de sueldo', 'Viernes OFF alta', 'Viernes OFF',
    'FAM/Trabajando fuera ofi',
})


def _holiday_weekday_set(from_date, to_date):
    """Set of weekday dates that are feriados or días no laborables within [from_date, to_date]."""
    qs = Holidays.objects.filter(
        type_holidays__in=['Feriado', 'Día no laborable'],
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    days = set()
    for h in qs:
        d = max(h.date_from, from_date)
        end = min(h.date_to, to_date)
        while d <= end:
            if d.weekday() < 5:
                days.add(d)
            d += timedelta(days=1)
    return days


def _days_overlap(records, from_date, to_date):
    """Sum actual calendar days (inclusive) covered by a queryset of date-range records."""
    total = 0
    for r in records:
        start = max(r.date_from, from_date)
        end = min(r.date_to, to_date)
        if start <= end:
            total += (end - start).days + 1
    return total


def _days_overlap_habil(records, from_date, to_date, holiday_days):
    """Sum hábil days (Mon-Fri, non-holiday) covered by records within [from_date, to_date]."""
    total = 0
    for r in records:
        start = max(r.date_from, from_date)
        end = min(r.date_to, to_date)
        d = start
        while d <= end:
            if d.weekday() < 5 and d not in holiday_days:
                total += 1
            d += timedelta(days=1)
    return total


def count_workable_days(from_date, to_date):
    """Días hábiles: Mon-Fri excluding all feriados and días no laborables (any work_level)."""
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

    holiday_days = _holiday_weekday_set(from_date, to_date)
    total = 0
    current = from_date
    while current <= to_date:
        if current.weekday() < 5 and current not in holiday_days:
            total += 1
        current += timedelta(days=1)
    return total


def get_working_days_worker(from_date, to_date, worker):
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

    holiday_days = _holiday_weekday_set(from_date, to_date)

    working_days = sum(
        1 for i in range((to_date - from_date).days + 1)
        if (from_date + timedelta(i)).weekday() < 5
        and (from_date + timedelta(i)) not in holiday_days
    )

    worked_holiday_records = Absence.objects.filter(
        absence_user=worker,
        type_absence='Feriado trabajado',
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    worked_holiday_days = _days_overlap(worked_holiday_records, from_date, to_date)

    worked_holiday_half_records = Absence.objects.filter(
        absence_user=worker,
        type_absence='Feriado trabajado 1/2',
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    worked_holiday_days += _days_overlap(worked_holiday_half_records, from_date, to_date) * 0.5

    absence_records = Absence.objects.filter(
        absence_user=worker,
        type_absence__in=_ABSENCE_TYPES_REDUCE_WORK,
        date_from__lte=to_date,
        date_to__gte=from_date,
    )
    absence_days = _days_overlap_habil(absence_records, from_date, to_date, holiday_days)

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


def _get_opted_out_user_ids(notification_type):
    """Returns set of user IDs explicitly opted out from a notification type."""
    from .models import NotificationPreference
    return set(
        NotificationPreference.objects.filter(
            notification_type=notification_type, is_active=False
        ).values_list('user_id', flat=True)
    )


def get_explicit_subscriber_emails(notification_type):
    """Returns list of emails for explicitly subscribed (is_active=True) users."""
    from .models import NotificationPreference
    return list(
        NotificationPreference.objects
        .filter(notification_type=notification_type, is_active=True)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
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

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
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
    opted_out = _get_opted_out_user_ids('margin_warning')
    sales_users = IntranetUser.objects.filter(userType="Ventas").exclude(email="").exclude(id__in=opted_out)

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

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    manager_name = "Vic"

    subject = "⚠️ Aliwen Intranet – Advertencias de Rentabilidad (Aliwen)"
    to_emails = get_explicit_subscriber_emails('margin_manager') or ["va@aliwenincoming.com.ar"]
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

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    pref, _ = NotificationPreference.objects.get_or_create(
        user=client,
        notification_type='tariff_client',
        defaults={'is_active': True},
    )
    unsubscribe_url = site_url + reverse('notification_unsubscribe', kwargs={'token': pref.unsubscribe_token})

    if date_from:
        day   = date_from.day
        suffix = "th" if 11 <= day <= 13 else {1:"st",2:"nd",3:"rd"}.get(day % 10, "th")
        since_date = date_from.strftime(f"%A, {day}{suffix} of %B %Y")
    else:
        since_date = None

    subject = f"Aliwen Incoming – Rate Update"
    template = "emails/tariff_client_news.html"
    context = {
        "client_name": client.other_name,
        "today": date.today().strftime("%B %d, %Y"),
        "since_date": since_date,
        "locations": locations,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
        "unsubscribe_url": unsubscribe_url,
    }

    return subject, to_emails, template, context


def send_tariff_client_weekly(stdout=None):
    """Send the weekly rate-update email to all opted-in clients. Called every Monday."""
    from datetime import timedelta
    today      = date.today()
    date_from  = today - timedelta(days=7)

    clients = (
        User.objects.filter(isActivated=True, userType='Cliente')
        .exclude(email='')
    )

    sent = skipped = errors = 0
    for client in clients:
        pref = NotificationPreference.objects.filter(
            user=client, notification_type='tariff_client'
        ).first()
        # Default is opted-in; only skip if explicitly deactivated
        if pref and not pref.is_active:
            skipped += 1
            continue
        try:
            subject, to_emails, template, context = build_tariff_client_news_context(
                client, date_from=date_from
            )
            if not context.get('locations'):
                skipped += 1
                continue
            send_templated_email(subject, [to_emails] if isinstance(to_emails, str) else to_emails, template, context)
            sent += 1
        except Exception as exc:
            errors += 1
            if stdout:
                stdout.write(f"  Error enviando a {client.username}: {exc}")

    return {'sent': sent, 'skipped': skipped, 'errors': errors}


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

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
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
    ISNULL(DRM.NAME, '')  AS agent_name,
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
        ELSE ISNULL(BSD.PAX, 0)
    END AS num_pax,
    CASE BHD.STATUS
        WHEN 'HL' THEN 0
        ELSE (ISNULL(BSD.AGENT, 0) - ISNULL(BSD.COST, 0)) / CASE ISNULL(BSD.AGENT, 0) WHEN 0 THEN 1 ELSE ISNULL(BSD.AGENT, 0) END
    END AS rent_perc,
    CASE BHD.STATUS WHEN 'HL' THEN 0 ELSE ISNULL(BSD.AGENT, 0) END AS amount,
    ISNULL((
        SELECT STUFF((
            SELECT ' | ' + RTRIM(LTRIM(CAST(N2.MESSAGE_TEXT AS NVARCHAR(MAX))))
            FROM NTS N2
            WHERE N2.BHD_ID = BHD.BHD_ID AND N2.CATEGORY = 'REN'
            FOR XML PATH (''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 3, '')
    ), '') AS tp_notes,
    BHD.SALE4 AS cotizado_code,
    ISNULL((
        SELECT STUFF((
            SELECT ' | ' + RTRIM(LTRIM(CAST(N3.MESSAGE_TEXT AS NVARCHAR(MAX))))
            FROM NTS N3
            WHERE N3.BHD_ID = BHD.BHD_ID AND N3.CATEGORY = 'PNR'
            FOR XML PATH (''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 3, '')
    ), '') AS pnr_notes,
    CASE BHD.STATUS WHEN 'HL' THEN 0 ELSE
        CASE BHD.CURRENCY WHEN 'ARS' THEN
            CASE ISNULL((SELECT CRT_RATE FROM CRT
                WHERE CUR_CODE_TO = 'USD'
                  AND CRT_DATE    = CONVERT(date, BHD.UDTEXT5)
                  AND CUR_CODE_FM = BHD.CURRENCY
                  AND CSC_CODE    = BHD.CURR_SC), 0)
            WHEN 0 THEN 0
            ELSE ROUND(ISNULL((
                SELECT SUM(CASE
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='VAL') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='TAX') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='COM') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='TOC') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='VAL') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='TAX') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='COM') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='TOC') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                END)
                FROM TRL JOIN TRH ON TRH.TRH_ID = TRL.TRH_ID
                    AND TRH.LEDGER = 'R'
                    AND (TRH.TRAN_TYPE = 1 OR TRH.TRAN_TYPE = 2)
                WHERE TRL.TRANSACTION_ITEM = BHD.FULL_REFERENCE), 0), 2)
            / ISNULL((SELECT CRT_RATE FROM CRT
                WHERE CUR_CODE_TO = 'USD'
                  AND CRT_DATE    = CONVERT(date, BHD.UDTEXT5)
                  AND CUR_CODE_FM = BHD.CURRENCY
                  AND CSC_CODE    = BHD.CURR_SC), 0)
            END
        ELSE
            ROUND(ISNULL((
                SELECT SUM(CASE
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='VAL') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='TAX') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='COM') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=1 AND TRL.LINE_CATEGORY='TOC') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='VAL') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='TAX') THEN -(TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='COM') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                    WHEN (TRH.TRAN_TYPE=2 AND TRL.LINE_CATEGORY='TOC') THEN  (TRL.TRANSACTION_VALUE + TRL.BASE_INCREMENT_VALUE)
                END)
                FROM TRL JOIN TRH ON TRH.TRH_ID = TRL.TRH_ID
                    AND TRH.LEDGER = 'R'
                    AND (TRH.TRAN_TYPE = 1 OR TRH.TRAN_TYPE = 2)
                WHERE TRL.TRANSACTION_ITEM = BHD.FULL_REFERENCE), 0), 2)
        END
    END AS invoiced
FROM BHD
LEFT JOIN DRM ON DRM.CODE = BHD.AGENT
LEFT JOIN BSD ON BSD.BHD_ID = BHD.BHD_ID AND BSD.BSL_ID = 0
WHERE BHD.BRANCH = 'AL'
  AND BHD.TRAVELDATE >= %s
  AND BHD.TRAVELDATE <= %s
"""

_BOOKING_STATUSES  = {"OK", "FI", "CT", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
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
                        amount_raw = str(round(float(am)))
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
            trip.consultant_tp = users_by_other_tp[responsable_code]
        elif responsable_code:
            try:
                trip.consultant_tp = User.objects.get(username=responsable_code)
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
                trip.amount = round(float(am))
            except (ValueError, TypeError):
                pass

        trips_to_update.append(trip)

    if trips_to_update:
        Trip.objects.bulk_update(trips_to_update, [
            "travelling_date", "out_date", "dh_type",
            "consultant_tp", "operations_user", "dh",
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


def copy_consultant_to_responsable(date_from, date_to):
    """
    For trips whose travelling_date falls within [date_from, date_to],
    copy consultant_tp → responsable_user where consultant_tp is set.

    Useful for backfilling historical records where both fields should match.

    Usage from Django shell:
        from intranet.utils import copy_consultant_to_responsable
        from datetime import date
        updated, skipped = copy_consultant_to_responsable(date(2024, 1, 1), date(2026, 6, 30))
        print(f"Updated: {updated} | Skipped (no consultant_tp): {skipped}")
    """
    trips_qs = Trip.objects.filter(
        travelling_date__gte=date_from,
        travelling_date__lte=date_to,
        consultant_tp__isnull=False,
    ).select_related("consultant_tp")

    to_update = []
    skipped = 0
    for trip in trips_qs:
        if trip.consultant_tp_id:
            trip.responsable_user_id = trip.consultant_tp_id
            to_update.append(trip)
        else:
            skipped += 1

    if to_update:
        Trip.objects.bulk_update(to_update, ["responsable_user"])

    print(f"Updated: {len(to_update)} | Skipped (no consultant_tp): {skipped}")
    return len(to_update), skipped


def clear_responsable_from_date(cutoff_date, dry_run=True):
    """
    Clears responsable_user (sets to None) for all trips whose travelling_date
    is >= cutoff_date, so they can be reassigned later.

    Trips with travelling_date < cutoff_date are left untouched.

    Usage from Django shell (dry run first):
        from intranet.utils import clear_responsable_from_date
        from datetime import date
        count, trips = clear_responsable_from_date(date(2026, 7, 1), dry_run=True)
        # Review the list, then execute:
        count, trips = clear_responsable_from_date(date(2026, 7, 1), dry_run=False)
        print(f"Cleared: {count}")
    """
    trips_qs = Trip.objects.filter(
        travelling_date__gte=cutoff_date,
        responsable_user__isnull=False,
    ).select_related("responsable_user").order_by("travelling_date")

    preview = [
        {
            "id": t.id,
            "name": t.name,
            "travelling_date": t.travelling_date.strftime("%d/%m/%Y"),
            "responsable_user": t.responsable_user.username if t.responsable_user else "",
        }
        for t in trips_qs
    ]

    if dry_run:
        print(f"DRY RUN — would clear responsable_user on {len(preview)} trips (travelling_date >= {cutoff_date})")
        for p in preview:
            print(f"  [{p['travelling_date']}] {p['name']} (id={p['id']}) — was: {p['responsable_user']}")
        return len(preview), preview

    for t in trips_qs:
        t.responsable_user = None
    Trip.objects.bulk_update(list(trips_qs), ["responsable_user"])

    print(f"Cleared responsable_user on {len(preview)} trips (travelling_date >= {cutoff_date})")
    return len(preview), preview


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

def booking_sheet_season_year():
    """Returns the start year of the current season (May–April)."""
    today = date.today()
    return today.year if today.month >= 5 else today.year - 1


def get_booking_sheet_data(date_from_str, date_to_str):
    """
    Returns all confirmed Tourplan bookings (status in _BOOKING_STATUSES),
    excluding Personal Trip (ALPP) and Sites (ALSI) prefixes,
    filtered to the given date range (YYYYMMDD strings).
    Each dict includes in_intranet (bool) and intranet_trip_id (int or None).
    """
    conn = get_tourplan_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_TOURPLAN_SYNC_QUERY, (date_from_str, date_to_str))
        rows = cursor.fetchall()
    finally:
        conn.close()

    def _s(row, key):
        v = row.get(key)
        return str(v).strip() if v is not None else ""

    _intranet_trips = list(
        Trip.objects.select_related("responsable_user", "vr_requested_by")
        .exclude(tourplanId="").exclude(tourplanId__isnull=True)
    )
    trips_by_tp = {t.tourplanId: t.id for t in _intranet_trips}
    _difficulty_by_tp = {t.tourplanId: (t.difficulty or "") for t in _intranet_trips}
    _vr_by_tp = {}
    _vr_requested_by_tp = {}
    for _t in _intranet_trips:
        if _t.responsable_user:
            _vr_by_tp[_t.tourplanId] = {
                "id": _t.responsable_user.id,
                "username": _t.responsable_user.username,
                "color": str(_t.responsable_user.color) if _t.responsable_user.color else "#6c757d",
            }
        else:
            _vr_by_tp[_t.tourplanId] = None
        if _t.vr_requested_by:
            _vr_requested_by_tp[_t.tourplanId] = {
                "id": _t.vr_requested_by.id,
                "username": _t.vr_requested_by.username,
            }
        else:
            _vr_requested_by_tp[_t.tourplanId] = None

    _all_users = list(User.objects.all())
    users_by_other_tp_bs = {
        u.other_tp.strip(): u
        for u in _all_users
        if u.other_tp and u.other_tp.strip()
    }
    users_by_username_bs = {
        u.username.strip(): u
        for u in _all_users
        if u.username and u.username.strip()
    }

    def _fmt_amount(val):
        if val is None:
            return ""
        try:
            return str(round(float(val)))
        except (ValueError, TypeError):
            return ""

    def _user_pill(code):
        if not code:
            return None
        code = code.strip()
        u = users_by_other_tp_bs.get(code) or users_by_username_bs.get(code)
        if not u:
            return None
        return {"name": u.other_name or u.username, "color": str(u.color) if u.color else "#6c757d"}


    _bs_prefix_re = re.compile(r'^AL([A-Z]+)', re.IGNORECASE)

    result = []
    for row in rows:
        tp_id = _s(row, "tourplan_id")
        if not tp_id:
            continue
        raw_status = _s(row, "status")
        if not raw_status:
            continue

        m = _bs_prefix_re.match(tp_id)
        tp_prefix = m.group(1).upper() if m else tp_id[:4].upper()

        td = row.get("travelling_date")
        od = row.get("out_date")

        rent_perc_raw = row.get("rent_perc")
        rent_perc_display = ""
        rent_perc_for_create = ""
        if rent_perc_raw is not None:
            try:
                pct = round(float(rent_perc_raw) * 100, 2)
                rent_perc_display = f"{pct}%"
                rent_perc_for_create = rent_perc_display
            except (ValueError, TypeError):
                pass

        amount_raw = row.get("amount")
        amount_display = ""
        if amount_raw:
            try:
                amount_display = str(round(float(amount_raw)))
            except (ValueError, TypeError):
                pass

        dh_name = _s(row, "dh_name")
        if dh_name.upper().startswith("DH "):
            dh_name = dh_name[3:].strip()

        num_pax = 2
        try:
            num_pax = int(row.get("num_pax") or 2)
        except (ValueError, TypeError):
            pass

        trip_id = trips_by_tp.get(tp_id)
        result.append({
            "tp_id":              tp_id,
            "name":               _s(row, "pax_name"),
            "client_name":        _s(row, "agent_name"),
            "client_reference":   _s(row, "client_reference"),
            "travelling_date":    td.strftime("%d/%m/%Y") if td else "",
            "travelling_date_sort": td.strftime("%Y%m%d") if td else "00000000",
            "travelling_date_month": td.strftime("%Y-%m") if td else "",
            "out_date":           od.strftime("%d/%m/%Y") if od else "",
            "raw_status":         raw_status,
            "num_pax":            num_pax,
            "amount":             amount_display,
            "rent_perc":          rent_perc_display,
            "responsable_code":   _s(row, "responsable_code"),
            "responsable_user":   _user_pill(_s(row, "responsable_code")),
            "operations_code":    _s(row, "operations_code"),
            "operations_user":    _user_pill(_s(row, "operations_code")),
            "dh_type":            _s(row, "dh_type"),
            "dh_name":            dh_name,
            "guide":              _s(row, "guide"),
            "tp_prefix":          tp_prefix,
            "tp_notes":           strip_html_keep_newlines(_s(row, "tp_notes")),
            "pnr_notes":          strip_html_keep_newlines(_s(row, "pnr_notes")),
            "cotizado_code":      _s(row, "cotizado_code"),
            "cotizado_user":      _user_pill(_s(row, "cotizado_code")),
            "invoiced":           _fmt_amount(row.get("invoiced")),
            "in_intranet":        trip_id is not None,
            "intranet_trip_id":   trip_id,
            "intranet_vr":        _vr_by_tp.get(tp_id) if trip_id else None,
            "vr_requested_by":    _vr_requested_by_tp.get(tp_id) if trip_id else None,
            "difficulty":         _difficulty_by_tp.get(tp_id, "") if trip_id else "",
            # Fields needed for single-trip creation
            "contact_name":       "",
            "vendedor_tp":        _s(row, "responsable_code"),
            "operations_tp":      _s(row, "operations_code"),
            "quantity_pax":       num_pax,
            "rent_perc_raw":      rent_perc_for_create,
            "amount_raw":         amount_display,
        })

    result.sort(key=lambda r: r["travelling_date_sort"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Weekly roster email para todos
# ---------------------------------------------------------------------------

DIAS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
}

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

def _format_date_es(d):
    """Devuelve 'Lunes 19 de mayo' en español."""
    return f"{DIAS_ES[d.weekday()]} {d.day} de {MESES_ES[d.month]}"

def _date_range(date_from, date_to):
    """Genera todos los días entre date_from y date_to inclusive."""
    current = date_from
    while current <= date_to:
        yield current
        current += timedelta(days=1)

def _get_week_data(monday, friday):
    """
    Reúne toda la información de una semana laboral (lunes a viernes).
    Devuelve un dict con:
      - label: string "Lunes DD de mes – Viernes DD de mes"
      - holidays: lista de dicts con info de feriados que caen en la semana
      - absences: lista de dicts {user_display, type, date_from, date_to}
      - birthdays: lista de dicts {user_display, date}
    """
    from .models import Holidays, Absence, User as IntranetUser

    # ── Feriados que se cruzan con la semana ─────────────────────────────
    holidays_qs = Holidays.objects.filter(
        date_from__lte=friday,
        date_to__gte=monday,
        type_holidays="Feriado",
    )

    holidays_data = []
    for h in holidays_qs:
        # Días del feriado que caen dentro de la semana
        h_start = max(h.date_from, monday)
        h_end = min(h.date_to, friday)
        days_in_week = [
            _format_date_es(d) for d in _date_range(h_start, h_end)
        ]
        # Usuarios que trabajan ese feriado (Feriado trabajado en Absence)
        workers_qs = Absence.objects.filter(
            type_absence__in=["Feriado trabajado", "Feriado trabajado 1/2"],
            date_from__lte=h_end,
            date_to__gte=h_start,
            absence_user__isActivated=True,
        ).select_related("absence_user")
        workers = [
            {
                "name": a.absence_user.other_name or a.absence_user.username,
                "half": a.type_absence == "Feriado trabajado 1/2",
            }
            for a in workers_qs
        ]
        holidays_data.append({
            "name": h.name or h.get_type_holidays_display(),
            "days": days_in_week,
            "workers": workers,
        })

    # ── Ausencias de la semana (excluir Feriado trabajado, cumpleaños y home) ──
    EXCLUDE_ABSENCE = {
        "Feriado trabajado", "Feriado trabajado 1/2",
        "Cumpleaños",
        "Semana home", "FAM/Trabajando fuera ofi",
    }
    absences_qs = Absence.objects.filter(
        date_from__lte=friday,
        date_to__gte=monday,
        absence_user__isActivated=True,
    ).exclude(
        type_absence__in=EXCLUDE_ABSENCE
    ).select_related("absence_user").order_by("absence_user__other_name", "date_from")

    absences_data = []
    for a in absences_qs:
        disp_from = max(a.date_from, monday)
        disp_to = min(a.date_to, friday)
        absences_data.append({
            "name": a.absence_user.other_name or a.absence_user.username,
            "type": a.type_absence,
            "date_from": _format_date_es(disp_from),
            "date_to": _format_date_es(disp_to),
            "single_day": disp_from == disp_to,
        })

    # ── Home / FAM de la semana ──────────────────────────────────────────
    home_qs = Absence.objects.filter(
        type_absence__in=["Semana home", "FAM/Trabajando fuera ofi"],
        date_from__lte=friday,
        date_to__gte=monday,
        absence_user__isActivated=True,
    ).select_related("absence_user").order_by("absence_user__other_name")

    home_data = []
    for a in home_qs:
        disp_from = max(a.date_from, monday)
        disp_to = min(a.date_to, friday)
        home_data.append({
            "name": a.absence_user.other_name or a.absence_user.username,
            "type": a.type_absence,
            "date_from": _format_date_es(disp_from),
            "date_to": _format_date_es(disp_to),
            "single_day": disp_from == disp_to,
        })

    # ── Cumpleaños de la semana ──────────────────────────────────────────
    # Comparamos solo mes y día (el año del cumpleaños no importa)
    all_users = IntranetUser.objects.filter(isActivated=True).exclude(userType="Cliente")
    birthdays_data = []
    for day in _date_range(monday, friday):
        # Buscar en Absence con type "Cumpleaños" que caiga en ese día
        bday_absences = Absence.objects.filter(
            type_absence="Cumpleaños",
            date_from__lte=day,
            date_to__gte=day,
            absence_user__isActivated=True,
        ).select_related("absence_user")
        for b in bday_absences:
            birthdays_data.append({
                "name": b.absence_user.other_name or b.absence_user.username,
                "date": _format_date_es(day),
            })

    label = f"{_format_date_es(monday)} – {_format_date_es(friday)}"

    return {
        "label": label,
        "holidays": holidays_data,
        "absences": absences_data,
        "birthdays": birthdays_data,
        "home": home_data,
    }


def _week_has_content(week):
    return bool(week["holidays"] or week["absences"] or week["birthdays"] or week["home"])


def build_weekly_roster_context():
    """
    Construye el contexto para el email semanal de roster.
    Destinatarios: todos los usuarios Ventas, Operaciones y Manager con email.
    Devuelve None si no hay ningún contenido en ninguna de las dos semanas.

    Returns (subject, to_emails, template, context) tuple, or None.
    """
    from .models import User as IntranetUser

    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    this_friday = this_monday + timedelta(days=4)
    next_monday = this_monday + timedelta(weeks=1)
    next_friday = next_monday + timedelta(days=4)

    this_week = _get_week_data(this_monday, this_friday)
    next_week = _get_week_data(next_monday, next_friday)

    if not _week_has_content(this_week) and not _week_has_content(next_week):
        return None

    # Destinatarios: Ventas + Operaciones + Manager de Aliwen con email
    opted_out = _get_opted_out_user_ids('weekly_roster')
    to_emails = list(
        IntranetUser.objects
        .filter(userType__in=["Ventas", "Operaciones", "Manager"], isActivated=True, department="AI")
        .exclude(email="")
        .exclude(id__in=opted_out)
        .values_list("email", flat=True)
    )
    if not to_emails:
        to_emails = [settings.DEFAULT_FROM_EMAIL]

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    subject = f"📅 Roster semanal: {this_week['label']}"
    template = "emails/weekly_roster.html"

    context = {
        "recipient_name": "equipo",
        "today": _format_date_es(today),
        "this_week": this_week,
        "next_week": next_week,
        "logo_url": logo_url,
        "icons_base_url": icons_base_url,
        "site_url": site_url,
    }

    return subject, to_emails, template, context


def send_weekly_roster():
    """
    Envía el email de roster semanal a todos los usuarios Ventas, Operaciones y Manager.
    No envía si no hay contenido para ninguna de las dos semanas.
    Llamar desde el scheduler todos los lunes.

    Usage desde Django shell:
        from intranet.utils import send_weekly_roster
        send_weekly_roster()
    """
    result = build_weekly_roster_context()
    if result is None:
        print("Weekly roster: sin contenido, email no enviado.")
        return
    subject, to_emails, template, context = result
    send_templated_email(subject, to_emails, template, context)
    print(f"Weekly roster sent to {to_emails}")


# ── English date helpers ─────────────────────────────────────────────────────

_EN_WEEKDAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                4: "Friday", 5: "Saturday", 6: "Sunday"}


def _ordinal_en(n):
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    sfx = {1: 'st', 2: 'nd', 3: 'rd'}
    return f"{n}{sfx.get(n % 10, 'th')}"


def _date_en(d):
    return f"{_EN_WEEKDAYS[d.weekday()]} {_ordinal_en(d.day)}"


def _holiday_range_en(h):
    if h.date_from == h.date_to:
        return _date_en(h.date_from)
    return f"from {_date_en(h.date_from)} to {_date_en(h.date_to)}"


# ── Consecutive holiday group detection ──────────────────────────────────────

def _find_consecutive_holiday_group(today):
    """
    If a Feriado/Día no laborable starts exactly 7 days from today, return the list of
    all consecutive holiday objects in that group (no hábil working days between them).
    Returns [] otherwise.
    """
    target = today + timedelta(days=7)

    first = (
        Holidays.objects
        .filter(type_holidays__in=["Feriado", "Día no laborable"], date_from=target)
        .order_by("date_from", "id")
        .first()
    )
    if not first:
        return []

    group = [first]
    current_end = first.date_to

    future = list(
        Holidays.objects
        .filter(
            type_holidays__in=["Feriado", "Día no laborable"],
            date_from__gt=current_end,
            date_from__lte=target + timedelta(days=30),
        )
        .order_by("date_from", "id")
    )

    # Pre-build set of all holiday dates for O(1) gap checks
    holiday_date_set = set()
    for h in group + future:
        d = h.date_from
        while d <= h.date_to:
            holiday_date_set.add(d)
            d += timedelta(days=1)

    for next_h in future:
        d = current_end + timedelta(days=1)
        has_gap = False
        while d < next_h.date_from:
            if d.weekday() < 5 and d not in holiday_date_set:
                has_gap = True
                break
            d += timedelta(days=1)
        if has_gap:
            break
        group.append(next_h)
        current_end = next_h.date_to

    return group


def _get_holiday_workers(group):
    group_from = min(h.date_from for h in group)
    group_to   = max(h.date_to   for h in group)
    qs = (
        Absence.objects
        .filter(
            type_absence__in=["Feriado trabajado", "Feriado trabajado 1/2"],
            date_from__lte=group_to,
            date_to__gte=group_from,
        )
        .select_related("absence_user")
        .order_by("absence_user__other_name")
    )
    seen, result = set(), []
    for a in qs:
        uid = a.absence_user_id
        if uid not in seen:
            seen.add(uid)
            result.append({
                "name": a.absence_user.other_name or a.absence_user.username,
                "half": a.type_absence == "Feriado trabajado 1/2",
            })
    return result


def _build_ooo_text(group, workers, office_closed=False):
    dates_en = [_holiday_range_en(h) for h in group]
    if len(dates_en) == 1:
        dates_phrase, verb = dates_en[0], "is"
    elif len(dates_en) == 2:
        dates_phrase, verb = f"{dates_en[0]} and {dates_en[1]}", "are"
    else:
        dates_phrase = ", ".join(dates_en[:-1]) + f" and {dates_en[-1]}"
        verb = "are"

    if office_closed:
        para1 = (
            f"Kindly note that next {dates_phrase} {verb} national "
            "holidays in Argentina and our office will be closed. "
            "We will reply to your emails on the next working day."
        )
        paragraphs = [
            "Dear friends & colleagues,",
            "",
            para1,
            "",
            "As usual you can contact quote@aliwenincoming.com.ar for any questions or new requests. "
            "Your mail will not be automatically forwarded.",
            "",
            "Please take into account that most of our suppliers will not be working, "
            "so there might be delays with confirmations and special requests.",
            "",
            "For any emergencies do not hesitate to contact us at our emergency telephone: + 54 911 6991 7018.",
            "",
            "Regards,",
        ]
        return "\n".join(paragraphs)

    para1 = (
        f"Kindly note that next {dates_phrase} {verb} national "
        "holidays in Argentina so I will have no access to my e-mails."
    )
    if workers:
        names = [w["name"] for w in workers]
        if len(names) == 1:
            workers_note = f"Please note that {names[0]} will be available to assist with urgent requests during this time."
        elif len(names) == 2:
            workers_note = f"Please note that {names[0]} and {names[1]} will be available to assist with urgent requests during this time."
        else:
            workers_note = f"Please note that {', '.join(names[:-1])} and {names[-1]} will be available to assist with urgent requests during this time."
    else:
        workers_note = None

    paragraphs = [
        "Dear friends & colleagues,",
        "",
        para1,
    ]
    if workers_note:
        paragraphs.append(workers_note)
    paragraphs += [
        "",
        "As usual you can contact quote@aliwenincoming.com.ar for any questions or new requests. "
        "Your mail will not be automatically forwarded.",
        "",
        "Please take into account that most of our suppliers will not be working, "
        "so there might be delays with confirmations and special requests.",
        "",
        "For any emergencies do not hesitate to contact us at our emergency telephone: + 54 911 6991 7018.",
        "",
        "For important information in regards to pax in situ these days, on top of calling "
        "you may send the information to duty@aliwenincoming.com.ar",
        "",
        "Regards,",
    ]
    return "\n".join(paragraphs)


# ── Holiday reminder email ────────────────────────────────────────────────────

def build_holiday_reminder_context(today=None):
    """
    Returns (subject, to_emails, template, context) if a holiday starts in exactly 7 days,
    None otherwise.
    """
    from .models import User as IntranetUser

    if today is None:
        today = date.today()

    group = _find_consecutive_holiday_group(today)
    if not group:
        return None

    workers = _get_holiday_workers(group)
    office_closed = all(h.type_holidays == "Día no laborable" for h in group) and not workers

    holidays_info = []
    for h in group:
        single = h.date_from == h.date_to
        holidays_info.append({
            "name":          h.name or h.get_type_holidays_display(),
            "date_from_ddmm": h.date_from.strftime("%d/%m"),
            "date_to_ddmm":   h.date_to.strftime("%d/%m"),
            "date_range_es":  (
                _format_date_es(h.date_from) if single
                else f"{_format_date_es(h.date_from)} al {_format_date_es(h.date_to)}"
            ),
            "date_range_en": _holiday_range_en(h),
            "single_day":    single,
        })

    # Signature line
    dates_en = [_holiday_range_en(h) for h in group]
    if office_closed:
        if len(dates_en) == 1:
            sig = f"Please bear in mind that our office will be closed on {dates_en[0]} (Argentine national holiday). We will reply to your emails on the next working day."
        else:
            sig = f"Please bear in mind that our office will be closed from {dates_en[0]} to {dates_en[-1]} (Argentine national holidays). We will reply to your emails on the next working day."
    elif len(dates_en) == 1:
        sig = f"Please bear in mind that {dates_en[0]} is a national holiday in Argentina."
    elif len(dates_en) == 2:
        sig = f"Please bear in mind that {dates_en[0]} and {dates_en[1]} are national holidays in Argentina."
    else:
        sig = f"Please bear in mind that {', '.join(dates_en[:-1])} and {dates_en[-1]} are national holidays in Argentina."

    # Subject
    if len(group) == 1:
        h0 = group[0]
        d_str = h0.date_from.strftime("%d/%m") if h0.date_from == h0.date_to else f"{h0.date_from.strftime('%d/%m')}-{h0.date_to.strftime('%d/%m')}"
        subject = f"🇦🇷 ¡Se acerca un feriado! - {d_str}: {h0.name or h0.get_type_holidays_display()}"
    else:
        d_parts = [
            h.date_from.strftime("%d/%m") if h.date_from == h.date_to
            else f"{h.date_from.strftime('%d/%m')}-{h.date_to.strftime('%d/%m')}"
            for h in group
        ]
        names_part = " + ".join(h.name or h.get_type_holidays_display() for h in group)
        subject = f"🇦🇷 ¡Se acercan feriados! - {' y '.join(d_parts)}: {names_part}"

    opted_out = _get_opted_out_user_ids('holiday_reminder')
    to_emails = list(
        IntranetUser.objects
        .filter(userType__in=["Ventas", "Operaciones", "Manager"], isActivated=True, department="AI")
        .exclude(email="")
        .exclude(id__in=opted_out)
        .values_list("email", flat=True)
    )
    if not to_emails:
        to_emails = [settings.DEFAULT_FROM_EMAIL]

    _site_url = getattr(settings, "SITE_URL", "https://intranet.aliwenincoming.com")
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip("/")
    static_url = settings.STATIC_URL.strip("/")
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    return subject, to_emails, "emails/holiday_reminder.html", {
        "logo_url":       logo_url,
        "icons_base_url": icons_base_url,
        "site_url":       site_url,
        "today":          today.strftime("%d/%m/%Y"),
        "holidays":       holidays_info,
        "workers":        workers,
        "office_closed":  office_closed,
        "signature_line": sig,
        "ooo_text":       _build_ooo_text(group, workers, office_closed=office_closed),
    }


def send_holiday_reminder(today=None):
    """
    Send the holiday reminder email if a holiday starts in exactly 7 days.
    Call daily from daily_tasks.

    Usage:
        from intranet.utils import send_holiday_reminder
        send_holiday_reminder()
    """
    result = build_holiday_reminder_context(today)
    if result is None:
        print("Holiday reminder: no holiday starting in 7 days, email not sent.")
        return
    subject, to_emails, template, context = result
    send_templated_email(subject, to_emails, template, context)
    print(f"Holiday reminder sent to {to_emails}")


def send_quality_closure_notification(entry, feedbacks):
    """Send closure summary email to quality_closure notification subscribers."""
    from intranet.models import NotificationPreference
    from django.utils import timezone as _tz

    recipients = list(
        NotificationPreference.objects
        .filter(notification_type='quality_closure', is_active=True)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )
    if not recipients:
        return

    _site_url = getattr(settings, 'SITE_URL', 'https://intranet.aliwenincoming.com')
    if isinstance(_site_url, (list, tuple)):
        _site_url = _site_url[0]
    site_url = _site_url.rstrip('/')
    static_url = settings.STATIC_URL.strip('/')
    icons_base_url = f"{site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    trip = entry.trip
    feedback_rows = []
    for fb in feedbacks:
        feedback_rows.append({
            'objective': fb.target_display(),
            'brief_summary': fb.brief_summary or '',
            'solution': fb.solution or '',
            'cost': fb.cost or 0,
        })

    closed_date = ''
    if entry.closing_date:
        closed_date = entry.closing_date.strftime('%d/%m/%Y')

    entry_url = f"{site_url}/calidad"

    context = {
        'entry': entry,
        'trip': trip,
        'feedbacks': feedback_rows,
        'closed_date': closed_date,
        'entry_url': entry_url,
        'logo_url': logo_url,
        'icons_base_url': icons_base_url,
    }

    subject = f"[Calidad] Gestión cerrada — {trip.name} [ref:QE-{entry.id}]"

    html_content = render_to_string('emails/quality_closure_notification.html', context)

    extra_headers = {}
    quality_inbox = getattr(settings, 'QUALITY_INBOX_EMAIL', None)
    if quality_inbox:
        extra_headers['Reply-To'] = quality_inbox

    msg = EmailMultiAlternatives(
        subject=subject,
        body='Este email requiere HTML.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        headers=extra_headers,
    )
    msg.attach_alternative(html_content, 'text/html')
    msg.send()


def send_quality_followup(entry, feedbacks):
    """Send a plain-text follow-up email to the responsable of a quality entry."""
    import logging as _log
    from django.utils import timezone as _tz
    from tariff.quality_ai import generate_quality_followup_text

    responsable = entry.user_working
    if not responsable or not getattr(responsable, 'email', None):
        return

    days_elapsed = (_tz.now() - entry.starting_date).days

    try:
        ai_body = generate_quality_followup_text(entry, feedbacks, days_elapsed)
    except Exception as exc:
        _log.getLogger(__name__).warning("generate_quality_followup_text raised: %s", exc)
        fb_list = '; '.join(fb.brief_summary or fb.target_display() for fb in feedbacks)
        ai_body = (
            f"Te escribimos para hacer seguimiento del case de calidad correspondiente al viaje "
            f"{entry.trip.name}, que lleva {days_elapsed} días abierto.\n\n"
            f"Feedbacks pendientes: {fb_list}\n\n"
            f"Por favor informanos el estado de la gestión, cómo se resolvió cada punto "
            f"y si hubo algún costo asociado."
        )

    full_name = (responsable.other_name or responsable.username or '').strip()
    first_name = full_name.split()[0] if full_name else responsable.username

    subject = f"Re: [Calidad] Queja asignada — {entry.trip.name} [ref:QE-{entry.id}]"

    quality_inbox = getattr(settings, 'QUALITY_INBOX_EMAIL', 'calidad@aliwenincoming.com.ar')

    body = f"Hola {first_name},\n\n{ai_body}\n\n— Aliwen Calidad"

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[responsable.email],
            headers={'Reply-To': quality_inbox},
        )
        msg.send()

        entry.last_followup_sent = _tz.now()
        entry.save(update_fields=['last_followup_sent'])
    except Exception as exc:
        _log.getLogger(__name__).warning("send_quality_followup failed for entry %s: %s", entry.id, exc)


def run_quality_close_check(stdout=None):
    """
    Check INBOX for replies to quality notification emails ([ref:QE-N] in subject).
    For each reply: run AI, close the Entry if info is complete, or auto-reply if not.
    Returns dict with keys: processed, closed, replied, error.
    Extracted from calidad_check_close_replies view so daily_tasks can call it directly.
    """
    import os, re as _re
    from dotenv import load_dotenv
    from imap_tools import MailBox
    from django.core.mail import EmailMultiAlternatives
    from django.utils import timezone as tz
    from tariff.models import Feedback
    from intranet.models import Entry, PROGRESS_OPTIONS
    from tariff.quality_ai import process_quality_close_reply, generate_incomplete_reply_text

    load_dotenv(override=True)
    username = os.environ.get('MAIL_USERNAME')
    password = os.environ.get('MAIL_PASSWORD')
    server   = os.environ.get('MAIL_SERVER')

    def _log(msg):
        if stdout:
            stdout.write(msg)

    if not all([username, password, server]):
        return {'error': 'Faltan variables de entorno de correo', 'processed': 0, 'closed': 0, 'replied': 0}

    _QE_PATTERN = _re.compile(r'\[ref:QE-(\d+)\]', _re.IGNORECASE)
    processed = closed = replied = 0
    seen_ids = set()

    def _get_message_id(msg):
        raw = msg.headers.get('message-id') or msg.headers.get('Message-ID') or []
        if isinstance(raw, list) and raw:
            return raw[0].strip()
        return raw.strip() if isinstance(raw, str) else f'uid-{msg.uid}'

    def _close_entry_action(entry, result, feedbacks):
        global_sol  = (result.get('global_solution') or '').strip()
        global_cost = float(result.get('global_cost') or 0)
        per_fb_map  = {item['feedback_id']: item for item in (result.get('per_feedback') or [])}
        for fb in feedbacks:
            sol  = (per_fb_map.get(fb.id, {}).get('solution') or global_sol).strip()
            cost = float(per_fb_map.get(fb.id, {}).get('cost') or global_cost or 0)
            fields = []
            if sol and not fb.solution:  fb.solution = sol;  fields.append('solution')
            if cost and not fb.cost:     fb.cost = cost;     fields.append('cost')
            if fb.status != 'cerrado':   fb.status = 'cerrado'; fields.append('status')
            if fields:
                fb.save(update_fields=fields)
        entry.isClosed     = True
        entry.closing_date = tz.now()
        entry.progress     = PROGRESS_OPTIONS[-1][0]
        entry.save(update_fields=['isClosed', 'closing_date', 'progress'])
        try:
            send_quality_closure_notification(entry, feedbacks)
        except Exception:
            pass

    def _incomplete_reply(sender, orig_subject, orig_msg_id, missing_labels,
                          entry=None, missing_fbs=None, body_excerpt=''):
        reply_subject = f"Re: {orig_subject}" if not orig_subject.startswith('Re:') else orig_subject
        body = None
        if entry and missing_fbs:
            try:
                body = generate_incomplete_reply_text(entry, missing_fbs, body_excerpt)
            except Exception:
                pass
        if not body:
            body = (
                "Gracias por tu respuesta.\n\n"
                "Para poder cerrar el case de calidad nos falta información de solución para los siguientes feedbacks:\n"
                + ', '.join(str(m) for m in missing_labels)
                + "\n\nPor favor respondé a este email indicando cómo se resolvió cada uno y el costo si hubo alguno.\n\n— Aliwen Calidad"
            )
        headers = {}
        if orig_msg_id:
            mid = orig_msg_id if orig_msg_id.startswith('<') else f'<{orig_msg_id}>'
            headers['In-Reply-To'] = mid
            headers['References']  = mid
        EmailMultiAlternatives(
            subject=reply_subject, body=body,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[sender], headers=headers,
        ).send()

    try:
        with MailBox(server).login(username, password, 'INBOX') as mb:
            to_archive = []
            for msg in mb.fetch('SUBJECT "[ref:QE-"', mark_seen=False, bulk=True):
                msg_id       = _get_message_id(msg)
                subject      = msg.subject or ''
                body         = (msg.text or '').strip()
                from_raw     = msg.from_ or ''
                m_addr       = _re.search(r'<([^>]+)>', from_raw)
                sender_email = m_addr.group(1).lower() if m_addr else from_raw.lower().strip()

                m = _QE_PATTERN.search(subject)
                if not m:
                    continue

                if msg_id in seen_ids:
                    to_archive.append(msg.uid)
                    continue
                seen_ids.add(msg_id)

                own = {e.lower() for e in getattr(settings, 'ALIWEN_OWN_EMAILS', set())}
                own.add((settings.DEFAULT_FROM_EMAIL or '').lower())
                if sender_email in own:
                    to_archive.append(msg.uid)
                    continue

                entry_id = int(m.group(1))
                try:
                    entry = Entry.objects.select_related('trip').get(pk=entry_id)
                except Entry.DoesNotExist:
                    to_archive.append(msg.uid)
                    continue

                if entry.isClosed:
                    to_archive.append(msg.uid)
                    continue

                feedbacks = list(
                    Feedback.objects.filter(trip=entry.trip, sentiment='negativo')
                    .select_related('supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity')
                )
                if not feedbacks:
                    to_archive.append(msg.uid)
                    continue

                result = process_quality_close_reply(body, feedbacks)
                processed += 1

                if result is None or not result.get('is_close_request'):
                    to_archive.append(msg.uid)
                    continue

                if result.get('complete'):
                    _close_entry_action(entry, result, feedbacks)
                    closed += 1
                    _log(f"  ✓ Cerrado QE-{entry_id}")
                else:
                    missing = result.get('missing') or []
                    if missing:
                        fb_map = {fb.id: fb for fb in feedbacks}
                        missing_labels = []
                        missing_fbs = []
                        for fb_id in missing:
                            fb = fb_map.get(int(fb_id))
                            if fb:
                                missing_labels.append(fb.target_display())
                                missing_fbs.append(fb)
                        _incomplete_reply(
                            sender_email, subject, msg_id, missing_labels,
                            entry=entry, missing_fbs=missing_fbs, body_excerpt=body[:500],
                        )
                        replied += 1

                to_archive.append(msg.uid)

            if to_archive:
                try:
                    from intranet.management.commands.process_quality_inbox import _gmail_archive
                    _gmail_archive(mb, to_archive)
                except Exception:
                    pass

    except Exception as exc:
        return {'error': str(exc), 'processed': processed, 'closed': closed, 'replied': replied}

    return {'processed': processed, 'closed': closed, 'replied': replied}


def run_quality_followups(stdout=None):
    """
    Send AI-generated follow-up emails to responsables of open quality entries older than 2 days.
    Returns dict with key: sent.
    """
    from django.utils import timezone
    from datetime import timedelta
    from tariff.models import Feedback
    from intranet.models import Entry

    def _log(msg):
        if stdout:
            stdout.write(msg)

    open_entries = Entry.objects.filter(
        status='Queja', isClosed=False
    ).select_related('trip', 'user_working')

    two_days_ago = timezone.now() - timedelta(days=2)
    sent = 0

    for entry in open_entries:
        needs = (
            (entry.last_followup_sent is None and entry.starting_date < two_days_ago)
            or (entry.last_followup_sent is not None and entry.last_followup_sent < two_days_ago)
        )
        if not needs:
            continue
        feedbacks = list(
            Feedback.objects.filter(trip=entry.trip, sentiment='negativo')
            .select_related('supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity')
        )
        if not feedbacks:
            continue
        try:
            send_quality_followup(entry, feedbacks)
            sent += 1
            _log(f"  ↪ Seguimiento enviado a {entry.user_working} — QE-{entry.id}")
        except Exception as exc:
            _log(f"  ! Error en QE-{entry.id}: {exc}")

    return {'sent': sent}


def send_quality_update_notification(entry, trip, responsable, priority, new_feedbacks):
    """
    Send 'new feedbacks added' email to responsable when new negative feedbacks
    arrive for a trip that already has an open quality Entry.
    Reuses the same template as the opening notification but with an 'Actualización' banner.
    """
    from django.utils import timezone
    if not responsable or not getattr(responsable, 'email', None):
        return

    _site_url = getattr(settings, 'SITE_URL', 'https://intranet.aliwenincoming.com')
    static_url = settings.STATIC_URL.strip('/')
    icons_base_url = f"{_site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    full_name = (responsable.other_name or responsable.username or '').strip()
    first_name = full_name.split()[0] if full_name else responsable.username

    import re as _re
    priority_display = _re.sub(r'^\d+ - ', '', priority or '')
    trip_id_str = f' ({trip.tourplanId})' if getattr(trip, 'tourplanId', None) else ''

    feedback_rows = []
    for fb in new_feedbacks:
        feedback_rows.append({
            'objective':     fb.target_display(),
            'brief_summary': fb.brief_summary or '',
            'content':       fb.content or '',
            'verbatim':      fb.verbatim or '',
        })

    context = {
        'entry':            entry,
        'trip':             trip,
        'first_name':       first_name,
        'priority_display': priority_display,
        'feedback_rows':    feedback_rows,
        'supplier_rows':    [],
        'deadline':         timezone.now() + __import__('datetime').timedelta(days=2),
        'entry_url':        f"{_site_url}/calidad",
        'logo_url':         logo_url,
        'icons_base_url':   icons_base_url,
        'is_update':        True,
    }

    subject = f"[Calidad] Actualización de queja — {trip.name}{trip_id_str} [ref:QE-{entry.id}]"
    html_content = render_to_string('emails/quality_entry_notification.html', context)

    extra_headers = {'Reply-To': getattr(settings, 'QUALITY_INBOX_EMAIL', settings.DEFAULT_FROM_EMAIL)}
    msg = EmailMultiAlternatives(
        subject=subject,
        body='Este email requiere HTML.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[responsable.email],
        headers=extra_headers,
    )
    msg.attach_alternative(html_content, 'text/html')
    msg.send()


def send_quality_entry_notification(entry, trip, responsable, priority, negative_feedbacks):
    """Send assignment email to responsable when a Queja Entry is created."""
    from django.utils import timezone

    if not responsable or not getattr(responsable, 'email', None):
        return

    _site_url = getattr(settings, 'SITE_URL', 'https://intranet.aliwenincoming.com')
    static_url = settings.STATIC_URL.strip('/')
    icons_base_url = f"{_site_url}/{static_url}/intranet/images/"
    logo_url = f"{icons_base_url}logo.png"

    full_name = (responsable.other_name or responsable.username or '').strip()
    first_name = full_name.split()[0] if full_name else responsable.username

    priority_display = re.sub(r'^\d+ - ', '', priority) if priority else priority

    feedback_rows = []
    for fb in negative_feedbacks:
        feedback_rows.append({
            'objective': fb.target_display(),
            'sentiment_label': fb.get_sentiment_display(),
            'brief_summary': fb.brief_summary or '',
            'content': fb.content or '',
            'verbatim': fb.verbatim or '',
        })

    supplier_rows = []
    for fb in negative_feedbacks:
        if getattr(fb, 'supplier_id', None) and getattr(fb, 'supplier', None):
            supplier_rows.append({
                'supplier_name': fb.supplier.name,
                'content': fb.content or '',
                'verbatim': fb.verbatim or '',
            })

    deadline = (timezone.now() + timedelta(days=2)).date()
    entry_url = f"{_site_url}/entries"

    trip_id_str = f" · {trip.tourplanId}" if trip.tourplanId else ''
    # Token [ref:QE-{id}] lets us identify this Entry when a reply comes in
    subject = f"[Calidad] Queja asignada — {trip.name}{trip_id_str} [ref:QE-{entry.id}]"

    context = {
        'first_name': first_name,
        'trip': trip,
        'priority': priority,
        'priority_display': priority_display,
        'feedback_rows': feedback_rows,
        'supplier_rows': supplier_rows,
        'deadline': deadline,
        'entry_url': entry_url,
        'logo_url': logo_url,
        'icons_base_url': icons_base_url,
        'today': timezone.now().date(),
    }

    html_content = render_to_string('emails/quality_entry_notification.html', context)

    # Look up the original client email so we can reply on the same thread
    extra_headers = {}
    for fb in negative_feedbacks:
        inbox_items = list(fb.inbox_source.all()[:1])
        if inbox_items:
            orig_mid = inbox_items[0].gmail_message_id or ''
            if orig_mid:
                if not orig_mid.startswith('<'):
                    orig_mid = f'<{orig_mid}>'
                extra_headers['In-Reply-To'] = orig_mid
                extra_headers['References'] = orig_mid
            break

    # Replies from responsable should come back to the quality inbox
    quality_inbox = getattr(settings, 'QUALITY_INBOX_EMAIL', settings.DEFAULT_FROM_EMAIL)
    if quality_inbox:
        extra_headers['Reply-To'] = quality_inbox

    msg = EmailMultiAlternatives(
        subject=subject,
        body='Este email requiere HTML.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[responsable.email],
        headers=extra_headers,
    )
    msg.attach_alternative(html_content, 'text/html')
    msg.send()