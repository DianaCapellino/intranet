from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from tariff.models import Location, SupplierGroup, Supplier, ProductGroup, Product, FixedRateCost, RateGroup, Rate, CostItem, RateLine, CsvFileTourplan, CsvFormTourplan, TourplanLine
from tariff.utils import apply_client_margin
from intranet.models import Client
import csv
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import date
import logging
from django.db.models import Prefetch, Q


@login_required
def index(request):

    this_year = date.today().year

    return render(request, "tariff/tariff.html", {
        "locations":Location.objects.all(),
        "clients": Client.objects.all(),
        "this_year": this_year,
    })

logger = logging.getLogger(__name__)


@login_required
def tariff_search(request):

    has_params = any(request.GET.get(key) for key in ['client', 'location', 'type', 'season'])
    if not has_params:
        return render(request, "tariff/tariff_table_partial.html", {'rate_lines': None})

    loc_id = request.GET.get('location')
    t_type = request.GET.get('type')
    season = request.GET.get('season')
    client_id = request.GET.get('client')

    show_costs = request.session.get("show_costs", False)

    if t_type == "acc":
        rate_lines = (
            RateLine.objects
            .select_related(
                "group__product__supplier__group",
                "group__product__group",
                "group__product__supplier",
            )
            .prefetch_related("line_rates")
            .order_by(
                "group__product__supplier__group__order",
                "group__product__supplier__id",
                "group__product__group__order",
                "date_from",
                "date_to",
                "group__product__order",
            )
        )
    else:
        rate_lines = (
            RateLine.objects
            .select_related(
                "group__product__supplier__group",
                "group__product__group",
                "group__product__supplier",
            )
            .prefetch_related("line_rates")
            .order_by(
                "group__product__supplier__group__order",
                "group__product__supplier__id",
                "group__product__group__order",
                "group__product__order",
                "date_from",
                "date_to",
            )
        )

    if loc_id:
        rate_lines = rate_lines.filter(group__product__group__location_id=loc_id)

    if t_type == "acc":
        rate_lines = rate_lines.filter(group__product__type_service="AC")
    else:
        rate_lines = rate_lines.filter(group__product__type_service="NA")

    if season:
        year = int(season)

        season_start = date(year, 5, 1)        # 01 May
        season_end   = date(year + 1, 4, 30)   # 30 Apr siguiente año

        rate_lines = rate_lines.filter(
            date_from__lte=season_end,
            date_to__gte=season_start
        )
        
    if client_id:
        client = Client.objects.get(id=client_id)
        rate_lines = rate_lines.filter(group__product__clients__id=client_id)
    else:
        client = Client.objects.get(name=request.user.other_name)
        rate_lines = rate_lines.filter(group__product__clients__id=client.id)

    for line in rate_lines:
        rates = {}

        for r in line.line_rates.all():

            sell_adjusted = apply_client_margin(
                rate=r,
                client_category=client.category,
                service_type="AC" if t_type == "acc" else "NA"
            )

            rates[r.column_options] = sell_adjusted

        line.rates_by_column = rates

        is_internal = not hasattr(request.user, "client")
        if not is_internal:
            show_costs = False

        if show_costs and request.user.userType != "Cliente":
            line.costs_by_column = {
                r.column_options: r.cost
                for r in line.line_rates.all()
            }
        else:
            line.costs_by_column = {}

    return render(request, "tariff/tariff_table_partial.html", {
        "rate_lines": rate_lines,
        "tariff_type": t_type,
        "show_costs": show_costs,
    })

@login_required
def toggle_costs(request):
    request.session["show_costs"] = not request.session.get("show_costs", False)
    return redirect(request.META.get("HTTP_REFERER", "/"))

@login_required
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
                        if col == "-   ":
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