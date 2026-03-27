def admin_nav_counts(request):
    """Inject nav badge counts for admin users."""
    if not request.user.is_authenticated or not getattr(request.user, 'isAdmin', False):
        return {}

    from tariff.models import FeedbackInboxItem, Supplier
    pending_emails = FeedbackInboxItem.objects.filter(status='pendiente').count()
    pending_revised = Supplier.objects.filter(
        supplier_products__rate_products__group_rate__is_revised=False
    ).distinct().count()

    return {
        'nav_pending_emails': pending_emails,
        'nav_pending_revised': pending_revised,
    }
