import math
from django.db.models import Q


MARGIN_INFO_MAP = {
    0.89: "Low",
    0.85: "Regular",
    0.82: "High",
}


def sync_supplier_margin_info(dry_run=False):
    """
    Update margin_info for all AC suppliers based on their margin value.

    Mapping:  0.89 → Low  |  0.85 → Regular  |  0.82 → High

    Usage from Django shell:
        from tariff.utils import sync_supplier_margin_info
        sync_supplier_margin_info()          # applies changes
        sync_supplier_margin_info(dry_run=True)  # preview only
    """
    from tariff.models import Supplier

    suppliers = Supplier.objects.filter(group__type_service="AC").select_related("group")

    updated = []
    skipped = []

    for s in suppliers:
        new_info = MARGIN_INFO_MAP.get(s.margin)
        if new_info is None:
            skipped.append(f"  SKIP  {s.name!r:40s} margin={s.margin} (unknown value)")
            continue
        if s.margin_info == new_info:
            continue
        updated.append((s, new_info))

    print(f"Suppliers to update : {len(updated)}")
    print(f"Suppliers skipped   : {len(skipped)}")

    for s, new_info in updated:
        print(f"  {'(dry-run) ' if dry_run else ''}UPDATE {s.name!r:40s} {s.margin_info!r} → {new_info!r}")
        if not dry_run:
            s.margin_info = new_info
            s.save(update_fields=["margin_info"])

    if skipped:
        print("\nSkipped (margin value not in map):")
        for msg in skipped:
            print(msg)

    if not dry_run:
        print(f"\nDone — {len(updated)} record(s) updated.")

def fix_rates_status_and_margin(dry_run=False):
    """
    Fix all Rate records that have an empty status or empty margin.

    - status: sets to "Confirmed" when blank/null
    - margin:  sets to the supplier's margin_info when blank/null

    Usage from Django shell:
        from tariff.utils import fix_rates_status_and_margin
        fix_rates_status_and_margin()             # applies changes
        fix_rates_status_and_margin(dry_run=True) # preview only
    """
    from tariff.models import Rate

    VALID_STATUS = {"Confirmed", "Provisional"}
    VALID_MARGIN = {"High", "Regular", "Low"}

    rates = Rate.objects.select_related(
        "rate_line__group__product__supplier"
    ).exclude(status__in=VALID_STATUS, margin__in=VALID_MARGIN)

    updated_status = 0
    updated_margin = 0
    skipped_margin = 0

    for rate in rates:
        fields = []
        changed = []

        if rate.status not in VALID_STATUS:
            changed.append(f"status '{rate.status}' → 'Confirmed'")
            rate.status = "Confirmed"
            fields.append("status")

        if rate.margin not in VALID_MARGIN:
            try:
                supplier_margin = rate.rate_line.group.product.supplier.margin_info
            except Exception:
                supplier_margin = ""

            if supplier_margin:
                rate.margin = supplier_margin
                fields.append("margin")
                changed.append(f"margin → '{supplier_margin}'")
            else:
                skipped_margin += 1
                changed.append("margin SKIPPED (supplier has no margin_info)")

        if fields:
            print(f"  {'(dry-run) ' if dry_run else ''}Rate #{rate.pk:6d} — {', '.join(changed)}")
            if not dry_run:
                rate.save(update_fields=fields)
            if "status" in fields:
                updated_status += 1
            if "margin" in fields:
                updated_margin += 1

    print(f"\nStatus fixed : {updated_status}")
    print(f"Margin fixed : {updated_margin}")
    if skipped_margin:
        print(f"Margin skipped (no supplier margin_info): {skipped_margin}")
    if not dry_run:
        print("Done.")


def apply_client_margin(rate, client_category, service_type):
    sell = rate.sell

    if client_category == "C":
        return sell

    if service_type == "AC":
        if rate.margin == "Regular":
            if client_category == "B":
                sell *= 1.0366
            elif client_category == "A":
                sell *= 1.0625
        elif rate.margin == "High":
            if client_category in ("A", "B"):
                sell *= 1.025

    elif service_type == "NA":
        if rate.margin == "Regular":
            if client_category == "B":
                sell *= 1.03
            elif client_category == "A":
                sell *= 1.06

    return math.ceil(sell)