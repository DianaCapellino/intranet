from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from tariff.models import Supplier, Client, SupplierGroup, Product, ProductGroup, Location, RateLine, Rate, RateGroup, Change, CostItem, FixedRateCost, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, HOTEL_QUALITY_OPTIONS, FCU_OPTIONS, TOURS_TIMING, TYPE_HISTORY, TAXES
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from collections import defaultdict
from datetime import date
from django.db.models import Avg
import json

MARGIN_SVS_OPTIONS = [
    ("Low", "0.87"),
    ("Regular", "0.8"),
    ("High", "0.8"),
]

MARGIN_ACC_OPTIONS = [
    ("Low", "0.89"),
    ("Regular", "0.85"),
    ("High", "0.82"),
]

@login_required
def modify_tariff(request):
    return render(request, "tariff/modify_tariff.html")


@login_required
def accommodation(request):
    return render(request, "tariff/accommodation.html")


@login_required
def service(request):
    return render(request, "tariff/service.html")


"""
LOCATIONS
"""

# Showing locations and creating new ones
@login_required
def locations(request):
    if request.method == "POST":

        code = request.POST["code"].upper()
        name = request.POST["name"]
        min_nights = request.POST["min_nights"]
        max_nights = request.POST["max_nights"]
        margin_acc = request.POST["margin_acc"]
        margin_svs = request.POST["margin_svs"]

        if not name or not code or not min_nights or not max_nights or not margin_acc or not margin_svs:
            return render(request, "tariff/locations.html", {
                "message": "Todos los campos deben ser completados",
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
            })

        Location.objects.create(
            code=code.upper(),
            name=name,
            description=request.POST.get("description", ""),
            children_ranking=request.POST["children_ranking"],
            disabled_ranking=request.POST["disabled_ranking"],
            sustentability_ranking=request.POST["sustentability_ranking"],
            attractions=request.POST.getlist("attractions"),
            interests=request.POST.getlist("interests"),
            min_nights=min_nights,
            max_nights=max_nights,
            margin_acc=margin_acc,
            margin_svs=margin_svs,
            pic1_url=request.POST.get("pic1_url"),
            pic2_url=request.POST.get("pic2_url"),
            pic3_url=request.POST.get("pic3_url"),
        )


        return render(request, "tariff/locations.html", {
            "locations": Location.objects.all(),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
        })
    else:
        return render(request, "tariff/locations.html", {
            "locations": Location.objects.all(),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
        })


# Modifying a particular location
@login_required
def modify_location(request, location_id):
    # Gets the object of the location modifying
    location = Location.objects.get(id=location_id)
    
    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify location
        code = request.POST["code"].upper()
        name = request.POST["name"]
        min_nights = request.POST["min_nights"]
        max_nights = request.POST["max_nights"]
        margin_acc = request.POST["margin_acc"]
        margin_svs = request.POST["margin_svs"]        

        # Validations
        if not name or not code or not min_nights or not max_nights or not margin_acc or not margin_svs:
            return render(request, "tariff/locations.html", {
                "message_modify": "Todos los campos deben ser completados",
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
            })
        
        # Modifies the model of the location from the form information
        location.name=name
        location.code=code
        location.description=request.POST["description"]
        location.children_ranking=request.POST["children_ranking"]
        location.disabled_ranking=request.POST["disabled_ranking"]
        location.sustentability_ranking=request.POST["sustentability_ranking"]
        location.attractions=request.POST.getlist("attractions")
        location.interests=request.POST.getlist("interests")
        location.min_nights=min_nights
        location.max_nights=max_nights
        location.margin_acc=margin_acc
        location.margin_svs=margin_svs
        location.pic1_url=request.POST.get("pic1_url")
        location.pic2_url=request.POST.get("pic2_url")
        location.pic3_url=request.POST.get("pic3_url")
        
        location.save()

        return HttpResponseRedirect(reverse("locations"), {
            "locations": Location.objects.all(),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
        })


# Json to edit and delete a particular location
@login_required
@csrf_exempt
def json_location(request, location_id):
    
    # Query for location
    try:
        location_obj = Location.objects.get(pk=location_id)
        location = model_to_dict(location_obj)
    except Location.DoesNotExist:
        return JsonResponse({"error": "Location not found"}, status=404)

    # Return location contents
    if request.method == "GET":
        return JsonResponse(location, safe=False)

    # Update location
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the contact
        if data.get("name") is not None:
            location_obj.name = data["name"]

        # Save the changes of the contact
        location_obj.save()
        return HttpResponse(status=204)
    
    # Deletes the contact
    elif request.method == "DELETE":
        location_obj.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


"""
SUPPLIER GROUP
"""

# Modifying an specific group
@login_required
def modify_supplier_group(request, group_id):
    # Gets the object of the group modifying
    group = SupplierGroup.objects.get(id=group_id) 
    
    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify group
        name = request.POST["name"]
        location_form = request.POST["location"]
        order = request.POST["order"]
        type_service = request.POST["type_service"]

        # Validations
        if not name or not location_form or not order or not type_service:
            if group.type_service == "AC":
                return render(request, "tariff/accommodation/supplier_group.html", {
                    "message_modify": "Todos los campos deben ser completados",
                    "groups": SupplierGroup.objects.filter(type_service="AC"),
                    "locations": Location.objects.all(),
                })
        
        location = Location.objects.get(pk=location_form)

        # Modifies the model of the supplier group from the form information
        group.name=name
        group.location=location
        group.order=order
        group.type_service=type_service
        
        group.save()
        
        if group.type_service == "AC":
            return HttpResponseRedirect(reverse("acc_supplier_group"), {
                "message_modify": "Se ha modificado correctamente",
                "groups": SupplierGroup.objects.filter(type_service="AC"),
                "locations": Location.objects.all(),
            })
        else:
            return HttpResponseRedirect(reverse("acc_supplier_group"), {
                "message_modify": "Se ha modificado correctamente",
                "groups": SupplierGroup.objects.filter(type_service="AC"),
                "locations": Location.objects.all(),
            })

# Editing or deleting a particular supplier group
@login_required
@csrf_exempt
def json_supplier_group(request, group_id):
    
    # Query for contact
    try:
        group_obj = SupplierGroup.objects.get(pk=group_id)
        group = model_to_dict(group_obj)
    except SupplierGroup.DoesNotExist:
        return JsonResponse({"error": "Supplier Group not found"}, status=404)

    # Return contact contents
    if request.method == "GET":
        return JsonResponse(group, safe=False)

    # Update contact
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the contact
        if data.get("name") is not None:
            group_obj.name = data["name"]
        if data.get("location") is not None:
            location_obj = Location.objects.get(pk=int(data["location"]))
            group_obj.location = location_obj
        if data.get("order") is not None:
            group_obj.order = data["order"]

        # Save the changes of the contact
        group_obj.save()
        return HttpResponse(status=204)
    
    # Deletes the contact
    elif request.method == "DELETE":
        group_obj.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


"""
PRODUCT GROUP
"""

# Modifying an specific group
@login_required
def modify_product_group(request, group_id):
    # Gets the object of the group modifying
    group = ProductGroup.objects.get(id=group_id) 
    
    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify group
        name = request.POST["name"]
        location_form = request.POST["location"]
        order = request.POST["order"]
        type_service = request.POST["type_service"]

        # Validations
        if not name or not location_form or not order or not type_service:
            if group.type_service == "AC":
                return render(request, "tariff/accommodation/product_group.html", {
                    "message_modify": "Todos los campos deben ser completados",
                    "groups": ProductGroup.objects.filter(type_service="AC"),
                    "locations": Location.objects.all(),
                })
            else:
                return render(request, "tariff/service/product_group.html", {
                    "message_modify": "Todos los campos deben ser completados",
                    "groups": ProductGroup.objects.filter(type_service="NA"),
                    "locations": Location.objects.all(),
                })

        location = Location.objects.get(pk=location_form)

        # Modifies the model of the supplier group from the form information
        group.name=name
        group.location=location
        group.order=order
        group.type_service=type_service
        
        group.save()

        if group.type_service == "AC":
            return HttpResponseRedirect(reverse("acc_product_group"), {
                "message_modify": "Se ha modificado correctamente",
                "groups": ProductGroup.objects.filter(type_service="AC"),
                "locations": Location.objects.all(),
            })
        else:
            return HttpResponseRedirect(reverse("svs_product_group"), {
                "message_modify": "Se ha modificado correctamente",
                "groups": ProductGroup.objects.filter(type_service="NA"),
                "locations": Location.objects.all(),
            })


# Editing or deleting a particular supplier group
@login_required
@csrf_exempt
def json_product_group(request, group_id):
    
    # Query for contact
    try:
        group_obj = ProductGroup.objects.get(pk=group_id)
        group = model_to_dict(group_obj)
    except ProductGroup.DoesNotExist:
        return JsonResponse({"error": "Product Group not found"}, status=404)

    # Return contact contents
    if request.method == "GET":
        return JsonResponse(group, safe=False)

    # Update contact
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the contact
        if data.get("name") is not None:
            group_obj.name = data["name"]
        if data.get("location") is not None:
            location_obj = Location.objects.get(pk=int(data["location"]))
            group_obj.location = location_obj
        if data.get("order") is not None:
            group_obj.order = data["order"]

        # Save the changes of the contact
        group_obj.save()
        return HttpResponse(status=204)
    
    # Deletes the contact
    elif request.method == "DELETE":
        group_obj.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)

"""
SUPPLIER
"""

# Modifying a particular supplier
@login_required
def modify_supplier(request, supplier_id):
    # Gets the object of the supplier modifying
    supplier = Supplier.objects.get(id=supplier_id)

    type_service = supplier.group.type_service

    supplier_groups = SupplierGroup.objects.filter(type_service=type_service)
    product_groups = ProductGroup.objects.filter(type_service=type_service)

    default_location = Location.objects.get(code="BUE")

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify supplier
        code = request.POST["code"].upper()
        name = request.POST["name"]
        margin = request.POST["margin"]
        order = request.POST["order"]

        if type_service == "AC":
            category = request.POST["category"]
            group_form = request.POST["group"]

        # Validations
        if not name or not code or not margin:
            if type_service == "AC":
                return render(request, "tariff/accommodation/supplier.html", {
                    "message_modify": "Todos los campos deben ser completados",
                    "suppliers": Supplier.objects.filter(group__type_service=type_service),
                    "locations": Location.objects.all(),
                    "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                    "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                    "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                    "ATTRACTIONS": ATTRACTIONS,
                    "INTERESTS": INTERESTS,
                    "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
                    "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                    "supplier_groups": supplier_groups.order_by("location__name", "name"),
                })
            else:
                return render(request, "tariff/service/supplier.html", {
                    "suppliers": Supplier.objects.filter(group__type_service=type_service),
                    "locations": Location.objects.all(),
                    "products": Product.objects.filter(type_service="NA"),
                    "ATTRACTIONS": ATTRACTIONS,
                    "INTERESTS": INTERESTS,
                    "product_groups": product_groups .order_by("location__name", "name"),
                    "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
                    "default_location": default_location,
                    "locations": Location.objects.all(),
                })

        if type_service == "AC":
            group = SupplierGroup.objects.get(pk=group_form)

        if type_service == "AC":
            supplier.children_ranking=request.POST["children_ranking"]
            supplier.disabled_ranking=request.POST["disabled_ranking"]
            supplier.sustentability_ranking=request.POST["sustentability_ranking"]
            supplier.hotel_quality=category
            supplier.group=group
            supplier.prepayment=request.POST.get("prepayment")

        # Modifies the model of the supplier from the form information
        supplier.name=name
        supplier.code=code
        supplier.order=order
        supplier.description=request.POST["description"]
        supplier.attractions=request.POST.getlist("attractions")
        supplier.interests=request.POST.getlist("interests")
        supplier.margin=request.POST["margin"]
        supplier.note=request.POST.get("note")
        supplier.pic1_url=request.POST.get("pic1_url")
        supplier.pic2_url=request.POST.get("pic2_url")
        supplier.pic3_url=request.POST.get("pic3_url")
        
        supplier.save()

        if type_service == "AC":
            return HttpResponseRedirect(reverse("acc_supplier"), {
                "suppliers": Supplier.objects.filter(group__type_service=type_service),
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
                "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                "supplier_groups": supplier_groups .order_by("location__name", "name"),
            })
        else:
            return HttpResponseRedirect(reverse("svs_supplier"), {
                "suppliers": Supplier.objects.filter(group__type_service=type_service),
                "locations": Location.objects.all(),
                "products": Product.objects.filter(type_service="NA"),
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "product_groups": product_groups .order_by("location__name", "name"),
                "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
                "default_location": default_location,
                "locations": Location.objects.all(),
            })


# Json to edit and delete a particular supplier
@login_required
@csrf_exempt
def json_supplier(request, supplier_id):
    
    # Query for supplier
    try:
        supplier_obj = Supplier.objects.get(pk=supplier_id)
        supplier = model_to_dict(supplier_obj)
    except Supplier.DoesNotExist:
        return JsonResponse({"error": "Supplier not found"}, status=404)

    # Return supplier contents
    if request.method == "GET":
        return JsonResponse(supplier, safe=False)

    # Update location
    elif request.method == "PUT":

        # Get json information
        data = json.loads(request.body)

        # Update information of the contact
        if data.get("name") is not None:
            supplier_obj.name = data["name"]

        # Save the changes of the contact
        supplier_obj.save()
        return HttpResponse(status=204)
    
    # Deletes the contact
    elif request.method == "DELETE":
        supplier_obj.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)


def _cost_per_pax(value, fcu, tax, increase, usd, exchange, pax):
    """Calculate cost per passenger applying tax, increase and exchange."""
    v = float(value)
    if fcu == 'Group' and pax:
        v = v / pax
    v *= (1 + float(tax or 0) / 100)
    v *= (1 + float(increase or 0) / 100)
    if not usd and exchange:
        v /= float(exchange)
    return round(v, 2)


def calculate_margins(rate):
    if not rate:
        return

    if rate.cost > 0 and rate.sell_tourplan > 0:
        rate.margin_tp = ((rate.sell_tourplan - rate.cost) / rate.sell_tourplan) * 100
    else:
        rate.margin_tp = 0

    if rate.cost > 0 and rate.sell > 0:
        rate.margin_ai = ((rate.sell - rate.cost) / rate.sell) * 100
    else:
        rate.margin_ai = 0


# Modifying a particular supplier rates
@login_required
def modify_supplier_rates(request, supplier_id):

    if request.user.userType == "Cliente":
        this_year = date.today().year

        return render(request, "tariff/tariff.html", {
            "locations":Location.objects.all(),
            "clients": Client.objects.all(),
            "this_year": this_year,
        })

    # Gets the object of the supplier modifying
    supplier = Supplier.objects.get(id=supplier_id)

    products = Product.objects.filter(supplier=supplier)

    type_service = supplier.group.type_service

    product_groups = ProductGroup.objects.filter(type_service=type_service)

    # Create the list of lines in the correct order
    rate_lines = (
        RateLine.objects
        .filter(group__product__supplier=supplier)
        .select_related("group__product")
        .prefetch_related("line_rates", "line_rates__cost_items", "line_rates__rates_with_fixed")
        .order_by("date_from", "group__product__order")
    )

    if type_service == "AC":
        for line in rate_lines:
            line.sgl = None
            line.dbl = None
            line.tpl = None

            for rate in line.line_rates.all():
                if rate.column_options == "SGL":
                    line.sgl = rate
                elif rate.column_options == "DBL":
                    line.dbl = rate
                elif rate.column_options == "TPL":
                    line.tpl = rate

            calculate_margins(line.sgl)
            calculate_margins(line.dbl)
            calculate_margins(line.tpl)
    else:
        for line in rate_lines:
            bases_map = {str(i): None for i in range(1, 7)}

            for rate in line.line_rates.all():
                if rate.column_options in bases_map:
                    bases_map[rate.column_options] = rate

            line.bases = []
            for i in range(1, 7):
                rate = bases_map[str(i)]
                calculate_margins(rate)

                cost_items_list = []
                fixed_costs_list = []
                if rate:
                    for ci in rate.cost_items.all():
                        ci.cost_per_pax = _cost_per_pax(
                            ci.value, ci.fcu, ci.tax, rate.increase, ci.usd, ci.exchange, i
                        )
                        cost_items_list.append(ci)
                    for frc in rate.rates_with_fixed.all():
                        frc.cost_per_pax = _cost_per_pax(
                            frc.value, frc.fcu, 0, frc.increase, frc.usd, frc.exchange, i
                        )
                        fixed_costs_list.append(frc)

                has_items  = bool(cost_items_list or fixed_costs_list)
                total_cost = round(
                    sum(ci.cost_per_pax for ci in cost_items_list) +
                    sum(frc.cost_per_pax for frc in fixed_costs_list), 2
                ) if has_items else None

                effective_cost = total_cost if has_items else (float(rate.cost) if rate and rate.cost else None)
                margin_ai      = getattr(rate, 'margin_ai', 0) if rate else 0
                suggested_sell = None
                if has_items and total_cost and supplier.margin:
                    import math as _math
                    suggested_sell = _math.ceil(total_cost / supplier.margin)
                elif effective_cost and margin_ai and 0 < margin_ai < 100:
                    suggested_sell = round(effective_cost / (1 - margin_ai / 100))

                line.bases.append({
                    "pax": i,
                    "rate": rate,
                    "cost_items": cost_items_list,
                    "fixed_costs": fixed_costs_list,
                    "has_items": has_items,
                    "total_cost": total_cost,
                    "suggested_sell": suggested_sell,
                })

            import json as _json
            line.rate_map_json = _json.dumps({
                str(b['pax']): b['rate'].id if b['rate'] else None
                for b in line.bases
            })

    blocks = defaultdict(list)

    for line in rate_lines:
        key = (line.date_from, line.date_to, line.season)
        blocks[key].append(line)

    rate_blocks = []

    for (date_from, date_to, season), lines in blocks.items():
        sorted_lines = sorted(lines, key=lambda x: x.group.product.orden if hasattr(x.group.product, 'orden') and x.group.product.orden is not None else 999999)
        
        rate_blocks.append({
            "date_from": date_from,
            "date_to": date_to,
            "season": season,
            "lines": sorted_lines,
            "margin": supplier.margin,
        })

    if type_service == "AC":
        return render(request, "tariff/accommodation/supplier_rates.html", {
            "supplier": supplier,
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
            "products": products,
            "product_groups": product_groups,
            "rate_lines": rate_lines,
            "rate_blocks": rate_blocks,
        })
    else:
        fixed_rate_costs = list(
            FixedRateCost.objects.filter(supplier=supplier)
            .values('id', 'name', 'date_from', 'date_to', 'value', 'usd', 'exchange', 'increase', 'fcu')
        )
        import json as _json
        return render(request, "tariff/service/supplier_rates.html", {
            "supplier": supplier,
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "products": products,
            "product_groups": product_groups,
            "rate_lines": rate_lines,
            "rate_blocks": rate_blocks,
            "TAXES": TAXES,
            "fixed_rate_costs_json": _json.dumps(fixed_rate_costs, default=str),
            "default_exchange": supplier.default_exchange,
        })


"""
PRODUCT
"""

# Modifying a particular product
@login_required
def modify_product(request, product_id):
    # Obtener el producto
    product = Product.objects.get(id=product_id)
    supplier = product.supplier

    type_service = product.group.type_service
    
    # Obtener datos necesarios para los selects
    suppliers = Supplier.objects.filter(group__type_service=type_service).order_by("name")
    product_groups = ProductGroup.objects.filter(type_service=type_service).order_by("location__name", "name")
    clients = Client.objects.all().order_by("name")
    
    if request.method == "POST":
        # Obtener información del formulario
        code = request.POST["code"].upper()
        name = request.POST["name"]
        description = request.POST.get("description", "")
        supplier_id = request.POST["supplier"]
        group_id = request.POST["group"]
        order = request.POST["order"]
        quality = request.POST.get("quality", "")
        fcu = request.POST["fcu"]
        scu = request.POST["scu"]
        note = request.POST.get("note", "")

        if type_service == "NA":
            tour_timing = request.POST["timing"]
        
        # Validaciones
        if not name or not code or not supplier_id or not group_id or not order:
            return render(request, "tariff/accommodation/modify_product.html", {
                "message": "Todos los campos obligatorios deben ser completados",
                "product": product,
                "suppliers": suppliers,
                "product_groups": product_groups,
                "clients": clients,
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "FCU_OPTIONS": FCU_OPTIONS,
            })
        
        # Obtener objetos relacionados
        new_supplier = Supplier.objects.get(pk=supplier_id)
        new_group = ProductGroup.objects.get(pk=group_id)
        
        # Modificar el producto
        product.code = code
        product.name = name
        product.description = description
        product.supplier = new_supplier
        product.group = new_group
        product.order = order
        product.quality = quality
        product.fcu = fcu
        product.scu = scu
        product.note = note
        product.children_ranking = request.POST["children_ranking"]
        product.disabled_ranking = request.POST["disabled_ranking"]
        product.sustentability_ranking = request.POST["sustentability_ranking"]
        product.attractions = request.POST.getlist("attractions")
        product.interests = request.POST.getlist("interests")
        product.pic1_url = request.POST.get("pic1_url", "")
        product.pic2_url = request.POST.get("pic2_url", "")
        product.pic3_url = request.POST.get("pic3_url", "")
        product.shown = request.POST.get("shown") == "on"
        product.recommended = request.POST.get("recommended") == "on"
        product.isActivated = request.POST.get("isActivated") == "on"
        
        # Actualizar clientes disponibles
        selected_clients = request.POST.getlist("clients")
        product.clients.set(selected_clients)

        if type_service == "NA":
            product.tour_timing = tour_timing
        
        product.save()
        
        # Redirigir a la página de tarifas del proveedor
        return HttpResponseRedirect(reverse("modify_supplier_rates", args=[supplier.id]))
    
    else:

        if type_service == "AC":
            return render(request, "tariff/accommodation/modify_product.html", {
                "product": product,
                "supplier": supplier,
                "suppliers": suppliers,
                "product_groups": product_groups,
                "clients": clients,
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "FCU_OPTIONS": FCU_OPTIONS,
            })
        else:
            return render(request, "tariff/service/modify_product.html", {
                "product": product,
                "supplier": supplier,
                "suppliers": suppliers,
                "product_groups": product_groups,
                "clients": clients,
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "FCU_OPTIONS": FCU_OPTIONS,
                "tours_timing": TOURS_TIMING,
            })


@login_required
@csrf_exempt
def update_rate_block(request):
    try:
        if not request.body:
            return JsonResponse({"ok": False, "error": "No se recibieron datos"}, status=400)
        
        data = json.loads(request.body)
        
        if "rates" not in data:
            return JsonResponse({"ok": False, "error": "Falta el campo 'rates'"}, status=400)
        
        updated_count = 0
        errors = []
        
        rate_ids = [r.get("rate_id") for r in data["rates"] if r.get("rate_id")]

        ratelines = RateLine.objects.filter(
            line_rates__id__in=rate_ids
        ).distinct()

        rateline_data = {}

        for rl in ratelines:
            old_avg = rl.line_rates.aggregate(
                avg=Avg("sell")
            )["avg"] or 0

            rateline_data[rl.id] = {
                "instance": rl,
                "old_avg": old_avg
            }

        # Actualizar rates
        for r in data["rates"]:
            rate_id = r.get("rate_id")
            field = r.get("field")
            value = r.get("value")
            
            if not rate_id or not field:
                continue
            
            try:
                rate_id = int(rate_id)
            except (ValueError, TypeError):
                errors.append(f"ID inválido: {rate_id}")
                continue
                
            if field not in ["cost", "sell", "sell_tourplan"]:
                errors.append(f"Campo no permitido: {field}")
                continue
            
            try:
                if field == "cost":
                    value = float(value) if value != "" else 0.0
                else:
                    value = int(float(value)) if value != "" else 0
            except (ValueError, TypeError):
                errors.append(f"Valor inválido para {field}: {value}")
                continue
            
            if not Rate.objects.filter(id=rate_id).exists():
                errors.append(f"Rate con ID {rate_id} no existe")
                continue
            
            updated = Rate.objects.filter(id=rate_id).update(**{field: value})
            updated_count += updated
        
        # 👇 Actualizar season si se envió
        if "season" in data and data["season"]:
            # Obtener los rate_ids del bloque
            rate_ids = [r.get("rate_id") for r in data["rates"] if r.get("rate_id")]
            
            # Encontrar las RateLines asociadas
            ratelines = RateLine.objects.filter(
                line_rates__id__in=rate_ids
            ).distinct()
            
            # Actualizar el season
            ratelines.update(season=data["season"])

        if "status" in data and data["status"]:
            return
        
        if "margin" in data and data["margin"]:
            return
        
        if "increase" in data and data["increase"]:
            return
        
        # ✅ Actualizar nombres de RateGroup
        if "groups" in data and data["groups"]:
            for g in data["groups"]:
                group_id = g.get("group_id")
                new_name = g.get("new_name")
                
                if not group_id or not new_name:
                    continue
                
                try:
                    group_id = int(group_id)
                    
                    # Verificar que exista el RateGroup
                    if not RateGroup.objects.filter(id=group_id).exists():
                        errors.append(f"RateGroup con ID {group_id} no existe")
                        continue
                    
                    # Actualizar el nombre del grupo
                    RateGroup.objects.filter(id=group_id).update(name=new_name.strip())
                    updated_count += 1
                    
                except (ValueError, TypeError):
                    errors.append(f"ID de grupo inválido: {group_id}")
                    continue

        for rl_id, data_rl in rateline_data.items():
            rl = data_rl["instance"]
            old_avg = data_rl["old_avg"]

            new_avg = rl.line_rates.aggregate(
                avg=Avg("sell")
            )["avg"] or 0

            if old_avg == new_avg:
                continue

            if old_avg == 0 and new_avg > 0:

                previous = RateLine.objects.filter(
                    group=rl.group,
                    season=rl.season
                ).exclude(id=rl.id).order_by("-date_from").first()

                if previous:
                    previous_avg = previous.line_rates.aggregate(
                        avg=Avg("sell")
                    )["avg"] or 0
                else:
                    previous_avg = 0

                change_type = "Add"
                percent = ((new_avg - previous_avg) / previous_avg * 100) if previous_avg != 0 else 0
            else:
                change_type = "Update"
                percent = ((new_avg - old_avg) / old_avg * 100) if old_avg != 0 else 0

            Change.objects.create(
                rate_line=rl,
                type=change_type,
                amount=round(percent, 2)
            )

        return JsonResponse({
            "ok": True, 
            "updated": updated_count,
            "errors": errors if errors else None,
            "message": f"Se actualizaron {updated_count} tarifas"
        })
        
    except Exception as e:
        import traceback
        print("Error completo:")
        print(traceback.format_exc())
        
        return JsonResponse({
            "ok": False, 
            "error": f"Error en el servidor: {str(e)}"
        }, status=500)


@login_required
@csrf_exempt
def copy_rate_block(request):
    try:
        if not request.body:
            return JsonResponse({"ok": False, "error": "No se recibieron datos"}, status=400)
        
        data = json.loads(request.body)
        
        print("Datos recibidos:", data)  # 👈 Debug
        
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        season = data.get("season")
        lines = data.get("lines", [])
        
        if not date_from or not date_to or not season:
            return JsonResponse({"ok": False, "error": "Faltan datos requeridos (fechas o season)"}, status=400)
        
        if not lines:
            return JsonResponse({"ok": False, "error": "No hay líneas para copiar"}, status=400)
        
        created_ratelines = 0
        created_rates = 0
        errors = []
        
        # Para cada línea original
        for line_data in lines:
            rateline_id = line_data.get("rateline_id")
            rategroup_id = line_data.get("rategroup_id")
            
            print(f"Procesando línea: rateline_id={rateline_id}, rategroup_id={rategroup_id}")  # 👈 Debug
            
            if not rateline_id or not rategroup_id:
                errors.append(f"Línea sin IDs válidos")
                continue
            
            # Obtener la RateLine original
            try:
                original_rateline = RateLine.objects.get(id=rateline_id)
            except RateLine.DoesNotExist:
                errors.append(f"RateLine {rateline_id} no existe")
                continue
            
            # Obtener el RateGroup
            try:
                rate_group = RateGroup.objects.get(id=rategroup_id)
            except RateGroup.DoesNotExist:
                errors.append(f"RateGroup {rategroup_id} no existe")
                continue
            
            # Crear nueva RateLine
            new_rateline = RateLine.objects.create(
                date_from=date_from,
                date_to=date_to,
                group=rate_group,
                season=season
            )
            created_ratelines += 1
            
            print(f"Nueva RateLine creada: {new_rateline.id}")  # 👈 Debug
            
            # Copiar todos los Rates de la línea original
            original_rates = Rate.objects.filter(rate_line=original_rateline)
            
            print(f"Copiando {original_rates.count()} rates")  # 👈 Debug
            
            for original_rate in original_rates:
                new_rate = Rate.objects.create(
                    rate_line=new_rateline,
                    status=original_rate.status,
                    increase=original_rate.increase,
                    cost=original_rate.cost,
                    margin=original_rate.margin,
                    sell=original_rate.sell,
                    sell_tourplan=original_rate.sell_tourplan,
                    column_options=original_rate.column_options,
                    has_rate=original_rate.has_rate,
                    has_items=original_rate.has_items,
                    text_value=original_rate.text_value
                )
                # Copy CostItems from original rate
                for ci in original_rate.cost_items.all():
                    CostItem.objects.create(
                        name=ci.name, value=ci.value, tax=ci.tax,
                        usd=ci.usd, exchange=ci.exchange, fcu=ci.fcu,
                        code=ci.code, rate=new_rate,
                    )
                created_rates += 1
                print(f"Rate creado: {new_rate.id} - {new_rate.column_options}")  # 👈 Debug
        
        if created_ratelines == 0:
            return JsonResponse({
                "ok": False,
                "error": "No se pudo crear ninguna línea",
                "details": errors
            }, status=400)

        return JsonResponse({
            "ok": True,
            "created_ratelines": created_ratelines,
            "created_rates": created_rates,
            "errors": errors if errors else None,
            "message": f"Se crearon {created_ratelines} líneas con {created_rates} tarifas"
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("Error completo:")
        print(error_detail)
        
        return JsonResponse({
            "ok": False,
            "error": f"Error en el servidor: {str(e)}",
            "traceback": error_detail
        }, status=500)


@login_required
@csrf_exempt
def delete_rate_block(request):
    try:
        if not request.body:
            return JsonResponse({"ok": False, "error": "No se recibieron datos"}, status=400)
        
        data = json.loads(request.body)
        rateline_ids = data.get("rateline_ids", [])
        
        if not rateline_ids:
            return JsonResponse({"ok": False, "error": "No hay líneas para eliminar"}, status=400)
        
        print(f"Eliminando RateLines: {rateline_ids}")
        
        # Obtener las RateLines
        ratelines = RateLine.objects.filter(id__in=rateline_ids)
        count = ratelines.count()
        
        if count == 0:
            return JsonResponse({"ok": False, "error": "No se encontraron líneas para eliminar"}, status=404)
        
        # Los Rates se eliminan automáticamente por CASCADE
        ratelines.delete()
        
        return JsonResponse({
            "ok": True,
            "deleted": count,
            "message": f"Se eliminaron {count} líneas tarifarias"
        })
        
    except Exception as e:
        import traceback
        print("Error completo:")
        print(traceback.format_exc())
        
        return JsonResponse({
            "ok": False,
            "error": f"Error en el servidor: {str(e)}"
        }, status=500)


@login_required
@csrf_exempt
def create_rate_block(request):
    try:
        if not request.body:
            return JsonResponse({"ok": False, "error": "No se recibieron datos"}, status=400)
        
        data = json.loads(request.body)
        
        print("Datos recibidos:", data)
        
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        season = data.get("season")
        product_ids = data.get("product_ids", [])
        base_costs = data.get("base_costs", {})
        increase = data.get("increase")
        margin = data.get("margin")
        status = data.get("status")
        
        if not date_from or not date_to or not season:
            return JsonResponse({"ok": False, "error": "Faltan datos requeridos"}, status=400)
        
        if not product_ids:
            return JsonResponse({"ok": False, "error": "Debes seleccionar al menos un producto"}, status=400)
        
        print(margin, status)

        created_ratelines = 0
        created_rates = 0
        errors = []
        
        # Para cada producto seleccionado
        for product_id in product_ids:
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                errors.append(f"Producto {product_id} no existe")
                continue
            
            # Obtener o crear RateGroups para este producto
            # Asumimos que cada producto tiene al menos un RateGroup
            rate_groups = RateGroup.objects.filter(product=product)
            
            if not rate_groups.exists():

                # Create RateGroup for accommodation
                if product.group.type_service == "AC":
                    name = "Breakfast included"

                # Create RateGroup for services
                else:
                    name = "To be defined"

                rate_group = RateGroup.objects.create(
                    name=name,
                    order=1,
                    product=product
                )
                rate_groups = [rate_group]
           
            # Crear RateLine para cada RateGroup
            for rate_group in rate_groups:
                new_rateline = RateLine.objects.create(
                    date_from=date_from,
                    date_to=date_to,
                    group=rate_group,
                    season=season
                )
                created_ratelines += 1
                
                # Obtener el margin del supplier
                supplier = product.supplier
                
                if product.group.type_service == "AC":
                    columns = ["SGL", "DBL", "TPL"]
                else:
                    columns = ["1", "2", "3", "4", "5", "6"]

                # Crear Rates para cada columna
                for column_type in columns:
                    # Check if existing rates for this product+column have CostItems
                    template_rate = (
                        Rate.objects
                        .filter(
                            rate_line__group__product=product,
                            column_options=column_type,
                            has_items=True,
                        )
                        .prefetch_related('cost_items')
                        .first()
                    )
                    new_rate = Rate.objects.create(
                        rate_line=new_rateline,
                        status=status,
                        increase=increase,
                        cost=0,
                        margin=margin,
                        sell=0,
                        sell_tourplan=0,
                        column_options=column_type,
                        has_rate=True,
                        has_items=bool(template_rate),
                        text_value=None
                    )
                    # Replicate CostItem structure with value=0
                    if template_rate:
                        for ci in template_rate.cost_items.all():
                            CostItem.objects.create(
                                name=ci.name, value=0, tax=ci.tax,
                                usd=ci.usd, exchange=ci.exchange, fcu=ci.fcu,
                                code=ci.code, rate=new_rate,
                            )
                    created_rates += 1

                # Check if it is the first rate_line in the product
                rate_lines_count = RateLine.objects.filter(
                    group__product=product
                ).count()

                if rate_lines_count == 1:
                    # Create the history of changes
                    new_change = Change.objects.create(
                        date = date.today(),
                        type = "New",
                        rate_line = new_rateline,
                    )
                    new_change.save()
                
                print(f"RateLine creada: {new_rateline.id} para {product.name}")
        
        if created_ratelines == 0:
            return JsonResponse({
                "ok": False,
                "error": "No se pudo crear ninguna línea",
                "details": errors
            }, status=400)
        
        return JsonResponse({
            "ok": True,
            "created_ratelines": created_ratelines,
            "created_rates": created_rates,
            "errors": errors if errors else None,
            "message": f"Se crearon {created_ratelines} líneas con {created_rates} tarifas"
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("Error completo:")
        print(error_detail)
        
        return JsonResponse({
            "ok": False,
            "error": f"Error en el servidor: {str(e)}",
            "traceback": error_detail
        }, status=500)


def modify_change(request, change_id):

    change = Change.objects.get(id=change_id)

    if request.method == "POST":
        type = request.POST["type"]
        amount = request.POST["percentage"]

        # Update information
        change.type = type
        change.amount = amount
        change.save()

        today = date.today()

        last_year = date(today.year - 1, today.month, today.day)

        changes = Change.objects.filter(date__range=(last_year, today))

        return HttpResponseRedirect(reverse("history_of_changes"), {
            "changes": changes,
            "types": TYPE_HISTORY,
        })

# Json to edit and delete a particular change
@login_required
@csrf_exempt
def json_changes(request, change_id):
    
    # Query for change
    try:
        change_obj = Change.objects.get(pk=change_id)
        change = model_to_dict(change_obj)
    except Change.DoesNotExist:
        return JsonResponse({"error": "Change not found"}, status=404)

    # Return change contents
    if request.method == "GET":
        return JsonResponse(change, safe=False)
    
    # Deletes the change
    elif request.method == "DELETE":
        change_obj.delete()
        return HttpResponse(status=204)

    # ClientContact requests must be via GET or PUT or DELETE
    else:
        return JsonResponse({
            "error": "GET or PUT or DELETE request required."
        }, status=400)

# ─── Cost Items & Fixed Rate Costs CRUD ───────────────────────────────────────

@login_required
def add_cost_item(request):
    """Create a CostItem linked to one or more Rate IDs."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    rate_ids  = data.get('rate_ids', [])
    name      = data.get('name', '')
    value     = float(data.get('value', 0))
    tax       = data.get('tax', '0')
    usd       = data.get('usd', True)
    exchange  = int(data.get('exchange', 1))
    fcu       = data.get('fcu', 'Person')
    code      = data.get('code', '')

    created = []
    for rate_id in rate_ids:
        try:
            rate = Rate.objects.get(pk=rate_id)
            ci = CostItem.objects.create(
                name=name, value=value, tax=tax, usd=usd,
                exchange=exchange, fcu=fcu, rate=rate, code=code,
            )
            if not rate.has_items:
                rate.has_items = True
                rate.save(update_fields=['has_items'])
            created.append({'id': ci.id, 'rate_id': rate_id})
        except Rate.DoesNotExist:
            pass
    return JsonResponse({'created': created})


@login_required
def delete_cost_item(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        ci = CostItem.objects.select_related('rate').get(pk=item_id)
        rate = ci.rate
        ci.delete()
        if rate.has_items and not rate.cost_items.exists():
            rate.has_items = False
            rate.save(update_fields=['has_items'])
        return JsonResponse({'deleted': True})
    except CostItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def add_fixed_rate_link(request):
    """Link an existing FixedRateCost to one or more Rate IDs."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data     = json.loads(request.body)
    frc_id   = data.get('fixed_rate_id')
    rate_ids = data.get('rate_ids', [])
    try:
        frc = FixedRateCost.objects.get(pk=frc_id)
        for rate_id in rate_ids:
            frc.rate.add(rate_id)
        return JsonResponse({'linked': True})
    except FixedRateCost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def create_fixed_rate_cost(request):
    """Create a new FixedRateCost and link it to one or more Rate IDs."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    try:
        supplier = Supplier.objects.get(pk=data['supplier_id'])
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)
    frc = FixedRateCost.objects.create(
        name      = data['name'],
        date_from = data['date_from'],
        date_to   = data['date_to'],
        supplier  = supplier,
        value     = float(data['value']),
        usd       = data.get('usd', True),
        exchange  = int(data.get('exchange', 1)),
        increase  = float(data['increase']) if data.get('increase') else None,
        fcu       = data.get('fcu', 'Person'),
    )
    for rate_id in data.get('rate_ids', []):
        frc.rate.add(rate_id)
    return JsonResponse({'id': frc.id, 'name': frc.name})


@login_required
def remove_fixed_rate_link(request):
    """Remove a FixedRateCost from a specific Rate."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data   = json.loads(request.body)
    frc_id = data.get('fixed_rate_id')
    rate_id = data.get('rate_id')
    try:
        frc = FixedRateCost.objects.get(pk=frc_id)
        frc.rate.remove(rate_id)
        return JsonResponse({'removed': True})
    except FixedRateCost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def update_fixed_rate_cost(request):
    """Update an existing FixedRateCost."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    try:
        frc = FixedRateCost.objects.get(pk=data['id'])
    except FixedRateCost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    frc.name      = data.get('name', frc.name)
    frc.value     = float(data.get('value', frc.value))
    frc.usd       = data.get('usd', frc.usd)
    frc.exchange  = int(data.get('exchange', frc.exchange))
    frc.date_from = data.get('date_from', str(frc.date_from))
    frc.date_to   = data.get('date_to',   str(frc.date_to))
    frc.increase  = float(data['increase']) if data.get('increase') not in (None, '') else None
    frc.fcu       = data.get('fcu', frc.fcu)
    frc.save()
    return JsonResponse({'updated': True})


@login_required
def delete_fixed_rate_cost(request, frc_id):
    """Permanently delete a FixedRateCost."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        FixedRateCost.objects.get(pk=frc_id).delete()
        return JsonResponse({'deleted': True})
    except FixedRateCost.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def update_supplier_exchange(request, supplier_id):
    """Set the default_exchange on a Supplier."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    try:
        s = Supplier.objects.get(pk=supplier_id)
        s.default_exchange = int(data.get('exchange', 1))
        s.save(update_fields=['default_exchange'])
        return JsonResponse({'updated': True})
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def bulk_update_exchange(request, supplier_id):
    """Update exchange on all ARS CostItems and FixedRateCosts for this supplier."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data     = json.loads(request.body)
    exchange = int(data.get('exchange', 1))

    # All rates belonging to this supplier
    rate_ids = Rate.objects.filter(
        rate_line__group__product__supplier_id=supplier_id
    ).values_list('id', flat=True)

    ci_updated  = CostItem.objects.filter(rate_id__in=rate_ids, usd=False).update(exchange=exchange)
    frc_updated = FixedRateCost.objects.filter(supplier_id=supplier_id, usd=False).update(exchange=exchange)

    return JsonResponse({'cost_items': ci_updated, 'fixed_rate_costs': frc_updated})


@login_required
def update_cost_item(request):
    """Update an existing CostItem."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = json.loads(request.body)
    try:
        ci = CostItem.objects.get(pk=data['id'])
    except CostItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    ci.name     = data.get('name', ci.name)
    ci.value    = float(data.get('value', ci.value))
    ci.fcu      = data.get('fcu', ci.fcu)
    ci.tax      = data.get('tax', ci.tax)
    ci.usd      = data.get('usd', ci.usd)
    ci.exchange = int(data.get('exchange', ci.exchange))
    ci.save()
    return JsonResponse({'updated': True})


@login_required
def update_rate_cost(request):
    """Update Rate.cost when cost items total changes."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data    = json.loads(request.body)
    rate_id = data['rate_id']
    cost    = float(data['cost'])
    Rate.objects.filter(pk=rate_id).update(cost=cost)
    return JsonResponse({'ok': True})
