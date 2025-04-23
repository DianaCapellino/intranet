from django.contrib import admin
from .models import User, Trip, Client, ClientContact, Entry, Holidays, Country

admin.site.register(User)
admin.site.register(Trip)
admin.site.register(Client)
admin.site.register(ClientContact)
admin.site.register(Entry)
admin.site.register(Holidays)
admin.site.register(Country)