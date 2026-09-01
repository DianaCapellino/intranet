"""
Itinerario público por Entry: editor (staff, login requerido) + vista pública (sin login,
por token UUID). El contenido es un snapshot editable armado una vez desde Tourplan
(reusando fetch_itinerary_from_tourplan del módulo de Calidad) y después vive en la base
de la app — no se re-consulta Tourplan en cada visita al link público.
"""

import base64
import hashlib
import json
import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from .models import Entry, PublicItinerary, ItineraryDay, ItineraryLine, DEFAULT_ITINERARY_INTRO_TEXT
from .utils import strip_html
from tariff.models import Product, Supplier
from tariff.quality_ai import fetch_itinerary_from_tourplan

_log = logging.getLogger(__name__)

# service_code (OPT.SERVICE / Product_service) -> (label, ícono FontAwesome).
# El contenido que ve el cliente en el itinerario público va en inglés (por ahora, un solo
# idioma) — estas labels son client-facing, así que quedan en inglés aunque el resto de la
# intranet (staff) esté en español.
SERVICE_LABELS = {
    "AC": ("Accommodation", "fa-bed"),
    "FB": ("Meals", "fa-utensils"),
    "GU": ("Guide", "fa-user-tie"),
    "TF": ("Transfer", "fa-shuttle-van"),
    "TR": ("Transportation", "fa-bus"),
    "EN": ("Entrance", "fa-ticket"),
    "EX": ("Excursion", "fa-person-hiking"),
    "CI": ("Car Rental", "fa-car"),
    "IM": ("Tax", "fa-file-invoice-dollar"),
    "WE": ("Welcome", "fa-hand-holding-heart"),
    "FT": ("Flight", "fa-plane"),
    "IN": ("Not Included", "fa-circle-info"),
}
DEFAULT_SERVICE_LABEL = ("Service", "fa-map-pin")

# service_code -> bucket visual (icono/color de fondo) para la vista pública, agrupando los
# 12 códigos de SERVICE_LABELS en las 6 categorías de color del diseño de referencia.
SERVICE_TYPE_BUCKET = {
    "AC": "hotel",
    "TF": "transfer", "TR": "transfer", "CI": "transfer",
    "EX": "excursion", "EN": "excursion", "GU": "excursion",
    "FB": "meal", "WE": "meal",
    "IM": "fee", "IN": "fee",
    "FT": "flight",
}
DEFAULT_SERVICE_TYPE_BUCKET = "fee"

# Contexto vacío para el <template> de línea clonable por JS ("Agregar ítem"): un dict con
# todas las claves presentes (en vez de None) para que el include no falle al resolver
# `line.campo` como argumento de un filtro (Django no atrapa VariableDoesNotExist ahí).
EMPTY_LINE_CONTEXT = {
    "service_code": "", "supplier_code": "", "option_code": "", "location_code": "",
    "location_name": "", "supplier_name": "", "title_note": "", "option_description": "",
    "room_summary": "", "nights": "", "conditions_note": "", "is_optional": False,
    "custom_title": "", "custom_description": "", "image_url": "", "image_url_2": "",
    "image_url_3": "", "amount": "",
}

# Entries pueden pertenecer a cualquier departamento; se filtra por FULL_REFERENCE exacto
# igual, así que traer las 3 branches acá es seguro (a diferencia del uso en Calidad, que
# mantiene el default 'AL' para no cambiar su comportamiento actual).
_ALL_BRANCHES = ("AL", "DM", "GR")


def _safe_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _booking_ref_for_entry(entry):
    if entry.tourplanId:
        return entry.tourplanId
    if entry.trip and entry.trip.tourplanId:
        return entry.trip.tourplanId
    return ""


def _lookup_product(option_code, supplier_code, location_code):
    """
    Auto-match una línea de Tourplan contra el Product del tarifario ya sincronizado, mismo
    patrón que usa tariff/views/tariff.py para el tarifario. El CODE de un producto no es
    único por sí solo — la clave real es (CODE, LOCATION, SUPPLIER) — así que se exige el
    triple match; si location_code no vino o no matchea nada, se cae a (CODE, SUPPLIER) SOLO
    si eso ya identifica un único producto sin ambigüedad (nunca se adivina entre varios).
    """
    if not option_code:
        return None
    qs = Product.objects.filter(code=option_code)
    if supplier_code:
        qs = qs.filter(supplier__code=supplier_code)

    if location_code:
        exact = qs.filter(tp_location_code=location_code)
        match = exact.first()
        if match and exact.count() == 1:
            return match

    if qs.count() == 1:
        return qs.first()
    return None


def _photo_url_for(product, supplier_code, allow_supplier_fallback=False):
    """
    allow_supplier_fallback: si no hay foto de producto, buscar la del proveedor en el
    tarifario. Solo tiene sentido para alojamiento — el código de proveedor de Tourplan se
    reutiliza para TODOS los cargos de un mismo hotel (habitación, impuesto, etc.), así que
    para líneas que no son de alojamiento este fallback terminaba mostrando la foto del hotel
    en cosas como un impuesto (confirmado con datos reales: reserva ALFI122048, línea
    'Impuesto Ciudad de Buenos Aires' de Palo Santo Hotel mostraba la foto del hotel).
    """
    filename = None
    if product and product.pic1_url:
        filename = product.pic1_url
    elif allow_supplier_fallback and supplier_code:
        supplier = Supplier.objects.filter(code=supplier_code).first()
        if supplier and supplier.pic1_url:
            filename = supplier.pic1_url

    if not filename:
        return None
    if filename.startswith("http") or filename.startswith("/"):
        return filename
    return static(f"tariff/{filename}")


# Categorías de nota de producto en Tourplan (NTS) usadas para armar el itinerario público.
# Confirmado contra datos reales:
# DAY = nombre elaborado (título) de servicios que no son alojamiento.
# ODE = para alojamiento, el título (tipo de habitación/producto, ej. "Premium Room with
#       Breakfast"); para el resto, un texto casi idéntico a DAY (no sirve como contenido).
# OIE = el descriptivo largo real de servicios que no son alojamiento (lo que se muestra al
#       desplegar) — no confundir con ODE, que solo repite el título.
# FH1/FH2/FH3 = fotos de hoteles. ODX = foto de todo lo que no es hotel.
# CCP/IMS/IMP/IMB = condiciones/avisos puntuales de la línea (política de niños, restricciones,
# importante). BIT = comentario importante a nivel de todo el itinerario. CPP = requisito de
# prepago (solo aplica a alojamiento).
_PRODUCT_NOTE_CATEGORIES = (
    "DAY", "ODE", "OIE", "FH1", "FH2", "FH3", "ODX",
    "CCP", "IMS", "IMP", "IMB", "BIT", "CPP",
)

# OPSView.Singles/Doubles/Twins/Triples/Quads/Others -> etiqueta legible del tipo de habitación.
_ROOM_TYPE_FIELDS = (
    ("Singles", "Single"),
    ("Doubles", "Double"),
    ("Twins", "Twin"),
    ("Triples", "Triple"),
    ("Quads", "Quad"),
    ("Others", "Other"),
)


def _int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _room_summary_for(row):
    """Ej.: '1 Double — 3 nights', a partir de los conteos de habitación que ya trae OPSView."""
    parts = []
    for field, label in _ROOM_TYPE_FIELDS:
        qty = _int_or_zero(row.get(field))
        if qty:
            parts.append(f"{qty} {label}{'s' if qty != 1 else ''}")
    nights = _int_or_zero(row.get("Nights"))
    summary = ", ".join(parts)
    if nights:
        night_txt = f"{nights} night{'s' if nights != 1 else ''}"
        summary = f"{summary} — {night_txt}" if summary else night_txt
    return summary


def _looks_like_text_note(text):
    """Heurística para descartar una nota de texto que en realidad trae una imagen/blob en
    vez de texto (visto en los datos reales: pasa ocasionalmente con OIE/BIT). Texto real
    casi siempre tiene espacios; un bloque base64 largo no."""
    if not text:
        return False
    if len(text) > 100 and " " not in text[:200]:
        return False
    return True


# El itinerario público es en inglés (por ahora, un solo idioma) — algunos productos tienen
# más de una nota histórica para la misma categoría, a veces en otro idioma (visto en datos
# reales: alemán). No hace falta un detector de idioma genérico, solo reconocer alemán y
# descartarlo a favor de la otra versión: diéresis/ß, o palabras alemanas muy comunes que
# casi nunca aparecen en inglés.
_GERMAN_MARKERS = re.compile(
    r"[äöüßÄÖÜ]|\b(?:und|der|die|das|mit|für|nicht|ist|sie|wird|werden|eine|einen|über|bitte|Uhr|Anreise|Abreise)\b",
    re.IGNORECASE,
)


def _looks_german(text):
    return bool(text) and bool(_GERMAN_MARKERS.search(text))


def _fetch_all_notes(cursor, triples):
    """
    Notas de producto (DAY/ODE/OIE/FH1-3/ODX/...) para TODAS las líneas del itinerario en
    UNA sola consulta (en vez de una por línea, que con reservas de muchos servicios tardaba
    demasiado por la cantidad de round-trips secuenciales a un servidor remoto). Asume que
    NTS.BHD_ID (mal nombrada para este tipo de nota) en realidad guarda el OPT_ID del
    producto — hipótesis confirmada contra datos reales, PERO solo para SOURCE='DB ' (notas
    de catálogo, BSL_ID=0). Confirmado contra datos reales (reserva ALFI122048): para
    SOURCE='BS ' (notas de voucher por reserva puntual) el mismo campo BHD_ID coincide
    numéricamente con OPT_IDs de productos sin ninguna relación real — pura casualidad de
    numeración — y termina trayendo condiciones/fotos de OTRA reserva/proveedor totalmente
    distinto. Por eso el filtro `SOURCE = 'DB ' AND BSL_ID = 0` es obligatorio, no cosmético.

    Confirmado contra datos reales: NTS.MESSAGE_TEXT es solo un valor "por defecto" que puede
    quedar en cualquier idioma según quién lo haya editado último — NO es la fuente de verdad
    del idioma. La traducción real por idioma vive en NTL (NTS_ID + Language + su propio
    Message_Text; códigos vistos: 'SP', 'EN', 'DE', 'IT'). Por eso se prioriza siempre
    NTL.Language='EN' sobre NTS.MESSAGE_TEXT; si un producto no tiene traducción al inglés
    cargada en NTL (hueco de carga real, no un bug), se cae al texto de NTS.MESSAGE_TEXT tal
    cual esté, y ahí sí puede seguir apareciendo en otro idioma — de ahí que el detector de
    alemán se mantenga como último recurso solo para ese caso límite.

    Falla en silencio (devuelve {}) si algo no matchea, para no romper la generación del
    itinerario si el esquema resulta distinto al esperado.

    triples: iterable de (option_code, supplier_code, location_code).
    Devuelve {(option_code, supplier_code, location_code): {categoria: texto}}.
    """
    triples = list(dict.fromkeys(t for t in triples if t[0]))  # dedupe, descarta sin option_code
    if not cursor or not triples:
        return {}
    try:
        cat_placeholders = ", ".join(["%s"] * len(_PRODUCT_NOTE_CATEGORIES))
        triple_conditions = " OR ".join(
            ["(OPT.CODE = %s AND OPT.SUPPLIER = %s AND OPT.LOCATION = %s)"] * len(triples)
        )
        sql = f"""
            SELECT OPT.CODE, OPT.SUPPLIER, OPT.LOCATION, NTS.CATEGORY, NTS.NTS_ID,
                   NTS.MESSAGE_TEXT, NTL.Message_Text AS EN_TEXT
            FROM OPT
            JOIN NTS ON NTS.BHD_ID = OPT.OPT_ID
            LEFT JOIN NTL ON NTL.NTS_ID = NTS.NTS_ID AND NTL.Language = 'EN'
            WHERE NTS.CATEGORY IN ({cat_placeholders})
              AND NTS.SOURCE = 'DB '
              AND NTS.BSL_ID = 0
              AND ({triple_conditions})
        """
        params = list(_PRODUCT_NOTE_CATEGORIES)
        for triple in triples:
            params.extend(triple)
        cursor.execute(sql, params)

        # Tourplan puede tener más de un OPT_ID histórico para el mismo (CODE, SUPPLIER,
        # LOCATION), así que puede haber más de una fila candidata por categoría. Prioridad:
        # 1) la que tenga traducción real en NTL.Language='EN'; 2) entre las que no, la que
        # no parezca alemana; 3) como desempate, la más reciente (NTS_ID más alto).
        best_scores = {}
        result = {}
        for row in cursor.fetchall():
            key = (
                (row["CODE"] or "").strip(),
                (row["SUPPLIER"] or "").strip(),
                (row["LOCATION"] or "").strip(),
            )
            category = (row["CATEGORY"] or "").strip()
            en_text = row["EN_TEXT"]
            text = en_text if en_text else row["MESSAGE_TEXT"]
            nts_id = row["NTS_ID"] or 0
            if en_text:
                tier = 2
            elif not _looks_german(text):
                tier = 1
            else:
                tier = 0
            score = (tier, nts_id)
            cell_key = (key, category)
            if cell_key not in best_scores or score > best_scores[cell_key]:
                best_scores[cell_key] = score
                result.setdefault(key, {})[category] = text
        return result
    except Exception:
        return {}


_SUPPLIER_PHOTO_CATEGORIES = ("DH1", "DH2", "DH3")


def _fetch_supplier_photos(cursor, supplier_codes):
    """
    DH1/DH2/DH3 = fotos a nivel de PROVEEDOR (el hotel en su conjunto — fachada, lobby, etc.)
    — distintas de FH1/FH2/FH3, que son a nivel de producto/habitación puntual (esas sí tienen
    copia única a nivel catálogo, ver _fetch_all_notes). DH1-3 NO tiene una copia única a
    nivel catálogo: confirmado contra datos reales (proveedor 1616) que Tourplan guarda una
    copia repetida por cada reserva que usó ese proveedor (SOURCE='BS ', NOTE_LEVEL='DSS'),
    todas con el mismo contenido — así que alcanza con tomar cualquier ocurrencia (la más
    reciente por NTS_ID) por código de proveedor.

    Devuelve {supplier_code: {"DH1": texto, "DH2": texto, "DH3": texto}}.
    Falla en silencio (devuelve {}) si algo no matchea.
    """
    supplier_codes = list(dict.fromkeys(c for c in supplier_codes if c))
    if not cursor or not supplier_codes:
        return {}
    try:
        cat_placeholders = ", ".join(["%s"] * len(_SUPPLIER_PHOTO_CATEGORIES))
        supplier_placeholders = ", ".join(["%s"] * len(supplier_codes))
        cursor.execute(
            f"""
            SELECT SUPPLIER_CODE, CATEGORY, MESSAGE_TEXT, NTS_ID
            FROM NTS
            WHERE SOURCE = 'BS ' AND CATEGORY IN ({cat_placeholders})
              AND SUPPLIER_CODE IN ({supplier_placeholders})
            """,
            list(_SUPPLIER_PHOTO_CATEGORIES) + supplier_codes,
        )
        best = {}  # (supplier_code, category) -> (nts_id, texto)
        for row in cursor.fetchall():
            key = ((row["SUPPLIER_CODE"] or "").strip(), (row["CATEGORY"] or "").strip())
            nts_id = row["NTS_ID"] or 0
            if key not in best or nts_id > best[key][0]:
                best[key] = (nts_id, row["MESSAGE_TEXT"])

        result = {}
        for (supplier_code, category), (_, text) in best.items():
            result.setdefault(supplier_code, {})[category] = text
        return result
    except Exception:
        _log.exception("No se pudieron traer las fotos de proveedor (DH1-3)")
        return {}


def _fetch_supplier_descriptions(cursor, supplier_codes):
    """
    SDE = descripción real del proveedor (el hotel en su conjunto — texto libre tipo "Palo
    Santo is a small luxury design and green hotel..."). Confirmado contra datos reales
    (proveedor 1618, Palo Santo): SOURCE='DS ', BHD_ID=0, BSL_ID=0 — a diferencia de DH1-3, acá
    hay UNA sola fila por proveedor (no se duplica por reserva), así que no hace falta lógica
    de "más reciente entre varias".

    Devuelve {supplier_code: texto}. Falla en silencio (devuelve {}) si algo no matchea.
    """
    supplier_codes = list(dict.fromkeys(c for c in supplier_codes if c))
    if not cursor or not supplier_codes:
        return {}
    try:
        placeholders = ", ".join(["%s"] * len(supplier_codes))
        cursor.execute(
            f"""
            SELECT SUPPLIER_CODE, MESSAGE_TEXT
            FROM NTS
            WHERE SOURCE = 'DS ' AND CATEGORY = 'SDE'
              AND SUPPLIER_CODE IN ({placeholders})
            """,
            supplier_codes,
        )
        return {(row["SUPPLIER_CODE"] or "").strip(): row["MESSAGE_TEXT"] for row in cursor.fetchall()}
    except Exception:
        _log.exception("No se pudo traer la descripción de proveedor (SDE)")
        return {}


def _fetch_package_pricing(cursor, all_rows):
    """
    Un "Paquete Sin Alojamiento" en Tourplan (Option Type) agrupa varios subitems internos
    (con proveedor/moneda propios, por temas impositivos) bajo un único encabezado. Solo el
    encabezado debe aparecer en el itinerario — sus subitems nunca se muestran como línea
    propia.

    El monto de venta (AGENT) del encabezado SIEMPRE figura en 0 en OPSView/BSD — no es un
    hueco de datos, es estructural: Tourplan nunca le asigna precio a la fila del encabezado
    en sí. El monto real que la agencia ve en la pantalla de Markup/Commission de la booking
    es la SUMA de BSD.AGENT de sus subitems para esa ocurrencia puntual del paquete — validado
    contra datos reales (booking ALFI119976, línea AEPG01: suma de subitems = USD 234.00,
    coincide exacto con lo que muestra la pantalla).

    Para armar esto se usa OPSView.Voucher_Number, que resulta ser exactamente BSL.BSL_ID
    (confirmado contra datos reales) — evita tener que resolver el BHD_ID real de la booking
    por separado. BSL.PCM_ID + BSL.PCM_SEQ identifican la ocurrencia puntual del paquete
    dentro de ESTA booking (una misma reserva puede repetir el mismo paquete más de una vez,
    ej. traslado de ida y de vuelta, cada uno con su propio PCM_SEQ) — encabezado y subitems
    de la misma ocurrencia comparten (PCM_ID, PCM_SEQ).

    Devuelve (header_amount_by_bsl_id, excluded_bsl_ids):
      - header_amount_by_bsl_id: {BSL_ID del encabezado: monto sumado de sus subitems}.
      - excluded_bsl_ids: set de BSL_ID que son subitems a ocultar como línea.
    Falla en silencio (devuelve ({}, set())) si algo no matchea, para no romper la generación
    del itinerario si el esquema de paquetes resulta distinto al esperado.
    """
    bsl_ids = list({row.get("Voucher_Number") for row in all_rows if row.get("Voucher_Number")})
    if not cursor or not bsl_ids:
        return {}, set()
    try:
        id_placeholders = ", ".join(["%s"] * len(bsl_ids))
        cursor.execute(
            f"SELECT BSL_ID, OPT_ID, PCM_ID, PCM_SEQ FROM BSL WHERE BSL_ID IN ({id_placeholders})",
            bsl_ids,
        )
        bsl_by_id = {row["BSL_ID"]: row for row in cursor.fetchall()}
        package_bsl_ids = [bsl_id for bsl_id, row in bsl_by_id.items() if row["PCM_ID"]]
        if not package_bsl_ids:
            return {}, set()

        opt_ids = list({bsl_by_id[bsl_id]["OPT_ID"] for bsl_id in package_bsl_ids})
        opt_placeholders = ", ".join(["%s"] * len(opt_ids))
        cursor.execute(f"SELECT OPT_ID FROM PKG WHERE OPT_ID IN ({opt_placeholders})", opt_ids)
        header_opt_ids = {row["OPT_ID"] for row in cursor.fetchall()}
        if not header_opt_ids:
            return {}, set()

        # Agrupar por (PCM_ID, PCM_SEQ) = una ocurrencia puntual del paquete en esta reserva.
        groups = {}
        for bsl_id in package_bsl_ids:
            row = bsl_by_id[bsl_id]
            groups.setdefault((row["PCM_ID"], row["PCM_SEQ"]), []).append((bsl_id, row["OPT_ID"]))

        header_amount_by_bsl_id = {}
        excluded_bsl_ids = set()
        for members in groups.values():
            header_bsl_id = next((bid for bid, opt_id in members if opt_id in header_opt_ids), None)
            if header_bsl_id is None:
                continue
            subitem_bsl_ids = [bid for bid, opt_id in members if bid != header_bsl_id]
            if not subitem_bsl_ids:
                continue
            sub_placeholders = ", ".join(["%s"] * len(subitem_bsl_ids))
            cursor.execute(f"SELECT AGENT FROM BSD WHERE BSL_ID IN ({sub_placeholders})", subitem_bsl_ids)
            total_agent = sum((row["AGENT"] or 0) for row in cursor.fetchall())
            header_amount_by_bsl_id[header_bsl_id] = float(total_agent)
            excluded_bsl_ids.update(subitem_bsl_ids)

        return header_amount_by_bsl_id, excluded_bsl_ids
    except Exception:
        _log.exception("No se pudo calcular el precio real de paquetes (BSL/BSD vía Voucher_Number)")
        return {}, set()


def _fold_packages(day_rows, header_amount_by_bsl_id, excluded_bsl_ids):
    """
    Oculta, dentro de las filas de un mismo día, las que son subitems de un paquete — "solo
    deben figurar estos encabezados y no los items que incluye dentro" — y les pisa el monto
    a los encabezados con la suma real calculada en _fetch_package_pricing (Service_Sell de
    OPSView siempre viene en 0 para encabezados de paquete). El cruce se hace por
    Voucher_Number (== BSL_ID).
    """
    if not excluded_bsl_ids:
        return day_rows

    kept_rows = []
    for row in day_rows:
        bsl_id = row.get("Voucher_Number")
        if bsl_id in excluded_bsl_ids:
            continue
        if bsl_id in header_amount_by_bsl_id:
            row = dict(row)
            row["Service_Sell"] = header_amount_by_bsl_id[bsl_id]
        kept_rows.append(row)
    return kept_rows


_IMAGE_MAGIC_BYTES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def _sniff_image_ext(raw_bytes):
    for magic, ext in _IMAGE_MAGIC_BYTES:
        if raw_bytes.startswith(magic):
            return ext
    if raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        return "webp"
    return "jpg"


_DATA_URI_RE = re.compile(r'data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=]+)')


def _resolve_photo(text):
    """
    Las notas de foto (FH1/FH2/FH3/ODX/DH1-3) vienen como una URL, o como HTML con la imagen
    embebida adentro de un data-URI (`<img src="data:image/png;base64,XXXX">`) — NO como
    base64 puro suelto. Confirmado con datos reales (proveedor Palo Santo, DH1-3): decodificar
    el bloque completo (incluidas las etiquetas HTML alrededor) como si fuera base64 puro
    produce basura o falla directo (esto pasaba desapercibido porque nunca se verificó
    visualmente que una imagen decodificada abriera bien). Por eso primero se busca el
    payload real adentro del data-URI; solo si no hay ningún `data:image/...;base64,` se
    intenta el texto entero como fallback (por si algún caso sí viniera en base64 puro).
    Si es base64, se decodifica y se guarda como archivo (nombrado por hash del contenido,
    así una misma foto no se duplica cada vez que se regenera un itinerario) y se devuelve su
    URL; si ya es una URL, se devuelve tal cual.
    """
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://") or text.startswith("/"):
        return text

    match = _DATA_URI_RE.search(text)
    cleaned = match.group(1) if match else "".join(text.split())
    try:
        raw = base64.b64decode(cleaned)
    except Exception:
        return None
    if len(raw) < 100:  # muy chico para ser una foto real
        return None

    ext = _sniff_image_ext(raw)
    digest = hashlib.sha1(raw).hexdigest()[:16]
    rel_path = f"itinerarios/tp_notes/{digest}.{ext}"
    if not default_storage.exists(rel_path):
        default_storage.save(rel_path, ContentFile(raw))
    return default_storage.url(rel_path)


def _group_rows_by_day(rows):
    """Agrupa filas de fetch_itinerary_from_tourplan por Service_Date (string dd/mm/YYYY),
    en orden cronológico; filas sin fecha válida van al final."""
    groups = OrderedDict()
    for row in rows:
        date_str = (row.get("Service_Date") or "").strip()
        parsed = None
        if date_str:
            try:
                parsed = datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                parsed = None
        groups.setdefault(parsed, []).append(row)
    dated_keys = sorted(k for k in groups if k is not None)
    ordered_keys = dated_keys + ([None] if None in groups else [])
    return [(k, groups[k]) for k in ordered_keys]


def _resolve_line_data(row, all_notes, supplier_photos=None, supplier_descriptions=None):
    """
    Junta todo lo que hace falta para una línea (match de producto, notas DAY/ODE/OIE/FH1-3/
    ODX/CCP/IMS/IMP/IMB, foto, desglose de habitación, si es upgrade opcional) — llamado
    antes de la transacción de Django, con las notas de TODO el itinerario ya traídas en una
    sola consulta batch (all_notes).

    Devuelve (line_kwargs, bit_text, cpp_text): line_kwargs es lo que se guarda en
    ItineraryLine; bit_text/cpp_text son comentarios a nivel de TODO el itinerario (no de
    esta línea puntual) que el caller acumula aparte (BIT = comentario importante general,
    CPP = requisito de prepago, solo relevante en alojamiento).
    """
    supplier_code = (row.get("Supplier_Code") or "").strip()
    option_code = (row.get("Product_Option_Code") or "").strip()
    location_code = (row.get("Product_Location") or "").strip()
    service_code = (row.get("Product_service") or "").strip().upper()
    is_hotel = service_code == "AC"
    product = _lookup_product(option_code, supplier_code, location_code)
    notes = all_notes.get((option_code, supplier_code, location_code), {})

    def _clean_note(category):
        text = notes.get(category)
        if not text or not _looks_like_text_note(text):
            return ""
        cleaned = strip_html(text)
        # Si la única nota disponible está en alemán (sin alternativa en inglés para elegir),
        # no la mostramos — mismo criterio que "sin descriptivo real, no mostrar nada".
        if _looks_german(cleaned):
            return ""
        return cleaned

    title_note = _clean_note("ODE") if is_hotel else _clean_note("DAY")
    if is_hotel:
        # Descripción real del proveedor (SDE, ver _fetch_supplier_descriptions) — no la nota
        # OIE, que es a nivel producto/habitación y no existe para alojamiento.
        supplier_desc = (supplier_descriptions or {}).get(supplier_code)
        content_note = (
            strip_html(supplier_desc).strip()
            if supplier_desc and _looks_like_text_note(supplier_desc) else ""
        )
    else:
        content_note = _clean_note("OIE")

    room_summary = _room_summary_for(row) if is_hotel else ""
    conditions_note = "\n".join(
        text for text in (_clean_note(cat) for cat in ("CCP", "IMS", "IMP", "IMB")) if text
    )
    rvt2 = (row.get("Rate_Voucher_Text2") or "").strip()
    if rvt2:
        conditions_note = f"{conditions_note}\n{rvt2}" if conditions_note else rvt2

    # Antes se detectaba buscando "option" en Service_StatusName, pero ese texto viene en el
    # idioma configurado en Tourplan (confirmado con datos reales: "Opcional", en español, que
    # no contiene "option") — poco confiable. El código de status SÍ es estable: 'OP' está
    # confirmado contra la tabla sst de Tourplan (sst.INCLUDEINTOTAL = False para 'OP', o sea
    # que ni el propio Tourplan lo suma al total).
    status_code = (row.get("Service_status") or "").strip().upper()
    is_optional = status_code == "OP"

    # Hoteles: hasta 3 fotos, con prioridad DH1-3 (proveedor — fachada/lobby del hotel en su
    # conjunto, confirmado que es lo que se quiere mostrar) por sobre FH1-3 (producto/
    # habitación puntual, que queda como respaldo — la vista por habitación se revisa más
    # adelante). El resto de los servicios solo tiene una (ODX) hasta donde vimos en los datos
    # reales.
    if is_hotel:
        sp = (supplier_photos or {}).get(supplier_code, {})
        image_url = (
            _resolve_photo(sp.get("DH1")) or _resolve_photo(notes.get("FH1"))
            or _photo_url_for(product, supplier_code, allow_supplier_fallback=True)
        )
        image_url_2 = _resolve_photo(sp.get("DH2")) or _resolve_photo(notes.get("FH2"))
        image_url_3 = _resolve_photo(sp.get("DH3")) or _resolve_photo(notes.get("FH3"))
    else:
        image_url = _resolve_photo(notes.get("ODX")) or _photo_url_for(product, supplier_code)
        image_url_2 = None
        image_url_3 = None

    line_kwargs = dict(
        service_code=service_code,
        supplier_code=supplier_code,
        option_code=option_code,
        location_code=location_code,
        location_name=(row.get("Product_Location_Name") or "").strip(),
        supplier_name=(row.get("Proveedor") or "").strip(),
        title_note=title_note,
        option_description=content_note,  # vacío si no hay nota OIE real — sin fallback al nombre crudo
        room_summary=room_summary,
        nights=_int_or_zero(row.get("Nights")) or None,
        conditions_note=conditions_note,
        is_optional=is_optional,
        image_url=image_url,
        image_url_2=image_url_2,
        image_url_3=image_url_3,
        amount=_safe_float(row.get("Service_Sell")),
    )
    bit_text = _clean_note("BIT")
    cpp_text = _clean_note("CPP") if is_hotel else ""
    return line_kwargs, bit_text, cpp_text


def _populate_from_tourplan(itinerary, entry):
    """
    Trae/actualiza el snapshot desde Tourplan. Segura para llamar más de una vez (borra los
    days/lines existentes antes de recrearlos) — así sirve tanto para la primera generación
    como para el botón "Actualizar desde Tourplan", que pisa a propósito lo editado a mano.
    """
    booking_ref = _booking_ref_for_entry(entry)
    if not booking_ref:
        _log.warning("Itinerario %s: entry %s no tiene tourplanId, no se puede sincronizar", itinerary.id, entry.id)
        return
    # A diferencia de Calidad (que no necesita ver impuestos/mensajes de bienvenida/vuelos/
    # "no incluye" para identificar proveedor/guía en una queja), el itinerario público sí
    # quiere mostrarlos — todos tienen su propio label en SERVICE_LABELS. Solo se sigue
    # excluyendo OC ("Other Charges"), sin label conocido ni confirmado como apto para
    # mostrarle al cliente.
    rows = fetch_itinerary_from_tourplan(booking_ref, branches=_ALL_BRANCHES, skip_service_types={"OC"})
    if not rows:
        _log.warning(
            "Itinerario %s: fetch_itinerary_from_tourplan(%r) no devolvió filas — revisar "
            "conexión/permisos de Tourplan (ver warnings de tariff.quality_ai) o que el "
            "booking_ref sea válido y esté dentro de la ventana de fechas.",
            itinerary.id, booking_ref,
        )
    grouped = _group_rows_by_day(rows)

    # Una sola conexión y UNA sola query de notas para TODO el itinerario (en vez de una
    # query por línea, que con reservas de muchos servicios tardaba demasiado por la
    # cantidad de round-trips secuenciales a un servidor remoto), y todo el trabajo de red
    # se resuelve ANTES de abrir la transacción de Django.
    from intranet.utils import get_tourplan_connection
    all_notes = {}
    supplier_photos = {}
    supplier_descriptions = {}
    header_amount_by_bsl_id, excluded_bsl_ids = {}, set()
    try:
        conn = get_tourplan_connection()
        try:
            cursor = conn.cursor()
            all_rows = [row for _, day_rows in grouped for row in day_rows]
            triples = [
                (
                    (row.get("Product_Option_Code") or "").strip(),
                    (row.get("Supplier_Code") or "").strip(),
                    (row.get("Product_Location") or "").strip(),
                )
                for row in all_rows
            ]
            all_notes = _fetch_all_notes(cursor, triples)
            hotel_supplier_codes = [
                (row.get("Supplier_Code") or "").strip()
                for row in all_rows if (row.get("Product_service") or "").strip().upper() == "AC"
            ]
            supplier_photos = _fetch_supplier_photos(cursor, hotel_supplier_codes)
            supplier_descriptions = _fetch_supplier_descriptions(cursor, hotel_supplier_codes)
            header_amount_by_bsl_id, excluded_bsl_ids = _fetch_package_pricing(cursor, all_rows)
        finally:
            conn.close()
    except Exception:
        _log.exception("Itinerario %s: no se pudo conectar a Tourplan para traer notas DAY/ODE/OIE/fotos", itinerary.id)
        all_notes = {}

    # Paquetes ("Paquete Sin Alojamiento"): ocultar subitems y pisarle a los encabezados el
    # monto real (suma de AGENT de sus subitems, ver _fetch_package_pricing) ANTES de resolver
    # notas/fotos por línea, para que las líneas ocultas ni siquiera lleguen a generarse como
    # ItineraryLine.
    grouped = [
        (day_date, _fold_packages(day_rows, header_amount_by_bsl_id, excluded_bsl_ids))
        for day_date, day_rows in grouped
    ]

    days_data = []
    important_comments = []
    prepayments_required = []
    for day_date, day_rows in grouped:
        lines_data = []
        for row in day_rows:
            line_kwargs, bit_text, cpp_text = _resolve_line_data(row, all_notes, supplier_photos, supplier_descriptions)
            lines_data.append(line_kwargs)
            if bit_text and bit_text not in important_comments:
                important_comments.append(bit_text)
            if cpp_text and cpp_text not in prepayments_required:
                prepayments_required.append(cpp_text)
        days_data.append((day_date, lines_data))

    with transaction.atomic():
        itinerary.days.all().delete()  # idempotente: permite re-sincronizar sin duplicar
        for day_order, (day_date, lines_data) in enumerate(days_data):
            day = ItineraryDay.objects.create(
                itinerary=itinerary,
                order=day_order,
                date=day_date,
                title=f"Day {day_order + 1}",
            )
            for line_order, line_kwargs in enumerate(lines_data):
                ItineraryLine.objects.create(day=day, order=line_order, **line_kwargs)
        itinerary.synced_from_tourplan_at = timezone_now()
        itinerary.important_comments = "\n\n".join(important_comments)
        itinerary.prepayments_required = "\n\n".join(prepayments_required)
        if rows:
            itinerary.pax_count = _int_or_zero(rows[0].get("Total_Pax")) or itinerary.pax_count
            itinerary.consultant_name = (rows[0].get("Consultant") or "").strip() or itinerary.consultant_name
        itinerary.save(update_fields=[
            "synced_from_tourplan_at", "important_comments", "prepayments_required",
            "pax_count", "consultant_name",
        ])


def _serialize_itinerary(itinerary):
    return {
        "title": itinerary.title,
        "intro_text": itinerary.intro_text,
        "cover_image_url": itinerary.cover_image_url or "",
        "show_prices": itinerary.show_prices,
        "currency": itinerary.currency,
        "total_amount": itinerary.total_amount,
        "is_published": itinerary.is_published,
        "important_comments": itinerary.important_comments,
        "prepayments_required": itinerary.prepayments_required,
        "pax_count": itinerary.pax_count,
        "consultant_name": itinerary.consultant_name,
        "trip_style": itinerary.trip_style,
        "sustainability_note": itinerary.sustainability_note,
        "days": [
            {
                "date": day.date.isoformat() if day.date else "",
                "title": day.title,
                "description": day.description,
                "image_url": day.image_url or "",
                "lines": [
                    {
                        "service_code": line.service_code,
                        "supplier_code": line.supplier_code,
                        "option_code": line.option_code,
                        "location_code": line.location_code,
                        "location_name": line.location_name,
                        "supplier_name": line.supplier_name,
                        "title_note": line.title_note,
                        "option_description": line.option_description,
                        "room_summary": line.room_summary,
                        "nights": line.nights,
                        "conditions_note": line.conditions_note,
                        "is_optional": line.is_optional,
                        "custom_title": line.custom_title,
                        "custom_description": line.custom_description,
                        "image_url": line.image_url or "",
                        "image_url_2": line.image_url_2 or "",
                        "image_url_3": line.image_url_3 or "",
                        "amount": line.amount,
                    }
                    for line in day.lines.all()
                ],
            }
            for day in itinerary.days.all()
        ],
    }


def render_itinerary_cell(entry, itinerary):
    """HTML para la columna "Itinerario" de la tabla de Pendientes (staff)."""
    if not _booking_ref_for_entry(entry):
        return '<span class="text-muted" title="Sin código Tourplan">—</span>'

    edit_url = reverse("entry_itinerary_edit", args=[entry.id])
    if not itinerary:
        return (
            f'<a href="{edit_url}" target="_blank" class="btn btn-sm btn-outline-secondary" '
            f'title="Generar itinerario"><i class="fa-solid fa-route"></i></a>'
        )
    if itinerary.is_published:
        badge = '<span class="badge rounded-pill bg-success" title="Publicado">Publicado</span>'
    else:
        badge = '<span class="badge rounded-pill bg-secondary" title="Borrador, no publicado">Borrador</span>'
    return (
        f'<a href="{edit_url}" target="_blank" class="btn btn-sm btn-outline-secondary me-1" '
        f'title="Editar itinerario"><i class="fa-solid fa-route"></i></a>{badge}'
    )


def _staff_entry_or_404(request, entry_id):
    return get_object_or_404(
        Entry.objects.select_related("trip"),
        id=entry_id, trip__department=request.user.department,
    )


@login_required
def entry_itinerary_edit(request, entry_id):
    if request.user.userType == "Cliente":
        return JsonResponse({"error": "No autorizado"}, status=403)

    entry = _staff_entry_or_404(request, entry_id)
    itinerary, created = PublicItinerary.objects.get_or_create(
        entry=entry,
        defaults={
            "title": entry.trip.name if entry.trip else "",
            "total_amount": entry.amount,
            "created_by": request.user,
        },
    )
    if itinerary.synced_from_tourplan_at is None:
        _populate_from_tourplan(itinerary, entry)

    public_url = request.build_absolute_uri(reverse("public_itinerary", args=[itinerary.token]))
    return render(request, "intranet/itinerary_edit.html", {
        "entry": entry,
        "itinerary": itinerary,
        "public_url": public_url,
        "itinerary_json": json.dumps(_serialize_itinerary(itinerary)),
        "service_labels": SERVICE_LABELS,
        "empty_line": EMPTY_LINE_CONTEXT,
        "default_intro_text": DEFAULT_ITINERARY_INTRO_TEXT,
    })


@login_required
def entry_itinerary_resync(request, entry_id):
    """Vuelve a traer el itinerario desde Tourplan, pisando a propósito lo editado a mano."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    if request.user.userType == "Cliente":
        return JsonResponse({"error": "No autorizado"}, status=403)

    entry = _staff_entry_or_404(request, entry_id)
    itinerary = get_object_or_404(PublicItinerary, entry=entry)
    _populate_from_tourplan(itinerary, entry)
    return JsonResponse({"ok": True})


@login_required
def entry_itinerary_save(request, entry_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    if request.user.userType == "Cliente":
        return JsonResponse({"error": "No autorizado"}, status=403)

    entry = _staff_entry_or_404(request, entry_id)
    itinerary = get_object_or_404(PublicItinerary, entry=entry)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    with transaction.atomic():
        itinerary.title = (data.get("title") or "").strip()
        itinerary.intro_text = data.get("intro_text") or ""
        itinerary.cover_image_url = (data.get("cover_image_url") or "").strip() or None
        itinerary.show_prices = bool(data.get("show_prices", True))
        itinerary.currency = (data.get("currency") or "USD").strip()
        itinerary.total_amount = _safe_float(data.get("total_amount"))
        itinerary.important_comments = data.get("important_comments") or ""
        itinerary.prepayments_required = data.get("prepayments_required") or ""
        itinerary.pax_count = _int_or_zero(data.get("pax_count")) or None
        itinerary.consultant_name = (data.get("consultant_name") or "").strip()
        itinerary.trip_style = (data.get("trip_style") or "").strip()
        itinerary.sustainability_note = (data.get("sustainability_note") or "").strip()
        itinerary.edited_manually_at = timezone_now()
        itinerary.save()

        itinerary.days.all().delete()
        for day_order, day_data in enumerate(data.get("days", [])):
            day_date = None
            if day_data.get("date"):
                try:
                    day_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()
                except ValueError:
                    day_date = None
            day = ItineraryDay.objects.create(
                itinerary=itinerary,
                order=day_order,
                date=day_date,
                title=(day_data.get("title") or "").strip(),
                description=day_data.get("description") or "",
                image_url=(day_data.get("image_url") or "").strip() or None,
            )
            for line_order, line_data in enumerate(day_data.get("lines", [])):
                ItineraryLine.objects.create(
                    day=day,
                    order=line_order,
                    service_code=(line_data.get("service_code") or "").strip().upper(),
                    supplier_code=(line_data.get("supplier_code") or "").strip(),
                    option_code=(line_data.get("option_code") or "").strip(),
                    location_code=(line_data.get("location_code") or "").strip(),
                    location_name=(line_data.get("location_name") or "").strip(),
                    supplier_name=(line_data.get("supplier_name") or "").strip(),
                    title_note=(line_data.get("title_note") or "").strip(),
                    option_description=(line_data.get("option_description") or "").strip(),
                    room_summary=(line_data.get("room_summary") or "").strip(),
                    nights=_int_or_zero(line_data.get("nights")) or None,
                    conditions_note=line_data.get("conditions_note") or "",
                    is_optional=bool(line_data.get("is_optional")),
                    custom_title=(line_data.get("custom_title") or "").strip(),
                    custom_description=line_data.get("custom_description") or "",
                    image_url=(line_data.get("image_url") or "").strip() or None,
                    image_url_2=(line_data.get("image_url_2") or "").strip() or None,
                    image_url_3=(line_data.get("image_url_3") or "").strip() or None,
                    amount=_safe_float(line_data.get("amount")),
                )

    return JsonResponse({"ok": True})


@login_required
def entry_itinerary_publish(request, entry_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    if request.user.userType == "Cliente":
        return JsonResponse({"error": "No autorizado"}, status=403)

    entry = _staff_entry_or_404(request, entry_id)
    itinerary = get_object_or_404(PublicItinerary, entry=entry)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        data = {}
    itinerary.is_published = bool(data.get("published", not itinerary.is_published))
    itinerary.save(update_fields=["is_published"])
    return JsonResponse({"ok": True, "is_published": itinerary.is_published})


@login_required
def entry_itinerary_upload_image(request, entry_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    if request.user.userType == "Cliente":
        return JsonResponse({"error": "No autorizado"}, status=403)

    _staff_entry_or_404(request, entry_id)
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "Falta el archivo"}, status=400)
    path = default_storage.save(f"itinerarios/{entry_id}/{photo.name}", photo)
    return JsonResponse({"url": default_storage.url(path)})


def public_itinerary_view(request, token):
    """Sin login. Bearer token: si no existe o no está publicado, no se filtran detalles."""
    itinerary = (
        PublicItinerary.objects
        .filter(token=token, is_published=True)
        .select_related("entry")
        .first()
    )
    if not itinerary:
        return render(request, "intranet/itinerary_public.html", {"unavailable": True}, status=404)

    days = list(itinerary.days.prefetch_related("lines").all())
    # Separar líneas incluidas de las opcionales/upgrade (mismo día, pero se muestran en
    # secciones distintas — "regular_days"/"optional_days" son listas de (day, lines)).
    regular_days = []
    optional_days = []
    accommodation_cards = []
    quote_brief_groups = OrderedDict()  # nombre de ciudad/location -> [(day, line), ...]
    for day in days:
        lines = list(day.lines.all())
        regular_lines = [line for line in lines if not line.is_optional]
        optional_lines = [line for line in lines if line.is_optional]
        if regular_lines:
            regular_days.append((day, regular_lines))
        if optional_lines:
            optional_days.append((day, optional_lines))
        for line in regular_lines:
            if line.service_code == "AC" and day.date:
                nights = line.nights or 1
                photos = [u for u in (line.image_url, line.image_url_2, line.image_url_3) if u]
                accommodation_cards.append({
                    "line": line,
                    "checkin": day.date,
                    "checkout": day.date + timedelta(days=nights),
                    "nights": nights,
                    "photos": photos,
                })
            loc_name = line.location_name or line.location_code or "Other"
            quote_brief_groups.setdefault(loc_name, []).append((day, line))

    dated_days = [d for d in days if d.date]
    nights_total = (dated_days[-1].date - dated_days[0].date).days if len(dated_days) >= 2 else 0
    days_total = nights_total + 1 if dated_days else len(days)

    # No hay pasajeros nombrados en el sistema todavía (solo la cantidad) — placeholders
    # "Adult N" por ahora, a pedido explícito, hasta que se incorpore el dato real de
    # Tourplan (existe por reserva, pero no lo traemos hoy).
    passengers = [f"Adult {i + 1}" for i in range(itinerary.pax_count or 0)]
    per_person_amount = None
    if itinerary.total_amount and itinerary.pax_count:
        per_person_amount = itinerary.total_amount / itinerary.pax_count

    return render(request, "intranet/itinerary_public.html", {
        "unavailable": False,
        "itinerary": itinerary,
        "default_cover_url": static("intranet/images/itinerary_cover_default.png"),
        "default_intro_text": DEFAULT_ITINERARY_INTRO_TEXT,
        "regular_days": regular_days,
        "optional_days": optional_days,
        "quote_brief_groups": list(quote_brief_groups.items()),
        "accommodation_cards": accommodation_cards,
        "days_total": days_total,
        "nights_total": nights_total,
        "dated_days_first": dated_days[0].date if dated_days else None,
        "dated_days_last": dated_days[-1].date if dated_days else None,
        "passengers": passengers,
        "per_person_amount": per_person_amount,
        "service_labels": SERVICE_LABELS,
        "default_service_label": DEFAULT_SERVICE_LABEL,
        "service_type_bucket": SERVICE_TYPE_BUCKET,
        "default_service_type_bucket": DEFAULT_SERVICE_TYPE_BUCKET,
    })
