from django.contrib.auth.models import AbstractUser
from django.db import models
import django.utils.timezone
from datetime import datetime, timedelta
from django import forms

STATUS_OPTIONS = [
    ("Quote", "Quote"),
    ("Booking", "Booking"),
    ("Final Itinerary", "Final Itinerary"),
    ("Void", "Void"),
    ("Cancelado", "Cancelado"),
    ("Programa", "Programa"),
    ("Bloqueo", "Bloqueo"),
    ("Otro", "Otro")
]

IMPORTANCE_OPTIONS = [
    ("1 - BAJA - min", "BAJA - min"),
    ("2 - BAJA - standard", "BAJA - standard"),
    ("3 - BAJA - plus", "BAJA - plus"),
    ("4 - MED - min", "MED - min"),
    ("5 - MED - standard", "MED - standard"),
    ("6 - MED - pide urgente", "MED - pide urgente"),
    ("7 - ALTA - standard", "ALTA - standard"),
    ("8 - ALTA - pide urgente", "ALTA - pide urgente"),
    ("9 - ALTA - cliente nuevo", "ALTA - cliente nuevo"),
    ("10 - ALTA - last minute", "ALTA - last minute")
]

DEPARTMENTS = [
    ("AI", "Aliwen"),
    ("SH", "Say Hueque")
]

PROGRESS_OPTIONS = [
    ("0 - No comenzado", "No comenzado"),
    ("1 - Analizado", "Analizado"),
    ("2 - Contactados proveedores", "Contactados proveedores"),
    ("3 - Enviado Status", "Enviado status"),
    ("4 - Falta respuesta proveedor/cliente", "Falta respuesta proveedor/cliente"),
    ("5 - Finalizado", "Finalizado"),
]

DH_TYPES = [
    ("B", "Basic"),
    ("S", "Standard"),
    ("F", "Full"),
    ("Sin definir", "Sin definir"),
    ("No", "Sin seguimiento"),
]

TRIP_TYPES = [
    ("FIT's", "FIT's"),
    ("Personal Trips", "Personal Trips"),
    ("FAM Tours", "FAM Tours"),
    ("Grupos", "Grupos"),
]

USER_TYPES = [
    ("Ventas", "Ventas"),
    ("Operaciones", "Operaciones"),
    ("DH", "DH"),
    ("Internal", "Internal"),
    ("Client", "Client"),
]

CLIENT_CATEGORIES = [
    ("A", "A"),
    ("B", "B"),
    ("C", "C"),
]

MONTHS = [
    (1, "January"),
    (2, "February"),
    (3, "March"),
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December")
]

DIFFICULTY_OPTIONS = [
    ("1", "Muy Fácil"),
    ("2", "Fácil"),
    ("3", "Moderado"),
    ("4", "Complejo"),
    ("5", "Muy Complejo"),
]

class User(AbstractUser):
    other_name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    department = models.CharField(max_length=64, choices=DEPARTMENTS)
    isAdmin = models.BooleanField(default=False)
    userType = models.CharField(max_length=64, choices=USER_TYPES, default="Sales")

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.username}"
     

class Country(models.Model):
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Client(models.Model):
    name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="client_countries")
    department = models.CharField(max_length=64, choices=DEPARTMENTS)
    category = models.CharField(max_length=64, choices=CLIENT_CATEGORIES, default="B")
    tp_id = models.CharField(max_length=64, blank=True, null=True, default="")

    def __str__(self):
        return f"{self.name}"
    
    def serialize(self):
        return {
            "name": self.name,
            "isActivated": self.isActivated,
            "country": f"{self.country.code} - {self.country.name}",
            "department": self.department,
            "category": self.category,
        }


class ClientContact(models.Model):
    name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="client_contacts", default="1")
    email = models.EmailField(default='quote@aliwenincoming.com.ar')

    def __str__(self):
        return f"{self.name}"


class Trip(models.Model):
    name = models.CharField(max_length=64)
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS)
    version = models.IntegerField(blank=True, null=True, default=0)
    version_quote = models.CharField(max_length=64, null=True, default="@")
    difficulty = models.CharField(max_length=64, choices=DIFFICULTY_OPTIONS)
    amount = models.FloatField(null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="trip_clients")
    client_reference = models.CharField(max_length=64, null=True, default="n/a")
    starting_date = models.DateField(default=django.utils.timezone.now, verbose_name='starting date')
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date')
    conversion_date = models.DateTimeField(null=True, verbose_name='conversion date')
    travelling_date = models.DateField(default=django.utils.timezone.now, verbose_name='travelling date')
    out_date = models.DateField(null=True, verbose_name='out_date')
    contact = models.ForeignKey(ClientContact, on_delete=models.CASCADE, related_name="trip_contacts")
    department = models.CharField(max_length=64, choices=DEPARTMENTS)
    tourplanId = models.CharField(max_length=64, null=True, blank=True, default="")
    itId = models.CharField(max_length=64, null=True, blank=True, default="")
    dh_type = models.CharField(max_length=64, choices=DH_TYPES, default="Sin definir")
    trip_type = models.CharField(max_length=64, choices=TRIP_TYPES, default="FIT's")
    responsable_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trip_responsable_users", null=True)
    operations_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trip_operations_users", null=True)
    quantity_pax = models.IntegerField(default=2)
    rent_perc = models.FloatField(default=0, blank=True, null=True)
    guide = models.CharField(max_length=64, null=True, blank=True, default="")
    dh = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dh_user", null=True)
    creation_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="creation_users")

    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        ordering = ["-creation_date"]


class Notes(models.Model):
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date')
    user = models.ForeignKey(User,on_delete=models.CASCADE, related_name="notes_user")
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_notes")
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date', null=True)
    content = models.CharField(max_length=512)

    def __str__(self):
        return f"{self.content} (by: {self.user})"


class Entry(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="entry_trips")
    version_quote = models.CharField(max_length=64, default="A")
    version = models.IntegerField(blank=True, null=True, default=0)
    user_creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_creator_users")
    user_working = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_working_users")
    starting_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='starting date')
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date')
    closing_date = models.DateTimeField(null=True, blank=True, verbose_name='closing date', default=django.utils.timezone.now)
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS)
    amount = models.FloatField(null=True, blank=True)
    isClosed = models.BooleanField(default=False)
    importance = models.CharField(max_length=64, choices=IMPORTANCE_OPTIONS)
    progress = models.CharField(max_length=64, choices=PROGRESS_OPTIONS)
    note = models.CharField(max_length=500, null=True, blank=True)

    @property
    def response_days(self):
        if self.closing_date != None:
            return self.closing_date - self.starting_date
        else:
            return django.utils.timezone.now - self.starting_date

    class Meta:
        ordering = ["-starting_date"]

    
    def serialize(self):
        return {
            "id": self.id,
            "trip": self.trip.name,
            "trip_id": self.trip.id,
            "version_quote": self.version_quote,
            "version": self.version,
            "user_creator": self.user_creator.username,
            "user_working": self.user_working.username,
            "starting_date": (self.starting_date - timedelta(hours=3)).strftime("%Y/%m/%d - %I:%M %p"),
            "last_modification_date": (self.last_modification_date - timedelta(hours=3)).strftime("%d %b %Y, %I:%M %p"),
            "closing_date": (self.closing_date - timedelta(hours=3)).strftime("%Y/%m/%d - %I:%M %p"),
            "status": self.status,
            "amount": self.amount,
            "isClosed": self.isClosed,
            "importance": self.importance,
            "progress": self.progress,
        }
        

class Holidays(models.Model):
    date = models.DateField(verbose_name="holidays date")
    working_user = models.ManyToManyField(User, related_name="working_users", blank=True)


class Absence(models.Model):
    date = models.DateField(verbose_name="holidays date")
    absence_user = models.ManyToManyField(User, related_name="absence_users", blank=True)    


class CsvFileTourplanFiles (models.Model):
    file_name = models.FileField(upload_to="csvFiles")
    uploaded_time = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Csv File ID: {self.id} - Csv Name: {self.file_name}"
    
class CsvFormTourplanFiles (forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
            visible.field.widget.attrs['aria-describedby'] = 'input-file'
            visible.field.widget.attrs['aria-label'] = 'SUBIR'

    class Meta:
        model = CsvFileTourplanFiles
        fields = ('file_name',)
        labels = {
            "file_name": ""
        }