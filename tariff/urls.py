from django.urls import path
from tariff.views import tariff, modify, accommodation, service

urlpatterns = [
    # General urls
    path("", tariff.index, name="tariff"),
    path("tp_mod_list", tariff.tp_mod_list, name="tp_mod_list"),
    path('search/', tariff.tariff_search, name='tariff_search'),
    path('special_dates', tariff.special_dates, name='special_dates'),
    path('download_holidays_pdf/<int:year>', tariff.download_holidays_pdf, name='download_holidays_pdf'),
    path('history_of_changes', tariff.history_of_changes, name="history_of_changes"),
    path("export/services/excel/", tariff.export_services_excel, name="export_services_excel"),
    
    # Urls for tariff management
    path("modify", modify.modify_tariff, name="modify_tariff"),
    path("modify/accommodation", modify.accommodation, name="accommodation"),
    path("modify/service", modify.service, name="service"),    
    path("modify/locations", modify.locations, name="locations"),

    # Urls for accommodation management
    path("modify/acc_supplier", accommodation.supplier, name="acc_supplier"),
    path("modify/acc_supplier_group", accommodation.supplier_group, name="acc_supplier_group"),
    path("modify/acc_product/<int:supplier_id>", accommodation.product, name="acc_product"),
    path("modify/acc_product_group", accommodation.product_group, name="acc_product_group"),

    # Urls for service management
    path("modify/svs_supplier", service.supplier, name="svs_supplier"),
    path("modify/svs_product/<int:supplier_id>", service.product, name="svs_product"),
    path("modify/svs_product_group", service.product_group, name="svs_product_group"),
    
    # Urls for tariff changes
    path("modify/locations/modify/<int:location_id>", modify.modify_location, name="modify_location"),
    path("modify/suppliers/modify/<int:supplier_id>", modify.modify_supplier, name="modify_supplier"),
    path("modify/products/modify/<int:product_id>", modify.modify_product, name="modify_product"),
    path("modify/supplier/<int:supplier_id>/rates/", modify.modify_supplier_rates, name="modify_supplier_rates"),
    path("modify/supplier_group/modify/<int:group_id>", modify.modify_supplier_group, name="modify_supplier_group"),
    path("modify/product_group/modify/<int:group_id>", modify.modify_product_group, name="modify_product_group"),
    path("changes/<int:change_id>/modify/", modify.modify_change, name="modify_change"),

    path("report_error/hotel/<int:supplier_id>", tariff.report_error_hotel, name="report_error_tariff_hotel"),
    path("report_error/service/<int:product_id>", tariff.report_error_service, name="report_error_tariff_service"),

    # Json urls
    path("modify/location/json/<int:location_id>", modify.json_location, name="json_location"),
    path("modify/supplier/json/<int:supplier_id>", modify.json_supplier, name="json_supplier"),
    path("changes/json/<int:change_id>", modify.json_changes, name="json_changes"),
    path("modify/supplier-group/json/<int:group_id>", modify.json_supplier_group, name="json_supplier_group"),
    path("modify/product-group/json/<int:group_id>", modify.json_product_group, name="json_product_group"),
    path("modify/update-rate-block/", modify.update_rate_block, name="update_rate_block"),
    path('modify/copy-rate-block/', modify.copy_rate_block, name='copy_rate_block'),
    path('modify/delete-rate-block/', modify.delete_rate_block, name='delete_rate_block'),
    path('modify/create-rate-block/', modify.create_rate_block, name='create_rate_block'),
    path("changes/data/", tariff.history_of_changes_data, name="history_of_changes_data"),
    path("tp/apply-changes/",  tariff.apply_changes,   name="apply_changes"),
    path("tp/discard-changes/", tariff.discard_changes, name="discard_changes"),
]