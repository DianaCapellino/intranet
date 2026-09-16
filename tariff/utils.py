import math
from django.db.models import Q


def parse_optional_float(value):
    """Convierte un campo de formulario opcional (ej. latitude/longitude de Location) a float,
    o None si vino vacío/ausente/no numérico — para no reventar con un ValueError cuando el
    destino todavía no tiene coordenadas cargadas."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_pic_url(filename):
    """
    pic1_url/pic2_url/pic3_url de Location/Supplier/Product venían siendo un nombre de
    archivo suelto que alguien tipeaba a mano (ej. "bue1.jpg"), relativo a static/tariff/ —
    ahora que se suben como archivo real (ver save_pic_upload), quedan como una URL completa
    de MEDIA_ROOT en su lugar. Esta función resuelve CUALQUIERA de las dos formas, así las
    fotos viejas (nombre suelto) siguen andando exactamente igual sin necesidad de migrar
    datos, y las nuevas (URL completa) también — se usa tanto para mostrarlas (filtro de
    template) como en cualquier lugar que necesite la URL real a partir del valor guardado.
    """
    if not filename:
        return None
    if filename.startswith("http") or filename.startswith("/"):
        return filename
    from django.templatetags.static import static
    return static(f"tariff/{filename}")


def save_pic_upload(file, subfolder):
    """
    Guarda una foto subida (Location/Supplier/Product) en MEDIA_ROOT y devuelve su URL
    completa — mismo patrón ya usado por CarCategory (tariff/views/car_hire.py) e
    ItineraryLine (intranet/views_itinerary.py: entry_itinerary_upload_image), reutilizado acá
    para no reinventar el mecanismo de subida de fotos por tercera vez.
    """
    from django.core.files.storage import default_storage
    path = default_storage.save(f"tariff_photos/{subfolder}/{file.name}", file)
    return default_storage.url(path)


def get_ratelines_last_update(rateline_ids):
    """Returns {rateline_id: date} — the most recent Change (history) record
    date for each rate line. A rate line with no Change record (never went
    through a tracked create/update, or history was explicitly skipped) is
    simply absent from the dict."""
    from django.db.models import Max
    from tariff.models import Change
    rows = (
        Change.objects.filter(rate_line_id__in=list(rateline_ids))
        .values('rate_line_id')
        .annotate(last_date=Max('date'))
    )
    return {r['rate_line_id']: r['last_date'] for r in rows}


def get_suppliers_last_update(supplier_ids):
    """Returns {supplier_id: date} — the most recent Change (history) record
    date across all of that supplier's rate lines. A supplier with no tracked
    changes at all is absent from the dict."""
    from django.db.models import Max
    from tariff.models import Change
    rows = (
        Change.objects
        .filter(rate_line__group__product__supplier_id__in=list(supplier_ids))
        .values('rate_line__group__product__supplier_id')
        .annotate(last_date=Max('date'))
    )
    return {r['rate_line__group__product__supplier_id']: r['last_date'] for r in rows}


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
                amount = round(float(amount_val))
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