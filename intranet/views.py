from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.utils.datastructures import MultiValueDictKeyError
from django.db import IntegrityError
from .models import User, Country, Client, Trip, Entry, Notes, ClientContact, CsvFileTourplanFiles, CsvFormTourplanFiles, Search, Holidays, Absence, DEPARTMENTS, STATUS_OPTIONS, IMPORTANCE_OPTIONS, PROGRESS_OPTIONS, TRIP_TYPES, DH_TYPES, USER_TYPES, DIFFICULTY_OPTIONS, CLIENT_CATEGORIES, MONTHS
from tariff.models import Feedback, Supplier, Location, TYPE_QUALITY
from .utils import update_timingStatus
import json
from datetime import datetime, date, timedelta
from django.utils.timezone import localtime
from imap_tools import MailBox
import os
from dotenv import load_dotenv
import csv
from django.db.models import Q
from django.core.paginator import Paginator
from collections import OrderedDict
from django.views.decorators.http import require_GET
from .utils import get_working_days, get_working_days_worker


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

    return render(request, "intranet/index.html", {
        "pax_arriving": pax_arriving,
        "pax_insitu": pax_insitu,
        "notes": Notes.objects.all(),
        "entries": Entry.objects.all(),
        "pendings": data,
        "total_quotes": total_quotes,
        "total_bookings": total_bookings,
        "total_finals": total_finals,
        "total_others": total_others
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

    # Empty list of trips filtered
    filter_trips = []

    # Check if a search is saved
    if search:

       # Filter the trips by deparment
        dep_trips = Trip.objects.filter(department=user.department)

        if search.name != "":
            name_trips = dep_trips.filter(name__icontains=search.name)
        else:
            name_trips = dep_trips

        if search.client_reference != "":
            client_ref_trips = name_trips.filter(client_reference__icontains=search.client_reference)
        else:
            client_ref_trips = name_trips

        if search.tourplanId != "":
            tourplan_ref_trips = client_ref_trips.filter(tourplanId__icontains=search.tourplanId)
        else:
            tourplan_ref_trips = client_ref_trips

        filter_trips = tourplan_ref_trips
        status_trips = []
 
    # Filter applied when there is no search
    else:
        dep_trips = Trip.objects.filter(department=user.department)

        if user.userType == "Ventas":
            filter_trips = dep_trips.filter(responsable_user=user)
        else:
            for trip in dep_trips:
                if (trip.travelling_date - today).days < 16 and (trip.travelling_date - today).days >= 0:
                    filter_trips.append(trip)

    return filter_trips


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
            )
            new_user.save()
        except IntegrityError:
            return render(request, "intranet/users.html", {
                "message_new": "El usuario ya existe",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })

        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all()
        })

    else:
        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all()
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

        # Modifies the model of the user from the form information

        user.other_name=name
        user.username=username
        user.email=email
        user.department=department
        user.isAdmin=isAdmin
        user.isActivated=isActivated
        user.is_active=is_active
        user.userType=type
        user.color=color

        user.save()

        return HttpResponseRedirect(reverse("users"), {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all()
        })
    

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
                    "notes": Notes.objects.filter(trip__department=user.department),
                    "one_hundred": 100,
                    "feedbacks": Feedback.objects.filter(trip__department=user.department),
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
                    "notes": Notes.objects.filter(trip__department=user.department),
                    "one_hundred": 100,
                    "feedbacks": Feedback.objects.filter(trip__department=user.department),
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

            # Get the contact from the contact ID of the form
            if contact_form == "0" or contact_form == "Contacto" or not contact_form:
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
            dh = User.objects.get(pk=19)

            # Creates the model of the trip from the form information
            new_trip = Trip.objects.create(
                name=name,
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
        return render(request, "intranet/trips.html", 
                     get_return_page("trips", "", request.user))
    
    
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
            responsable_user_form = request.POST["responsable_user"]
            operations_user_form = request.POST["operations_user"]
            dh_form = request.POST["dh"]
            guide = request.POST["guide"]
        else:
            itId = ""
            dh_type = "Sin definir"
            responsable_user_form = User.objects.get(username="SD").id
            operations_user_form = User.objects.get(username="SD").id
            dh_form = User.objects.get(username="SD").id
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
        dh = User.objects.get(id=dh_form)

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
        
    # Shows all entries
    return render(request, "intranet/pendings.html", get_return_page("entries", "", request.user))
    
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
            return render(request, "intranet/new_entry.html", {
                "entries": filter_entries,
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "trip": trip,
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

        # Return all the entries without answer and the rest of the info for the form
        return render(request, "intranet/new_entry.html", {
            "entries": filter_entries,
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "trip": trip,
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
        if status == "Booking":
            if (entry.version == 1):
                trip.status = "Booking"
                trip.conversion_date = starting_date
            trip.version = version
        if status == "Quote":
            trip.version_quote = version_quote
        else:
            trip.version = version

        if isClosed == True:
            closing_date = datetime.fromisoformat(closing_date_form)
            entry.closing_date = closing_date

        # If there is no amount, get the trip amount and save it to the entry
        if empty_amount == False:
            trip.amount = amount
            entry.amount = amount

        # If there is tourplan ID is no empty get it from the form
        if tourplanId != "":
            trip.tourplanId = tourplanId
        
        # Save all the changes of the trip
        trip.save()

        update_timingStatus(entry)

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
    for i in range(-20, 20 + 1):
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
    
    # Obtener parámetros de la solicitud
    report_type = request.GET.get('type', 'vendor')
    period = request.GET.get('period', 'Período Personalizado')
    
    context = {
        'report_type': report_type,
        'period': period,
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
    
    # Obtener parámetros de la solicitud
    report_type = request.GET.get('type', 'vendor')
    period = request.GET.get('period', 'Período Personalizado')
    
    context = {
        'report_type': report_type,
        'period': period,
    }
    
    return render(request, 'intranet/stats_trips_report.html', context)

@login_required
def holidays(request):
    return render(request, "intranet/holidays.html")


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
    """
    Function to create json for FullCalendar
    """

    # Getting the information of the dates required
    start_date_str = request.GET.get('start', None)
    end_date_str = request.GET.get('end', None)

    # Filter the events of the model according to the required dates
    if start_date_str and end_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
        holidays = Holidays.objects.filter(date_from__gte=start_date, date_to__lte=end_date)
        absences = Absence.objects.filter(date_from__gte=start_date, date_to__lte=end_date)

    # Inicialize empty list of the data to be send
    data = []

    # Get the holidays events
    for event in holidays:

        # Select the color according to the type
        if event.type_holidays == "Feriado":
            color = "#FF0000"
        elif event.type_holidays == "Fin de semana":
            color = "#808080"
        elif event.type_holidays == "Día no laborable":
            color = "#FF8000"
        
        # If it is workable it will bring the name of the user, otherwise empty string
        if event.workable:
            title = event.working_user.username
        else:
            title = ""

        data.append({
            'id': event.id,
            'title': title,
            'start': event.date_from.isoformat(),
            'end': event.date_to.isoformat(),
            'allDay': True,
            'backgroundColor': color,
        })
    
    for event in absences:
        
        data.append({
            'id': event.id,
            'title': event.absence_user.username,
            'start': event.date_from.isoformat(),
            'end': event.date_to.isoformat(),
            'allDay': True,
            'backgroundColor': "#00aae4",
        })
    
    return JsonResponse(data, safe=False)


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
def json_contacts(_request):

    # Get the list of the contacts
    contacts = list(ClientContact.objects.values())
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

@login_required
@csrf_exempt
def entries_data(request):
    # Columnas en el mismo orden que tu tabla HTML
    columns = [
        "starting_date",
        "closing_date",
        "trip__name",
        "status",
        "amount",
        "trip__client__name",
        "trip__contact__name",
        "trip__client_reference",
        "user_creator__username",
        "user_working__username",
        "progress",
        "importance",
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
    user_filter = request.GET.get("user_filter", "").strip()  # username o ""

    order_col_index = int(request.GET.get("order[0][column]", 0))
    order_dir = request.GET.get("order[0][dir]", "asc")
    order_col = columns[order_col_index]
    if order_dir == "desc":
        order_col = f"-{order_col}"

    # 🚩 Filtrar solo entradas del mismo departamento que el usuario
    qs = Entry.objects.select_related("trip", "user_creator", "user_working", "trip__client", "trip__contact").filter(
        trip__department=request.user.department
    )
    
    # 🚩 Solo entradas abiertas (isClosed == False) si no se pidió show_all
    if show_all != "1":
        qs = qs.filter(isClosed=False)

    # si viene filtro de usuario, aplicar (ejemplo: filtrar por user_creator username)
    if user_filter != "":
        qs = qs.filter(user_working__username=user_filter)

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

    total_records = Entry.objects.filter(trip__department=request.user.department).count()
    filtered_records = qs.count()

    # Orden + paginación
    qs = qs.order_by(order_col)
    paginator = Paginator(qs, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    # Preparar datos
    data = []
    for entry in page_obj:
        # status con versión
        status = f"{entry.status} {entry.version_quote if entry.status == 'Quote' else entry.version}"

        # monto
        amount = f"USD {entry.amount}" if entry.amount else "Pendiente"

        # fechas
        starting_date = localtime(entry.starting_date).strftime("%Y/%m/%d %H:%M")
        closing_date = localtime(entry.closing_date).strftime("%Y/%m/%d %H:%M") if entry.isClosed else f"<div class='bg-{entry.timingStatus}'>n/a</div>"
        travelling_date = entry.trip.travelling_date.strftime("%Y/%m/%d") if entry.trip and entry.trip.travelling_date else ""
        #user_working = f"<div style='background-color: {entry.user_working.color}; color:white'>{entry.user_working.username}</div>"

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

        data.append({
            "starting_date": starting_date,
            "closing_date": closing_date,
            "trip": entry.trip.name if entry.trip else "",
            "status": status,
            "amount": amount,
            "client": entry.trip.client.name if entry.trip and entry.trip.client else "",
            "contact": str(entry.trip.contact) if entry.trip and entry.trip.contact else "",
            "client_reference": entry.trip.client_reference if entry.trip else "",
            "user_creator": entry.user_creator.username,
            "user_working": entry.user_working.username,
            "progress": entry.progress,
            "importance": entry.importance,
            "note": entry.note or "n/a",
            "travelling_date": travelling_date,
            "acciones": acciones_html,
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
    order_col_index = int(request.GET.get("order[0][column]", 0))
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

    if date_from and date_to:
        qs = qs.filter(starting_date__date__range=[date_from, date_to])

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

    order_col_index = int(request.GET.get("order[0][column]", 0))
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

            vendors_b[vendor] = {
                "total": 0,
                "workingDays": get_working_days_worker(date_from, date_to, entry.user_working),
                "first": 0,
                "audleyFirst": 0,
                "amountFirst": 0.0,
                "color": user_color
            }
        if entry.version == 1:
            vendors_b[vendor]["first"] += 1
            if entry.trip and entry.trip.client and entry.trip.client.name == "Audley Travel UK":
                vendors_b[vendor]["audleyFirst"] += 1
            if entry.amount:
                vendors_b[vendor]["amountFirst"] += float(entry.amount)
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
    pass


def stats_entries_by_speed(qs, date_from, date_to):
    pass

def stats_entries_by_worker(qs):
    pass

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

    # base queryset
    qs = Entry.objects.select_related(
        "user_working", "trip", "trip__client"
    ).filter(
        trip__department=department
    )

    # filtro por fechas
    if month and year:
        qs = qs.filter(starting_date__month=month, starting_date__year=year)
    elif date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            qs = qs.filter(starting_date__range=(d_from, d_to))
        except ValueError:
            pass

    this_year = datetime.strptime(date_from, "%Y-%m-%d").year
    this_month = datetime.strptime(date_from, "%Y-%m-%d").month

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

    quotes = qs.filter(status="Quote").filter(version_quote="A")

    # === RESUMEN GLOBAL (para tu tabla doble entrada quotes) ===
    total_count_quotes = quotes.count()
    total_amount_quotes = sum(float(e.amount or 0) for e in quotes)

    # Count of the quotes
    individual_count_quotes = quotes.filter(trip__trip_type="FIT's").count()  # suponiendo que tu modelo Trip tiene "is_group"
    audley_count_quotes = quotes.filter(trip__client__name="Audley Travel UK").count()
    group_count_quotes = quotes.filter(trip__trip_type="Grupos").count()
    fam_count_quotes = quotes.filter(trip__trip_type="FAM Tours").count()
    this_season_count_quotes = quotes.filter(trip__travelling_date__range=(this_season_from, this_season_to)).count()
    next_season_count_quotes = quotes.filter(trip__travelling_date__range=(next_season_from, next_season_to)).count()

    # Changes of the quotes (B, C, D)
    total_changes_quotes = qs.filter(status="Quote").exclude(version_quote="A").count()

    # Amounts for quotes
    individual_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__trip_type="FIT's"))
    audley_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__client__name="Audley Travel UK"))
    group_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__trip_type="Grupos"))
    fam_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__trip_type="FAM Tours"))
    this_season_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__travelling_date__range=(this_season_from, this_season_to)))
    next_season_amount_quotes = sum(float(e.amount or 0) for e in quotes.filter(trip__travelling_date__range=(next_season_from, next_season_to)))

    # Percentages
    individual_perc_quotes = round(float(individual_amount_quotes / total_amount_quotes * 100), 2)
    audley_perc_quotes = round(float(audley_amount_quotes / total_amount_quotes * 100), 2)
    group_perc_quotes = round(float(group_amount_quotes / total_amount_quotes * 100), 2)
    fam_perc_quotes = round(float(fam_amount_quotes / total_amount_quotes * 100), 2)
    this_season_perc_quotes = round(float(this_season_amount_quotes / total_amount_quotes * 100), 2)
    next_season_perc_quotes = round(float(next_season_amount_quotes / total_amount_quotes * 100), 2)

    # Promedio por día (si hay rango de fechas)
    days = 1
    if date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            days = get_working_days(d_from, d_to)
        except Exception:
            pass

    average_quotes_quantity = round(total_count_quotes / days, 2) if days else 0
    average_quotes_amount = round(total_amount_quotes / days, 2) if days else 0

    if total_count_quotes > 0:
        average_difficulty = round(sum(int(e.trip.difficulty or 0) for e in quotes) / total_count_quotes, 2)
    else:
        average_difficulty = 0

    difficulty_1 = quotes.filter(trip__difficulty="1").count()
    difficulty_2 = quotes.filter(trip__difficulty="2").count()
    difficulty_3 = quotes.filter(trip__difficulty="3").count()
    difficulty_4 = quotes.filter(trip__difficulty="4").count()
    difficulty_5 = quotes.filter(trip__difficulty="5").count()

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

    bookings = qs.filter(status="Booking").filter(version=1)

    # === RESUMEN GLOBAL (para tu tabla doble entrada bookings) ===
    total_count_bookings = bookings.count()
    total_amount_bookings = sum(float(e.amount or 0) for e in bookings)

    # Count of the bookings
    individual_count_bookings = bookings.filter(trip__trip_type="FIT's").count()  # suponiendo que tu modelo Trip tiene "is_group"
    audley_count_bookings = bookings.filter(trip__client__name="Audley Travel UK").count()
    group_count_bookings = bookings.filter(trip__trip_type="Grupos").count()
    fam_count_bookings = bookings.filter(trip__trip_type="FAM Tours").count()
    this_season_count_bookings = bookings.filter(trip__travelling_date__range=(this_season_from, this_season_to)).count()
    next_season_count_bookings = bookings.filter(trip__travelling_date__range=(next_season_from, next_season_to)).count()

    # Changes of the bookings (2, 3, 4)
    total_changes_bookings = qs.filter(status="Booking").exclude(version=1).count()

    # Amounts for bookings
    individual_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__trip_type="FIT's"))
    audley_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__client__name="Audley Travel UK"))
    group_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__trip_type="Grupos"))
    fam_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__trip_type="FAM Tours"))
    this_season_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__travelling_date__range=(this_season_from, this_season_to)))
    next_season_amount_bookings = sum(float(e.amount or 0) for e in bookings.filter(trip__travelling_date__range=(next_season_from, next_season_to)))

    # Percentages
    individual_perc_bookings = round(float(individual_amount_bookings / total_amount_bookings * 100), 2)
    audley_perc_bookings = round(float(audley_amount_bookings / total_amount_bookings * 100), 2)
    group_perc_bookings = round(float(group_amount_bookings / total_amount_bookings * 100), 2)
    fam_perc_bookings = round(float(fam_amount_bookings / total_amount_bookings * 100), 2)
    this_season_perc_bookings = round(float(this_season_amount_bookings / total_amount_bookings * 100), 2)
    next_season_perc_bookings = round(float(next_season_amount_bookings / total_amount_bookings * 100), 2)

    average_bookings_quantity = round(total_count_bookings / days, 2) if days else 0
    average_bookings_amount = round(total_amount_bookings / days, 2) if days else 0

    # Cancellation information
    cancellations_count = qs.filter(status="Cancelado").count()

    # Cancellation amounts (difference with the last booking)
    cancellations_amount = 0.0
    cancellation_entries = qs.filter(status="Cancelado")

    for entry in cancellation_entries:
        trip_obj = entry.trip
        
        last_booking = Entry.objects.filter(trip=trip_obj).filter(status="Booking").first()
        if last_booking:
            cancellations_amount += (last_booking.amount)
        else:
            cancellations_amount = entry.amount

    conversion_perc = round(total_count_bookings / total_count_quotes * 100, 2)
    conversion_perc_audley = round(audley_count_bookings / audley_count_quotes * 100, 2)

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
    speed = stats_entries_by_speed(qs, d_from, d_to)
    speed_by_worker = stats_entries_by_worker(qs)
    clients = stats_entries_by_client(qs)

    return JsonResponse({
        "vendors_quote": vendors_quote,
        "vendors_bookings": vendors_bookings,
        "summary_table_quotes": summary_table_quotes,
        "summary_table_bookings": summary_table_bookings,
    })


def read_emails(request):
    load_dotenv()
    
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

    # List to be import
    tourplan_list = []

    user_usernames = []
    all_users = User.objects.all()
    for user in all_users:
        user_usernames.append(user.username)
    
    contact_names = []
    all_contacts = ClientContact.objects.all()
    for contact in all_contacts:
        contact_names.append(contact.name)

    # All trips
    trip_ids = []
    all_trips = Trip.objects.all()
    for item in all_trips:
        if item.tourplanId == None or item.tourplanId == "":
            pass
        else:
            trip_ids.append(item.tourplanId)

    # Open the csv and read all the data
    with open(csv_obj.file_name.path, 'r') as f:
        reader = csv.reader(f, delimiter=';')

        for i, row in enumerate(reader):
            if i >= 7:
                col_number = 1
                for col in row:
                    if col_number == 3:
                        # Read only the lines with tourplan id
                        if col in trip_ids:
                            trip = Trip.objects.get(tourplanId=col)
                            tourplan_list.append(trip)
                            col_number+=1
                        else:
                            break
                    elif col_number == 4:
                        date_obj = datetime.strptime(col, "%d/%m/%Y")
                        formatted_date = date_obj.strftime("%Y-%m-%d")
                        trip.travelling_date = formatted_date
                        trip.save()
                        col_number+=1
                    elif col_number == 5:
                        date_obj = datetime.strptime(col, "%d/%m/%Y")
                        formatted_date = date_obj.strftime("%Y-%m-%d")
                        trip.out_date = formatted_date
                        trip.save()
                        col_number+=1  
                    elif col_number == 8:
                        if col == "S" or col == "B" or col == "F":
                            trip.dh_type = col
                        trip.save()
                        col_number+=1
                    elif col_number == 10:
                        if col in user_usernames:
                            responsable_user = User.objects.get(username=col)
                            trip.responsable_user = responsable_user
                            trip.save()
                        col_number+=1
                    elif col_number == 11:
                        if col in user_usernames:
                            operations_user = User.objects.get(username=col)
                            trip.operations_user = operations_user
                            trip.save()
                        col_number+=1
                    elif col_number == 12:
                        if col in user_usernames:
                            dh = User.objects.get(username=col)
                            trip.dh = dh
                            trip.save()
                        col_number+=1
                    elif col_number == 14:
                        if col in contact_names:
                            contact = ClientContact.objects.get(name=col)
                            trip.contact = contact
                            trip.save()
                        col_number+=1
                    elif col_number == 17:
                        trip.guide = col
                        trip.save()
                        col_number+=1
                    elif col_number == 21:
                        trip.rent_perc = col
                        trip.save()
                        col_number+=1
                    elif col_number == 22:
                        trip.amount = col
                        trip.save()
                        tp_entry = Entry.objects.filter(tourplanId=trip.tourplanId).last()
                        if tp_entry:
                            tp_entry.amount = col
                            tp_entry.save()
                        col_number+=1
                    else:
                        col_number+=1

    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()

    return tourplan_list


# Page to load the tourplan csv
@login_required
def tourplan_files(request):

    if request.method == "POST":
        form = CsvFormTourplanFiles(request.POST, request.FILES)
        if form.is_valid():

            form.save()

            # Create data from tourplan csv
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
                        dh=User.objects.get(username="SD"),
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