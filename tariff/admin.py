from django.contrib import admin
from .models import Location, SupplierGroup, Supplier, ProductGroup, Product, FixedRateCost, RateGroup, Rate, CostItem, RateLine, CsvFileTourplan, TourplanLine


admin.site.register(Location)
admin.site.register(SupplierGroup)
admin.site.register(Supplier)
admin.site.register(ProductGroup)
admin.site.register(Product)
admin.site.register(FixedRateCost)
admin.site.register(RateGroup)
admin.site.register(Rate)
admin.site.register(RateLine)
admin.site.register(CostItem)
admin.site.register(CsvFileTourplan)
admin.site.register(TourplanLine)