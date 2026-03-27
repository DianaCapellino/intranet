"""
quality_ai.py — AI processing of feedback inbox emails using Claude API.

Flow:
  1. Load itinerary CSV (media/itinerarios/itinerarios.csv)
  2. For each FeedbackInboxItem with status='pendiente':
       - Find relevant itinerary rows (by file ID in email, or by date window)
       - Call Claude Haiku with email + itinerary context
       - Save ai_analysis JSON to the item (list of targets)
  3. Calidad view shows analysis as pre-filled confirmation cards
  4. User confirms → one Feedback per target is created
"""

import csv
import io
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta

import anthropic
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
ITINERARIO_PATH = os.path.normpath(
    os.path.join(_HERE, '..', '..', 'media', 'itinerarios', 'itinerarios.csv')
)

SKIP_SERVICE_TYPES = {'WE', 'FT', 'IM', 'IN', 'OC'}

SERVICE_TYPE_LABELS = {
    'AC': 'Accommodation (hotel)',
    'FB': 'Food & Beverages',
    'GU': 'Guía',
    'TF': 'Transfer',
    'TR': 'Transporte',
    'EN': 'Entrada',
    'EX': 'Excursión',
    'CI': 'Alquiler de auto',
}

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Sos un asistente especializado en analizar feedback de viajeros para Aliwen, una agencia de turismo argentina.

Dado un email (que puede ser una cadena con reenvíos o comunicaciones con proveedores), extraés información estructurada para registrar feedbacks.

REGLAS CRÍTICAS:
- Un email puede tener feedback sobre MÚLTIPLES entidades. Identificá cada una por separado.
- Cada target tiene su propio sentiment, tipo, resumen y solución.
- Para identificar el proveedor, usá el itinerario: cruzá destino + tipo de servicio + fechas.
- Si el pasajero elogia "el equipo de Aliwen", "el servicio de Aliwen", "su agencia" → target_type="aliwen_team"
- Si mencionan un guía por nombre (persona que acompañó el viaje, no empleado de Aliwen) → target_type="guide"
- Si mencionan un Destination Host (DH) por nombre → target_type="dh"
- Si mencionan a alguien que claramente es empleado interno de Aliwen (vendedor, operador) → target_type="user"
- Si no podés identificar el proveedor exacto → target_type="entity", name="Servicio no registrado"

TIPOS DE TARGET:
- "supplier": un proveedor del itinerario (hotel, restaurante, excursión, transfer, etc.)
- "user": un empleado interno de Aliwen (vendedor, operador) mencionado por nombre o rol
- "guide": un guía de viaje mencionado por nombre (puede ser freelance o externo)
- "dh": un Destination Host (DH) mencionado por nombre
- "aliwen_team": elogio/queja al equipo Aliwen sin nombre específico → se asignará al vendedor y operador del file
- "entity": categoría general que no encaja en las anteriores

CONTENT vs VERBATIM:
- "content": resumen propio de TODO el feedback relevante a este target, incluyendo el contexto de cadenas de emails o comunicaciones con proveedores. Redactalo en español, en forma de resumen.
- "verbatim": SOLO el texto textual original del pasajero (sus propias palabras). Reglas:
  - Si el pasajero escribió en inglés u otro idioma distinto al español: incluí hasta 200 caracteres de sus palabras, truncando con "..." si es más largo
  - Si el pasajero escribió en español, o si el email es texto interno de Aliwen: verbatim=""
  - NUNCA incluyas texto de Aliwen, proveedores ni reenvíos en verbatim
  - IMPORTANTE: el campo verbatim debe ser una cadena JSON válida — escapá las comillas dobles como \" y los saltos de línea como \n

SOLUCIÓN (para feedbacks negativos):
- Si el email o la cadena menciona cómo se resolvió el problema, incluilo en "solution" (resumen breve en español)
- Si se menciona un costo de resolución (compensación, reembolso, etc.) incluilo en "cost" como número sin símbolo de moneda
- Si no hay información de resolución: solution="", cost=0

DEDUPLICACIÓN (usar solo si se proveen FEEDBACKS EXISTENTES del viaje en el prompt):
- Misma cadena, mismo target → "existing_feedback_id": <id>, "content" con SOLO la info nueva.
- Gestión con proveedor (Aliwen contactó/fue contactado por el proveedor para resolver) → "existing_feedback_id": <id>, "is_provider_update": true, "content" con resumen breve de esa gestión.
- Target nuevo no registrado → omitir existing_feedback_id.

Respondé ÚNICAMENTE con este JSON (sin markdown, sin texto extra):
{
  "targets": [
    {
      "target_type": "supplier" | "user" | "guide" | "dh" | "aliwen_team" | "entity",
      "existing_feedback_id": null,
      "is_provider_update": false,
      "name": "nombre exacto del proveedor/guía/DH según itinerario, o nombre mencionado",
      "destination": "ciudad/destino donde trabajó el guía o DH según el itinerario (ej: 'Bariloche', 'Buenos Aires') — solo para guide y dh, null para el resto",
      "sentiment": "positivo" | "neutral" | "negativo",
      "type": "Calidad del servicio" | "Demora/rapidez" | "Salud/higiene" | "Inclusiones" | "Otro",
      "brief_summary": "máximo 120 caracteres, frase completa y coherente",
      "content": "resumen del feedback (solo info nueva si existing_feedback_id está presente)",
      "solution": "cómo se resolvió (solo si aplica)",
      "cost": 0
    }
  ],
  "trip_file_id": "código ALAL/ALFI/ALGR/ALFT del viaje SOLO si aparece literalmente en el texto del email — no inferir ni inventar, dejar null si no está explícito",
  "verbatim": "primeras 200 chars del texto original del pasajero (solo si está en otro idioma), truncar con '...' si es más largo, o vacío",
  "needs_more_info": true | false,
  "missing_fields": ["lista de campos faltantes"]
}"""

# ── CSV loading ────────────────────────────────────────────────────────────────

def load_itinerario_csv():
    if not os.path.exists(ITINERARIO_PATH):
        return []
    with open(ITINERARIO_PATH, encoding='utf-8-sig') as f:
        lines = f.readlines()
    data_lines = lines[6:]  # skip 6 metadata rows
    reader = csv.DictReader(io.StringIO(''.join(data_lines)), delimiter=';')
    rows = []
    for row in reader:
        svc = (row.get('Product_service') or '').strip().upper()
        if svc not in SKIP_SERVICE_TYPES:
            rows.append(dict(row))
    return rows


def _parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except (ValueError, AttributeError):
        return None


def _extract_tourplan_codes(text):
    """
    Extract Tourplan codes: ALFI / ALGR / ALFT / ALAL + 6 digits.
    Tolerates optional space or hyphen between prefix and digits,
    e.g. 'ALFI123456', 'ALFI 123456', 'ALFI-123456'.
    """
    matches = re.findall(
        r'\b(AL(?:FI|GR|FT|AL))[\s\-]?(\d{6})\b',
        text, re.IGNORECASE
    )
    return [f"{prefix}{digits}".upper() for prefix, digits in matches]


def _extract_audley_refs(text):
    """Extract 7-digit Audley references (optionally followed by /N)."""
    return re.findall(r'\b(\d{7})(?:/\d+)?\b', text)


def find_matching_trip(email_subject, email_body, email_date):
    """
    Strict trip matching — never guesses. Priority order:

    1. Tourplan code (ALFI/ALGR/ALFT/ALAL + 6 digits) anywhere in subject or body.
    2. Audley 7-digit reference (only for trips belonging to an Audley client).
    3. Words from the SUBJECT ONLY (letters only, ≥3 chars) — if exactly ONE trip
       in the DB has any of those words in its name → return it.
       If zero or multiple trips match → return None (ask user for Tourplan code).
    """
    from intranet.models import Trip, Client

    full_text = f"{email_subject or ''}\n\n{email_body or ''}"

    # 1 — Tourplan code anywhere in the email
    for code in _extract_tourplan_codes(full_text):
        trip = Trip.objects.filter(tourplanId__iexact=code).first()
        if trip:
            return trip

    # 2 — Audley 7-digit reference
    audley_refs = _extract_audley_refs(full_text)
    if audley_refs:
        audley_ids = list(
            Client.objects.filter(name__icontains='Audley').values_list('id', flat=True)
        )
        if audley_ids:
            for ref in audley_refs:
                trip = Trip.objects.filter(
                    client_id__in=audley_ids,
                    client_reference__startswith=ref[:7],
                ).first()
                if trip:
                    return trip

    # 3 — Subject words only (letters, ≥3 chars)
    subject_words = re.findall(r'[A-Za-záéíóúüñÁÉÍÓÚÜÑ]{3,}', email_subject or '')
    subject_words = [w for w in subject_words if _norm(w) not in _SURNAME_STOP]

    matched_trips = set()
    for word in subject_words:
        for trip_id in Trip.objects.filter(name__icontains=word).values_list('id', flat=True):
            matched_trips.add(trip_id)

    if len(matched_trips) == 1:
        return Trip.objects.get(pk=next(iter(matched_trips)))

    return None  # Zero or multiple matches — ask user for Tourplan code


def get_relevant_rows(rows, email_text, email_date, matched_trip=None):
    """
    Return itinerary rows for the AI prompt.
    Uses the programmatically-matched trip as the primary filter,
    then explicit Tourplan codes, then a narrow ±10-day date window.
    Returns [] when no confident match (better no context than wrong context).
    """
    # 1 — Rows for the matched trip's tourplanId
    if matched_trip and matched_trip.tourplanId:
        trip_rows = [r for r in rows
                     if (r.get('NumeroDeFile') or '').upper() == matched_trip.tourplanId.upper()]
        if trip_rows:
            return trip_rows[:80]

    # 2 — Tourplan codes found in the email text
    codes = set(_extract_tourplan_codes(email_text))
    if codes:
        code_rows = [r for r in rows if (r.get('NumeroDeFile') or '').upper() in codes]
        if code_rows:
            return code_rows[:80]

    # 3 — Narrow date window (±10 days) — only when unambiguous
    if email_date:
        base = (email_date.replace(tzinfo=None)
                if getattr(email_date, 'tzinfo', None) else email_date)
        w_start = base - timedelta(days=10)
        w_end   = base + timedelta(days=10)
        date_rows = [r for r in rows
                     if (d := _parse_date(r.get('Service_Date', ''))) and w_start <= d <= w_end]
        if date_rows:
            return date_rows[:80]

    return []


def format_existing_feedbacks_for_prompt(trip):
    """
    Return a compact text summary of existing feedbacks for a trip,
    to give the AI context for deduplication.
    Returns empty string if no feedbacks exist.
    """
    if not trip:
        return ''
    from tariff.models import Feedback
    fbs = Feedback.objects.filter(trip=trip).select_related(
        'supplier', 'target_guide', 'target_dh', 'target_user', 'target_entity'
    )
    if not fbs.exists():
        return ''
    lines = ['FEEDBACKS YA REGISTRADOS PARA ESTE VIAJE:',
             'ID | Target | Sentimiento | Resumen']
    for fb in fbs:
        if fb.supplier:
            target = f"proveedor:{fb.supplier.name}"
        elif fb.target_guide:
            target = f"guía:{fb.target_guide.name}"
        elif fb.target_dh:
            target = f"dh:{fb.target_dh.name}"
        elif fb.target_user:
            target = f"usuario:{fb.target_user.other_name or fb.target_user.username}"
        elif fb.target_entity:
            target = f"entidad:{fb.target_entity.name}"
        else:
            target = "aliwen_team"
        lines.append(f"{fb.id} | {target} | {fb.sentiment} | {fb.brief_summary[:80]}")
    return '\n'.join(lines)


def format_rows_for_prompt(rows):
    if not rows:
        return "(sin itinerario disponible)"
    lines = ["NumeroDeFile | Fecha | Destino | Servicio | Tipo | Proveedor | Operador | Vendedor"]
    for r in rows:
        svc = (r.get('Product_service') or '').strip().upper()
        label = SERVICE_TYPE_LABELS.get(svc, svc)
        lines.append(
            f"{r.get('NumeroDeFile','')} | {r.get('Service_Date','')} | "
            f"{r.get('Product_Location','')} | {r.get('Product_name','')[:35]} | "
            f"{label} | {r.get('Proveedor','')} | "
            f"{r.get('Operador','')} | {r.get('Consultant','')}"
        )
    return '\n'.join(lines)


# ── AI call ────────────────────────────────────────────────────────────────────

def _sanitize_email_body(text, max_chars=3500):
    """
    Prepare email body for sending to the AI.
    - Strips control characters (keeps newlines and tabs)
    - Replaces straight double-quotes with typographic quotes so the AI
      can safely copy verbatim text into JSON without breaking string delimiters
    - Strips carriage returns
    """
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\r]', '', text or '')
    # Replace straight quotes with typographic equivalents to avoid JSON breakage
    cleaned = cleaned.replace('"', '\u201c').replace('"', '\u201d')
    return cleaned[:max_chars]


def _fix_json_strings(s):
    """
    Escape control characters that appear INSIDE JSON string values only.
    Uses a character-by-character state machine to avoid touching structural JSON.
    Also fixes unescaped double-quotes inside strings by escaping them.
    """
    result = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if in_string:
            if c == '\\' and i + 1 < len(s):
                # Already escaped sequence — pass through as-is
                result.append(c)
                result.append(s[i + 1])
                i += 2
                continue
            elif c == '"':
                result.append(c)
                in_string = False
            elif c == '\n':
                result.append('\\n')
            elif c == '\r':
                result.append('\\r')
            elif c == '\t':
                result.append('\\t')
            elif ord(c) < 0x20:
                result.append(f'\\u{ord(c):04x}')
            else:
                result.append(c)
        else:
            if c == '"':
                result.append(c)
                in_string = True
            else:
                result.append(c)
        i += 1
    return ''.join(result)


def _safe_json_loads(raw):
    """
    Try to parse JSON from AI response, with several fallback repair strategies.
    """
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract the outermost {...} block
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    candidate = m.group() if m else raw

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Strategy 3: fix control characters inside string values (state machine)
    try:
        return json.loads(_fix_json_strings(candidate))
    except json.JSONDecodeError:
        pass

    # Strategy 4: wipe long text fields one by one until it parses
    text = _fix_json_strings(candidate)
    for field in ('verbatim', 'content', 'solution', 'brief_summary'):
        text = re.sub(
            r'("' + re.escape(field) + r'"\s*:\s*)"[^"]{20,}"',
            r'\1""',
            text
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Give up — include truncated raw response in error for debugging
    preview = raw[:300].replace('\n', '↵')
    raise ValueError(f"No se pudo parsear JSON de la respuesta IA. Primeros 300 chars: {preview!r}")


def process_inbox_item_with_ai(item):
    load_dotenv(override=True)
    api_key = os.environ.get('EXPO_PUBLIC_ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("EXPO_PUBLIC_ANTHROPIC_API_KEY no configurada")

    all_rows = load_itinerario_csv()
    email_text = f"{item.email_subject}\n\n{item.email_body}"

    # --- Strict trip matching before calling AI ---
    matched_trip = find_matching_trip(item.email_subject, item.email_body, item.received_at)
    relevant_rows = get_relevant_rows(all_rows, email_text, item.received_at, matched_trip=matched_trip)
    itinerary_text = format_rows_for_prompt(relevant_rows)

    # Build trip context note for the AI prompt
    trip_note = ""
    if matched_trip:
        trip_note = (
            f"\nVIAJE IDENTIFICADO: {matched_trip.tourplanId} — {matched_trip.name}"
            f" (cliente: {matched_trip.client})\n"
        )

    existing_fb_text = format_existing_feedbacks_for_prompt(matched_trip)

    user_prompt = (
        f"EMAIL:\nDe: {item.email_sender}\n"
        f"Asunto: {item.email_subject}\n"
        f"Fecha: {item.received_at.strftime('%d/%m/%Y')}\n"
        f"{trip_note}\n"
        f"{_sanitize_email_body(item.email_body)}\n\n"
        f"---\nITINERARIO (servicios relevantes):\n{itinerary_text}"
        + (f"\n\n---\n{existing_fb_text}" if existing_fb_text else "")
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    analysis = _safe_json_loads(raw)

    # --- Override / validate trip_file_id ---
    if matched_trip and matched_trip.tourplanId:
        # We found a definitive match — trust it over AI
        analysis['trip_file_id'] = matched_trip.tourplanId
    elif analysis.get('trip_file_id'):
        # AI suggested one — validate it exists in DB, reject if not
        from intranet.models import Trip
        if not Trip.objects.filter(tourplanId__iexact=analysis['trip_file_id']).exists():
            analysis['trip_file_id'] = None
            analysis['needs_more_info'] = True
            missing = analysis.get('missing_fields') or []
            if 'trip_file_id' not in missing:
                missing.append('trip_file_id')
            analysis['missing_fields'] = missing

    enrich_targets_from_trip(analysis, relevant_rows=relevant_rows, matched_trip=matched_trip)

    # Extract the earliest service date from the itinerario rows for use as creation_date
    service_date = None
    for r in relevant_rows:
        d = _parse_date(r.get('Service_Date', ''))
        if d and (service_date is None or d < service_date):
            service_date = d
    if service_date:
        analysis['service_date'] = service_date.strftime('%Y-%m-%d')

    item.ai_analysis = analysis
    item.save(update_fields=['ai_analysis'])
    return analysis


def process_all_pending(stdout=None, force=False):
    from tariff.models import FeedbackInboxItem
    if force:
        # Reset all items to pendiente so they can be re-analyzed and re-confirmed
        FeedbackInboxItem.objects.exclude(status='pendiente').update(
            status='pendiente', resolved_feedback=None
        )
        pending = FeedbackInboxItem.objects.all()
    else:
        pending = FeedbackInboxItem.objects.filter(status='pendiente', ai_analysis__isnull=True)
    processed = 0
    errors = 0
    for item in pending:
        try:
            analysis = process_inbox_item_with_ai(item)
            processed += 1
            targets = analysis.get('targets', [])
            if stdout:
                stdout.write(f"  ✓ {item.email_subject[:50]} → {len(targets)} target(s)")
        except Exception as e:
            errors += 1
            if stdout:
                stdout.write(f"  ✗ Error en '{item.email_subject[:50]}': {e}")
    return processed, errors


# ── Target resolution ──────────────────────────────────────────────────────────

# Words stripped when comparing supplier names (common prefixes/suffixes that
# don't distinguish one property from another, plus city names that the AI
# often appends to the property name).
_SUPPLIER_NOISE = frozenset([
    'hotel', 'hoteles', 'hostel', 'apart', 'aparthotel', 'boutique',
    'suite', 'suites', 'lodge', 'resort', 'inn', 'spa', 'casa',
    'buenos', 'aires', 'argentina', 'mendoza', 'cordoba', 'bariloche',
    'ushuaia', 'salta', 'iguazu', 'calafate', 'chalten', 'patagonia',
    'de', 'del', 'la', 'el', 'los', 'las', 'y',
])


def _norm(s):
    """Lowercase, strip diacritics/accents, collapse whitespace."""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', s.lower().strip())


# Words that are unlikely to be passenger surnames
_SURNAME_STOP = frozenset(_norm(w) for w in [
    'tour', 'travel', 'hotel', 'aliwen', 'buenos', 'aires', 'argentina',
    'viaje', 'viajes', 'incoming', 'trip', 'hola', 'para', 'gracias',
    'thanks', 'thank', 'regards', 'saludos', 'welcome', 'estimado',
    'estimada', 'senal', 'senor', 'senora', 'dear', 'from',
    'subject', 'asunto', 'fecha', 'itinerario', 'servicio',
    'calidad', 'feedback', 'hostel', 'lodge', 'resort',
])


def _core_words(name):
    """Significant words after normalization, removing noise and short words."""
    return [w for w in _norm(name).split() if len(w) >= 3 and w not in _SUPPLIER_NOISE]


def _supplier_score(query_name, supplier_name):
    """
    Return a match score for how well query_name matches supplier_name.
    Higher is better; 0 means no match.
      4 – exact (accent-normalized)
      3 – one name fully contained in the other (accent-normalized)
      2 – one name contained in the other after noise removal
      1 – 2+ significant core words shared
    """
    qn = _norm(query_name)
    sn = _norm(supplier_name)

    # 4: exact match after accent normalization
    if qn == sn:
        return 4

    # 3: containment in either direction
    if qn in sn or sn in qn:
        return 3

    # 2: containment after stripping noise words
    qc = ' '.join(_core_words(query_name))
    sc = ' '.join(_core_words(supplier_name))
    if qc and sc and (qc in sc or sc in qc):
        return 2

    # 1: 2+ significant core words shared
    qw = set(_core_words(query_name))
    sw = set(_core_words(supplier_name))
    if len(qw & sw) >= 2:
        return 1

    return 0


def try_match_supplier(name):
    if not name:
        return None
    from tariff.models import Supplier

    # Fast DB lookup first (exact, then contains)
    match = Supplier.objects.filter(name__iexact=name).first()
    if match:
        return match
    match = Supplier.objects.filter(name__icontains=name).first()
    if match:
        return match

    # Accent/noise-aware scoring against all suppliers
    best, best_score = None, 0
    for s in Supplier.objects.all():
        score = _supplier_score(name, s.name)
        if score > best_score:
            best_score = score
            best = s

    return best if best_score >= 1 else None


def try_match_user_by_name(name):
    """
    Match a staff member by other_name or username.
    Single-word names only match on exact equality — partial first-name
    matches are intentionally skipped to avoid misidentifying guides as users.
    Multi-word names match if all words appear in the full name.
    """
    if not name:
        return None
    from intranet.models import User
    u = User.objects.filter(other_name__iexact=name).first()
    if u:
        return u
    words = [w for w in name.split() if len(w) > 2]
    # Require at least 2 significant words for partial matching
    if len(words) >= 2:
        for u in User.objects.all():
            full = (u.other_name or u.username).lower()
            if all(w.lower() in full for w in words):
                return u
    return None


def get_trip_staff(trip_file_id):
    """Return (responsable_user, operations_user) for a trip file ID."""
    if not trip_file_id:
        return None, None
    from intranet.models import Trip
    trip = Trip.objects.filter(tourplanId__iexact=trip_file_id.strip()).first()
    if not trip:
        return None, None
    return trip.responsable_user, trip.operations_user


def try_match_trip(trip_file_id):
    if not trip_file_id:
        return None
    from intranet.models import Trip
    return Trip.objects.filter(tourplanId__iexact=trip_file_id.strip()).first()


def _names_overlap(a, b):
    """True if one name contains the other (case-insensitive) or shares 2+ significant words."""
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    words_a = {w for w in a.split() if len(w) > 2}
    words_b = {w for w in b.split() if len(w) > 2}
    return len(words_a & words_b) >= 2


def _resolve_guide_for_target(suggested_name, trip, destination_hint=None):
    from intranet.models import Guide

    def _name_matches(g, name):
        if not name:
            return False
        if g.name.lower() == name.lower():
            return True
        words = [w for w in name.split() if len(w) > 2]
        return bool(words and all(w.lower() in g.name.lower() for w in words))

    # 1. If we have a destination hint, try name matching scoped to that location first
    if destination_hint:
        dest_norm = _norm(destination_hint)
        location_qs = Guide.objects.filter(location__name__icontains=destination_hint)
        if not location_qs.exists():
            # Try accent-normalized match on location name
            for g in Guide.objects.select_related('location').all():
                loc_name = g.location.name if g.location else ''
                if dest_norm and dest_norm in _norm(loc_name):
                    location_qs = Guide.objects.filter(pk=g.pk) | location_qs
        for g in location_qs:
            if _name_matches(g, suggested_name):
                return g

    # 2. Global exact match
    if suggested_name:
        g = Guide.objects.filter(name__iexact=suggested_name).first()
        if g:
            return g
        # Partial word match — if destination_hint, prefer same-location result
        words = [w for w in suggested_name.split() if len(w) > 2]
        if words:
            candidates = []
            for g in Guide.objects.select_related('location').all():
                if all(w.lower() in g.name.lower() for w in words):
                    # Score higher if location matches destination hint
                    loc_name = g.location.name if g.location else ''
                    score = 1
                    if destination_hint and _norm(destination_hint) in _norm(loc_name):
                        score = 2
                    candidates.append((score, g))
            if candidates:
                candidates.sort(key=lambda x: -x[0])
                return candidates[0][1]

    # 3. Cross-reference with Trip.guide CharField
    trip_name = (trip.guide or '').strip() if trip else ''
    if not trip_name:
        return None
    g = Guide.objects.filter(name__iexact=trip_name).first()
    if g:
        return g
    # Names overlap → create from Trip's definitive name
    if _names_overlap(suggested_name, trip_name) or not suggested_name:
        guide, _ = Guide.objects.get_or_create(name=trip_name)
        return guide
    return None


def _resolve_dh_for_target(suggested_name, trip):
    from intranet.models import DestinationHost
    # 1. Exact match in DH model
    if suggested_name:
        d = DestinationHost.objects.filter(name__iexact=suggested_name).first()
        if d:
            return d
    # 2. Cross-reference with Trip.dh CharField
    trip_name = (trip.dh or '').strip() if trip else ''
    if not trip_name:
        return None
    d = DestinationHost.objects.filter(name__iexact=trip_name).first()
    if d:
        return d
    # Names overlap → create from Trip's definitive name
    if _names_overlap(suggested_name, trip_name) or not suggested_name:
        dh, _ = DestinationHost.objects.get_or_create(name=trip_name)
        return dh
    return None


def _destination_hint_for_target(t, relevant_rows, trip_file_id):
    """
    Return the best destination string for a guide/dh target.
    Priority: AI-provided 'destination' field → GU/DH row in itinerary for that file.
    """
    hint = (t.get('destination') or '').strip()
    if hint:
        return hint
    # Extract from itinerary rows: look for guide (GU) rows for the same file
    if relevant_rows and trip_file_id:
        file_rows = [r for r in relevant_rows
                     if (r.get('NumeroDeFile') or '').upper() == trip_file_id.upper()]
        for r in file_rows:
            svc = (r.get('Product_service') or '').strip().upper()
            if svc == 'GU':
                loc = (r.get('Product_Location') or '').strip()
                if loc:
                    return loc
        # Fallback: any row's location for that file
        for r in file_rows:
            loc = (r.get('Product_Location') or '').strip()
            if loc:
                return loc
    return ''


def enrich_targets_from_trip(analysis, relevant_rows=None, matched_trip=None):
    """
    After AI analysis, auto-link guide/dh targets using the matched Trip's fields.
    Adds guide_id / dh_id directly to each target dict so the template can
    pre-populate the hidden FK fields without an extra JS search.
    Uses destination context from itinerary rows to disambiguate guides by location.

    matched_trip: Trip instance from find_matching_trip() — takes priority over AI's trip_file_id.
    """
    trip_file_id = analysis.get('trip_file_id')
    # Prefer the programmatically-matched trip; fall back to AI's trip_file_id
    trip = matched_trip or (try_match_trip(trip_file_id) if trip_file_id else None)

    for t in analysis.get('targets', []):
        target_type = t.get('target_type')
        suggested = (t.get('name') or '').strip()

        if target_type == 'supplier' and not t.get('supplier_id'):
            supplier = try_match_supplier(suggested)
            if supplier:
                t['supplier_id'] = supplier.id
                t['name'] = supplier.name

        elif target_type == 'user':
            # Verify the name actually exists as a User; if not, reclassify
            user = try_match_user_by_name(suggested)
            if user:
                t['user_id'] = user.id
                t['name'] = user.other_name or user.username
            elif trip:
                dest = _destination_hint_for_target(t, relevant_rows, trip_file_id)
                guide = _resolve_guide_for_target(suggested, trip, destination_hint=dest)
                if guide:
                    t['target_type'] = 'guide'
                    t['guide_id'] = guide.id
                    t['name'] = guide.name
                    if not trip.guide_fk_id:
                        trip.guide_fk = guide
                        trip.save(update_fields=['guide_fk'])
                else:
                    dh = _resolve_dh_for_target(suggested, trip)
                    if dh:
                        t['target_type'] = 'dh'
                        t['dh_id'] = dh.id
                        t['name'] = dh.name
                        if not trip.dh_fk_id:
                            trip.dh_fk = dh
                            trip.save(update_fields=['dh_fk'])

        elif target_type == 'guide':
            dest = _destination_hint_for_target(t, relevant_rows, trip_file_id)
            guide = _resolve_guide_for_target(suggested, trip, destination_hint=dest)
            if guide:
                t['guide_id'] = guide.id
                t['name'] = guide.name
                if trip and not trip.guide_fk_id:
                    trip.guide_fk = guide
                    trip.save(update_fields=['guide_fk'])

        elif target_type == 'dh':
            dh = _resolve_dh_for_target(suggested, trip)
            if dh:
                t['dh_id'] = dh.id
                t['name'] = dh.name
                if trip and not trip.dh_fk_id:
                    trip.dh_fk = dh
                    trip.save(update_fields=['dh_fk'])


def get_or_create_entity(name):
    from tariff.models import FeedbackEntity
    obj, _ = FeedbackEntity.objects.get_or_create(name=name)
    return obj


def check_sender_is_internal(sender_email):
    from intranet.models import User
    return User.objects.filter(
        email__iexact=sender_email,
        userType__in=['Ventas', 'Operaciones', 'Internal'],
    ).first()


# ── Feedback creation ──────────────────────────────────────────────────────────

def create_feedbacks_from_inbox(item, confirmed_targets, overrides=None):
    """
    Create one Feedback per confirmed target from a FeedbackInboxItem.
    Target types: supplier, user, guide, dh, aliwen_team, entity.
    Returns list of created Feedback objects.
    """
    from tariff.models import Feedback, Supplier, FeedbackEntity
    from intranet.models import User, Guide, DestinationHost

    overrides = overrides or {}
    trip_file_id = overrides.get('trip_file_id') or (item.ai_analysis or {}).get('trip_file_id')
    verbatim     = overrides.get('verbatim', (item.ai_analysis or {}).get('verbatim', ''))
    trip         = try_match_trip(trip_file_id)

    # Use service date from itinerario if available, otherwise fall back to email received date
    service_date_str = (item.ai_analysis or {}).get('service_date')
    if service_date_str:
        try:
            from datetime import datetime as _dt
            creation_date = _dt.strptime(service_date_str, '%Y-%m-%d')
        except ValueError:
            creation_date = item.received_at
    else:
        creation_date = item.received_at

    creator = check_sender_is_internal(item.email_sender)
    if not creator:
        creator = User.objects.filter(userType='Internal').first()

    created = []

    for t in confirmed_targets:
        target_type   = t.get('target_type', 'entity')
        sentiment     = t.get('sentiment', 'neutral')
        fb_type       = t.get('type', 'Otro')
        brief_summary = (t.get('brief_summary') or '')[:120]
        content       = t.get('content', '')
        solution      = (t.get('solution') or '')
        cost          = t.get('cost') or 0
        fb_status     = 'abierto' if sentiment == 'negativo' else 'cerrado'

        # ── Update existing feedback (same chain or provider communication) ──
        existing_id = t.get('existing_feedback_id')
        if existing_id:
            try:
                existing_fb = Feedback.objects.get(pk=existing_id)
                date_str = creation_date.strftime('%d/%m/%Y') if hasattr(creation_date, 'strftime') else str(creation_date)
                if t.get('is_provider_update'):
                    note = f"\n[{date_str}] Gestión con proveedor: {content}"
                else:
                    note = f"\n[{date_str}] Actualización: {content}"
                existing_fb.content = (existing_fb.content or '') + note
                if solution and not existing_fb.solution:
                    existing_fb.solution = solution
                if cost and not existing_fb.cost:
                    existing_fb.cost = cost
                update_fields = ['content']
                if solution and not existing_fb.solution:
                    update_fields.append('solution')
                if cost and not existing_fb.cost:
                    update_fields.append('cost')
                existing_fb.save(update_fields=update_fields)
                created.append(existing_fb)
                continue
            except Feedback.DoesNotExist:
                pass  # Fall through to create new

        supplier     = None
        target_user  = None
        target_guide = None
        target_dh    = None
        entity       = None

        if target_type == 'supplier':
            sid = t.get('supplier_id')
            supplier = Supplier.objects.filter(pk=sid).first() if sid else None

        elif target_type == 'user':
            uid = t.get('user_id')
            target_user = User.objects.filter(pk=uid).first() if uid else None

        elif target_type == 'guide':
            gid = t.get('guide_id')
            target_guide = Guide.objects.filter(pk=gid).first() if gid else None

        elif target_type == 'dh':
            dhid = t.get('dh_id')
            target_dh = DestinationHost.objects.filter(pk=dhid).first() if dhid else None

        elif target_type == 'aliwen_team':
            seller, operator = get_trip_staff(trip_file_id)
            staff_members = [u for u in [seller, operator] if u]
            aliwen_entity = get_or_create_entity('Aliwen - Equipo general')
            if not staff_members:
                staff_members = [None]

            for staff in staff_members:
                fb = Feedback.objects.create(
                    user=creator, trip=trip,
                    target_user=staff,
                    target_entity=aliwen_entity if not staff else None,
                    sentiment=sentiment, type=fb_type,
                    brief_summary=brief_summary, content=content,
                    solution=solution, cost=cost,
                    verbatim=verbatim, source='email',
                    email_sender=item.email_sender, status=fb_status,
                    creation_date=creation_date,
                )
                created.append(fb)
            continue

        else:  # entity / otros
            eid = t.get('entity_id')
            entity = FeedbackEntity.objects.filter(pk=eid).first() if eid else None
            if not entity:
                entity = get_or_create_entity('Servicio no registrado')

        fb = Feedback.objects.create(
            user=creator, trip=trip,
            supplier=supplier,
            target_user=target_user,
            target_guide=target_guide,
            target_dh=target_dh,
            target_entity=entity,
            sentiment=sentiment, type=fb_type,
            brief_summary=brief_summary, content=content,
            solution=solution, cost=cost,
            verbatim=verbatim, source='email',
            email_sender=item.email_sender, status=fb_status,
            creation_date=item.received_at,
        )
        created.append(fb)

    if created:
        item.status = 'confirmado'
        item.resolved_feedback = created[0]
        item.save(update_fields=['status', 'resolved_feedback'])

    return created
