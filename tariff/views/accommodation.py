from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from tariff.models import Supplier, SupplierGroup, Product, ProductGroup, Location, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, HOTEL_QUALITY_OPTIONS, SUSTAINABLE_ACTION_CATEGORIES
from intranet.models import Client
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from datetime import date
from tariff.utils import save_pic_upload

MARGIN_ACC_OPTIONS = [
    ("Low", "0.89"),
    ("Regular", "0.85"),
    ("High", "0.82"),
]

MARGIN_VALUE_TO_INFO = {v: label for label, v in MARGIN_ACC_OPTIONS}

@login_required
def supplier(request):

    supplier_groups = SupplierGroup.objects.filter(type_service="AC")

    suppliers = Supplier.objects.filter(
        group__type_service="AC"
    ).prefetch_related("supplier_products", "sustainable_actions")

    from tariff.utils import get_suppliers_last_update
    supplier_last_update = get_suppliers_last_update(suppliers.values_list('id', flat=True))

    if request.method == "POST":

        # Get the information from the form
        code = request.POST["code"].upper()
        name = request.POST["name"]
        category = request.POST["category"]
        group_form = request.POST["group"]
        margin = request.POST["margin"]

        # Validations
        if not name or not code or not category or not group_form or not margin:
            return render(request, "tariff/accommodation/supplier.html", {
                "suppliers": suppliers,
                "locations": Location.objects.all(),
                "products": Product.objects.filter(type_service="AC"),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
                "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
                "SUSTAINABLE_ACTION_CATEGORIES": SUSTAINABLE_ACTION_CATEGORIES,
            })

        group = SupplierGroup.objects.get(pk=group_form)
        
        existing_suppliers = Supplier.objects.filter(
            group=group
        ).order_by("order")

        last_group = existing_suppliers.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the supplier from the form information
        new_supplier = Supplier.objects.create(
            name=name,
            code=code,
            description=request.POST["description"],
            hotel_quality=category,
            group=group,
            order=order,
            children_ranking=request.POST["children_ranking"],
            disabled_ranking=request.POST["disabled_ranking"],
            sustentability_ranking=request.POST["sustentability_ranking"],
            attractions=request.POST.getlist("attractions"),
            interests=request.POST.getlist("interests"),
            margin=margin,
            margin_info=MARGIN_VALUE_TO_INFO.get(margin, "Regular"),
            note=request.POST.get("note"),
            child_note=request.POST.get("child_note"),
            stay_note=request.POST.get("stay_note"),
            closing_note=request.POST.get("closing_note"),
            prepayment=request.POST.get("prepayment"),
            recommended=request.POST.get("recommended") == "on",
            highlight=request.POST.get("highlight", ""),
            highlight_sustentability=request.POST.get("highlight_sustentability", ""),
            room_quantity=request.POST.get("room_quantity", ""),
            inclusions=request.POST.get("inclusions", ""),
            bedding=request.POST.get("bedding", ""),
            note_aliwen=request.POST.get("note_aliwen", ""),
            note_audley=request.POST.get("note_audley", ""),
            pic1_url=save_pic_upload(request.FILES.get("pic1"), "suppliers") if request.FILES.get("pic1") else None,
            pic2_url=save_pic_upload(request.FILES.get("pic2"), "suppliers") if request.FILES.get("pic2") else None,
            pic3_url=save_pic_upload(request.FILES.get("pic3"), "suppliers") if request.FILES.get("pic3") else None,
        )
        # Auto-resolve any provisional suppliers with a similar name
        from tariff.models import Feedback
        for prov in Supplier.objects.filter(is_provisional=True):
            if name.lower() in prov.name.lower() or prov.name.lower() in name.lower():
                Feedback.objects.filter(supplier=prov).update(supplier=new_supplier)
                prov.delete()

        return HttpResponseRedirect(reverse("acc_supplier"), {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="AC"),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
            "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
        })

    else:

        return render(request, "tariff/accommodation/supplier.html", {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="AC"),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
            "supplier_groups": supplier_groups.order_by("location__name", "name"),
            "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
            "SUSTAINABLE_ACTION_CATEGORIES": SUSTAINABLE_ACTION_CATEGORIES,
            "supplier_last_update": supplier_last_update,
        })


@login_required
def export_notes_excel(request):
    """Downloadable spreadsheet of every accommodation supplier that has at
    least one client-facing note loaded (nota general, prepago, niños, estadía
    mínima, cierre) — one row per hotel, one column per note type, so the note
    text itself (not just a Sí/No flag) can be reviewed/trimmed in Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from django.db.models import Q

    suppliers = (
        Supplier.objects
        .filter(group__type_service="AC")
        .filter(
            Q(note__gt="") | Q(prepayment__gt="") | Q(child_note__gt="") |
            Q(stay_note__gt="") | Q(closing_note__gt="")
        )
        .select_related("group__location")
        .order_by("group__location__name", "order", "name")
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Notas alojamiento"

    header_fill = PatternFill("solid", fgColor="212529")
    bold_white = Font(bold=True, color="FFFFFF", size=10)
    normal_font = Font(size=9)
    wrap_align = Alignment(wrap_text=True, vertical="top")
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ["Destino", "Nombre", "Código", "Categoría", "Grupo", "Nota", "Prepago", "Nota Niños", "Nota Estadía Mínima", "Nota Cierre"]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = bold_white
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = 26

    for supplier in suppliers:
        row_data = [
            supplier.group.location.name,
            supplier.name,
            supplier.code,
            supplier.hotel_quality,
            supplier.group.name,
            supplier.note,
            supplier.prepayment,
            supplier.child_note,
            supplier.stay_note,
            supplier.closing_note,
        ]
        ws.append(row_data)
        data_row = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=data_row, column=col_idx)
            cell.font = normal_font
            cell.border = border
            cell.alignment = wrap_align
        max_lines = max((len(str(v or "")) // 40 + str(v or "").count("\n") + 1) for v in row_data)
        ws.row_dimensions[data_row].height = max(15, min(max_lines * 14, 100))

    widths = [16, 26, 10, 16, 18, 30, 30, 26, 26, 26]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="Notas_Alojamiento.xlsx"'
    wb.save(response)
    return response


@login_required
def supplier_group(request):
    # "locations" (todos) alimenta el selector de destino del modal de EDICIÓN de cada grupo
    # existente — tiene que poder seguir mostrando el destino actual aunque después se haya
    # desactivado. "active_locations" es solo para el desplegable de ALTA de un grupo nuevo,
    # donde si tiene sentido ofrecer solo destinos activos en el tarifario.
    active_locations = Location.objects.filter(isActivated=True)

    if request.method == "POST":

        # Attempt to create group supplier
        name = request.POST["name"]
        location_form = request.POST["location"]

        # Validations
        if not name or not location_form:
            return render(request, "tariff/accommodation/supplier_group.html", {
                "message": "Todos los campos deben ser completados",
                "groups": SupplierGroup.objects.filter(type_service="AC"),
                "locations": Location.objects.all(),
                "active_locations": active_locations,
            })

        location = Location.objects.get(id=location_form)

        existing_groups = SupplierGroup.objects.filter(
            type_service="AC",
            location=location
        ).order_by("order")

        last_group = existing_groups.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the group from the form information
        new_group = SupplierGroup.objects.create(
            name=name,
            location=location,
            order=order,
            type_service="AC",
        )
        new_group.save()

        return render(request, "tariff/accommodation/supplier_group.html", {
            "groups": SupplierGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
            "active_locations": active_locations,
        })

    else:
        return render(request, "tariff/accommodation/supplier_group.html", {
            "groups": SupplierGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
            "active_locations": active_locations,
        })

@login_required
def product(request, supplier_id):

    supplier = Supplier.objects.get(pk=supplier_id)

    supplier_groups = SupplierGroup.objects.filter(type_service="AC")
    product_groups = ProductGroup.objects.filter(location=supplier.group.location)
    product_groups = product_groups.filter(type_service="AC")

    default_location = Location.objects.get(code="BUE")

    suppliers = Supplier.objects.filter(
        group__type_service="AC"
    ).prefetch_related("supplier_products")

    if request.method == "POST":

        today = date.today()
        
        # Get the information from the form
        code = request.POST["code"].upper()
        name = request.POST["name"]
        group_form = request.POST["group"]

        # Validations
        if not name or not code or not group_form:
            return render(request, "tariff/accommodation/product.html", {
                "suppliers": suppliers,
                "locations": Location.objects.all(),
                "products": Product.objects.filter(type_service="AC"),
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
                "product_groups": product_groups,
                "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
                "clients": Client.objects.all(),
                "default_location": default_location,
                "supplier": supplier,
            })

        group = ProductGroup.objects.get(pk=group_form)
        
        existing_products = Product.objects.filter(
            group=group
        ).order_by("order")

        last_group = existing_products.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the supplier from the form information
        new_product = Product.objects.create(
            name=name,
            code=code,
            description=request.POST["description"],
            supplier=supplier,
            children_ranking=supplier.children_ranking,
            disabled_ranking=supplier.disabled_ranking,
            sustentability_ranking=supplier.sustentability_ranking,
            note=request.POST.get("note"),
            type_service="AC",
            recommended=request.POST.get("recommended") == "on",
            shown=True,
            fcu="Group",
            scu=1,
            lw_date=today,
            order=order,
            group=group,
            pic1_url=save_pic_upload(request.FILES.get("pic1"), "products") if request.FILES.get("pic1") else None,
            pic2_url=save_pic_upload(request.FILES.get("pic2"), "products") if request.FILES.get("pic2") else None,
            pic3_url=save_pic_upload(request.FILES.get("pic3"), "products") if request.FILES.get("pic3") else None,
        )

        new_product.save()

        clients = request.POST.getlist("clients")
        new_product.clients.set(clients)

        new_product.save()

        return HttpResponseRedirect(reverse("acc_supplier"), {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="AC"),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
            "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
            "default_location": default_location,      
        })

    else:

        return render(request, "tariff/accommodation/product.html", {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="AC"),
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
            "product_groups": product_groups,
            "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
            "clients": Client.objects.all(),
            "default_location": default_location,
            "supplier": supplier,
        })

@login_required
def product_group(request):
    # Ver comentario análogo en supplier_group: "locations" (todos) es para el modal de
    # edición de cada grupo existente, "active_locations" solo para el alta de uno nuevo.
    active_locations = Location.objects.filter(isActivated=True)

    if request.method == "POST":

        # Attempt to create group supplier
        name = request.POST["name"]
        location_form = request.POST["location"]

        # Validations
        if not name or not location_form:
            return render(request, "tariff/accommodation/product_group.html", {
                "message": "Todos los campos deben ser completados",
                "groups": ProductGroup.objects.filter(type_service="AC"),
                "locations": Location.objects.all(),
                "active_locations": active_locations,
            })

        location = Location.objects.get(id=location_form)

        existing_groups = ProductGroup.objects.filter(
            type_service="AC",
            location=location
        ).order_by("order")

        last_group = existing_groups.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the group from the form information
        new_group = ProductGroup.objects.create(
            name=name,
            location=location,
            order=order,
            type_service="AC",
        )
        new_group.save()

        return render(request, "tariff/accommodation/product_group.html", {
            "groups": ProductGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
            "active_locations": active_locations,
        })

    else:
        return render(request, "tariff/accommodation/product_group.html", {
            "groups": ProductGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
            "active_locations": active_locations,
        })
