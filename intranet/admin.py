from django.contrib import admin
from .models import User, Trip, Client, ClientContact, Entry, Holidays, Country, CsvFileTourplanFiles, Notes, Search, Absence

admin.site.register(User)
admin.site.register(Trip)
admin.site.register(Client)
admin.site.register(ClientContact)
admin.site.register(Entry)
admin.site.register(Holidays)
admin.site.register(Absence)
admin.site.register(Country)
admin.site.register(CsvFileTourplanFiles)
admin.site.register(Notes)
admin.site.register(Search)