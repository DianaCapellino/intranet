from django.urls import path
from . import views

urlpatterns = [
    path("",views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("countries", views.create_country, name="countries"),
    path("clients", views.create_client, name="clients"),
    path("client_contacts", views.create_client_contact, name="client_contacts"),
    path("users", views.create_user, name="users"),
    path("trips", views.create_trip, name="trips"),

    # API routes
    path("trip/json", views.jsontrips, name="jsontrips"),
    path("trip/json/<int:trip_id>", views.jsontrip, name="jsontrip"),
]