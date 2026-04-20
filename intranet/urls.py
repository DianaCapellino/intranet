from django.urls import path
from . import views

urlpatterns = [
    # General paths
    path("",views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("error", views.error, name="error"),
    path("entries", views.pendings, name="entries"),
    path("stats", views.stats, name="stats"),
    path("holidays", views.holidays, name="holidays"),

    # Paths for creating items
    path("countries", views.create_country, name="countries"),
    path("clients", views.create_client, name="clients"),
    path("contacts", views.create_client_contact, name="contacts"),
    path("users", views.create_user, name="users"),
    path("trips", views.create_trip, name="trips"),
    path("trips/clean", views.clean_search, name="clean_search"),
    path("create_entry/<int:trip_id>", views.create_entry, name="create_entry"),
    path("create_note/<int:trip_id>", views.create_note, name="create_note"),
    path("create_feedback/<int:trip_id>", views.create_feedback, name="create_feedback"),

    # Paths for modifying items
    path("modify_user/<int:user_id>", views.modify_user, name="modify_user"),
    path("change_password/<int:user_id>", views.change_password_user, name="change_password_user"),
    path("modify_country/<int:country_id>", views.modify_country, name="modify_country"),
    path("modify_client/<int:client_id>", views.modify_client, name="modify_client"),
    path("modify_contact/<int:contact_id>", views.modify_contact, name="modify_contact"),
    path("modify_trip/<int:trip_id>", views.modify_trip, name="modify_trip"),
    path("modify_entry/<int:entry_id>", views.modify_entry, name="modify_entry"),

    # API routes trips and entries
    path("trips/json", views.jsontrips, name="jsontrips"),
    path("trips/json/<int:trip_id>", views.jsontrip, name="jsontrip"),
    path("entries_trip/json/<int:trip_id>", views.jsontrip_entries, name="jsontrip_entries"),
    path("notes_trip/json/<int:trip_id>", views.jsontrip_notes, name="jsontrip_notes"),
    path("entries/json/<int:entry_id>", views.json_entry, name="json_entry"),
    path("entries/data/", views.entries_data, name="entries_data"),
    path("entries/json/pendings", views.json_pendings, name="json_pendings"),
    path("entries/json/last_entry", views.json_last_entry, name="json_last_entry"),
    path("stats/data/", views.stats_data, name="stats_data"),   
    path("stats/data/entries/presentation/", views.stats_presentation_entries, name="stats_presentation_entries"),
    path("stats/data/trips/presentation/", views.stats_presentation_trips, name="stats_presentation_trips"),

    # API routes for configurations
    path("countries/json/<int:country_id>", views.jsoncountry, name="jsoncountry"),
    path("clients/json/<int:client_id>", views.jsonclient, name="jsonclient"),
    path("contacts/json/<int:contact_id>", views.jsoncontact, name="jsoncontact"),
    path("users/json/<int:user_id>", views.jsonuser, name="jsonuser"),
    path("countries/json", views.json_countries, name="json_countries"),
    path("clients/json", views.json_clients, name="json_clients"),
    path("contacts/json", views.json_contacts, name="json_contacts"),
    path("users/json", views.json_users, name="json_users"),
    path("entries/json", views.json_entries, name="json_entries"),
    path("holidays/json", views.json_holidays, name="json_holidays"),

    # Other paths for views
    path("read_emails", views.read_emails, name="read_emails"),
    path("tourplan_files", views.tourplan_files, name="tourplan_files"),
    path("tourplan_files/create", views.tourplan_create_trips, name="tourplan_create_trips"),
    path("tourplan_files/discard", views.tourplan_discard_trips, name="tourplan_discard_trips"),
    path("tourplan_files/assign", views.tourplan_assign_tp, name="tourplan_assign_tp"),
    path("intranet_files", views.intranet_files, name="intranet_files"),
    path("advanced_search", views.advanced_search, name="advanced_search"),
    path("stats/entries/", views.stats_entries_report, name="stats_entries_report"),
    path("stats/trips/", views.stats_trips_report, name="stats_trips_report"),

    # Email processor
    path("email_processor", views.email_processor, name="email_processor"),
    path("email_processor/create", views.email_processor_create, name="email_processor_create"),
    path("email_processor/archive", views.email_processor_archive, name="email_processor_archive"),
    path("email_processor/search_trips", views.email_processor_search_trips, name="email_processor_search_trips"),

    # Trip filter
    path("filter_trips", views.trip_filter, name="trip_filter"),
    path("filter_trips/clients", views.trip_filter_clients, name="trip_filter_clients"),
    path("filter_trips/results", views.trip_filter_results, name="trip_filter_results"),

    # Margin management
    path("margin_management", views.margin_management, name="margin_management"),
    path("margin_management/review/<int:trip_id>", views.margin_review_trip, name="margin_review_trip"),
    path("margin_management/ignore/<int:trip_id>", views.margin_ignore_trip, name="margin_ignore_trip"),

    # Calidad
    path("calidad", views.calidad, name="calidad"),
    path("calidad/fetch_inbox", views.calidad_fetch_inbox, name="calidad_fetch_inbox"),
    path("calidad/upload_itinerario", views.calidad_upload_itinerario, name="calidad_upload_itinerario"),
    path("calidad/inbox/<int:item_id>/discard", views.calidad_discard_inbox, name="calidad_discard_inbox"),
    path("calidad/inbox/<int:item_id>/process", views.calidad_process_ai, name="calidad_process_ai"),
    path("calidad/inbox/<int:item_id>/confirm", views.calidad_confirm_inbox, name="calidad_confirm_inbox"),
    # Provisional supplier
    path("calidad/suppliers/create", views.calidad_create_supplier, name="calidad_create_supplier"),
    path("calidad/suppliers/resolve", views.calidad_resolve_provisional, name="calidad_resolve_provisional"),
    # Search endpoints for target selection
    path("calidad/feedbacks/by_target", views.calidad_feedbacks_by_target, name="calidad_feedbacks_by_target"),
    path("calidad/search/suppliers", views.calidad_search_suppliers, name="calidad_search_suppliers"),
    path("calidad/search/users", views.calidad_search_users, name="calidad_search_users"),
    path("calidad/search/guides", views.calidad_search_guides, name="calidad_search_guides"),
    path("calidad/search/dhs", views.calidad_search_dhs, name="calidad_search_dhs"),
    path("calidad/search/entities", views.calidad_search_entities, name="calidad_search_entities"),
    # Guide / DH create & delete
    path("calidad/guides/create", views.calidad_create_guide, name="calidad_create_guide"),
    path("calidad/guides/<int:guide_id>/delete", views.calidad_delete_guide, name="calidad_delete_guide"),
    path("calidad/guides/<int:guide_id>/edit", views.calidad_edit_guide, name="calidad_edit_guide"),
    path("calidad/dhs/create", views.calidad_create_dh, name="calidad_create_dh"),
    path("calidad/dhs/<int:dh_id>/delete", views.calidad_delete_dh, name="calidad_delete_dh"),
    path("calidad/dhs/<int:dh_id>/edit", views.calidad_edit_dh, name="calidad_edit_dh"),
    # FeedbackEntity CRUD
    path("calidad/entities", views.calidad_entities, name="calidad_entities"),
    path("calidad/entities/<int:entity_id>/edit",   views.calidad_edit_entity,   name="calidad_edit_entity"),
    path("calidad/entities/<int:entity_id>/delete", views.calidad_entity_delete, name="calidad_entity_delete"),

    # Feedback edit / delete
    path("calidad/feedbacks/<int:feedback_id>/edit",   views.calidad_edit_feedback,   name="calidad_edit_feedback"),
    path("calidad/feedbacks/<int:feedback_id>/delete", views.calidad_delete_feedback, name="calidad_delete_feedback"),

]