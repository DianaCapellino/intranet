from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from tariff.models import Supplier, SupplierGroup, Product, ProductGroup, Location, ATTRACTIONS, CHILDREN_RANKING_OPTIONS, DISABLED_RANKING_OPTIONS, SUSTENTABILITY_RANKING_OPTIONS, INTERESTS, TOURS_TIMING
from intranet.models import Client
from django.http import HttpResponseRedirect
from django.urls import reverse
from datetime import date

MARGIN_SVS_OPTIONS = [
    ("Low", "0.86"),
    ("Regular", "0.8"),
    ("High", "0.7"),
]

@login_required
def supplier(request):

    product_groups = ProductGroup.objects.filter(type_service="NA")

    suppliers = Supplier.objects.filter(
        group__type_service="NA"
    ).prefetch_related("supplier_products")

    if request.method == "POST":

        # Get the information from the form
        code = request.POST["code"].upper()
        name = request.POST["name"]
        margin = request.POST["margin"]
        location_id = request.POST["location"]

        # Validations
        if not name or not code or not margin or not location_id:
            return render(request, "tariff/service/supplier.html", {
                "suppliers": suppliers,
                "locations": Location.objects.all(),
                "products": Product.objects.filter(type_service="NA"),
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "product_groups": product_groups .order_by("location__name", "name"),
                "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
            })

        location = Location.objects.get(pk=location_id)

        try:
            group = SupplierGroup.objects.get(location=location, name="Unique")
        except SupplierGroup.DoesNotExist:
            group = SupplierGroup.objects.create(
                name="Unique",
                location=location,
                order=1,
                type_service="NA",
            )
        
        existing_suppliers = Supplier.objects.filter(
            group=group
        ).order_by("order")

        last_group = existing_suppliers.last()

        order = (last_group.order + 5) if last_group else 1

        # Creates the model of the supplier from the form information
        Supplier.objects.create(
            name=name,
            code=code,
            group=group,
            order=order,
            children_ranking=1,
            disabled_ranking=1,
            sustentability_ranking=1,
            attractions=request.POST.getlist("attractions"),
            interests=request.POST.getlist("interests"),
            margin=margin,
            note=request.POST.get("note"),
            pic1_url=request.POST.get("pic1_url"),
            pic2_url=request.POST.get("pic2_url"),
            pic3_url=request.POST.get("pic3_url"),
        )

        return HttpResponseRedirect(reverse("svs_supplier"), {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="NA"),
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "product_groups": product_groups .order_by("location__name", "name"),
            "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
        })

    else:

        return render(request, "tariff/service/supplier.html", {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="NA"),
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "product_groups": product_groups .order_by("location__name", "name"),
            "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
        })


@login_required
def product(request, supplier_id):

    supplier = Supplier.objects.get(pk=supplier_id)

    supplier_groups = SupplierGroup.objects.filter(type_service="NA")
    product_groups = ProductGroup.objects.filter(location=supplier.group.location)
    product_groups = product_groups.filter(type_service="NA")

    default_location = Location.objects.get(code="BUE")

    suppliers = Supplier.objects.filter(
        group__type_service="NA"
    ).prefetch_related("supplier_products")

    if request.method == "POST":

        today = date.today()
        
        # Get the information from the form
        code = request.POST["code"].upper()
        name = request.POST["name"]
        group_form = request.POST["group"]

        # Validations
        if not name or not code or not group_form:
            return render(request, "tariff/service/product.html", {
                "suppliers": suppliers,
                "locations": Location.objects.all(),
                "products": Product.objects.filter(type_service="AC"),
                "supplier_groups": supplier_groups.order_by("location__name", "name"),
                "product_groups": product_groups,
                "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
                "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
                "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
                "ATTRACTIONS": ATTRACTIONS,
                "INTERESTS": INTERESTS,
                "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
                "tours_timing": TOURS_TIMING,
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
            tour_timing=request.POST["timing"],
            supplier=supplier,
            children_ranking=supplier.children_ranking,
            disabled_ranking=supplier.disabled_ranking,
            sustentability_ranking=supplier.sustentability_ranking,
            attractions=request.POST.getlist("attractions"),
            interests=request.POST.getlist("interests"),
            note=request.POST.get("note"),
            type_service="NA",
            recommended=False,
            shown=True,
            fcu="Person",
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

        return render(request, "tariff/service/supplier.html", {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="NA"),
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "product_groups": product_groups .order_by("location__name", "name"),
            "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
            "default_location": default_location,     
        })

    else:

        return render(request, "tariff/service/product.html", {
            "suppliers": suppliers,
            "locations": Location.objects.all(),
            "products": Product.objects.filter(type_service="AC"),
            "supplier_groups": supplier_groups .order_by("location__name", "name"),
            "product_groups": product_groups,
            "CHILDREN_RANKING_OPTIONS": CHILDREN_RANKING_OPTIONS,
            "DISABLED_RANKING_OPTIONS": DISABLED_RANKING_OPTIONS,
            "SUSTENTABILITY_RANKING_OPTIONS": SUSTENTABILITY_RANKING_OPTIONS,
            "ATTRACTIONS": ATTRACTIONS,
            "INTERESTS": INTERESTS,
            "MARGIN_SVS_OPTIONS": MARGIN_SVS_OPTIONS,
            "tours_timing": TOURS_TIMING,
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
            return render(request, "tariff/service/product_group.html", {
                "message": "Todos los campos deben ser completados",
                "groups": ProductGroup.objects.filter(type_service="NA"),
                "locations": Location.objects.all(),
            })

        location = Location.objects.get(id=location_form)

        existing_groups = ProductGroup.objects.filter(
            type_service="NA",
            location=location
        ).order_by("order")

        last_group = existing_groups.last()

        order = (last_group.order + 5) if last_group else 1
        
        # Creates the model of the group from the form information
        new_group = ProductGroup.objects.create(
            name=name,
            location=location,
            order=order,
            type_service="NA",
        )
        new_group.save()

        return render(request, "tariff/service/product_group.html", {
            "groups": ProductGroup.objects.filter(type_service="NA"),
            "locations": Location.objects.all(),
        })

    else:
        return render(request, "tariff/service/product_group.html", {
            "groups": ProductGroup.objects.filter(type_service="NA"),
            "locations": Location.objects.all(),
        })