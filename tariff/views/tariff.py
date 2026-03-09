from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, FileResponse
from django.urls import reverse
from tariff.models import Location, SupplierGroup, Supplier, ProductGroup, Product, FixedRateCost, RateGroup, Rate, CostItem, RateLine, CsvFileTourplan, CsvFormTourplan, TourplanLine, Change, TYPE_HISTORY
from tariff.utils import apply_client_margin
from intranet.utils import report_tariff_error_hotel, send_templated_email, report_tariff_error_service
from intranet.models import Client, Holidays
import csv
from django.contrib.auth.decorators import login_required
from datetime import date, datetime
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
import json
from collections import defaultdict
from django.contrib import messages
import math

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
            changes, stats = upload_data(csv_obj)

            if stats["rows_read"] == 0:
                messages.warning(
                    request,
                    "No se leyó ninguna tarifa del archivo. "
                    "Verificá que el formato del CSV sea correcto y que los códigos de proveedor y producto existan en el sistema."
                )
            else:
                parts = [f"Se procesaron <strong>{stats['rows_read']}</strong> tarifas."]
                if stats["up_to_date"]:
                    parts.append(f"<strong>{stats['up_to_date']}</strong> ya coinciden ✓")
                if stats["to_update"]:
                    parts.append(f"<strong>{stats['to_update']}</strong> para actualizar")
                if stats["to_add"]:
                    parts.append(f"<strong>{stats['to_add']}</strong> para agregar")
                if stats["to_delete"]:
                    parts.append(f"<strong>{stats['to_delete']}</strong> líneas sin coincidencia")

                if changes:
                    request.session["pending_changes"] = changes
                    messages.info(request, " · ".join(parts))
                else:
                    messages.success(request, " · ".join(parts) + " — Todo está al día.")

            return HttpResponseRedirect(reverse("tp_mod_list"))

    else:
        form = CsvFormTourplan()

    pending_changes = request.session.get("pending_changes", None)

    return render(request, "tariff/tp_mod_list.html", {
        "form": form,
        "pending_changes_json": json.dumps(pending_changes) if pending_changes else None,
        "has_pending": bool(pending_changes),
    })


def apply_changes(request):
    """
    Receives { confirmed: [...], ignored_ids: [...] }
    Applies confirmed items and removes both confirmed + ignored from session.
    """
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            confirmed    = body.get("confirmed", [])
            ignored_ids  = set(body.get("ignored_ids", []))

            if confirmed:
                apply_confirmed_changes(confirmed)
                n = len(confirmed)
                messages.success(request, f"Se guardaron <strong>{n}</strong> cambio{'s' if n != 1 else ''} correctamente.")

            # Remove processed items (confirmed + ignored) from session
            confirmed_ids = {item["_id"] for item in confirmed}
            removed_ids   = confirmed_ids | ignored_ids

            pending = request.session.get("pending_changes", [])
            remaining = [item for item in pending if item.get("_id") not in removed_ids]

            if remaining:
                request.session["pending_changes"] = remaining
                request.session.modified = True
            else:
                request.session.pop("pending_changes", None)

        except (json.JSONDecodeError, KeyError) as e:
            messages.error(request, f"Error al aplicar los cambios: {e}")

    return HttpResponseRedirect(reverse("tp_mod_list"))


def discard_changes(request):
    """Descarta todos los cambios pendientes."""
    request.session.pop("pending_changes", None)
    messages.warning(request, "Se descartaron todos los cambios pendientes.")
    return HttpResponseRedirect(reverse("tp_mod_list"))


def upload_data(csv_obj):
    today = date.today()
    result = []
    stats = {
        "rows_read":    0,
        "rows_skipped": 0,
        "up_to_date":   0,
        "to_update":    0,
        "to_add":       0,
        "to_delete":    0,
    }

    supplier_codes = set(Supplier.objects.values_list("code", flat=True))
    product_map = {
        (p.supplier.code, p.code): p
        for p in Product.objects.select_related("supplier").all()
    }

    # Track which (product_id, date_from, date_to) combos appeared in the CSV
    # so we can find RateLines in the DB that have no CSV counterpart
    csv_product_dates = set()   # set of (product_id, date_from_db, date_to_db)
    csv_products_seen = set()   # set of product_id — to scope the Delete search

    ctx_supplier     = None
    ctx_supplier_obj = None
    ctx_product      = None
    ctx_price_code   = None
    ctx_date_from    = None
    ctx_date_to      = None
    ctx_date_from_db = None
    ctx_date_to_db   = None

    with open(csv_obj.file_name.path, "r") as f:
        reader = csv.reader(f, delimiter=";")

        for i, row in enumerate(reader):
            if i < 7:
                continue

            cols = row + [""] * max(0, 17 - len(row))

            c1  = cols[0].strip()
            c4  = cols[3].strip()
            c7  = cols[6].strip()
            c8  = cols[7].strip()
            c9  = cols[8].strip()
            c11 = cols[10].strip()
            c13 = cols[12].strip()
            c16 = cols[15].strip()
            c17 = cols[16].strip()

            # ---- inherit: supplier
            if c1:
                if c1 not in supplier_codes:
                    ctx_supplier = ctx_supplier_obj = None
                    ctx_product = ctx_price_code = None
                    ctx_date_from = ctx_date_to = None
                    continue
                ctx_supplier = c1
                ctx_supplier_obj = Supplier.objects.get(code=c1)

            # ---- inherit: product
            if c4:
                key = (ctx_supplier, c4)
                ctx_product = product_map.get(key)

            # ---- inherit: price_code
            if c7:
                ctx_price_code = c7

            # ---- inherit: dates
            if c8:
                try:
                    date_obj = datetime.strptime(c8, "%d/%m/%Y")
                    ctx_date_from    = c8
                    ctx_date_from_db = date_obj.date()
                except ValueError:
                    ctx_date_from = ctx_date_from_db = None

            if c9:
                try:
                    ctx_date_to    = c9
                    ctx_date_to_db = datetime.strptime(c9, "%d/%m/%Y").date()
                except ValueError:
                    ctx_date_to = ctx_date_to_db = None

            # ---- per-row: room type
            if c11 == "Single":
                column_options = "SGL"
            elif c11 in ("Double", "Twin"):
                column_options = "DBL"
            else:
                continue

            # ---- per-row: fcu
            if c13 == "Room":
                fcu = "Group"
            elif c13 == "Person":
                fcu = "Person"
            else:
                continue

            # ---- price_code → RateGroup name filter
            # Maps CSV price_code to the RateGroup names to search within.
            # CX/TD: treat as zero-cost comparison (no real cost from CSV needed).
            PRICE_CODE_MAP = {
                "AU": ["Audley Exclusive Rates"],
                "NR": ["Net rates - per night", "Rates per night for 1 night"],
                "DM": ["Net rates - per night", "Rates per night for 1 night"],
                "CX": None,   # zero-cost sentinel
                "TD": None,   # zero-cost sentinel
            }
            if ctx_price_code not in PRICE_CODE_MAP:
                continue   # unknown price_code — ignore row

            is_zero_cost = PRICE_CODE_MAP[ctx_price_code] is None
            target_group_names = PRICE_CODE_MAP[ctx_price_code]  # list or None

            # ---- per-row: cost
            if is_zero_cost:
                cost = 0.0
            else:
                raw_cost = c16.replace("\xa0", "").replace(" ", "")
                if not raw_cost or set(raw_cost) <= {"-"}:
                    continue
                try:
                    cost = round(float(raw_cost.replace(",", ".")), 2)
                except ValueError:
                    continue

            # ---- validate context
            if not ctx_product or not ctx_supplier_obj:
                continue
            if not ctx_date_from_db or not ctx_date_to_db:
                continue
            if ctx_date_from_db <= today:
                continue

            # ---- calculate sell_tourplan
            if is_zero_cost:
                sell_tourplan = 0
            else:
                margin = ctx_supplier_obj.margin
                if not margin or margin == 0:
                    continue
                sell_tourplan = math.ceil(cost / margin)

            margin = ctx_supplier_obj.margin

            # ---- track product+date combo for Delete detection
            csv_products_seen.add(ctx_product.pk)
            csv_product_dates.add((ctx_product.pk, ctx_date_from_db, ctx_date_to_db))

            stats["rows_read"] += 1

            # ---- find matching RateGroup(s) for this price_code
            rg_qs = RateGroup.objects.filter(product=ctx_product)
            if target_group_names:
                rg_qs = rg_qs.filter(name__in=target_group_names)
            target_rate_groups = list(rg_qs.order_by("order"))

            if not target_rate_groups:
                # No matching RateGroup exists yet — nothing to compare against, skip
                continue

            row_index = stats["rows_read"] - 1
            base_item = {
                "_id":            row_index,
                "product_code":   ctx_product.code,
                "product_name":   str(ctx_product),
                "price_code":     ctx_price_code,
                "date_from":      ctx_date_from,
                "date_to":        ctx_date_to,
                "column_options": column_options,
                "fcu":            fcu,
                "cost":           cost,
                "sell_tourplan":  sell_tourplan,
                "sell":           sell_tourplan,
                "margin":         margin,
            }

            # ---- classify Update / Add — check each target RateGroup
            for rate_group in target_rate_groups:
                matching_rate_line = (
                    RateLine.objects.filter(
                        group=rate_group,
                        date_from=ctx_date_from_db,
                        date_to=ctx_date_to_db,
                    )
                    .select_related("group")
                    .first()
                )

                item_base = {**base_item, "_id": row_index, "rate_group_name": rate_group.name}

                if matching_rate_line:
                    existing_rate = Rate.objects.filter(
                        rate_line=matching_rate_line,
                        column_options=column_options,
                    ).first()

                    if existing_rate:
                        if existing_rate.sell_tourplan != sell_tourplan:
                            stats["to_update"] += 1
                            result.append({
                                **item_base,
                                "action":                "Update",
                                "current_sell_tourplan": existing_rate.sell_tourplan,
                                "current_sell":          existing_rate.sell,
                                "current_cost":          existing_rate.cost,
                                "rate_id":               existing_rate.pk,
                                "rate_group_id":         None,
                            })
                        else:
                            stats["up_to_date"] += 1
                    else:
                        stats["to_add"] += 1
                        result.append({
                            **item_base,
                            "action":                "Add",
                            "current_sell_tourplan": None,
                            "current_sell":          None,
                            "current_cost":          None,
                            "rate_id":               None,
                            "rate_group_id":         matching_rate_line.group.pk,
                        })
                else:
                    stats["to_add"] += 1
                    result.append({
                        **item_base,
                        "action":                "Add",
                        "current_sell_tourplan": None,
                        "current_sell":          None,
                        "current_cost":          None,
                        "rate_id":               None,
                        "rate_group_id":         rate_group.pk,
                    })
                row_index += 1  # each rate_group gets its own _id

    # ------------------------------------------------------------------ Delete detection
    # Find RateLines that belong to products seen in the CSV, are still current/future,
    # but whose (product, date_from, date_to) combo never appeared in the CSV.
    if csv_products_seen:
        orphan_lines = (
            RateLine.objects.filter(
                group__product__in=csv_products_seen,
                date_from__gt=today,
            )
            .select_related("group__product__supplier")
            .prefetch_related("line_rates")  # prefetch related Rates
        )

        next_id = stats["rows_read"]  # continue _id sequence
        for rl in orphan_lines:
            product = rl.group.product
            combo   = (product.pk, rl.date_from, rl.date_to)
            if combo in csv_product_dates:
                continue  # this line was in the CSV — not orphan

            # Collect existing rates for display
            rates = list(rl.line_rates.all())
            rates_summary = [
                {"column_options": r.column_options, "sell_tourplan": r.sell_tourplan, "sell": r.sell, "cost": r.cost}
                for r in rates
            ]

            stats["to_delete"] += 1
            result.append({
                "_id":            next_id,
                "action":         "Delete",
                "product_code":   product.code,
                "product_name":   str(product),
                "date_from":      rl.date_from.strftime("%d/%m/%Y"),
                "date_to":        rl.date_to.strftime("%d/%m/%Y"),
                "season":         rl.season,
                "rate_line_id":   rl.pk,
                "rates_summary":  rates_summary,
                # unused by Delete but kept for uniform shape
                "price_code": None, "column_options": None, "fcu": None,
                "cost": None, "sell_tourplan": None, "sell": None, "margin": None,
                "current_sell_tourplan": None, "current_sell": None, "current_cost": None,
                "rate_id": None, "rate_group_id": None,
            })
            next_id += 1

    csv_obj.read = True
    csv_obj.save()
    csv_obj.delete()

    return result, stats


def apply_confirmed_changes(confirmed_items):
    for item in confirmed_items:
        action        = item.get("action")
        cost          = item.get("cost", 0)
        sell_tourplan = item.get("sell_tourplan")
        sell          = item.get("sell", sell_tourplan)

        if action == "Update":
            Rate.objects.filter(pk=item["rate_id"]).update(
                cost=cost,
                sell_tourplan=sell_tourplan,
                sell=sell,
            )

        elif action == "Add":
            rate_group_id = item.get("rate_group_id")
            if not rate_group_id:
                continue

            date_from = datetime.strptime(item["date_from"], "%d/%m/%Y").date()
            date_to   = datetime.strptime(item["date_to"],   "%d/%m/%Y").date()

            rate_line, _ = RateLine.objects.get_or_create(
                group_id=rate_group_id,
                date_from=date_from,
                date_to=date_to,
                defaults={"season": "To be defined"},
            )

            Rate.objects.get_or_create(
                rate_line=rate_line,
                column_options=item["column_options"],
                defaults={
                    "cost":          cost,
                    "sell_tourplan": sell_tourplan,
                    "sell":          sell,
                    "status":        "Active",
                    "margin":        "0",
                    "has_rate":      True,
                },
            )

        elif action == "Delete":
            rate_line_id = item.get("rate_line_id")
            if rate_line_id:
                RateLine.objects.filter(pk=rate_line_id).delete()


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