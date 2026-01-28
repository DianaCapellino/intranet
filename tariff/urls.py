from django.urls import path
from tariff.views import tariff, modify, accommodation

urlpatterns = [
    # General urls
    path("", tariff.index, name="tariff"),
    path("tp_mod_list", tariff.tp_mod_list, name="tp_mod_list"),
    path('search/', tariff.tariff_search, name='tariff_search'),
    path("toggle-costs/", tariff.toggle_costs, name="toggle_costs"),

    # Urls for tariff management
    path("modify", modify.modify_tariff, name="modify_tariff"),
    path("modify/accommodation", modify.accommodation, name="accommodation"),
    path("modify/locations", modify.locations, name="locations"),
    path("modify/acc_supplier", accommodation.supplier, name="acc_supplier"),
    path("modify/acc_supplier_group", accommodation.supplier_group, name="acc_supplier_group"),
    path("modify/acc_product/<int:supplier_id>", accommodation.product, name="acc_product"),
    path("modify/acc_product_group", accommodation.product_group, name="acc_product_group"),

    # Urls for tariff changes
    path("modify/locations/modify/<int:location_id>", modify.modify_location, name="modify_location"),
    path("modify/suppliers/modify/<int:supplier_id>", modify.modify_supplier, name="modify_supplier"),
    path("modify/products/modify/<int:product_id>", modify.modify_product, name="modify_product"),
    path("modify/supplier/<int:supplier_id>/rates/", modify.modify_supplier_rates, name="modify_supplier_rates"),
    path("modify/supplier_group/modify/<int:group_id>", modify.modify_supplier_group, name="modify_supplier_group"),
    path("modify/product_group/modify/<int:group_id>", modify.modify_product_group, name="modify_product_group"),

    # Json urls
    path("modify/location/json/<int:location_id>", modify.json_location, name="json_location"),
    path("modify/supplier/json/<int:supplier_id>", modify.json_supplier, name="json_supplier"),
    path("modify/supplier-group/json/<int:group_id>", modify.json_supplier_group, name="json_supplier_group"),
    path("modify/product-group/json/<int:group_id>", modify.json_product_group, name="json_product_group"),
    path("modify/update-rate-block/", modify.update_rate_block, name="update_rate_block"),
]