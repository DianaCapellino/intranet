from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.utils.datastructures import MultiValueDictKeyError
from django.db import IntegrityError
import django.utils.timezone
from .models import User, Country, Client, Trip, Entry, Notes, ClientContact, DEPARTMENTS, STATUS_OPTIONS, IMPORTANCE_OPTIONS, PROGRESS_OPTIONS, TRIP_TYPES, DH_TYPES, USER_TYPES
import json
import datetime
from datetime import datetime, date, timedelta
from imap_tools import MailBox
import os
from dotenv import load_dotenv


@login_required
def index (request):

    pax_arriving = []
    pax_insitu = []

    today = date.today()

    # Gets the difference between today and arriving dates and add these trips to the list
    for trip in Trip.objects.all():
        if (trip.travelling_date - today).days < 16 and (trip.travelling_date - today).days >= 0 and trip.status == "Booking":
            pax_arriving.append(trip)
    
    pax_arriving.sort(key=lambda trip: trip.travelling_date)

    # Gets the difference between today and arriving dates and add these trips to the list
    for trip in Trip.objects.all():
        if trip.out_date != None:
            if (trip.travelling_date - today).days > -60 and (trip.travelling_date - today).days <= 0 and (trip.out_date - today).days >= 0 and trip.status == "Booking":
                pax_insitu.append(trip)
    
    pax_insitu.sort(key=lambda trip: trip.travelling_date)

    return render(request, "intranet/index.html", {
        "pax_arriving": pax_arriving,
        "pax_insitu": pax_insitu,
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

        # Attempt to create contact
        name = request.POST["name"]
        country_form = request.POST["country"]

        # Validations
        if not name or not country_form:
            return render(request, "intranet/clients.html", {
                "message": "Todos los campos deben ser completados",
                "clients": Client.objects.all(),
                "countries": Country.objects.all(),
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
        )
        new_client.save()

        return render(request, "intranet/clients.html", {
            "clients": Client.objects.all(),
            "countries": Country.objects.all(),
        })
    
    # If method is GET it displays the form to add new client
    else:
        return render(request, "intranet/clients.html", {
            "clients": Client.objects.all(),
            "countries": Country.objects.all(),
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
        try:

            user.username=username
            user.email=email
            user.department=department
            user.isAdmin=isAdmin
            user.isActivated=isActivated
            user.is_active=is_active
            user.userType=type
            
            user.save()

        # Shows and error if the username already exists    
        except IntegrityError:
            return render(request, "intranet/users.html", {
                "message_modify": "El usuario ya existe",
                "departments": DEPARTMENTS,
                "user_types": USER_TYPES,
                "users": User.objects.all()
            })
        return HttpResponseRedirect(reverse("users"), {
            "departments": DEPARTMENTS,
            "user_types": USER_TYPES,
            "users": User.objects.all()
        })
    
def get_return_page(page, type):

    # List of the dates formated for the form
    formated_starting_dates = []
    formated_travelling_dates = []
    formated_out_dates = []

    for trip in Trip.objects.all():
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
                    "clients": Client.objects.all(),
                    "contacts": ClientContact.objects.all(),
                    "trips": Trip.objects.all(),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                    "users": User.objects.all(),
                    "entries": Entry.objects.all(),
                    "notes": Notes.objects.all(),
                }
        else:
            return {
                    "status": STATUS_OPTIONS,
                    "trip_types": TRIP_TYPES,
                    "dh_types": DH_TYPES,
                    "clients": Client.objects.all(),
                    "contacts": ClientContact.objects.all(),
                    "trips": Trip.objects.all(),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                    "users": User.objects.all(),
                    "entries": Entry.objects.all(),
                    "notes": Notes.objects.all(),
                }
        
    if page == "entries":
        if type == "error":
            return {
                    "message_new": "Completar todos los campos",
                    "entries": Entry.objects.all(),
                    "trips": Trip.objects.all(),
                    "status": STATUS_OPTIONS,
                    "importance_options": IMPORTANCE_OPTIONS,
                    "progress_options": PROGRESS_OPTIONS,
                    "users": User.objects.all(),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                }
        else:
            return {
                    "entries": Entry.objects.all(),
                    "trips": Trip.objects.all(),
                    "status": STATUS_OPTIONS,
                    "importance_options": IMPORTANCE_OPTIONS,
                    "progress_options": PROGRESS_OPTIONS,
                    "users": User.objects.all(),
                    "formated_starting_dates": formated_starting_dates,
                    "formated_travelling_dates": formated_travelling_dates,
                    "formated_out_dates": formated_out_dates,
                }


@login_required
def create_trip(request):

    if request.method == "POST":
        name = request.POST["name"]
        starting_date = request.POST["starting_date"]
        travelling_date = request.POST["travelling_date"]
        client_form = request.POST["client"]
        contact_form = request.POST["contact"]
        client_reference = request.POST["client_reference"]
        status = request.POST["status"]

        if not name or not starting_date or not client_form or not contact_form or not status:
            return render(request, "intranet/trips.html", get_return_page("trips", "error") )
        
        # Get the client from the client ID of the form
        client = Client.objects.get(id=client_form)

        # Get the contact from the contact ID of the form
        contact = ClientContact.objects.get(id=contact_form)

        # Get the department from the user department
        department = request.user.department

        # Set the default undefined users for the new trip booking options
        responsable_user = User.objects.get(pk=19)
        operations_user = User.objects.get(pk=19)
        dh = User.objects.get(pk=19)

        # Creates the model of the contact from the form information
        new_trip = Trip.objects.create(
            name=name,
            status=status,
            client=client,
            client_reference=client_reference,
            starting_date=starting_date,
            travelling_date=travelling_date,
            contact=contact,
            department=department,
            responsable_user=responsable_user,
            operations_user=operations_user,
            dh=dh,
            creation_user=request.user
        )
        new_trip.save()

        #return HttpResponseRedirect(reverse("trips"), get_return_page("trips", ""))
        return HttpResponse(status=204)

    else:
        return render(request, "intranet/trips.html", get_return_page("trips", ""))
    
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
        tourplanId = request.POST["tourplanId"]
        itId = request.POST["itId"]
        trip_type = request.POST["trip_type"]
        dh_type = request.POST["dh_type"]
        responsable_user_form = request.POST["responsable_user"]
        operations_user_form = request.POST["operations_user"]
        dh_form = request.POST["dh"]
        out_date_form = request.POST["out_date"]
        guide = request.POST["guide"]


        if not name or not starting_date_form or not client_form or not contact_form or not status or not quantity_pax:
            return render(request, "intranet/trips.html", get_return_page("trips", "error"))
        
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

        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", ""))
    

@login_required
def create_note(request, trip_id):

    trip = Trip.objects.get(id=trip_id)

    # If method is POST it will create the new client
    if request.method == "POST":

        # Gets the information from the form
        content = request.POST["content"]

        # Validations
        if not content:
            return render(request, "intranet/pendings.html", get_return_page("trips", "error"))


        # Creates the model of the note from the form information
        new_note = Notes.objects.create(
            user=request.user,
            trip=trip,
            content=content,
            creation_date=datetime.now(),
        )
        new_note.save()

        return HttpResponseRedirect(reverse("trips"), get_return_page("trips", ""))


@login_required
def pendings(request):

    # Shows all entries
    return render(request, "intranet/pendings.html", get_return_page("entries", ""))
    
@login_required
def create_entry(request, trip_id):

    # Get the trip from the trip ID of the button
    trip = Trip.objects.get(id=trip_id)

    if request.method == "POST":
        starting_date = request.POST["starting_date"]
        status = request.POST["status"]
        importance = request.POST["importance"]
        user_working_form = request.POST["user_working"]

        # Validations of the form
        if not starting_date or not status or not importance or not user_working_form:
            return render(request, "intranet/new_entry.html", {
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "trip": trip,
            })
        
        # Get the user from the username in the form
        user_working = User.objects.get(username=user_working_form)

        # Get the elements for the last and first entries
        last_entry = Entry.objects.filter(trip=trip).filter(status="Quote").last()
        first_entry = Entry.objects.filter(trip=trip).first()

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
                trip.save()
            version = int(trip.version) + 1
            version_quote = trip.version_quote
            user_creator = user_working
            trip.version += 1
        else:
            version = int(trip.version) + 1
            version_quote = trip.version
            user_creator = user_working
            trip.version = version

        trip.save()

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
        )
        new_entry.save()

        return HttpResponse(status=204)

    else:
        return render(request, "intranet/new_entry.html", {
            "entries": Entry.objects.all(),
            "trips": Trip.objects.all(),
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

    iso_starting_date = entry.starting_date.isoformat()
    formated_starting_date = iso_starting_date[:16]

    if request.method == "POST":
        starting_date = request.POST["starting_date"]
        status = request.POST["status"]
        importance = request.POST["importance"]
        user_working_form = request.POST["user_working"]
        version = request.POST["version"]
        user_creator_form = request.POST["user_creator"]
        user_working_form = request.POST["user_working"]
        amount = request.POST["amount"]
        progress = request.POST["progress"]
        closing_date_form = request.POST["closing_date"]

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
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "entry": entry,
                "formated_starting_date": formated_starting_date
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
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "entry": entry,
                "formated_starting_date": formated_starting_date
            })
        elif (status == "Quote" or status == "Booking" or status == "Cancelado") and isClosed and empty_amount == True:
            return render(request, "intranet/edit_entry.html", {
                "message": "El monto es obligatorio para status Quote y Booking",
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
                "progress_options": PROGRESS_OPTIONS,
                "users": User.objects.all(),
                "entry": entry,
                "formated_starting_date": formated_starting_date
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
            trip.version_quote = version
        else:
            trip.version = version

        if isClosed == True:
            closing_date = datetime.fromisoformat(closing_date_form)
            entry.closing_date = closing_date

        if empty_amount == False:
            trip.amount = amount
            entry.amount=amount
        
        trip.save()

        # Modifies the model of the entry with the form information
        entry.starting_date=starting_date
        entry.status=status
        entry.importance=importance
        entry.user_working=user_working
        entry.user_creator=user_creator       
        entry.progress=progress
        entry.isClosed=isClosed

        if status == "Quote":
            entry.version_quote=version
        else:
            entry.version=version

        entry.save()

        return HttpResponseRedirect(reverse("entries"), {
            "entries": Entry.objects.all(),
            "trips": Trip.objects.all(),
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "entry": entry,
            "formated_starting_date": formated_starting_date,
            })
    
    else:
        return render(request, "intranet/edit_entry.html", {
            "entries": Entry.objects.all(),
            "trips": Trip.objects.all(),
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
            "entry": entry,
            "formated_starting_date": formated_starting_date,
            })
    
@login_required
def stats(request):
    return render(request, "intranet/stats.html")

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
def json_entries(_request):

    # Get the list of the entries
    entries_object_list = Entry.objects.all()
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
        client = model_to_dict(client_object)
    except Client.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)

    # Return client contents
    if request.method == "GET":
        return JsonResponse(client, safe=False)

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
    clients = list(Client.objects.values())

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

def tourplan_files(request):
    return HttpResponseRedirect(reverse("trips"), get_return_page("trips", ""))

def tourplan_costs(request):
    return HttpResponseRedirect(reverse("tariff"))