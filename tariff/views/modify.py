from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from tariff.models import Supplier, SupplierGroup, Product, ProductGroup, Location, RateLine, Rate, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, HOTEL_QUALITY_OPTIONS
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from collections import defaultdict
import json

MARGIN_SVS_OPTIONS = [
    ("Low", "0.87"),
    ("Regular", "0.8"),
    ("High", "0.8"),
]

@login_required
def modify_tariff(request):
    return render(request, "tariff/modify_tariff.html")


@login_required
def accommodation(request):
    return render(request, "tariff/accommodation.html")

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
            return HttpResponseRedirect(reverse("acc_product_group"), {
                "message_modify": "Se ha modificado correctamente",
                "groups": ProductGroup.objects.filter(type_service="AC"),
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
    supplier_groups = SupplierGroup.objects.filter(type_service="AC")

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify supplier
        code = request.POST["code"].upper()
        name = request.POST["name"]
        category = request.POST["category"]
        group_form = request.POST["group"]
        margin = request.POST["margin"]
        order = request.POST["order"]

        # Validations
        if not name or not code or not category or not group_form or not margin:
            return render(request, "tariff/accommodation/supplier.html", {
                "message_modify": "Todos los campos deben ser completados",
                "suppliers": Supplier.objects.filter(group__type_service="AC"),
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
            })

        group = SupplierGroup.objects.get(pk=group_form)
        print(group)
        
        # Modifies the model of the supplier from the form information
        supplier.name=name
        supplier.code=code
        supplier.description=request.POST["description"]
        supplier.hotel_quality=category
        supplier.group=group
        supplier.order=order
        supplier.children_ranking=request.POST["children_ranking"]
        supplier.disabled_ranking=request.POST["disabled_ranking"]
        supplier.sustentability_ranking=request.POST["sustentability_ranking"]
        supplier.attractions=request.POST.getlist("attractions")
        supplier.interests=request.POST.getlist("interests")
        supplier.margin=request.POST["margin"]
        supplier.note=request.POST.get("note")
        supplier.prepayment=request.POST.get("prepayment")
        supplier.pic1_url=request.POST.get("pic1_url")
        supplier.pic2_url=request.POST.get("pic2_url")
        supplier.pic3_url=request.POST.get("pic3_url")
        
        supplier.save()

        return HttpResponseRedirect(reverse("acc_supplier"), {
            "suppliers": Supplier.objects.filter(group__type_service="AC"),
            "locations": Location.objects.all(),
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
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


# Modifying a particular supplier rates
@login_required
def modify_supplier_rates(request, supplier_id):
    # Gets the object of the supplier modifying
    supplier = Supplier.objects.get(id=supplier_id)

    products = Product.objects.filter(supplier=supplier)

    product_groups = ProductGroup.objects.filter(type_service="AC")

    # Create the list of lines in the correct order
    rate_lines = (
        RateLine.objects
        .filter(group__product__supplier=supplier)
        .select_related("group__product")
        .prefetch_related("line_rates")
        .order_by("date_from")
    )

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

    blocks = defaultdict(list)

    for line in rate_lines:
        key = (line.date_from, line.date_to)
        blocks[key].append(line)

    rate_blocks = []

    for (date_from, date_to), lines in blocks.items():
        rate_blocks.append({
            "date_from": date_from,
            "date_to": date_to,
            "lines": lines
        })

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify supplier
        code = request.POST["code"].upper()
        name = request.POST["name"]
        category = request.POST["category"]
        group_form = request.POST["group"]
        margin = request.POST["margin"]
        order = request.POST["order"]

        # Validations
        if not name or not code or not category or not group_form or not margin:
            return render(request, "tariff/accommodation/supplier.html", {
                "message_modify": "Todos los campos deben ser completados",
                "suppliers": Supplier.objects.filter(group__type_service="AC"),
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
            })

        group = SupplierGroup.objects.get(pk=group_form)
        print(group)
        
        # Modifies the model of the supplier from the form information
        supplier.name=name
        supplier.code=code
        supplier.description=request.POST["description"]
        supplier.hotel_quality=category
        supplier.group=group
        supplier.order=order
        supplier.children_ranking=request.POST["children_ranking"]
        supplier.disabled_ranking=request.POST["disabled_ranking"]
        supplier.sustentability_ranking=request.POST["sustentability_ranking"]
        supplier.attractions=request.POST.getlist("attractions")
        supplier.interests=request.POST.getlist("interests")
        supplier.margin=request.POST["margin"]
        supplier.note=request.POST.get("note")
        supplier.prepayment=request.POST.get("prepayment")
        supplier.pic1_url=request.POST.get("pic1_url")
        supplier.pic2_url=request.POST.get("pic2_url")
        supplier.pic3_url=request.POST.get("pic3_url")
        
        supplier.save()

        return HttpResponseRedirect(reverse("acc_supplier"), {
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
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
        })
    else:
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


"""
PRODUCT
"""

# Modifying a particular product
@login_required
def modify_product(request, product_id):
    # Gets the object of the product modifying
    product = Product.objects.get(id=product_id)
    product_groups = ProductGroup.objects.filter(type_service="AC")
    supplier = product.supplier
    products = supplier.supplier_products.all()

    # Create the list of lines in the correct order
    rate_lines = (
        RateLine.objects
        .filter(group__product__supplier=supplier)
        .select_related("group__product")
        .prefetch_related("line_rates")
        .order_by("date_from")
    )

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

    blocks = defaultdict(list)

    for line in rate_lines:
        key = (line.date_from, line.date_to)
        blocks[key].append(line)

    rate_blocks = []

    for (date_from, date_to), lines in blocks.items():
        rate_blocks.append({
            "date_from": date_from,
            "date_to": date_to,
            "lines": lines
        })

    # Gets the information from the form
    if request.method == "POST":

        # Attempt to modify supplier
        code = request.POST["code"].upper()
        name = request.POST["name"]
        category = request.POST["category"]
        group_form = request.POST["group"]
        margin = request.POST["margin"]
        order = request.POST["order"]

        # Validations
        if not name or not code or not category or not group_form or not margin:
            return render(request, "tariff/accommodation/supplier.html", {
                "message_modify": "Todos los campos deben ser completados",
                "suppliers": Supplier.objects.filter(group__type_service="AC"),
                "locations": Location.objects.all(),
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "HOTEL_QUALITY_OPTIONS": HOTEL_QUALITY_OPTIONS,
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
            })

        group = SupplierGroup.objects.get(pk=group_form)
        print(group)
        
        # Modifies the model of the supplier from the form information
        supplier.name=name
        supplier.code=code
        supplier.description=request.POST["description"]
        supplier.hotel_quality=category
        supplier.group=group
        supplier.order=order
        supplier.children_ranking=request.POST["children_ranking"]
        supplier.disabled_ranking=request.POST["disabled_ranking"]
        supplier.sustentability_ranking=request.POST["sustentability_ranking"]
        supplier.attractions=request.POST.getlist("attractions")
        supplier.interests=request.POST.getlist("interests")
        supplier.margin=request.POST["margin"]
        supplier.note=request.POST.get("note")
        supplier.prepayment=request.POST.get("prepayment")
        supplier.pic1_url=request.POST.get("pic1_url")
        supplier.pic2_url=request.POST.get("pic2_url")
        supplier.pic3_url=request.POST.get("pic3_url")
        
        supplier.save()

        return HttpResponseRedirect(reverse("acc_supplier"), {
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
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
        })
    else:
        return render(request, "tariff/accommodation/modify_product.html", {
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
            "default_product": product,
            "rate_blocks": rate_blocks,
        })


@csrf_exempt
def update_rate_block(request):
    try:
        # Verificar que el body no esté vacío
        if not request.body:
            return JsonResponse({"ok": False, "error": "No se recibieron datos"}, status=400)
        
        data = json.loads(request.body)
        
        # Verificar que exista el campo rates
        if "rates" not in data:
            return JsonResponse({"ok": False, "error": "Falta el campo 'rates'"}, status=400)
        
        # Actualizar cada rate
        updated_count = 0
        errors = []
        
        for r in data["rates"]:
            rate_id = r.get("rate_id")
            field = r.get("field")
            value = r.get("value")
            
            # Validaciones
            if not rate_id or not field:
                continue
            
            # Verificar que el rate_id sea válido y convertirlo a int
            try:
                rate_id = int(rate_id)
            except (ValueError, TypeError):
                errors.append(f"ID inválido: {rate_id}")
                continue
                
            # Validar que el campo sea permitido
            if field not in ["cost", "sell", "sell_tourplan"]:
                errors.append(f"Campo no permitido: {field}")
                continue
            
            # Convertir el valor al tipo correcto
            try:
                if field == "cost":
                    # cost es FloatField
                    value = float(value) if value != "" else 0.0
                else:
                    # sell y sell_tourplan son PositiveIntegerField
                    value = int(float(value)) if value != "" else 0
            except (ValueError, TypeError):
                errors.append(f"Valor inválido para {field}: {value}")
                continue
            
            # Verificar que el Rate existe
            if not Rate.objects.filter(id=rate_id).exists():
                errors.append(f"Rate con ID {rate_id} no existe")
                continue
            
            # Actualizar
            updated = Rate.objects.filter(id=rate_id).update(**{field: value})
            updated_count += updated
        
        return JsonResponse({
            "ok": True, 
            "updated": updated_count,
            "errors": errors if errors else None,
            "message": f"Se actualizaron {updated_count} tarifas"
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            "ok": False, 
            "error": f"Error al parsear JSON: {str(e)}"
        }, status=400)
        
    except Exception as e:
        # Log del error completo para debugging
        import traceback
        print("Error completo:")
        print(traceback.format_exc())
        
        return JsonResponse({
            "ok": False, 
            "error": f"Error en el servidor: {str(e)}"
        }, status=500)