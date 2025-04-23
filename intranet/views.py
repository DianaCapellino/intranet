from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.utils.datastructures import MultiValueDictKeyError
from django.db import IntegrityError
from .models import User, Country, Client, Trip, Entry, Notes, CountryForm, ClientForm, ClientContact, DEPARTMENTS, STATUS_OPTIONS, IMPORTANCE_OPTIONS, PROGRESS_OPTIONS
import json

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

@login_required
def create_country(request):

    # If method is POST it will create the new country
    if request.method == "POST":

        form = CountryForm(request.POST)

        if form.is_valid():
            new_country = form.save(commit=False)
            new_country.save()
            form.save_m2m()

            # After saving the listing it redirects to the main page
            return HttpResponseRedirect(reverse("countries"))
        
        # If there are any errors in the form, it will display the form again
        else:
            return render(request, "intranet/countries.html", {
                "form": form
            })
    
    # If method is GET it displays the form to add new country
    else:
        return render(request, "intranet/countries.html", {
            "form": CountryForm(),
            "countries": Country.objects.all()
        })
    
@login_required
def create_client(request):

    # If method is POST it will create the new client
    if request.method == "POST":

        form = ClientForm(request.POST)

        if form.is_valid():
            new_client = form.save(commit=False)
            new_client.save()
            form.save_m2m()

            # After saving the listing it redirects to the main page
            return HttpResponseRedirect(reverse("clients"))
        
        # If there are any errors in the form, it will display the form again
        else:
            return render(request, "intranet/clients.html", {
                "form": form
            })
    
    # If method is GET it displays the form to add new client
    else:
        return render(request, "intranet/clients.html", {
            "form": ClientForm(),
            "clients": Client.objects.all()
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
    

@login_required
@csrf_exempt
def jsontrips(_request):

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