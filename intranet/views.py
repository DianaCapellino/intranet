# ── Tourplan DB connection toggle ────────────────────────────────────────────
# Set to False to disable the live lookup when editing entries (entry_tp_lookup).
# The daily sync task (tourplan_db_sync) is NOT affected by this flag.
TOURPLAN_ENABLED = True
# ─────────────────────────────────────────────────────────────────────────────

from django.shortcuts import render
from django.template.loader import render_to_string
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.utils.datastructures import MultiValueDictKeyError
from django.db import IntegrityError
from .models import User, Country, Client, Trip, Entry, Notes, ClientContact, CsvFileTourplanFiles, CsvFormTourplanFiles, Search, Holidays, Absence, Guide, DestinationHost, Driver, DEPARTMENTS, STATUS_OPTIONS, IMPORTANCE_OPTIONS, PROGRESS_OPTIONS, TRIP_TYPES, DH_TYPES, USER_TYPES, DIFFICULTY_OPTIONS, CLIENT_CATEGORIES, MONTHS, TYPE_ABSENCE, NotificationPreference, NOTIFICATION_TYPES, NOTIFICATION_AUTO_TYPES, ExternalCalendarEntry, EXT_CALENDAR_CATEGORIES, RevisionScheduleDay
from tariff.models import Feedback, Supplier, Location, TYPE_QUALITY
from .utils import update_timingStatus, check_duplicate_trips, check_missing_amounts, check_incongruent_entry_dates, check_incongruent_trip_dates
import json
from difflib import SequenceMatcher
from datetime import datetime, date, timedelta
import math
from django.utils.timezone import localtime, now as timezone_now
from imap_tools import MailBox
import os
from dotenv import load_dotenv
import csv
from django.db.models import Count, Avg, Q, FloatField, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.core.paginator import Paginator
from collections import OrderedDict
from django.views.decorators.http import require_GET
from .utils import get_working_days, get_working_days_worker, count_workable_days

_ABSENT_TYPES = frozenset({
    'Vacaciones', 'Beneficio Vacaciones', 'Compensatorios',
    'Enfermedad', 'Exámenes/Día de Estudio',
    'Sin goce de sueldo', 'Viernes OFF alta', 'Viernes OFF',
    'Cumpleaños en baja', 'FAM/Trabajando fuera ofi',
})

def _absences_on_day(target_date, department):
    """Return Absence queryset for staff absent on target_date within a department."""
    return Absence.objects.filter(
        type_absence__in=_ABSENT_TYPES,
        date_from__lte=target_date,
        date_to__gte=target_date,
        absence_user__isActivated=True,
        absence_user__department=department,
        absence_user__userType__in=['Ventas', 'Operaciones', 'Internal', 'Manager'],
    ).select_related('absence_user')

def _next_working_days(from_date, n):
    """Return list of next n working days (Mon–Fri, non-holiday) after from_date."""
    from .utils import _holiday_weekday_set
    # look ahead up to 14 days to find n working days
    look_ahead = from_date + timedelta(days=14)
    holiday_days = _holiday_weekday_set(from_date + timedelta(days=1), look_ahead)
    result = []
    d = from_date + timedelta(days=1)
    while len(result) < n and d <= look_ahead:
        if d.weekday() < 5 and d not in holiday_days:
            result.append(d)
        d += timedelta(days=1)
    return result

def _ordinal(n):
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return {1: f"{n}st", 2: f"{n}nd", 3: f"{n}rd"}.get(n % 10, f"{n}th")

def _get_client_holiday_alert(today):
    """Returns holiday banner context dict for client homepage, or None."""
    _MONTHS = ['January','February','March','April','May','June',
               'July','August','September','October','November','December']

    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        return {'type': 'weekend'}

    today_holiday = Holidays.objects.filter(
        type_holidays__in=['Feriado', 'Día no laborable'],
        date_from__lte=today,
        date_to__gte=today,
    ).first()

    if today_holiday:
        working_users = []
        if today_holiday.work_level in ('half', 'full'):
            working_users = list(
                User.objects.filter(
                    absence_users__type_absence__in=['Feriado trabajado', 'Feriado trabajado 1/2'],
                    absence_users__date_from__lte=today,
                    absence_users__date_to__gte=today,
                    isActivated=True,
                ).order_by('other_name').distinct()
            )
        return {
            'type': 'today_holiday',
            'holiday': today_holiday,
            'working_users': working_users,
        }

    # Check next 1–2 business days for an upcoming Feriado
    biz_passed = 0
    d = today + timedelta(days=1)
    while d <= today + timedelta(days=10):
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue
        upcoming_h = Holidays.objects.filter(
            type_holidays='Feriado',
            date_from__lte=d,
            date_to__gte=d,
        ).first()
        if upcoming_h is not None:
            if biz_passed < 2:
                date_str = f"{d.strftime('%A')} {_ordinal(d.day)} {_MONTHS[d.month - 1]}"
                return {'type': 'upcoming_holiday', 'holiday': upcoming_h, 'date_str': date_str, 'days_ahead': biz_passed + 1}
            break
        biz_passed += 1
        if biz_passed >= 2:
            break
        d += timedelta(days=1)

    return None

from collections import defaultdict


@login_required
def index (request):

    pax_arriving = []
    pax_insitu = []

    today = date.today()

    # Filter the trips according to the rol of the user
    if request.user.userType == "Internal" and request.user.isAdmin:
        trips = Trip.objects.filter(department=request.user.department).filter(status="Booking").order_by('travelling_date')
    elif request.user.userType == "Ventas":
        trips = Trip.objects.filter(status="Booking").filter(responsable_user=request.user).order_by('travelling_date')
    elif request.user.userType == "Operaciones":
        trips = Trip.objects.filter(status="Booking").filter(operations_user=request.user).order_by('travelling_date')
    elif request.user.userType == "Cliente":
        user_client = getattr(request.user, 'client', None)
        if not user_client:
            try:
                user_client = Client.objects.get(name=request.user.other_name)
            except Client.DoesNotExist:
                user_client = None
        if user_client:
            trips = Trip.objects.filter(status="Booking", client=user_client).order_by('travelling_date')
            if user_client.name == "Audley Travel UK":
                client_contact_email = "audley@aliwenincoming.com.ar"
            else:
                client_contact_email = "quote@aliwenincoming.com.ar"
        else:
            trips = Trip.objects.none()
            client_contact_email = "quote@aliwenincoming.com.ar"
    else:
        trips = Trip.objects.filter(status="Booking").filter(responsable_user=request.user).order_by('travelling_date')

    # Quantity of files starting in 1 for arriving
    q_files = 1

    for trip in trips:
        if trip.out_date:

            # Gets the difference between today and arriving dates and add these trips to the list
            if (trip.travelling_date - today).days > -60 and (trip.travelling_date - today).days <= 0 and (trip.out_date - today).days >= 0:
                pax_insitu.append(trip)

        # Gets the next 10 trips arriving
        if q_files < 11:
            if (trip.travelling_date - today).days >=0:
                pax_arriving.append(trip)
                q_files+=1

    data = get_pendings(request.user.department)

    total_quotes = 0
    total_bookings = 0
    total_finals = 0
    total_others = 0

    row_num = 0
    for row in data:
        if row_num != 0:
            col_num = 0
            for i in row:
                if col_num == 1:
                    total_quotes+=row[col_num]
                elif col_num == 2:
                    total_bookings+=row[col_num]
                elif col_num == 3:
                    total_finals+=row[col_num]
                elif col_num == 4:
                    total_others+=row[col_num]
                col_num+=1
        row_num+=1

    today_absences = [
        {
            "name": a.absence_user.other_name or a.absence_user.username,
            "color": a.absence_user.color or '#6c757d',
            "type": a.type_absence,
        }
        for a in _absences_on_day(today, request.user.department)
    ]

    client_holiday_alert = (
        _get_client_holiday_alert(today)
        if request.user.userType == "Cliente" else None
    )

    return render(request, "intranet/index.html", {
        "pax_arriving": pax_arriving,
        "pax_insitu": pax_insitu,
        "client_contact_email": locals().get("client_contact_email", "quote@aliwenincoming.com.ar"),
        "notes": Notes.objects.all(),
        "entries": Entry.objects.all(),
        "pendings": data,
        "total_quotes": total_quotes,
        "total_bookings": total_bookings,
        "total_finals": total_finals,
        "total_others": total_others,
        "today_absences": today_absences,
        "client_holiday_alert": client_holiday_alert,
    })

def login_view (request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "intranet/login.html", {
                "message": "Error en usuario y/o contraseña."
            })
    else:
        return render(request, "intranet/login.html")

@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))

def error (request):
    return render(request, "intranet/error.html")


def get_filtered_trips(user):

    today = date.today()

    try:
        search = Search.objects.get(user=user)
    except Search.DoesNotExist:
        search = None

    base_qs = Trip.objects.filter(department=user.department).select_related(
        'client', 'contact', 'responsable_user', 'operations_user', 'consultant_tp'
    )

    if search:
        qs = base_qs
        if search.name:
            qs = qs.filter(name__icontains=search.name)
        if search.client_reference:
            qs = qs.filter(client_reference__icontains=search.client_reference)
        if search.tourplanId:
            qs = qs.filter(tourplanId__icontains=search.tourplanId)
        return qs

    # No search — default view
    if user.userType == "Ventas":
        return base_qs.filter(responsable_user=user)
    else:
        cutoff = today + timedelta(days=16)
        return base_qs.filter(travelling_date__gte=today, travelling_date__lt=cutoff)


@login_required
def advanced_search(request):
    # Get 2 years from now
    today = datetime.today()
    days = 730
    to_date = today + timedelta(days=days)

    # Transform to ISO to use as a default in the form
    to_date_iso = to_date.strftime("%Y-%m-%d")

    if request.method == "POST":

        # Delete previous search/s
        previous_search = Search.objects.filter(user=request.user)
        previous_search.delete()

        # Get the information from the form
        starting_date_from_form = request.POST["starting_date_from"]
        starting_date_to_form = request.POST["starting_date_to"]
        name = request.POST["name"]
        client_reference = request.POST["client_reference"]
        tourplanId = request.POST["tourplanId"]
        status = request.POST.getlist("status", None)
        difficulty = request.POST.getlist("difficulty", None)
        responsable_user_form = request.POST.getlist("responsable_user", None)
        operations_user_form = request.POST.getlist("operations_user", None)

        starting_date_from = datetime.fromisoformat(starting_date_from_form)
        starting_date_to = datetime.fromisoformat(starting_date_to_form)

        # Create the search info
        search = Search.objects.create(
            user=request.user,
            starting_date_from=starting_date_from,
            starting_date_to=starting_date_to,
            name=name,
            client_reference=client_reference,
            tourplanId=tourplanId,
            status=status,
            difficulty=difficulty,
        )
        search.save()

        # Add the information of users to the new search info
        if responsable_user_form:
            for user_id in responsable_user_form:
                responsable_user = User.objects.get(id=user_id)
                search.responsable_user.add(responsable_user)

        if operations_user_form:
            for operations_user_id in operations_user_form:
                operations_user = User.objects.get(id=operations_user_id)
                search.operations_user.add(operations_user)

        search.save()

        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))

    else:
        return render(request, "intranet/search.html", {
            "trips":Trip.objects.all(),
            "status": STATUS_OPTIONS,
            "trip_types": TRIP_TYPES,
            "dh_types": DH_TYPES,
            "difficulty_options": DIFFICULTY_OPTIONS,
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all(),
            "users": User.objects.all(),
            "to_date_default": to_date_iso,
        })


@login_required
def create_country(request):

    # If method is POST it will create the new country
    if request.method == "POST":

        # Attempt to create country
        name = request.POST["name"]
        code = request.POST["code"]

        # Validations
        if not name or not code:
            return render(request, "intranet/countries.html", {
                "message": "Todos los campos deben ser completados",
                "countries": Country.objects.all(),
            })

        if len(code) != 2:
            return render(request, "intranet/countries.html", {
                "message": "El código del país debe tener 2 caracteres",
                "countries": Country.objects.all(),
            })

        # Creates the model of the country from the form information
        new_country = Country.objects.create(
            name=name,
            code=code,
        )
        new_country.save()

        return render(request, "intranet/countries.html", {
            "countries": Country.objects.all(),
        })


    # If method is GET it displays the form to add new country
    else:
        return render(request, "intranet/countries.html", {
            "countries": Country.objects.all()
        })

@login_required
def create_client(request):

    # If method is POST it will create the new client
    if request.method == "POST":

        # Attempt to create client
        name = request.POST["name"]
        country_form = request.POST["country"]
        category = request.POST["category"]

        # Validations
        if not name or not country_form or not category:
            return render(request, "intranet/clients.html", {
                "message": "Todos los campos deben ser completados",
                "clients": Client.objects.all(),
                "countries": Country.objects.all(),
                "categories": CLIENT_CATEGORIES,
                "departments": DEPARTMENTS,
            })

        # Defines the department as the user department
        department = request.user.department

        # Get the country from the country ID of the form
        country = Country.objects.get(id=country_form)

        # Creates the model of the client from the form information
        new_client = Client.objects.create(
            name=name,
            country=country,
            department=department,
            category=category,
        )
        new_client.save()

        # Habilitar todos los productos activos para la nueva agencia
        from tariff.models import Product
        new_client.available_clients.set(Product.objects.filter(isActivated=True))

        return render(request, "intranet/clients.html", {
            "clients": Client.objects.all(),
            "countries": Country.objects.all(),
            "categories": CLIENT_CATEGORIES,
            "departments": DEPARTMENTS,
        })

    # If method is GET it displays the form to add new client
    else:
        return render(request, "intranet/clients.html", {
            "clients": Client.objects.all(),
            "countries": Country.objects.all(),
            "categories": CLIENT_CATEGORIES,
            "departments": DEPARTMENTS,
        })


@login_required
def create_client_contact(request):
    if request.method == "POST":

        # Attempt to create contact
        name = request.POST["name"]
        email = request.POST["email"]
        client_form = request.POST["client"]

        # Validations
        if not name or not email or not client_form:
            return render(request, "intranet/contacts.html", {
                "message": "Todos los campos deben ser completados",
                "clients": Client.objects.all(),
                "contacts": ClientContact.objects.all()
            })

        # Get the client from the client ID of the form
        client = Client.objects.get(id=client_form)

        # Creates the model of the contact from the form information
        new_contact = ClientContact.objects.create(
            name=name,
            email=email,
            client=client,
        )
        new_contact.save()

        return render(request, "intranet/contacts.html", {
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all()
        })

    else:
        return render(request, "intranet/contacts.html", {
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all()
        })


@login_required
def create_user(request):
    if request.method == "POST":

        # Attempt to create user
        name = request.POST["name"]
        username= request.POST["username"]
        other_tp = request.POST.get("other_tp", "").strip()
        email = request.POST["email"]
        password = request.POST["password"]
        department = request.POST["department"]
        type = request.POST["type"]

        try:
            isAdmin = request.POST['admin']
        except MultiValueDictKeyError:
            isAdmin = False

        if isAdmin != False:
            isAdmin = True

        # Validations
        if not name or not email or not username or not password or not department or not type:
            return render(request, "intranet/users.html", {
                "message_new": "Todos los campos deben ser completados",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })

        if len(username) < 2 or len(username) > 3:
            return render(request, "intranet/users.html", {
                "message_new": "El usuario debe tener entre 2 y 3 caracteres",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })

        client_id = request.POST.get("client_id") if type == "Cliente" else None
        if type == "Cliente":
            isAdmin = False

        # Creates the model of the user from the form information
        try:
            new_user = User.objects.create_user(
                other_name=name,
                username=username,
                email=email,
                password=password,
                department=department,
                isAdmin=isAdmin,
                userType=type,
                client_id=client_id or None,
            )

            if other_tp:
                new_user.other_tp = other_tp

            new_user.save()


        except IntegrityError:
            return render(request, "intranet/users.html", {
                "message_new": "El usuario ya existe",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all(),
                "clients": Client.objects.order_by("name"),
            })

        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all(),
            "clients": Client.objects.order_by("name"),
        })

    else:
        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all(),
            "clients": Client.objects.order_by("name"),
        })

@login_required
def modify_user(request, user_id):

    # Gets the object of the user modifying
    user = User.objects.get(id=user_id)

    # Gets the information from the form
    if request.method == "POST":
        # Attempt to modify user
        name = request.POST["name"]
        username = request.POST["username"]
        other_tp = request.POST.get("other_tp", "").strip()
        email = request.POST["email"]
        department = request.POST["department"]
        type = request.POST["type"]

        try:
            isAdmin = request.POST['admin']
        except MultiValueDictKeyError:
            isAdmin = False

        if isAdmin != False:
            isAdmin = True

        try:
            isActivated = request.POST['isActivated']
        except MultiValueDictKeyError:
            isActivated = False

        if isActivated != False:
            isActivated = True

        try:
            is_active = request.POST['isActive']
        except MultiValueDictKeyError:
            is_active = False

        if is_active != False:
            is_active = True

        try:
            color = request.POST['color']
        except MultiValueDictKeyError:
            color = "#000000"

        show_in_client_team = request.POST.get('show_in_client_team') == 'on'

        # Validations
        if not name or not email or not username or not department or not type:
            return render(request, "intranet/users.html", {
                "message_modify": "Todos los campos deben ser completados",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })

        if len(username) < 2 or len(username) > 3:
            return render(request, "intranet/users.html", {
                "message_modify": "El usuario debe tener entre 2 y 3 caracteres",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })

        client_id = request.POST.get("client_id") if type == "Cliente" else None
        if type == "Cliente":
            isAdmin = False

        # Modifies the model of the user from the form information
        user.other_name = name
        user.username = username
        user.other_tp = other_tp if other_tp else user.username
        user.email = email
        user.department = department
        user.isAdmin = isAdmin
        user.isActivated = isActivated
        user.is_active = is_active
        user.userType = type
        user.color = color
        user.show_in_client_team = show_in_client_team
        user.client_id = client_id or None
        user.chat_webhook_url = request.POST.get('chat_webhook_url', '').strip()
        user.chat_user_id = request.POST.get('chat_user_id', '').strip()

        user.save()

        return HttpResponseRedirect(reverse("users"), {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all(),
            "clients": Client.objects.order_by("name"),
        })


@login_required
def change_password_user(request, user_id):
    requesting_user = User.objects.get(id=request.user.id)
    if not requesting_user.isAdmin:
        return HttpResponseRedirect(reverse("users"))

    if request.method == "POST":
        target_user = User.objects.get(id=user_id)
        new_password = request.POST.get("new_password", "").strip()
        if new_password:
            target_user.set_password(new_password)
            target_user.save()

    return HttpResponseRedirect(reverse("users"))


@login_required
def modify_client(request, client_id):

    # Gets the object of the client modifying
    client = Client.objects.get(id=client_id)

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify client
        name = request.POST["name"]
        country_form = request.POST["country"]
        category = request.POST["category"]
        department = request.POST["department"]

        try:
            isActivated = request.POST['isActivated']
        except MultiValueDictKeyError:
            isActivated = False

        if isActivated != False:
            isActivated = True

        # Validations
        if not name or not country_form or not category or not department:
            return render(request, "intranet/clients.html", {
                "message_modify": "Todos los campos deben ser completados",
                "clients": Client.objects.all(),
                "countries": Country.objects.all(),
                "categories": CLIENT_CATEGORIES,
                "departments": DEPARTMENTS,
            })

        country = Country.objects.get(pk=country_form)

        # Modifies the model of the user from the form information
        client.name=name
        client.country=country
        client.category=category
        client.department=department
        client.isActivated=isActivated

        client.save()

        return HttpResponseRedirect(reverse("clients"), {
            "clients": Client.objects.all(),
            "countries": Country.objects.all(),
            "categories": CLIENT_CATEGORIES,
            "departments": DEPARTMENTS,
        })


@login_required
def modify_contact(request, contact_id):

    # Gets the object of the contact modifying
    contact = ClientContact.objects.get(id=contact_id)

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify contact
        name = request.POST["name"]
        email = request.POST["email"]
        client_form = request.POST["client"]

        try:
            isActivated = request.POST['isActivated']
        except MultiValueDictKeyError:
            isActivated = False

        if isActivated != False:
            isActivated = True

        # Validations
        if not name or not email or not client_form:
            return render(request, "intranet/contacts.html", {
                "message_modify": "Todos los campos deben ser completados",
                "clients": Client.objects.all(),
                "contacts": ClientContact.objects.all()
            })

        client = Client.objects.get(pk=client_form)

        # Modifies the model of the contact from the form information
        contact.name=name
        contact.email=email
        contact.client=client
        contact.isActivated=isActivated

        contact.save()

        return HttpResponseRedirect(reverse("contacts"), {
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all()
        })


@login_required
def modify_country(request, country_id):

    # Gets the object of the country modifying
    country = Country.objects.get(id=country_id)

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify country
        name = request.POST["name"]
        code = request.POST["code"]

        # Validations
        if not name or not code:
            return render(request, "intranet/countries.html", {
                "message_modify": "Todos los campos deben ser completados",
                "countries": Country.objects.all(),
            })

        if len(code) != 2:
            return render(request, "intranet/countries.html", {
                "message_modify": "El código del país debe tener 2 caracteres",
                "countries": Country.objects.all(),
            })

        # Modifies the model of the contact from the form information
        country.name=name
        country.code=code

        country.save()

        return HttpResponseRedirect(reverse("countries"), {
            "countries": Country.objects.all(),
        })


def get_return_page(page, type, user):

    filter_trips = get_filtered_trips(user)

    formated_starting_dates = []
    formated_travelling_dates = []
    formated_out_dates = []

    for trip in filter_trips:
        formated_starting_date = trip.starting_date.isoformat()
        formated_starting_dates.append((trip.id, formated_starting_date))
        formated_travelling_date = trip.travelling_date.isoformat()
        formated_travelling_dates.append((trip.id, formated_travelling_date))
        if trip.out_date:
            formated_out_date = trip.out_date.isoformat()
        else:
            formated_out_date = (trip.travelling_date + timedelta(days=1)).isoformat()
        formated_out_dates.append((trip.id, formated_out_date))

    if page == "trips":

        if type == "error":
            return {
                    "message_new": "Completar todos los campos",
                    "status": STATUS_OPTIONS,
                    "trip_types": TRIP_TYPES,
                    "dh_types": DH_TYPES,
                    "difficulty_options": DIFFICULTY_OPTIONS,
                    "clients": Client.objects.filter(department=user.department),
                    "contacts": ClientContact.objects.filter(client__department=user.department),
                    "trips": filter_trips,
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                    "users": User.objects.filter(department=user.department),
                    "notes": Notes.objects.filter(trip__in=filter_trips).select_related('trip', 'user'),
                    "one_hundred": 100,
                    "feedbacks": Feedback.objects.filter(trip__in=filter_trips).select_related('trip'),
                }
        else:
            return {
                    "status": STATUS_OPTIONS,
                    "trip_types": TRIP_TYPES,
                    "dh_types": DH_TYPES,
                    "difficulty_options": DIFFICULTY_OPTIONS,
                    "clients": Client.objects.filter(department=user.department),
                    "contacts": ClientContact.objects.filter(client__department=user.department),
                    "trips": filter_trips,
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                    "users": User.objects.filter(department=user.department),
                    "notes": Notes.objects.filter(trip__in=filter_trips).select_related('trip', 'user'),
                    "one_hundred": 100,
                    "feedbacks": Feedback.objects.filter(trip__in=filter_trips).select_related('trip'),
                }

    if page == "entries":
        if type == "error":
            return {
                    "message_new": "Completar todos los campos",
                    "status": STATUS_OPTIONS,
                    "importance_options": IMPORTANCE_OPTIONS,
                    "progress_options": PROGRESS_OPTIONS,
                    "users": User.objects.filter(department=user.department),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                }
        else:
            return {
                    "status": STATUS_OPTIONS,
                    "importance_options": IMPORTANCE_OPTIONS,
                    "progress_options": PROGRESS_OPTIONS,
                    "users": User.objects.filter(department=user.department),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                }


def clean_search(request):

    try:
        # Delete previous search/s
        previous_search = Search.objects.filter(user=request.user)
        previous_search.delete()
    except Search.DoesNotExist:
        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))

    return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))

@login_required
def create_trip(request):
    if request.method == "POST":
        # Detectar si es una request AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        try:
            # Get all the info from the form
            name = request.POST.get("name", "").strip()
            quantity_pax = request.POST["quantity_pax"]
            starting_date = request.POST.get("starting_date")
            travelling_date = request.POST.get("travelling_date")
            client_form = request.POST.get("client")
            contact_form = request.POST.get("contact")
            client_reference = request.POST.get("client_reference", "")
            status = request.POST.get("status")
            difficulty = request.POST.get("difficulty", "")

            # Validar campos requeridos
            if not name or not starting_date or not travelling_date or not status or difficulty == "":
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': 'Por favor complete todos los campos requeridos',
                        'errors': {
                            'form': ['Faltan campos obligatorios']
                        }
                    }, status=400)
                else:
                    return render(request, "intranet/trips.html",
                                get_return_page("trips", "error", request.user))

            # Get the client from the client ID of the form
            if client_form == "0" or client_form == "Cliente" or not client_form:
                client = Client.objects.get(name="Sin Cliente")
            else:
                try:
                    client = Client.objects.get(id=client_form)
                except Client.DoesNotExist:
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'message': 'Cliente no encontrado',
                            'errors': {'client': ['Cliente inválido']}
                        }, status=400)
                    else:
                        return render(request, "intranet/trips.html",
                                    get_return_page("trips", "error", request.user))

            # Get the contact from the contact ID of the form (or create inline)
            new_contact_name  = request.POST.get("new_contact_name", "").strip()
            new_contact_email = request.POST.get("new_contact_email", "").strip()
            if new_contact_name and client_form and client_form not in ("0", "Cliente"):
                try:
                    _client_for_contact = Client.objects.get(id=client_form)
                except Client.DoesNotExist:
                    _client_for_contact = None
                if _client_for_contact:
                    contact = ClientContact.objects.create(
                        name=new_contact_name,
                        email=new_contact_email or 'quote@aliwenincoming.com.ar',
                        client=_client_for_contact,
                    )
                else:
                    contact = ClientContact.objects.get(name="Sin Contacto")
            elif contact_form == "0" or contact_form == "Contacto" or not contact_form:
                contact = ClientContact.objects.get(name="Sin Contacto")
            else:
                try:
                    contact = ClientContact.objects.get(id=contact_form)
                except ClientContact.DoesNotExist:
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'message': 'Contacto no encontrado',
                            'errors': {'contact': ['Contacto inválido']}
                        }, status=400)
                    else:
                        return render(request, "intranet/trips.html",
                                    get_return_page("trips", "error", request.user))

            # Get the department from the user department
            department = request.user.department

            # Set the default undefined users SD for the new trip booking options
            responsable_user = User.objects.get(pk=19)
            operations_user = User.objects.get(pk=19)
            dh = None

            # Creates the model of the trip from the form information
            new_trip = Trip.objects.create(
                name=name,
                quantity_pax=quantity_pax,
                status=status,
                client=client,
                client_reference=client_reference,
                starting_date=starting_date,
                travelling_date=travelling_date,
                contact=contact,
                difficulty=difficulty,
                department=department,
                responsable_user=responsable_user,
                operations_user=operations_user,
                dh=dh,
                creation_user=request.user
            )
            new_trip.save()

            # Responder según el tipo de request
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'trip_id': new_trip.id,
                    'user_id': request.user.id,
                    'message': 'Viaje creado exitosamente',
                    'trip_name': new_trip.name
                })
            else:
                # Método tradicional (fallback)
                return HttpResponse(status=204)

        except Exception as e:
            # Manejo de errores generales
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al crear el viaje: {str(e)}',
                    'errors': {'general': [str(e)]}
                }, status=500)
            else:
                return render(request, "intranet/trips.html",
                            get_return_page("trips", "error", request.user))

    else:
        # GET request - mostrar el formulario
        context = get_return_page("trips", "", request.user)

        # Filtros para drill-down desde estadísticas
        date_from    = request.GET.get("date_from")
        date_to      = request.GET.get("date_to")
        month        = request.GET.get("month")
        year         = request.GET.get("year")
        week         = request.GET.get("week")
        season       = request.GET.get("season")
        vr_filter    = request.GET.get("vr_filter")
        op_filter    = request.GET.get("op_filter")
        client_filter = request.GET.get("client_filter")
        user_filter  = request.GET.get("user_filter")   # vendedor en entradas
        status_filter = request.GET.get("status_filter")  # ej. "Booking" desde stats de viajes

        has_filter = any([date_from, date_to, month, year, week, season,
                          vr_filter, op_filter, client_filter, user_filter, status_filter])

        if has_filter:
            qs = Trip.objects.filter(
                department=request.user.department
            ).select_related('client', 'contact', 'responsable_user', 'operations_user')

            if status_filter:
                qs = qs.filter(status=status_filter)

            if date_from and date_to:
                qs = qs.filter(travelling_date__range=(date_from, date_to))
            elif month and year:
                qs = qs.filter(travelling_date__month=month, travelling_date__year=year)
            elif season:
                _s = int(season)
                qs = qs.filter(travelling_date__range=(date(_s, 5, 1), date(_s + 1, 4, 30)))
            elif week:
                _today = date.today()
                _this_week = _today.isocalendar()[1]
                _week_year = _today.year - 1 if int(week) > _this_week else _today.year
                qs = qs.filter(travelling_date__range=(
                    date.fromisocalendar(_week_year, int(week), 1),
                    date.fromisocalendar(_week_year, int(week), 7),
                ))

            if vr_filter:
                qs = qs.filter(responsable_user__other_name=vr_filter)
            if op_filter:
                qs = qs.filter(operations_user__other_name=op_filter)
            if client_filter:
                qs = qs.filter(client__name=client_filter)
            if user_filter:
                qs = qs.filter(entry_trips__user_working__other_name=user_filter).distinct()

            formated_starting_dates, formated_travelling_dates, formated_out_dates = [], [], []
            for t in qs:
                formated_starting_dates.append((t.id, t.starting_date.isoformat()))
                formated_travelling_dates.append((t.id, t.travelling_date.isoformat()))
                _out = t.out_date or (t.travelling_date + timedelta(days=1))
                formated_out_dates.append((t.id, _out.isoformat()))

            context.update({
                "trips": qs,
                "formated_starting_dates": formated_starting_dates,
                "formated_travelling_dates": formated_travelling_dates,
                "formated_out_dates": formated_out_dates,
                "notes": Notes.objects.filter(trip__in=qs).select_related('trip', 'user'),
                "feedbacks": Feedback.objects.filter(trip__in=qs).select_related('trip'),
                "filter_active": True,
            })

        return render(request, "intranet/trips.html", context)


@login_required
def modify_trip(request, trip_id):

    # Gets the object of the trip modifying
    trip = Trip.objects.get(id=trip_id)

    if request.method == "POST":
        name = request.POST["name"]
        quantity_pax = request.POST["quantity_pax"]
        starting_date_form = request.POST["starting_date"]
        travelling_date_form = request.POST["travelling_date"]
        client_form = request.POST["client"]
        contact_form = request.POST["contact"]
        client_reference = request.POST["client_reference"]
        status = request.POST["status"]
        difficulty = request.POST["difficulty"]
        tourplanId = request.POST["tourplanId"]
        trip_type = request.POST["trip_type"]
        out_date_form = request.POST["out_date"]

        if trip.status == "Booking":
            itId = request.POST["itId"]
            dh_type = request.POST["dh_type"]
            if request.user.isAdmin:
                responsable_user_form = request.POST.get("responsable_user") or (trip.responsable_user.id if trip.responsable_user else User.objects.get(username="SD").id)
            else:
                responsable_user_form = trip.responsable_user.id if trip.responsable_user else User.objects.get(username="SD").id
            operations_user_form = request.POST["operations_user"]
            dh_form = request.POST.get("dh", "")
            guide = request.POST["guide"]
        else:
            itId = ""
            dh_type = "Sin definir"
            responsable_user_form = User.objects.get(username="SD").id
            operations_user_form = User.objects.get(username="SD").id
            dh_form = ""
            guide = ""


        if not name or not starting_date_form or not client_form or not contact_form or not status or not quantity_pax or not difficulty:
            return render(request, "intranet/trips.html", get_return_page("trips", "error", request.user))


        # Get the client from the client ID of the form
        client = Client.objects.get(id=client_form)

        # Get the contact from the contact ID of the form
        contact = ClientContact.objects.get(id=contact_form)

        # Get the department from the user department
        department = request.user.department

        # Get the user from the user ID of the form
        responsable_user = User.objects.get(id=responsable_user_form)
        operations_user = User.objects.get(id=operations_user_form)
        dh = dh_form

        # Return the correct date to the model from the form
        starting_date = datetime.fromisoformat(starting_date_form)
        travelling_date = datetime.fromisoformat(travelling_date_form)
        out_date = datetime.fromisoformat(out_date_form)

        # Modifies the model of the user from the form information
        trip.name=name
        trip.quantity_pax=quantity_pax
        trip.status=status
        trip.difficulty=difficulty
        trip.client=client
        trip.client_reference=client_reference
        trip.starting_date=starting_date
        trip.travelling_date=travelling_date
        trip.contact=contact
        trip.department=department
        trip.tourplanId=tourplanId
        trip.itId=itId
        trip.trip_type=trip_type
        trip.dh_type=dh_type
        trip.responsable_user=responsable_user
        trip.operations_user=operations_user
        trip.out_date=out_date
        trip.dh=dh
        trip.guide=guide

        if request.POST.get("reactivate_margin_warning"):
            trip.ignore_margin_warning = False

        trip.save()

        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))


@login_required
def create_note(request, trip_id):

    trip = Trip.objects.get(id=trip_id)

    # If method is POST it will create the new note
    if request.method == "POST":

        # Gets the information from the form
        content = request.POST["content"]

        # Validations
        if not content:
            return render(request, "intranet/trips.html", get_return_page("trips", "error", request.user))


        # Creates the model of the note from the form information
        new_note = Notes.objects.create(
            user=request.user,
            trip=trip,
            content=content,
            creation_date=datetime.now(),
        )
        new_note.save()

        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))


@login_required
def create_feedback(request, trip_id):

    trip = Trip.objects.get(id=trip_id)

    # If method is POST it will create the new feedback
    if request.method == "POST":

        # Gets the information from the form
        content = request.POST["content"]
        creation_date = request.POST["creation_date"]
        supplier_form = request.POST["supplier"]
        destination_form = request.POST["destination"]
        type = request.POST["type"]

        try:
            complaint = request.POST['complaint']
            if complaint == "on":
                complaint = True
        except MultiValueDictKeyError:
            complaint = False

        # Validations
        if not content or not creation_date or not type:
            return render(request, "intranet/trips.html", get_return_page("trips", "error", request.user))

        if supplier_form != "":
            supplier = Supplier.objects.get(id=supplier_form)
        else:
            supplier = None
        if destination_form != "":
            destination = Location.objects.get(id=destination_form)
        else:
            destination = None

        # Creates the model of the feedback from the form information
        new_feedback = Feedback.objects.create(
            user=request.user,
            trip=trip,
            content=content,
            creation_date=creation_date,
            last_modification_date=datetime.now(),
            supplier=supplier,
            destination=destination,
            type=type,
            complaint=complaint,
        )
        new_feedback.save()

        # After created it goes to Trip page again
        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", "", request.user))
    else:

        # Return the feedback info for the form
        return render(request, "intranet/new_feedback.html", {
            "trip": trip,
            "suppliers": Supplier.objects.all(),
            "destinations": Location.objects.all(),
            "types": TYPE_QUALITY,
        })


@login_required
def pendings(request):
    ctx = get_return_page("entries", "", request.user)
    if request.user.userType != "Cliente":
        today = date.today()
        ctx["today_absences"] = [
            {
                "name": a.absence_user.other_name or a.absence_user.username,
                "color": a.absence_user.color or '#6c757d',
                "type": a.type_absence,
            }
            for a in _absences_on_day(today, request.user.department)
        ]
    else:
        ctx["today_absences"] = []
    ctx["progress_legend"] = [
        (
            f'<span style="background:{bg};color:{fg};padding:2px 10px;'
            f'border-radius:999px;font-size:.82em;white-space:nowrap;">{label}</span>',
            desc,
        )
        for label, bg, fg, desc in [
            ("0 - Not started yet",        "#9ca3af", "#fff", "The enquiry has been received but work has not yet begun."),
            ("1 - Analysed",               "#60a5fa", "#fff", "The request has been reviewed and understood."),
            ("2 - Suppliers contacted",    "#3b82f6", "#fff", "We have reached out to the relevant suppliers for availability, pricing or reconfirmation."),
            ("3 - Status sent",            "#f59e0b", "#fff", "A status update or draft information has been sent to you."),
            ("4 - Awaiting response",      "#f97316", "#fff", "We are waiting for a reply from a supplier or from your side."),
            ("5 - Finalised",              "#22c55e", "#fff", "The quote, booking or final itinerary is complete and under final revision."),
        ]
    ]
    if request.user.userType == "Cliente":
        ctx["client_holiday_alert"] = _get_client_holiday_alert(date.today())
    if request.user.userType != "Cliente":
        ctx["dept_users_for_revision"] = User.objects.filter(
            department=request.user.department, isActivated=True,
            show_in_calendar=True, userType='Ventas',
        ).order_by('username')
        ctx["my_revision_pending_count"] = Entry.objects.filter(
            revising_user=request.user,
            is_revised=False,
            trip__department=request.user.department,
        ).exclude(revision_link__isnull=True).exclude(revision_link='').count()
    return render(request, "intranet/pendings.html", ctx)

@login_required
def create_entry(request, trip_id):

    filter_entries = Entry.objects.filter(isClosed=False)

    # Get the trip from the trip ID of the button
    trip = Trip.objects.get(id=trip_id)

    if request.method == "POST":
        starting_date = request.POST["starting_date"]
        status = request.POST["status"]
        importance = request.POST["importance"]
        user_working_form = request.POST["user_working"]
        note = request.POST["note"]

        # Validations of the form
        if not starting_date or not status or not importance or not user_working_form:
            _today = date.today()
            _next = _next_working_days(_today, 2)
            _day_labels = [(_today, 'hoy')] + [(_next[i], f'en {i+1} día{"s" if i else ""} hábil{"es" if i else ""}') for i in range(len(_next))]
            _alerts = {}
            for _d, _l in _day_labels:
                for _a in _absences_on_day(_d, request.user.department):
                    if _a.absence_user.username not in _alerts:
                        _alerts[_a.absence_user.username] = _l
            return render(request, "intranet/new_entry.html", {
                "entries": filter_entries,
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "trip": trip,
                "absence_alerts": _alerts,
            })

        # Get the user from the username in the form
        user_working = User.objects.get(username=user_working_form)

        # Get the elements for the last and first entries
        first_entry = Entry.objects.filter(trip=trip).last()

        # Set the version of the quote and booking defaults
        if status == "Quote":
            version_quote = chr(int(ord(trip.version_quote)) + 1)
            version = trip.version
            user_creator = user_working
            trip.version_quote = chr(int(ord(trip.version_quote)) + 1)
        elif status == "Booking":
            if (trip.version == 0):
                trip.conversion_date = starting_date
                trip.status = "Booking"
            if first_entry != None:
                trip.user_creator = first_entry.user_working
                user_creator = first_entry.user_working
            else:
                user_creator = user_working
            trip.save()
            version = int(trip.version) + 1
            version_quote = trip.version_quote

            trip.version += 1

        # If the status is Final Itinerary the user creator is the responsable user
        elif status == "Final Itinerary":
            version = 1
            user_creator = trip.responsable_user or user_working
            version_quote = trip.version_quote

        # If file is cancelled then the trip status change to "Cancelado"
        elif status == "Cancelado":
            version = 1
            version_quote = trip.version_quote
            user_creator = trip.responsable_user or user_working
            trip.status = "Cancelado"
            trip.save()
        else:
            version_quote = "@"
            version = 1
            user_creator = user_working

        trip.save()

        # Chose the first option progress by default
        progress = PROGRESS_OPTIONS[0]

        # Creates the model of the contact from the form information
        new_entry = Entry.objects.create(
            trip=trip,
            starting_date=starting_date,
            status=status,
            importance=importance,
            user_working=user_working,
            user_creator=user_creator,
            version_quote=version_quote,
            version=version,
            progress=progress[0],
            amount=0,
            creation_user=request.user,
            note=note
        )
        new_entry.save()

        # Si la petición viene por AJAX (fetch con header X-Requested-With)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "entry_id": new_entry.id,
                "user_id": request.user.id
            })

        # Si no, comportamiento normal (mantiene compatibilidad)
        return HttpResponse(status=204)

    else:
        today = date.today()
        next_wd = _next_working_days(today, 2)
        day_labels = [(today, 'hoy')] + [
            (next_wd[i], f'en {i+1} día{"s" if i else ""} hábil{"es" if i else ""}')
            for i in range(len(next_wd))
        ]
        absence_alerts = {}
        for d, label in day_labels:
            for a in _absences_on_day(d, request.user.department):
                uname = a.absence_user.username
                if uname not in absence_alerts:
                    absence_alerts[uname] = label

        last_entry = Entry.objects.filter(trip=trip).order_by('-id').first()
        last_user_working = last_entry.user_working.username if last_entry and last_entry.user_working else ''

        return render(request, "intranet/new_entry.html", {
            "entries": filter_entries,
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "trip": trip,
            "absence_alerts": absence_alerts,
            "last_user_working": last_user_working,
        })

@login_required
def modify_entry(request, entry_id):

    # Get the entry from the entry ID of the button
    entry = Entry.objects.get(id=entry_id)

    entries_trips = Trip.objects.filter(department=request.user.department)

    # Substract 3 hours for dates and make the iso format to match the form
    three_hours = timedelta(hours=3)
    starting_date_local = entry.starting_date - three_hours
    iso_starting_date = starting_date_local.isoformat()
    formated_starting_date = iso_starting_date[:16]

    closing_date_local = entry.closing_date - three_hours
    iso_closing_date = closing_date_local.isoformat()
    formated_closing_date = iso_closing_date[:16]

    # Get the information from the form
    if request.method == "POST":
        starting_date = request.POST["starting_date"]
        status = request.POST["status"]
        importance = request.POST["importance"]
        user_working_form = request.POST["user_working"]
        version = request.POST["version"]
        version_quote = request.POST["version_quote"]
        user_creator_form = request.POST["user_creator"]
        user_working_form = request.POST["user_working"]
        amount = request.POST["amount"]
        progress = request.POST["progress"]
        closing_date_form = request.POST["closing_date"]
        note = request.POST["note"]
        tourplanId = request.POST["tourplanId"]

        try:
            isClosed = request.POST['isClosed']
        except MultiValueDictKeyError:
            isClosed = False

        if isClosed != False:
            isClosed = True

        # Validations of the form
        if not starting_date or not status or not importance or not user_working_form:
            return render(request, "intranet/edit_entry.html", {
                "message": "Completar todos los campos obligatorios",
                "trips": entries_trips,
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.filter(department=request.user),
                "entry": entry,
                "formated_starting_date": formated_starting_date,
                "formated_closing_date": formated_closing_date,
            })

        # Checks if version and amount are Int
        versionIsInt = isinstance(version, int)

        empty_amount = False

        try:
            amount = int(amount)
        except ValueError:
            empty_amount = True

        if status != "Quote" and versionIsInt:
            return render(request, "intranet/edit_entry.html", {
                "message": "La versión debe ser un número, a no ser que sea status Quote",
                "trips": entries_trips,
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.filter(department=request.user),
                "entry": entry,
                "formated_starting_date": formated_starting_date,
                "formated_closing_date": formated_closing_date,
            })
        elif (status == "Quote" or status == "Booking" or status == "Cancelado") and isClosed and empty_amount == True:
            return render(request, "intranet/edit_entry.html", {
                "message": "El monto es obligatorio para status Quote y Booking",
                "trips": entries_trips,
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.filter(department=request.user),
                "entry": entry,
                "formated_starting_date": formated_starting_date,
                "formated_closing_date": formated_closing_date,
            })

        # Get the user from the username in the form
        user_working = User.objects.get(id=user_working_form)
        user_creator = User.objects.get(id=user_creator_form)

        # Get the trip from the entry
        trip = entry.trip

        # Set the version of the quote and booking defaults
        new_version = int(version) if str(version).isdigit() else 0
        if status == "Booking" and new_version == 1:
            trip.status = "Booking"
            if not trip.conversion_date:
                trip.conversion_date = timezone_now()

        if status == "Quote":
            trip.version_quote = version_quote
        else:
            trip.version = version

        if isClosed == True:
            closing_date = datetime.fromisoformat(closing_date_form)
            entry.closing_date = closing_date
            entry.update_response()

        # If there is no amount, get the trip amount and save it to the entry
        if empty_amount == False:
            trip.amount = amount
            entry.amount = amount

        # If there is tourplan ID is no empty get it from the form
        if tourplanId != "":
            trip.tourplanId = tourplanId

        # Save all the changes of the trip
        trip.save()

        # Modifies the model of the entry with the form information
        entry.starting_date=starting_date
        entry.status=status
        entry.importance=importance
        entry.user_working=user_working
        entry.user_creator=user_creator
        entry.progress=progress
        entry.isClosed=isClosed
        entry.note=note
        entry.tourplanId=tourplanId

        if status == "Quote":
            entry.version_quote = version_quote
        else:
            entry.version = version

        update_timingStatus(entry)

        entry.save()

        return HttpResponseRedirect(reverse("entries"), {
            "trips": entries_trips,
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "entry": entry,
            "formated_starting_date": formated_starting_date,
            "formated_closing_date": formated_closing_date,
            })

    else:
        return render(request, "intranet/edit_entry.html", {
            "trips": entries_trips,
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "entry": entry,
            "formated_starting_date": formated_starting_date,
            "formated_closing_date": formated_closing_date,
            })

@login_required
def stats(request):

    # Get current month, year and week
    this_month = date.today().month
    this_week = date.today().isocalendar()[1]
    this_year = date.today().year
    today = date.today()

    # Empty list of the weeks that will be listed in the form
    weeks = []

    # Get the Monday of the current week (ISO: monday=1, sunday=7)
    start_of_week = today - timedelta(days=today.isoweekday() - 1)

    # Get the list of the 20 weeks before and 20 weeks later than the current week
    for i in range(-30, 1):
        start = start_of_week + timedelta(weeks=i)
        end = start + timedelta(days=6)
        week_number = start.isocalendar()[1]

        # Add the weeks with Spanish format
        weeks.append(
            (week_number, f"Semana {week_number} - {start.strftime('%-d-%m-%Y')} al {end.strftime('%-d-%m-%Y')}")
        )

    return render(request, "intranet/stats.html", {
        "months":MONTHS,
        "this_month":this_month,
        "this_year":this_year,
        "this_week":this_week,
        "weeks":weeks,
    })


@require_GET
def stats_entries_report(request):
    """
    Renderiza la página de reporte de estadísticas
    Recibe parámetros por GET:
    - type: 'vendor' o 'client'
    - period: descripción del período
    - week/month/year/date_from/date_to: según el filtro
    """

    # Get the dates from the information sent
    date_from = request.GET.get('date_from', "Desde")
    date_to = request.GET.get('date_to', "Hasta")

    date_from_formatted = datetime.fromisoformat(date_from)
    date_to_formatted = datetime.fromisoformat(date_to)

    # Check if there are any errors
    missing_amounts = check_missing_amounts(date_from, date_to)
    if missing_amounts:
        missing_amounts_entries = []

        for entry in missing_amounts:
            missing_amounts_entries.append((entry.trip.name, entry.status))

        message_one = f"Falta monto de: {missing_amounts_entries})"
    else:
        message_one = "Todos los montos están completos"

    incongruent_entry_dates = check_incongruent_entry_dates(date_from, date_to)
    if incongruent_entry_dates:
        incongruent_entries = []

        for entry in incongruent_entry_dates:
            incongruent_entries.append((entry.trip.name, entry.status))

        message_two = f"Inconsistencia en fecha: {incongruent_entries})"
    else:
        message_two = "Todos las fechas están correctas"

    # Get the information type and period
    report_type = request.GET.get('type', 'vendor')
    period = request.GET.get('period', 'Período Personalizado')

    context = {
        'report_type': report_type,
        'period': period,
        'message_one': message_one,
        'message_two': message_two,
    }

    return render(request, 'intranet/stats_entries_report.html', context)


@require_GET
def stats_trips_report(request):
    """
    Renderiza la página de reporte de estadísticas
    Recibe parámetros por GET:
    - type: 'vendor' o 'client'
    - period: descripción del período
    - week/month/year/date_from/date_to: según el filtro
    """

    # Get the dates from the information sent
    date_from = request.GET.get('date_from', "Desde")
    date_to = request.GET.get('date_to', "Hasta")

    date_from_formatted = datetime.fromisoformat(date_from)
    date_to_formatted = datetime.fromisoformat(date_to)

    # Check if there are any errors
    duplicated = check_duplicate_trips(date_from, date_to)
    if duplicated:
        duplicate_trips = []

        for trip in duplicated:
            duplicate_trips.append((trip.name, trip.client))

        message_one = f"Viaje duplicado: {duplicate_trips})"
    else:
        message_one = "No hay viajes duplicados"

    incongruent_trip_dates = check_incongruent_trip_dates(date_from, date_to)
    if incongruent_trip_dates:
        incongruent_trips = []

        for trip in incongruent_trip_dates:
            incongruent_trips.append((trip.name, trip.client))

        message_two = f"Inconsistencia en fecha: {incongruent_trips})"
    else:
        message_two = "Todos las fechas están correctas"

    # Get the information type and period
    report_type = request.GET.get('type', 'vendor')
    period = request.GET.get('period', 'Período Personalizado')

    context = {
        'report_type': report_type,
        'period': period,
        'message_one': message_one,
        'message_two': message_two,
    }

    return render(request, 'intranet/stats_trips_report.html', context)


_HOLIDAY_COLORS = {
    'Feriado': '#87CEEB',
    'Fin de semana': '#BDBDBD',
    'Día no laborable': '#F0F0F0',
}

_ABSENCE_COLORS = {
    'Beneficio Vacaciones': '#FFB3C1',
    'Compensatorios': '#ADD8E6',
    'Cumpleaños': '#FF1744',
    'Cumpleaños en baja': '#90EE90',
    'Enfermedad': '#FF6D00',
    'Exámenes/Día de Estudio': '#A8E6A3',
    'FAM/Trabajando fuera ofi': '#00E5FF',
    'Feriado trabajado': '#1A237E',
    'Feriado trabajado 1/2': '#3949AB',
    'Semana home': '#827717',
    'Sin goce de sueldo': '#5D1919',
    'Vacaciones': '#FF00FF',
    'Viernes OFF alta': '#FFD600',
    'Viernes OFF': '#FFD600',
}


def _calendar_staff_users(department):
    from django.db.models import Case, When, Value, IntegerField
    return (
        User.objects
        .filter(
            isActivated=True,
            department=department,
            userType__in=['Internal', 'Ventas', 'Operaciones', 'Manager'],
        )
        .annotate(_order=Case(
            When(userType='Internal',    then=Value(0)),
            When(userType='Ventas',      then=Value(1)),
            When(userType='Operaciones', then=Value(2)),
            When(userType='Manager',     then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ))
        .order_by('_order', 'username')
    )


@login_required
def holidays(request):
    staff_users = _calendar_staff_users(request.user.department)
    locations = Location.objects.all().order_by('order', 'name')
    return render(request, "intranet/holidays.html", {
        'staff_users': staff_users,
        'absence_types': TYPE_ABSENCE,
        'current_year': date.today().year,
        'locations': locations,
        'ext_categories': EXT_CALENDAR_CATEGORIES,
    })


@login_required
def calendar_view(request):
    is_client = request.user.userType == "Cliente"
    staff_users = [] if is_client else _calendar_staff_users(request.user.department)
    locations = Location.objects.all().order_by('order', 'name')
    return render(request, "intranet/calendar.html", {
        'staff_users': staff_users,
        'current_year': date.today().year,
        'locations': locations,
        'is_client': is_client,
    })


@login_required
@csrf_exempt
def update_calendar_visibility(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    visible_ids = set(int(i) for i in data.get('visible_ids', []))
    staff = _calendar_staff_users(request.user.department)
    for u in staff:
        new_val = u.id in visible_ids
        if u.show_in_calendar != new_val:
            u.show_in_calendar = new_val
            u.save(update_fields=['show_in_calendar'])
    return JsonResponse({'ok': True})


def create_weekend_holidays(start_date, end_date):
    """
    Creates the weekend holidays events
    """
    current = start_date
    while current <= end_date:
        if current.weekday() in (5, 6):  # 5 = saturday, 6 = sunday
            Holidays.objects.get_or_create(
                date_from=current,
                date_to=current,
                type_holidays="Fin de semana",
                defaults={
                    "workable": False,
                    "working_user": None
                }
            )
        current += timedelta(days=1)


@login_required
@csrf_exempt
def json_holidays(request):
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if start_str and end_str:
        # FullCalendar may pass ISO strings with timezone offset; strip the time part
        start_date = datetime.fromisoformat(start_str[:10]).date()
        end_date = datetime.fromisoformat(end_str[:10]).date()
        holiday_qs = Holidays.objects.filter(date_from__lte=end_date, date_to__gte=start_date)
        absence_qs = Absence.objects.filter(
            date_from__lte=end_date, date_to__gte=start_date
        ).select_related('absence_user')
    else:
        holiday_qs = Holidays.objects.all()
        absence_qs = Absence.objects.all().select_related('absence_user')

    data = []

    for event in holiday_qs:
        color = _HOLIDAY_COLORS.get(event.type_holidays, '#E74C3C')
        title = event.name or event.type_holidays
        if event.workable and event.working_user:
            title = f"{title} ({event.working_user.username})"
        # FullCalendar allDay end is exclusive: add 1 day
        end_date_fc = (event.date_to + timedelta(days=1)).isoformat()
        data.append({
            'id': f'h_{event.id}',
            'title': title,
            'start': event.date_from.isoformat(),
            'end': end_date_fc,
            'allDay': True,
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'eventType': 'holiday',
                'type_holidays': event.type_holidays,
                'workable': event.workable,
                'work_level': event.work_level,
                'min_workers': event.min_workers,
            },
        })

    for event in absence_qs:
        color = _ABSENCE_COLORS.get(event.type_absence, '#00aae4')
        user_name = ''
        if event.absence_user:
            user_name = event.absence_user.get_full_name() or event.absence_user.username
        title = f"{user_name}: {event.type_absence}" if user_name else event.type_absence
        end_date_fc = (event.date_to + timedelta(days=1)).isoformat()
        data.append({
            'id': f'a_{event.id}',
            'title': title,
            'start': event.date_from.isoformat(),
            'end': end_date_fc,
            'allDay': True,
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'eventType': 'absence',
                'type_absence': event.type_absence,
                'user_id': event.absence_user_id,
                'user_name': user_name,
            },
        })

    return JsonResponse(data, safe=False)


@login_required
@csrf_exempt
def create_holiday(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    date_from = date.fromisoformat(data['date_from'])
    date_to = date.fromisoformat(data.get('date_to') or data['date_from'])
    working_user = None
    if data.get('working_user_id'):
        working_user = User.objects.filter(pk=data['working_user_id']).first()
    h = Holidays.objects.create(
        name=data.get('name', ''),
        type_holidays=data.get('type_holidays', 'Feriado'),
        date_from=date_from,
        date_to=date_to,
        workable=data.get('workable', False),
        working_user=working_user,
        work_level=data.get('work_level', 'none'),
        min_workers=data.get('min_workers') or None,
    )
    return JsonResponse({'id': h.id, 'success': True})


@login_required
@csrf_exempt
def edit_holiday(request, holiday_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        h = Holidays.objects.get(pk=holiday_id)
    except Holidays.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    old_from = h.date_from
    old_to   = h.date_to
    update_fields = []
    if 'min_workers' in data:
        val = data['min_workers']
        h.min_workers = int(val) if val else None
        update_fields.append('min_workers')
    if 'name' in data:
        h.name = data['name'] or None
        update_fields.append('name')
    if 'work_level' in data:
        h.work_level = data['work_level']
        update_fields.append('work_level')
    if 'date_from' in data:
        h.date_from = data['date_from']
        update_fields.append('date_from')
    if 'date_to' in data:
        h.date_to = data['date_to']
        update_fields.append('date_to')
    if update_fields:
        h.save(update_fields=update_fields)
    # If dates changed, shift associated Feriado trabajado absences
    if 'date_from' in data or 'date_to' in data:
        Absence.objects.filter(
            type_absence__in=['Feriado trabajado', 'Feriado trabajado 1/2'],
            date_from=old_from,
            date_to=old_to,
        ).update(date_from=h.date_from, date_to=h.date_to)
    return JsonResponse({'success': True})


@login_required
@csrf_exempt
def delete_holiday(request, holiday_id):
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        Holidays.objects.get(pk=holiday_id).delete()
        return JsonResponse({'success': True})
    except Holidays.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
@csrf_exempt
def create_absence(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    date_from = date.fromisoformat(data['date_from'])
    date_to = date.fromisoformat(data.get('date_to') or data['date_from'])
    absence_user = None
    if data.get('absence_user_id'):
        absence_user = User.objects.filter(pk=data['absence_user_id']).first()
    a = Absence.objects.create(
        type_absence=data.get('type_absence', 'Vacaciones'),
        date_from=date_from,
        date_to=date_to,
        absence_user=absence_user,
    )
    return JsonResponse({'id': a.id, 'success': True})


@login_required
@csrf_exempt
def delete_absence(request, absence_id):
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        Absence.objects.get(pk=absence_id).delete()
        return JsonResponse({'success': True})
    except Absence.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ── External Calendar ──────────────────────────────────────────────────────────

@login_required
def json_external_calendar(request):
    start_str = request.GET.get('start')
    end_str   = request.GET.get('end')
    if start_str and end_str:
        start_date = datetime.fromisoformat(start_str[:10]).date()
        end_date   = datetime.fromisoformat(end_str[:10]).date()
        qs = ExternalCalendarEntry.objects.filter(
            date_from__lte=end_date, date_to__gte=start_date
        ).select_related('location')
        holiday_qs = Holidays.objects.filter(
            date_from__lte=end_date, date_to__gte=start_date,
            type_holidays='Feriado',
        )
    else:
        qs = ExternalCalendarEntry.objects.all().select_related('location')
        holiday_qs = Holidays.objects.filter(
            type_holidays='Feriado',
        )

    CATEGORY_COLORS = {
        'holiday':         '#87CEEB',
        'long_weekend':    '#FFD700',
        'other':           '#C8E6C9',
        'full_moon':       '#E1D5F7',
        'not_recommended': '#FFAB91',
    }
    events = []
    for e in qs:
        end = e.date_to + timedelta(days=1)
        events.append({
            'id':              f'ext_{e.id}',
            'title':           e.name or e.get_category_display(),
            'start':           str(e.date_from),
            'end':             str(end),
            'backgroundColor': CATEGORY_COLORS.get(e.category, '#ccc'),
            'extendedProps': {
                'category':    e.category,
                'location_id': e.location_id,
                'name':        e.name,
                'notes':       e.notes,
                'source':      'external',
                'entry_id':    e.id,
            },
        })
    # Internal holidays appear in all location rows (read-only)
    for h in holiday_qs:
        end = h.date_to + timedelta(days=1)
        events.append({
            'id':              f'hol_{h.id}',
            'title':           h.name or h.type_holidays,
            'start':           str(h.date_from),
            'end':             str(end),
            'backgroundColor': '#87CEEB',
            'extendedProps': {
                'category':    'holiday',
                'location_id': None,
                'name':        h.name or h.type_holidays,
                'source':      'internal',
                'entry_id':    None,
            },
        })
    return JsonResponse(events, safe=False)


@login_required
@csrf_exempt
def create_external_entry(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    loc_id = data.get('location_id') or None
    entry = ExternalCalendarEntry.objects.create(
        date_from=data['date_from'],
        date_to=data['date_to'],
        name=data.get('name', ''),
        notes=data.get('notes', ''),
        category=data.get('category', 'holiday'),
        location_id=loc_id,
    )
    return JsonResponse({'id': entry.id, 'success': True})


@login_required
@csrf_exempt
def edit_external_entry(request, entry_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        entry = ExternalCalendarEntry.objects.get(pk=entry_id)
    except ExternalCalendarEntry.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    entry.date_from   = data.get('date_from', entry.date_from)
    entry.date_to     = data.get('date_to', entry.date_to)
    entry.name        = data.get('name', entry.name)
    entry.notes       = data.get('notes', entry.notes)
    entry.category    = data.get('category', entry.category)
    entry.location_id = data.get('location_id') or None
    entry.save()
    return JsonResponse({'success': True})


@login_required
@csrf_exempt
def delete_external_entry(request, entry_id):
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        ExternalCalendarEntry.objects.get(pk=entry_id).delete()
        return JsonResponse({'success': True})
    except ExternalCalendarEntry.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


def _calculate_full_moons(year):
    """
    Full moon dates for a year via the synodic period (29.53059 days).
    Reference: Jan 21, 2000 04:40 UTC. Dates resolved in Argentina time (UTC-3).
    """
    from datetime import timezone
    KNOWN_UTC = datetime(2000, 1, 21, 4, 40, tzinfo=timezone.utc)
    SYNODIC   = 29.53058867
    ARG       = timedelta(hours=-3)
    k = math.ceil((datetime(year, 1, 1, tzinfo=timezone.utc) - KNOWN_UTC).total_seconds() / (SYNODIC * 86400))
    results = []
    while True:
        moment_arg = KNOWN_UTC + timedelta(days=k * SYNODIC) + ARG
        d = moment_arg.date()
        if d.year > year:
            break
        if d.year == year:
            results.append(d)
        k += 1
    return results


@login_required
@csrf_exempt
def import_long_weekends(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    year = int(data.get('year', date.today().year))

    # Get all Feriados for the year
    feriados = Holidays.objects.filter(
        type_holidays='Feriado',
        date_from__year=year,
    )

    # Existing long_weekend entries for the year (by date_from)
    existing = set(
        ExternalCalendarEntry.objects.filter(
            category='long_weekend',
            date_from__year=year,
        ).values_list('date_from', flat=True)
    )

    created = 0
    for h in feriados:
        saturday = sunday = None
        # Check first day: Friday → weekend after
        if h.date_from.weekday() == 4:
            saturday = h.date_from + timedelta(days=1)
            sunday   = h.date_from + timedelta(days=2)
        # Check last day: Monday → weekend before
        elif h.date_to.weekday() == 0:
            saturday = h.date_to - timedelta(days=2)
            sunday   = h.date_to - timedelta(days=1)

        if saturday and saturday not in existing:
            name = f'Long Weekend — {h.name or h.type_holidays}'
            ExternalCalendarEntry.objects.create(
                date_from=saturday, date_to=sunday,
                name=name, category='long_weekend', location=None,
            )
            existing.add(saturday)
            created += 1

    return JsonResponse({'created': created, 'year': year})


@login_required
@csrf_exempt
def import_full_moons(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    year = int(data.get('year', date.today().year))

    full_moon_dates = _calculate_full_moons(year)

    ExternalCalendarEntry.objects.filter(category='full_moon', date_from__year=year).delete()

    for d in full_moon_dates:
        ExternalCalendarEntry.objects.create(
            date_from=d, date_to=d,
            name='Full Moon', category='full_moon', location=None,
        )

    return JsonResponse({'created': len(full_moon_dates), 'total': len(full_moon_dates), 'year': year})


@login_required
@csrf_exempt
def copy_special_entries(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    source_year = int(data.get('source_year'))
    target_year = int(data.get('target_year'))

    source_entries = ExternalCalendarEntry.objects.select_related('location').filter(
        category__in=['other', 'not_recommended'],
        date_from__year=source_year,
    )

    existing = set(
        (e.name, e.category, e.location_id, e.date_from.month, e.date_from.day)
        for e in ExternalCalendarEntry.objects.filter(
            category__in=['other', 'not_recommended'],
            date_from__year=target_year,
        )
    )

    def _shift(d):
        try:
            return d.replace(year=target_year)
        except ValueError:
            return d.replace(year=target_year, day=28)

    created = 0
    for entry in source_entries:
        key = (entry.name, entry.category, entry.location_id, entry.date_from.month, entry.date_from.day)
        if key in existing:
            continue
        ExternalCalendarEntry.objects.create(
            date_from=_shift(entry.date_from),
            date_to=_shift(entry.date_to),
            name=entry.name,
            category=entry.category,
            location=entry.location,
            notes=entry.notes,
        )
        existing.add(key)
        created += 1

    return JsonResponse({'created': created, 'source_year': source_year, 'target_year': target_year})


@login_required
@csrf_exempt
def jsontrips(_request):

    # Get the list of the trips
    trips = list(Trip.objects.values())

    return JsonResponse(trips, safe=False)


@login_required
@csrf_exempt
def jsontrip(request, trip_id):

    # Query for trip
    try:
        trip_object = Trip.objects.get(pk=trip_id)
        trip = model_to_dict(trip_object)
    except Trip.DoesNotExist:
        return JsonResponse({"error": "Viaje no encontrado"}, status=404)

    # Return trip contents
    if request.method == "GET":
        return JsonResponse(trip, safe=False)

    # Update trip
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the trip
        trip_object.name = data["name"]

        # Save the changes of the trip
        trip_object.save()
        return HttpResponse(status=204)

    # Deletes the trip
    elif request.method == "DELETE":
        trip_object.delete()
        return HttpResponse(status=204)

    # Trip requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


@login_required
@csrf_exempt
def json_entries(request):

    # Get the list of the entries
    entries_object_list = []
    trip_entries = Trip.objects.filter(department=request.user.department)

    for entry in Entry.objects.all():
        if entry.trip in trip_entries:
            entries_object_list.append(entry)

    #entries_object_list = Entry.objects.filter(department=request.user.department)
    entries = [entry.serialize() for entry in entries_object_list]

    return JsonResponse(entries, safe=False)


@login_required
def entry_tp_lookup(request):
    """
    Queries the Tourplan DB for a single booking by tourplanId,
    updates the related Trip, and returns the amount + key fields as JSON.
    """
    if not TOURPLAN_ENABLED:
        return JsonResponse({"error": "Conexión a Tourplan deshabilitada temporalmente"}, status=503)

    tp_id = request.GET.get("tp_id", "").strip()
    if not tp_id:
        return JsonResponse({"error": "tp_id requerido"}, status=400)

    from intranet.utils import get_tourplan_connection, _BOOKING_STATUSES, _CANCELLED_STATUSES

    SINGLE_BOOKING_QUERY = """
        SELECT
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
                      AND OPT.SERVICE = 'GU' AND OPT.LOCATION = 'BUE'
                    GROUP BY CRM.NAME
                    FOR XML PATH ('')
                ), 1, 1, '')
            ))), '') AS guide,
            CASE BHD.STATUS WHEN 'HL' THEN 0 WHEN 'XC' THEN 0 WHEN 'XX' THEN 0
                ELSE BSD.PAX END AS num_pax,
            CASE BHD.STATUS WHEN 'HL' THEN 0
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
        WHERE BHD.FULL_REFERENCE = %s
    """

    try:
        conn = get_tourplan_connection()
        try:
            cur = conn.cursor()
            cur.execute(SINGLE_BOOKING_QUERY, (tp_id,))
            row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        return JsonResponse({"error": f"Error conectando a Tourplan: {e}"}, status=500)

    if not row:
        return JsonResponse({"error": f"Código {tp_id} no encontrado en Tourplan"}, status=404)

    # Update the related Trip in the app (same logic as sync_from_tourplan_db)
    trip = Trip.objects.filter(tourplanId=tp_id).first()
    if trip:
        users_by_other_tp = {u.other_tp: u for u in User.objects.all() if u.other_tp}
        if row.get("travelling_date"):
            trip.travelling_date = row["travelling_date"]
        if row.get("out_date"):
            trip.out_date = row["out_date"]
        dh_type_val = (row.get("dh_type") or "").strip()
        if dh_type_val in ("S", "B", "F"):
            trip.dh_type = dh_type_val
        resp_code = (row.get("responsable_code") or "").strip()
        if resp_code in users_by_other_tp:
            trip.consultant_tp = users_by_other_tp[resp_code]
        elif resp_code:
            try:
                trip.consultant_tp = User.objects.get(username=resp_code)
            except User.DoesNotExist:
                pass
        ops_code = (row.get("operations_code") or "").strip()
        if ops_code in users_by_other_tp:
            trip.operations_user = users_by_other_tp[ops_code]
        elif ops_code:
            try:
                trip.operations_user = User.objects.get(username=ops_code)
            except User.DoesNotExist:
                pass
        dh_name_val = (row.get("dh_name") or "").strip()
        if dh_name_val.upper().startswith("DH "):
            dh_name_val = dh_name_val[3:].strip()
        trip.dh = dh_name_val
        trip.guide    = (row.get("guide") or "").strip()
        from intranet.utils import strip_html
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
        trip.save()

    amount = row.get("amount")
    try:
        amount = round(float(amount)) if amount else None
    except (ValueError, TypeError):
        amount = None

    td = row.get("travelling_date")
    od = row.get("out_date")
    raw_status = (row.get("status") or "").strip()
    if raw_status in _BOOKING_STATUSES:
        app_status = "Booking"
    elif raw_status in _CANCELLED_STATUSES:
        app_status = "Cancelado"
    else:
        app_status = "Quote"

    return JsonResponse({
        "amount":          amount,
        "status":          app_status,
        "travelling_date": td.strftime("%d/%m/%Y") if td else "",
        "out_date":        od.strftime("%d/%m/%Y") if od else "",
        "pax_name":        (row.get("pax_name") or "").strip(),
        "guide":           (row.get("guide") or "").strip(),
    })


@login_required
@csrf_exempt
def json_entry(request, entry_id):

    # Query for entry
    try:
        entry_object = Entry.objects.get(pk=entry_id)
        entry = model_to_dict(entry_object)
    except Entry.DoesNotExist:
        return JsonResponse({"error": "Entry not found"}, status=404)

    # Return entry contents
    if request.method == "GET":
        return JsonResponse(entry, safe=False)

    # Update entry
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the entry
        entry_object.version = data["version"]

        # Save the changes of the entry
        entry_object.save()
        return HttpResponse(status=204)

    # Deletes the entry
    elif request.method == "DELETE":
        entry_object.delete()
        return HttpResponse(status=204)

    # Entry requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


@login_required
@csrf_exempt
def json_last_entry(request):

    # Get the last user entry
    entry = Entry.objects.filter(creation_user=request.user).first()
    return JsonResponse(entry.serialize(), safe=False)


@login_required
@csrf_exempt
def jsontrip_entries(request, trip_id):

    # Query for entries for the trip
    try:
        trip_object = Trip.objects.get(pk=trip_id)
        entries_object_list = Entry.objects.filter(trip=trip_object)
        if not entries_object_list:
            return JsonResponse({"empty": "No entries"})

    except Trip.DoesNotExist:
        return JsonResponse({"error": "Trip not found"}, status=404)


    # Return entries contents
    if request.method == "GET":
        return JsonResponse([entry.serialize() for entry in entries_object_list], safe=False)

    # Entry requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET request required."
        }, status=400)


@login_required
@csrf_exempt
def jsontrip_notes(request, trip_id):

    # Query for entries for the trip
    try:
        trip_object = Trip.objects.get(pk=trip_id)
        notes_object_list = Notes.objects.filter(trip=trip_object)
        if not notes_object_list:
            return JsonResponse({"empty": "No notes"})

    except Trip.DoesNotExist:
        return JsonResponse({"error": "Trip not found"}, status=404)


    # Return entries contents
    if request.method == "GET":
        return JsonResponse([note.serialize() for note in notes_object_list], safe=False)

    # Entry requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET request required."
        }, status=400)


@login_required
@csrf_exempt
def jsoncountry(request, country_id):

    # Query for country
    try:
        country_object = Country.objects.get(pk=country_id)
        country = model_to_dict(country_object)
    except Country.DoesNotExist:
        return JsonResponse({"error": "Country not found"}, status=404)

    # Return country contents
    if request.method == "GET":
        return JsonResponse(country, safe=False)

    # Update country
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body.decode('utf-8'))

        # Update information of the country
        if data.get("name") is not None:
            country_object.name = data["name"]
        if data.get("code") is not None:
            if len(data["code"]) != 2:
                return JsonResponse({
                    "error": "Code should have a lenght of 2."
                }, status=400)
            else:
                country_object.code = data["code"]


        # Save the changes of the country
        country_object.save()
        return HttpResponse(status=204)

    # Deletes the country
    elif request.method == "DELETE":
        country_object.delete()
        return HttpResponse(status=204)

    # Country requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)

@login_required
@csrf_exempt
def json_countries(_request):

    # Get the list of the countries
    countries = list(Country.objects.values())

    return JsonResponse(countries, safe=False)

@login_required
@csrf_exempt
def jsonclient(request, client_id):

    # Query for client
    try:
        client_object = Client.objects.get(pk=client_id)
        # client = model_to_dict(client_object)
    except Client.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)

    # Return client contents
    if request.method == "GET":
        return JsonResponse(client_object.serialize(), safe=False)

    # Update client
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the client
        if data.get("name") is not None:
            client_object.name = data["name"]
        if data.get("isActivated") is not None:
            client_object.isActivated = data["isActivated"]
        if data.get("country") is not None:
            country_object = Country.objects.get(pk=int(data["country"]))
            client_object.country = country_object
        if data.get("department") is not None:
            client_object.department = data["department"]
        if data.get("category") is not None:
            client_object.category = data["category"]

        # Save the changes of the client
        client_object.save()
        return HttpResponse(status=204)

    # Deletes the client
    elif request.method == "DELETE":
        client_object.delete()
        return HttpResponse(status=204)

    # Client requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)

@login_required
@csrf_exempt
def json_clients(_request):

    # Get the list of the clients
    clients_object_list = Client.objects.all()
    clients = [client.serialize() for client in clients_object_list]

    return JsonResponse(clients, safe=False)

@login_required
@csrf_exempt
def jsoncontact(request, contact_id):
    # Query for contact
    try:
        contact_object = ClientContact.objects.get(pk=contact_id)
        contact = model_to_dict(contact_object)
    except ClientContact.DoesNotExist:
        return JsonResponse({"error": "Contact not found"}, status=404)

    # Return contact contents
    if request.method == "GET":
        return JsonResponse(contact, safe=False)

    # Update contact
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the contact
        if data.get("name") is not None:
            contact_object.name = data["name"]
        if data.get("client") is not None:
            client_object = Client.objects.get(pk=int(data["client"]))
            contact_object.client = client_object
        if data.get("email") is not None:
            contact_object.email = data["email"]
        if data.get("isActivated") is not None:
            contact_object.isActivated = data["isActivated"]

        # Save the changes of the contact
        contact_object.save()
        return HttpResponse(status=204)

    # Deletes the contact
    elif request.method == "DELETE":
        contact_object.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)

@login_required
@csrf_exempt
def json_contacts(request):
    client_id = request.GET.get('client_id')
    qs = ClientContact.objects.all()
    if client_id:
        qs = qs.filter(client_id=client_id)
    contacts = list(qs.values('id', 'name', 'email', 'client_id'))
    data = {'contacts': contacts}
    return JsonResponse(data)

@login_required
@csrf_exempt
def jsonuser(request, user_id):
    # Query for user
    try:
        user_object = User.objects.get(pk=user_id)
        user = model_to_dict(user_object)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    # Return user contents
    if request.method == "GET":
        return JsonResponse(user, safe=False)

    # Update user
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the user
        user_object.username = data["username"]
        user_object.other_name = data["other_name"]


        # Save the changes of the user
        user_object.save()
        return HttpResponse(status=204)

    # Deletes the user
    elif request.method == "DELETE":
        user_object.delete()
        return HttpResponse(status=204)

    # User requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


@login_required
@csrf_exempt
def json_users(_request):

    # Get the list of the users
    users = list(User.objects.values())
    data = {'users': users}
    return JsonResponse(data)

def get_pendings(department):

    # Empty list for the table
    data = []

    # Empty list for labels (each row)
    labels = []

    # Create the columns and add to the table
    columns = ["Nombre", "Quote", "Booking", "Final Itinerary", "Otro"]
    data.append(columns)

    # Filter only the entries that are not closed (pending)
    pendings = Entry.objects.filter(isClosed=False)

    # Add only the labels once and the ones in the department of the user
    for entry in pendings:
        if entry.user_working.username not in labels and entry.trip.department == department:
            labels.append(entry.user_working.username)

    row = []

    for label in range(len(labels)):
        for column in range(len(columns)):
            row.append(0)
        data.append(row)
        row = []

    # Create the first row data with the labels
    row_num = 0
    for row in data:
        if row_num != 0:
            num = 0
            for i in row:
                if num == 0:
                    row[num] = labels[row_num-1]
                num+=1
        row_num+=1

    # Fill the information for each label (user)
    for entry in pendings:
        for row in data:
            if row[0] == entry.user_working.username:
                if entry.status == "Quote":
                    row[1]+=1
                elif entry.status == "Booking":
                    row[2]+=1
                elif entry.status == "Final Itinerary":
                    row[3]+=1
                else:
                    row[4]+=1
    return data

@login_required
@csrf_exempt
def json_pendings(request):
    data = get_pendings(request.user.department)

    return JsonResponse(data, safe=False)

_PROGRESS_DATA = [
    ("0 - No comenzado",                     "0 - Not started yet",         "#9ca3af", "#fff"),
    ("1 - Analizado",                         "1 - Analysed",                "#60a5fa", "#fff"),
    ("2 - Contactados proveedores",           "2 - Suppliers contacted",     "#3b82f6", "#fff"),
    ("3 - Enviado Status",                    "3 - Status sent",             "#f59e0b", "#fff"),
    ("4 - Falta respuesta proveedor/cliente", "4 - Awaiting response",       "#f97316", "#fff"),
    ("5 - Finalizado",                        "5 - Finalised",               "#22c55e", "#fff"),
]
_PROGRESS_OPTIONS  = [d[0] for d in _PROGRESS_DATA]
_PROGRESS_LABELS_EN = {d[0]: (d[1], d[2], d[3]) for d in _PROGRESS_DATA}

_PILL_BASE  = "padding:2px 10px;border-radius:999px;font-size:.82em;white-space:nowrap;"
_PILL_OPT   = _PILL_BASE + "cursor:pointer;display:block;margin-bottom:4px;"
_DROP_STYLE = ("display:none;position:absolute;z-index:1050;background:#fff;"
               "border:1px solid #dee2e6;border-radius:8px;padding:8px;"
               "box-shadow:0 4px 16px rgba(0,0,0,.18);min-width:220px;"
               "top:calc(100% + 4px);left:0;")


def _progress_label_en(current):
    entry = _PROGRESS_LABELS_EN.get(current)
    if entry:
        label, bg, color = entry
    else:
        label, bg, color = (current or "—", "#9ca3af", "#fff")
    return (
        f'<span style="background:{bg};color:{color};{_PILL_BASE}">{label}</span>'
    )


def _progress_select_html(entry_id, current):
    cur = _PROGRESS_LABELS_EN.get(current)
    if cur:
        cur_label, cur_bg, cur_fg = cur
    else:
        cur_label, cur_bg, cur_fg = (current or "—", "#9ca3af", "#fff")

    opts = "".join(
        f'<span class="progress-pill-option" data-value="{val}" data-bg="{bg}" data-fg="{fg}" '
        f'style="background:{bg};color:{fg};{_PILL_OPT}">{label}</span>'
        for val, label, bg, fg in _PROGRESS_DATA
    )
    return (
        f'<div class="progress-pill-widget" data-entry-id="{entry_id}" '
        f'style="position:relative;display:inline-block;">'
        f'<span class="progress-pill-display" '
        f'style="background:{cur_bg};color:{cur_fg};{_PILL_BASE}cursor:pointer;user-select:none;">'
        f'{cur_label}</span>'
        f'<div class="progress-pill-dropdown" style="{_DROP_STYLE}">{opts}</div>'
        f'</div>'
    )


@login_required
@csrf_exempt
def update_entry_progress(request, entry_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    data = json.loads(request.body)
    progress = data.get('progress', '')
    try:
        entry = Entry.objects.get(pk=entry_id, trip__department=request.user.department)
        entry.progress = progress
        entry.save(update_fields=['progress'])
        return JsonResponse({'success': True})
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)


@login_required
@csrf_exempt
def client_entry_inquiry(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    if request.user.userType != 'Cliente':
        return JsonResponse({'error': 'forbidden'}, status=403)
    data = json.loads(request.body)
    entry_id = data.get('entry_id')
    message = data.get('message', '').strip()
    try:
        entry = Entry.objects.select_related('trip', 'trip__client', 'user_working').get(
            pk=entry_id, trip__department=request.user.department
        )
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)

    client_ref = entry.trip.client_reference or '—'
    trip_display = f"{entry.trip.name} x {entry.trip.quantity_pax}" if entry.trip else '—'
    status_label = f"{entry.status} {entry.version_quote if entry.status == 'Quote' else entry.version}".strip()
    subject = f"Consulta de cliente desde Intranet - Ref: {client_ref} - Viaje: {trip_display}"

    uw = entry.user_working
    uw_name = (uw.other_name or uw.username) if uw else '—'
    if uw and uw.color:
        color = str(uw.color)
        try:
            h = color.lstrip('#')
            r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
            text = '#333333' if (0.2126*r + 0.7152*g + 0.0722*b) > 0.45 else '#ffffff'
        except (ValueError, TypeError):
            text = '#333333'
        uw_pill = (f'<span style="background-color:{color};color:{text};'
                   f'padding:2px 10px;border-radius:999px;font-size:.85em;">'
                   f'{uw_name}</span>')
    else:
        uw_pill = uw_name

    html_body = (
        f"<p><strong>Client:</strong> {request.user.other_name or request.user.username}</p>"
        f"<p><strong>Reference:</strong> {client_ref}</p>"
        f"<p><strong>Trip:</strong> {trip_display}</p>"
        f"<p><strong>Entry status:</strong> {status_label}</p>"
        f"<p><strong>Working:</strong> {uw_pill}</p>"
        f"<hr><p>{message}</p>"
    )
    from intranet.utils import send_templated_email
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as _settings
    msg = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=_settings.DEFAULT_FROM_EMAIL,
        to=['quote@aliwenincoming.com.ar'],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send()
    return JsonResponse({'success': True})


@login_required
@csrf_exempt
def entries_data(request):
    # Columnas en el mismo orden que tu tabla HTML
    columns = [
        "starting_date",
        "closing_date",
        "trip__name",
        "trip__trip_type",
        "status",
        "amount",
        "trip__client__name",
        "trip__contact__name",
        "trip__client_reference",
        "user_creator__username",
        "user_working__username",
        "progress",
        "importance",
        "difficulty",
        "note",
        "trip__travelling_date",
        "id"  # para acciones
    ]

    # Parámetros DataTables
    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    search_value = request.GET.get("search[value]", "")
    show_all = request.GET.get("show_all", "0")
    user_filter = request.GET.get("user_filter", "").strip()  # username (pendings UI select)
    user_other_name_filter = request.GET.get("user_other_name_filter", "").strip()  # other_name (stats drill-down)
    client_filter_param = request.GET.get("client_filter", "").strip()  # stats drill-down
    status_filter_param = request.GET.get("status_filter", "").strip()  # stats drill-down (Quote/Booking/Final)
    date_from_param = request.GET.get("date_from", "").strip()
    date_to_param   = request.GET.get("date_to", "").strip()
    month_param     = request.GET.get("month", "").strip()
    year_param      = request.GET.get("year", "").strip()
    week_param      = request.GET.get("week", "").strip()
    season_param    = request.GET.get("season", "").strip()

    order_col_index = int(request.GET.get("order[0][column]", 0))
    order_dir = request.GET.get("order[0][dir]", "asc")
    order_col = columns[order_col_index]
    if order_dir == "desc":
        order_col = f"-{order_col}"

    # 🚩 Filtrar solo entradas del mismo departamento que el usuario
    qs = Entry.objects.select_related(
        "trip", "user_creator", "user_working", "trip__client", "trip__contact", "revising_user"
    ).filter(
        trip__department=request.user.department
    )

    # 🚩 Solo entradas abiertas (isClosed == False) si no se pidió show_all
    if show_all != "1":
        qs = qs.filter(isClosed=False)

    # filtro de usuario por username (selector de pendings)
    if user_filter != "":
        qs = qs.filter(user_working__username=user_filter)

    # filtro de usuario por other_name (drill-down desde estadísticas)
    if user_other_name_filter:
        qs = qs.filter(user_working__other_name=user_other_name_filter)

    # filtro de cliente (drill-down desde estadísticas)
    if client_filter_param:
        qs = qs.filter(trip__client__name=client_filter_param)

    # filtro de status (drill-down desde estadísticas: Quote / Booking / Final)
    if status_filter_param:
        qs = qs.filter(status=status_filter_param)

    # filtros de fecha (drill-down desde estadísticas)
    if month_param and year_param:
        qs = qs.filter(starting_date__month=month_param, starting_date__year=year_param)
    if week_param:
        _today = date.today()
        _this_week = _today.isocalendar()[1]
        _week_year = _today.year - 1 if int(week_param) > _this_week else _today.year
        _wdf = date.fromisocalendar(_week_year, int(week_param), 1)
        _wdt = date.fromisocalendar(_week_year, int(week_param), 7)
        qs = qs.filter(starting_date__date__range=[_wdf, _wdt])
    if season_param:
        _s = int(season_param)
        qs = qs.filter(starting_date__date__range=[date(_s, 5, 1), date(_s + 1, 4, 30)])
    if date_from_param and date_to_param:
        qs = qs.filter(starting_date__date__range=[date_from_param, date_to_param])

    # Búsqueda global
    if search_value:
        qs = qs.filter(
            Q(trip__name__icontains=search_value) |
            Q(status__icontains=search_value) |
            Q(user_creator__username__icontains=search_value) |
            Q(user_working__username__icontains=search_value) |
            Q(trip__client__name__icontains=search_value) |
            Q(trip__contact__name__icontains=search_value) |
            Q(progress__icontains=search_value) |
            Q(importance__icontains=search_value) |
            Q(note__icontains=search_value)
        )

    if request.user.userType == "Cliente":
        try:
            client_obj = Client.objects.get(name=request.user.other_name)
            qs = qs.filter(trip__client=client_obj)
        except Client.DoesNotExist:
            return HttpResponseRedirect(reverse("index"))

    total_records = Entry.objects.filter(trip__department=request.user.department).count()
    filtered_records = qs.count()

    # Orden + paginación
    qs = qs.order_by(order_col)
    paginator = Paginator(qs, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    def _user_pill(user):
        if not user:
            return ""
        color = str(user.color) if user.color else "#999999"
        try:
            h = color.lstrip('#')
            r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
            text = '#333333' if (0.2126*r + 0.7152*g + 0.0722*b) > 0.45 else '#ffffff'
        except (ValueError, TypeError):
            text = '#333333'
        return (f'<span style="background-color:{color};color:{text};'
                f'padding:2px 10px;border-radius:999px;font-size:.85em;">'
                f'{user.username}</span>')

    # Preparar datos
    data = []
    for entry in page_obj:

        trip_name = f"{entry.trip.name if entry.trip else ''} x {entry.trip.quantity_pax}"

        is_client_user = request.user.userType == "Cliente"

        # status con versión
        status_raw = entry.status
        version_str = (entry.version_quote if status_raw == 'Quote' else entry.version) or ''
        status = f"{status_raw} {version_str}".strip()

        _status_colors = {
            'Quote':   ('#3b82f6', '#fff'),
            'Booking': ('#22c55e', '#fff'),
            'Final':   ('#f97316', '#fff'),
            'Queja':   ('#ef4444', '#fff'),
        }
        _bg, _fg = _status_colors.get(status_raw, ('#6b7280', '#fff'))
        status_label = ('Complaint' if status_raw == 'Queja' else status) if is_client_user else status
        status_display = (
            f'<span style="background:{_bg};color:{_fg};padding:2px 10px;'
            f'border-radius:999px;font-size:.85em;white-space:nowrap;">{status_label}</span>'
        )

        # monto
        if entry.amount:
            amount = f"USD {entry.amount}"
        elif is_client_user:
            amount = "<span class='text-muted small fst-italic'>Not available yet</span>"
        else:
            amount = "Pendiente"

        # fechas
        if is_client_user:
            starting_date = localtime(entry.starting_date).strftime("%d %b %Y")
            closing_date = localtime(entry.closing_date).strftime("%d %b %Y") if entry.isClosed else "—"
            travelling_date = entry.trip.travelling_date.strftime("%d %b %Y") if entry.trip and entry.trip.travelling_date else "—"
        else:
            starting_date = localtime(entry.starting_date).strftime("%Y/%m/%d %H:%M")
            closing_date = localtime(entry.closing_date).strftime("%Y/%m/%d %H:%M") if entry.isClosed else f"<div class='bg-{entry.timingStatus}'>n/a</div>"
            travelling_date = entry.trip.travelling_date.strftime("%Y/%m/%d") if entry.trip and entry.trip.travelling_date else ""

        if is_client_user:
            client_ref = entry.trip.client_reference if entry.trip else ""
            trip_display = f"{entry.trip.name if entry.trip else ''} x {entry.trip.quantity_pax}"
            acciones_html = (
                f'<div class="text-center">'
                f'<button class="btn btn-sm btn-outline-secondary client-entry-email-btn" '
                f'data-entry-id="{entry.id}" '
                f'data-ref="{client_ref}" '
                f'data-trip="{trip_display}" '
                f'data-status="{status_label}" '
                f'title="Send an email about this {status_label.lower()}">'
                f'<i class="fa-solid fa-envelope"></i>'
                f'</button></div>'
            )
        else:
            # acciones con modal
            acciones_html = f"""
                <div class="d-flex justify-content-around p-2">
                    <a id="pencil-edit-entry" href="/modify_entry/{entry.id}"><i class="fa-solid fa-pencil align-top" id="pencil-entries-{entry.id}"></i></a>
                    <i class="fa-solid fa-trash" data-bs-toggle="modal" data-bs-target="#deleteModal{entry.id}"></i>
                </div>

                <!-- Modal de eliminación -->
                    <div class="modal fade modal-lg" id="deleteModal{entry.id}" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h1 class="modal-title fs-8">Eliminar {status} de {entry.trip.name}</h1>
                                    <!-- Botón cerrar con id único -->
                                    <button id="btn-close-entries-{entry.id}" type="button"
                                            class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body text-center">
                                    <h3>¿Está seguro que desea eliminar la entrada?</h3>
                                    <!-- Botón eliminar con data-id -->
                                    <button class="btn btn-dark btn-lg delete-entries-btn"
                                            id="delete-entry-{entry.id}">
                                        ELIMINAR
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
            """

        if is_client_user:
            progress_display = _progress_label_en(entry.progress)
        else:
            progress_display = _progress_select_html(entry.id, entry.progress)

        # Revision column (non-client only)
        if is_client_user:
            revision_html = ""
        elif entry.is_revised:
            revision_html = '<span style="color:#16a34a;font-size:1.1em;" title="Revisado">✓</span>'
        elif entry.revision_link:
            if entry.revising_user:
                revision_html = (
                    f'<button class="btn btn-sm btn-link p-0 revision-user-btn" '
                    f'data-entry-id="{entry.id}" data-user-id="{entry.revising_user.id}" '
                    f'title="Revisor: {entry.revising_user.username} – click para cambiar">'
                    f'{_user_pill(entry.revising_user)}</button>'
                )
            else:
                revision_html = (
                    f'<button class="btn btn-sm btn-link p-0 revision-user-btn" '
                    f'data-entry-id="{entry.id}" data-user-id="" '
                    f'title="Sin revisor asignado – click para asignar">⚠️</button>'
                )
        else:
            trip_label = entry.trip.name if entry.trip else ""
            revision_html = (
                f'<button class="btn btn-sm btn-link p-0 text-muted send-revision-btn" '
                f'data-entry-id="{entry.id}" data-trip="{trip_label}" '
                f'title="Mandar a revisar">—</button>'
            )

        data.append({
            "starting_date": starting_date,
            "closing_date": closing_date,
            "trip": trip_name,
            "type": entry.trip.trip_type,
            "status": status_display,
            "amount": amount,
            "client": entry.trip.client.name if entry.trip and entry.trip.client else "",
            "contact": str(entry.trip.contact) if entry.trip and entry.trip.contact else "",
            "client_reference": entry.trip.client_reference if entry.trip else "",
            "user_creator": _user_pill(entry.user_creator),
            "user_working": _user_pill(entry.user_working),
            "progress": progress_display,
            "importance": entry.importance,
            "difficulty": entry.trip.difficulty,
            "note": entry.note or "n/a",
            "travelling_date": travelling_date,
            "acciones": acciones_html,
            "revision": revision_html,
            "id": entry.id,
        })

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data,
    })

def stats_entries_data(request):
    # columnas en el mismo orden que la tabla HTML
    columns = [
        "starting_date",
        "closing_date",
        "trip__name",
        "status",
        "version",
        "version_quote",
        "amount",
        "trip__client__name",
        "trip__contact__name",
        "user_creator__username",
        "user_working__username",
        "difficulty",
        "trip__travelling_date",
    ]

    # parámetros DataTables
    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    search_value = request.GET.get("search[value]", "")

    # filtros personalizados
    month = request.GET.get("month")
    year = request.GET.get("year")
    week = request.GET.get("week")
    season = request.GET.get("season")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # columna de orden
    order_col_index = min(int(request.GET.get("order[0][column]", 0)), len(columns) - 1)
    order_dir = request.GET.get("order[0][dir]", "asc")
    order_col = columns[order_col_index]
    if order_dir == "desc":
        order_col = f"-{order_col}"

    # queryset base
    qs = Entry.objects.select_related("trip", "user_creator", "user_working", "trip__client", "trip__contact").filter(
        trip__department=request.user.department
    )

    # filtros de fechas
    if month and year:
        qs = qs.filter(starting_date__month=month, starting_date__year=year)

    this_year = date.today().year

    if week:
        this_week = date.today().isocalendar()[1]
        if int(week) > this_week:
            week_year = this_year - 1
        else:
            week_year = this_year

        week_date_from = date.fromisocalendar(week_year, int(week), 1)
        week_date_to = date.fromisocalendar(week_year, int(week), 7)

        qs = qs.filter(starting_date__date__range=[week_date_from, week_date_to])

    if season:
        season_to = int(season) + 1
        season_date_from = date(int(season), 5, 1)
        season_date_to = date(season_to, 4, 30)

        qs = qs.filter(starting_date__date__range=[season_date_from, season_date_to])

    if date_from and date_to:
        qs = qs.filter(starting_date__date__range=[date_from, date_to])

    # filtros drill-down por usuario/cliente
    user_filter = request.GET.get("user_filter")
    client_filter = request.GET.get("client_filter")
    if user_filter:
        qs = qs.filter(user_working__other_name=user_filter)
    if client_filter:
        qs = qs.filter(trip__client__name=client_filter)

    # búsqueda global
    if search_value:
        qs = qs.filter(
            Q(trip__name__icontains=search_value) |
            Q(status__icontains=search_value) |
            Q(user_creator__username__icontains=search_value) |
            Q(user_working__username__icontains=search_value) |
            Q(trip__client__name__icontains=search_value) |
            Q(trip__contact__name__icontains=search_value) |
            Q(progress__icontains=search_value) |
            Q(importance__icontains=search_value)
        )

    total_records = Entry.objects.count()
    filtered_records = qs.count()

    # ordenar + paginar
    qs = qs.order_by(order_col)
    paginator = Paginator(qs, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    # preparar datos
    data = []
    for entry in page_obj:
        status = f"{entry.status} {entry.version_quote if entry.status == 'Quote' else entry.version}"
        amount = f"USD {entry.amount}" if entry.amount else "Pendiente"
        starting_date = localtime(entry.starting_date).strftime("%Y/%m/%d %H:%M")
        closing_date = (
            localtime(entry.closing_date).strftime("%Y/%m/%d %H:%M")
            if entry.isClosed
            else f"<td class='bg-{entry.timingStatus}'>n/a</td>"
        )
        travelling_date = (
            entry.trip.travelling_date.strftime("%Y/%m/%d")
            if entry.trip and entry.trip.travelling_date
            else ""
        )

        data.append({
            "starting_date": starting_date,
            "closing_date": closing_date,
            "trip": entry.trip.name if entry.trip else "",
            "status": status,
            "version": entry.version,
            "version_quote": entry.version_quote,
            "amount": amount,
            "client": entry.trip.client.name if entry.trip and entry.trip.client else "",
            "contact": str(entry.trip.contact) if entry.trip and entry.trip.contact else "",
            "user_creator": entry.user_creator.username,
            "user_working": entry.user_working.username,
            "difficulty": entry.trip.difficulty,
            "travelling_date": travelling_date,
        })

    # ejemplo dentro de stats_data (similar a entries_data)
    summary = {
        "quotesA_count": 0,
        "quotes_all_count": 0,
        "quotesA_sum": 0,
        "quotes_all_sum": 0,
        "bookings1_count": 0,
        "bookings_all_count": 0,
        "bookings1_sum": 0,
        "bookings_all_sum": 0,
        "others_count": 0,
    }

    for entry in qs:  # qs ya filtrado
        if entry.status == "Quote":
            summary["quotes_all_count"] += 1
            summary["quotes_all_sum"] += entry.amount or 0
            if entry.version_quote == "A":
                summary["quotesA_count"] += 1
                summary["quotesA_sum"] += entry.amount or 0
        elif entry.status == "Booking":
            summary["bookings_all_count"] += 1
            summary["bookings_all_sum"] += entry.amount or 0
            if entry.version == 1:
                summary["bookings1_count"] += 1
                summary["bookings1_sum"] += entry.amount or 0
        else:
            summary["others_count"] += 1


    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data,
        "summary": summary,
    })


def stats_trips_data(request):
    # Columnas en el mismo orden que definiste en el JS para trips
    columns = [
        "name",
        "client__name",
        "contact__name",
        "client_reference",
        "travelling_date",
        "amount",
        "difficulty",
        "responsable_user",
        "operations_user"
    ]

    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    search_value = request.GET.get("search[value]", "")

    order_col_index = min(int(request.GET.get("order[0][column]", 0)), len(columns) - 1)
    order_dir = request.GET.get("order[0][dir]", "asc")
    order_col = columns[order_col_index]
    if order_dir == "desc":
        order_col = f"-{order_col}"

    # 🚩 Filtrar solo viajes del departamento del usuario
    qs = Trip.objects.filter(
        department=request.user.department
    ).filter(status="Booking")

    # 🚩 filtros de fechas por travelling_date
    month = request.GET.get("month")
    year = request.GET.get("year")
    week = request.GET.get("week")
    season = request.GET.get("season")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if month and year:
        qs = qs.filter(
            travelling_date__year=year,
            travelling_date__month=month
        )
    elif date_from and date_to:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            qs = qs.filter(travelling_date__range=(date_from, date_to))
        except ValueError:
            pass  # si no se puede parsear, ignora el filtro

    this_year = date.today().year

    if week:
        this_week = date.today().isocalendar()[1]
        if int(week) > this_week:
            week_year = this_year - 1
        else:
            week_year = this_year

        week_date_from = date.fromisocalendar(week_year, int(week), 1)
        week_date_to = date.fromisocalendar(week_year, int(week), 7)

        qs = qs.filter(travelling_date__range=[week_date_from, week_date_to])

    if season:
        season_to = int(season) + 1
        season_date_from = date(int(season), 5, 1)
        season_date_to = date(season_to, 4, 30)

        qs = qs.filter(travelling_date__range=[season_date_from, season_date_to])

    # filtros drill-down por vendedor/operador/cliente
    vr_filter = request.GET.get("vr_filter")
    op_filter = request.GET.get("op_filter")
    trips_client_filter = request.GET.get("client_filter")
    if vr_filter:
        qs = qs.filter(responsable_user__other_name=vr_filter)
    if op_filter:
        qs = qs.filter(operations_user__other_name=op_filter)
    if trips_client_filter:
        qs = qs.filter(client__name=trips_client_filter)

    # 🚩 Búsqueda global
    if search_value:
        qs = qs.filter(
            Q(name__icontains=search_value) |
            Q(status__icontains=search_value) |
            Q(client__name__icontains=search_value) |
            Q(contact__name__icontains=search_value) |
            Q(client_reference__icontains=search_value) |
            Q(difficulty__icontains=search_value)
        )

    total_records = Trip.objects.filter(department=request.user.department).count()
    filtered_records = qs.count()

    # 🚩 Orden + paginación
    qs = qs.order_by(order_col)
    paginator = Paginator(qs, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    data = []
    for trip in page_obj:
        data.append({
            "name": trip.name,
            "client": trip.client.name if trip.client else "",
            "contact": str(trip.contact) if trip.contact else "",
            "reference": trip.client_reference or "n/a",
            "travelling_date": trip.travelling_date.strftime("%Y/%m/%d") if trip.travelling_date else "",
            "amount": f"USD {trip.amount:,.2f}" if trip.amount else "Pendiente",
            "difficulty": trip.difficulty,
            "responsable_user": trip.responsable_user.username,
            "operations_user": trip.operations_user.username
        })


    # summary inicialization
    summary = {
        "audley_count": 0,
        "audley_amount": 0,
        "others_count": 0,
        "others_amount": 0,
        "all_count": 0,
        "all_amount": 0
    }

    for trip in qs:  # qs ya filtrado
        if trip.client.name == "Audley Travel UK":
            summary["audley_count"] += 1
            summary["audley_amount"] += trip.amount or 0
        else:
            summary["others_count"] += 1
            summary["others_amount"] += trip.amount or 0

        summary["all_count"] += 1
        summary["all_amount"] += trip.amount or 0

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data,
        "summary": summary,
    })


@login_required
@csrf_exempt
def stats_data(request):
    """Router entre entries y trips para DataTables"""
    report_type = request.GET.get("type", "entries")

    if report_type == "trips":
        return stats_trips_data(request)
    else:
        return stats_entries_data(request)


def stats_entries_quotes_by_vendor(qs, date_from, date_to):

    quotes = qs.filter(status="Quote")
    # agrupación y agregación
    vendors = {}

    for entry in quotes:
        vendor = entry.user_working.other_name
        if vendor not in vendors:

            # ✅ Asegurar que el color sea string
            user_color = '#999999'  # Color por defecto

            if entry.user_working:
                if hasattr(entry.user_working, 'color'):
                    # Convertir explícitamente a string
                    color_value = entry.user_working.color
                    if color_value:
                        # Si es un objeto ColorField, convertir a string
                        user_color = str(color_value)

            vendors[vendor] = {
                "total": 0,
                "workingDays": get_working_days_worker(date_from, date_to, entry.user_working),
                "a": 0,
                "audleyA": 0,
                "montoA": 0.0,
                "color": user_color
            }
        if entry.version_quote == "A":
            vendors[vendor]["a"] += 1
            if entry.trip and entry.trip.client and entry.trip.client.name == "Audley Travel UK":
                vendors[vendor]["audleyA"] += 1
            if entry.amount:
                vendors[vendor]["montoA"] += float(entry.amount)
        vendors[vendor]["total"] += 1


    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por 'a' (cotizaciones A) descendente
    sorted_vendors = sorted(
        vendors.items(),
        key=lambda x: x[1]['a'],  # Ordenar por cantidad de cotizaciones A
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    vendors_ordered = OrderedDict(sorted_vendors)

    return dict(vendors_ordered)


def stats_entries_bookings_by_vendor(qs, date_from, date_to):
    bookings = qs.filter(status="Booking")
    # agrupación y agregación
    vendors_b = {}

    for entry in bookings:
        vendor = entry.user_working.other_name
        if vendor not in vendors_b:

            # ✅ Asegurar que el color sea string
            user_color = '#999999'  # Color por defecto

            if entry.user_working:
                if hasattr(entry.user_working, 'color'):
                    # Convertir explícitamente a string
                    color_value = entry.user_working.color
                    if color_value:
                        # Si es un objeto ColorField, convertir a string
                        user_color = str(color_value)

            # Create empty vendors
            vendors_b[vendor] = {
                "total": 0,
                "workingDays": get_working_days_worker(date_from, date_to, entry.user_working),
                "first": 0,
                "audleyFirst": 0,
                "amountFirst": 0.0,
                "conversionCount": 0,
                "color": user_color
            }

        # Complete the information of the vendors with booking information
        if entry.version == 1:
            vendors_b[vendor]["first"] += 1
            if entry.trip and entry.trip.client and entry.trip.client.name == "Audley Travel UK":
                vendors_b[vendor]["audleyFirst"] += 1
            if entry.amount:
                vendors_b[vendor]["amountFirst"] += float(entry.amount)

            # Get the information of the person who booked the trip
            vendor_quoted = entry.user_creator.other_name

            # Check if the vendor is in the original list
            if vendor_quoted not in vendors_b:
                vendors_b["Otros"] = {
                    "total": 0,
                    "workingDays": 0,
                    "first": 0,
                    "audleyFirst": 0,
                    "amountFirst": 0.0,
                    "conversionCount": 0,
                    "color": '#999999',
                }
                vendors_b["Otros"]["conversionCount"] += 1
            else:
                vendors_b[entry.user_creator.other_name]["conversionCount"] += 1

        vendors_b[vendor]["total"] += 1

    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por 'a' (cotizaciones A) descendente
    sorted_vendors_b = sorted(
        vendors_b.items(),
        key=lambda x: x[1]['first'],  # Ordenar por cantidad de cotizaciones A
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    vendors_ordered_bookings = OrderedDict(sorted_vendors_b)

    return dict(vendors_ordered_bookings)


def stats_entries_by_client(qs):
    # agrupación y agregación
    clients = {}

    for entry in qs:
        client = entry.trip.client.name
        if client not in clients:
            # Create empty clients
            clients[client] = {
                "quotesCount": 0,
                "quotesAmount": 0.0,
                "bookingsCount": 0,
                "bookingsAmount": 0.0,
                "others": 0,
            }

        # Complete the information of the clients
        if entry.status == "Quote" and entry.version_quote == "A":
            clients[client]["quotesCount"] += 1
            if entry.amount:
                clients[client]["quotesAmount"] += float(entry.amount)

        elif entry.status == "Booking" and entry.version == 1:
            clients[client]["bookingsCount"] += 1
            if entry.amount:
                clients[client]["bookingsAmount"] += float(entry.amount)
        else:
            clients[client]["others"] += 1

    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por 'a' (cotizaciones A) descendente
    sorted_clients = sorted(
        clients.items(),
        key=lambda x: x[1]['quotesCount'],  # Ordenar por cantidad de cotizaciones A
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    clients_ordered = OrderedDict(sorted_clients)

    return dict(clients_ordered)


def stats_entries_by_speed(qs):

    """
    Calcula las estadísticas de rapidez de respuesta utilizando el campo preguardado `response_speed`.
    Devuelve el mismo formato JSON que la versión anterior, sin requerir cambios en el JS.
    """

    # --- Categorías principales (manteniendo compatibilidad con el JS) ---
    categories = {
        "total": qs,
        "individual_quotes": qs.filter(status="Quote", trip__trip_type="FIT's"),
        "group_quotes": qs.filter(status="Quote", trip__trip_type="Grupos"),
        "audley_quotes": qs.filter(status="Quote", trip__client__name="Audley Travel UK"),
        "bookings": qs.filter(status="Booking"),
        "final_itineraries": qs.filter(status="Final Itinerary"),
    }

    def summarize_speed(subset):
        """Devuelve un dict con los conteos y porcentajes por rango de días (1 sola query)."""
        agg = subset.aggregate(
            total=Count('id'),
            same_day=Count('id', filter=Q(response_speed=0)),
            one_day=Count('id', filter=Q(response_speed=1)),
            two_days=Count('id', filter=Q(response_speed=2)),
            three_days=Count('id', filter=Q(response_speed=3)),
            four_days=Count('id', filter=Q(response_speed=4)),
            five_days=Count('id', filter=Q(response_speed=5)),
            more_days=Count('id', filter=Q(response_speed__gt=5)),
            unanswered=Count('id', filter=Q(response_speed__isnull=True)),
            avg=Coalesce(Avg("response_speed", output_field=FloatField()), 0.0),
        )
        total = agg['total'] or 0
        unanswered = agg['unanswered'] or 0
        responded = total - unanswered
        if total == 0:
            return {
                "total": 0, "same_day": 0, "one_day": 0, "two_days": 0,
                "three_days": 0, "four_days": 0, "five_days": 0, "more_days": 0,
                "unanswered": 0, "average": 0, "percentages": {},
            }
        speed_keys = ("same_day", "one_day", "two_days", "three_days", "four_days", "five_days", "more_days")
        ranges = {k: agg[k] or 0 for k in (*speed_keys, "unanswered")}
        # Speed bucket %s are over answered entries; SC % is over total
        percentages = {k: round(ranges[k] / responded * 100, 2) if responded > 0 else 0 for k in speed_keys}
        percentages['unanswered'] = round(unanswered / total * 100, 2) if total > 0 else 0
        return {
            "total": total,
            **ranges,
            "average": round(agg['avg'], 2),
            "percentages": percentages,
        }

    # --- Totales globales por categoría ---
    summary = {cat: summarize_speed(subset) for cat, subset in categories.items()}

    # --- Totales por vendedor: 1 sola query con conditional counts por status × speed ---
    vendors = defaultdict(dict)
    _SPEED_FIELDS = ("same_day","one_day","two_days","three_days","four_days","five_days","more_days","unanswered")
    _SPEED_Q = {
        "same_day":   Q(response_speed=0),
        "one_day":    Q(response_speed=1),
        "two_days":   Q(response_speed=2),
        "three_days": Q(response_speed=3),
        "four_days":  Q(response_speed=4),
        "five_days":  Q(response_speed=5),
        "more_days":  Q(response_speed__gt=5),
        "unanswered": Q(response_speed__isnull=True),
    }
    _STATUSES = {
        "total":    Q(),
        "quotes":   Q(status="Quote") & Q(trip__trip_type__in=["FIT's", "Grupos"]),
        "bookings": Q(status="Booking"),
        "finals":   Q(status="Final Itinerary"),
    }
    ann_kwargs = {}
    for stat_key, stat_q in _STATUSES.items():
        ann_kwargs[f"{stat_key}__total"] = Count('id', filter=stat_q)
        ann_kwargs[f"{stat_key}__avg"]   = Coalesce(Avg("response_speed", filter=stat_q, output_field=FloatField()), 0.0)
        for spd_key, spd_q in _SPEED_Q.items():
            ann_kwargs[f"{stat_key}__{spd_key}"] = Count('id', filter=stat_q & spd_q)

    vendor_rows = (
        qs
        .values("user_working__other_name")
        .annotate(**ann_kwargs)
        .exclude(user_working__other_name__isnull=True)
        .exclude(user_working__other_name__exact="")
    )

    # pre-fetch colors in one query
    user_colors = {u.other_name: str(u.color) if u.color else "#999999"
                   for u in User.objects.exclude(other_name__isnull=True).exclude(other_name="")}

    def _build_speed_entry(row, prefix):
        total = row[f"{prefix}__total"] or 0
        if total == 0:
            return {"total":0,"same_day":0,"one_day":0,"two_days":0,"three_days":0,
                    "four_days":0,"five_days":0,"more_days":0,"unanswered":0,"average":0,"percentages":{}}
        ranges = {k: row[f"{prefix}__{k}"] or 0 for k in _SPEED_FIELDS}
        unanswered = ranges['unanswered']
        responded = total - unanswered
        _speed_only = ("same_day","one_day","two_days","three_days","four_days","five_days","more_days")
        percentages = {k: round(ranges[k] / responded * 100, 2) if responded > 0 else 0 for k in _speed_only}
        percentages['unanswered'] = round(unanswered / total * 100, 2) if total > 0 else 0
        return {
            "total": total,
            **ranges,
            "average": round(row[f"{prefix}__avg"], 2),
            "percentages": percentages,
        }

    for row in vendor_rows:
        vname = row["user_working__other_name"]
        vendors[vname]["total"]    = _build_speed_entry(row, "total")
        vendors[vname]["quotes"]   = _build_speed_entry(row, "quotes")
        vendors[vname]["bookings"] = _build_speed_entry(row, "bookings")
        vendors[vname]["finals"]   = _build_speed_entry(row, "finals")
        vendors[vname]["color"]    = user_colors.get(vname, "#999999")

    # --- Estructura final compatible con tu JS ---
    summary_speed = {
        "summary": summary,  # Totales globales
        "vendors": vendors,  # Totales por vendedor
    }

    return summary_speed


@login_required
def stats_presentation_entries(request):
    """
    Devuelve datos agregados por vendedor (user_working)
    para generar estadísticas tipo generateSampleData().
    """
    department = request.user.department

    # filtros opcionales (mismo formato que tus otras vistas)
    month = request.GET.get("month")
    year = request.GET.get("year")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    season = request.GET.get("season")


    # base queryset
    qs = Entry.objects.select_related(
        "user_working", "trip", "trip__client"
    ).filter(
        trip__department=department
    )

    # Resolve d_from / d_to / this_year / this_month from whichever filter is active
    import calendar as _cal
    _today = date.today()
    if date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to   = datetime.strptime(date_to,   "%Y-%m-%d").date()
        except ValueError:
            d_from = d_to = _today
    elif month and year:
        _y, _m = int(year), int(month)
        d_from = date(_y, _m, 1)
        d_to   = date(_y, _m, _cal.monthrange(_y, _m)[1])
    elif season:
        _s = int(season)
        d_from = date(_s, 5, 1)
        d_to   = date(_s + 1, 4, 30)
    else:
        d_from = d_to = _today
    this_year  = d_from.year
    this_month = d_from.month

    # filtro por fechas — usar __date__range para que el último día sea inclusivo
    if month and year:
        qs = qs.filter(starting_date__month=month, starting_date__year=year)
    elif date_from and date_to:
        qs = qs.filter(starting_date__date__range=(d_from, d_to))
    elif season:
        qs = qs.filter(starting_date__date__range=(d_from, d_to))

    if this_month > 4:
        # String representation of the seasons if it is May or higher
        this_season_str = str(this_year) + "/" + str(this_year + 1)
        next_season_str = str(this_year + 1) + "/" + str(this_year + 2)
        next2_season_str = str(this_year + 2) + "/" + str(this_year + 3)

        # Dates in the specific seasons
        this_season_from = date(this_year, 5, 1)
        this_season_to = date(this_year + 1, 4, 30)
        next_season_from = date(this_year + 1, 5, 1)
        next_season_to = date(this_year + 2, 4, 30)
        next2_season_from = date(this_year + 2, 5, 1)
        next2_season_to = date(this_year + 3, 4, 30)

    else:
        # String representation of the seasons if it is January to April
        this_season_str = str(this_year - 1) + "/" + str(this_year)
        next_season_str = str(this_year) + "/" + str(this_year + 1)
        next2_season_str = str(this_year + 1) + "/" + str(this_year + 2)

        # Dates in the specific seasons
        this_season_from = date(this_year - 1, 5, 1)
        this_season_to = date(this_year, 4, 30)
        next_season_from = date(this_year, 5, 1)
        next_season_to = date(this_year + 1, 4, 30)
        next2_season_from = date(this_year + 1, 5, 1)
        next2_season_to = date(this_year + 2, 4, 30)

    quotes = qs.filter(status="Quote", version_quote="A")

    def _pct(num, denom): return round(num / denom * 100, 2) if denom else 0

    # Single aggregate query replaces ~20 individual queries
    q_agg = quotes.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        individual_count=Count('id', filter=Q(trip__trip_type="FIT's")),
        individual_amount=Sum('amount', filter=Q(trip__trip_type="FIT's")),
        audley_count=Count('id', filter=Q(trip__client__name="Audley Travel UK")),
        audley_amount=Sum('amount', filter=Q(trip__client__name="Audley Travel UK")),
        group_count=Count('id', filter=Q(trip__trip_type="Grupos")),
        group_amount=Sum('amount', filter=Q(trip__trip_type="Grupos")),
        fam_count=Count('id', filter=Q(trip__trip_type="FAM Tours")),
        fam_amount=Sum('amount', filter=Q(trip__trip_type="FAM Tours")),
        this_season_count=Count('id', filter=Q(trip__travelling_date__range=(this_season_from, this_season_to))),
        this_season_amount=Sum('amount', filter=Q(trip__travelling_date__range=(this_season_from, this_season_to))),
        next_season_count=Count('id', filter=Q(trip__travelling_date__range=(next_season_from, next_season_to))),
        next_season_amount=Sum('amount', filter=Q(trip__travelling_date__range=(next_season_from, next_season_to))),
        diff_1=Count('id', filter=Q(trip__difficulty="1")),
        diff_2=Count('id', filter=Q(trip__difficulty="2")),
        diff_3=Count('id', filter=Q(trip__difficulty="3")),
        diff_4=Count('id', filter=Q(trip__difficulty="4")),
        diff_5=Count('id', filter=Q(trip__difficulty="5")),
    )

    total_count_quotes        = q_agg['total_count'] or 0
    total_amount_quotes       = float(q_agg['total_amount'] or 0)
    individual_count_quotes   = q_agg['individual_count'] or 0
    individual_amount_quotes  = float(q_agg['individual_amount'] or 0)
    audley_count_quotes       = q_agg['audley_count'] or 0
    audley_amount_quotes      = float(q_agg['audley_amount'] or 0)
    group_count_quotes        = q_agg['group_count'] or 0
    group_amount_quotes       = float(q_agg['group_amount'] or 0)
    fam_count_quotes          = q_agg['fam_count'] or 0
    fam_amount_quotes         = float(q_agg['fam_amount'] or 0)
    this_season_count_quotes  = q_agg['this_season_count'] or 0
    this_season_amount_quotes = float(q_agg['this_season_amount'] or 0)
    next_season_count_quotes  = q_agg['next_season_count'] or 0
    next_season_amount_quotes = float(q_agg['next_season_amount'] or 0)
    difficulty_1 = q_agg['diff_1'] or 0
    difficulty_2 = q_agg['diff_2'] or 0
    difficulty_3 = q_agg['diff_3'] or 0
    difficulty_4 = q_agg['diff_4'] or 0
    difficulty_5 = q_agg['diff_5'] or 0

    total_changes_quotes = qs.filter(status="Quote").exclude(version_quote="A").count()

    individual_perc_quotes    = _pct(individual_amount_quotes,    total_amount_quotes)
    audley_perc_quotes        = _pct(audley_amount_quotes,        total_amount_quotes)
    group_perc_quotes         = _pct(group_amount_quotes,         total_amount_quotes)
    fam_perc_quotes           = _pct(fam_amount_quotes,           total_amount_quotes)
    this_season_perc_quotes   = _pct(this_season_amount_quotes,   total_amount_quotes)
    next_season_perc_quotes   = _pct(next_season_amount_quotes,   total_amount_quotes)

    days = max(count_workable_days(d_from, d_to), 1)
    average_quotes_quantity = round(total_count_quotes / days, 2)
    average_quotes_amount   = round(total_amount_quotes / days, 2)
    average_difficulty = round(
        (1*difficulty_1 + 2*difficulty_2 + 3*difficulty_3 + 4*difficulty_4 + 5*difficulty_5) / total_count_quotes, 2
    ) if total_count_quotes else 0

    summary_table_quotes = {
        "working_days": days,
        "difficulty_1": difficulty_1,
        "difficulty_2": difficulty_2,
        "difficulty_3": difficulty_3,
        "difficulty_4": difficulty_4,
        "difficulty_5": difficulty_5,
        "average_difficulty": average_difficulty,
        "total_count_quotes": total_count_quotes,
        "total_amount_quotes": total_amount_quotes,
        "total_changes_quotes": total_changes_quotes,
        "fam_count_quotes": fam_count_quotes,
        "fam_amount_quotes": fam_amount_quotes,
        "average_quotes_quantity": average_quotes_quantity,
        "average_quotes_amount": average_quotes_amount,
        "individual_count_quotes": individual_count_quotes,
        "individual_amount_quotes": individual_amount_quotes,
        "group_count_quotes": group_count_quotes,
        "group_amount_quotes": group_amount_quotes,
        "individual_perc_quotes": individual_perc_quotes,
        "group_perc_quotes": group_perc_quotes,
        "fam_perc_quotes": fam_perc_quotes,
        "audley_count_quotes": audley_count_quotes,
        "audley_amount_quotes": audley_amount_quotes,
        "audley_perc_quotes": audley_perc_quotes,
        "this_season_str": this_season_str,
        "next_season_str": next_season_str,
        "this_season_count_quotes": this_season_count_quotes,
        "this_season_amount_quotes": this_season_amount_quotes,
        "this_season_perc_quotes": this_season_perc_quotes,
        "next_season_count_quotes": next_season_count_quotes,
        "next_season_amount_quotes": next_season_amount_quotes,
        "next_season_perc_quotes": next_season_perc_quotes
    }

    bookings = qs.filter(status="Booking", version=1)

    # Single aggregate query replaces ~16 individual queries
    b_agg = bookings.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        individual_count=Count('id', filter=Q(trip__trip_type="FIT's")),
        individual_amount=Sum('amount', filter=Q(trip__trip_type="FIT's")),
        audley_count=Count('id', filter=Q(trip__client__name="Audley Travel UK")),
        audley_amount=Sum('amount', filter=Q(trip__client__name="Audley Travel UK")),
        group_count=Count('id', filter=Q(trip__trip_type="Grupos")),
        group_amount=Sum('amount', filter=Q(trip__trip_type="Grupos")),
        fam_count=Count('id', filter=Q(trip__trip_type="FAM Tours")),
        fam_amount=Sum('amount', filter=Q(trip__trip_type="FAM Tours")),
        this_season_count=Count('id', filter=Q(trip__travelling_date__range=(this_season_from, this_season_to))),
        this_season_amount=Sum('amount', filter=Q(trip__travelling_date__range=(this_season_from, this_season_to))),
        next_season_count=Count('id', filter=Q(trip__travelling_date__range=(next_season_from, next_season_to))),
        next_season_amount=Sum('amount', filter=Q(trip__travelling_date__range=(next_season_from, next_season_to))),
    )

    total_count_bookings        = b_agg['total_count'] or 0
    total_amount_bookings       = float(b_agg['total_amount'] or 0)
    individual_count_bookings   = b_agg['individual_count'] or 0
    individual_amount_bookings  = float(b_agg['individual_amount'] or 0)
    audley_count_bookings       = b_agg['audley_count'] or 0
    audley_amount_bookings      = float(b_agg['audley_amount'] or 0)
    group_count_bookings        = b_agg['group_count'] or 0
    group_amount_bookings       = float(b_agg['group_amount'] or 0)
    fam_count_bookings          = b_agg['fam_count'] or 0
    fam_amount_bookings         = float(b_agg['fam_amount'] or 0)
    this_season_count_bookings  = b_agg['this_season_count'] or 0
    this_season_amount_bookings = float(b_agg['this_season_amount'] or 0)
    next_season_count_bookings  = b_agg['next_season_count'] or 0
    next_season_amount_bookings = float(b_agg['next_season_amount'] or 0)

    total_changes_bookings = qs.filter(status="Booking").exclude(version=1).count()

    individual_perc_bookings    = _pct(individual_amount_bookings,    total_amount_bookings)
    audley_perc_bookings        = _pct(audley_amount_bookings,        total_amount_bookings)
    group_perc_bookings         = _pct(group_amount_bookings,         total_amount_bookings)
    fam_perc_bookings           = _pct(fam_amount_bookings,           total_amount_bookings)
    this_season_perc_bookings   = _pct(this_season_amount_bookings,   total_amount_bookings)
    next_season_perc_bookings   = _pct(next_season_amount_bookings,   total_amount_bookings)

    average_bookings_quantity = round(total_count_bookings / days, 2)
    average_bookings_amount   = round(total_amount_bookings / days, 2)

    # By trip type (all TRIP_TYPES, single group-by query each)
    q_by_type_qs = quotes.values('trip__trip_type').annotate(count=Count('id'), amount=Sum('amount'))
    b_by_type_qs = bookings.values('trip__trip_type').annotate(count=Count('id'), amount=Sum('amount'))
    q_type_map = {r['trip__trip_type']: r for r in q_by_type_qs}
    b_type_map = {r['trip__trip_type']: r for r in b_by_type_qs}
    by_type_quotes = []
    by_type_bookings = []
    for tt_val, tt_label in TRIP_TYPES:
        rq = q_type_map.get(tt_val, {})
        rb = b_type_map.get(tt_val, {})
        cnt_q = rq.get('count', 0) or 0
        amt_q = float(rq.get('amount', 0) or 0)
        cnt_b = rb.get('count', 0) or 0
        amt_b = float(rb.get('amount', 0) or 0)
        by_type_quotes.append({'label': tt_label, 'count': cnt_q, 'amount': amt_q, 'perc': _pct(amt_q, total_amount_quotes)})
        by_type_bookings.append({'label': tt_label, 'count': cnt_b, 'amount': amt_b, 'perc': _pct(amt_b, total_amount_bookings)})
    by_type_quotes.append({'label': 'TOTAL', 'count': total_count_quotes, 'amount': total_amount_quotes, 'perc': 100.0, 'is_total': True})
    by_type_bookings.append({'label': 'TOTAL', 'count': total_count_bookings, 'amount': total_amount_bookings, 'perc': 100.0, 'is_total': True})

    # By travelling season (dynamic: all distinct seasons from actual data)
    def _season_of(d):
        return d.year if d.month >= 5 else d.year - 1

    td_q = set(quotes.exclude(trip__travelling_date__isnull=True).values_list('trip__travelling_date', flat=True))
    td_b = set(bookings.exclude(trip__travelling_date__isnull=True).values_list('trip__travelling_date', flat=True))
    season_starts_list = sorted(set(_season_of(d) for d in (td_q | td_b)))
    by_season_quotes = []
    by_season_bookings = []
    for ss in season_starts_list:
        sf  = date(ss,     5, 1)
        st_ = date(ss + 1, 4, 30)
        slabel = f"{ss}/{ss + 1}"
        sq = quotes.filter(trip__travelling_date__range=(sf, st_))
        sq_c = sq.count()
        sq_a = float(sq.aggregate(s=Sum('amount'))['s'] or 0)
        sb = bookings.filter(trip__travelling_date__range=(sf, st_))
        sb_c = sb.count()
        sb_a = float(sb.aggregate(s=Sum('amount'))['s'] or 0)
        by_season_quotes.append({'label': slabel, 'count': sq_c, 'amount': sq_a, 'perc': _pct(sq_a, total_amount_quotes)})
        by_season_bookings.append({'label': slabel, 'count': sb_c, 'amount': sb_a, 'perc': _pct(sb_a, total_amount_bookings)})
    by_season_quotes.append({'label': 'TOTAL', 'count': total_count_quotes, 'amount': total_amount_quotes, 'perc': 100.0, 'is_total': True})
    by_season_bookings.append({'label': 'TOTAL', 'count': total_count_bookings, 'amount': total_amount_bookings, 'perc': 100.0, 'is_total': True})

    # Cancellation information
    cancellations_count = qs.filter(status="Cancelado").count()

    # Cancellation amounts (difference with the last booking)
    cancellations_amount = 0.0
    cancellation_entries = qs.filter(status="Cancelado")

    for entry in cancellation_entries:
        trip_obj = entry.trip
        last_booking = Entry.objects.filter(trip=trip_obj, status="Booking").first()
        if last_booking:
            cancellations_amount += float(last_booking.amount or 0)
        else:
            cancellations_amount += float(entry.amount or 0)

    conversion_perc        = _pct(total_count_bookings,  total_count_quotes)
    conversion_perc_audley = _pct(audley_count_bookings, audley_count_quotes)

    summary_table_bookings = {
        "total_count_bookings": total_count_bookings,
        "total_amount_bookings": total_amount_bookings,
        "total_changes_bookings": total_changes_bookings,
        "fam_count_bookings": fam_count_bookings,
        "fam_amount_bookings": fam_amount_bookings,
        "average_bookings_quantity": average_bookings_quantity,
        "average_bookings_amount": average_bookings_amount,
        "individual_count_bookings": individual_count_bookings,
        "individual_amount_bookings": individual_amount_bookings,
        "group_count_bookings": group_count_bookings,
        "group_amount_bookings": group_amount_bookings,
        "individual_perc_bookings": individual_perc_bookings,
        "group_perc_bookings": group_perc_bookings,
        "fam_perc_bookings": fam_perc_bookings,
        "audley_count_bookings": audley_count_bookings,
        "audley_amount_bookings": audley_amount_bookings,
        "audley_perc_bookings": audley_perc_bookings,
        "this_season_count_bookings": this_season_count_bookings,
        "this_season_amount_bookings": this_season_amount_bookings,
        "this_season_perc_bookings": this_season_perc_bookings,
        "next_season_count_bookings": next_season_count_bookings,
        "next_season_amount_bookings": next_season_amount_bookings,
        "next_season_perc_bookings": next_season_perc_bookings,
        "cancellations_count": cancellations_count,
        "cancellations_amount": cancellations_amount,
        "conversion_perc": conversion_perc,
        "conversion_perc_audley": conversion_perc_audley,
    }

    vendors_quote = stats_entries_quotes_by_vendor(qs, d_from, d_to)
    vendors_bookings = stats_entries_bookings_by_vendor(qs, d_from, d_to)
    summary_speed = stats_entries_by_speed(qs)
    clients = stats_entries_by_client(qs)

    # Monthly breakdown (only for season or multi-month ranges)
    import calendar as _cal2
    _is_multi_month = season or (
        date_from and date_to and (
            (d_to.year * 12 + d_to.month) - (d_from.year * 12 + d_from.month) >= 1
        )
    )
    monthly_breakdown = []
    if _is_multi_month:
        rows = (
            qs
            .annotate(_month=TruncMonth('starting_date'))
            .values('_month')
            .annotate(
                quotes_count=Count('id', filter=Q(status='Quote', version_quote='A')),
                quotes_amount=Sum('amount', filter=Q(status='Quote', version_quote='A')),
                bookings_count=Count('id', filter=Q(status='Booking')),
                bookings_amount=Sum('amount', filter=Q(status='Booking')),
                active_vendors=Count('user_working', filter=Q(status__in=['Quote', 'Booking']), distinct=True),
            )
            .order_by('_month')
        )
        _MONTH_NAMES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        for r in rows:
            m = r['_month']
            if not m:
                continue
            monthly_breakdown.append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES[m.month - 1]} {m.year}",
                'quotes_count': r['quotes_count'] or 0,
                'quotes_amount': float(r['quotes_amount'] or 0),
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
                'active_vendors': r['active_vendors'] or 0,
            })

    monthly_by_vendor = {}
    monthly_by_client = {}
    if _is_multi_month:
        _MONTH_NAMES2 = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        vendor_rows = (
            qs
            .filter(user_working__userType='Ventas')
            .annotate(_month=TruncMonth('starting_date'))
            .values('_month', 'user_working__other_name')
            .annotate(
                quotes_count=Count('id', filter=Q(status='Quote', version_quote='A')),
                quotes_amount=Sum('amount', filter=Q(status='Quote', version_quote='A')),
                bookings_count=Count('id', filter=Q(status='Booking', version=1)),
                bookings_amount=Sum('amount', filter=Q(status='Booking', version=1)),
            )
            .order_by('user_working__other_name', '_month')
        )
        for r in vendor_rows:
            m = r['_month']
            if not m:
                continue
            vname = r['user_working__other_name'] or 'Desconocido'
            if vname not in monthly_by_vendor:
                monthly_by_vendor[vname] = []
            monthly_by_vendor[vname].append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES2[m.month - 1]} {m.year}",
                'quotes_count': r['quotes_count'] or 0,
                'quotes_amount': float(r['quotes_amount'] or 0),
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
            })

        client_rows = (
            qs
            .annotate(_month=TruncMonth('starting_date'))
            .values('_month', 'trip__client__name')
            .annotate(
                quotes_count=Count('id', filter=Q(status='Quote', version_quote='A')),
                quotes_amount=Sum('amount', filter=Q(status='Quote', version_quote='A')),
                bookings_count=Count('id', filter=Q(status='Booking', version=1)),
                bookings_amount=Sum('amount', filter=Q(status='Booking', version=1)),
            )
            .order_by('trip__client__name', '_month')
        )
        for r in client_rows:
            m = r['_month']
            if not m:
                continue
            cname = r['trip__client__name'] or 'Desconocido'
            if cname not in monthly_by_client:
                monthly_by_client[cname] = []
            monthly_by_client[cname].append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES2[m.month - 1]} {m.year}",
                'quotes_count': r['quotes_count'] or 0,
                'quotes_amount': float(r['quotes_amount'] or 0),
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
            })

    vendor_types = {
        r['user_working__other_name']: r['user_working__userType']
        for r in qs.values('user_working__other_name', 'user_working__userType').distinct()
        if r['user_working__other_name']
    }

    return JsonResponse({
        "vendors_quote": vendors_quote,
        "vendors_bookings": vendors_bookings,
        "summary_table_quotes": summary_table_quotes,
        "summary_table_bookings": summary_table_bookings,
        "by_type_quotes": by_type_quotes,
        "by_type_bookings": by_type_bookings,
        "by_season_quotes": by_season_quotes,
        "by_season_bookings": by_season_bookings,
        "summary_speed": summary_speed,
        "clients": clients,
        "monthly_breakdown": monthly_breakdown,
        "monthly_by_vendor": monthly_by_vendor,
        "monthly_by_client": monthly_by_client,
        "vendor_types": vendor_types,
    })


def stats_trips_by_responsable(qs, date_from, date_to):
    bookings = qs.filter(status="Booking")
    # agrupación y agregación
    responsable_users = {}

    for trip in bookings:
        vendor = trip.responsable_user.other_name
        if vendor not in responsable_users:

            # ✅ Asegurar que el color sea string
            user_color = '#999999'  # Color por defecto

            if trip.responsable_user:
                if hasattr(trip.responsable_user, 'color'):
                    # Convertir explícitamente a string
                    color_value = trip.responsable_user.color
                    if color_value:
                        # Si es un objeto ColorField, convertir a string
                        user_color = str(color_value)

            # Create empty vendors
            responsable_users[vendor] = {
                "total": 0,
                "amountTotal": 0,
                "audley": 0,
                "amountAudley": 0.0,
                "color": user_color,
                "workingDays": get_working_days_worker(date_from, date_to, trip.responsable_user),
            }

        # Complete the information of the vendors with booking information
        if trip.client and trip.client.name == "Audley Travel UK":
            responsable_users[vendor]["audley"] += 1
            if trip.amount:
                responsable_users[vendor]["amountAudley"] += float(trip.amount)

        responsable_users[vendor]["total"] += 1
        if trip.amount:
            responsable_users[vendor]["amountTotal"] += float(trip.amount)

    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por 'a' (cotizaciones A) descendente
    sorted_vendors = sorted(
        responsable_users.items(),
        key=lambda x: x[1]['total'],  # Ordenar por cantidad de cotizaciones A
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    vendors_ordered_bookings = OrderedDict(sorted_vendors)

    return dict(vendors_ordered_bookings)


def stats_trips_by_operator(qs, date_from, date_to):
    bookings = qs.filter(status="Booking")
    # agrupación y agregación
    operations_users = {}

    for trip in bookings:
        operator = trip.operations_user.other_name
        if operator not in operations_users:

            # ✅ Asegurar que el color sea string
            user_color = '#999999'  # Color por defecto

            if trip.operations_user:
                if hasattr(trip.operations_user, 'color'):
                    # Convertir explícitamente a string
                    color_value = trip.operations_user.color
                    if color_value:
                        # Si es un objeto ColorField, convertir a string
                        user_color = str(color_value)

            # Create empty vendors
            operations_users[operator] = {
                "total": 0,
                "amountTotal": 0,
                "audley": 0,
                "amountAudley": 0.0,
                "color": user_color,
                "workingDays": get_working_days_worker(date_from, date_to, trip.responsable_user),
            }

        # Complete the information of the vendors with booking information
        if trip.client and trip.client.name == "Audley Travel UK":
            operations_users[operator]["audley"] += 1
            if trip.amount:
                operations_users[operator]["amountAudley"] += float(trip.amount)

        operations_users[operator]["total"] += 1
        if trip.amount:
            operations_users[operator]["amountTotal"] += float(trip.amount)

    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por 'a' (cotizaciones A) descendente
    sorted_operators = sorted(
        operations_users.items(),
        key=lambda x: x[1]['total'],  # Ordenar por cantidad de cotizaciones A
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    operators_ordered_bookings = OrderedDict(sorted_operators)

    return dict(operators_ordered_bookings)


def stats_trips_by_client(qs):
    # agrupación y agregación
    clients = {}
    bookings = qs.filter(status="Booking")

    for trip in bookings:
        client = trip.client.name
        if client not in clients:
            # Create empty clients
            clients[client] = {
                "bookingsCount": 0,
                "bookingsAmount": 0.0,
                "cancelled": 0,
                "totalDifficulty": 0,
            }


        clients[client]["bookingsCount"] += 1
        clients[client]["totalDifficulty"] += int(trip.difficulty)
        if trip.amount:
            clients[client]["bookingsAmount"] += float(trip.amount)

    for trip in qs:
        if trip.status == "Cancelado":
            clients[client]["cancelled"] += 1


    # ✅ ORDENAR: Convertir a lista de tuplas y ordenar por cantidad
    sorted_clients = sorted(
        clients.items(),
        key=lambda x: x[1]['bookingsCount'],
        reverse=True  # De mayor a menor
    )

    # ✅ Convertir de vuelta a diccionario ordenado
    clients_ordered = OrderedDict(sorted_clients)

    return dict(clients_ordered)


@login_required
def stats_presentation_trips(request):

    department = request.user.department

    # filtros opcionales
    month = request.GET.get("month")
    year = request.GET.get("year")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    season = request.GET.get("season")


    # base queryset
    qs = Trip.objects.select_related("client").filter(
        department=department
    )

    # Resolve d_from / d_to / this_year / this_month from whichever filter is active
    import calendar as _cal
    _today = date.today()
    if date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to   = datetime.strptime(date_to,   "%Y-%m-%d").date()
        except ValueError:
            d_from = d_to = _today
    elif month and year:
        _y, _m = int(year), int(month)
        d_from = date(_y, _m, 1)
        d_to   = date(_y, _m, _cal.monthrange(_y, _m)[1])
    elif season:
        _s = int(season)
        d_from = date(_s, 5, 1)
        d_to   = date(_s + 1, 4, 30)
    else:
        d_from = d_to = _today
    this_year  = d_from.year
    this_month = d_from.month

    # filtro por fechas
    if month and year:
        qs = qs.filter(travelling_date__month=month, travelling_date__year=year)
    elif date_from and date_to:
        qs = qs.filter(travelling_date__range=(d_from, d_to))
    elif season:
        qs = qs.filter(travelling_date__range=(d_from, d_to))

    if this_month > 4:
        # String representation of the seasons if it is May or higher
        this_season_str = str(this_year) + "/" + str(this_year + 1)
        next_season_str = str(this_year + 1) + "/" + str(this_year + 2)
        next2_season_str = str(this_year + 2) + "/" + str(this_year + 3)

        # Dates in the specific seasons
        this_season_from = date(this_year, 5, 1)
        this_season_to = date(this_year + 1, 4, 30)
        next_season_from = date(this_year + 1, 5, 1)
        next_season_to = date(this_year + 2, 4, 30)
        next2_season_from = date(this_year + 2, 5, 1)
        next2_season_to = date(this_year + 3, 4, 30)

    else:
        # String representation of the seasons if it is January to April
        this_season_str = str(this_year - 1) + "/" + str(this_year)
        next_season_str = str(this_year) + "/" + str(this_year + 1)
        next2_season_str = str(this_year + 1) + "/" + str(this_year + 2)

        # Dates in the specific seasons
        this_season_from = date(this_year - 1, 5, 1)
        this_season_to = date(this_year, 4, 30)
        next_season_from = date(this_year, 5, 1)
        next_season_to = date(this_year + 1, 4, 30)
        next2_season_from = date(this_year + 1, 5, 1)
        next2_season_to = date(this_year + 2, 4, 30)

    trips = qs.filter(status="Booking")

    def _pct(num, denom): return round(num / denom * 100, 2) if denom else 0

    # Single aggregate query replaces ~18 individual queries
    t_agg = trips.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        individual_count=Count('id', filter=Q(trip_type="FIT's")),
        individual_amount=Sum('amount', filter=Q(trip_type="FIT's")),
        audley_count=Count('id', filter=Q(client__name="Audley Travel UK")),
        audley_amount=Sum('amount', filter=Q(client__name="Audley Travel UK")),
        group_count=Count('id', filter=Q(trip_type="Grupos")),
        group_amount=Sum('amount', filter=Q(trip_type="Grupos")),
        fam_count=Count('id', filter=Q(trip_type="FAM Tours")),
        fam_amount=Sum('amount', filter=Q(trip_type="FAM Tours")),
        all_rent=Sum('rent_perc'),
        individual_rent_sum=Sum('rent_perc', filter=Q(trip_type="FIT's")),
        audley_rent_sum=Sum('rent_perc', filter=Q(client__name="Audley Travel UK")),
        group_rent_sum=Sum('rent_perc', filter=Q(trip_type="Grupos")),
        fam_rent_sum=Sum('rent_perc', filter=Q(trip_type="FAM Tours")),
        diff_1=Count('id', filter=Q(difficulty="1")),
        diff_2=Count('id', filter=Q(difficulty="2")),
        diff_3=Count('id', filter=Q(difficulty="3")),
        diff_4=Count('id', filter=Q(difficulty="4")),
        diff_5=Count('id', filter=Q(difficulty="5")),
    )

    total_count_trips       = t_agg['total_count'] or 0
    total_amount_trips      = float(t_agg['total_amount'] or 0)
    individual_count_trips  = t_agg['individual_count'] or 0
    individual_amount_trips = float(t_agg['individual_amount'] or 0)
    audley_count_trips      = t_agg['audley_count'] or 0
    audley_amount_trips     = float(t_agg['audley_amount'] or 0)
    group_count_trips       = t_agg['group_count'] or 0
    group_amount_trips      = float(t_agg['group_amount'] or 0)
    fam_count_trips         = t_agg['fam_count'] or 0
    fam_amount_trips        = float(t_agg['fam_amount'] or 0)
    difficulty_1 = t_agg['diff_1'] or 0
    difficulty_2 = t_agg['diff_2'] or 0
    difficulty_3 = t_agg['diff_3'] or 0
    difficulty_4 = t_agg['diff_4'] or 0
    difficulty_5 = t_agg['diff_5'] or 0

    individual_perc_trips = _pct(individual_amount_trips, total_amount_trips)
    audley_perc_trips     = _pct(audley_amount_trips,     total_amount_trips)
    group_perc_trips      = _pct(group_amount_trips,      total_amount_trips)
    fam_perc_trips        = _pct(fam_amount_trips,        total_amount_trips)

    all_rent_average = _pct(float(t_agg['all_rent'] or 0),          total_count_trips)
    individual_rent  = _pct(float(t_agg['individual_rent_sum'] or 0), individual_count_trips)
    audley_rent      = _pct(float(t_agg['audley_rent_sum'] or 0),     audley_count_trips)
    group_rent       = _pct(float(t_agg['group_rent_sum'] or 0),      group_count_trips)
    fam_rent         = _pct(float(t_agg['fam_rent_sum'] or 0),        fam_count_trips)

    average_difficulty = round(
        (1*difficulty_1 + 2*difficulty_2 + 3*difficulty_3 + 4*difficulty_4 + 5*difficulty_5) / total_count_trips, 2
    ) if total_count_trips else 0

    # Cancellation information
    canc_agg = qs.filter(status="Cancelado").aggregate(count=Count('id'), amount=Sum('amount'))
    cancellations_count  = canc_agg['count'] or 0
    cancellations_amount = float(canc_agg['amount'] or 0)

    summary_table_trips = {
        "difficulty_1": difficulty_1,
        "difficulty_2": difficulty_2,
        "difficulty_3": difficulty_3,
        "difficulty_4": difficulty_4,
        "difficulty_5": difficulty_5,
        "average_difficulty": average_difficulty,
        "total_count_trips": total_count_trips,
        "total_amount_trips": total_amount_trips,
        "fam_count_trips": fam_count_trips,
        "fam_amount_trips": fam_amount_trips,
        "individual_count_trips": individual_count_trips,
        "individual_amount_trips": individual_amount_trips,
        "group_count_trips": group_count_trips,
        "group_amount_trips": group_amount_trips,
        "individual_perc_trips": individual_perc_trips,
        "group_perc_trips": group_perc_trips,
        "fam_perc_trips": fam_perc_trips,
        "audley_count_trips": audley_count_trips,
        "audley_amount_trips": audley_amount_trips,
        "audley_perc_trips": audley_perc_trips,
        "cancellations_count": cancellations_count,
        "cancellations_amount": cancellations_amount,
        "all_rent_average": all_rent_average,
        "individual_rent": individual_rent,
        "audley_rent": audley_rent,
        "group_rent": group_rent,
        "fam_rent": fam_rent,
    }

    trips_by_responsable = stats_trips_by_responsable(qs, d_from, d_to)
    trips_by_operator = stats_trips_by_operator(qs, d_from, d_to)
    clients = stats_trips_by_client(qs)

    # Monthly breakdown (only for season or multi-month ranges)
    import calendar as _cal2
    _is_multi_month = season or (
        date_from and date_to and (
            (d_to.year * 12 + d_to.month) - (d_from.year * 12 + d_from.month) >= 1
        )
    )
    monthly_breakdown = []
    if _is_multi_month:
        rows = (
            qs
            .annotate(_month=TruncMonth('travelling_date'))
            .values('_month')
            .annotate(
                bookings_count=Count('id', filter=Q(status='Booking')),
                bookings_amount=Sum('amount', filter=Q(status='Booking')),
                avg_rent=Avg('rent_perc', filter=Q(status='Booking')),
                cancellations_count=Count('id', filter=Q(status='Cancelado')),
            )
            .order_by('_month')
        )
        _MONTH_NAMES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        for r in rows:
            m = r['_month']
            if not m:
                continue
            monthly_breakdown.append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES[m.month - 1]} {m.year}",
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
                'avg_rent': round(float(r['avg_rent'] or 0) * 100, 2),
                'cancellations_count': r['cancellations_count'] or 0,
            })

    monthly_by_vr = {}
    monthly_by_operator = {}
    monthly_by_client = {}
    if _is_multi_month:
        _MONTH_NAMES2 = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        vr_rows = (
            qs.filter(status='Booking')
            .annotate(_month=TruncMonth('travelling_date'))
            .values('_month', 'responsable_user__other_name')
            .annotate(
                bookings_count=Count('id'),
                bookings_amount=Sum('amount'),
            )
            .order_by('responsable_user__other_name', '_month')
        )
        for r in vr_rows:
            m = r['_month']
            if not m:
                continue
            vname = r['responsable_user__other_name'] or 'Desconocido'
            if vname not in monthly_by_vr:
                monthly_by_vr[vname] = []
            monthly_by_vr[vname].append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES2[m.month - 1]} {m.year}",
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
            })

        op_rows = (
            qs.filter(status='Booking')
            .annotate(_month=TruncMonth('travelling_date'))
            .values('_month', 'operations_user__other_name')
            .annotate(
                bookings_count=Count('id'),
                bookings_amount=Sum('amount'),
            )
            .order_by('operations_user__other_name', '_month')
        )
        for r in op_rows:
            m = r['_month']
            if not m:
                continue
            opname = r['operations_user__other_name'] or 'Desconocido'
            if opname not in monthly_by_operator:
                monthly_by_operator[opname] = []
            monthly_by_operator[opname].append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES2[m.month - 1]} {m.year}",
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
            })

        client_rows = (
            qs.filter(status='Booking')
            .annotate(_month=TruncMonth('travelling_date'))
            .values('_month', 'client__name')
            .annotate(
                bookings_count=Count('id'),
                bookings_amount=Sum('amount'),
            )
            .order_by('client__name', '_month')
        )
        for r in client_rows:
            m = r['_month']
            if not m:
                continue
            cname = r['client__name'] or 'Desconocido'
            if cname not in monthly_by_client:
                monthly_by_client[cname] = []
            monthly_by_client[cname].append({
                'month_key': m.strftime('%Y-%m'),
                'label': f"{_MONTH_NAMES2[m.month - 1]} {m.year}",
                'bookings_count': r['bookings_count'] or 0,
                'bookings_amount': float(r['bookings_amount'] or 0),
            })

    # By trip type (group-by query)
    t_by_type_qs = trips.values('trip_type').annotate(
        count=Count('id'),
        amount=Sum('amount'),
        rent_sum=Sum('rent_perc'),
    )
    t_type_map = {r['trip_type']: r for r in t_by_type_qs}
    by_type_trips = []
    for tt_val, tt_label in TRIP_TYPES:
        r = t_type_map.get(tt_val, {})
        cnt  = r.get('count', 0) or 0
        amt  = float(r.get('amount', 0) or 0)
        rent_s = float(r.get('rent_sum', 0) or 0)
        avg_rent_pct = _pct(rent_s, cnt)
        by_type_trips.append({
            'label':        tt_label,
            'count':        cnt,
            'amount':       amt,
            'amount_perc':  _pct(amt, total_amount_trips),
            'avg_rent_perc': avg_rent_pct,
            'rent_amount':  avg_rent_pct / 100 * amt,
        })
    total_rent_amount = all_rent_average / 100 * total_amount_trips
    by_type_trips.append({
        'label':        'TOTAL',
        'count':        total_count_trips,
        'amount':       total_amount_trips,
        'amount_perc':  100.0,
        'avg_rent_perc': all_rent_average,
        'rent_amount':  total_rent_amount,
        'is_total':     True,
    })

    return JsonResponse({
        "summary_table_trips": summary_table_trips,
        "by_type_trips": by_type_trips,
        "trips_by_responsable": trips_by_responsable,
        "trips_by_operator": trips_by_operator,
        "clients": clients,
        "monthly_breakdown": monthly_breakdown,
        "monthly_by_vr": monthly_by_vr,
        "monthly_by_operator": monthly_by_operator,
        "monthly_by_client": monthly_by_client,
    })


def read_emails(request):
    load_dotenv(override=True)

    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_SERVER = os.environ.get("MAIL_SERVER")

    emails = []

    with MailBox(MAIL_SERVER).login(MAIL_USERNAME, MAIL_PASSWORD, "Inbox") as mb:
        for msg in mb.fetch(limit=10, reverse=True, mark_seen=True):

            attachments = []
            for att in msg.attachments:
                attachments.append(att.part)
            emails.append({"id":msg.uid, "subject":msg.subject, "date":msg.date, "flags":msg.flags, "text":msg.text, "attachments":attachments})


    return render(request, "intranet/read_emails.html", {
        "emails": emails,
    })


@login_required
def tourplan_files(request):

    if request.method == "POST":
        form = CsvFormTourplanFiles(request.POST, request.FILES)
        if form.is_valid():

            form.save()

            csv_obj = CsvFileTourplanFiles.objects.get(read=False)
            tourplan_files = upload_data(csv_obj)

            return render(request, "intranet/tourplan_files.html", {
                "form":form,
                "tourplan_files":tourplan_files,
                "users": User.objects.all,
            })
    else:
        form = CsvFormTourplanFiles()

    return render(request, "intranet/tourplan_files.html", {
        "form":form,
        "users": User.objects.all,
    })

def upload_data(csv_obj):

    # Pre-fetch lookups into dicts to avoid per-row DB queries
    users_by_other_tp = {u.other_tp: u for u in User.objects.all() if u.other_tp}

    trips_by_tourplan = {
        t.tourplanId: t
        for t in Trip.objects.select_related(
            "responsable_user", "operations_user"
        ).exclude(tourplanId="").exclude(tourplanId__isnull=True)
    }

    booking_tp_ids = set(
        Trip.objects.filter(status="Booking")
        .exclude(tourplanId="").exclude(tourplanId__isnull=True)
        .values_list("tourplanId", flat=True)
    )

    # For extended matching: Entry tourplanIds and Trip client_references (raw, no splitting)
    entry_tp_ids = set(
        Entry.objects.exclude(tourplanId="").exclude(tourplanId__isnull=True)
        .values_list("tourplanId", flat=True)
    )
    client_ref_set = set()
    for ref in Trip.objects.exclude(client_reference="").exclude(client_reference__isnull=True).values_list("client_reference", flat=True):
        if ref:
            r = str(ref).strip()
            client_ref_set.add(r)
            if "/" in r:
                client_ref_set.add(r.split("/")[0])

    updated_count = 0
    csv_not_in_app = []        # dicts with row data for TP IDs not found in app
    csv_client_ref_to_tp = {}  # client_ref_prefix (col 15) → tp_id (col 3), for TP suggestions
    csv_quote_tp_ids = set()   # TP IDs that appear in the CSV with Quote status
    matched_tp_ids = set()
    trips_to_update = []

    with open(csv_obj.file_name.path, 'r') as f:
        reader = csv.reader(f, delimiter=';')

        for i, row in enumerate(reader):
            if i < 7:
                continue

            # col 3 (index 2) — tourplanId
            if len(row) < 3:
                continue
            tp_id = row[2].strip()
            if not tp_id:
                continue

            # col 15 (index 14) — client reference from CSV (e.g. "2640190/1")
            csv_client_ref = str(row[14]).strip() if len(row) > 14 else ""
            client_ref_prefix = str(csv_client_ref.split("/")[0]).strip() if "/" in csv_client_ref else csv_client_ref
            csv_client_name = row[12].strip() if len(row) > 12 else ""
            is_consumidor_final = csv_client_name.lower().startswith("consumidor final")

            # Build prefix→{tp_id, name} map: ONLY Booking rows (OK/FI), never Quote
            # Exclude "Consumidor Final" rows — they are extensions, not the main trip
            raw_status_csv = row[5].strip() if len(row) > 5 else ""
            is_booking_row = raw_status_csv in ("OK", "FI")
            is_cancelled_row = raw_status_csv in ("RX", "XC", "XX")
            if not is_booking_row and not is_cancelled_row:
                csv_quote_tp_ids.add(tp_id)
            if client_ref_prefix and not is_consumidor_final and is_booking_row:
                csv_pax_name = row[6].strip() if len(row) > 6 else ""
                if client_ref_prefix not in csv_client_ref_to_tp:
                    csv_client_ref_to_tp[client_ref_prefix] = {"tp_id": tp_id, "name": csv_pax_name}

            if tp_id not in trips_by_tourplan:
                # 2nd pass: check Entry.tourplanId
                if tp_id in entry_tp_ids:
                    continue
                # 3rd pass: compare client_reference prefix (col 15) against stored client_reference values
                # Skip this check for "Consumidor Final" rows — they should go to csv_not_in_app
                if not is_consumidor_final and client_ref_prefix and client_ref_prefix in client_ref_set:
                    continue

                raw_status = row[5].strip() if len(row) > 5 else ""
                if raw_status in ("OK", "FI"):
                    trip_status = "Booking"
                elif raw_status in ("RX", "XC", "XX"):
                    trip_status = "Cancelado"
                else:
                    trip_status = "Quote"

                raw_pax = row[19].strip() if len(row) > 19 else ""
                try:
                    quantity_pax = int(raw_pax)
                except ValueError:
                    quantity_pax = 2
                if trip_status in ("Booking", "Cancelado") and not tp_id.startswith(("ALSI", "ALPP")):
                    raw_rent = row[20].strip() if len(row) > 20 else ""
                    raw_amount = row[21].strip() if len(row) > 21 else ""
                    csv_not_in_app.append({
                        "tp_id":            tp_id,
                        "name":             row[6].strip() if len(row) > 6 else "",
                        "client_name":      row[12].strip() if len(row) > 12 else "",
                        "contact_name":     row[13].strip() if len(row) > 13 else "",
                        "client_reference": row[14].strip() if len(row) > 14 else "",
                        "travelling_date":  row[3].strip() if len(row) > 3 else "",
                        "out_date":         row[4].strip() if len(row) > 4 else "",
                        "dh_type":          row[7].strip() if len(row) > 7 else "",
                        "vendedor_tp":      row[9].strip() if len(row) > 9 else "",
                        "operations_tp":    row[10].strip() if len(row) > 10 else "",
                        "dh_name":          row[11].strip()[3:].strip() if len(row) > 11 and row[11].strip().startswith("DH ") else (row[11].strip() if len(row) > 11 else ""),
                        "guide":            row[16].strip() if len(row) > 16 else "",
                        "status":           trip_status,
                        "quantity_pax":     quantity_pax,
                        "rent_perc_raw":    raw_rent,
                        "amount_raw":       raw_amount,
                    })
                continue

            trip = trips_by_tourplan[tp_id]
            matched_tp_ids.add(tp_id)
            updated_count += 1

            # col 4 (index 3) — travelling_date
            if len(row) > 3 and row[3].strip():
                try:
                    trip.travelling_date = datetime.strptime(row[3].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass

            # col 5 (index 4) — out_date
            if len(row) > 4 and row[4].strip():
                try:
                    trip.out_date = datetime.strptime(row[4].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass

            # col 8 (index 7) — dh_type
            if len(row) > 7:
                val = row[7].strip()
                if val in ("S", "B", "F"):
                    trip.dh_type = val

            # col 10 (index 9) — consultant_tp (Tourplan CONSULTANT code, lookup by other_tp)
            if len(row) > 9:
                val = row[9].strip()
                if val in users_by_other_tp:
                    trip.consultant_tp = users_by_other_tp[val]
                else:
                    try:
                        trip.consultant_tp = User.objects.get(username=val)
                    except User.DoesNotExist:
                        pass

            # col 11 (index 10) — operations_user (lookup by other_tp)
            if len(row) > 10:
                val = row[10].strip()
                if val in users_by_other_tp:
                    trip.operations_user = users_by_other_tp[val]
                else:
                    try:
                        trip.operations_user = User.objects.get(username=val)
                    except User.DoesNotExist:
                        pass

            # col 12 (index 11) — dh: strip "DH " prefix, store name string
            if len(row) > 11:
                val = row[11].strip()
                if val.startswith("DH "):
                    val = val[3:].strip()
                if val:
                    trip.dh = val

            # col 17 (index 16) — guide
            if len(row) > 16:
                trip.guide = row[16].strip()

            # col 21 (index 20) — rent_perc: convert "10%" or "10" → 0.10
            if len(row) > 20 and row[20].strip():
                val = row[20].strip().replace("%", "").replace(",", ".").strip()
                try:
                    trip.rent_perc = float(val) / 100
                except ValueError:
                    pass

            # col 22 (index 21) — amount
            if len(row) > 21 and row[21].strip():
                try:
                    trip.amount = round(float(row[21].strip().replace(".", "").replace(",", ".")))
                except ValueError:
                    pass

            trips_to_update.append(trip)

    # Single bulk_update instead of per-column saves
    if trips_to_update:
        Trip.objects.bulk_update(trips_to_update, [
            "travelling_date", "out_date", "dh_type",
            "consultant_tp", "operations_user", "dh",
            "guide", "rent_perc", "amount",
        ])
        # Update matching Entry amounts
        for trip in trips_to_update:
            if trip.amount:
                tp_entry = Entry.objects.filter(tourplanId=trip.tourplanId).first()
                if tp_entry:
                    tp_entry.amount = trip.amount
                    tp_entry.save()

    # Booking trips split into 3 groups based on their tourplanId vs. CSV data:
    #   group1 – no TP assigned at all
    #   group2 – has a TP that is a Quote in the CSV (should be a Booking TP)
    #   group3 – has a TP but CSV suggests a different Booking TP for same client ref
    no_tp_group1 = []
    no_tp_group2 = []
    no_tp_group3 = []
    for t in (Trip.objects.filter(status="Booking")
              .select_related("responsable_user", "client")
              .order_by("travelling_date")):
        client_ref = str(t.client_reference).strip() if t.client_reference else ""
        cr_prefix = client_ref.split("/")[0] if "/" in client_ref else client_ref
        # Skip references that are not real (n/a, -, or fewer than 6 digits)
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

    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()

    return updated_count, no_tp_group1, no_tp_group2, no_tp_group3, csv_not_in_app


# Page to load the tourplan csv
@login_required
def tourplan_files(request):

    if request.method == "POST":
        form = CsvFormTourplanFiles(request.POST, request.FILES)
        if form.is_valid():

            # Delete any stale unread files before saving the new one
            CsvFileTourplanFiles.objects.filter(read=False).delete()

            form.save()

            csv_obj = CsvFileTourplanFiles.objects.filter(read=False).last()
            updated_count, no_tp_group1, no_tp_group2, no_tp_group3, csv_not_in_app = upload_data(csv_obj)

            request.session["tp_csv_not_in_app"] = csv_not_in_app
            request.session["tp_no_tp_group1"]   = no_tp_group1
            request.session["tp_no_tp_group2"]   = no_tp_group2
            request.session["tp_no_tp_group3"]   = no_tp_group3
            request.session.modified = True

            return render(request, "intranet/tourplan_files.html", {
                "form":            form,
                "updated_count":   updated_count,
                "no_tp_group1":    no_tp_group1,
                "no_tp_group2":    no_tp_group2,
                "no_tp_group3":    no_tp_group3,
                "csv_not_in_app":  csv_not_in_app,
                "show_results_modal": True,
                "users": User.objects.all,
            })
    else:
        form = CsvFormTourplanFiles()

    pending_csv    = request.session.get("tp_csv_not_in_app", [])
    pending_group1 = request.session.get("tp_no_tp_group1", [])
    pending_group2 = request.session.get("tp_no_tp_group2", [])
    pending_group3 = request.session.get("tp_no_tp_group3", [])
    return render(request, "intranet/tourplan_files.html", {
        "form":            form,
        "csv_not_in_app":  pending_csv,
        "no_tp_group1":    pending_group1,
        "no_tp_group2":    pending_group2,
        "no_tp_group3":    pending_group3,
        "show_results_modal": bool(pending_csv or pending_group1 or pending_group2 or pending_group3),
        "users": User.objects.all,
    })


@login_required
def tourplan_db_sync(request):
    """Sync trips directly from the Tourplan SQL Server database."""
    if not request.user.isAdmin:
        return redirect("error")
    from intranet.utils import sync_from_tourplan_db
    try:
        updated_count, no_tp_group1, no_tp_group2, no_tp_group3, not_in_app = sync_from_tourplan_db()
    except Exception as e:
        return render(request, "intranet/tourplan_files.html", {
            "form": CsvFormTourplanFiles(),
            "db_sync_error": str(e),
            "users": User.objects.all,
        })

    request.session["tp_csv_not_in_app"] = not_in_app
    request.session["tp_no_tp_group1"]   = no_tp_group1
    request.session["tp_no_tp_group2"]   = no_tp_group2
    request.session["tp_no_tp_group3"]   = no_tp_group3
    request.session.modified = True

    return render(request, "intranet/tourplan_files.html", {
        "form":               CsvFormTourplanFiles(),
        "updated_count":      updated_count,
        "no_tp_group1":       no_tp_group1,
        "no_tp_group2":       no_tp_group2,
        "no_tp_group3":       no_tp_group3,
        "csv_not_in_app":     not_in_app,
        "show_results_modal": True,
        "users":              User.objects.all,
    })


@login_required
@csrf_exempt
def tourplan_create_trips(request):
    """Create selected trips from the CSV-not-in-app list stored in session."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        body = json.loads(request.body)
        selected_tp_ids = set(body.get("selected", []))
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    pending = request.session.get("tp_csv_not_in_app", [])

    users_by_other_tp  = {u.other_tp: u for u in User.objects.all() if u.other_tp}
    clients_by_name    = {c.name.strip().lower(): c for c in Client.objects.all()}
    contacts_by_name   = {c.name.strip().lower(): c for c in ClientContact.objects.all()}
    default_contact    = ClientContact.objects.filter(name="Sin Contacto").first()
    default_client     = Client.objects.filter(name="Sin Cliente").first()
    default_user       = User.objects.filter(username="SD").first()

    created = 0
    remaining = []
    unmatched_clients  = []  # {tp_id, csv_name} where no client found
    unmatched_contacts = []  # {tp_id, csv_name} where no contact found

    for row in pending:
        if row["tp_id"] not in selected_tp_ids:
            remaining.append(row)
            continue

        # ── Client matching ──────────────────────────────────────────────
        csv_client_name = row.get("client_name", "").strip()
        csv_client_lower = csv_client_name.lower()
        if csv_client_lower.startswith("consumidor final"):
            # Try exact CSV name first, then without "aliwen", then base fallback
            normalized = csv_client_lower.replace(" aliwen", "").strip()
            client = (
                clients_by_name.get(csv_client_lower)
                or clients_by_name.get(normalized)
                or clients_by_name.get("consumidor final")
                or default_client
            )
        else:
            client = clients_by_name.get(csv_client_lower)
            if not client:
                # Partial: check if any stored name contains the CSV name or vice-versa
                client = next(
                    (c for name, c in clients_by_name.items()
                     if csv_client_lower and (csv_client_lower in name or name in csv_client_lower)),
                    None
                )
            if not client:
                unmatched_clients.append({"tp_id": row["tp_id"], "csv_name": csv_client_name})
                client = default_client

        # ── Contact matching ─────────────────────────────────────────────
        csv_contact_name = row.get("contact_name", "").strip()
        csv_contact_lower = csv_contact_name.lower()
        contact = contacts_by_name.get(csv_contact_lower)
        if not contact and csv_contact_lower:
            contact = next(
                (c for name, c in contacts_by_name.items()
                 if csv_contact_lower in name or name in csv_contact_lower),
                None
            )
        if not contact:
            if csv_contact_name:
                unmatched_contacts.append({"tp_id": row["tp_id"], "csv_name": csv_contact_name})
            contact = default_contact

        # ── Users ────────────────────────────────────────────────────────
        consultant  = users_by_other_tp.get(row["vendedor_tp"])
        operations  = users_by_other_tp.get(row["operations_tp"]) or default_user

        # ── Dates ────────────────────────────────────────────────────────
        try:
            td = datetime.strptime(row["travelling_date"], "%d/%m/%Y").date() if row["travelling_date"] else date.today()
            od = datetime.strptime(row["out_date"], "%d/%m/%Y").date() if row["out_date"] else td
        except ValueError:
            td = date.today()
            od = td

        # ── Financials ───────────────────────────────────────────────────
        rent_perc = None
        raw_rent = row.get("rent_perc_raw", "")
        if raw_rent:
            try:
                rent_perc = float(raw_rent.replace("%", "").replace(",", ".").strip()) / 100
            except ValueError:
                pass

        amount = None
        raw_amount = row.get("amount_raw", "").strip()
        if raw_amount:
            try:
                amount = round(float(raw_amount.replace(".", "").replace(",", ".")))
            except ValueError:
                pass

        Trip.objects.create(
            name=row["name"] or row["tp_id"],
            tourplanId=row["tp_id"],
            status=row["status"],
            client=client,
            contact=contact,
            client_reference=row.get("client_reference", ""),
            travelling_date=td,
            out_date=od,
            starting_date=td,
            dh_type=row["dh_type"] or "Sin definir",
            dh=row["dh_name"],
            guide=row["guide"],
            consultant_tp=consultant,
            operations_user=operations,
            creation_user=request.user,
            department=request.user.department,
            quantity_pax=row["quantity_pax"],
            difficulty="1",
            rent_perc=rent_perc,
            amount=amount or 0,
        )
        created += 1

    # Update session — keep only unselected rows
    if remaining:
        request.session["tp_csv_not_in_app"] = remaining
    else:
        request.session.pop("tp_csv_not_in_app", None)
    request.session.modified = True

    return JsonResponse({
        "created":            created,
        "remaining":          len(remaining),
        "unmatched_clients":  unmatched_clients,
        "unmatched_contacts": unmatched_contacts,
    })


@login_required
def tourplan_discard_trips(request):
    """Discard all (or selected) pending CSV rows from the session."""
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            selected_tp_ids = set(body.get("selected", []))
        except (json.JSONDecodeError, KeyError):
            selected_tp_ids = set()

        if selected_tp_ids:
            pending = request.session.get("tp_csv_not_in_app", [])
            remaining = [r for r in pending if r["tp_id"] not in selected_tp_ids]
            if remaining:
                request.session["tp_csv_not_in_app"] = remaining
            else:
                request.session.pop("tp_csv_not_in_app", None)
        else:
            request.session.pop("tp_csv_not_in_app", None)
        request.session.modified = True
    return JsonResponse({"ok": True})


@login_required
@csrf_exempt
def tourplan_assign_tp(request):
    """Assign a tourplanId to Booking trips that have none, based on user selection."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        body = json.loads(request.body)
        assignments = body.get("assignments", [])  # [{trip_id, tp_id}, ...]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    assigned_trip_ids = set()
    for item in assignments:
        tp_id = item.get("tp_id", "").strip()
        if not tp_id:
            continue
        try:
            trip = Trip.objects.get(id=item["trip_id"])
            trip.tourplanId = tp_id
            trip.save()
            assigned_trip_ids.add(str(item["trip_id"]))
        except Trip.DoesNotExist:
            pass

    # Remove assigned trips from all 3 session groups
    for key in ("tp_no_tp_group1", "tp_no_tp_group2", "tp_no_tp_group3"):
        pending = request.session.get(key, [])
        remaining = [r for r in pending if str(r["trip_id"]) not in assigned_trip_ids]
        if remaining:
            request.session[key] = remaining
        else:
            request.session.pop(key, None)
    request.session.modified = True

    return JsonResponse({"assigned": len(assigned_trip_ids)})


@login_required
def booking_sheet(request):
    """Planilla de Reservas: all confirmed Tourplan bookings vs intranet."""
    if request.user.userType == "Cliente":
        return HttpResponseRedirect(reverse("index"))
    from intranet.utils import get_booking_sheet_data, booking_sheet_season_year

    current_year = booking_sheet_season_year()

    try:
        season_start = int(request.GET.get("season", current_year))
    except (ValueError, TypeError):
        season_start = current_year

    date_from = date(season_start, 5, 1).strftime("%Y%m%d")
    date_to   = date(season_start + 1, 4, 30).strftime("%Y%m%d")

    season_options = [
        {"year": y, "label": f"{y}/{y+1}", "selected": y == season_start}
        for y in range(current_year - 3, current_year + 3)
    ]

    try:
        rows = get_booking_sheet_data(date_from, date_to)
        error = None
    except Exception as e:
        rows = []
        error = str(e)

    _BS_TYPE_LABELS = {
        "FI":  "FIT's",
        "FAM": "FAM Tours",
        "GR":  "Grupales",
        "PP":  "Personal Trips",
        "SI":  "Sites",
    }
    _BS_DEFAULT_OFF = {"PP", "SI", "TE"}

    _BS_STATUS_LABELS = {
        "FI": "Final IT",
        "OK": "OK",
        "CT": "Cerrado",
    }

    seen_prefixes = sorted({r["tp_prefix"] for r in rows})
    type_filters = [
        {
            "code": p,
            "label": _BS_TYPE_LABELS.get(p, p),
            "default_on": p not in _BS_DEFAULT_OFF,
        }
        for p in seen_prefixes
    ]

    _BS_STATUS_DEFAULT_ON = {"OK", "FI", "CT"}
    seen_statuses = sorted({r["raw_status"] for r in rows})
    status_filters = [
        {"code": s, "label": _BS_STATUS_LABELS.get(s, s), "default_on": s in _BS_STATUS_DEFAULT_ON}
        for s in seen_statuses
    ]

    # Totals only count types that are on by default
    visible_rows = [r for r in rows if r["tp_prefix"] not in _BS_DEFAULT_OFF]
    total_pax = sum(r.get("num_pax") or 0 for r in visible_rows)
    total_amount = sum(int(r["amount"]) for r in visible_rows if r.get("amount"))
    total_amount_display = f"{total_amount:,}".replace(",", ".")

    import json as _json
    ventas_users = list(
        User.objects.filter(userType="Ventas", isActivated=True, department=request.user.department)
        .values("id", "username", "other_name", "color")
        .order_by("other_name")
    )
    for u in ventas_users:
        u["color"] = str(u["color"]) if u["color"] else "#6c757d"

    return render(request, "intranet/booking_sheet.html", {
        "rows": rows,
        "error": error,
        "season_label": f"{season_start}/{season_start + 1}",
        "season_options": season_options,
        "season_start": season_start,
        "total_files": len(visible_rows),
        "total_pax": total_pax,
        "total_amount": total_amount_display,
        "type_filters": type_filters,
        "status_filters": status_filters,
        "current_user_tp": (request.user.other_tp or request.user.username or "").strip(),
        "current_user_username": request.user.username or "",
        "is_admin": request.user.isAdmin,
        "ventas_users_json": _json.dumps(ventas_users),
    })


@login_required
@csrf_exempt
def booking_sheet_create(request):
    """Create a single trip from a Tourplan booking row."""
    if not request.user.isAdmin:
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)
    try:
        row = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tp_id = row.get("tp_id", "").strip()
    if not tp_id:
        return JsonResponse({"error": "No tp_id"}, status=400)

    if Trip.objects.filter(tourplanId=tp_id).exists():
        existing = Trip.objects.filter(tourplanId=tp_id).first()
        return JsonResponse({"already_exists": True, "trip_id": existing.id})

    users_by_other_tp = {u.other_tp: u for u in User.objects.all() if u.other_tp}
    clients_by_name   = {c.name.strip().lower(): c for c in Client.objects.all()}
    contacts_by_name  = {c.name.strip().lower(): c for c in ClientContact.objects.all()}
    default_contact   = ClientContact.objects.filter(name="Sin Contacto").first()
    default_client    = Client.objects.filter(name="Sin Cliente").first()
    default_user      = User.objects.filter(username="SD").first()

    csv_client_name  = row.get("client_name", "").strip()
    csv_client_lower = csv_client_name.lower()
    if csv_client_lower.startswith("consumidor final"):
        normalized = csv_client_lower.replace(" aliwen", "").strip()
        client = (
            clients_by_name.get(csv_client_lower)
            or clients_by_name.get(normalized)
            or clients_by_name.get("consumidor final")
            or default_client
        )
    else:
        client = clients_by_name.get(csv_client_lower)
        if not client:
            client = next(
                (c for name, c in clients_by_name.items()
                 if csv_client_lower and (csv_client_lower in name or name in csv_client_lower)),
                None
            )
        if not client:
            client = default_client

    csv_contact_lower = row.get("contact_name", "").strip().lower()
    contact = contacts_by_name.get(csv_contact_lower)
    if not contact and csv_contact_lower:
        contact = next(
            (c for name, c in contacts_by_name.items()
             if csv_contact_lower in name or name in csv_contact_lower),
            None
        )
    if not contact:
        contact = default_contact

    consultant  = users_by_other_tp.get(row.get("vendedor_tp", ""))
    operations  = users_by_other_tp.get(row.get("operations_tp", "")) or default_user

    try:
        td = datetime.strptime(row["travelling_date"], "%d/%m/%Y").date() if row.get("travelling_date") else date.today()
        od = datetime.strptime(row["out_date"], "%d/%m/%Y").date() if row.get("out_date") else td
    except ValueError:
        td = date.today()
        od = td

    rent_perc = None
    raw_rent = row.get("rent_perc_raw", "")
    if raw_rent:
        try:
            rent_perc = float(raw_rent.replace("%", "").replace(",", ".").strip()) / 100
        except ValueError:
            pass

    amount = None
    raw_amount = row.get("amount_raw", "").strip()
    if raw_amount:
        try:
            amount = round(float(raw_amount.replace(".", "").replace(",", ".")))
        except ValueError:
            pass

    trip = Trip.objects.create(
        name=row.get("name") or tp_id,
        tourplanId=tp_id,
        status="Booking",
        client=client,
        contact=contact,
        client_reference=row.get("client_reference", ""),
        travelling_date=td,
        out_date=od,
        starting_date=td,
        dh_type=row.get("dh_type") or "Sin definir",
        dh=row.get("dh_name", ""),
        guide=row.get("guide", ""),
        consultant_tp=consultant,
        operations_user=operations,
        creation_user=request.user,
        department=request.user.department,
        quantity_pax=int(row.get("quantity_pax") or 2),
        difficulty="1",
        rent_perc=rent_perc,
        amount=amount or 0,
    )
    return JsonResponse({"created": True, "trip_id": trip.id})


@login_required
@csrf_exempt
def booking_sheet_set_vr(request):
    """Admin-only: set or clear responsable_user on a Trip from the booking sheet."""
    if not request.user.isAdmin:
        return JsonResponse({"error": "No autorizado"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    import json as _json
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    trip_id = data.get("trip_id")
    user_id = data.get("user_id")
    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        return JsonResponse({"error": "Trip no encontrado"}, status=404)

    if user_id:
        try:
            vr_user = User.objects.get(id=user_id)
            trip.responsable_user = vr_user
        except User.DoesNotExist:
            return JsonResponse({"error": "Usuario no encontrado"}, status=404)
    else:
        trip.responsable_user = None

    trip.save(update_fields=["responsable_user"])
    vr_data = None
    if trip.responsable_user:
        vr_data = {
            "id": trip.responsable_user.id,
            "username": trip.responsable_user.username,
            "color": str(trip.responsable_user.color) if trip.responsable_user.color else "#6c757d",
        }
    return JsonResponse({"ok": True, "vr": vr_data})


@login_required
@csrf_exempt
def booking_sheet_auto_assign_vr(request):
    """Admin-only: auto-assign responsable_user to unassigned trips, balanced by month."""
    if not request.user.isAdmin:
        return JsonResponse({"error": "No autorizado"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    import json as _json
    from collections import Counter
    try:
        data = _json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    tp_ids = data.get("tp_ids", [])
    if not tp_ids:
        return JsonResponse({"ok": True, "assigned": 0, "assignments": []})

    ventas_users = list(User.objects.filter(
        userType="Ventas", isActivated=True, department=request.user.department
    ))
    if not ventas_users:
        return JsonResponse({"error": "No hay usuarios de Ventas"}, status=400)

    trips_without_vr = list(
        Trip.objects.filter(tourplanId__in=tp_ids, responsable_user__isnull=True)
        .order_by("travelling_date")
    )
    if not trips_without_vr:
        return JsonResponse({"ok": True, "assigned": 0, "assignments": [], "message": "No hay files sin VR"})

    # Group by (year, month) and assign balanced within each month
    from itertools import groupby as _groupby
    user_id_map = {u.id: u for u in ventas_users}
    ventas_ids = [u.id for u in ventas_users]
    to_update = []
    assignments = []

    def _get_month(trip):
        return (trip.travelling_date.year, trip.travelling_date.month)

    trips_sorted = sorted(trips_without_vr, key=_get_month)
    for (year, month), month_trips in _groupby(trips_sorted, key=_get_month):
        month_trips = list(month_trips)
        # Count existing VRs for this month
        existing = Counter(
            Trip.objects.filter(
                travelling_date__year=year,
                travelling_date__month=month,
                responsable_user__in=ventas_users,
            ).values_list("responsable_user_id", flat=True)
        )
        counts = {uid: existing.get(uid, 0) for uid in ventas_ids}
        for trip in month_trips:
            min_uid = min(counts, key=lambda uid: counts[uid])
            user = user_id_map[min_uid]
            trip.responsable_user = user
            counts[min_uid] += 1
            to_update.append(trip)
            assignments.append({
                "trip_id": trip.id,
                "tp_id": trip.tourplanId,
                "user_id": user.id,
                "username": user.username,
                "color": str(user.color) if user.color else "#6c757d",
            })

    if to_update:
        Trip.objects.bulk_update(to_update, ["responsable_user"])

    return JsonResponse({"ok": True, "assigned": len(to_update), "assignments": assignments})


@login_required
def booking_sheet_request_vr(request):
    """Any logged-in user can request VR assignment for an intranet trip."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    import json as _json
    try:
        data = _json.loads(request.body)
        trip_id = int(data.get("trip_id"))
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        return JsonResponse({"error": "File no encontrado"}, status=404)
    if trip.responsable_user:
        return JsonResponse({"error": "El file ya tiene VR asignado"}, status=400)
    trip.vr_requested_by = request.user
    trip.save(update_fields=["vr_requested_by"])
    return JsonResponse({"ok": True, "username": request.user.username, "user_id": request.user.id})


@login_required
def booking_sheet_bulk_set_vr(request):
    """Admin-only: save checked VR assignments from the modal and send notification emails."""
    if not request.user.isAdmin:
        return JsonResponse({"error": "No autorizado"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    import json as _json
    from collections import defaultdict
    from datetime import date as _date
    from calendar import monthrange
    try:
        data = _json.loads(request.body)
        assignments = data.get("assignments", [])
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    results = []
    months_affected = set()
    for asgn in assignments:
        try:
            trip = Trip.objects.select_related("client").get(id=int(asgn["trip_id"]))
            user = User.objects.get(id=int(asgn["user_id"]))
            trip.responsable_user = user
            trip.vr_requested_by = None
            trip.save(update_fields=["responsable_user", "vr_requested_by"])
            if trip.travelling_date:
                months_affected.add((trip.travelling_date.year, trip.travelling_date.month))
            results.append({
                "trip_id": trip.id,
                "tp_id": trip.tourplanId,
                "user_id": user.id,
                "username": user.username,
                "color": str(user.color) if user.color else "#6c757d",
            })
        except Exception:
            continue

    # Send one email per VR user per affected month
    try:
        from intranet.utils import send_templated_email
        from django.conf import settings as _settings
        from django.templatetags.static import static as _static
        _static_url = getattr(_settings, "STATIC_URL", "static/")
        _site_url = getattr(_settings, "SITE_URL", "https://intranet.aliwenincoming.com")
        if isinstance(_site_url, (list, tuple)):
            _site_url = _site_url[0]
        site_url = _site_url.rstrip("/")
        icons_base_url = f"{site_url}/{_static_url.lstrip('/')}/intranet/images/"
        logo_url = f"{icons_base_url}logo.png"

        _MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

        for (yr, mo) in sorted(months_affected):
            month_start = _date(yr, mo, 1)
            last_day = monthrange(yr, mo)[1]
            month_end = _date(yr, mo, last_day)
            month_label = f"{_MESES[mo-1]} {yr}"

            month_trips = (
                Trip.objects
                .filter(
                    travelling_date__range=(month_start, month_end),
                    responsable_user__userType="Ventas",
                    responsable_user__isActivated=True,
                    responsable_user__department=request.user.department,
                )
                .select_related("responsable_user", "client", "consultant_tp")
                .order_by("travelling_date")
            )

            by_user = defaultdict(list)
            for t in month_trips:
                by_user[t.responsable_user].append(t)

            for vr_user, trips in by_user.items():
                if not vr_user.email:
                    continue
                trip_rows = []
                mismatch_trips = []
                for t in trips:
                    row = {
                        "tourplanId": t.tourplanId or "",
                        "name": t.name or "",
                        "client_name": t.client.name if t.client else "",
                        "travelling_date": t.travelling_date,
                        "quantity_pax": t.quantity_pax,
                        "amount": int(t.amount) if t.amount else None,
                        "difficulty": t.difficulty or "",
                    }
                    trip_rows.append(row)
                    # Flag files where the Tourplan consultant is a different vendedor
                    if (
                        t.consultant_tp_id
                        and t.consultant_tp_id != t.responsable_user_id
                        and t.consultant_tp.userType == "Ventas"
                    ):
                        mismatch_trips.append({
                            **row,
                            "consultant_username": t.consultant_tp.username,
                        })
                send_templated_email(
                    subject=f"Asignación VR – {month_label}",
                    to_emails=[vr_user.email],
                    template_name="emails/vr_assignment.html",
                    context={
                        "user_name": vr_user.other_name or vr_user.username,
                        "month_label": month_label,
                        "trips": trip_rows,
                        "mismatch_trips": mismatch_trips,
                        "total_files": len(trip_rows),
                        "total_pax": sum(t["quantity_pax"] for t in trip_rows),
                        "logo_url": logo_url,
                        "icons_base_url": icons_base_url,
                        "site_url": site_url,
                    },
                )
    except Exception:
        pass  # Email errors don't block the save response

    return JsonResponse({"ok": True, "assigned": len(results), "assignments": results})


@login_required
def booking_sheet_test_vr_email(request):
    """Admin-only: preview VR assignment emails (using draft state) sent to the requesting user's address."""
    if not request.user.isAdmin:
        return JsonResponse({"error": "No autorizado"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    import json as _json
    from collections import defaultdict
    from datetime import date as _date
    from calendar import monthrange
    try:
        data = _json.loads(request.body)
        month_str = data.get("month", "")
        assignments = data.get("assignments", [])  # [{trip_id, user_id}] from draft
        yr, mo = int(month_str[:4]), int(month_str[5:7])
    except Exception:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    if not assignments:
        return JsonResponse({"error": "No hay asignaciones para este mes"}, status=400)

    try:
        from intranet.utils import send_templated_email
        from django.conf import settings as _settings
        _static_url = getattr(_settings, "STATIC_URL", "static/")
        _site_url = getattr(_settings, "SITE_URL", "https://intranet.aliwenincoming.com")
        if isinstance(_site_url, (list, tuple)):
            _site_url = _site_url[0]
        site_url = _site_url.rstrip("/")
        icons_base_url = f"{site_url}/{_static_url.lstrip('/')}/intranet/images/"
        logo_url = f"{icons_base_url}logo.png"

        _MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        month_label = f"{_MESES[mo-1]} {yr}"

        # Build trip→user map from the draft assignments
        trip_ids = [int(a["trip_id"]) for a in assignments]
        user_ids = {int(a["user_id"]) for a in assignments}
        trip_user_map = {int(a["trip_id"]): int(a["user_id"]) for a in assignments}

        trips_qs = (
            Trip.objects
            .filter(id__in=trip_ids)
            .select_related("client", "consultant_tp")
            .order_by("travelling_date")
        )
        users_qs = {u.id: u for u in User.objects.filter(id__in=user_ids)}

        by_user = defaultdict(list)
        for t in trips_qs:
            uid = trip_user_map.get(t.id)
            if uid and uid in users_qs:
                by_user[users_qs[uid]].append(t)

        test_email = request.user.email
        sent = 0
        for vr_user, trips in by_user.items():
            trip_rows = []
            mismatch_trips = []
            for t in sorted(trips, key=lambda x: x.travelling_date or _date.min):
                row = {
                    "tourplanId": t.tourplanId or "",
                    "name": t.name or "",
                    "client_name": t.client.name if t.client else "",
                    "travelling_date": t.travelling_date,
                    "quantity_pax": t.quantity_pax,
                    "amount": int(t.amount) if t.amount else None,
                    "difficulty": t.difficulty or "",
                }
                trip_rows.append(row)
                if (
                    t.consultant_tp_id
                    and t.consultant_tp_id != vr_user.id
                    and t.consultant_tp.userType == "Ventas"
                ):
                    mismatch_trips.append({**row, "consultant_username": t.consultant_tp.username})
            send_templated_email(
                subject=f"[PRUEBA – {vr_user.username}] Asignación VR – {month_label}",
                to_emails=[test_email],
                template_name="emails/vr_assignment.html",
                context={
                    "user_name": vr_user.other_name or vr_user.username,
                    "month_label": month_label,
                    "trips": trip_rows,
                    "mismatch_trips": mismatch_trips,
                    "total_files": len(trip_rows),
                    "total_pax": sum(t["quantity_pax"] for t in trip_rows),
                    "logo_url": logo_url,
                    "icons_base_url": icons_base_url,
                    "site_url": site_url,
                },
            )
            sent += 1

        return JsonResponse({"ok": True, "sent": sent, "to": test_email})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def compare_ref(ref1, ref2):
    if len(ref1) >= 7 and len(ref2) >= 7:
        return ref1[:7] == ref2[:7]
    else:
        return False


def compare_name(name1, name2):
    if len(name1) >= 11 and len(name2) >= 11:
        return name1[:11] == name2[:11]
    else:
        return False


def upload_csv_intranet(csv_obj):

    user_usernames = []
    all_users = User.objects.all()
    for user in all_users:
        user_usernames.append(user.username)

    clients_names = []
    all_clients = Client.objects.all()
    for client in all_clients:
        clients_names.append(client.name)

    contact_names = []
    all_contacts = ClientContact.objects.all()
    for contact in all_contacts:
        contact_names.append(contact.name)

    # All trips
    tourplanIds = []
    all_trips = Trip.objects.all()
    for trip in all_trips:
        if trip.tourplanId != '':
            tourplanIds.append(trip.tourplanId)

    # Empty list of temp objects
    all_obj = []

    # Open the csv and read all the data
    with open(csv_obj.file_name.path, 'r') as f:
        reader = csv.reader(f, delimiter=';')

        for i, row in enumerate(reader):
            if i >= 1:
                col_number = 1
                temp_obj = {}
                for col in row:
                    if col_number == 1:
                        if col in tourplanIds:
                            break
                        else:
                            temp_obj["tourplanId"] = col
                        col_number+=1
                    elif col_number == 2:
                        temp_obj["client_reference"] = col
                        col_number+=1
                    elif col_number == 3:
                        temp_obj["name"] = col
                        col_number+=1
                    elif col_number == 4:
                        temp_obj["status"] = col
                        col_number+=1
                    elif col_number == 7:
                        temp_obj["trip_type"] = col
                        col_number+=1
                    elif col_number == 10:
                        if col == "n/a":
                            date_obj = datetime.today()
                            temp_obj["travelling_date"] = date_obj.strftime("%Y-%m-%d")
                        else:
                            date_obj = datetime.strptime(col, "%d/%m/%Y")
                            formatted_date = date_obj.strftime("%Y-%m-%d")
                            temp_obj["travelling_date"] = formatted_date
                        col_number+=1
                    elif col_number == 11:
                        if col != "":
                            temp_obj["amount"] = float(col)
                        else:
                            temp_obj["amount"] = 0
                        col_number+=1
                    elif col_number == 12:
                        client_found = False
                        for client in clients_names:
                            is_client = compare_ref(client, col)
                            if col in clients_names:
                                is_client = True
                            if is_client:
                                temp_obj["client"] = Client.objects.get(name=client)
                                client_found = True
                                col_number+=1
                        if not client_found:
                            print("Client not found, retry when it is created: ", col)
                            break
                    elif col_number == 14:
                        if col != "":
                            temp_obj["department"] = col
                        else:
                            temp_obj["department"] = "AI"
                        col_number+=1
                    else:
                        col_number+=1
                if temp_obj:
                    trip_obj = Trip.objects.create(
                        name=temp_obj["name"],
                        status=temp_obj["status"],
                        client=temp_obj["client"],
                        client_reference=temp_obj["client_reference"],
                        contact=ClientContact.objects.get(name="Sin Contacto"),
                        difficulty=1,
                        department="SH",
                        responsable_user=User.objects.get(username="SD"),
                        operations_user=User.objects.get(username="SD"),
                        dh=None,
                        creation_user=User.objects.get(username="KoalaDiana"),
                        trip_type=temp_obj["trip_type"],
                        travelling_date=temp_obj["travelling_date"],
                        tourplanId=temp_obj["tourplanId"],
                    )

                    trip_obj.save()

                    all_obj.append(trip_obj)


    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()

    return all_obj


def upload_csv_entries(csv_obj):

    user_usernames = []
    all_users = User.objects.all()
    for user in all_users:
        user_usernames.append(user.username)

    clients_names = []
    all_clients = Client.objects.all()
    for client in all_clients:
        clients_names.append(client.name)

    # All trips
    client_refs = []
    for trip in Trip.objects.all():
        if trip.client_reference == "-" or trip.client_reference == "" or trip.client_reference == "n/a":
            continue
        else:
            client_refs.append(trip.client_reference)

    # Empty list of temp objects
    all_obj = []

    # Open the csv and read all the data
    with open(csv_obj.file_name.path, 'r') as f:
        reader = csv.reader(f, delimiter=';')

        for i, row in enumerate(reader):
            if i >= 1:
                col_number = 1
                temp_obj = {}
                for col in row:
                    if col_number == 1:
                        if col != "n/a":
                            trip = Trip.objects.filter(client_reference__icontains=col).first()
                            if trip == None:
                                continue
                            temp_obj["trip"] = trip
                        else:
                            print("No reference")
                        col_number+=1
                    elif col_number == 2:
                        if row[0] == "n/a":

                            trip = Trip.objects.filter(name__icontains=col).first()
                            if trip == None:
                                print("Trip is not found by reference")
                                break

                            temp_obj["trip"] = trip
                        col_number+=1
                    elif col_number == 3:
                        temp_obj["status"] = col
                        col_number+=1
                    elif col_number == 4:
                        if col != '':
                            temp_obj["version_quote"] = col
                        else:
                            temp_obj["version_quote"] = "A"
                        col_number+=1
                    elif col_number == 5:
                        if col != '':
                            temp_obj["version"] = col
                        else:
                            temp_obj["version"] = "1"
                        col_number+=1
                    elif col_number == 7:
                        if col == "n/a":
                            date_obj = datetime.today()
                            temp_obj["starting_date"] = date_obj.strftime("%Y-%m-%d")
                        else:
                            date_obj = datetime.strptime(col, "%d/%m/%Y")
                            formatted_date = date_obj.strftime("%Y-%m-%d")
                            temp_obj["starting_date"] = formatted_date
                        col_number+=1
                    elif col_number == 8:
                        if col == "n/a":
                            date_obj = datetime.today()
                            temp_obj["closing_date"] = date_obj.strftime("%Y-%m-%d")
                            temp_obj["isClosed"] = False
                        else:
                            date_obj = datetime.strptime(col, "%d/%m/%Y")
                            formatted_date = date_obj.strftime("%Y-%m-%d")
                            temp_obj["closing_date"] = formatted_date
                            temp_obj["isClosed"] = True
                        col_number+=1
                    elif col_number == 10:
                        if col != "":
                            temp_obj["amount"] = float(col)
                        else:
                            temp_obj["amount"] = None
                        col_number+=1
                    elif col_number == 14:
                        try:
                            user = User.objects.get(username=col)
                            temp_obj["user_working"] = user
                        except User.DoesNotExist:
                            temp_obj["user_working"] = User.objects.get(username="SD")
                        col_number+=1
                    elif col_number == 15:
                        try:
                            user = User.objects.get(username=col)
                            temp_obj["user_creator"] = user
                        except User.DoesNotExist:
                            temp_obj["user_creator"] = User.objects.get(username="SD")
                        col_number+=1
                    elif col_number == 17:
                        temp_obj["note"] = col
                        col_number+=1
                    elif col_number == 17:
                        temp_obj["note"] = col
                        col_number+=1
                    else:
                        col_number+=1

                if temp_obj:
                    entry_obj = Entry.objects.create(
                        trip=temp_obj["trip"],
                        version_quote=temp_obj["version_quote"],
                        version=temp_obj["version"],
                        user_creator=temp_obj["user_creator"],
                        user_working=temp_obj["user_working"],
                        starting_date=temp_obj["starting_date"],
                        closing_date=temp_obj["closing_date"],
                        status=temp_obj["status"],
                        creation_user=User.objects.get(username="KoalaDiana"),
                        amount=temp_obj["amount"],
                        isClosed=temp_obj["isClosed"],
                        note=temp_obj["note"],
                    )

                    entry_obj.save()

                    all_obj.append(entry_obj)

    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()

    return all_obj


@login_required
def intranet_files(request):

    if request.method == "POST":
        form = CsvFormTourplanFiles(request.POST, request.FILES)
        if form.is_valid():

            form.save()

            csv_obj = CsvFileTourplanFiles.objects.get(read=False)
            #intranet_files = upload_csv_intranet(csv_obj)
            intranet_files = upload_csv_entries(csv_obj)

            return render(request, "intranet/intranet_files.html", {
                "form":form,
                "intranet_files":intranet_files,
                "users": User.objects.all,
            })
    else:
        form = CsvFormTourplanFiles()

    return render(request, "intranet/intranet_files.html", {
        "form":form,
        "users": User.objects.all,
    })

# ── Margin Management ──────────────────────────────────────────────────────────

def _trip_to_dict(t):
    from intranet.utils import strip_html
    return {
        "id": t.id,
        "name": t.name,
        "tourplanId": t.tourplanId or "",
        "travelling_date": t.travelling_date.strftime("%d/%m/%Y"),
        "quantity_pax": t.quantity_pax,
        "rent_perc_display": round((t.rent_perc or 0) * 100, 1),
        "rent_perc_low": (t.rent_perc or 0) < 0.15,
        "operations_user_name": t.operations_user.username if t.operations_user else "",
        "client_name": t.client.name if t.client else "",
        "margin_reviewed": t.margin_reviewed,
        "seller_name": t.responsable_user.username if t.responsable_user else "",
        "tp_notes": strip_html(t.tp_notes or ""),
    }


@login_required
def margin_management(request):
    from itertools import groupby
    today = date.today()

    if request.user.userType == "Internal":
        # Admin view: all Booking trips next 2 months, grouped by seller
        date_limit = today + timedelta(days=60)
        trips_qs = Trip.objects.select_related(
            "client", "operations_user", "responsable_user"
        ).filter(
            status="Booking",
            travelling_date__range=(today, date_limit),
            ignore_margin_warning=False,
        ).filter(
            Q(rent_perc__gt=0.35) | Q(rent_perc__lt=0.15)
        ).exclude(
            amount__isnull=True
        ).exclude(
            amount=0
        ).order_by("responsable_user__username", "travelling_date")

        seller_groups = []
        for seller, seller_trips in groupby(trips_qs, key=lambda t: t.responsable_user):
            trips_list = [_trip_to_dict(t) for t in seller_trips]
            seller_name = (seller.get_full_name() or seller.username) if seller else "Sin vendedor"
            seller_groups.append({"seller_name": seller_name, "trips": trips_list})

        # Ignored trips (any seller, next 2 months)
        ignored_qs = Trip.objects.select_related(
            "client", "responsable_user"
        ).filter(
            status="Booking",
            ignore_margin_warning=True,
        ).filter(
            Q(rent_perc__gt=0.35) | Q(rent_perc__lt=0.15)
        ).exclude(
            amount__isnull=True
        ).exclude(
            amount=0
        ).order_by("responsable_user__username", "travelling_date")
        ignored_trips = [_trip_to_dict(t) for t in ignored_qs]

        total = sum(len(g["trips"]) for g in seller_groups)
        reviewed = sum(1 for g in seller_groups for t in g["trips"] if t["margin_reviewed"])

        return render(request, "intranet/margin_management.html", {
            "is_admin": True,
            "seller_groups": seller_groups,
            "ignored_trips": ignored_trips,
            "total": total,
            "reviewed_count": reviewed,
        })

    else:
        # Seller view: own trips, next 12 months
        date_limit = today + timedelta(days=365)
        trips_qs = Trip.objects.select_related(
            "client", "operations_user", "responsable_user"
        ).filter(
            responsable_user=request.user,
            status="Booking",
            travelling_date__range=(today, date_limit),
            ignore_margin_warning=False,
        ).filter(
            Q(rent_perc__gt=0.35) | Q(rent_perc__lt=0.15)
        ).exclude(
            amount__isnull=True
        ).exclude(
            amount=0
        ).order_by("travelling_date")

        trips = [_trip_to_dict(t) for t in trips_qs]
        reviewed = sum(1 for t in trips if t["margin_reviewed"])

        return render(request, "intranet/margin_management.html", {
            "is_admin": False,
            "trips": trips,
            "total": len(trips),
            "reviewed_count": reviewed,
        })


@login_required
def margin_review_trip(request, trip_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        reviewed = bool(data.get("reviewed", True))
        if request.user.userType == "Internal":
            trip = Trip.objects.get(id=trip_id)
        else:
            trip = Trip.objects.get(id=trip_id, responsable_user=request.user)
        trip.margin_reviewed = reviewed
        trip.save(update_fields=["margin_reviewed"])
        return JsonResponse({"ok": True, "reviewed": reviewed})
    except Trip.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@login_required
def margin_ignore_trip(request, trip_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        if request.user.userType == "Internal":
            trip = Trip.objects.get(id=trip_id)
        else:
            trip = Trip.objects.get(id=trip_id, responsable_user=request.user)
        trip.ignore_margin_warning = True
        trip.save(update_fields=["ignore_margin_warning"])
        return JsonResponse({"ok": True})
    except Trip.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


# ── Trip Filter ────────────────────────────────────────────────────────────────

SEASON_MONTHS = [
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
]


@login_required
def trip_filter(request):
    today = date.today()
    season_start_year = today.year if today.month >= 5 else today.year - 1
    seasons = []
    for i in range(3):
        y = season_start_year + i
        seasons.append({
            "label": f"{y}/{y+1}",
            "start": f"{y}-05-01",
            "end": f"{y+1}-04-30",
            "current": i == 0,
        })
    return render(request, "intranet/filter_trips.html", {
        "seasons": seasons,
        "months": SEASON_MONTHS,
    })


@login_required
def trip_filter_clients(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    season_start = data.get("season_start")
    season_end   = data.get("season_end")
    status_list  = data.get("status_list", [])

    qs = Trip.objects.select_related("client").filter(
        department=request.user.department,
        travelling_date__range=(season_start, season_end),
    )
    if request.user.userType == "Ventas":
        qs = qs.filter(responsable_user=request.user)
    elif request.user.userType == "Operaciones":
        qs = qs.filter(operations_user=request.user)
    if status_list:
        qs = qs.filter(status__in=status_list)

    clients = (
        qs.values("client__id", "client__name")
        .distinct()
        .order_by("client__name")
    )
    return JsonResponse({
        "clients": [{"id": c["client__id"], "name": c["client__name"]} for c in clients]
    })


@login_required
def trip_filter_results(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    season_start = data.get("season_start")
    season_end   = data.get("season_end")
    status_list  = data.get("status_list", [])
    filter_type  = data.get("filter_type")   # "month" | "client" | None
    values       = data.get("values", [])

    qs = Trip.objects.select_related(
        "client", "contact", "responsable_user", "operations_user"
    ).filter(
        department=request.user.department,
        travelling_date__range=(season_start, season_end),
    )
    if request.user.userType == "Ventas":
        qs = qs.filter(responsable_user=request.user)
    elif request.user.userType == "Operaciones":
        qs = qs.filter(operations_user=request.user)
    if status_list:
        qs = qs.filter(status__in=status_list)
    if filter_type == "month" and values:
        qs = qs.filter(travelling_date__month__in=[int(m) for m in values])
    elif filter_type == "client" and values:
        qs = qs.filter(client__id__in=[int(c) for c in values])
    qs = qs.order_by("travelling_date")

    trips = list(qs)
    html = render_to_string(
        "intranet/filter_trips_results.html",
        {"trips": trips},
        request=request,
    )
    return JsonResponse({"html": html, "count": len(trips)})


# ── Email Processor ────────────────────────────────────────────────────────────

import re
import io as _io


def _parse_email_subject(subject):
    """Return (entry_status, ref_full, ref_prefix) from email subject."""
    su = subject.upper()
    if 'RECONFIRMATION' in su:
        status = 'Final Itinerary'
    elif 'BOOKING' in su:
        status = 'Booking'
    elif 'QUOTE' in su:
        status = 'Quote'
    elif 'BLOQUEO' in su or 'BLOCK' in su:
        status = 'Bloqueo'
    elif 'PROGRAMA' in su or 'PROGRAM' in su:
        status = 'Programa'
    else:
        status = 'Otro'

    # Audley pattern: "Audley 2778624/1"
    m = re.search(r'[Aa]udley\s+(\d{6,8}/\d+)', subject)
    if m:
        ref_full   = m.group(1)
        ref_prefix = ref_full.split('/')[0]
    else:
        ref_full = ref_prefix = ''

    return status, ref_full, ref_prefix


def _parse_audley_csv(content_bytes):
    """Parse Audley CSV. Extracts owner (travel agent) and first real service date.
    Audley CSVs have a metadata header section followed by a data table starting
    with a 'Date,Place,Service,...' header row. Only dates from the data table are
    considered, and Package_Item rows (the overall trip wrapper) are skipped.
    """
    text = content_bytes.decode('utf-8-sig', errors='replace')
    reader = csv.reader(_io.StringIO(text))
    rows = list(reader)

    meta = {'owner': '', 'first_date': None}
    _DATE_FMTS = ['%a %d %b %Y', '%d/%m/%Y', '%Y-%m-%d', '%d %b %Y', '%d-%b-%Y']

    in_data_section = False

    for row in rows:
        if not row:
            continue
        cells = [c.strip() for c in row]
        labels = [c.lower() for c in cells]

        # Owner detection — only in metadata section (before data table)
        if not in_data_section:
            if not meta['owner']:
                for i, lbl in enumerate(labels):
                    if 'owner' in lbl and 'business' not in lbl:
                        val = next((cells[j] for j in range(i + 1, len(cells)) if cells[j]), '')
                        if val:
                            meta['owner'] = val
                            break

            # Detect start of data table: any row that has 'date' in the first 3 cells
            if any(lbl == 'date' for lbl in labels[:3]) and len(cells) > 2:
                in_data_section = True
            continue

        # --- Inside the data table ---
        # Skip Package_Item rows (the overall trip container — not a real service)
        if any('package' in c.lower() for c in cells):
            continue

        # First parseable date in col[0] is our answer
        if not meta['first_date']:
            raw_tc = cells[0].title()
            for fmt in _DATE_FMTS:
                try:
                    meta['first_date'] = datetime.strptime(raw_tc, fmt).date()
                    break
                except ValueError:
                    pass

        if meta['owner'] and meta['first_date']:
            break

    return meta


def _find_matching_trip(ref_full, ref_prefix, passenger_name, first_date, department, is_audley=False):
    """Return (trip_or_None, match_type_str).
    If is_audley=True, only match by reference (Audley always has one; fuzzy on other clients = noise).
    """
    # Pass 1: client reference
    if ref_prefix:
        qs = Trip.objects.select_related(
            'client', 'contact', 'responsable_user', 'operations_user'
        ).filter(department=department).filter(
            Q(client_reference__contains=ref_prefix)
        )
        if qs.exists():
            return qs.first(), 'reference'

    # If Audley and reference not found, skip fuzzy — create new
    if is_audley:
        return None, None

    # Pass 2: fuzzy passenger name + date proximity (non-Audley only)
    if passenger_name and passenger_name.upper() not in ('TBD TRAVELLER 1', ''):
        date_min = (first_date - timedelta(days=45)) if first_date else date.today()
        date_max = (first_date + timedelta(days=45)) if first_date else (date.today() + timedelta(days=730))
        candidates = Trip.objects.select_related(
            'client', 'contact', 'responsable_user', 'operations_user'
        ).filter(department=department, travelling_date__range=(date_min, date_max))

        best_trip, best_ratio = None, 0.40
        for t in candidates:
            ratio = SequenceMatcher(None, passenger_name.lower(), t.name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio, best_trip = ratio, t
        if best_trip:
            return best_trip, 'nombre'

    return None, None


@login_required
def email_processor(request):
    if not request.user.isAdmin:
        return HttpResponseRedirect(reverse('index'))

    load_dotenv(override=True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_SERVER   = os.environ.get('MAIL_SERVER')

    email_cards = []
    clients = Client.objects.filter(department=request.user.department, isActivated=True).order_by('name')

    with MailBox(MAIL_SERVER).login(MAIL_USERNAME, MAIL_PASSWORD, 'Inbox') as mb:
        for msg in mb.fetch(limit=30, reverse=True, mark_seen=False):
            status, ref_full, ref_prefix = _parse_email_subject(msg.subject)

            csv_meta = None
            has_pdf  = False
            for att in msg.attachments:
                fname = (att.filename or '').lower()
                if fname.endswith('.pdf'):
                    has_pdf = True
                elif fname.endswith('.csv') and 'passenger' not in fname:
                    csv_meta = _parse_audley_csv(att.payload)

            # Use CSV ref if subject has none
            if csv_meta and not ref_full:
                ref_full   = csv_meta.get('ref', '')
                ref_prefix = ref_full.split('/')[0] if '/' in ref_full else ref_full

            # Extract sender email address
            from_raw = msg.from_ or ''
            m_addr = re.search(r'<([^>]+)>', from_raw)
            sender_email = m_addr.group(1).lower() if m_addr else from_raw.lower().strip()

            # Extract CC user: match CC addresses against internal users
            cc_user = None
            for cc_addr in (msg.cc or []):
                cc_email = cc_addr.strip().lower()
                if cc_email:
                    cc_user = User.objects.filter(email__iexact=cc_email, isActivated=True).first()
                    if cc_user:
                        break

            passenger_name = ''
            first_date     = None
            pax            = 2
            suggested_note = ''

            # Build searchable text: plain text + HTML stripped of tags (structured content is often HTML-only)
            email_text = msg.text or ''
            if msg.html:
                _html_stripped = re.sub(r'<[^>]+>', ' ', msg.html)
                _html_stripped = re.sub(r'&nbsp;', ' ', _html_stripped)
                _html_stripped = re.sub(r'\s{2,}', ' ', _html_stripped)
                email_text = email_text + '\n' + _html_stripped

            # Date: 1) from CSV
            if csv_meta:
                first_date = csv_meta.get('first_date')

            # Surname from subject (used for trip matching)
            match_surname = ''
            _ref_surname = re.search(r'[Aa]udley\s+[\d/]+\s+([A-Z][a-zA-Z\-\']+)', msg.subject)
            if _ref_surname:
                match_surname = _ref_surname.group(1).strip()

            # Full passenger name from body "Primary Traveller"
            # HTML bold tags become * in stripped text: "*Primary Traveller * Laura Jane Nicholls"
            _pt = re.search(r'\*?Primary Traveller\s*\*?\s*([^\n\*<]+)', email_text, re.IGNORECASE)
            passenger_name = _pt.group(1).strip() if _pt else match_surname

            # Pax from "Group Size"
            _gs = re.search(r'\*?Group Size\s*\*?\s*(\d+)', email_text, re.IGNORECASE)
            if _gs:
                pax = int(_gs.group(1))

            # Occasion Comment
            _oc = re.search(r'\*?Occasion Comment\s*\*?\s*(.+?)(?=\n\*|\Z)', email_text, re.IGNORECASE | re.DOTALL)
            if _oc:
                suggested_note = ' '.join(_oc.group(1).strip().split())

            # Auto-detect contact + client:
            # 1) Match CSV owner name against ClientContact (most reliable for Audley)
            # 2) Fallback: match sender email against ClientContact
            sender_client_id  = None
            sender_contact_id = None
            _owner_name = (csv_meta.get('owner', '') if csv_meta else '').strip()

            if _owner_name:
                # Try exact name, then first name, then last name
                _parts = _owner_name.split()
                _cc = (
                    ClientContact.objects.filter(name__iexact=_owner_name, isActivated=True).first()
                    or (ClientContact.objects.filter(name__icontains=_parts[-1], isActivated=True).first() if _parts else None)
                    or (ClientContact.objects.filter(name__icontains=_parts[0], isActivated=True).first() if _parts else None)
                )
                if _cc:
                    sender_contact_id = _cc.id
                    sender_client_id  = _cc.client_id

            if not sender_contact_id and sender_email:
                _cc = ClientContact.objects.filter(email__iexact=sender_email, isActivated=True).first()
                if _cc:
                    sender_contact_id = _cc.id
                    sender_client_id  = _cc.client_id

            matched_trip, match_type = _find_matching_trip(
                ref_full, ref_prefix, match_surname or passenger_name, first_date,
                request.user.department, is_audley=bool(ref_prefix),
            )

            # Suggest default user_working: CC user takes priority, then trip-based
            suggested_user_id = cc_user.id if cc_user else None
            if not suggested_user_id and matched_trip:
                if status in ('Quote', 'Booking'):
                    first_entry = Entry.objects.filter(trip=matched_trip).order_by('starting_date').first()
                    if first_entry:
                        suggested_user_id = first_entry.user_working_id
                elif status == 'Final Itinerary':
                    suggested_user_id = matched_trip.operations_user_id

            email_cards.append({
                'uid':               msg.uid,
                'subject':           msg.subject,
                'date':              msg.date,
                'from_':             msg.from_,
                'sender_email':      sender_email,
                'sender_client_id':  sender_client_id,
                'sender_contact_id': sender_contact_id,
                'text':              (msg.text or '')[:400],
                'status':            status,
                'ref_full':          ref_full,
                'ref_prefix':        ref_prefix,
                'passenger_name':    passenger_name,
                'first_date':        first_date,
                'pax':               pax,
                'has_csv':           csv_meta is not None,
                'has_pdf':           has_pdf,
                'matched_trip':      matched_trip,
                'match_type':        match_type,
                'suggested_user_id': suggested_user_id,
                'suggested_note':    suggested_note,
            })

    users = User.objects.filter(
        department=request.user.department, isActivated=True
    ).filter(Q(userType='Ventas') | Q(userType='Operaciones'))

    contacts_map = {}
    for c in ClientContact.objects.filter(isActivated=True).select_related('client'):
        cid = str(c.client_id)
        contacts_map.setdefault(cid, []).append({'id': c.id, 'name': c.name})

    return render(request, 'intranet/email_processor.html', {
        'email_cards':    email_cards,
        'users':          users,
        'clients':        clients,
        'contacts_map':   json.dumps(contacts_map),
        'importance_options': IMPORTANCE_OPTIONS,
    })


@login_required
def email_processor_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = json.loads(request.body)

    trip_id          = data.get('trip_id')
    create_new_trip  = data.get('create_new_trip', False)
    status           = data.get('status', 'Quote')
    user_working_id  = data.get('user_working_id')
    importance       = data.get('importance', '2 - BAJA - standard')
    note             = data.get('note', '')
    client_id        = data.get('client_id')
    contact_id       = data.get('contact_id')
    trip_name        = data.get('trip_name', '')
    client_reference = data.get('client_reference', '')
    travelling_date_s = data.get('travelling_date', '')
    responsable_id   = data.get('responsable_user_id')
    pax              = int(data.get('pax', 2))

    try:
        user_working = User.objects.get(id=user_working_id)

        if create_new_trip:
            client    = Client.objects.get(id=client_id)
            contact   = ClientContact.objects.get(id=contact_id)
            responsable = User.objects.get(id=responsable_id) if responsable_id else user_working
            t_date    = datetime.strptime(travelling_date_s, '%Y-%m-%d').date() if travelling_date_s else date.today()

            trip = Trip.objects.create(
                name=trip_name,
                status='Quote',
                difficulty='1',
                amount=None,
                client=client,
                client_reference=client_reference,
                starting_date=date.today(),
                travelling_date=t_date,
                out_date=t_date,
                contact=contact,
                department=request.user.department,
                tourplanId='',
                trip_type="FIT's",
                responsable_user=responsable,
                operations_user=user_working,
                quantity_pax=pax,
                rent_perc=0,
                creation_user=request.user,
            )
        else:
            trip = Trip.objects.get(id=trip_id)

        # Replicate create_entry version logic
        first_entry  = Entry.objects.filter(trip=trip).last()
        now          = datetime.now()

        if status == 'Quote':
            version_quote = chr(ord(trip.version_quote) + 1)
            version       = trip.version
            user_creator  = user_working
            trip.version_quote = version_quote
        elif status == 'Booking':
            if trip.version == 0:
                trip.conversion_date = now
                trip.status = 'Booking'
            user_creator  = first_entry.user_working if first_entry else user_working
            if first_entry:
                trip.user_creator = user_creator
            version       = int(trip.version) + 1
            version_quote = trip.version_quote
            trip.version += 1
        elif status == 'Final Itinerary':
            version       = 1
            user_creator  = trip.responsable_user
            version_quote = trip.version_quote
        else:
            version_quote = '@'
            version       = 1
            user_creator  = user_working

        trip.save()

        new_entry = Entry.objects.create(
            trip=trip,
            starting_date=now,
            status=status,
            importance=importance,
            user_working=user_working,
            user_creator=user_creator,
            version_quote=version_quote,
            version=version,
            progress=PROGRESS_OPTIONS[0][0],
            amount=0,
            creation_user=request.user,
            note=note,
        )

        return JsonResponse({'ok': True, 'entry_id': new_entry.id, 'trip_id': trip.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def email_processor_search_trips(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'trips': []})
    trips = Trip.objects.filter(department=request.user.department).filter(
        Q(name__icontains=q) | Q(client_reference__icontains=q)
    ).select_related('client').exclude(
        status__in=['Cancelado', 'Void']
    ).order_by('-travelling_date')[:15]
    return JsonResponse({'trips': [
        {
            'id':     t.id,
            'name':   t.name,
            'client': str(t.client),
            'date':   t.travelling_date.strftime('%d/%m/%Y') if t.travelling_date else '—',
            'ref':    t.client_reference or '—',
            'status': t.status,
        }
        for t in trips
    ]})


def _gmail_archive(mb, uids):
    """
    Move messages to the Gmail 'All Mail' folder (archives them from INBOX).
    Detects the correct folder name by looking for the \\All special-use flag,
    since the name varies by account language (e.g. '[Gmail]/Todos los mensajes').
    Falls back to marking as read if the folder cannot be found.
    """
    all_mail_folder = None
    try:
        for f in mb.folder.list():
            flags = getattr(f, 'flags', ()) or ()
            if '\\All' in flags or '\\AllMail' in flags:
                all_mail_folder = f.name
                break
        if not all_mail_folder:
            for f in mb.folder.list():
                name_lower = (f.name or '').lower()
                if 'all mail' in name_lower or 'todos' in name_lower or 'all messages' in name_lower:
                    all_mail_folder = f.name
                    break
    except Exception:
        pass

    if all_mail_folder:
        mb.move(uids, all_mail_folder)
    else:
        mb.flag(uids, ['\\Seen'], True)


@login_required
def email_processor_archive(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = json.loads(request.body)
    uid  = data.get('uid')
    if not uid:
        return JsonResponse({'ok': True})

    load_dotenv(override=True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_SERVER   = os.environ.get('MAIL_SERVER')

    try:
        with MailBox(MAIL_SERVER).login(MAIL_USERNAME, MAIL_PASSWORD, 'Inbox') as mb:
            if 'gmail' in (MAIL_SERVER or '').lower():
                _gmail_archive(mb, [uid])
            else:
                try:
                    mb.move([uid], 'Archive')
                except Exception:
                    mb.flag([uid], ['\\Seen'], True)
    except Exception:
        pass  # archiving is non-fatal

    return JsonResponse({'ok': True})


# ── CALIDAD ──────────────────────────────────────────────────────────────────

ITINERARIO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'media', 'itinerarios', 'itinerarios.csv')
QUALITY_LABEL   = 'Calidad'


@login_required
def calidad_fetch_inbox(request):
    """Fetch new emails from the Calidad mailbox label and import as FeedbackInboxItem."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    load_dotenv(override=True)
    username = os.environ.get('MAIL_USERNAME')
    password = os.environ.get('MAIL_PASSWORD')
    server   = os.environ.get('MAIL_SERVER')

    if not all([username, password, server]):
        return JsonResponse({'error': 'Faltan variables de entorno de correo'}, status=500)

    from tariff.models import FeedbackInboxItem
    import re as _re
    from datetime import timezone as _tz

    def _get_message_id(msg):
        raw = msg.headers.get('message-id') or msg.headers.get('Message-ID') or []
        if isinstance(raw, list) and raw:
            return raw[0].strip()
        if isinstance(raw, str):
            return raw.strip()
        return f'uid-{msg.uid}'

    def _get_body(msg):
        if msg.text:
            return msg.text.strip()
        return ''

    def _clean_subject(s):
        """Decode literal \\uXXXX escapes that imap_tools emits for unusual header encodings."""
        if not s:
            return ''
        s = _re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
        # Strip control characters (but keep normal whitespace)
        s = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
        return s.strip()

    imported = 0
    skipped  = 0
    try:
        with MailBox(server).login(username, password, 'INBOX') as mb:
            to_archive = []
            # Gmail: fetch only inbox messages that carry the Calidad label
            label_criterion = f'X-GM-LABELS "{QUALITY_LABEL}"' if 'gmail' in (server or '').lower() else 'ALL'
            for msg in mb.fetch(label_criterion, mark_seen=False, bulk=True):
                message_id = _get_message_id(msg)
                if FeedbackInboxItem.objects.filter(gmail_message_id=message_id).exists():
                    # Already imported — archive it anyway so it leaves the inbox
                    to_archive.append(msg.uid)
                    skipped += 1
                    continue
                from_raw = msg.from_ or ''
                m = _re.search(r'<([^>]+)>', from_raw)
                sender = m.group(1).lower() if m else from_raw.lower().strip()
                received_at = msg.date
                if received_at and received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=_tz.utc)
                try:
                    FeedbackInboxItem.objects.create(
                        received_at=received_at,
                        email_subject=_clean_subject(msg.subject),
                        email_body=_get_body(msg),
                        email_sender=sender,
                        gmail_label='INBOX',
                        gmail_message_id=message_id,
                        status='pendiente',
                    )
                    imported += 1
                    to_archive.append(msg.uid)
                except Exception:
                    pass
            # Archive all processed messages (move to All Mail = removes from inbox)
            if to_archive:
                try:
                    _gmail_archive(mb, to_archive)
                except Exception:
                    pass
    except Exception as e:
        return JsonResponse({'error': f'Error al conectar al buzón: {e}'}, status=500)

    # Auto-process new items with AI
    ai_ok, ai_err = 0, 0
    if imported > 0:
        from tariff.quality_ai import process_all_pending
        ai_ok, ai_err = process_all_pending()

    return JsonResponse({'ok': True, 'imported': imported, 'skipped': skipped, 'ai_ok': ai_ok, 'ai_err': ai_err})


@login_required
@login_required
def calidad_open_trips_json(request):
    """Return open quality entries grouped by trip with their negative feedbacks."""
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Feedback
    entries = (
        Entry.objects
        .filter(status='Queja', isClosed=False)
        .select_related('trip', 'user_working')
        .order_by('-starting_date')
    )
    result = []
    for entry in entries:
        fbs = list(
            Feedback.objects.filter(trip=entry.trip, sentiment='negativo')
            .select_related('supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity')
            .order_by('creation_date')
        )
        fb_rows = []
        all_closed = True
        for fb in fbs:
            missing = []
            if not (fb.solution or '').strip(): missing.append('solución')
            if not fb.cost:                     missing.append('costo')
            if fb.status != 'cerrado':          all_closed = False
            fb_rows.append({
                'id':            fb.id,
                'objective':     fb.target_display(),
                'brief_summary': fb.brief_summary or '',
                'solution':      fb.solution or '',
                'cost':          float(fb.cost) if fb.cost else 0,
                'status':        fb.status,
                'missing':       missing,
            })
        trip = entry.trip
        result.append({
            'entry_id':    entry.id,
            'trip_id':     trip.id,
            'trip_name':   trip.name,
            'tourplan_id': trip.tourplanId or '',
            'pax':         trip.quantity_pax,
            'travel_date': trip.travelling_date.strftime('%d/%m/%Y') if trip.travelling_date else '',
            'responsable': (entry.user_working.other_name or entry.user_working.username) if entry.user_working else '',
            'all_closed':  all_closed and bool(fb_rows),
            'feedbacks':   fb_rows,
        })
    return JsonResponse({'trips': result})


@login_required
def calidad_close_trip(request, trip_id):
    """Close all negative feedbacks for a trip + quality Entry + send closure notification."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    from tariff.models import Feedback
    from intranet.utils import send_quality_closure_notification
    from django.utils import timezone as tz

    entry = Entry.objects.filter(trip_id=trip_id, status='Queja', isClosed=False).first()
    if not entry:
        return JsonResponse({'error': 'No hay gestión abierta para este viaje'}, status=404)

    feedbacks = list(
        Feedback.objects.filter(trip_id=trip_id, sentiment='negativo')
        .select_related('supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity')
    )

    incomplete = []
    for fb in feedbacks:
        missing = []
        if not (fb.solution or '').strip(): missing.append('solución')
        if not fb.cost:                     missing.append('costo')
        if fb.status != 'cerrado':          missing.append('estado cerrado')
        if missing:
            incomplete.append({'objective': fb.target_display(), 'missing': missing})

    if incomplete:
        return JsonResponse({'error': 'incomplete', 'incomplete': incomplete}, status=400)

    entry.isClosed     = True
    entry.closing_date = tz.now()
    entry.progress     = PROGRESS_OPTIONS[-1][0]
    entry.save(update_fields=['isClosed', 'closing_date', 'progress'])

    try:
        send_quality_closure_notification(entry, feedbacks)
    except Exception:
        pass

    return JsonResponse({'success': True})


def calidad_check_close_replies(request):
    """Thin wrapper — delegates to utils.run_quality_close_check()."""
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from intranet.utils import run_quality_close_check
    result = run_quality_close_check()
    if 'error' in result and not result.get('processed'):
        return JsonResponse({'error': result['error']}, status=500)
    return JsonResponse({'ok': True, **result})


@login_required
def calidad_send_followups(request):
    """Thin wrapper — delegates to utils.run_quality_followups()."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from intranet.utils import run_quality_followups
    return JsonResponse(run_quality_followups())


@login_required
def calidad_close_quality_entry(request, entry_id):
    """Manually close a quality entry and send closure notification."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    from django.utils import timezone
    from tariff.models import Feedback
    from intranet.utils import send_quality_closure_notification

    try:
        entry = Entry.objects.select_related('trip', 'user_working').get(pk=entry_id)
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'Entry not found'}, status=404)

    feedbacks = list(
        Feedback.objects.filter(
            trip=entry.trip, sentiment='negativo'
        ).select_related('supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity')
    )

    # Validate: every negative feedback must have solution and cost before closing
    incomplete = []
    for fb in feedbacks:
        missing = []
        if not (fb.solution or '').strip():
            missing.append('solución')
        if not fb.cost:
            missing.append('costo')
        if missing:
            incomplete.append({'objective': fb.target_display(), 'missing': missing})

    if incomplete:
        return JsonResponse({'error': 'incomplete', 'incomplete': incomplete}, status=400)

    from django.utils import timezone as tz
    entry.isClosed = True
    entry.closing_date = tz.now()
    entry.progress = PROGRESS_OPTIONS[-1][0]
    entry.save(update_fields=['isClosed', 'closing_date', 'progress'])

    try:
        send_quality_closure_notification(entry, feedbacks)
    except Exception:
        pass

    return JsonResponse({'success': True})


@login_required
def calidad(request):
    if not request.user.isAdmin:
        return HttpResponseRedirect(reverse('index'))

    from tariff.models import FeedbackInboxItem, Feedback, TYPE_QUALITY, FeedbackEntity, Supplier
    from intranet.models import IMPORTANCE_OPTIONS, Driver
    from django.db.models import Count

    inbox_items = list(FeedbackInboxItem.objects.filter(status='pendiente').order_by('-received_at'))
    feedbacks_qs = Feedback.objects.select_related(
        'supplier', 'supplier__group', 'supplier__group__location',
        'trip', 'target_user',
        'target_guide', 'target_guide__location',
        'target_dh', 'target_dh__location',
        'target_driver', 'target_driver__location',
        'target_entity',
        'responsable',
    ).order_by('-creation_date')
    feedbacks_open_count = feedbacks_qs.exclude(status='cerrado').count()
    feedbacks_total = feedbacks_qs.count()
    from django.db.models import Q
    entities = FeedbackEntity.objects.annotate(
        pos_count=Count('feedback_entities', filter=Q(feedback_entities__sentiment='positivo')),
        neu_count=Count('feedback_entities', filter=Q(feedback_entities__sentiment='neutral')),
        neg_count=Count('feedback_entities', filter=Q(feedback_entities__sentiment='negativo')),
        feedback_count=Count('feedback_entities'),
    ).order_by('name')
    guides = Guide.objects.annotate(
        pos_count=Count('feedback_guides', filter=Q(feedback_guides__sentiment='positivo'), distinct=True),
        neu_count=Count('feedback_guides', filter=Q(feedback_guides__sentiment='neutral'), distinct=True),
        neg_count=Count('feedback_guides', filter=Q(feedback_guides__sentiment='negativo'), distinct=True),
    ).order_by('name')
    dhs = DestinationHost.objects.annotate(
        pos_count=Count('feedback_dhs', filter=Q(feedback_dhs__sentiment='positivo'), distinct=True),
        neu_count=Count('feedback_dhs', filter=Q(feedback_dhs__sentiment='neutral'), distinct=True),
        neg_count=Count('feedback_dhs', filter=Q(feedback_dhs__sentiment='negativo'), distinct=True),
    ).order_by('name')
    suppliers_fb = Supplier.objects.annotate(
        pos_count=Count('feedback_suppliers', filter=Q(feedback_suppliers__sentiment='positivo')),
        neu_count=Count('feedback_suppliers', filter=Q(feedback_suppliers__sentiment='neutral')),
        neg_count=Count('feedback_suppliers', filter=Q(feedback_suppliers__sentiment='negativo')),
        feedback_count=Count('feedback_suppliers'),
    ).filter(feedback_count__gt=0).order_by('-feedback_count')
    users_fb = User.objects.annotate(
        pos_count=Count('feedback_targets', filter=Q(feedback_targets__sentiment='positivo')),
        neu_count=Count('feedback_targets', filter=Q(feedback_targets__sentiment='neutral')),
        neg_count=Count('feedback_targets', filter=Q(feedback_targets__sentiment='negativo')),
        feedback_count=Count('feedback_targets'),
    ).filter(feedback_count__gt=0).order_by('-feedback_count')

    itinerario_exists = os.path.exists(ITINERARIO_PATH)
    itinerario_date   = None
    if itinerario_exists:
        import datetime as _dt
        itinerario_date = _dt.datetime.fromtimestamp(os.path.getmtime(ITINERARIO_PATH)).strftime('%d/%m/%Y %H:%M')

    from tariff.models import Location
    locations = Location.objects.all().order_by('name')

    internal_users = User.objects.filter(
        isActivated=True,
        show_in_calendar=True,
        userType__in=['Ventas', 'Operaciones', 'Manager'],
    ).order_by('other_name')

    # Pre-resolve trip responsable for each inbox item (single bulk query)
    trip_fids = [
        (item.ai_analysis or {}).get('trip_file_id', '')
        for item in inbox_items
    ]
    from intranet.models import Trip
    trip_resp_map = {
        t.tourplanId.upper(): t.responsable_user_id
        for t in Trip.objects.filter(tourplanId__in=[f for f in trip_fids if f])
    }
    for item in inbox_items:
        fid = (item.ai_analysis or {}).get('trip_file_id', '')
        item.default_responsable_id = trip_resp_map.get(fid.upper()) if fid else None

    drivers = Driver.objects.select_related('supplier').annotate(
        pos_count=Count('feedback_drivers', filter=Q(feedback_drivers__sentiment='positivo'), distinct=True),
        neu_count=Count('feedback_drivers', filter=Q(feedback_drivers__sentiment='neutral'), distinct=True),
        neg_count=Count('feedback_drivers', filter=Q(feedback_drivers__sentiment='negativo'), distinct=True),
    ).order_by('name')

    # Build a map from trip_id → open quality Entry id for the "Cerrar gestión" button
    quality_entries_qs = Entry.objects.filter(
        status='Queja', isClosed=False
    ).values('id', 'trip_id')
    trip_to_quality_entry = {e['trip_id']: e['id'] for e in quality_entries_qs}

    return render(request, 'intranet/calidad.html', {
        'inbox_items':          inbox_items,
        'feedbacks':            feedbacks_qs,
        'feedbacks_open_count': feedbacks_open_count,
        'feedbacks_total':      feedbacks_total,
        'entities':             entities,
        'guides':               guides,
        'dhs':                  dhs,
        'drivers':              drivers,
        'locations':            locations,
        'suppliers_fb':         suppliers_fb,
        'users_fb':             users_fb,
        'itinerario_exists':    itinerario_exists,
        'itinerario_date':      itinerario_date,
        'type_quality_choices':   TYPE_QUALITY,
        'internal_users':         internal_users,
        'importance_options':     IMPORTANCE_OPTIONS,
        'trip_to_quality_entry':  trip_to_quality_entry,
    })


@login_required
def calidad_upload_itinerario(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    f = request.FILES.get('itinerario')
    if not f:
        return JsonResponse({'error': 'No file'}, status=400)

    if not f.name.lower().endswith('.csv'):
        return JsonResponse({'error': 'Solo se aceptan archivos CSV'}, status=400)

    os.makedirs(os.path.dirname(ITINERARIO_PATH), exist_ok=True)
    with open(ITINERARIO_PATH, 'wb+') as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    import datetime as _dt
    uploaded_date = _dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    return JsonResponse({'ok': True, 'date': uploaded_date, 'filename': f.name})


@login_required
def calidad_discard_inbox(request, item_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackInboxItem
    try:
        item = FeedbackInboxItem.objects.get(pk=item_id)
        item.status = 'descartado'
        item.save(update_fields=['status'])
        return JsonResponse({'ok': True})
    except FeedbackInboxItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def calidad_process_ai(request, item_id):
    """Run AI analysis on a single FeedbackInboxItem and return the result."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackInboxItem
    from tariff.quality_ai import process_inbox_item_with_ai, try_match_supplier, try_match_trip
    try:
        item = FeedbackInboxItem.objects.get(pk=item_id, status='pendiente')
        analysis = process_inbox_item_with_ai(item)
        supplier = try_match_supplier(analysis.get('supplier_name'))
        trip     = try_match_trip(analysis.get('trip_file_id'))
        return JsonResponse({
            'ok': True,
            'analysis': analysis,
            'supplier_matched': supplier.name if supplier else None,
            'supplier_id':      supplier.id   if supplier else None,
            'trip_matched':     trip.name     if trip     else None,
            'trip_id':          trip.id       if trip     else None,
        })
    except FeedbackInboxItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def calidad_confirm_inbox(request, item_id):
    """Confirm an AI-analyzed inbox item, creating one Feedback per target."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackInboxItem
    from tariff.quality_ai import create_feedbacks_from_inbox
    try:
        item = FeedbackInboxItem.objects.get(pk=item_id, status='pendiente')
        data = json.loads(request.body)
        confirmed_targets = data.get('targets', [])
        overrides = {k: v for k, v in data.items() if k != 'targets'}
        feedbacks, entry_created, entry_missing = create_feedbacks_from_inbox(item, confirmed_targets, overrides=overrides)
        return JsonResponse({'ok': True, 'created': len(feedbacks), 'entry_created': entry_created, 'entry_missing': entry_missing})
    except FeedbackInboxItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Calidad: search endpoints ─────────────────────────────────────────────────

@login_required
def calidad_feedbacks_by_target(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    target_type = request.GET.get('type', '')
    target_id   = request.GET.get('id', '')
    if not target_type or not target_id:
        return JsonResponse({'error': 'Missing params'}, status=400)
    from tariff.models import Feedback
    filter_map = {
        'guide':    {'target_guide_id': target_id},
        'dh':       {'target_dh_id': target_id},
        'supplier': {'supplier_id': target_id},
        'user':     {'target_user_id': target_id},
        'chofer':   {'target_driver_id': target_id},
        'entity':   {'target_entity_id': target_id},
    }
    if target_type not in filter_map:
        return JsonResponse({'error': 'Invalid type'}, status=400)
    fbs = (Feedback.objects.filter(**filter_map[target_type])
           .select_related('trip', 'user').order_by('-creation_date'))
    result = []
    for fb in fbs:
        result.append({
            'id': fb.id,
            'sentiment': fb.sentiment,
            'brief_summary': fb.brief_summary or '',
            'content': fb.content or '',
            'verbatim': fb.verbatim or '',
            'solution': fb.solution or '',
            'cost': float(fb.cost) if fb.cost else 0,
            'status': fb.status,
            'type': fb.type or '',
            'source': fb.source or '',
            'email_sender': fb.email_sender or '',
            'user': fb.user.get_full_name() or fb.user.username if fb.user else '',
            'creation_date': fb.creation_date.strftime('%d/%m/%Y') if fb.creation_date else '',
            'last_modification_date': fb.last_modification_date.strftime('%d/%m/%Y') if fb.last_modification_date else '',
            'trip_tourplan': fb.trip.tourplanId if fb.trip else '',
            'trip_name': fb.trip.name if fb.trip else '',
        })
    return JsonResponse({'feedbacks': result})

@login_required
def calidad_search_guides(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    qs = Guide.objects.select_related('location').filter(name__icontains=q) if q else Guide.objects.select_related('location').all()
    results = [{'id': g.id, 'name': g.name, 'notes': g.notes, 'location_id': g.location_id, 'location_name': g.location.name if g.location else ''} for g in qs[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_search_dhs(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    qs = DestinationHost.objects.select_related('location').filter(name__icontains=q) if q else DestinationHost.objects.select_related('location').all()
    results = [{'id': d.id, 'name': d.name, 'location_id': d.location_id, 'location_name': d.location.name if d.location else ''} for d in qs[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_create_guide(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Location
    data = json.loads(request.body)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    location_id = data.get('location_id') or None
    location = Location.objects.filter(pk=location_id).first() if location_id else None
    guide, created = Guide.objects.get_or_create(name=name, defaults={'notes': data.get('notes', ''), 'location': location})
    return JsonResponse({'ok': True, 'id': guide.id, 'name': guide.name, 'created': created,
                         'location_id': guide.location_id, 'location_name': guide.location.name if guide.location else ''})


@login_required
def calidad_create_dh(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Location
    data = json.loads(request.body)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    location_id = data.get('location_id') or None
    location = Location.objects.filter(pk=location_id).first() if location_id else None
    dh, created = DestinationHost.objects.get_or_create(name=name, defaults={'location': location, 'notes': data.get('notes', '')})
    return JsonResponse({'ok': True, 'id': dh.id, 'name': dh.name, 'created': created,
                         'location_id': dh.location_id, 'location_name': dh.location.name if dh.location else ''})


@login_required
def calidad_delete_guide(request, guide_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        g = Guide.objects.get(pk=guide_id)
        if g.feedback_guides.exists() or g.trips.exists():
            return JsonResponse({'error': 'Tiene feedbacks o viajes asociados, no se puede eliminar'}, status=400)
        g.delete()
        return JsonResponse({'ok': True})
    except Guide.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def calidad_delete_dh(request, dh_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        d = DestinationHost.objects.get(pk=dh_id)
        if d.feedback_dhs.exists() or d.trips.exists():
            return JsonResponse({'error': 'Tiene feedbacks o viajes asociados, no se puede eliminar'}, status=400)
        d.delete()
        return JsonResponse({'ok': True})
    except DestinationHost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def calidad_edit_guide(request, guide_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Location
    try:
        g = Guide.objects.get(pk=guide_id)
    except Guide.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    g.name = (data.get('name') or g.name).strip()
    g.email = data.get('email', g.email).strip()
    g.notes = data.get('notes', g.notes).strip()
    location_id = data.get('location_id') or None
    g.location = Location.objects.filter(pk=location_id).first() if location_id else None
    g.save()
    return JsonResponse({'ok': True, 'id': g.id, 'name': g.name,
                         'location_id': g.location_id, 'location_name': g.location.name if g.location else ''})


@login_required
def calidad_edit_dh(request, dh_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Location
    try:
        d = DestinationHost.objects.get(pk=dh_id)
    except DestinationHost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    d.name = (data.get('name') or d.name).strip()
    d.email = data.get('email', d.email).strip()
    d.notes = data.get('notes', d.notes).strip()
    location_id = data.get('location_id') or None
    d.location = Location.objects.filter(pk=location_id).first() if location_id else None
    d.save()
    return JsonResponse({'ok': True, 'id': d.id, 'name': d.name,
                         'location_id': d.location_id, 'location_name': d.location.name if d.location else ''})


@login_required
def calidad_search_drivers(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    qs = Driver.objects.select_related('supplier').filter(name__icontains=q) if q else Driver.objects.select_related('supplier').all()
    results = [{'id': d.id, 'name': d.name, 'notes': d.notes,
                'supplier_id': d.supplier_id, 'supplier_name': d.supplier.name if d.supplier else ''} for d in qs[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_create_driver(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    from tariff.models import Supplier
    supplier_id = data.get('supplier_id') or None
    supplier = Supplier.objects.filter(pk=supplier_id).first() if supplier_id else None
    driver, created = Driver.objects.get_or_create(
        name=name, defaults={'notes': data.get('notes', ''), 'supplier': supplier}
    )
    return JsonResponse({'ok': True, 'id': driver.id, 'name': driver.name, 'created': created,
                         'supplier_id': driver.supplier_id, 'supplier_name': driver.supplier.name if driver.supplier else ''})


@login_required
def calidad_delete_driver(request, driver_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        d = Driver.objects.get(pk=driver_id)
        if d.feedback_drivers.exists():
            return JsonResponse({'error': 'Tiene feedbacks asociados, no se puede eliminar'}, status=400)
        d.delete()
        return JsonResponse({'ok': True})
    except Driver.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def calidad_edit_driver(request, driver_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        d = Driver.objects.select_related('supplier').get(pk=driver_id)
    except Driver.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    d.name = (data.get('name') or d.name).strip()
    d.email = data.get('email', d.email).strip()
    d.notes = data.get('notes', d.notes).strip()
    if 'supplier_id' in data:
        from tariff.models import Supplier
        sid = data.get('supplier_id') or None
        d.supplier = Supplier.objects.filter(pk=sid).first() if sid else None
    d.save()
    return JsonResponse({'ok': True, 'id': d.id, 'name': d.name,
                         'supplier_id': d.supplier_id, 'supplier_name': d.supplier.name if d.supplier else ''})


@login_required
def calidad_search_suppliers(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Supplier
    from tariff.quality_ai import _supplier_score
    q = request.GET.get('q', '').strip()
    if not q:
        results = [{'id': s.id, 'name': s.name, 'provisional': s.is_provisional}
                   for s in Supplier.objects.order_by('is_provisional', 'name')[:30]]
        return JsonResponse({'results': results})

    # First try DB-level contains (fast)
    db_matches = list(Supplier.objects.filter(name__icontains=q).order_by('is_provisional', 'name')[:30])

    # Then score ALL suppliers with the accent/noise-aware scorer
    scored = []
    seen_ids = {s.id for s in db_matches}
    for s in Supplier.objects.all():
        if s.id in seen_ids:
            continue
        score = _supplier_score(q, s.name)
        if score >= 1:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])

    combined = db_matches + [s for _, s in scored]
    results = [{'id': s.id, 'name': s.name, 'provisional': s.is_provisional}
               for s in combined[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_create_supplier(request):
    """Create a provisional Supplier (no group, minimal fields)."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Supplier
    data = json.loads(request.body)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    s, created = Supplier.objects.get_or_create(
        name=name, is_provisional=True,
        defaults={
            'code': '', 'children_ranking': 1, 'disabled_ranking': 1,
            'sustentability_ranking': 1, 'order': 9999,
            'margin': 0, 'margin_info': 'Regular', 'group': None, 'note': '',
        }
    )
    return JsonResponse({'ok': True, 'id': s.id, 'name': s.name, 'created': created, 'provisional': True})


@login_required
def calidad_resolve_provisional(request):
    """Move feedbacks from a provisional supplier to a real one, then delete provisional."""
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Supplier, Feedback
    data = json.loads(request.body)
    prov_id = data.get('provisional_id')
    real_id = data.get('real_id')
    try:
        prov = Supplier.objects.get(pk=prov_id, is_provisional=True)
        real = Supplier.objects.get(pk=real_id)
        count = Feedback.objects.filter(supplier=prov).update(supplier=real)
        prov.delete()
        return JsonResponse({'ok': True, 'feedbacks_moved': count})
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)


@login_required
def calidad_edit_feedback(request, feedback_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Feedback
    try:
        fb = Feedback.objects.get(pk=feedback_id)
    except Feedback.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    if 'brief_summary' in data:
        fb.brief_summary = data['brief_summary']
    if 'content' in data:
        fb.content = data['content']
    if 'solution' in data:
        fb.solution = data['solution']
    if 'cost' in data:
        try:
            fb.cost = float(data['cost']) if data['cost'] not in (None, '') else 0
        except (ValueError, TypeError):
            fb.cost = 0
    if 'status' in data:
        fb.status = data['status']
    if 'sentiment' in data:
        fb.sentiment = data['sentiment']
    if 'type' in data:
        fb.type = data['type']
    if 'verbatim' in data:
        fb.verbatim = data['verbatim']
    # Clear all targets first, then set only the chosen one
    target_type = data.get('target_type')
    if target_type:
        fb.supplier       = None
        fb.target_guide   = None
        fb.target_dh      = None
        fb.target_driver  = None
        fb.target_user    = None
        fb.target_entity  = None
        if target_type == 'supplier':
            sid = data.get('supplier_id')
            fb.supplier = Supplier.objects.filter(pk=sid).first() if sid else None
        elif target_type == 'guide':
            from intranet.models import Guide
            gid = data.get('guide_id')
            fb.target_guide = Guide.objects.filter(pk=gid).first() if gid else None
        elif target_type == 'dh':
            from intranet.models import DestinationHost
            dhid = data.get('dh_id')
            fb.target_dh = DestinationHost.objects.filter(pk=dhid).first() if dhid else None
        elif target_type == 'chofer':
            from intranet.models import Driver
            did = data.get('driver_id')
            fb.target_driver = Driver.objects.filter(pk=did).first() if did else None
        elif target_type == 'user':
            uid = data.get('user_id')
            fb.target_user = User.objects.filter(pk=uid).first() if uid else None
        elif target_type == 'entity':
            from tariff.models import FeedbackEntity
            eid = data.get('entity_id')
            fb.target_entity = FeedbackEntity.objects.filter(pk=eid).first() if eid else None
    else:
        # Legacy path: backwards compat for supplier/guide only
        if 'supplier_id' in data:
            sid = data['supplier_id']
            fb.supplier = Supplier.objects.filter(pk=sid).first() if sid else None
        if 'guide_id' in data:
            gid = data['guide_id']
            from intranet.models import Guide
            fb.target_guide = Guide.objects.filter(pk=gid).first() if gid else None
    if 'trip_file' in data and data['trip_file']:
        from intranet.models import Trip
        trip = Trip.objects.filter(tourplanId__iexact=data['trip_file'].strip()).first()
        if trip:
            fb.trip = trip
    if 'responsable_id' in data:
        rid = data['responsable_id']
        fb.responsable = User.objects.filter(pk=rid).first() if rid else None
    if 'priority' in data:
        fb.priority = data['priority'] or ''
    fb.save()
    return JsonResponse({'ok': True})


@login_required
def calidad_feedback_json(request, feedback_id):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Feedback
    try:
        fb = Feedback.objects.select_related(
            'supplier', 'target_guide', 'target_dh', 'target_driver', 'target_user', 'target_entity', 'trip', 'responsable'
        ).get(pk=feedback_id)
    except Feedback.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    if fb.supplier:          target_type = 'supplier'
    elif fb.target_guide:    target_type = 'guide'
    elif fb.target_dh:       target_type = 'dh'
    elif fb.target_driver:   target_type = 'chofer'
    elif fb.target_user:     target_type = 'user'
    elif fb.target_entity:   target_type = 'entity'
    else:                    target_type = 'supplier'
    return JsonResponse({
        'id': fb.id,
        'brief_summary': fb.brief_summary or '',
        'content':       fb.content or '',
        'verbatim':      fb.verbatim or '',
        'solution':      fb.solution or '',
        'cost':          fb.cost or 0,
        'status':        fb.status,
        'sentiment':     fb.sentiment,
        'type':          fb.type or '',
        'source':        fb.source or '',
        'email_sender':  fb.email_sender or '',
        'trip_file':     fb.trip.tourplanId if fb.trip else '',
        'trip_name':     fb.trip.name if fb.trip else '',
        'target_type':   target_type,
        'supplier_id':   fb.supplier_id or '',
        'supplier_name': fb.supplier.name if fb.supplier else '',
        'guide_id':      fb.target_guide_id or '',
        'guide_name':    fb.target_guide.name if fb.target_guide else '',
        'dh_id':         fb.target_dh_id or '',
        'dh_name':       fb.target_dh.name if fb.target_dh else '',
        'driver_id':     fb.target_driver_id or '',
        'driver_name':   fb.target_driver.name if fb.target_driver else '',
        'user_id':       fb.target_user_id or '',
        'user_name':     (fb.target_user.get_full_name() or fb.target_user.username) if fb.target_user else '',
        'entity_id':     fb.target_entity_id or '',
        'entity_name':   fb.target_entity.name if fb.target_entity else '',
        'responsable_id':   fb.responsable_id or '',
        'responsable_name': (fb.responsable.other_name or fb.responsable.username) if fb.responsable else '',
        'priority':         fb.priority or '',
        'creation_date':    fb.creation_date.strftime('%d/%m/%Y') if fb.creation_date else '',
    })


@login_required
def calidad_create_feedback(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Feedback, FeedbackEntity
    data = json.loads(request.body)
    target_type = data.get('target_type', 'supplier')
    supplier = target_user = target_guide = target_dh = target_driver = target_entity = None
    if target_type == 'supplier':
        sid = data.get('supplier_id')
        supplier = Supplier.objects.filter(pk=sid).first() if sid else None
    elif target_type == 'guide':
        from intranet.models import Guide
        gid = data.get('guide_id')
        target_guide = Guide.objects.filter(pk=gid).first() if gid else None
    elif target_type == 'dh':
        from intranet.models import DestinationHost
        dhid = data.get('dh_id')
        target_dh = DestinationHost.objects.filter(pk=dhid).first() if dhid else None
    elif target_type == 'chofer':
        from intranet.models import Driver
        did = data.get('driver_id')
        target_driver = Driver.objects.select_related('supplier').filter(pk=did).first() if did else None
    elif target_type == 'user':
        uid = data.get('user_id')
        target_user = User.objects.filter(pk=uid).first() if uid else None
    elif target_type == 'entity':
        eid = data.get('entity_id')
        target_entity = FeedbackEntity.objects.filter(pk=eid).first() if eid else None
    trip = None
    if data.get('trip_file'):
        from intranet.models import Trip
        trip = Trip.objects.filter(tourplanId__iexact=data['trip_file'].strip()).first()
    try:
        cost = float(data.get('cost') or 0)
    except (ValueError, TypeError):
        cost = 0
    responsable = None
    if data.get('responsable_id'):
        responsable = User.objects.filter(pk=data['responsable_id']).first()
    priority = data.get('priority', '')
    fb = Feedback.objects.create(
        user=request.user,
        trip=trip,
        supplier=supplier,
        target_user=target_user,
        target_guide=target_guide,
        target_dh=target_dh,
        target_driver=target_driver,
        target_entity=target_entity,
        sentiment=data.get('sentiment', 'neutral'),
        status=data.get('status', 'abierto'),
        type=data.get('type', 'Otro'),
        brief_summary=(data.get('brief_summary') or '')[:120],
        content=data.get('content', ''),
        verbatim=data.get('verbatim', ''),
        solution=data.get('solution', ''),
        cost=cost,
        source='manual',
        responsable=responsable,
        priority=priority,
    )
    # If driver has a linked supplier, also create a supplier feedback
    sup_fb = None
    if target_driver and target_driver.supplier_id:
        sup_fb = Feedback.objects.create(
            user=request.user,
            trip=trip,
            supplier=target_driver.supplier,
            sentiment=data.get('sentiment', 'neutral'),
            status=data.get('status', 'abierto'),
            type=data.get('type', 'Otro'),
            brief_summary=(data.get('brief_summary') or '')[:120],
            content=data.get('content', ''),
            solution=data.get('solution', ''),
            cost=cost,
            source='manual',
            responsable=responsable,
            priority=priority,
        )
    # Auto-create Entry for manual negative feedbacks with responsable and priority
    if fb.sentiment == 'negativo' and trip and responsable and priority:
        from tariff.quality_ai import _create_quality_entry
        all_negative = [fb] + ([sup_fb] if sup_fb else [])
        _create_quality_entry(trip, responsable, priority, all_negative, request.user)
    return JsonResponse({'ok': True, 'id': fb.id})


@login_required
def calidad_delete_feedback(request, feedback_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import Feedback
    try:
        Feedback.objects.get(pk=feedback_id).delete()
        return JsonResponse({'ok': True})
    except Feedback.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def calidad_search_users(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = request.GET.get('q', '').strip()
    qs = User.objects.filter(userType__in=['Ventas', 'Operaciones', 'Internal'])
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(other_name__icontains=q) | Q(username__icontains=q))
    results = [{'id': u.id, 'name': u.other_name or u.username} for u in qs.order_by('other_name')[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_search_entities(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackEntity
    q = request.GET.get('q', '').strip()
    qs = FeedbackEntity.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    results = [{'id': e.id, 'name': e.name, 'description': e.description} for e in qs.order_by('name')[:30]]
    return JsonResponse({'results': results})


@login_required
def calidad_entities(request):
    """Create a new FeedbackEntity (POST) or list all (GET)."""
    if not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackEntity
    if request.method == 'POST':
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()
        if not name:
            return JsonResponse({'error': 'El nombre es obligatorio'}, status=400)
        entity, created = FeedbackEntity.objects.get_or_create(name=name, defaults={'description': description})
        return JsonResponse({'ok': True, 'id': entity.id, 'name': entity.name, 'created': created})
    entities = list(FeedbackEntity.objects.order_by('name').values('id', 'name', 'description'))
    return JsonResponse({'results': entities})


@login_required
def calidad_edit_entity(request, entity_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackEntity
    try:
        entity = FeedbackEntity.objects.get(pk=entity_id)
    except FeedbackEntity.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    data = json.loads(request.body)
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'El nombre es obligatorio'}, status=400)
    entity.name = name
    entity.description = (data.get('description') or '').strip()
    entity.save()
    return JsonResponse({'ok': True, 'name': entity.name, 'description': entity.description})


@login_required
def calidad_entity_delete(request, entity_id):
    if request.method != 'POST' or not request.user.isAdmin:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from tariff.models import FeedbackEntity
    try:
        entity = FeedbackEntity.objects.get(pk=entity_id)
        if entity.feedback_entities.exists():
            return JsonResponse({'error': 'Tiene feedbacks asociados, no se puede eliminar'}, status=400)
        entity.delete()
        return JsonResponse({'ok': True})
    except FeedbackEntity.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

# ── Notification management ──────────────────────────────────────────────────

def _auto_logic_users(notification_type):
    """Returns list of User objects that auto-logic would send this type to."""
    if notification_type == 'margin_warning':
        return list(User.objects.filter(userType='Ventas').exclude(email='').order_by('username'))
    if notification_type in ('weekly_roster', 'holiday_reminder'):
        return list(
            User.objects.filter(
                userType__in=['Ventas', 'Operaciones', 'Manager'],
                isActivated=True,
                department='AI',
            ).exclude(email='').order_by('username')
        )
    return []


@login_required
def notifications_management(request):
    if not request.user.isAdmin:
        return HttpResponseRedirect(reverse('index'))

    TYPE_LABELS = dict(NOTIFICATION_TYPES)

    sections = []
    for type_key, type_label in NOTIFICATION_TYPES:
        is_auto = type_key in NOTIFICATION_AUTO_TYPES

        pref_map = {
            p.user_id: p
            for p in NotificationPreference.objects.filter(
                notification_type=type_key
            ).select_related('user')
        }

        rows = []
        shown_user_ids = set()
        is_client_type = (type_key == 'tariff_client')
        admin_dept = request.user.department

        if is_auto:
            for user in _auto_logic_users(type_key):
                if user.department != admin_dept:
                    continue
                pref = pref_map.get(user.id)
                rows.append({
                    'user': user,
                    'is_auto': True,
                    'is_active': pref.is_active if pref else True,
                    'opt_out_by': pref.opt_out_by if pref else '',
                    'pref_id': pref.id if pref else None,
                })
                shown_user_ids.add(user.id)

        # Explicit records not already shown
        for uid, pref in pref_map.items():
            if uid in shown_user_ids:
                continue
            u = pref.user
            if is_client_type:
                if u.userType != 'Cliente':
                    continue
            else:
                if u.department != admin_dept or u.userType == 'Cliente':
                    continue
            rows.append({
                'user': u,
                'is_auto': False,
                'is_active': pref.is_active,
                'opt_out_by': pref.opt_out_by,
                'pref_id': pref.id,
            })
            shown_user_ids.add(uid)

        if is_client_type:
            available_users = (
                User.objects.filter(isActivated=True, userType='Cliente')
                .exclude(email='')
                .exclude(id__in=shown_user_ids)
                .order_by('username')
            )
        else:
            available_users = (
                User.objects.filter(isActivated=True, department=admin_dept)
                .exclude(email='')
                .exclude(userType='Cliente')
                .exclude(id__in=shown_user_ids)
                .order_by('username')
            )

        sections.append({
            'type': type_key,
            'label': type_label,
            'is_auto': is_auto,
            'rows': rows,
            'available_users': available_users,
        })

    return render(request, 'intranet/notifications.html', {
        'sections': sections,
    })


@login_required
def notification_toggle(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return HttpResponseRedirect(reverse('index'))

    user_id = request.POST.get('user_id')
    notification_type = request.POST.get('notification_type')
    action = request.POST.get('action')  # 'deactivate' or 'activate'

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseRedirect(reverse('notifications_management'))

    pref, _ = NotificationPreference.objects.get_or_create(
        user=target_user,
        notification_type=notification_type,
        defaults={'is_active': True},
    )

    if action == 'deactivate':
        pref.is_active = False
        pref.opt_out_by = 'admin'
    else:
        pref.is_active = True
        pref.opt_out_by = ''
    pref.save()

    return HttpResponseRedirect(reverse('notifications_management') + f'#{notification_type}')


@login_required
def notification_add(request):
    if request.method != 'POST' or not request.user.isAdmin:
        return HttpResponseRedirect(reverse('index'))

    user_id = request.POST.get('user_id')
    notification_type = request.POST.get('notification_type')

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseRedirect(reverse('notifications_management'))

    pref, _ = NotificationPreference.objects.get_or_create(
        user=target_user,
        notification_type=notification_type,
        defaults={'is_active': True, 'opt_out_by': ''},
    )
    if not pref.is_active:
        pref.is_active = True
        pref.opt_out_by = ''
        pref.save()

    return HttpResponseRedirect(reverse('notifications_management') + f'#{notification_type}')


def notification_unsubscribe(request, token):
    """Public unsubscribe endpoint — no login required (link is in email)."""
    try:
        pref = NotificationPreference.objects.select_related('user').get(unsubscribe_token=token)
    except NotificationPreference.DoesNotExist:
        return HttpResponse("Invalid or expired unsubscribe link.", status=404)

    already_done = not pref.is_active
    if not already_done:
        pref.is_active = False
        pref.opt_out_by = 'self'
        pref.save()

    return render(request, 'intranet/notifications_unsubscribed.html', {
        'notification_label': pref.get_notification_type_display(),
        'already_done': already_done,
    })


# ─── Revision / Correcciones ──────────────────────────────────────────────────

def _send_gchat_notification(department, text, mention_user=None):
    webhook_user = (
        User.objects.filter(department=department)
        .exclude(chat_webhook_url='').first()
    )
    if not webhook_user:
        return
    if mention_user and getattr(mention_user, 'chat_user_id', ''):
        text = f"<users/{mention_user.chat_user_id}> {text}"
    try:
        import requests as _req
        _req.post(webhook_user.chat_webhook_url, json={'text': text}, timeout=5)
    except Exception:
        pass


def _auto_assign_reviewer(entry, department):
    """Pick the best reviewer for an entry based on today's schedule and workload."""
    from django.db.models import Count as _Count
    today = date.today()
    weekday = today.weekday()  # 0=Mon…4=Fri
    if weekday > 4:
        return None

    absent_ids = set(
        _absences_on_day(today, department).values_list('absence_user_id', flat=True)
    )

    schedule_qs = (
        RevisionScheduleDay.objects
        .filter(
            weekday=weekday,
            user__department=department,
            user__isActivated=True,
            user__show_in_calendar=True,
            user__userType='Ventas',
        )
        .exclude(user_id__in=absent_ids)
        .select_related('user')
        .order_by('order')
    )

    # Junior itineraries can only be reviewed by Seniors
    entry_user = entry.trip.responsable_user if entry.trip else None
    if entry_user and entry_user.seniority == 'Junior':
        schedule_qs = schedule_qs.filter(user__seniority='Senior')

    eligible = [s for s in schedule_qs if s.user_id != (entry_user.id if entry_user else None)]
    if not eligible:
        return None

    # Balance by pending revision count; use schedule order as tiebreaker
    user_ids = [s.user_id for s in eligible]
    pending = dict(
        Entry.objects
        .filter(revising_user_id__in=user_ids, is_revised=False)
        .exclude(revision_link__isnull=True).exclude(revision_link='')
        .values('revising_user_id')
        .annotate(n=_Count('id'))
        .values_list('revising_user_id', 'n')
    )
    best = min(eligible, key=lambda s: (pending.get(s.user_id, 0), s.order))
    return best.user


@login_required
def revising_itineraries(request):
    dept = request.user.department
    WEEKDAYS = [(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes')]

    schedule_days = (
        RevisionScheduleDay.objects
        .filter(user__department=dept, user__isActivated=True)
        .select_related('user')
        .order_by('weekday', 'order')
    )
    grid = {wd: [] for wd, _ in WEEKDAYS}
    for sd in schedule_days:
        grid[sd.weekday].append(sd.user)

    dept_users = User.objects.filter(
        department=dept, isActivated=True, show_in_calendar=True,
        userType='Ventas',
    ).order_by('username')

    pending_entries = (
        Entry.objects
        .filter(trip__department=dept, is_revised=False)
        .exclude(revision_link__isnull=True).exclude(revision_link='')
        .select_related('trip', 'trip__client', 'trip__responsable_user', 'revising_user', 'user_working')
        .order_by('trip__travelling_date')
    )

    grid_rows = [(wd, label, grid[wd]) for wd, label in WEEKDAYS]
    today = date.today()
    absent_ids = set(
        _absences_on_day(today, dept).values_list('absence_user_id', flat=True)
    )

    return render(request, 'intranet/revising_itineraries.html', {
        'grid_rows': grid_rows,
        'all_dept_users': dept_users,
        'pending_entries': pending_entries,
        'absent_ids': absent_ids,
        'today_weekday': today.weekday(),
    })


@login_required
def revision_schedule_update(request):
    if not request.user.isAdmin:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    import json as _json
    try:
        data = _json.loads(request.body)  # {"0": [uid, ...], "1": [...], ...}
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    dept = request.user.department
    RevisionScheduleDay.objects.filter(user__department=dept).delete()
    rows = []
    for wd_str, uid_list in data.items():
        wd = int(wd_str)
        for order, uid in enumerate(uid_list):
            try:
                user = User.objects.get(id=int(uid), department=dept)
                rows.append(RevisionScheduleDay(user=user, weekday=wd, order=order))
            except User.DoesNotExist:
                pass
    RevisionScheduleDay.objects.bulk_create(rows)
    return JsonResponse({'ok': True})


@login_required
def entry_send_for_revision(request, entry_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    import json as _json
    try:
        body = _json.loads(request.body)
        link = body.get('link', '').strip()
    except Exception:
        link = ''
    try:
        entry = Entry.objects.select_related(
            'trip', 'trip__responsable_user'
        ).get(id=entry_id, trip__department=request.user.department)
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'Entrada no encontrada'}, status=404)

    entry.revision_link = link
    entry.is_revised = False
    entry.progress = "5 - Finalised"
    # Reload with trip relation needed for auto-assignment
    entry_with_trip = Entry.objects.select_related(
        'trip', 'trip__responsable_user'
    ).get(id=entry.id)
    reviewer = _auto_assign_reviewer(entry_with_trip, request.user.department)
    entry.revising_user = reviewer
    entry.save(update_fields=['revision_link', 'is_revised', 'revising_user', 'progress'])
    if reviewer:
        trip_name = entry_with_trip.trip.name if entry_with_trip.trip else '—'
        client_name = entry_with_trip.trip.client.name if entry_with_trip.trip and entry_with_trip.trip.client else '—'
        _send_gchat_notification(
            request.user.department,
            f"📋 *Nueva corrección asignada a {reviewer.other_name or reviewer.username}*\n*Viaje:* {trip_name}\n*Cliente:* {client_name}\n*Link:* {link or '—'}",
            mention_user=reviewer,
        )
    return JsonResponse({
        'ok': True,
        'revising_user': reviewer.username if reviewer else None,
        'revising_user_id': reviewer.id if reviewer else None,
    })


@login_required
def entry_update_revising_user(request, entry_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    import json as _json
    try:
        body = _json.loads(request.body)
        user_id = body.get('user_id')
        revision_link = body.get('revision_link', None)
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    try:
        entry = Entry.objects.get(id=entry_id, trip__department=request.user.department)
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'Entrada no encontrada'}, status=404)
    if user_id:
        try:
            reviewer = User.objects.get(id=int(user_id), department=request.user.department)
            entry.revising_user = reviewer
        except User.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    else:
        entry.revising_user = None
    update_fields = ['revising_user']
    if revision_link is not None:
        entry.revision_link = revision_link.strip()
        update_fields.append('revision_link')
    entry.save(update_fields=update_fields)
    if user_id and entry.revising_user:
        entry_full = Entry.objects.select_related('trip', 'trip__client').get(id=entry.id)
        trip_name = entry_full.trip.name if entry_full.trip else '—'
        client_name = entry_full.trip.client.name if entry_full.trip and entry_full.trip.client else '—'
        effective_link = entry.revision_link if revision_link is not None else (entry_full.revision_link or '—')
        reviewer_name = entry.revising_user.other_name or entry.revising_user.username
        _send_gchat_notification(
            request.user.department,
            f"📋 *Corrección asignada a {reviewer_name}*\n*Viaje:* {trip_name}\n*Cliente:* {client_name}\n*Link:* {effective_link}",
            mention_user=entry.revising_user,
        )
    return JsonResponse({'ok': True})


@login_required
def entry_mark_revised(request, entry_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        entry = Entry.objects.get(id=entry_id, trip__department=request.user.department)
    except Entry.DoesNotExist:
        return JsonResponse({'error': 'Entrada no encontrada'}, status=404)
    entry.is_revised = True
    entry.save(update_fields=['is_revised'])
    return JsonResponse({'ok': True})
