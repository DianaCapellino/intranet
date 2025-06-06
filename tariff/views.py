from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Location, SupplierGroup, Supplier, ProductGroup, Product, FixedRateCost, RateGroup, Rate, CostItem, RateLine, CsvFileTourplan, CsvFormTourplan, TourplanLine
import csv
import pandas as pd

def tariff(request):
    return render(request, "tariff/tariff.html", {
        "products":Product.objects.all(),
        "rates":Rate.objects.all(),
        "locations":Location.objects.all(),
        "supplier_group": SupplierGroup.objects.all(),
        "supplier": Supplier.objects.all(),
        "product_group": ProductGroup.objects.all(),
        "fixed_rates": FixedRateCost.objects.all(),
        "rate_group": RateGroup.objects.all(),
        "cost_item": CostItem.objects.all(),
        "rate_lines": RateLine.objects.all(),
    })

def tp_mod_list(request):

    if request.method == "POST":
        form = CsvFormTourplan(request.POST, request.FILES)
        if form.is_valid():

            form.save()

            csv_obj = CsvFileTourplan.objects.get(read=False)    
            upload_data(csv_obj)

            return HttpResponseRedirect(reverse("tp_mod_list"), {
                "tourplan_list": TourplanLine.objects.all(),
                "form":form,
            })
    else:
        form = CsvFormTourplan()

    return render(request, "tariff/tp_mod_list.html", {
        "tourplan_list": TourplanLine.objects.all(),
        "form":form
    })


def upload_data(csv_obj):

    TP_PRICE_CODES = {
        "NR": "Regular Rate",
        "AU": "Audley Rate"}
    
    TP_ROOM_CODES = {
        "Single": "SGL",
        "Double": "DBL",
        "Triple": "TPL",
        "4QR": "CPL",
    }

    # Create empty list
    tourplan_list = []

    TourplanLine.objects.all().delete()
    
    supplier_codes = []

    all_suppliers = Supplier.objects.all()
    for supplier in all_suppliers:
        supplier_codes.append(supplier.code)

    product_codes = []
    all_products = Product.objects.all()
    for product in all_products:
        product_codes.append(product.code)

    # Open the csv and read all the data
    with open(csv_obj.file_name.path, 'r') as f:
        reader = csv.reader(f, delimiter=';')

        for i, row in enumerate(reader):
            if i >= 7:
                new_line = TourplanLine.objects.create(
                    order=i,
                )
                new_line.save()
                col_number = 1
                for col in row:
                    if col_number == 1:
                        if col in supplier_codes:
                            new_line.supplier_code = col
                            new_line.save()
                            col_number+=1
                        else:
                            new_line.delete()
                            break
                    elif col_number == 2:
                        new_line.supplier_name = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 3:
                        new_line.service_code = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 4:
                        new_line.location_code = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 5:
                        new_line.option_code = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 6:
                        new_line.option_description = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 7:
                        new_line.option_comment = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 8:
                        new_line.price_code = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 9:
                        new_line.date_from = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 10:
                        new_line.date_to = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 11:
                        new_line.rate_status = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 12:
                        new_line.serv_item = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 13:
                        new_line.tax_list = col
                        new_line.save()
                        col_number+=1
                    elif col_number == 14:
                        if col == "-":
                            new_line.delete()
                            break
                        else:
                            new_line.fit_cost = col
                            new_line.save()
                            col_number+=1
                    elif col_number == 15:
                        new_line.fit_sell = col
                        new_line.save()
                        col_number+=1
                tourplan_list.append(new_line)
                print(new_line)

    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()
    return tourplan_list