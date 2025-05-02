from django.contrib.auth.models import AbstractUser
from django.db import models
import django.utils.timezone
from django.forms import ModelForm

STATUS_OPTIONS = [
    ("Quote", "Quote"),
    ("Booking", "Booking"),
    ("Quote Modification", "Quote Modification"),
    ("Booking Modification", "Booking Modification"),
    ("Final Itinerary", "Final Itinerary"),
    ("Void", "Void"),
    ("Cancelled", "Cancelled"),
    ("Program", "Program"),
    ("Other", "Other")
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
    ("5 - Finalizado", "Finalizado")
]

class User(AbstractUser):
    other_name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    department = models.CharField(max_length=64, choices=DEPARTMENTS)
    isAdmin = models.BooleanField(default=False)

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
    

class CountryForm(ModelForm):
    class Meta:
        model = Country
        fields = [
            'name',
            'code',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control-sm'})
        self.fields['code'].widget.attrs.update({'class': 'form-control-sm'})
        self.fields['name'].widget.attrs.update({'placeholder': 'Nombre'})
        self.fields['code'].widget.attrs.update({'placeholder': 'Código'})


class Client(models.Model):
    name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="client_countries")
    department = models.CharField(max_length=64, choices=DEPARTMENTS)

    def __str__(self):
        return f"{self.name}"


class ClientContact(models.Model):
    name = models.CharField(max_length=64)
    isActivated = models.BooleanField(default=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="client_contacts", default="1")
    email = models.EmailField(default='quote@aliwenincoming.com.ar')

    def __str__(self):
        return f"{self.name}"


class Trip(models.Model):
    name = models.CharField(max_length=64)
    tourplanId = models.CharField(max_length=64, null=True)
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS)
    version = models.CharField(max_length=64, null=True)
    amount = models.FloatField(null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="trip_clients")
    client_reference = models.CharField(max_length=64, null=True)
    starting_date = models.DateField(default=django.utils.timezone.now, verbose_name='starting date')
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='starting date')
    conversion_date = models.DateTimeField(null=True, verbose_name='conversion date')
    travelling_date = models.DateField(default=django.utils.timezone.now, verbose_name='travelling date')
    contact = models.ForeignKey(ClientContact, on_delete=models.CASCADE, related_name="trip_contacts")
    department = models.CharField(max_length=64, choices=DEPARTMENTS)

    def __str__(self):
        return f"{self.name}"


class Notes(models.Model):
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_notes")
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date')
    content = models.CharField(max_length=512)


class Entry(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="entry_trips")
    version = models.IntegerField(default=1)
    user_creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_creator_users")
    user_working = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_working_users")
    starting_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='starting date')
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date')
    closing_date = models.DateTimeField(null=True, blank=True, verbose_name='closing date')
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS)
    amount = models.FloatField(null=True, blank=True)
    isClosed = models.BooleanField(default=False)
    importance = models.CharField(max_length=64, choices=IMPORTANCE_OPTIONS)
    progress = models.CharField(max_length=64, choices=PROGRESS_OPTIONS, default=PROGRESS_OPTIONS[0])

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
            "version": self.version,
            "user_creator": self.user_creator.username,
            "user_working": self.user_working.username,
            "starting_date": self.starting_date.strftime("%d %b %Y, %I:%M %p"),
            "last_modification_date": self.last_modification_date.strftime("%d %b %Y, %I:%M %p"),
            "closing_date": self.closing_date.strftime("%d %b %Y, %I:%M %p"),
            "status": self.status,
            "amount": self.amount,
            "isClosed": self.isClosed,
            "importance": self.importance,
            "progress": self.progress,
        }
        

class Holidays(models.Model):
    date = models.DateField(verbose_name="holidays date")
    working_user = models.ManyToManyField(User, related_name="working_users", blank=True)