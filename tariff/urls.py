from django.urls import path
from . import views

urlpatterns = [
    path("",views.tariff, name="tariff"),
    path("tp_mod_list", views.tp_mod_list, name="tp_mod_list")
]