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
    ("1", "BAJA - min"),
    ("2", "BAJA - standard"),
    ("3", "BAJA - plus"),
    ("4", "MED - min"),
    ("5", "MED - standard"),
    ("6", "MED - pide urgente"),
    ("7", "ALTA - standard"),
    ("8", "ALTA - pide urgente"),
    ("9", "ALTA - cliente nuevo"),
    ("10", "ALTA - last minute")
]

DEPARTMENTS = [
    ("AI", "Aliwen"),
    ("SH", "Say Hueque")
]

PROGRESS_OPTIONS = [
    ("0", "No comenzado"),
    ("1", "Analizado"),
    ("2", "Contactados proveedores"),
    ("3", "Enviado status"),
    ("4", "Falta respuesta proveedor/cliente"),
    ("5", "Finalizado")
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

    def __str__(self):
        return f"{self.name}"
    

class ClientForm(ModelForm):
    class Meta:
        model = Client
        fields = [
            'name',
            'isActivated',
            'country',
        ]


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
    starting_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='starting date')
    conversion_date = models.DateTimeField(null=True, verbose_name='conversion date')
    travelling_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='travelling date')
    contact = models.ForeignKey(ClientContact, on_delete=models.CASCADE, related_name="trip_contacts")
    department = models.CharField(max_length=64, choices=DEPARTMENTS)

    def __str__(self):
        return f"{self.name} de {self.client} - {self.status} {self.version}"


class Notes(models.Model):
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_notes")
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date')
    content = models.CharField(max_length=512)


class Entry(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="entry_trips")
    version = models.IntegerField()
    user_creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_creator_users")
    user_working = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entry_working_users")
    starting_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='starting date')
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date')
    closing_date = models.DateTimeField(null=True, verbose_name='closing date')
    response_days = models.IntegerField()
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS)
    amount = models.FloatField(null=True)
    isClosed = models.BooleanField(default=False)
    importance = models.CharField(max_length=64, choices=IMPORTANCE_OPTIONS)
    progress = models.CharField(max_length=64, choices=PROGRESS_OPTIONS, default=PROGRESS_OPTIONS[0])


class Holidays(models.Model):
    date = models.DateField(verbose_name="holidays date")