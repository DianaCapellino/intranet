from django.db import models
from intranet.models import Client
from intranet.models import User
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
    ("Boutique 5***** Lux", "Boutique 5***** Lux"),
    ("Glamping", "Glamping"),
    ("Winery", "Winery")
]

SERVICES_OPTIONS = [
    ("Shared", "Shared"),
    ("Shared boutique", "Shared shared"),
    ("Private with driver only", "Private with driver only"),
    ("Private with English-speaking guide", "Private with English-speaking guide"),
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

    def __str__(self):
        return f"{self.name}"
    

class SupplierGroup(models.Model):
    name = models.CharField(max_length=64)
    order = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name}"

class Supplier(models.Model):
    code = models.CharField(max_length=6)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=500, blank=True)
    pic1_url = models.CharField(max_length=500, blank=True, null=True)
    pic2_url = models.CharField(max_length=500, blank=True, null=True)
    pic3_url = models.CharField(max_length=500, blank=True, null=True)
    children_ranking = models.PositiveSmallIntegerField(choices=CHILDREN_RANKING_OPTIONS)
    disabled_ranking = models.PositiveSmallIntegerField(choices=DISABLED_RANKING_OPTIONS)
    sustentability_ranking = models.PositiveSmallIntegerField(choices=SUSTENTABILITY_RANKING_OPTIONS)
    attractions = MultiSelectField(choices=ATTRACTIONS, max_length=64, blank=True, null=True)
    interests = MultiSelectField(choices=INTERESTS, max_length=64, blank=True, null=True)
    note = models.CharField(max_length=500, blank=True, default=None)
    recommended = models.BooleanField(default=False)
    order = models.PositiveIntegerField()
    group = models.ForeignKey(SupplierGroup, on_delete=models.CASCADE, related_name="group_products")
    margin = models.FloatField()

    def __str__(self):
        return f"{self.name}"
    

class ProductGroup(models.Model):
    name = models.CharField(max_length=64)
    order = models.PositiveIntegerField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="location_products")

    def __str__(self):
        return f"{self.location} - {self.name}"


class Product(models.Model):
    code = models.CharField(max_length=6)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=500, blank=True)
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
    
    # Supplier to organize for clients
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="supplier_products")
    
    # Supplier for the real costs show internally
    real_supplier = models.CharField(max_length=64)
    
    # Visible for clients
    shown = models.BooleanField(default=True)

    fcu = models.CharField(choices=FCU_OPTIONS, max_length=64)
    scu = models.PositiveSmallIntegerField()
    lw_date = models.DateField(default=django.utils.timezone.now, verbose_name='last_working_date')

    quality = models.CharField(max_length=64)
    order = models.PositiveIntegerField()
    group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, related_name="group_products")
    clients = models.ManyToManyField(Client, related_name="available_clients", blank=True)

    def __str__(self):
        return f"{self.supplier} - {self.name}"
    
    class Meta:
        ordering = ["-order"]


class FixedRateCost(models.Model):
    name = models.CharField(max_length=64)
    date_from = models.DateField(verbose_name='from_date')
    date_to = models.DateField(verbose_name='to_date')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="fixed_rate_location")
    increase = models.FloatField(null=True, blank=True)
    usd = models.BooleanField(default=True)
    exchange = models.PositiveIntegerField(default=1)
    value = models.FloatField()

    def __str__(self):
        return f"{self.location} - {self.name}"


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

    def __str__(self):
        return f"{self.group} - {self.date_from}/{self.date_to}"

class Rate(models.Model):
    rate_line = models.ForeignKey(RateLine, on_delete=models.CASCADE, related_name="line_rates")
    status = models.CharField(choices=STATUS, max_length=64)
    increase = models.FloatField(null=True, blank=True)
    cost = models.FloatField()
    margin = models.CharField(choices=MARGIN_OPTIONS, max_length=64)
    increase = models.FloatField(null=True, blank=True)
    sell = models.PositiveIntegerField()
    sell_tourplan = models.PositiveIntegerField()
    column_options = models.CharField(max_length=64)
    has_rate = models.BooleanField(default=True)
    text_value = models.CharField(max_length=3, blank=True, null=True)

    def __str__(self):
        return f"{self.rate_line} - {self.column_options}"


class CostItem(models.Model):
    name = models.CharField(max_length=64)
    usd = models.BooleanField(default=True)
    exchange = models.PositiveIntegerField(default=1)
    tax = models.CharField(choices=TAXES, max_length=64)
    rate = models.ForeignKey(Rate, on_delete=models.CASCADE, related_name="cost_items")
    value = models.FloatField()

    def __str__(self):
        return f"{self.name} - {self.rate}"
    
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