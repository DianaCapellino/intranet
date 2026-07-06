from django.db import models
from intranet.models import Client, User, Trip
from multiselectfield import MultiSelectField
import django.utils.timezone
from django import forms

SRV = [
    ("AC", "Accommodation"),
    ("NA", "Non-accommodation"),
]

FCU_OPTIONS = [
    ("Group", "Group"),
    ("Person", "Person"),
]

TAXES = [
    (0, "0 - No taxes"),
    (10.5, "10.5 - Transport"),
    (21, "21 - Other"),
]

AC_OPTIONS = [
    ("SGL", "SGL"),
    ("DBL", "DBL"),
    ("TPL", "TPL"),
    ("CPL", "CPL")
]

NA_OPTIONS = [
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5", "5"),
    ("6", "6"),
    ("SIB", "SIB"),
]

ATTRACTIONS = [
    ("CITY", "City"),
    ("FALLS", "Falls"),
    ("MOUNTAINS", "Mountains"),
    ("COUNTRYSIDE", "Countryside"),
    ("GLACIERS", "Glaciers"),
    ("WILDLIFE", "Wildlife")
]

INTERESTS = [
    ("FOOD", "Food"),
    ("MUSIC", "Music"),
    ("ART", "Art"),
    ("TREKKING", "Trekking"),
    ("ACTIVE", "Active Activities"),
    ("RELAXING", "Relaxing"),
    ("LANDSCAPES", "Landscapes"),
    ("NATURE", "Nature"),
    ("CULTURE", "Culture")
]

CHILDREN_RANKING_OPTIONS = [
    (1, "1"),
    (2, "2"),
    (3, "3"),
    (4, "4"),
    (5, "5"),
]

DISABLED_RANKING_OPTIONS = [
    (1, "1"),
    (2, "2"),
    (3, "3"),
    (4, "4"),
    (5, "5"),
]

SUSTENTABILITY_RANKING_OPTIONS = [
    (1, "1"),
    (2, "2"),
    (3, "3"),
    (4, "4"),
    (5, "5"),
]

HOTEL_QUALITY_OPTIONS = [
    ("5***** Luxury", "5***** Luxury"),
    ("5***** Superior", "5***** Superior"),
    ("5***** Standard", "5***** Standard"),
    ("4**** Superior", "4**** Superior"),
    ("4**** Standard", "4**** Standard"),
    ("3*** Superior", "3*** Superior"),
    ("3*** Standard", "3*** Standard"),
    ("Boutique Luxury", "Boutique Luxury"),
    ("Boutique Superior", "Boutique Superior"),
    ("Boutique Standard", "Boutique Standard"),
    ("Winery Luxury", "Winery Luxury"),
    ("Winery Superior", "Winery Superior"),
    ("Winery Standard", "Winery Standard"),
    ("Estancia Luxury", "Estancia Luxury"),
    ("Estancia Superior", "Estancia Superior"),
    ("Estancia Standard", "Estancia Standard"),
    ("Glamping Superior", "Glamping Superior"),
    ("Glamping Standard", "Glamping Standard"),
]

STATUS = [
    ("Confirmed", "Confirmed"),
    ("Provisional", "Provisional"),
]

MARGIN_OPTIONS = [
    ("Low", "Low"),
    ("Regular", "Regular"),
    ("High", "High"),
]


TYPE_QUALITY = [
    ("Calidad del servicio", "Calidad del servicio"),
    ("Demora/rapidez", "Demora/rapidez"),
    ("Salud/higiene", "Salud/higiene"),
    ("Inclusiones", "Inclusiones"),
    ("Otro", "Otro"),
]

SENTIMENT = [
    ("positivo", "Positivo"),
    ("neutral", "Neutral"),
    ("negativo", "Negativo"),
]

FEEDBACK_STATUS = [
    ("abierto", "Abierto"),
    ("cerrado", "Cerrado"),
]

FEEDBACK_SOURCE = [
    ("manual", "Manual"),
    ("email", "Email"),
]

INBOX_STATUS = [
    ("pendiente", "Pendiente"),
    ("confirmado", "Confirmado"),
    ("descartado", "Descartado"),
]

# Service type codes from Tourplan itinerary sheet
SERVICE_TYPE_CODES = [
    ("AC", "Accommodation"),
    ("FB", "Food & Beverages"),
    ("GU", "Guide"),
    ("TF", "Transfer"),
    ("TR", "Transport"),
    ("EN", "Entrance fee"),
    ("EX", "Excursion"),
    ("CI", "Car rental"),
    ("IM", "Impuesto"),
    ("WE", "Welcome"),
    ("FT", "Flight info"),
    ("IN", "Not included"),
]

TYPE_HISTORY = [
    ("Update", "Updated existing rates"),
    ("New", "New property/product"),
    ("Add", "Added rates to existing property/product")
]

SUSTAINABLE_ACTION_CATEGORIES = [
    ('WASTE', 'Wastes / Recycle'),
    ('ENERGY', 'Energy'),
    ('PURCHASING', 'Purchasing / Efficiency'),
    ('SOCIAL', 'Social / Culture'),
    ('SOIL', 'Soil / Food / Environment'),
    ('GUEST', 'Guest Participation'),
    ('OTHER', 'Other'),
]

TOURS_TIMING = [
    ("AM", "Morning"),
    ("PM", "Afternoon"),
    ("AM/PM", "Morning & Afternoon"),
    ("Night", "Evening"),
]

class Location(models.Model):
    code = models.CharField(max_length=3)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=500, blank=True)
    pic1_url = models.CharField(max_length=500, blank=True, null=True)
    pic2_url = models.CharField(max_length=500, blank=True, null=True)
    pic3_url = models.CharField(max_length=500, blank=True, null=True)
    children_ranking = models.PositiveSmallIntegerField(choices=CHILDREN_RANKING_OPTIONS)
    disabled_ranking = models.PositiveSmallIntegerField(choices=DISABLED_RANKING_OPTIONS)
    sustentability_ranking = models.PositiveSmallIntegerField(choices=SUSTENTABILITY_RANKING_OPTIONS)
    attractions = MultiSelectField(choices=ATTRACTIONS, max_length=500)
    interests = MultiSelectField(choices=INTERESTS, max_length=500)
    min_nights = models.PositiveSmallIntegerField()
    max_nights = models.PositiveSmallIntegerField()
    margin_svs = models.FloatField()
    margin_acc = models.FloatField()
    order = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.name}"


class SupplierGroup(models.Model):
    name = models.CharField(max_length=64)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="location_suppliers")
    order = models.PositiveIntegerField()
    type_service = models.CharField(choices=SRV, max_length=64)

    def __str__(self):
        return f"{self.name}"


class Supplier(models.Model):
    code = models.CharField(max_length=6)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=3000, blank=True)
    pic1_url = models.CharField(max_length=500, blank=True, null=True)
    pic2_url = models.CharField(max_length=500, blank=True, null=True)
    pic3_url = models.CharField(max_length=500, blank=True, null=True)
    children_ranking = models.PositiveSmallIntegerField(choices=CHILDREN_RANKING_OPTIONS)
    disabled_ranking = models.PositiveSmallIntegerField(choices=DISABLED_RANKING_OPTIONS)
    sustentability_ranking = models.PositiveSmallIntegerField(choices=SUSTENTABILITY_RANKING_OPTIONS)
    attractions = MultiSelectField(choices=ATTRACTIONS, max_length=64, blank=True, null=True)
    interests = MultiSelectField(choices=INTERESTS, max_length=64, blank=True, null=True)

    # Notes to show in the tariff
    note = models.CharField(max_length=500, blank=True, default=None)
    child_note = models.CharField(max_length=150, blank=True, null=True)
    prepayment = models.CharField(max_length=500, null=True, blank=True)
    stay_note = models.CharField(max_length=150, null=True, blank=True)
    closing_note = models.CharField(max_length=300, null=True, blank=True)

    is_provisional = models.BooleanField(default=False, verbose_name='Provisional')
    recommended = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=9999)
    group = models.ForeignKey(SupplierGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="group_products")
    hotel_quality = models.CharField(choices=HOTEL_QUALITY_OPTIONS, max_length=64, blank=True, null=True)
    
    # Exact amount
    margin = models.FloatField()

    # Margin option
    margin_info = models.CharField(choices=MARGIN_OPTIONS, max_length=64)

    # This allows to update or not from Tourplan system
    update_tp = models.BooleanField(default=True)

    # Default exchange rate pre-filled when creating cost items for this supplier
    default_exchange = models.PositiveIntegerField(default=1)

    # Accommodation highlights
    highlight = models.CharField(max_length=500, blank=True, default='')
    highlight_sustentability = models.CharField(max_length=500, blank=True, default='')

    # General accommodation notes
    room_quantity = models.CharField(max_length=100, blank=True, default='')
    inclusions = models.CharField(max_length=500, blank=True, default='')
    bedding = models.CharField(max_length=300, blank=True, default='')

    def __str__(self):
        return f"{self.name}"

    @property
    def pos_fb_count(self):
        return self.feedback_suppliers.filter(sentiment='positivo').count()

    @property
    def neu_fb_count(self):
        return self.feedback_suppliers.filter(sentiment='neutral').count()

    @property
    def neg_fb_count(self):
        return self.feedback_suppliers.filter(sentiment='negativo').count()

    @property
    def all_feedbacks(self):
        return self.feedback_suppliers.all().order_by('-creation_date')


class ProductGroup(models.Model):
    name = models.CharField(max_length=64)
    order = models.PositiveIntegerField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="location_products")
    type_service = models.CharField(choices=SRV, max_length=64)

    def __str__(self):
        return f"{self.location} - {self.name}"


class Product(models.Model):
    code = models.CharField(max_length=6)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=3000, blank=True)
    pic1_url = models.CharField(max_length=500, blank=True, null=True)
    pic2_url = models.CharField(max_length=500, blank=True, null=True)
    pic3_url = models.CharField(max_length=500, blank=True, null=True)
    children_ranking = models.PositiveSmallIntegerField(choices=CHILDREN_RANKING_OPTIONS)
    disabled_ranking = models.PositiveSmallIntegerField(choices=DISABLED_RANKING_OPTIONS)
    sustentability_ranking = models.PositiveSmallIntegerField(choices=SUSTENTABILITY_RANKING_OPTIONS)
    attractions = MultiSelectField(choices=ATTRACTIONS, max_length=64, blank=True, null=True)
    interests = MultiSelectField(choices=INTERESTS, max_length=64, blank=True, null=True)
    isActivated = models.BooleanField(default=True)
    type_service = models.CharField(choices=SRV, max_length=64)
    recommended = models.BooleanField(default=False)

    # Supplier for the real costs
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="supplier_products")

    # Important information
    note = models.CharField(max_length=150, blank=True, null=True)
    child_note = models.CharField(max_length=150, blank=True, null=True)

    # Visible for clients
    shown = models.BooleanField(default=True)

    # Per group or per person
    fcu = models.CharField(choices=FCU_OPTIONS, max_length=64)

    # Per night is 1 or per package of x nights
    scu = models.PositiveSmallIntegerField()

    # Last working date
    lw_date = models.DateField(default=django.utils.timezone.now, verbose_name='last_working_date')

    quality = models.CharField(max_length=64, blank=True, null=True)
    order = models.PositiveIntegerField()
    group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, related_name="group_products")
    clients = models.ManyToManyField(Client, related_name="available_clients", blank=True)

    # If the tour is in the morning, afternoon or evening
    tour_timing = models.CharField(choices=TOURS_TIMING, max_length=64, blank=True, null=True)

    # Tourplan location code used to filter sync results; defaults to the product group's location code
    tp_location_code = models.CharField(max_length=10, blank=True)

    def save(self, *args, **kwargs):
        if not self.tp_location_code:
            if self.supplier and self.supplier.group and self.supplier.group.location:
                self.tp_location_code = self.supplier.group.location.code
            elif self.group and self.group.location:
                self.tp_location_code = self.group.location.code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier} - {self.name} - {self.group}"

    class Meta:
        ordering = ["order"]


class RateGroup(models.Model):
    name = models.CharField(max_length=64)
    order = models.PositiveIntegerField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="rate_products")

    def __str__(self):
        return f"{self.product} - {self.name}"


class RateLine(models.Model):
    date_from = models.DateField(verbose_name='from_date')
    date_to = models.DateField(verbose_name='to_date')
    group = models.ForeignKey(RateGroup, on_delete=models.CASCADE, related_name="group_rate")
    season = models.CharField(max_length=64)
    is_revised = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.group} - {self.date_from}/{self.date_to}"

class Rate(models.Model):
    rate_line = models.ForeignKey(RateLine, on_delete=models.CASCADE, related_name="line_rates")
    status = models.CharField(choices=STATUS, max_length=64)
    increase = models.FloatField(null=True, blank=True)
    cost = models.FloatField()
    margin = models.CharField(choices=MARGIN_OPTIONS, max_length=64)
    sell = models.PositiveIntegerField()
    sell_tourplan = models.PositiveIntegerField()
    column_options = models.CharField(max_length=64)
    has_rate = models.BooleanField(default=True)
    text_value = models.CharField(max_length=3, blank=True, null=True)
    has_items = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.rate_line} - {self.column_options}"


class CostItem(models.Model):
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=64, blank=True)
    usd = models.BooleanField(default=True)
    exchange = models.PositiveIntegerField(default=1)
    tax = models.CharField(choices=TAXES, max_length=64)
    rate = models.ForeignKey(Rate, on_delete=models.CASCADE, related_name="cost_items")
    value = models.FloatField()
    fcu = models.CharField(choices=FCU_OPTIONS, max_length=64, default='Person')
    increase = models.FloatField(null=True, blank=True, default=0)

    def __str__(self):
        return f"{self.name} - {self.rate}"


class FixedRateCost(models.Model):
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=64, blank=True, null=True)
    date_from = models.DateField(verbose_name='from_date')
    date_to = models.DateField(verbose_name='to_date')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="fixed_rate_costs", null=True, blank=True)
    increase = models.FloatField(null=True, blank=True)
    usd = models.BooleanField(default=True)
    exchange = models.PositiveIntegerField(default=1)
    value = models.FloatField()
    fcu = models.CharField(choices=FCU_OPTIONS, max_length=64, default='Person')
    rate = models.ManyToManyField(Rate, related_name="rates_with_fixed", blank=True)

    def __str__(self):
        return f"{self.supplier} - {self.name}"


class CsvFileTourplan (models.Model):
    file_name = models.FileField(upload_to="csvFiles")
    uploaded_time = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Csv File ID: {self.id} - Csv Name: {self.file_name}"

class CsvFormTourplan(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
            visible.field.widget.attrs['aria-describedby'] = 'input-file'
            visible.field.widget.attrs['aria-label'] = 'SUBIR'

    class Meta:
        model = CsvFileTourplan
        fields = ('file_name',)
        labels = {
            "file_name": ""
        }

class TourplanLine(models.Model):
    order = models.IntegerField()
    supplier_code = models.CharField(max_length=64, blank=True, null=True)
    supplier_name = models.CharField(max_length=64, blank=True, null=True)
    service_code = models.CharField(max_length=2, blank=True, null=True)
    location_code = models.CharField(max_length=3, blank=True, null=True)
    option_code = models.CharField(max_length=6, blank=True, null=True)
    option_description = models.CharField(max_length=64, blank=True, null=True)
    option_comment = models.CharField(max_length=64, blank=True, null=True)
    price_code = models.CharField(max_length=2, blank=True, null=True)
    date_from = models.CharField(max_length=64, blank=True, null=True)
    date_to = models.CharField(max_length=64, blank=True, null=True)
    rate_status = models.CharField(max_length=1, blank=True, null=True)
    serv_item = models.CharField(max_length=64, blank=True, null=True)
    tax_list = models.CharField(max_length=3, blank=True, null=True)
    fit_cost = models.CharField(max_length=8, blank=True, null=True)
    fit_sell = models.CharField(max_length=8, blank=True, null=True)

    def __str__ (self):
        return f"Line: {self.order} - Supplier: {self.supplier_name} - Info: {self.option_description} - Date: {self.date_from}"


class FeedbackEntity(models.Model):
    """
    General feedback targets not mapped to a specific Supplier or User.
    E.g. 'Aliwen - Equipo general', 'Aliwen - Logística', 'Empresa en general'.
    Managed from the Calidad section.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=300, blank=True, default="")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Entidad de feedback"
        verbose_name_plural = "Entidades de feedback"
        ordering = ["name"]


class Feedback(models.Model):
    creation_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedback_user")
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="feedback_trips", null=True, blank=True)
    last_modification_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='last modification date', null=True)
    closing_date = models.DateTimeField(default=django.utils.timezone.now, verbose_name='closing date', null=True)

    # Exactly one of these should be set
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="feedback_suppliers", null=True, blank=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="feedback_targets", null=True, blank=True)
    target_guide = models.ForeignKey('intranet.Guide', on_delete=models.SET_NULL, related_name="feedback_guides", null=True, blank=True)
    target_dh = models.ForeignKey('intranet.DestinationHost', on_delete=models.SET_NULL, related_name="feedback_dhs", null=True, blank=True)
    target_driver = models.ForeignKey('intranet.Driver', on_delete=models.SET_NULL, related_name="feedback_drivers", null=True, blank=True)
    target_entity = models.ForeignKey(FeedbackEntity, on_delete=models.SET_NULL, related_name="feedback_entities", null=True, blank=True)

    type = models.CharField(max_length=64, choices=TYPE_QUALITY)
    sentiment = models.CharField(max_length=16, choices=SENTIMENT, default="neutral")
    brief_summary = models.CharField(max_length=120, blank=True, default="", verbose_name="Resumen breve")
    content = models.TextField(blank=True, default="")
    verbatim = models.TextField(blank=True, default="", verbose_name="Texto original del pasajero")
    solution = models.CharField(max_length=3000, null=True, blank=True)
    cost = models.FloatField(default=0, null=True, blank=True)
    status = models.CharField(max_length=20, choices=FEEDBACK_STATUS, default="abierto")
    source = models.CharField(max_length=10, choices=FEEDBACK_SOURCE, default="manual")
    email_sender = models.EmailField(blank=True, default="")
    responsable = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='responsible_feedbacks',
        verbose_name='Responsable del feedback',
    )
    priority = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Prioridad',
        choices=[
            ("1 - BAJA - min", "BAJA - min"),
            ("2 - BAJA - standard", "BAJA - standard"),
            ("3 - BAJA - plus", "BAJA - plus"),
            ("4 - MED - min", "MED - min"),
            ("5 - MED - standard", "MED - standard"),
            ("6 - MED - pide urgente", "MED - pide urgente"),
            ("7 - ALTA - standard", "ALTA - standard"),
            ("8 - ALTA - pide urgente", "ALTA - pide urgente"),
            ("9 - ALTA - cliente nuevo", "ALTA - cliente nuevo"),
            ("10 - ALTA - last minute", "ALTA - last minute"),
        ],
    )

    def target_display(self):
        if self.supplier:
            return self.supplier.name
        if self.target_user:
            return self.target_user.get_full_name() or self.target_user.username
        if self.target_guide:
            return f'Guía: {self.target_guide.name}'
        if self.target_dh:
            return f'DH: {self.target_dh.name}'
        if self.target_driver:
            return f'Chofer: {self.target_driver.name}'
        if self.target_entity:
            return self.target_entity.name
        return "Sin objetivo"

    def __str__(self):
        return f"{self.get_sentiment_display()} – {self.target_display()} ({self.creation_date.date()})"


class FeedbackInboxItem(models.Model):
    """Raw email from the quality inbox waiting to be processed or confirmed."""
    received_at = models.DateTimeField()
    email_subject = models.CharField(max_length=500, blank=True, default="")
    email_body = models.TextField()
    email_sender = models.EmailField()
    gmail_label = models.CharField(max_length=100, blank=True, default="")
    gmail_message_id = models.CharField(max_length=200, unique=True)
    ai_analysis = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=INBOX_STATUS, default="pendiente")
    resolved_feedback = models.ForeignKey(
        Feedback, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inbox_source"
    )

    def __str__(self):
        return f"{self.email_sender} – {self.email_subject[:60]} ({self.received_at.date()})"

    class Meta:
        ordering = ["-received_at"]


class Change(models.Model):
    date = models.DateField(default=django.utils.timezone.now, verbose_name='date status')
    type = models.CharField(max_length=64, choices=TYPE_HISTORY)
    rate_line = models.ForeignKey(RateLine, on_delete=models.CASCADE, related_name="ratelines")
    amount = models.FloatField(default=0)

    def __str__ (self):
        return f"{self.type.upper()} - Travel frame: {self.rate_line.date_from }/{self.rate_line.date_to} - Supplier: {self.rate_line.group.product.supplier.name} - Product: {self.rate_line.group.product.name}"

    class Meta:
        ordering = ["-date"]


class SustainableAction(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='sustainable_actions')
    category = models.CharField(choices=SUSTAINABLE_ACTION_CATEGORIES, max_length=20)
    description = models.TextField()

    def __str__(self):
        return f"{self.get_category_display()}: {self.description[:50]}"

    class Meta:
        ordering = ['category']

# ============================================================================
# ALQUILER DE VEHÍCULO — pegar al final de tariff/models.py
# Reutiliza: Location, STATUS, FCU_OPTIONS (ya definidos arriba en el archivo)
# ============================================================================
 
CAR_EXTRA_TYPES = [
    ("AIRPORT", "Airport"),
    ("SMART", "Smart"),
    ("COVER", "Tyres Cover"),
]
# Nota: "Map" se sacó de acá. Es un costo fijo (monto plano), no un
# porcentaje sobre la tarifa RACK -> se carga como un CarFixedCost más,
# igual que Conductor adicional, Drop off, Snow Chain, etc.
 
 
class CarHireConfig(models.Model):
    """
    Singleton: markup, tipo de cambio y porcentajes DEFAULT de Airport/
    Smart/Cover para TODO el módulo (se gestiona desde la página de
    Destinos). Cada categoría puede pisar estos defaults si su % real
    difiere (ver CarCategory.airport_pct / smart_pct / cover_pct).
    """
    markup = models.FloatField(default=0.82, verbose_name="Markup general")
    exchange = models.PositiveIntegerField(default=1400, verbose_name="Tipo de cambio (ARS x USD)")
    increase = models.FloatField(default=0, verbose_name="Aumento general %")
 
    default_airport_pct = models.FloatField(default=23, verbose_name="Airport % (default, sobre venta RACK)")
    default_smart_pct = models.FloatField(default=38, verbose_name="Smart % (default, sobre venta RACK)")
    default_cover_pct = models.FloatField(default=15, verbose_name="Cover % (default, sobre venta RACK)")
    commission = models.FloatField(default=0, verbose_name="Comisión %")
    extra_discount = models.FloatField(default=20, verbose_name="Descuento adicional %")
    extras_rounding = models.PositiveSmallIntegerField(default=5, verbose_name="Redondeo extras x pax (USD)")
    conditions_text = models.TextField(blank=True, default="", verbose_name="Condiciones generales (cotizador)")
 
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
 
    def delete(self, *args, **kwargs):
        pass  # el singleton no se borra
 
    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
 
    def __str__(self):
        return f"Config Alquiler de Vehículo (markup {self.markup})"
 
 
class CarCategory(models.Model):
    """
    Categoría / modelo de vehículo dentro de un Destino.
    Es el equivalente a 'Product' en Servicios: lo que aparece dentro
    del modal al clickear un Destino, y lleva al $ -> rate lines.
    """
    code = models.CharField(max_length=10, verbose_name="Categoría Hertz (ej: H1, K1, N1)")
    name = models.CharField(max_length=150, verbose_name="Modelo (ej: Fiat Cronos Mt 4 Ptas)")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="car_categories")
    order = models.PositiveIntegerField(default=9999)
    note = models.CharField(max_length=300, blank=True, default="")
    pic1_url = models.CharField(max_length=500, blank=True, null=True)
    isActivated = models.BooleanField(default=True)
 
    # Porcentajes propios de la categoría (sobre la venta RACK). Si quedan
    # en None, se usa el default general de CarHireConfig.
    airport_pct = models.FloatField(null=True, blank=True, verbose_name="Airport % (vacío = usar default general)")
    smart_pct = models.FloatField(null=True, blank=True, verbose_name="Smart % (vacío = usar default general)")
    cover_pct = models.FloatField(null=True, blank=True, verbose_name="Cover % (vacío = usar default general)")
    max_passengers = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Máx. pasajeros")
    max_luggage = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Máx. valijas")
    transmission = models.CharField(max_length=1, choices=[('M','Manual'),('A','Automatic')], blank=True, default='')
 
    def pct_for(self, extra_type, config):
        """Devuelve el % efectivo (propio si está cargado, si no el default general)."""
        own = {"AIRPORT": self.airport_pct, "SMART": self.smart_pct, "COVER": self.cover_pct}.get(extra_type)
        if own is not None:
            return own
        return {"AIRPORT": config.default_airport_pct, "SMART": config.default_smart_pct, "COVER": config.default_cover_pct}.get(extra_type, 0)
 
    class Meta:
        ordering = ["order"]
        verbose_name_plural = "Car categories"
 
    def __str__(self):
        return f"{self.location.code} - {self.code} - {self.name}"
 
 
class CarRateGroup(models.Model):
    """Grupo tarifario de la categoría (por defecto uno solo, 'Tarifa estándar')."""
    name = models.CharField(max_length=64, default="Tarifa estándar")
    order = models.PositiveIntegerField(default=1)
    category = models.ForeignKey(CarCategory, on_delete=models.CASCADE, related_name="rate_groups")
 
    def __str__(self):
        return f"{self.category} - {self.name}"
 
 
class CarRateLine(models.Model):
    """Bloque de vigencia (equivalente a RateLine). Un bloque = una temporada."""
    date_from = models.DateField(verbose_name="from_date")
    date_to = models.DateField(verbose_name="to_date")
    group = models.ForeignKey(CarRateGroup, on_delete=models.CASCADE, related_name="group_rate")
    season = models.CharField(max_length=64, blank=True, default="")
    is_revised = models.BooleanField(default=True)
    usd = models.BooleanField(default=False, verbose_name="Costo en USD")

    def __str__(self):
        return f"{self.group} - {self.date_from}/{self.date_to}"
 
 
class CarRate(models.Model):
    """
    Tarifa base del alquiler (costo/venta por día del vehículo, sin extras).
    Equivalente a 'Rate', pero sin columnas de pax: un solo valor por bloque.
    """
    rate_line = models.ForeignKey(CarRateLine, on_delete=models.CASCADE, related_name="line_rates")
    status = models.CharField(choices=STATUS, max_length=64, default="Confirmed")
    increase = models.FloatField(null=True, blank=True, default=0)
    cost = models.FloatField(default=0, verbose_name="Costo x día (ARS)")
    sell = models.PositiveIntegerField(default=0, verbose_name="Venta x día (USD)")
    locked = models.BooleanField(default=False)
 
    def __str__(self):
        return f"{self.rate_line} - costo {self.cost} / venta {self.sell}"
 
 
class CarExtra(models.Model):
    """
    Extras opcionales que el cliente puede o no pedir (Airport, Smart, Cover).
    El monto se calcula por defecto como % de la venta RACK (CarRate.sell)
    usando CarCategory.pct_for() / CarHireConfig, pero se puede pisar a mano
    con 'manual_override' si el % no refleja el caso real.
    """
    rate = models.ForeignKey(CarRate, on_delete=models.CASCADE, related_name="extras")
    type = models.CharField(choices=CAR_EXTRA_TYPES, max_length=20)
    cost = models.FloatField(default=0, verbose_name="Costo x día (ARS)")
    sell = models.PositiveIntegerField(default=0, verbose_name="Venta x día (USD)")
    manual_override = models.BooleanField(default=False, verbose_name="Cargado a mano (no recalcular automático)")
 
    class Meta:
        unique_together = ("rate", "type")
 
    def __str__(self):
        return f"{self.get_type_display()} - {self.rate}"
 
 
class CarFixedCost(models.Model):
    """
    Costos fijos generales: Additional Driver, Baby Seat, Return after hours,
    Snow Chain, Border Crossing, etc.
    location=None significa 'aplica a TODOS los destinos'.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=64, blank=True, null=True)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="car_fixed_costs",
        null=True, blank=True, verbose_name="Destino (vacío = todos)"
    )
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    usd = models.BooleanField(default=True)
    exchange = models.PositiveIntegerField(default=1)
    value = models.FloatField(default=0, verbose_name="Costo")
    fcu = models.CharField(choices=FCU_OPTIONS, max_length=64, default="Group")
    per_day = models.BooleanField(default=True, verbose_name="Por día (vs único por estadía)")
    recommended = models.BooleanField(default=True, verbose_name="Recomendado (pre-tildado en cotizador)")
    increase = models.FloatField(null=True, blank=True, default=0)
 
    def __str__(self):
        dest = self.location.code if self.location else "TODOS"
        return f"{self.name} ({dest})"