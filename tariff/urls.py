from django.urls import path
from tariff.views import tariff, modify, accommodation, service, car_hire

urlpatterns = [
    # General urls
    path("", tariff.index, name="tariff"),
    path("tp_mod_list", tariff.tp_mod_list, name="tp_mod_list"),
    path('search/', tariff.tariff_search, name='tariff_search'),
    path('hotel-comparison/', tariff.hotel_comparison, name='hotel_comparison'),
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
    path("modify/supplier/<int:supplier_id>/rates-summary/", modify.rates_summary_api, name="rates_summary_api"),
    path("changes/json/<int:change_id>", modify.json_changes, name="json_changes"),
    path("modify/supplier-group/json/<int:group_id>", modify.json_supplier_group, name="json_supplier_group"),
    path("modify/product-group/json/<int:group_id>", modify.json_product_group, name="json_product_group"),
    path("modify/update-rate-block/", modify.update_rate_block, name="update_rate_block"),
    path('modify/copy-rate-block/', modify.copy_rate_block, name='copy_rate_block'),
    path('modify/delete-rate-block/', modify.delete_rate_block, name='delete_rate_block'),
    path('modify/delete-rate-line/', modify.delete_rate_line, name='delete_rate_line'),
    path('modify/create-rate-block/', modify.create_rate_block, name='create_rate_block'),
    # Cost item / fixed rate cost management
    path('modify/cost-item/add/', modify.add_cost_item, name='add_cost_item'),
    path('modify/cost-item/update/', modify.update_cost_item, name='update_cost_item'),
    path('modify/cost-item/<int:item_id>/delete/', modify.delete_cost_item, name='delete_cost_item'),
    path('modify/fixed-rate-link/add/', modify.add_fixed_rate_link, name='add_fixed_rate_link'),
    path('modify/fixed-rate-cost/create/', modify.create_fixed_rate_cost, name='create_fixed_rate_cost'),
    path('modify/fixed-rate-link/remove/', modify.remove_fixed_rate_link, name='remove_fixed_rate_link'),
    path('modify/fixed-rate-cost/update/', modify.update_fixed_rate_cost, name='update_fixed_rate_cost'),
    path('modify/fixed-rate-cost/<int:frc_id>/delete/', modify.delete_fixed_rate_cost, name='delete_fixed_rate_cost'),
    path('modify/supplier/<int:supplier_id>/set-exchange/', modify.update_supplier_exchange, name='update_supplier_exchange'),
    path('modify/supplier/<int:supplier_id>/bulk-update-exchange/', modify.bulk_update_exchange, name='bulk_update_exchange'),
    path('modify/supplier/<int:supplier_id>/fix-group-fcu/', modify.fix_group_fcu, name='fix_group_fcu'),
    path('modify/rate/update-cost/', modify.update_rate_cost, name='update_rate_cost'),
    path('modify/rate/toggle-lock/', modify.toggle_rate_lock, name='toggle_rate_lock'),
    path('modify/rate/create-missing/', modify.create_missing_rate, name='create_missing_rate'),
    path('modify/rate/delete-single/', modify.delete_single_rate, name='delete_single_rate'),
    path('modify/suppliers/reorder/', modify.reorder_suppliers, name='reorder_suppliers'),
    path('modify/suppliers/auto-sort/', modify.auto_sort_suppliers, name='auto_sort_suppliers'),
    path('modify/supplier/<int:supplier_id>/sustainable-action/add/', modify.add_sustainable_action, name='add_sustainable_action'),
    path('modify/sustainable-action/<int:action_id>/delete/', modify.delete_sustainable_action, name='delete_sustainable_action'),

    path("aliwen-green/", tariff.aliwen_green, name="aliwen_green"),
    path("aliwen-green/excel/", tariff.aliwen_green_excel, name="aliwen_green_excel"),
    path("aliwen-green/ai-extract/", tariff.aliwen_green_ai_extract, name="aliwen_green_ai_extract"),
    path("aliwen-green/ai-save/", tariff.aliwen_green_ai_save, name="aliwen_green_ai_save"),
    path("aliwen-green/supplier-search/", tariff.aliwen_green_supplier_search, name="aliwen_green_supplier_search"),
    path("pdf/select/", tariff.pdf_select, name="pdf_select"),
    path("pdf/view/", tariff.pdf_view, name="pdf_view"),

    path("changes/data/", tariff.history_of_changes_data, name="history_of_changes_data"),
    path("changes/bulk-delete/", tariff.bulk_delete_changes, name="bulk_delete_changes"),
    path("tp/apply-changes/",  tariff.apply_changes,   name="apply_changes"),
    path("tp/discard-changes/", tariff.discard_changes, name="discard_changes"),
    path("tp/review/",          tariff.tp_mod_review,   name="tp_mod_review"),
    path("tp/toggle-update-tp/", tariff.toggle_supplier_update_tp, name="toggle_supplier_update_tp"),
    path("tp/upload-services/",  tariff.tp_mod_list_services,      name="tp_mod_list_services"),
    path("tp/sync-db-accommodation/", tariff.sync_tariff_from_db_accommodation, name="sync_tariff_from_db_accommodation"),
    path("tp/sync-db-services/",      tariff.sync_tariff_from_db_services,      name="sync_tariff_from_db_services"),
    path("tp/quick-sync/<int:supplier_id>/", tariff.quick_sync_supplier, name="quick_sync_supplier"),
    path("rateline/<int:line_id>/mark-revised/",   tariff.mark_rate_line_revised,   name="mark_rate_line_revised"),
    path("rateline/<int:line_id>/mark-unrevised/", tariff.mark_rate_line_unrevised, name="mark_rate_line_unrevised"),

    # Car hire urls
    path("modify/car-hire", car_hire.destinations, name="car_hire_destinations"),
    path("modify/car-hire/config/", car_hire.update_config, name="car_hire_update_config"),
 
    path("modify/car-hire/category/create/", car_hire.category_create, name="car_hire_category_create"),
    path("modify/car-hire/category/<int:category_id>/delete/", car_hire.category_delete, name="car_hire_category_delete"),
    path("modify/car-hire/category/<int:category_id>/update-pct/", car_hire.category_update_pct, name="car_hire_category_update_pct"),
    path("modify/car-hire/category/<int:category_id>/rates/", car_hire.category_rates, name="car_hire_category_rates"),
 
    path("modify/car-hire/rate-block/create/", car_hire.create_rate_block, name="car_hire_create_rate_block"),
    path("modify/car-hire/rate-block/delete/", car_hire.delete_rate_block, name="car_hire_delete_rate_block"),
    path("modify/car-hire/rate/update/", car_hire.update_rate, name="car_hire_update_rate"),
    path("modify/car-hire/extra/update/", car_hire.update_extra, name="car_hire_update_extra"),
    path("modify/car-hire/extra/reset-auto/", car_hire.reset_extra_auto, name="car_hire_reset_extra_auto"),
 
    path("modify/car-hire/fixed-cost/create/", car_hire.create_fixed_cost, name="car_hire_create_fixed_cost"),
    path("modify/car-hire/fixed-cost/update/", car_hire.update_fixed_cost, name="car_hire_update_fixed_cost"),
    path("modify/car-hire/fixed-cost/<int:frc_id>/delete/", car_hire.delete_fixed_cost, name="car_hire_delete_fixed_cost"),

    # Destination rates page
    path("modify/car-hire/destination/<int:location_id>/rates/", car_hire.destination_rates, name="car_hire_destination_rates"),
    path("modify/car-hire/destination/block/create/", car_hire.create_destination_block, name="car_hire_create_destination_block"),
    path("modify/car-hire/destination/category-rate/create/", car_hire.create_category_rate_in_block, name="car_hire_create_category_rate_in_block"),
    path("modify/car-hire/destination/block/delete/", car_hire.delete_destination_block, name="car_hire_delete_destination_block"),
    path("modify/car-hire/destination/block/currency/", car_hire.update_block_currency, name="car_hire_update_block_currency"),
    path("modify/car-hire/destination/block/increase/", car_hire.update_block_increase, name="car_hire_update_block_increase"),

    # Vehicle model editing
    path("modify/car-hire/model/update/", car_hire.category_update_model, name="car_hire_category_update_model"),

    # Cotizador online
    path("car-hire/quoter/", car_hire.quoter_page, name="car_hire_quoter"),
    path("car-hire/quoter/calculate/", car_hire.quoter_calculate, name="car_hire_quoter_calculate"),
    path("car-hire/quoter/list-categories/", car_hire.quoter_list_categories, name="car_hire_quoter_list_categories"),
    path("car-hire/quoter/parse-email/", car_hire.quoter_parse_email, name="car_hire_quoter_parse_email"),
    path("car-hire/quoter/category-info/", car_hire.quoter_category_info, name="car_hire_quoter_category_info"),

]