import math
from django.db.models import Q


_AMOUNT_QUERY = """
    SELECT
        BHD.FULL_REFERENCE AS tourplan_id,
        CASE BHD.STATUS WHEN 'HL' THEN 0 ELSE BSD.AGENT END AS amount
    FROM BHD
    JOIN BSD ON BSD.BHD_ID = BHD.BHD_ID AND BSD.BSL_ID = 0
    WHERE BHD.FULL_REFERENCE = %s
"""


def fill_missing_amounts_from_tourplan():
    """
    Find Quote/Booking entries without an amount and try to fill from Tourplan.

    Returns:
        updated        - list of Entry objects that were updated
        no_tourplan_id - list of Entry objects with no tourplanId (can't look up)
        not_found      - list of Entry objects whose tourplanId wasn't found in Tourplan
    """
    from intranet.models import Entry, Trip
    from intranet.utils import get_tourplan_connection

    entries_no_amount = (
        Entry.objects.filter(status__in=["Quote", "Booking"])
        .filter(Q(amount__isnull=True) | Q(amount=0))
        .select_related("trip")
    )

    no_tourplan_id = []
    updated = []
    not_found = []

    try:
        conn = get_tourplan_connection()
    except Exception as e:
        print(f"Error conectando a Tourplan: {e}")
        return updated, no_tourplan_id, not_found

    try:
        cur = conn.cursor()
        for entry in entries_no_amount:
            tp_id = (entry.tourplanId or "").strip()
            if not tp_id:
                # Fall back to the trip's tourplanId
                trip_tp_id = (entry.trip.tourplanId or "").strip() if entry.trip else ""
                if not trip_tp_id:
                    no_tourplan_id.append(entry)
                    continue
                tp_id = trip_tp_id

            cur.execute(_AMOUNT_QUERY, (tp_id,))
            row = cur.fetchone()

            if not row:
                not_found.append(entry)
                continue

            amount_val = row.get("amount")
            if not amount_val:
                not_found.append(entry)
                continue

            try:
                amount = int(float(amount_val))
            except (ValueError, TypeError):
                not_found.append(entry)
                continue

            entry.amount = amount
            entry.save(update_fields=["amount"])

            if entry.trip and not entry.trip.amount:
                entry.trip.amount = amount
                entry.trip.save(update_fields=["amount"])

            updated.append(entry)
    finally:
        conn.close()

    print(f"Actualizados: {len(updated)}")
    print(f"Sin tourplanId: {len(no_tourplan_id)}")
    if no_tourplan_id:
        for e in no_tourplan_id:
            print(f"  - {e.trip.name if e.trip else '?'} ({e.status})")
    print(f"No encontrados en Tourplan: {len(not_found)}")
    if not_found:
        for e in not_found:
            print(f"  - {e.trip.name if e.trip else '?'} ({e.status}) tourplanId={e.tourplanId!r}")

    return updated, no_tourplan_id, not_found


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