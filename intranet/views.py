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
from .models import User, Country, Client, Trip, Entry, Notes, ClientContact, DEPARTMENTS, STATUS_OPTIONS, IMPORTANCE_OPTIONS, PROGRESS_OPTIONS
import json
import datetime

def index (request):
    return render(request, "intranet/index.html", {
        "trips": Trip.objects.all()
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
        try:
            isAdmin = request.POST['admin']
        except MultiValueDictKeyError:
            isAdmin = False

        if isAdmin != False:
            isAdmin = True

        # Validations
        if not name or not email or not username or not password or not department:
            return render(request, "intranet/users.html", {
                "message": "Todos los campos deben ser completados",
                "departments": DEPARTMENTS,
                "users": User.objects.all()
            })
        
        if len(username) < 2 or len(username) > 3:
            return render(request, "intranet/users.html", {
                "message": "El usuario debe tener entre 2 y 3 caracteres",
                "departments": DEPARTMENTS,
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
            )
            new_user.save()
        except IntegrityError:
            return render(request, "intranet/users.html", {
                "message": "El usuario ya existe",
                "departments": DEPARTMENTS,
                "users": User.objects.all()
            })

        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "users": User.objects.all()
        })

    else:
        return render(request, "intranet/users.html", {
            "departments": DEPARTMENTS,
            "users": User.objects.all()
        })
    

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
            return render(request, "intranet/trips.html", {
                "message": "Completar los campos obligatorios",
                "status": STATUS_OPTIONS,
                "clients": Client.objects.all(),
                "contacts": ClientContact.objects.all(),
                "trips": Trip.objects.all()
            })
        
        # Get the client from the client ID of the form
        client = Client.objects.get(id=client_form)

        # Get the contact from the contact ID of the form
        contact = ClientContact.objects.get(id=contact_form)

        # Get the department from the user department
        department = request.user.department

        # Creates the model of the contact from the form information
        new_trip = Trip.objects.create(
            name=name,
            status=status,
            client=client,
            client_reference=client_reference,
            starting_date=starting_date,
            travelling_date=travelling_date,
            contact=contact,
            department=department
        )
        new_trip.save()

        return render(request, "intranet/trips.html", {
            "status": STATUS_OPTIONS,
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all(),
            "trips": Trip.objects.all()
        })

    else:
        return render(request, "intranet/trips.html", {
            "status": STATUS_OPTIONS,
            "clients": Client.objects.all(),
            "contacts": ClientContact.objects.all(),
            "trips": Trip.objects.all()
        })
    

def pendings(request):

    # Creates new entry
    if request.method == "POST":

        trip_form = request.POST["trip"]
        starting_date = request.POST["starting_date"]
        status = request.POST["status"]
        importance = request.POST["importance"]
        user_working_form = request.POST["user_working"]

        if not trip_form or not starting_date or not status or not importance or not user_working_form:
            return render(request, "intranet/pendings.html", {
                "message": "Completar todos los campos",
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
            })
        
        # Get the trip from the trip ID of the form
        trip = Trip.objects.get(id=trip_form)

        # Get the user from the user ID of the form
        user_working = User.objects.get(id=user_working_form)

        # Get the elements for the last and first entries
        last_entry = Entry.objects.filter(trip=trip).last()
        first_entry = Entry.objects.filter(trip=trip).first()

        # Set the version of the quote and booking defaults
        if trip.version != "0":

            # When a quote already exists
            if status == "Quote":

                # When it is a quote but the status of the trip is a booking
                if trip.status == "Booking":
                    version_booking = trip.version
                    version_quote = chr(int(ord(last_entry.version_quote)) + 1)

                # When it is quote but the trip is other options that are not a booking
                else:
                    version_booking = 0
                    version_quote = chr(int(ord(trip.version)) + 1)
            
            # When it is not a quote
            else:
                version_quote = chr(int(ord(trip.version)) + 1)
                version_booking = int(trip.version) + 1
        else:
            version_quote = "A"
            if status == "Booking":
                version_booking = 1
            else:
                version_booking = 0


        # Creates defauls according to the trip status
        if trip.version == "0":
            if status == "Booking":
                # If it is the first booking version by default it will be the user SC
                user_creator = User.objects.get(id=12)
                trip.conversion_date = django.utils.timezone.now
            else:
                user_creator = user_working
            
        else:
            if trip.status == "Quote" and status == "Booking":
                # Get the last version trip
                user_creator = first_entry.user_working
                trip.conversion_date = django.utils.timezone.now
            else:
                user_creator = last_entry.user_working                

        # Creates the model of the contact from the form information
        new_entry = Entry.objects.create(
            trip=trip,
            starting_date=starting_date,
            status=status,
            importance=importance,
            user_working=user_working,
            user_creator=user_creator,
            version_quote=version_quote,
            version_booking=version_booking,
        )
        new_entry.save()

        # Updates the trip version and amounts
        if status == "Quote":
            trip.version = version_quote
        else:
            trip.version = str(version_booking)

        return HttpResponseRedirect(reverse("create_entry", kwargs={"entry_id": new_entry.id}))
    
    # Shows all entries
    else:
        return render(request, "intranet/pendings.html", {
            "entries": Entry.objects.all(),
            "trips": Trip.objects.all(),
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
            "progress_options": PROGRESS_OPTIONS,
            "users": User.objects.all(),
        })
    
@login_required
@csrf_exempt
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
            return render(request, "intranet/pendings.html", {
                "message": "Completar todos los campos",
                "entries": Entry.objects.all(),
                "trips": Trip.objects.all(),
                "status": STATUS_OPTIONS,
                "importance_options": IMPORTANCE_OPTIONS,
            })
        
        # Get the user from the username in the form
        user_working = User.objects.get(username=user_working_form)

        # Get the elements for the last and first entries
        last_entry = Entry.objects.filter(trip=trip).filter(status="Quote").last()
        first_entry = Entry.objects.filter(trip=trip).first()

        # Set the version of the quote and booking defaults
        if status == "Quote":
            version_quote = chr(int(ord(last_entry.version_quote)) + 1)
            version = trip.version
            user_creator = user_working
            trip.version = version_quote
        else:
            version_quote = trip.version
            version = int(trip.version) + 1
            user_creator = user_working
            trip.version = version

        progress = PROGRESS_OPTIONS[0]
        # Creates defauls according to the trip status


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

        return render(request, "intranet/pendings.html", {
            "entries": Entry.objects.all(),
            "trips": Trip.objects.all(),
            "status": STATUS_OPTIONS,
            "importance_options": IMPORTANCE_OPTIONS,
        })
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
    
def stats(request):
    return render(request, "intranet/stats.html")

@login_required
@csrf_exempt
def jsontrips(_request):

    # Get the list of the trips
    trips = list(Trip.objects.values())
    data = {'trips': trips}
    return JsonResponse(data)


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
    entries = list(Entry.objects.values())
    data = {'entries': entries}
    return JsonResponse(data)


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
            "error": "GET or PUT or DELETE request required."
        }, status=400)
    
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
        data = json.loads(request.body)

        # Update information of the country
        country_object.name = data["name"]
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
        client_object.name = data["name"]


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
        contact_object.name = data["name"]


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