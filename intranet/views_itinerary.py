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

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timezone import now as timezone_now

from .models import (
    Entry, PublicItinerary, ItineraryDay, ItineraryLine, ItineraryPassenger,
    DEFAULT_ITINERARY_INTRO_TEXT, ExternalCalendarEntry,
)
from .utils import strip_html_keep_newlines
from tariff.models import Product, Supplier, CarCategory, CarHireConfig, Location
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
    "WE": ("Welcome", "fa-map-pin"),
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
    "FB": "meal", "WE": "welcome",
    "IM": "fee", "IN": "not-included",
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


def _resolve_static_pic(filename):
    """pic1_url/pic2_url/pic3_url del tarifario (Product/Supplier/Location) son un nombre de
    archivo suelto relativo a static/tariff/ — a diferencia de CarCategory.pic1_url, que ya es
    una URL completa (subida vía default_storage, ver category_create en car_hire.py)."""
    if not filename:
        return None
    if filename.startswith("http") or filename.startswith("/"):
        return filename
    return static(f"tariff/{filename}")


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

    return _resolve_static_pic(filename)


# Categorías de nota de producto en Tourplan (NTS) usadas para armar el itinerario público.
# Confirmado contra datos reales:
# DAY = nombre elaborado (título) de servicios que no son alojamiento.
# ODE = para alojamiento, el título (tipo de habitación/producto, ej. "Premium Room with
#       Breakfast"); para el resto, un texto casi idéntico a DAY (no sirve como contenido).
# OIE = el descriptivo largo real de servicios que no son alojamiento (lo que se muestra al
#       desplegar) — no confundir con ODE, que solo repite el título.
# FH1/FH2/FH3 = fotos de hoteles. ODX = foto de todo lo que no es hotel.
# CCP/IMS/IMP = condiciones/avisos puntuales de la línea (política de niños, restricciones,
# importante), a nivel de producto/catálogo — EXCEPTO IMS para alojamiento, ver más abajo.
_PRODUCT_NOTE_CATEGORIES = (
    "DAY", "ODE", "OIE", "FH1", "FH2", "FH3", "ODX",
    "CCP", "IMS", "IMP",
)
# CPP (requisito de prepago) NO va acá — es una nota a nivel PROVEEDOR (mismo SOURCE='DS ' que
# SDE, la descripción del hotel), no de producto/catálogo — ver _fetch_supplier_prepayments.
# Antes se buscaba a nivel producto (y solo para hoteles), por eso a veces no aparecía nada.
#
# IMS, para alojamiento (AC), TAMPOCO se busca acá — a pedido explícito, para hoteles esta
# nota vive a nivel PROVEEDOR (mismo patrón que SDE/CPP), no a nivel producto — ver
# _fetch_supplier_important_notes. Para el resto de los servicios sigue siendo de catálogo,
# por eso queda en esta lista (se sigue usando para todo lo que no sea AC).
#
# IMB TAMPOCO va acá para NINGÚN servicio — a diferencia del resto, es una nota específica de
# ESTE archivo/reserva (se carga en cada file en particular, no en el producto genérico) —
# ver _fetch_file_specific_notes. Antes se buscaba como nota de catálogo (SOURCE='DB '), por
# lo que en la práctica nunca traía nada real (una nota de archivo puntual no vive ahí).
#
# BIT tampoco va acá — a pedido explícito, es la misma clase de nota que IMB: se carga a
# nivel de LA BOOKING en particular (SOURCE='BS ', por Voucher_Number/BSL_ID), no del
# producto genérico — ver _fetch_file_specific_notes. Antes se buscaba como nota de catálogo,
# igual que le pasaba a IMB.

# Categorías de FOTO entre las de arriba. La traducción NTL.Language='EN' tiene sentido para
# notas de TEXTO (una traducción real del mismo contenido) pero no para fotos: confirmado con
# datos reales (reserva ALFI119691, proveedor 295/Canal Fun, producto FDS002) que la fila NTL
# de una nota ODX puede quedar con una foto vieja mientras alguien actualiza la foto "por
# defecto" en NTS.MESSAGE_TEXT directamente — y como _fetch_all_notes siempre prefería NTL
# cuando existía, la app mostraba la foto vieja sin importar cuántas veces se resincronizara
# (el bug estaba en qué campo de Tourplan se leía, no en un caché local nuestro).
_PHOTO_NOTE_CATEGORIES = {"FH1", "FH2", "FH3", "ODX"}

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


def _ci_get(row, key):
    """Busca `key` en `row` sin importar mayúsculas/minúsculas. Las columnas SIN alias del
    SELECT de fetch_itinerary_from_tourplan (pickup, dropoff, pickup_time, dropoff_time,
    pickup_date) no tienen garantizado el casing con el que pymssql las devuelve — a
    diferencia del resto de los campos usados en este archivo, que están todos aliasados
    explícitamente en el SQL."""
    if key in row:
        return row[key]
    key_lower = key.lower()
    for k, v in row.items():
        if k.lower() == key_lower:
            return v
    return None


def _txt(value):
    """str() defensivo para campos sin alias que pueden venir como datetime.time (columna TIME
    de SQL Server) en vez de string — pickup/dropoff/pickup_time/dropoff_time."""
    return str(value).strip() if value not in (None, "") else ""


def _to_date(value):
    """dropoff_date/pickup_date vienen como datetime.datetime (no como date) — sin alias, así
    que se usan junto con _ci_get."""
    return value.date() if hasattr(value, "date") else None


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
            is_photo = category in _PHOTO_NOTE_CATEGORIES
            # Para fotos, ignorar NTL por completo — no es una "traducción" real de una imagen,
            # y priorizarla causaba mostrar fotos viejas (ver _PHOTO_NOTE_CATEGORIES). Se usa
            # siempre el MESSAGE_TEXT "por defecto", que es el que de verdad se mantiene
            # actualizado en Tourplan.
            en_text = None if is_photo else row["EN_TEXT"]
            text = en_text if en_text else row["MESSAGE_TEXT"]
            nts_id = row["NTS_ID"] or 0
            if is_photo:
                tier = 1  # sin noción de idioma/traducción acá — el desempate es solo por NTS_ID
            elif en_text:
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

    IMPORTANTE (confirmado con datos reales, causó un colgado real en producción): estas
    filas están duplicadas por cada reserva que usó el proveedor — para uno popular puede
    haber miles de copias, cada una con una foto de cientos de KB. Traer MESSAGE_TEXT de
    TODAS las filas y quedarse con la más reciente en Python (como se hacía antes) implica
    bajar potencialmente varios GB por la red. Por eso acá se resuelve en dos pasos: primero
    se busca el NTS_ID más reciente por (proveedor, categoría) con un simple MAX() —liviano,
    nunca toca la columna de texto—, y solo DESPUÉS se trae el contenido de esas filas
    puntuales ganadoras.
    """
    supplier_codes = list(dict.fromkeys(c for c in supplier_codes if c))
    if not cursor or not supplier_codes:
        return {}
    try:
        cat_placeholders = ", ".join(["%s"] * len(_SUPPLIER_PHOTO_CATEGORIES))
        supplier_placeholders = ", ".join(["%s"] * len(supplier_codes))
        cursor.execute(
            f"""
            SELECT SUPPLIER_CODE, CATEGORY, MAX(NTS_ID) AS NTS_ID
            FROM NTS
            WHERE SOURCE = 'BS ' AND CATEGORY IN ({cat_placeholders})
              AND SUPPLIER_CODE IN ({supplier_placeholders})
            GROUP BY SUPPLIER_CODE, CATEGORY
            """,
            list(_SUPPLIER_PHOTO_CATEGORIES) + supplier_codes,
        )
        winning_ids = [row["NTS_ID"] for row in cursor.fetchall() if row["NTS_ID"]]
        if not winning_ids:
            return {}

        id_placeholders = ", ".join(["%s"] * len(winning_ids))
        cursor.execute(
            f"SELECT SUPPLIER_CODE, CATEGORY, MESSAGE_TEXT FROM NTS WHERE NTS_ID IN ({id_placeholders})",
            winning_ids,
        )
        result = {}
        for row in cursor.fetchall():
            supplier_code = (row["SUPPLIER_CODE"] or "").strip()
            category = (row["CATEGORY"] or "").strip()
            result.setdefault(supplier_code, {})[category] = row["MESSAGE_TEXT"]
        return result
    except Exception:
        _log.exception("No se pudieron traer las fotos de proveedor (DH1-3)")
        return {}


def _fetch_supplier_text_note(cursor, supplier_codes, category, source):
    """
    Nota de texto libre a nivel PROVEEDOR — BHD_ID=0, BSL_ID=0, UNA sola fila por proveedor
    (no se duplica por reserva, a diferencia de DH1-3), así que no hace falta lógica de "más
    reciente entre varias". El SOURCE varía según la categoría (confirmado contra datos
    reales, proveedor 1618/Palo Santo, viendo la ficha real del proveedor en Tourplan):
    SDE y CPP usan SOURCE='DS ', pero IMS usa SOURCE='CR ' — a pesar de que en la pantalla de
    Tourplan las tres se cargan una debajo de la otra como si fueran el mismo tipo de nota, no
    comparten el mismo SOURCE en la base.

    Categorías que usan esto: SDE (descripción real del proveedor, ver
    _fetch_supplier_descriptions), CPP (requisito de prepago, ver _fetch_supplier_prepayments,
    no limitado a hoteles) e IMS de alojamiento (aviso importante del hotel, ver
    _fetch_supplier_important_notes — a diferencia del resto de los servicios, donde IMS sigue
    siendo una nota de catálogo, ver _PRODUCT_NOTE_CATEGORIES).

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
            WHERE SOURCE = %s AND CATEGORY = %s
              AND SUPPLIER_CODE IN ({placeholders})
            """,
            [source, category] + supplier_codes,
        )
        return {(row["SUPPLIER_CODE"] or "").strip(): row["MESSAGE_TEXT"] for row in cursor.fetchall()}
    except Exception:
        _log.exception("No se pudo traer la nota de proveedor (%s)", category)
        return {}


def _fetch_supplier_descriptions(cursor, supplier_codes):
    return _fetch_supplier_text_note(cursor, supplier_codes, "SDE", "DS ")


def _fetch_supplier_prepayments(cursor, supplier_codes):
    return _fetch_supplier_text_note(cursor, supplier_codes, "CPP", "DS ")


def _fetch_supplier_important_notes(cursor, supplier_codes):
    return _fetch_supplier_text_note(cursor, supplier_codes, "IMS", "CR ")


def _fetch_file_specific_notes(cursor, bsl_ids, category):
    """
    Nota específica de ESTE archivo/reserva para una línea puntual — a diferencia de las
    notas de catálogo (SOURCE='DB ', ver _fetch_all_notes), que viven en el producto genérico
    y son iguales para cualquier reserva que lo use, esta vive en la ocurrencia REAL de ese
    producto dentro de esta booking puntual: SOURCE='BS ', NTS.BSL_ID = el ID real de la línea
    reservada — el mismo campo que OPSView.Voucher_Number (ya confirmado y usado para resolver
    paquetes, ver _fetch_package_pricing). Usado hoy para IMB, la única categoría que se carga
    "por file" en vez de a nivel de producto o de proveedor.

    Devuelve {bsl_id: texto}. Falla en silencio (devuelve {}) si algo no matchea.
    """
    bsl_ids = list({b for b in bsl_ids if b})
    if not cursor or not bsl_ids:
        return {}
    try:
        id_placeholders = ", ".join(["%s"] * len(bsl_ids))
        cursor.execute(
            f"""
            SELECT BSL_ID, MESSAGE_TEXT
            FROM NTS
            WHERE SOURCE = 'BS ' AND CATEGORY = %s
              AND BSL_ID IN ({id_placeholders})
            """,
            [category] + bsl_ids,
        )
        return {row["BSL_ID"]: row["MESSAGE_TEXT"] for row in cursor.fetchall()}
    except Exception:
        _log.exception("No se pudo traer la nota específica de archivo (%s)", category)
        return {}


def _fetch_booking_important_note(cursor, all_rows):
    """
    BIT = comentario importante cargado a nivel de TODA la booking — a diferencia de IMB (por
    línea puntual, ver _fetch_file_specific_notes), BIT es UNA sola nota para la reserva
    entera, no por línea ni por proveedor. Confirmado contra datos reales (booking
    ALFI129473): una única fila en NTS con SOURCE='BH ', CATEGORY='BIT', BHD_ID = el ID real
    del booking header — compartido por TODAS las líneas de la reserva —, BSL_ID=0 y
    SUPPLIER_CODE vacío (el texto puede mencionar varios proveedores a la vez, ej. "Aliwen
    Exclusive Amenities & Agreements: Palo Santo: ... Patagonia Queen: ... Selvaje: ...").

    Para resolver el BHD_ID de esta booking se usa cualquier Voucher_Number (== BSL_ID, ver
    _fetch_package_pricing) de sus líneas — todas comparten el mismo BHD_ID — vía la tabla
    BSL.

    Devuelve el texto ya limpio de HTML, o "" si no hay nota o algo no matchea.
    """
    bsl_ids = list({row.get("Voucher_Number") for row in all_rows if row.get("Voucher_Number")})
    if not cursor or not bsl_ids:
        return ""
    try:
        id_placeholders = ", ".join(["%s"] * len(bsl_ids))
        cursor.execute(f"SELECT TOP 1 BHD_ID FROM BSL WHERE BSL_ID IN ({id_placeholders})", bsl_ids)
        bhd_row = cursor.fetchone()
        bhd_id = bhd_row["BHD_ID"] if bhd_row else None
        if not bhd_id:
            return ""
        cursor.execute(
            "SELECT MESSAGE_TEXT FROM NTS WHERE SOURCE = 'BH ' AND CATEGORY = 'BIT' AND BHD_ID = %s",
            (bhd_id,),
        )
        note_row = cursor.fetchone()
        text = note_row["MESSAGE_TEXT"] if note_row else None
        return strip_html_keep_newlines(text).strip() if text and _looks_like_text_note(text) else ""
    except Exception:
        _log.exception("No se pudo traer el comentario importante de la booking (BIT)")
        return ""


def _fetch_passenger_assignments(cursor, bsl_ids):
    """
    Pasajero(s) nombrado(s) asignado(s) a cada línea de servicio real — pestaña "Pax" de una
    línea en Tourplan (Single/Twin/Double/.../Pax Group), confirmada contra datos reales
    (booking ALFI119691, línea BUE/TF/1863/EZEG02, BSL_ID=630611, grupo "Hinnawi/Portal x 4").

    La cadena confirmada es: BRL (BSL_ID -> PAX_ID, que pese al nombre es en realidad el
    PXC_ID — la asignación de ESE pasajero a ESTA booking puntual, no su perfil reutilizable)
    -> PNB (PXC_ID -> PXN_ID, el perfil maestro del pasajero, reutilizado entre bookings si ya
    viajó antes con Aliwen) -> PXN (PXN_ID -> nombre/apellido/fecha de nacimiento, ver
    _fetch_passenger_details).

    NO confirmado contra datos reales: una habitación doble/twin con 2 pasajeros bajo UNA sola
    fila de BRL (ADULT_COUNT=2 en una sola fila en vez de 2 filas separadas) — acá cada fila
    de BRL cuenta como UN pasajero. Si en la práctica el precio por pasajero no cierra para
    habitaciones compartidas, revisar este supuesto primero.

    Devuelve {bsl_id: [pxn_id, ...]}. Falla en silencio (devuelve {}) si algo no matchea.
    """
    bsl_ids = list({b for b in bsl_ids if b})
    if not cursor or not bsl_ids:
        return {}
    try:
        id_placeholders = ", ".join(["%s"] * len(bsl_ids))
        cursor.execute(f"SELECT BSL_ID, PAX_ID FROM BRL WHERE BSL_ID IN ({id_placeholders})", bsl_ids)
        brl_rows = cursor.fetchall()
        pxc_ids = list({row["PAX_ID"] for row in brl_rows if row["PAX_ID"]})
        if not pxc_ids:
            return {}

        pxc_placeholders = ", ".join(["%s"] * len(pxc_ids))
        cursor.execute(f"SELECT PXC_ID, PXN_ID FROM PNB WHERE PXC_ID IN ({pxc_placeholders})", pxc_ids)
        pxn_by_pxc = {row["PXC_ID"]: row["PXN_ID"] for row in cursor.fetchall()}

        result = {}
        for row in brl_rows:
            pxn_id = pxn_by_pxc.get(row["PAX_ID"])
            if not pxn_id:
                continue
            result.setdefault(row["BSL_ID"], []).append(pxn_id)
        return result
    except Exception:
        _log.exception("No se pudo traer la asignación de pasajeros por línea (BRL/PNB)")
        return {}


def _fetch_passenger_details(cursor, pxn_ids):
    """
    Ficha del pasajero (PXN) — nombre completo y edad. La edad se calcula siempre que se
    pueda a partir de DATEOFBIRTH (fecha de nacimiento real); si no está cargada, se cae a
    CHILD_AGE (edad cargada a mano para menores, cuando no se conoce la fecha exacta) — a
    falta de las dos, no se muestra edad, a pedido explícito ("si está cargada, sino no
    aparece esa info").

    Devuelve {pxn_id: {"full_name": str, "age": int o None}}. Falla en silencio (devuelve {})
    si algo no matchea.
    """
    pxn_ids = list({p for p in pxn_ids if p})
    if not cursor or not pxn_ids:
        return {}
    try:
        placeholders = ", ".join(["%s"] * len(pxn_ids))
        cursor.execute(
            f"SELECT PXN_ID, PAX_FORENAME, PAX_SURNAME, DATEOFBIRTH, CHILD_AGE "
            f"FROM PXN WHERE PXN_ID IN ({placeholders})",
            pxn_ids,
        )
        today = timezone_now().date()
        result = {}
        for row in cursor.fetchall():
            forename = (row["PAX_FORENAME"] or "").strip()
            surname = (row["PAX_SURNAME"] or "").strip()
            full_name = f"{forename} {surname}".strip()
            age = None
            dob = row["DATEOFBIRTH"]
            if dob:
                dob_date = dob.date() if hasattr(dob, "date") else dob
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
            elif row["CHILD_AGE"]:
                age = row["CHILD_AGE"]
            result[row["PXN_ID"]] = {"full_name": full_name, "age": age}
        return result
    except Exception:
        _log.exception("No se pudo traer el detalle de pasajeros (PXN)")
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

    Hay OTRO tipo de paquete (de alojamiento — confirmado con Las Torres, booking ALFI119691,
    "Programa Las Torres Clásico (04D/03N)") donde es AL REVÉS: el encabezado SÍ trae el monto
    real (coincide exacto con BSD.AGENT) y son los subitems los que están en 0 — son solo
    placeholders informativos "Día 1/Día 2/Día 3/Día 4" para desglosar el programa día por día,
    sin precio propio. Ahí sumar los subitems (dando 0) y pisárselo al encabezado borraba el
    monto real. Por eso ahora, antes de sumar, se chequea el monto que el encabezado YA trae en
    OPSView: si es distinto de 0, se respeta tal cual y no se calcula/pisa nada.

    De paso, para ese mismo tipo de paquete (encabezado con Nights de relleno, ej. 1, cuando el
    programa dura varias noches reales — "04D/03N" en el nombre del producto), se recalculan
    las noches como la diferencia entre la fecha del subitem más lejano y la fecha del propio
    encabezado — confirmado con Las Torres: encabezado 10/02, subitems 10/02..13/02, da 3
    noches reales en vez del "1" que trae Nights en OPSView.

    Devuelve (header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids):
      - header_amount_by_bsl_id: {BSL_ID del encabezado: monto sumado de sus subitems} — solo
        para encabezados cuyo propio monto en OPSView es 0/nulo.
      - header_nights_by_bsl_id: {BSL_ID del encabezado: noches reales calculadas} — solo
        cuando se pudo calcular con fechas válidas de subitems.
      - excluded_bsl_ids: set de BSL_ID que son subitems a ocultar como línea.
    Falla en silencio (devuelve ({}, {}, set())) si algo no matchea, para no romper la
    generación del itinerario si el esquema de paquetes resulta distinto al esperado.
    """
    bsl_ids = list({row.get("Voucher_Number") for row in all_rows if row.get("Voucher_Number")})
    if not cursor or not bsl_ids:
        return {}, {}, set()
    row_by_bsl_id = {row.get("Voucher_Number"): row for row in all_rows if row.get("Voucher_Number")}

    def _parse_date(row):
        text = (row.get("Service_Date") or "").strip() if row else ""
        try:
            return datetime.strptime(text, "%d/%m/%Y").date()
        except ValueError:
            return None

    try:
        id_placeholders = ", ".join(["%s"] * len(bsl_ids))
        cursor.execute(
            f"SELECT BSL_ID, OPT_ID, PCM_ID, PCM_SEQ FROM BSL WHERE BSL_ID IN ({id_placeholders})",
            bsl_ids,
        )
        bsl_by_id = {row["BSL_ID"]: row for row in cursor.fetchall()}
        package_bsl_ids = [bsl_id for bsl_id, row in bsl_by_id.items() if row["PCM_ID"]]
        if not package_bsl_ids:
            return {}, {}, set()

        opt_ids = list({bsl_by_id[bsl_id]["OPT_ID"] for bsl_id in package_bsl_ids})
        opt_placeholders = ", ".join(["%s"] * len(opt_ids))
        cursor.execute(f"SELECT OPT_ID FROM PKG WHERE OPT_ID IN ({opt_placeholders})", opt_ids)
        header_opt_ids = {row["OPT_ID"] for row in cursor.fetchall()}
        if not header_opt_ids:
            return {}, {}, set()

        # Agrupar por (PCM_ID, PCM_SEQ) = una ocurrencia puntual del paquete en esta reserva.
        groups = {}
        for bsl_id in package_bsl_ids:
            row = bsl_by_id[bsl_id]
            groups.setdefault((row["PCM_ID"], row["PCM_SEQ"]), []).append((bsl_id, row["OPT_ID"]))

        header_amount_by_bsl_id = {}
        header_nights_by_bsl_id = {}
        excluded_bsl_ids = set()
        for members in groups.values():
            header_bsl_id = next((bid for bid, opt_id in members if opt_id in header_opt_ids), None)
            if header_bsl_id is None:
                continue
            subitem_bsl_ids = [bid for bid, opt_id in members if bid != header_bsl_id]
            if not subitem_bsl_ids:
                continue
            excluded_bsl_ids.update(subitem_bsl_ids)

            header_row = row_by_bsl_id.get(header_bsl_id)
            header_own_amount = _safe_float(header_row.get("Service_Sell")) if header_row else None
            if not header_own_amount:
                sub_placeholders = ", ".join(["%s"] * len(subitem_bsl_ids))
                cursor.execute(f"SELECT AGENT FROM BSD WHERE BSL_ID IN ({sub_placeholders})", subitem_bsl_ids)
                total_agent = sum((row["AGENT"] or 0) for row in cursor.fetchall())
                header_amount_by_bsl_id[header_bsl_id] = float(total_agent)
            # si header_own_amount ya es un monto real (caso Las Torres), no se pisa nada.

            header_date = _parse_date(header_row)
            if header_date:
                subitem_dates = [
                    d for d in (_parse_date(row_by_bsl_id.get(bid)) for bid in subitem_bsl_ids)
                    if d and d > header_date
                ]
                if subitem_dates:
                    header_nights_by_bsl_id[header_bsl_id] = (max(subitem_dates) - header_date).days

        return header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids
    except Exception:
        _log.exception("No se pudo calcular el precio/noches real de paquetes (BSL/BSD vía Voucher_Number)")
        return {}, {}, set()


def _fold_packages(day_rows, header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids):
    """
    Oculta, dentro de las filas de un mismo día, las que son subitems de un paquete — "solo
    deben figurar estos encabezados y no los items que incluye dentro" — y les pisa a los
    encabezados el monto y/o las noches reales calculadas en _fetch_package_pricing (ver ahí
    los dos tipos de paquete y por qué cada uno necesita su propio cálculo). El cruce se hace
    por Voucher_Number (== BSL_ID).
    """
    if not excluded_bsl_ids:
        return day_rows

    kept_rows = []
    for row in day_rows:
        bsl_id = row.get("Voucher_Number")
        if bsl_id in excluded_bsl_ids:
            continue
        if bsl_id in header_amount_by_bsl_id or bsl_id in header_nights_by_bsl_id:
            row = dict(row)
            if bsl_id in header_amount_by_bsl_id:
                row["Service_Sell"] = header_amount_by_bsl_id[bsl_id]
            if bsl_id in header_nights_by_bsl_id:
                row["Nights"] = header_nights_by_bsl_id[bsl_id]
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

# La categoría Hertz del auto (ej. "H2") viene mencionada dentro de la propia nota ODE del
# alquiler principal — confirmado con datos reales: "... or similar – Manual (Category H2)".
_CAR_CATEGORY_RE = re.compile(r'Category\s+([A-Za-z0-9]+)', re.IGNORECASE)


def _car_category_photo(title_note, location_code):
    """Foto de CarCategory (tarifario de Alquiler de Vehículo, tariff/views/car_hire.py) para
    el auto principal — matcheada por el código de categoría (extraído de title_note, ej. "H2")
    + el destino (Location.code, que en este módulo son los mismos códigos de 3 letras de
    Tourplan, ej. "BRC"). None si no matchea nada o la categoría no tiene foto cargada."""
    match = _CAR_CATEGORY_RE.search(title_note or "")
    if not match:
        return None
    category = (
        CarCategory.objects
        .filter(code__iexact=match.group(1), location__code=location_code)
        .first()
    )
    if not category or not category.pic1_url:
        return None
    pic = category.pic1_url
    # A diferencia de Product/Supplier.pic1_url (nombre de archivo suelto en static/tariff/),
    # el de CarCategory se sube vía default_storage y ya es una URL completa (ver
    # category_create en car_hire.py) — se usa tal cual, sin resolver con static().
    return pic if (pic.startswith("http") or pic.startswith("/")) else None


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


def _resolve_line_data(row, all_notes, supplier_photos=None, supplier_descriptions=None,
                        supplier_prepayments=None, supplier_important_notes=None,
                        file_notes_imb=None, is_first_car_item=False):
    """
    Junta todo lo que hace falta para una línea (match de producto, notas DAY/ODE/OIE/FH1-3/
    ODX/CCP/IMS/IMP, foto, desglose de habitación, si es upgrade opcional) — llamado antes de
    la transacción de Django, con las notas de TODO el itinerario ya traídas en una sola
    consulta batch (all_notes).

    is_first_car_item: True para el primer ítem CI (Car Item) de una tanda de alquiler de
    vehículo — ver el uso de "CI" más abajo para el porqué.

    BIT ya NO se resuelve acá: es una nota única a nivel de TODA la booking (no por línea),
    ver _fetch_booking_important_note, llamada una sola vez desde _populate_from_tourplan.

    Devuelve (line_kwargs, cpp_info): line_kwargs es lo que se guarda en ItineraryLine
    (incluye missing_prepayment); cpp_info es un dict con supplier_code/location_name/
    supplier_name/text (o None si no hay), que el caller acumula aparte con el formato
    "Destino - Proveedor - Nota" (requisito de prepago del proveedor, ver
    _fetch_supplier_prepayments).
    """
    supplier_code = (row.get("Supplier_Code") or "").strip()
    option_code = (row.get("Product_Option_Code") or "").strip()
    location_code = (row.get("Product_Location") or "").strip()
    service_code = (row.get("Product_service") or "").strip().upper()
    is_hotel = service_code == "AC"
    # Líneas "informativas" de vuelo que Tourplan arma con proveedor NOAPLI ("No aplica") y
    # producto VUELOS — no tienen tarifa ni proveedor real, son un placeholder para que el
    # itinerario público muestre el dato de pickup/dropoff (si está cargado) en un formato fijo,
    # en vez del nombre crudo "NO APLICA" o una nota OIE que no existe para este tipo de línea.
    is_flight_placeholder = supplier_code == "NOAPLI" and option_code == "VUELOS"
    product = _lookup_product(option_code, supplier_code, location_code)
    notes = all_notes.get((option_code, supplier_code, location_code), {})

    def _clean_note(category):
        text = notes.get(category)
        if not text or not _looks_like_text_note(text):
            return ""
        # strip_html_keep_newlines (no strip_html a secas) — esta nota puede tener varias
        # líneas reales en el HTML de origen (<br>, <p>...) y se muestra con |linebreaksbr en
        # el template; strip_html colapsa todo a un único renglón y se perdían los saltos
        # (confirmado con una nota IMP real de varias líneas — reserva ALFI121940, proveedor
        # 36, producto HDS006 — que se veía toda junta).
        cleaned = strip_html_keep_newlines(text)
        # Si la única nota disponible está en alemán (sin alternativa en inglés para elegir),
        # no la mostramos — mismo criterio que "sin descriptivo real, no mostrar nada".
        if _looks_german(cleaned):
            return ""
        return cleaned

    title_note = _clean_note("ODE") if is_hotel else _clean_note("DAY")
    if service_code == "CI":
        # Alquiler de vehículo: cada ítem "CI" (pickup, seguro, tasa, conductor adicional,
        # etc.) trae normalmente el texto real en DAY. La única excepción es el primero de la
        # tanda (el alquiler original) — confirmado con datos reales (ALFI119691, día 12): su
        # nota DAY es una plantilla sin completar ("Pick up: X (mes y día)..."), mientras que
        # la categoría y modelo real del auto está en ODE. Al revés que el resto de los
        # servicios (donde ODE es solo para alojamiento). Si a algún ítem CI le falta la nota
        # que le toca, se cae a la otra como respaldo, en vez de mostrar el nombre del
        # proveedor (confirmado real: CAR012 "Airport Tax" y CAR013 "Additional Driver" no
        # tienen nota DAY en absoluto, solo ODE).
        if is_first_car_item:
            title_note = _clean_note("ODE") or _clean_note("DAY")
        else:
            title_note = _clean_note("DAY") or _clean_note("ODE")
    if is_hotel:
        # Descripción real del proveedor (SDE, ver _fetch_supplier_descriptions) — no la nota
        # OIE, que es a nivel producto/habitación y no existe para alojamiento.
        supplier_desc = (supplier_descriptions or {}).get(supplier_code)
        content_note = (
            strip_html_keep_newlines(supplier_desc).strip()
            if supplier_desc and _looks_like_text_note(supplier_desc) else ""
        )
    else:
        content_note = _clean_note("OIE")

    if service_code == "CI" and is_first_car_item:
        # Debajo de la categoría/modelo del auto (título, ver arriba): pickup, drop-off y
        # cantidad de días del alquiler, calculados con los mismos campos pickup/dropoff (lugar
        # y horario) que ya se usan para el placeholder de vuelo, más pickup_date/dropoff_date
        # (agregado a la query — ver _ITINERARY_BASE_COLUMNS en quality_ai.py) para la duración.
        # Reemplaza el OIE (descriptivo) en vez de sumarse — a pedido explícito, este ítem no
        # debe mostrar la nota DAY/OIE, solo este bloque.
        content_note = ""
        pickup = _txt(_ci_get(row, "pickup"))
        dropoff = _txt(_ci_get(row, "dropoff"))
        pickup_time = _txt(_ci_get(row, "pickup_time"))
        dropoff_time = _txt(_ci_get(row, "dropoff_time"))
        pickup_date = _to_date(_ci_get(row, "pickup_date"))
        dropoff_date = _to_date(_ci_get(row, "dropoff_date"))

        car_lines = []
        if pickup:
            car_lines.append(f"Pick-up: {pickup} - {pickup_time} hs" if pickup_time else f"Pick-up: {pickup}")
        if dropoff:
            car_lines.append(f"Drop-off: {dropoff} - {dropoff_time} hs" if dropoff_time else f"Drop-off: {dropoff}")
        if pickup_date and dropoff_date:
            days_count = (dropoff_date - pickup_date).days
            if days_count > 0:
                car_lines.append(f"{days_count} days")
        if car_lines:
            content_note = "\n".join(car_lines)

    flight_text = ""
    if is_flight_placeholder:
        pickup = _txt(_ci_get(row, "pickup"))
        dropoff = _txt(_ci_get(row, "dropoff"))
        pickup_time = _txt(_ci_get(row, "pickup_time"))
        dropoff_time = _txt(_ci_get(row, "dropoff_time"))
        title_note = "Flight"
        content_note = ""  # no es un descriptivo, va como nota resaltada (conditions_note) más abajo
        if pickup and dropoff and pickup_time and dropoff_time:
            flight_text = (
                f"Your Flight details (not provided by Aliwen): {pickup} / {dropoff} "
                f"- {pickup_time}/{dropoff_time} hs"
            )
        else:
            flight_text = "Your Flight details (not provided by Aliwen): details to be informed"

    room_summary = _room_summary_for(row) if is_hotel else ""

    # IMS: para alojamiento vive a nivel PROVEEDOR (ver _fetch_supplier_important_notes), no
    # de catálogo — a pedido explícito. Para el resto de los servicios sigue siendo de
    # catálogo, igual que CCP/IMP.
    if is_hotel:
        supplier_ims = (supplier_important_notes or {}).get(supplier_code)
        ims_text = (
            strip_html_keep_newlines(supplier_ims).strip()
            if supplier_ims and _looks_like_text_note(supplier_ims) else ""
        )
    else:
        ims_text = _clean_note("IMS")

    # IMB: nota específica de ESTE archivo (ver _fetch_file_specific_notes), nunca de
    # catálogo — se busca por Voucher_Number (== BSL_ID real de esta línea reservada), para
    # CUALQUIER tipo de servicio.
    imb_raw = (file_notes_imb or {}).get(row.get("Voucher_Number"))
    imb_text = (
        strip_html_keep_newlines(imb_raw).strip()
        if imb_raw and _looks_like_text_note(imb_raw) else ""
    )

    conditions_note = "\n".join(
        text for text in (_clean_note("CCP"), ims_text, _clean_note("IMP"), imb_text) if text
    )
    rvt2 = (row.get("Rate_Voucher_Text2") or "").strip()
    if rvt2:
        conditions_note = f"{conditions_note}\n{rvt2}" if conditions_note else rvt2
    if flight_text:
        conditions_note = f"{flight_text}\n{conditions_note}" if conditions_note else flight_text

    # Antes se detectaba buscando "option" en Service_StatusName, pero ese texto viene en el
    # idioma configurado en Tourplan (confirmado con datos reales: "Opcional", en español, que
    # no contiene "option") — poco confiable. El código de status SÍ es estable: 'OP' está
    # confirmado contra la tabla sst de Tourplan (sst.INCLUDEINTOTAL = False para 'OP', o sea
    # que ni el propio Tourplan lo suma al total).
    status_code = (row.get("Service_status") or "").strip().upper()
    is_optional = status_code == "OP"

    # Hoteles: hasta 3 fotos, con prioridad FH1-3 (producto/habitación) por sobre DH1-3
    # (proveedor) — al revés de como estaba antes. Confirmado por el usuario viendo fotos
    # reales: las DH1-3 (proveedor) son de menor resolución y se pixelaban en el carrusel más
    # grande; las FH1-3 (producto) están en buena resolución. DH1-3 queda como respaldo para
    # cuando el producto puntual no tiene fotos propias cargadas. El resto de los servicios
    # solo tiene una (ODX) hasta donde vimos en los datos reales.
    if is_hotel:
        sp = (supplier_photos or {}).get(supplier_code, {})
        image_url = (
            _resolve_photo(notes.get("FH1")) or _resolve_photo(sp.get("DH1"))
            or _photo_url_for(product, supplier_code, allow_supplier_fallback=True)
        )
        image_url_2 = _resolve_photo(notes.get("FH2")) or _resolve_photo(sp.get("DH2"))
        image_url_3 = _resolve_photo(notes.get("FH3")) or _resolve_photo(sp.get("DH3"))
    else:
        image_url = _resolve_photo(notes.get("ODX")) or _photo_url_for(product, supplier_code)
        image_url_2 = None
        image_url_3 = None

    if service_code == "CI" and is_first_car_item:
        # Foto de la categoría del auto (tarifario de Alquiler de Vehículo), no la de ODX/
        # producto — a pedido explícito, para que se vea el modelo real contratado.
        category_photo = _car_category_photo(title_note, location_code)
        if category_photo:
            image_url = category_photo

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
    # CPP = requisito de prepago del proveedor — nota a nivel PROVEEDOR (ver
    # _fetch_supplier_prepayments), no de producto/catálogo. A pedido explícito, en
    # "Prepayments required" SOLO aparecen hoteles (AC) — un proveedor de otro tipo nunca
    # genera renglón ahí, tenga o no nota CPP cargada. Un hotel SIEMPRE debe traer renglón: si
    # no tiene nota cargada en Tourplan, se muestra "To be informed" en vez de omitirlo, y
    # queda marcado (missing_prepayment) para que el editor avise al staff — ver
    # _missing_hotel_prepayments.
    if is_hotel:
        supplier_prepayment = (supplier_prepayments or {}).get(supplier_code)
        cpp_text = (
            strip_html_keep_newlines(supplier_prepayment).strip()
            if supplier_prepayment and _looks_like_text_note(supplier_prepayment) else ""
        )
        line_kwargs["missing_prepayment"] = not cpp_text
        # cpp_info: lo que necesita el caller para armar el renglón "Destino - Proveedor -
        # Nota" del campo de prepagos (ver _populate_from_tourplan).
        cpp_info = {
            "supplier_code": supplier_code,
            "location_name": line_kwargs["location_name"] or location_code,
            "supplier_name": line_kwargs["supplier_name"] or supplier_code,
            "text": cpp_text or "To be informed",
        }
    else:
        line_kwargs["missing_prepayment"] = False
        cpp_info = None
    return line_kwargs, cpp_info


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
    supplier_prepayments = {}
    supplier_important_notes = {}
    file_notes_imb = {}
    booking_bit_note = ""
    passenger_assignments = {}
    passenger_details = {}
    header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids = {}, {}, set()
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
            # CPP (prepago) se muestra SOLO para hoteles — a pedido explícito, un proveedor
            # que no sea de alojamiento nunca aparece en "Prepayments required", tenga o no
            # nota CPP cargada — ver _fetch_supplier_prepayments.
            # IMB (ver _fetch_file_specific_notes) se busca por Voucher_Number == BSL_ID real
            # de cada línea reservada, para TODOS los servicios.
            bsl_ids = [row.get("Voucher_Number") for row in all_rows if row.get("Voucher_Number")]
            supplier_photos = _fetch_supplier_photos(cursor, hotel_supplier_codes)
            supplier_descriptions = _fetch_supplier_descriptions(cursor, hotel_supplier_codes)
            supplier_prepayments = _fetch_supplier_prepayments(cursor, hotel_supplier_codes)
            supplier_important_notes = _fetch_supplier_important_notes(cursor, hotel_supplier_codes)
            file_notes_imb = _fetch_file_specific_notes(cursor, bsl_ids, "IMB")
            # BIT (ver _fetch_booking_important_note) es UNA sola nota para TODA la booking,
            # se busca una única vez acá, no por línea.
            booking_bit_note = _fetch_booking_important_note(cursor, all_rows)
            # Pasajeros nombrados por línea (ver _fetch_passenger_assignments/
            # _fetch_passenger_details) — reemplaza los placeholders "Adult 1"/"Adult 2" del
            # resumen de pasajeros en Overview por nombre/edad/total real por persona.
            passenger_assignments = _fetch_passenger_assignments(cursor, bsl_ids)
            all_pxn_ids = {pxn_id for pxn_ids in passenger_assignments.values() for pxn_id in pxn_ids}
            passenger_details = _fetch_passenger_details(cursor, all_pxn_ids)
            header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids = _fetch_package_pricing(cursor, all_rows)
        finally:
            conn.close()
    except Exception:
        _log.exception("Itinerario %s: no se pudo conectar a Tourplan para traer notas DAY/ODE/OIE/fotos", itinerary.id)
        all_notes = {}

    # Paquetes: ocultar subitems y pisarle a los encabezados el monto y/o las noches reales
    # (ver _fetch_package_pricing) ANTES de resolver notas/fotos por línea, para que las
    # líneas ocultas ni siquiera lleguen a generarse como ItineraryLine.
    grouped = [
        (day_date, _fold_packages(day_rows, header_amount_by_bsl_id, header_nights_by_bsl_id, excluded_bsl_ids))
        for day_date, day_rows in grouped
    ]

    def _counts_toward_total(line_kwargs):
        """Mismo criterio usado para itinerary.total_amount: ni opcionales/Upgrade, ni Not
        Included, ni el placeholder de vuelo — ninguno de estos lleva precio real que
        repartir entre pasajeros."""
        return (
            not line_kwargs.get("is_optional")
            and line_kwargs.get("service_code") != "IN"
            and not (line_kwargs.get("supplier_code") == "NOAPLI" and line_kwargs.get("option_code") == "VUELOS")
        )

    days_data = []
    # BIT (ver _fetch_booking_important_note) es una sola nota para toda la booking — no hay
    # nada que deduplicar por línea, se muestra tal cual viene (ya puede mencionar varios
    # proveedores dentro del mismo texto, ej. "Aliwen Exclusive Amenities & Agreements: Palo
    # Santo: ... Patagonia Queen: ...").
    important_comments = [booking_bit_note] if booking_bit_note else []
    prepayments_required = []
    seen_prepayment_suppliers = set()
    # Total real por pasajero (ver ItineraryPassenger) — NO es el total dividido en partes
    # iguales: cada línea reparte su propio monto solo entre los pasajeros que tiene
    # asignados puntualmente (ver _fetch_passenger_assignments). pxn_order preserva el orden
    # de primera aparición para mostrarlos siempre en el mismo orden.
    passenger_totals = {}
    pxn_order = []
    for day_date, day_rows in grouped:
        lines_data = []
        prev_was_car_item = False
        for row in day_rows:
            # El primero de una tanda de ítems CI (alquiler de vehículo) necesita otra nota
            # (ver _resolve_line_data) — se detecta por ser CI sin otro CI justo antes, dentro
            # del mismo día (day_rows ya viene ordenado por secuencia real de Tourplan).
            is_car_item = (row.get("Product_service") or "").strip().upper() == "CI"
            is_first_car_item = is_car_item and not prev_was_car_item
            prev_was_car_item = is_car_item
            line_kwargs, cpp_info = _resolve_line_data(
                row, all_notes, supplier_photos, supplier_descriptions, supplier_prepayments,
                supplier_important_notes, file_notes_imb,
                is_first_car_item=is_first_car_item,
            )
            lines_data.append(line_kwargs)
            # "Destino - Proveedor - Nota", sin repetir proveedor (un mismo hotel puede
            # aparecer en varias líneas/días de la misma estadía) — a pedido explícito, ej.
            # "Buenos Aires - Palo Santo - No prepayments".
            if cpp_info and cpp_info["supplier_code"] not in seen_prepayment_suppliers:
                seen_prepayment_suppliers.add(cpp_info["supplier_code"])
                prepayments_required.append(
                    f"{cpp_info['location_name']} - {cpp_info['supplier_name']} - {cpp_info['text']}"
                )
            line_pxn_ids = passenger_assignments.get(row.get("Voucher_Number"))
            if line_pxn_ids and line_kwargs.get("amount") and _counts_toward_total(line_kwargs):
                unique_pxn_ids = list(dict.fromkeys(line_pxn_ids))  # sin duplicar si un pax aparece 2 veces en la misma línea
                share = line_kwargs["amount"] / len(unique_pxn_ids)
                for pxn_id in unique_pxn_ids:
                    if pxn_id not in passenger_totals:
                        passenger_totals[pxn_id] = 0.0
                        pxn_order.append(pxn_id)
                    passenger_totals[pxn_id] += share
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
        itinerary.passengers.all().delete()  # idempotente, mismo criterio que days/lines
        for pxn_order_index, pxn_id in enumerate(pxn_order):
            details = passenger_details.get(pxn_id) or {}
            ItineraryPassenger.objects.create(
                itinerary=itinerary,
                order=pxn_order_index,
                full_name=details.get("full_name") or "",
                age=details.get("age"),
                total_amount=passenger_totals.get(pxn_id),
            )
        itinerary.synced_from_tourplan_at = timezone_now()
        itinerary.important_comments = "\n\n".join(important_comments)
        itinerary.prepayments_required = "\n\n".join(prepayments_required)
        if rows:
            itinerary.pax_count = _int_or_zero(rows[0].get("Total_Pax")) or itinerary.pax_count
            itinerary.consultant_name = (rows[0].get("Consultant") or "").strip() or itinerary.consultant_name
            # Monto total del itinerario: suma de las líneas incluidas (ver _counts_toward_total)
            # — no el campo Entry.amount, que lo sincroniza un proceso aparte y puede no estar
            # actualizado todavía para una reserva nueva (visto en un caso real: los ítems
            # traían precio bien pero el total del itinerario quedaba en 0 por esto).
            itinerary.total_amount = sum(
                (line_kwargs.get("amount") or 0)
                for _, lines_data in days_data
                for line_kwargs in lines_data
                if _counts_toward_total(line_kwargs)
            )
        itinerary.save(update_fields=[
            "synced_from_tourplan_at", "important_comments", "prepayments_required",
            "pax_count", "consultant_name", "total_amount",
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


def _missing_map_locations(itinerary):
    """Destinos (líneas Welcome) de este itinerario que no se van a poder ubicar en el mapa
    público — porque no hay ningún Location con ese código, o le faltan las coordenadas.
    "Activo en el tarifario" (Location.isActivated) es un toggle sin relación con esto — solo
    controla si el destino aparece en el desplegable de filtro de tariff.html — así que
    NO se filtra por él acá. Devuelve nombres para mostrar en el aviso del editor, en orden
    de aparición y sin duplicados."""
    seen = set()
    missing = []
    for day in itinerary.days.prefetch_related("lines").all():
        for line in day.lines.all():
            if line.service_code != "WE" or not line.location_code or line.location_code in seen:
                continue
            seen.add(line.location_code)
            location = Location.objects.filter(code=line.location_code).first()
            if not location or location.latitude is None or location.longitude is None:
                missing.append(line.location_name or line.location_code)
    return missing


def _compute_map_points(we_occurrences, total_days):
    """A partir de las ocurrencias de líneas Welcome — [(day_index, location_code,
    location_name, line), ...], en orden, SIN deduplicar — y de la cantidad total de días del
    itinerario, arma los puntos del mapa con su rango de días (ver pestaña "Map"). Un punto
    por cada VISITA (revisitar un destino más adelante en el viaje es un punto nuevo, con su
    propio rango). Salta los destinos sin Location o sin coordenadas cargadas — no rompe el
    mapa, simplemente no los muestra (ya se avisó de esto en el editor, ver
    _missing_map_locations). "Activo en el tarifario" no aplica acá (ver esa función)."""
    points = []
    for i, (day_index, location_code, location_name, _line) in enumerate(we_occurrences):
        location = Location.objects.filter(code=location_code).first()
        if not location or location.latitude is None or location.longitude is None:
            continue
        day_start = day_index + 1
        day_end = (we_occurrences[i + 1][0] + 1) if i + 1 < len(we_occurrences) else total_days
        points.append({
            "name": location_name or location.name,
            "lat": location.latitude,
            "lng": location.longitude,
            "day_start": day_start,
            "day_end": day_end,
        })
    return points


def _build_quote_brief_blocks(quote_brief_rows):
    """
    Itinerary Quote Brief: bloques cortados por cada línea "Welcome" (no por location_name de
    cada fila) — así un destino visitado dos veces en el viaje (ej. "Welcome to Buenos Aires!"
    al principio y "Welcome back to Buenos Aires!" más adelante) queda en dos bloques
    separados en vez de mezclarse. La línea Welcome en sí no se muestra como fila, solo da el
    título del bloque (nombre completo del destino).

    Corte adicional: las líneas sin destino propio — vuelos (is_flight_placeholder) e ítems
    "Aliwen Green" (is_aliwen_green_item, código SAYALI/proveedor Say Green, que Tourplan
    agrega siempre al final de la reserva) — van en su propio bloque, sin título, separadas de
    lo que haya alrededor — pero si hay dos o más seguidas, quedan juntas en UN solo bloque en
    vez de uno por cada una. Al terminar, se retoma un bloque nuevo con el MISMO título de
    destino de antes (no se perdió el destino, no hubo un Welcome de por medio).

    quote_brief_rows: [(day, line, end_date), ...] en orden cronológico (ver
    public_itinerary_view). Devuelve [(title_o_None, rows), ...].
    """
    blocks = []
    current_title = None
    current_rows = []
    in_standalone_block = False

    def flush_block(title, rows):
        if title is not None or rows:
            blocks.append((title, rows))

    for day, line, end_date in quote_brief_rows:
        is_standalone = line.is_flight_placeholder or line.is_aliwen_green_item
        if line.service_code == "WE":
            # Si veníamos acumulando líneas sin destino y el próximo Welcome llega pegado (sin
            # ningún ítem normal en el medio), el bloque a cerrar es el de esas líneas — sin
            # título, no el del destino anterior.
            flush_block(None if in_standalone_block else current_title, current_rows)
            current_title = line.custom_title or line.location_name or line.location_code or ""
            current_rows = []
            in_standalone_block = False
        elif is_standalone:
            if not in_standalone_block:
                flush_block(current_title, current_rows)
                current_rows = []
                in_standalone_block = True
            current_rows.append((day, line, end_date))
        else:
            if in_standalone_block:
                flush_block(None, current_rows)
                current_rows = []
                in_standalone_block = False
            current_rows.append((day, line, end_date))
    if in_standalone_block:
        flush_block(None, current_rows)
    else:
        flush_block(current_title, current_rows)
    return blocks


def _fetch_special_dates(is_program, valid_until_date, we_occurrences, days, destination_location_cache):
    """
    "Special Dates" para la pestaña Good to Know — a partir del calendario externo de la app
    (ExternalCalendarEntry), NO de Tourplan. Mismo mecanismo de matcheo por destino/rango de
    fechas que ya usa el cotizador online de auto (ver
    tariff/views/car_hire.py:_special_calendar_hits): un entry con location=None aplica a
    CUALQUIER destino.

    - Itinerarios "Programa" (reutilizables, sin fechas reales, ver is_program): se muestran
      los special dates entre HOY y la fecha de validez (valid_until_date), para cualquiera de
      los destinos del itinerario (o "todos los destinos").
    - Resto de los itinerarios: un special date se muestra solo si su rango se solapa con las
      fechas REALES de estadía en ESE destino puntual (in/out del tramo del viaje ahí), o si
      aplica a "todos los destinos" y se solapa con esas mismas fechas.

    we_occurrences: [(day_index, location_code, location_name, line), ...] en orden, sin
    dedupe (ver public_itinerary_view). days: lista de ItineraryDay en orden.
    destination_location_cache: {location_code: Location o None}, ya resuelto por el caller.

    Devuelve una lista de dicts {"name", "date_from", "date_to", "notes", "destination"} en
    orden cronológico, sin duplicar el mismo entry para el mismo destino.
    """
    seen = set()
    hits = []

    def add(entry, destination_name):
        key = (entry.id, destination_name)
        if key in seen:
            return
        seen.add(key)
        hits.append({
            "name": entry.name or entry.get_category_display(),
            "date_from": entry.date_from,
            "date_to": entry.date_to,
            "notes": entry.notes,
            "destination": destination_name,
        })

    if is_program:
        today = timezone_now().date()
        if not valid_until_date or valid_until_date < today:
            return []
        location_ids = {loc.id for loc in destination_location_cache.values() if loc}
        qs = (
            ExternalCalendarEntry.objects
            .filter(Q(location_id__in=location_ids) | Q(location__isnull=True))
            .filter(date_from__lte=valid_until_date, date_to__gte=today)
            .select_related("location")
            .order_by("date_from")
        )
        for entry in qs:
            add(entry, entry.location.name if entry.location else "All destinations")
        return hits

    for i, (day_index, location_code, _location_name, _line) in enumerate(we_occurrences):
        start_day = days[day_index]
        if not start_day.date:
            continue
        end_index = we_occurrences[i + 1][0] if i + 1 < len(we_occurrences) else len(days) - 1
        end_day = days[end_index]
        end_date = end_day.date or start_day.date
        location = destination_location_cache.get(location_code)
        qs = (
            ExternalCalendarEntry.objects
            .filter(Q(location_id=location.id if location else None) | Q(location__isnull=True))
            .filter(date_from__lte=end_date, date_to__gte=start_day.date)
            .select_related("location")
            .order_by("date_from")
        )
        for entry in qs:
            add(entry, entry.location.name if entry.location else "All destinations")

    hits.sort(key=lambda h: h["date_from"])
    return hits


def _missing_hotel_prepayments(itinerary):
    """Proveedores de alojamiento (AC) de este itinerario sin nota de prepago (CPP) cargada en
    Tourplan — un hotel SIEMPRE debería traer una (ver _resolve_line_data/
    _fetch_supplier_prepayments). Devuelve nombres de proveedor para el aviso del editor, en
    orden de aparición y sin duplicados; el staff completa el faltante a mano en el campo
    "Prepayments required" (PublicItinerary.prepayments_required)."""
    seen = set()
    missing = []
    for day in itinerary.days.prefetch_related("lines").all():
        for line in day.lines.all():
            if not line.missing_prepayment or line.supplier_code in seen:
                continue
            seen.add(line.supplier_code)
            missing.append(line.supplier_name or line.supplier_code)
    return missing


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
        "missing_map_locations": _missing_map_locations(itinerary),
        "missing_hotel_prepayments": _missing_hotel_prepayments(itinerary),
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
        .select_related("entry", "entry__trip")
        .first()
    )
    if not itinerary:
        return render(request, "intranet/itinerary_public.html", {"unavailable": True}, status=404)

    # Versión "Programa": itinerarios reutilizables (mismo contenido para distintos grupos/
    # fechas), detectada automáticamente por el status de la Entry — ver STATUS_OPTIONS en
    # models.py. Acá no hay fechas reales que mostrarle al cliente (son solo de referencia
    # interna para armar el itinerario), así que en vez de fechas se muestra "Day N" y, en vez
    # del rango de fechas del viaje, la validez de la oferta (Trip.travelling_date).
    is_program = itinerary.entry.status == "Programa"
    valid_until_date = itinerary.entry.trip.travelling_date if itinerary.entry.trip else None

    days = list(itinerary.days.prefetch_related("lines").all())
    # Separar líneas incluidas de las opcionales/upgrade (mismo día, pero se muestran en
    # secciones distintas — "regular_days"/"optional_days" son listas de (day, lines)).
    regular_days = []
    optional_days = []
    accommodation_cards = []
    quote_brief_rows = []  # [(day, line, end_date), ...] en orden cronológico, sin agrupar por destino
    has_car_rental = False
    destination_codes = []  # [(location_code, location_name), ...] en orden de aparición, sin duplicados
    seen_destination_codes = set()
    we_occurrences = []  # [(day_index, location_code, location_name, line), ...] — CADA visita, sin dedupe
    destination_location_cache = {}  # location_code -> Location o None, para no repetir la consulta
    for day_index, day in enumerate(days):
        lines = list(day.lines.all())
        # Marca (en memoria, no persiste) cuál es el primer ítem CI de una tanda de alquiler de
        # auto dentro del día — mismo criterio que is_first_car_item al sincronizar (ver
        # _resolve_line_data). Se usa en el template para mostrar en Overview el bloque de
        # pickup/dropoff/días de ESTE ítem puntual, sin abrir la puerta al descriptivo completo
        # del resto de las líneas (que ahí sigue sin mostrarse).
        prev_was_car_item = False
        for line in lines:
            is_car_item = line.service_code == "CI"
            line.is_main_car_item = is_car_item and not prev_was_car_item
            if line.is_main_car_item:
                has_car_rental = True
            prev_was_car_item = is_car_item
            # Destinos para la pestaña "Destinations": uno por cada "Welcome" (mismo criterio
            # que ya usamos para los bloques de Itinerary in Brief), sin duplicar si se repite.
            if line.service_code == "WE" and line.location_code:
                we_occurrences.append((day_index, line.location_code, line.location_name, line))
                if line.location_code not in seen_destination_codes:
                    seen_destination_codes.add(line.location_code)
                    destination_codes.append((line.location_code, line.location_name))
                if line.location_code not in destination_location_cache:
                    destination_location_cache[line.location_code] = Location.objects.filter(code=line.location_code).first()
                dest_location = destination_location_cache[line.location_code]
                # Fotos del destino (Location de la app, no Tourplan) para mostrar en Day by
                # Day debajo del nombre — una al lado de la otra, no en carrusel.
                line.destination_photos = [
                    p for p in (
                        _resolve_static_pic(dest_location.pic1_url),
                        _resolve_static_pic(dest_location.pic2_url),
                        _resolve_static_pic(dest_location.pic3_url),
                    ) if p
                ] if dest_location else []
        regular_lines = [line for line in lines if not line.is_optional]
        optional_lines = [line for line in lines if line.is_optional]
        # Siempre se agrega el día a Day by Day, aunque no tenga ningún ítem incluido — antes
        # un día sin líneas quedaba directamente afuera del itinerario público; ahora se
        # muestra igual (con su fecha/foto) y el template pone un "Day at leisure" cuando no
        # hay nada que listar.
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
                    # Para la versión "Programa" (ver is_program) — día N a día M en vez de
                    # fechas de calendario reales.
                    "day_start": day.order + 1,
                    "day_end": day.order + 1 + nights,
                })
            # Fecha de fin del ítem para la tabla de Itinerary in Brief. Tourplan trae Nights=1
            # como valor "de relleno" en un montón de servicios que no son alojamiento (no es
            # una noche real ahí) — mostrarla para cualquier línea con Nights>0 generaba fechas
            # de fin espurias en casi todo el itinerario. Alcance acotado:
            #   - Alojamiento (AC): siempre, es la fecha de checkout real.
            #   - Not Included (IN): solo si la diferencia es de 2 noches o más (suele ser un
            #     cargo — ej. city tax — atado a varias noches de una estadía; con 1 sola noche
            #     es el mismo ruido que en el resto de los servicios).
            #   - Cualquier otro tipo de servicio: nunca.
            end_date = None
            if day.date and line.nights:
                if line.service_code == "AC":
                    end_date = day.date + timedelta(days=line.nights)
                elif line.service_code == "IN" and line.nights >= 2:
                    end_date = day.date + timedelta(days=line.nights)
            quote_brief_rows.append((day, line, end_date))

    quote_brief_blocks = _build_quote_brief_blocks(quote_brief_rows)

    # Day by Day: antes del nombre de un destino, si el anterior (inmediatamente antes en el
    # viaje) tiene coordenadas cargadas y este también, se arma un mini-mapa mostrando solo
    # ese tramo (mismo mecanismo de curva+flecha que la pestaña Map, pero enfocado nada más a
    # estos dos puntos). Si a cualquiera de los dos le faltan coordenadas, no se arma nada —
    # no rompe la vista, solo no aparece el mini-mapa para esa transición puntual.
    we_resolved = []
    for day_index, location_code, location_name, we_line in we_occurrences:
        location = destination_location_cache.get(location_code)
        has_coords = bool(location and location.latitude is not None and location.longitude is not None)
        we_resolved.append({
            "line": we_line,
            "name": location_name or (location.name if location else location_code),
            "lat": location.latitude if has_coords else None,
            "lng": location.longitude if has_coords else None,
            "has_coords": has_coords,
        })
    for i in range(1, len(we_resolved)):
        prev_occ, curr_occ = we_resolved[i - 1], we_resolved[i]
        if prev_occ["has_coords"] and curr_occ["has_coords"]:
            curr_occ["line"].route_segment_json = json.dumps({
                "from": {"lat": prev_occ["lat"], "lng": prev_occ["lng"], "name": prev_occ["name"]},
                "to": {"lat": curr_occ["lat"], "lng": curr_occ["lng"], "name": curr_occ["name"]},
            })

    dated_days = [d for d in days if d.date]
    nights_total = (dated_days[-1].date - dated_days[0].date).days if len(dated_days) >= 2 else 0
    days_total = nights_total + 1 if dated_days else len(days)

    # Passenger Summary: nombre/apellido real + edad (si está cargada) + el total que le
    # corresponde a ESE pasajero según sus líneas asignadas (ver ItineraryPassenger, sincronizado
    # en _populate_from_tourplan vía _fetch_passenger_assignments/_fetch_passenger_details) — no
    # el total dividido en partes iguales. Fallback a "Adult N" + total/pax_count (como antes)
    # si Tourplan no tenía pasajeros nombrados asignados a ninguna línea (ej. itinerarios
    # sincronizados antes de esta funcionalidad, o una reserva sin ese dato cargado).
    # "Per person" del price-hero es siempre el promedio simple (total/pax_count) — un
    # resumen general, distinto del total real por pasajero de la tabla de abajo.
    per_person_amount = (
        itinerary.total_amount / itinerary.pax_count
        if itinerary.total_amount and itinerary.pax_count else None
    )
    named_passengers = list(itinerary.passengers.all())
    if named_passengers:
        passengers = [
            {
                "name": f"{p.full_name} - {p.age}" if p.full_name and p.age else (p.full_name or f"Adult {i + 1}"),
                "amount": p.total_amount,
            }
            for i, p in enumerate(named_passengers)
        ]
    else:
        passengers = [
            {"name": f"Adult {i + 1}", "amount": per_person_amount}
            for i in range(itinerary.pax_count or 0)
        ]

    # Condiciones generales de Alquiler de Vehículo (CarHireConfig, tariff/views/car_hire.py) —
    # se muestran debajo del bloque de pickup/dropoff/días del auto principal. Es una
    # configuración global (no algo propio de esta reserva), así que se trae en el momento en
    # vez de guardarla en el snapshot — si cambia el texto general, ya se refleja sin necesidad
    # de resincronizar cada itinerario publicado.
    car_hire_conditions_text = CarHireConfig.get_solo().conditions_text if has_car_rental else ""

    # Pestaña "Destinations": fotos + descriptivo de cada destino visitado, desde el propio
    # tarifario de la app (Location), no desde Tourplan. Se salta un destino si no existe en
    # el tarifario o no tiene ni foto ni descripción cargada (nada útil para mostrar).
    itinerary_destinations = []
    for location_code, location_name in destination_codes:
        location = Location.objects.filter(code=location_code).first()
        if not location:
            continue
        photos = [
            p for p in (
                _resolve_static_pic(location.pic1_url),
                _resolve_static_pic(location.pic2_url),
                _resolve_static_pic(location.pic3_url),
            ) if p
        ]
        if not photos and not location.description:
            continue
        itinerary_destinations.append({
            "name": location_name or location.name,
            "description": location.description,
            "photos": photos,
        })

    itinerary_map_points = _compute_map_points(we_occurrences, len(days))
    special_dates = _fetch_special_dates(
        is_program, valid_until_date, we_occurrences, days, destination_location_cache
    )

    return render(request, "intranet/itinerary_public.html", {
        "unavailable": False,
        "itinerary": itinerary,
        "default_cover_url": static("intranet/images/itinerary_cover_default.png"),
        "default_intro_text": DEFAULT_ITINERARY_INTRO_TEXT,
        "regular_days": regular_days,
        "optional_days": optional_days,
        "quote_brief_blocks": quote_brief_blocks,
        "accommodation_cards": accommodation_cards,
        "car_hire_conditions_text": car_hire_conditions_text,
        "itinerary_destinations": itinerary_destinations,
        # Subtítulo del banner chico de cada pestaña (ver _itinerary_mini_banner.html) — se
        # arma acá, no con filtros de template encadenados, para manejar bien el plural.
        "days_total_label": f"{days_total} day{'s' if days_total != 1 else ''}",
        "is_program": is_program,
        "valid_until_date": valid_until_date,
        "destinations_count_label": f"{len(itinerary_destinations)} destination{'s' if len(itinerary_destinations) != 1 else ''}",
        "accommodation_count_label": f"{len(accommodation_cards)} hotel{'s' if len(accommodation_cards) != 1 else ''}",
        "itinerary_map_points_json": json.dumps(itinerary_map_points),
        "special_dates": special_dates,
        "mapbox_token": settings.MAPBOX_TOKEN,
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
