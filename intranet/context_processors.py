def admin_nav_counts(request):
    """Inject nav badge counts.

    'Pendientes' (own open entries + own pending corrections) shows for any
    non-Cliente user — it's a personal count, not department-wide. Calidad and
    Tariff-revision stay admin-only, as before.
    """
    if not request.user.is_authenticated or request.user.userType == "Cliente":
        return {}

    from intranet.models import Entry
    from intranet.views import _my_revision_pending_count

    context = {
        'nav_pending_entries': Entry.objects.filter(
            user_working=request.user, isClosed=False,
        ).count(),
        'nav_pending_corrections': _my_revision_pending_count(request.user),
    }

    if getattr(request.user, 'isAdmin', False):
        from tariff.models import FeedbackInboxItem, Supplier
        context['nav_pending_emails'] = FeedbackInboxItem.objects.filter(status='pendiente').count()
        context['nav_pending_revised'] = Supplier.objects.filter(
            supplier_products__rate_products__group_rate__is_revised=False
        ).distinct().count()

    return context
