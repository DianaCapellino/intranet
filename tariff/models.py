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
    ("3***", "3***"),
    ("3*** Superior", "3*** Superior"),
    ("4****", "4****"),
    ("4**** Superior", "4**** Superior"),
    ("5*****", "5*****"),
    ("5***** Lux", "5***** Lux"),
    ("Estancia", "Estancia"),
    ("Boutique 4****", "Boutique 4****"),
    ("Boutique 5*****", "Boutique 5*****"),
    ("Boutique Luxury", "Boutique Luxury"),
    ("Glamping", "Glamping"),
    ("Winery Standard", "Winery Standard"),
    ("Winery Superior", "Winery Superior"),
    ("Winery Luxury", "Winery Luxury"),
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
    ("en_seguimiento", "En seguimiento"),
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

    def __str__(self):
        return f"{self.name} - {self.rate}"


class FixedRateCost(models.Model):
    name = models.CharField(max_length=64)
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

    def target_display(self):
        if self.supplier:
            return self.supplier.name
        if self.target_user:
            return self.target_user.get_full_name() or self.target_user.username
        if self.target_guide:
            return f'Guía: {self.target_guide.name}'
        if self.target_dh:
            return f'DH: {self.target_dh.name}'
        if self.target_entity:
            return self.target_entity.name
        return "Sin destinatario"

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