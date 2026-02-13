from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from tariff.models import Supplier, Client, SupplierGroup, Product, ProductGroup, Location, RateLine, Rate, RateGroup, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, HOTEL_QUALITY_OPTIONS, FCU_OPTIONS
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
        .prefetch_related("line_rates")
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

            # Calcular márgenes para cada rate
            if line.sgl:
                if line.sgl.cost > 0 and line.sgl.sell_tourplan > 0:
                    line.sgl.margin_tp = ((line.sgl.sell_tourplan - line.sgl.cost) / line.sgl.sell_tourplan) * 100
                else:
                    line.sgl.margin_tp = 0
                
                if line.sgl.cost > 0 and line.sgl.sell > 0:
                    line.sgl.margin_ai = ((line.sgl.sell - line.sgl.cost) / line.sgl.sell) * 100
                else:
                    line.sgl.margin_ai = 0
            
            if line.dbl:
                if line.dbl.cost > 0 and line.dbl.sell_tourplan > 0:
                    line.dbl.margin_tp = ((line.dbl.sell_tourplan - line.dbl.cost) / line.dbl.sell_tourplan) * 100
                else:
                    line.dbl.margin_tp = 0
                
                if line.dbl.cost > 0 and line.dbl.sell > 0:
                    line.dbl.margin_ai = ((line.dbl.sell - line.dbl.cost) / line.dbl.sell) * 100
                else:
                    line.dbl.margin_ai = 0
            
            if line.tpl:
                if line.tpl.cost > 0 and line.tpl.sell_tourplan > 0:
                    line.tpl.margin_tp = ((line.tpl.sell_tourplan - line.tpl.cost) / line.tpl.sell_tourplan) * 100
                else:
                    line.tpl.margin_tp = 0
                
                if line.tpl.cost > 0 and line.tpl.sell > 0:
                    line.tpl.margin_ai = ((line.tpl.sell - line.tpl.cost) / line.tpl.sell) * 100
                else:
                    line.tpl.margin_ai = 0
    else:
        for line in rate_lines:
            line.one = None
            line.two = None
            line.three = None
            line.four = None
            line.five = None
            line.six = None

            for rate in line.line_rates.all():
                if rate.column_options == "1":
                    line.one = rate
                elif rate.column_options == "2":
                    line.two = rate
                elif rate.column_options == "3":
                    line.three = rate
                elif rate.column_options == "4":
                    line.four = rate
                elif rate.column_options == "5":
                    line.five = rate
                elif rate.column_options == "6":
                    line.six = rate

            # Calcular márgenes para cada rate
            if line.one:
                if line.one.cost > 0 and line.one.sell_tourplan > 0:
                    line.one.margin_tp = ((line.one.sell_tourplan - line.one.cost) / line.one.sell_tourplan) * 100
                else:
                    line.one.margin_tp = 0
                
                if line.one.cost > 0 and line.one.sell > 0:
                    line.one.margin_ai = ((line.one.sell - line.one.cost) / line.one.sell) * 100
                else:
                    line.one.margin_ai = 0
            
            if line.two:
                if line.two.cost > 0 and line.two.sell_tourplan > 0:
                    line.two.margin_tp = ((line.two.sell_tourplan - line.dtwobl.cost) / line.two.sell_tourplan) * 100
                else:
                    line.two.margin_tp = 0
                
                if line.two.cost > 0 and line.two.sell > 0:
                    line.two.margin_ai = ((line.two.sell - line.two.cost) / line.two.sell) * 100
                else:
                    line.two.margin_ai = 0
            
            if line.three:
                if line.three.cost > 0 and line.three.sell_tourplan > 0:
                    line.three.margin_tp = ((line.three.sell_tourplan - line.three.cost) / line.three.sell_tourplan) * 100
                else:
                    line.three.margin_tp = 0
                
                if line.three.cost > 0 and line.three.sell > 0:
                    line.three.margin_ai = ((line.three.sell - line.three.cost) / line.three.sell) * 100
                else:
                    line.three.margin_ai = 0

            if line.four:
                if line.four.cost > 0 and line.four.sell_tourplan > 0:
                    line.four.margin_tp = ((line.four.sell_tourplan - line.four.cost) / line.four.sell_tourplan) * 100
                else:
                    line.four.margin_tp = 0
                
                if line.four.cost > 0 and line.four.sell > 0:
                    line.four.margin_ai = ((line.four.sell - line.four.cost) / line.four.sell) * 100
                else:
                    line.four.margin_ai = 0

            if line.five:
                if line.five.cost > 0 and line.five.sell_tourplan > 0:
                    line.five.margin_tp = ((line.five.sell_tourplan - line.five.cost) / line.five.sell_tourplan) * 100
                else:
                    line.five.margin_tp = 0
                
                if line.five.cost > 0 and line.five.sell > 0:
                    line.five.margin_ai = ((line.five.sell - line.five.cost) / line.five.sell) * 100
                else:
                    line.five.margin_ai = 0

            if line.six:
                if line.six.cost > 0 and line.six.sell_tourplan > 0:
                    line.six.margin_tp = ((line.six.sell_tourplan - line.six.cost) / line.six.sell_tourplan) * 100
                else:
                    line.six.margin_tp = 0
                
                if line.six.cost > 0 and line.six.sell > 0:
                    line.six.margin_ai = ((line.six.sell - line.six.cost) / line.six.sell) * 100
                else:
                    line.six.margin_ai = 0

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
                    text_value=original_rate.text_value
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
                # Crear un RateGroup por defecto si no existe

                if product.group.type_service == "AC":
                    name = "Breakfast included"
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

                # Crear Rates para SGL, DBL, TPL
                for column_type in columns:
                    cost = 0
                    
                    Rate.objects.create(
                        rate_line=new_rateline,
                        status=status,
                        increase=increase,
                        cost=cost,
                        margin=margin,
                        sell=0,
                        sell_tourplan=0,
                        column_options=column_type,
                        has_rate=True,
                        text_value=None
                    )
                    created_rates += 1
                
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