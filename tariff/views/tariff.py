from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, FileResponse
from django.urls import reverse
from tariff.models import Location, SupplierGroup, Supplier, ProductGroup, Product, FixedRateCost, RateGroup, Rate, CostItem, RateLine, CsvFileTourplan, CsvFormTourplan, TourplanLine, Change, TYPE_HISTORY
from tariff.utils import apply_client_margin
from intranet.utils import report_tariff_error_hotel, send_templated_email, report_tariff_error_service
from intranet.models import Client, Holidays
import csv
from django.contrib.auth.decorators import login_required
from datetime import date
import logging
from django.conf import settings
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator


@login_required
def index(request):

    this_year = date.today().year

    return render(request, "tariff/tariff.html", {
        "locations":Location.objects.all(),
        "clients": Client.objects.all(),
        "this_year": this_year,
    })

logger = logging.getLogger(__name__)


def get_filtered_rate_lines(request):


    loc_id = request.GET.get('location')
    t_type = request.GET.get('type')
    season = request.GET.get('season')
    client_id = request.GET.get('client')

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
                "group__product__supplier__order",
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

    return rate_lines, t_type


@login_required
def tariff_search(request):

    has_params = any(request.GET.get(key) for key in ['client', 'location', 'type', 'season'])
    if not has_params:
        return render(request, "tariff/tariff_table_partial.html", {'rate_lines': None})

    rate_lines, t_type = get_filtered_rate_lines(request)

    return render(request, "tariff/tariff_table_partial.html", {
        "rate_lines": rate_lines,
        "tariff_type": t_type,
    })


def export_services_excel(request):

    has_params = any(request.GET.get(key) for key in ['client', 'location', 'type', 'season'])
    if not has_params:
        return HttpResponse("No data to export")

    rate_lines, t_type = get_filtered_rate_lines(request)
    # 👆 MISMA lógica que tu vista principal

    header_fill = PatternFill(start_color="D88775", end_color="D88775", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    for line in rate_lines:
        print(line.rates_by_column)
        break

    if t_type == "acc":
        type_label = "Accommodation"
    else:
        type_label = "Services"

    loc_id = request.GET.get("location")
    season = request.GET.get("season")

    location_label = ""
    if loc_id:
        location = Location.objects.filter(id=loc_id).first()
        if location:
            location_label = location.name

    season_label = ""
    if season:
        year = int(season)
        season_label = f"{year}/{year+1}"

    wb = Workbook()
    ws = wb.active
    ws.title = "Aliwen Tariff"

    filename = f"Aliwen Tariff - {type_label}"

    if location_label:
        filename += f" - {location_label}"

    if season_label:
        filename += f" - {season_label}"

    filename += ".xlsx"

    ws.freeze_panes = "A2"

    if t_type == "svs":
        ws.append([
            "Product",
            "Type",
            "Group",
            "From",
            "To",
            "1 Pax",
            "2 Pax",
            "3 Pax",
            "4 Pax",
            "5 Pax",
            "6 Pax",
        ])
        for line in rate_lines:
            ws.append([
                line.group.product.name,
                line.group.name,
                line.group.product.group.name,
                line.date_from,
                line.date_to,
                line.rates_by_column.get('1'),
                line.rates_by_column.get('2'),
                line.rates_by_column.get('3'),
                line.rates_by_column.get('4'),
                line.rates_by_column.get('5'),
                line.rates_by_column.get('6'),
            ])
    else:
        ws.append([
            "Supplier",
            "Room",
            "Type",
            "Condition",
            "From",
            "To",
            "SGL",
            "DBL",
        ])
        for line in rate_lines:
            ws.append([
                getattr(line.group.product.supplier, "name", ""),
                line.group.product.name,
                line.group.name,
                line.group.product.group.name,
                line.date_from,
                line.date_to,
                line.rates_by_column.get('SGL'),
                line.rates_by_column.get('DBL'),
            ])

    # Format of the header
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Correct the width of the columns
    for column_cells in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column_cells[0].column)

        for cell in column_cells:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        ws.column_dimensions[column_letter].width = max_length + 2

    # Aligment of the cells
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, (int, float)):
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")

    # Borders and more formats
    thin = Side(border_style="thin", color="DDDDDD")
    border = Border(top=thin, left=thin, right=thin, bottom=thin)

    for row in ws.iter_rows():
        for cell in row:
            cell.border = border

    alt_fill = PatternFill(start_color="F7F9FC", end_color="F7F9FC", fill_type="solid")

    for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if idx % 2 == 0:
            for cell in row:
                cell.fill = alt_fill

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response


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

@login_required
def special_dates(request):
    return render(
        request,
        "tariff/special_holidays.html",
        {
            "pdf_url": "documents/Argentina_National_Holidays_2026.pdf",
        }
    )

@login_required
def download_holidays_pdf(request, year):
    if year == 2026:
        file_path = os.path.join(
            settings.BASE_DIR,
            "static/documents/Argentina_National_Holidays_2026.pdf"
        )
        return FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename="Argentina_National_Holidays_2026.pdf"
        )
    elif year == 2027:
        file_path = os.path.join(
            settings.BASE_DIR,
            "static/documents/Argentina_National_Holidays_2027.pdf"
        )
        return FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename="Argentina_National_Holidays_2027.pdf"
        )
    else:
        # Implement later this exception
        pass

@login_required
def history_of_changes(request):

    return render(
        request,
        "tariff/history_of_changes.html",
        {
            "types": TYPE_HISTORY,
            "is_admin": request.user.isAdmin,
        }
    )

@login_required
def report_error_hotel(request, supplier_id):

    supplier_obj = Supplier.objects.get(pk=supplier_id)
    
    if request.method == "POST":

        note = request.POST["note"]

        subject, email, template, context = report_tariff_error_hotel(request.user, supplier_obj, note)

        send_templated_email(subject, email, template, context)

        this_year = date.today().year

        return render(request, "tariff/tariff.html", {
            "locations":Location.objects.all(),
            "clients": Client.objects.all(),
            "this_year": this_year,
        })

    return render(request, "tariff/report_error.html", {
        "supplier": supplier_obj,
        "type": "acc",
    })

@login_required
def report_error_service(request, product_id):

    product_obj = Product.objects.get(pk=product_id)
    
    if request.method == "POST":

        note = request.POST["note"]

        subject, email, template, context = report_tariff_error_service(request.user, product_obj, note)

        send_templated_email(subject, email, template, context)

        this_year = date.today().year

        return render(request, "tariff/tariff.html", {
            "locations":Location.objects.all(),
            "clients": Client.objects.all(),
            "this_year": this_year,
        })

    return render(request, "tariff/report_error.html", {
        "product": product_obj,
        "type": "svs",
    })

@login_required
def history_of_changes_data(request):
    today = date.today()
    last_year = date(today.year - 1, today.month, today.day)

    changes = (
        Change.objects
        .select_related(
            "rate_line",
            "rate_line__group",
            "rate_line__group__product",
            "rate_line__group__product__supplier",
            "rate_line__group__product__supplier__group",
            "rate_line__group__product__supplier__group__location",
        )
        .filter(date__range=(last_year, today))
    )

    data = []
    for change in changes:
        product = change.rate_line.group.product
        if product.type_service == "AC":
            supplier_display = str(product.supplier)
        else:
            supplier_display = f"{product.supplier.group.location} - Services"

        row = {
            "id": change.id,
            "date": str(change.date),
            "supplier": supplier_display,
            "product": f"{product.name}, {change.rate_line.group.name}",
            "validity": f"{change.rate_line.date_from}/{change.rate_line.date_to}",
            "type": change.type,
            "amount": f"{change.amount} %",
        }
        data.append(row)

    return JsonResponse({"data": data})