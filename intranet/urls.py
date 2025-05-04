from django.urls import path
from . import views

urlpatterns = [
    path("",views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("countries", views.create_country, name="countries"),
    path("clients", views.create_client, name="clients"),
    path("contacts", views.create_client_contact, name="contacts"),
    path("users", views.create_user, name="users"),
    path("trips", views.create_trip, name="trips"),
    path("error", views.error, name="error"),
    path("pendings", views.pendings, name="pendings"),
    path("stats", views.stats, name="stats"),
    path("create_entry/<int:trip_id>", views.create_entry, name="create_entry"),

    # API routes trips and entries
    path("trip/json", views.jsontrips, name="jsontrips"),
    path("trip/json/<int:trip_id>", views.jsontrip, name="jsontrip"),
    path("json_entries", views.json_entries, name="json_entries"),
    path("jsontrip_entries/<int:trip_id>", views.jsontrip_entries, name="jsontrip_entries"),
    path("json_entries/<int:entry_id>", views.json_entry, name="json_entry"),

    # API routes for configurations
    path("countries/json/<int:country_id>", views.jsoncountry, name="jsoncountry"),
    path("clients/json/<int:client_id>", views.jsonclient, name="jsonclient"),
    path("contacts/json/<int:contact_id>", views.jsoncontact, name="jsoncontact"),
    path("users/json/<int:user_id>", views.jsonuser, name="jsonuser"),
]