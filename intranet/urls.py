from django.urls import path
from . import views

urlpatterns = [
    path("",views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("error", views.error, name="error"),
    path("entries", views.pendings, name="entries"),
    path("stats", views.stats, name="stats"),
    path("holidays", views.holidays, name="holidays"),

    # Paths for creating items
    path("countries", views.create_country, name="countries"),
    path("clients", views.create_client, name="clients"),
    path("contacts", views.create_client_contact, name="contacts"),
    path("users", views.create_user, name="users"),
    path("trips", views.create_trip, name="trips"),
    path("trips/clean", views.clean_search, name="clean_search"),
    path("create_entry/<int:trip_id>", views.create_entry, name="create_entry"),
    path("create_note/<int:trip_id>", views.create_note, name="create_note"),

    # Paths for modifying items
    path("modify_user/<int:user_id>", views.modify_user, name="modify_user"),
    path("modify_country/<int:country_id>", views.modify_country, name="modify_country"),
    path("modify_client/<int:client_id>", views.modify_client, name="modify_client"),
    path("modify_contact/<int:contact_id>", views.modify_contact, name="modify_contact"),
    path("modify_trip/<int:trip_id>", views.modify_trip, name="modify_trip"),
    path("modify_entry/<int:entry_id>", views.modify_entry, name="modify_entry"),

    # API routes trips and entries
    path("trips/json", views.jsontrips, name="jsontrips"),
    path("trips/json/<int:trip_id>", views.jsontrip, name="jsontrip"),
    path("entries_trip/json/<int:trip_id>", views.jsontrip_entries, name="jsontrip_entries"),
    path("notes_trip/json/<int:trip_id>", views.jsontrip_notes, name="jsontrip_notes"),
    path("entries/json/<int:entry_id>", views.json_entry, name="json_entry"),
    path("entries/json/pendings", views.json_pendings, name="json_pendings"),
    path("entries/json/last_entry", views.json_last_entry, name="json_last_entry"),

    # API routes for configurations
    path("countries/json/<int:country_id>", views.jsoncountry, name="jsoncountry"),
    path("clients/json/<int:client_id>", views.jsonclient, name="jsonclient"),
    path("contacts/json/<int:contact_id>", views.jsoncontact, name="jsoncontact"),
    path("users/json/<int:user_id>", views.jsonuser, name="jsonuser"),
    path("countries/json", views.json_countries, name="json_countries"),
    path("clients/json", views.json_clients, name="json_clients"),
    path("contacts/json", views.json_contacts, name="json_contacts"),
    path("users/json", views.json_users, name="json_users"),
    path("entries/json", views.json_entries, name="json_entries"),
    path("holidays/json", views.json_holidays, name="json_holidays"),

    path("read_emails", views.read_emails, name="read_emails"),

    path("tourplan_files", views.tourplan_files, name="tourplan_files"),
    path("intranet_files", views.intranet_files, name="intranet_files"),
    path("advanced_search", views.advanced_search, name="advanced_search"),
]