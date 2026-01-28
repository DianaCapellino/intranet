from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from tariff.models import Supplier, SupplierGroup, Product, ProductGroup, Location, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, HOTEL_QUALITY_OPTIONS
from intranet.models import Client
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from datetime import date

MARGIN_ACC_OPTIONS = [
    ("Low", "0.89"),
    ("Regular", "0.85"),
    ("High", "0.82"),
]

@login_required
def supplier(request):

    supplier_groups = SupplierGroup.objects.filter(type_service="AC")
    
    default_location = Location.objects.get(code="BUE")

    suppliers = Supplier.objects.filter(
        group__type_service="AC"
    ).prefetch_related("supplier_products")

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
                "supplier_groups": supplier_groups .order_by("location__name", "name"),
                "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
                "default_location": default_location,
            })

        group = SupplierGroup.objects.get(pk=group_form)
        
        existing_suppliers = Supplier.objects.filter(
            group=group
        ).order_by("order")

        last_group = existing_suppliers.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the supplier from the form information
        Supplier.objects.create(
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
            note=request.POST.get("note"),
            prepayment=request.POST.get("prepayment"),
            pic1_url=request.POST.get("pic1_url"),
            pic2_url=request.POST.get("pic2_url"),
            pic3_url=request.POST.get("pic3_url"),
        )

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
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
            "MARGIN_ACC_OPTIONS": MARGIN_ACC_OPTIONS,
            "default_location": default_location,      
        })

@login_required
def supplier_group(request):
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
        })

    else:
        return render(request, "tariff/accommodation/supplier_group.html", {
            "groups": SupplierGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
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
            recommended=False,
            shown=True,
            fcu="Group",
            scu=1,
            lw_date=today,
            order=order,
            group=group,
            pic1_url=request.POST.get("pic1_url"),
            pic2_url=request.POST.get("pic2_url"),
            pic3_url=request.POST.get("pic3_url"),
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
        })

    else:
        return render(request, "tariff/accommodation/product_group.html", {
            "groups": ProductGroup.objects.filter(type_service="AC"),
            "locations": Location.objects.all(),
        })
