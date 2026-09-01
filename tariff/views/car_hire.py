"""
tariff/views/car_hire.py

Módulo de gestión de Alquiler de vehículo.
Calca el patrón de tariff/views/service.py + modify.py (Supplier -> Product ->
$ -> RateLine/Rate/CostItem/FixedRateCost) pero usando Destino (Location) en
vez de Proveedor, y con costo/venta único por día (sin columnas de pax).

Importar y registrar las urls de car_hire_urls.py en tariff/urls.py.
"""
import json
import math
import re
import unicodedata
from datetime import date, timedelta
from collections import defaultdict

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db.models import Q

from tariff.models import (
    Location, CarCategory, CarRateGroup, CarRateLine, CarRate, CarExtra,
    CarFixedCost, CarHireConfig, CAR_EXTRA_TYPES, STATUS, FCU_OPTIONS,
)
from intranet.models import ExternalCalendarEntry, Holidays

# Peak-period surcharge added to the quote when the hire dates hit a public
# holiday or a long weekend.
SPECIAL_DATES_SURCHARGE_PCT = 20.0


def _strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(c) != "Mn"
    )


def _special_calendar_hits(location_id, start, end):
    """Public holidays / long weekends that overlap the hire dates [start, end].

    - Feriados / días no laborables come from the Holidays master list; a
      Friday/Monday holiday also drags in the adjacent Sat–Sun, so a hire that
      only touches the weekend of a long weekend still counts.
    - Long weekends explicitly loaded in the external calendar
      (ExternalCalendarEntry) are also matched, scoped to the destination.
    """
    hits, seen = [], set()

    def add(name, category, d_from, d_to):
        key = (d_from, category)
        if key in seen:
            return
        seen.add(key)
        hits.append({"name": name, "category": category,
                     "date_from": d_from, "date_to": d_to})

    win_lo, win_hi = start - timedelta(days=4), end + timedelta(days=4)
    for h in (Holidays.objects
              .filter(type_holidays__in=("Feriado", "Día no laborable"))
              .filter(date_from__lte=win_hi, date_to__gte=win_lo)
              .values("name", "type_holidays", "date_from", "date_to")):
        span_from, span_to = h["date_from"], h["date_to"]
        if span_from.weekday() == 0:          # Monday holiday → + Sat/Sun before
            span_from -= timedelta(days=2)
        if span_to.weekday() == 4:            # Friday holiday → + Sat/Sun after
            span_to += timedelta(days=2)
        if span_from <= end and span_to >= start:
            add(h["name"] or h["type_holidays"], "holiday",
                h["date_from"], h["date_to"])

    for e in (ExternalCalendarEntry.objects
              .filter(category="long_weekend")
              .filter(Q(location_id=location_id) | Q(location__isnull=True))
              .filter(date_from__lte=end, date_to__gte=start)
              .values("name", "date_from", "date_to")):
        add(e["name"] or "Long weekend", "long_weekend",
            e["date_from"], e["date_to"])

    hits.sort(key=lambda x: x["date_from"])
    return hits

EXTRA_ORDER = ["AIRPORT", "SMART", "COVER"]
EXTRA_LABELS = dict(CAR_EXTRA_TYPES)


# ─── helpers ──────────────────────────────────────────────────────────────

def _daily_cost_usd(value, fcu, increase, usd, exchange, pax=1):
    """Convierte un costo (posiblemente en ARS, posiblemente 'por grupo') a
    costo diario en USD, aplicando aumento."""
    v = float(value or 0)
    if fcu == "Person" and pax:
        v = v  # ya es por unidad; se deja igual (día x persona no aplica normalmente)
    v *= (1 + float(increase or 0) / 100)
    if not usd and exchange:
        v /= float(exchange)
    return round(v, 2)


def _suggested_sell(cost_ars_or_usd, usd, exchange, markup, commission=0, extra_discount=0):
    """Sugerencia de venta en USD.
    1. Convierte a USD si hace falta.
    2. Descuenta la comisión: costo × (1 − comisión%).
    3. Descuenta el descuento adicional: × (1 − descuento%).
    4. Divide por el markup."""
    if not cost_ars_or_usd or not markup:
        return 0
    cost_usd = float(cost_ars_or_usd) if usd else float(cost_ars_or_usd) / float(exchange or 1)
    real_cost = cost_usd * (1 - float(commission or 0) / 100) * (1 - float(extra_discount or 0) / 100)
    return math.ceil(real_cost / float(markup))


def _recalc_extras_for_rate(rate, category, config, force=False):
    """
    Recalcula Airport/Smart/Cover como % de la venta RACK (rate.sell),
    tanto costo (en ARS, usando el T.C. general) como venta (en USD).
    Si force=False, respeta los extras marcados como manual_override.
    """
    for extra_type in EXTRA_ORDER:
        extra, _created = CarExtra.objects.get_or_create(rate=rate, type=extra_type)
        if extra.manual_override and not force:
            continue
        pct = category.pct_for(extra_type, config) / 100.0
        sell_usd = round((rate.sell or 0) * pct)
        cost_ars = round((rate.cost or 0) * pct, 2)
        extra.sell = sell_usd
        extra.cost = cost_ars
        extra.save()


def _manual_item_row(data, config, days, eff_pax):
    """Computes one manually-added quote line (Hertz importer / online quoter).

    amount → (+21% IVA if the amount is loaded without IVA) → USD → increase
    (the Hertz modal's "Aumento" box when sent, otherwise config.increase) →
    markup. No commission / extra_discount (same as the generic Hertz items).
    Returns None when the payload is invalid.
    """
    IVA      = 1.21
    exchange = float(config.exchange or 1) or 1
    markup   = float(config.markup or 1) or 1
    # The Hertz-import "Aumento %" box carries the general increase as its default,
    # so when it's sent it *replaces* config.increase (not stacked). Absent → config.
    _ei          = data.get("extra_increase")
    increase_pct = float(config.increase or 0) if _ei is None else float(_ei or 0)
    tot_inc  = 1.0 + increase_pct / 100.0
    days     = max(1, int(days or 1))
    eff_pax  = max(1, int(eff_pax or 1))

    label = re.sub(r"\s+", " ", str(data.get("label") or "")).strip()
    try:
        amount = float(data.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if not label or amount <= 0:
        return None

    is_usd     = str(data.get("currency") or "ARS").upper() == "USD"
    per_day    = bool(data.get("per_day"))
    with_iva   = amount if data.get("iva_included") else amount * IVA
    amount_usd = with_iva if is_usd else with_iva / exchange

    if per_day:
        sell_pd = math.ceil(amount_usd * tot_inc / markup / eff_pax) * eff_pax
        return {"label": label, "per_day": True,
                "sell_per_day": sell_pd, "sell_total": sell_pd * days}

    sell_total = math.ceil(amount_usd * tot_inc / markup / eff_pax) * eff_pax
    return {"label": label, "per_day": False,
            "sell_per_day": None, "sell_total": sell_total}


def _car_daily_sell(rack, usd, block_increase, config):
    """RACK (ARS incl. IVA, or USD) → (daily cost USD, sell USD) for the
    destination rates table. Same base-rental logic as the quoter: extra
    discount → commission (flat) → ÷ exchange (ARS only) → + increase → ÷ markup."""
    rack = float(rack or 0)
    if not rack:
        return None, None
    exchange  = float(config.exchange or 1) or 1
    markup    = float(config.markup or 1) or 1
    comm_dec  = float(config.commission or 0) / 100.0
    disc_f    = 1.0 - float(config.extra_discount or 0) / 100.0
    total_inc = 1.0 + (float(config.increase or 0) + float(block_increase or 0)) / 100.0
    rack_usd  = rack if usd else rack / exchange
    daily     = rack_usd * (1 - comm_dec) * disc_f * total_inc
    sell      = math.ceil(daily / markup)
    return daily, sell


# ─── Página principal: Destinos ──────────────────────────────────────────

@login_required
def destinations(request):
    """Lista de destinos con categorías cargadas + configuración general
    (markup, tipo de cambio) + gestión de costos fijos."""
    config = CarHireConfig.get_solo()

    locations = (
        Location.objects
        .filter(car_categories__isnull=False)
        .distinct()
        .order_by("name")
    )

    fixed_costs = list(
        CarFixedCost.objects.select_related("location")
        .values(
            "id", "name", "code", "location_id", "date_from", "date_to",
            "value", "usd", "exchange", "increase", "fcu", "per_day", "recommended",
        )
    )
    for fc in fixed_costs:
        fc["date_from"] = str(fc["date_from"]) if fc["date_from"] else None
        fc["date_to"] = str(fc["date_to"]) if fc["date_to"] else None

    # Agrupar categorías por (code, name) para el tab Modelos
    all_cats = CarCategory.objects.select_related("location").order_by("code", "name", "location__name")
    model_groups = defaultdict(list)
    for cat in all_cats:
        model_groups[(cat.code, cat.name)].append(cat)
    vehicle_models = [
        {
            "code": code,
            "name": name,
            "categories": cats,
            "locations": [c.location for c in cats],
            "pic1_url": cats[0].pic1_url,
            "max_passengers": cats[0].max_passengers,
            "max_luggage": cats[0].max_luggage,
            "transmission": cats[0].transmission,
            "note": cats[0].note or "",
            "ids": [c.id for c in cats],
            "location_ids": [c.location_id for c in cats],
        }
        for (code, name), cats in sorted(model_groups.items())
    ]

    return render(request, "tariff/car_hire/destinations.html", {
        "locations": locations,
        "all_locations": Location.objects.all().order_by("name"),
        "config": config,
        "fixed_costs_json": json.dumps(fixed_costs, default=str),
        "FCU_OPTIONS": FCU_OPTIONS,
        "vehicle_models": vehicle_models,
    })


@login_required
@csrf_exempt
def update_config(request):
    """Actualiza markup / tipo de cambio / aumento general."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    config = CarHireConfig.get_solo()
    config.markup = float(data.get("markup", config.markup))
    config.exchange = int(data.get("exchange", config.exchange))
    config.increase = float(data.get("increase", config.increase) or 0)
    config.default_airport_pct = float(data.get("default_airport_pct", config.default_airport_pct))
    config.default_smart_pct = float(data.get("default_smart_pct", config.default_smart_pct))
    config.default_cover_pct = float(data.get("default_cover_pct", config.default_cover_pct))
    config.commission = float(data.get("commission", config.commission) or 0)
    config.extra_discount = float(data.get("extra_discount", config.extra_discount) or 0)
    config.extras_rounding  = int(data.get("extras_rounding", config.extras_rounding) or 1)
    config.conditions_text  = data.get("conditions_text", config.conditions_text) or ""
    config.save()
    return JsonResponse({
        "ok": True, "markup": config.markup, "exchange": config.exchange, "increase": config.increase,
        "default_airport_pct": config.default_airport_pct,
        "default_smart_pct": config.default_smart_pct,
        "default_cover_pct": config.default_cover_pct,
        "commission": config.commission,
        "extra_discount": config.extra_discount,
        "extras_rounding": config.extras_rounding,
        "conditions_text": config.conditions_text,
    })


# ─── Categorías (equivalente a Product) ──────────────────────────────────

@login_required
def category_create(request):
    """Crea una categoría de vehículo en uno o más destinos (multipart/form-data)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    code = (request.POST.get("code") or "").upper().strip()
    name = (request.POST.get("name") or "").strip()
    location_ids = request.POST.getlist("location_ids")

    if not code or not name:
        return JsonResponse({"error": "Código y nombre son obligatorios"}, status=400)
    if not location_ids:
        return JsonResponse({"error": "Seleccioná al menos un destino"}, status=400)

    # Guardar foto una sola vez y reutilizar la ruta en todas las categorías
    pic_url = None
    photo = request.FILES.get("photo")
    if photo:
        from django.core.files.storage import default_storage
        path = default_storage.save(f"car_hire/{photo.name}", photo)
        pic_url = default_storage.url(path)

    max_passengers = request.POST.get("max_passengers") or None
    max_luggage    = request.POST.get("max_luggage") or None
    transmission   = request.POST.get("transmission") or ""
    note           = request.POST.get("note") or ""

    created = []
    for loc_id in location_ids:
        location = get_object_or_404(Location, pk=loc_id)
        last_order = (
            CarCategory.objects.filter(location=location)
            .order_by("-order").values_list("order", flat=True).first() or 0
        )
        cat = CarCategory.objects.create(
            code=code,
            name=name,
            location=location,
            order=last_order + 5,
            note=note,
            pic1_url=pic_url,
            max_passengers=max_passengers or None,
            max_luggage=max_luggage or None,
            transmission=transmission,
        )
        CarRateGroup.objects.create(name="Tarifa estándar", order=1, category=cat)
        created.append(cat.id)

    return JsonResponse({"ok": True, "created": created})


@login_required
@csrf_exempt
def category_delete(request, category_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    category = get_object_or_404(CarCategory, pk=category_id)
    category.delete()
    return JsonResponse({"ok": True})


@login_required
@csrf_exempt
def category_update_pct(request, category_id):
    """Actualiza los % propios de Airport/Smart/Cover de una categoría y
    recalcula todos sus extras existentes (respetando manual_override)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    category = get_object_or_404(CarCategory, pk=category_id)
    data = json.loads(request.body)

    category.airport_pct = data.get("airport_pct") or None
    category.smart_pct = data.get("smart_pct") or None
    category.cover_pct = data.get("cover_pct") or None
    category.save()

    config = CarHireConfig.get_solo()
    rates = CarRate.objects.filter(rate_line__group__category=category)
    for rate in rates:
        _recalc_extras_for_rate(rate, category, config)

    return JsonResponse({"ok": True})


# ─── Página de tarifas de una categoría (equivalente a supplier_rates) ───

@login_required
def category_rates(request, category_id):
    category = get_object_or_404(CarCategory, pk=category_id)
    config = CarHireConfig.get_solo()

    rate_lines = (
        CarRateLine.objects
        .filter(group__category=category)
        .select_related("group")
        .prefetch_related("line_rates", "line_rates__extras")
        .order_by("date_from")
    )

    fixed_costs = list(
        CarFixedCost.objects
        .filter(location__in=[category.location_id, None])
        .values(
            "id", "name", "code", "location_id", "date_from", "date_to",
            "value", "usd", "exchange", "increase", "fcu", "per_day", "recommended",
        )
    )
    for fc in fixed_costs:
        fc["date_from"] = str(fc["date_from"]) if fc["date_from"] else None
        fc["date_to"] = str(fc["date_to"]) if fc["date_to"] else None

    blocks = defaultdict(list)
    for line in rate_lines:
        blocks[(line.date_from, line.date_to, line.season)].append(line)

    rate_blocks = []
    for (date_from, date_to, season), lines in blocks.items():
        block_rows = []
        for line in lines:
            rate = line.line_rates.first()  # un solo Rate por línea (sin columnas de pax)
            extras_map = {e.type: e for e in (rate.extras.all() if rate else [])}
            row = {
                "rate_line_id": line.id,
                "rate": rate,
                "extras": [
                    {
                        "type": t,
                        "label": EXTRA_LABELS[t],
                        "obj": extras_map.get(t),
                    }
                    for t in EXTRA_ORDER
                ],
            }
            if rate:
                row["suggested_sell"] = _suggested_sell(rate.cost, True, config.exchange, config.markup, config.commission, config.extra_discount)
            block_rows.append(row)

        rate_blocks.append({
            "date_from": date_from,
            "date_to": date_to,
            "season": season,
            "rows": block_rows,
        })

    rate_blocks.sort(key=lambda b: b["date_from"])

    return render(request, "tariff/car_hire/rates.html", {
        "category": category,
        "location": category.location,
        "rate_blocks": rate_blocks,
        "config": config,
        "fixed_costs_json": json.dumps(fixed_costs, default=str),
        "extra_types": CAR_EXTRA_TYPES,
        "effective_pct": {
            "AIRPORT": category.pct_for("AIRPORT", config),
            "SMART": category.pct_for("SMART", config),
            "COVER": category.pct_for("COVER", config),
        },
    })


@login_required
@csrf_exempt
def create_rate_block(request):
    """Crea un nuevo bloque de vigencia (temporada) para una categoría, con
    su CarRate base + los 4 CarExtra en cero."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)

    category_id = data.get("category_id")
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    season = data.get("season", "")

    if not category_id or not date_from or not date_to:
        return JsonResponse({"ok": False, "error": "Faltan datos requeridos"}, status=400)

    category = get_object_or_404(CarCategory, pk=category_id)
    group = category.rate_groups.first()
    if not group:
        group = CarRateGroup.objects.create(name="Tarifa estándar", order=1, category=category)

    rate_line = CarRateLine.objects.create(
        date_from=date_from, date_to=date_to, group=group, season=season,
    )
    rate = CarRate.objects.create(rate_line=rate_line, cost=0, sell=0, status="Provisional")

    config = CarHireConfig.get_solo()
    _recalc_extras_for_rate(rate, category, config, force=True)  # arrancan en 0 (sell=0) pero ya creados

    return JsonResponse({"ok": True, "rate_line_id": rate_line.id, "rate_id": rate.id})


@login_required
@csrf_exempt
def delete_rate_block(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rateline_id = data.get("rateline_id")
    if not rateline_id:
        return JsonResponse({"ok": False, "error": "Falta rateline_id"}, status=400)
    deleted, _ = CarRateLine.objects.filter(pk=rateline_id).delete()
    return JsonResponse({"ok": bool(deleted)})


@login_required
@csrf_exempt
def update_rate(request):
    """Actualiza costo/venta de la tarifa base de un CarRate (equivalente a
    update_rate_block, pero sin columnas)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rate_id = data.get("rate_id")
    rate = get_object_or_404(CarRate, pk=rate_id)

    if "cost" in data:
        rate.cost = float(data["cost"] or 0)
    if "sell" in data:
        rate.sell = int(float(data["sell"] or 0))
    if "status" in data and data["status"] in ("Confirmed", "Provisional"):
        rate.status = data["status"]
    if "increase" in data:
        rate.increase = float(data["increase"] or 0)
    rate.save()

    config = CarHireConfig.get_solo()
    category = rate.rate_line.group.category
    _recalc_extras_for_rate(rate, category, config)  # respeta manual_override

    extras = {e.type: {"cost": e.cost, "sell": e.sell} for e in rate.extras.all()}
    return JsonResponse({
        "ok": True,
        "suggested_sell": _suggested_sell(rate.cost, True, config.exchange, config.markup, config.commission, config.extra_discount),
        "extras": extras,
    })


@login_required
@csrf_exempt
def update_extra(request):
    """Actualiza costo/venta de un extra (Airport/Smart/Cover) a mano.
    Al editarlo manualmente queda marcado como manual_override=True y deja
    de recalcularse automáticamente cuando cambie la tarifa RACK."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rate_id = data.get("rate_id")
    extra_type = data.get("type")
    rate = get_object_or_404(CarRate, pk=rate_id)

    extra, _created = CarExtra.objects.get_or_create(rate=rate, type=extra_type)
    if "cost" in data:
        extra.cost = float(data["cost"] or 0)
    if "sell" in data:
        extra.sell = int(float(data["sell"] or 0))
    extra.manual_override = True
    extra.save()

    config = CarHireConfig.get_solo()
    return JsonResponse({
        "ok": True,
        "suggested_sell": _suggested_sell(extra.cost, True, config.exchange, config.markup, config.commission, config.extra_discount),
    })


@login_required
@csrf_exempt
def reset_extra_auto(request):
    """Vuelve un extra al cálculo automático (% x RACK) descartando el valor manual."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rate = get_object_or_404(CarRate, pk=data.get("rate_id"))
    extra = get_object_or_404(CarExtra, rate=rate, type=data.get("type"))
    extra.manual_override = False
    extra.save()

    config = CarHireConfig.get_solo()
    category = rate.rate_line.group.category
    _recalc_extras_for_rate(rate, category, config, force=True)
    extra.refresh_from_db()
    return JsonResponse({"ok": True, "cost": extra.cost, "sell": extra.sell})


# ─── Costos fijos (equivalente a FixedRateCost) ──────────────────────────

@login_required
@csrf_exempt
def create_fixed_cost(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)

    location = None
    if data.get("location_id"):
        location = get_object_or_404(Location, pk=data["location_id"])

    frc = CarFixedCost.objects.create(
        name=data["name"],
        code=data.get("code") or None,
        location=location,
        date_from=data.get("date_from") or None,
        date_to=data.get("date_to") or None,
        value=float(data.get("value", 0)),
        usd=data.get("usd", True),
        exchange=int(data.get("exchange", 1)),
        fcu=data.get("fcu", "Group"),
        per_day=data.get("per_day", True),
        recommended=data.get("recommended", True),
        increase=float(data.get("increase", 0) or 0),
    )
    return JsonResponse({"ok": True, "id": frc.id})


@login_required
@csrf_exempt
def update_fixed_cost(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    frc = get_object_or_404(CarFixedCost, pk=data["id"])

    frc.name = data.get("name", frc.name)
    frc.code = data.get("code") or None
    frc.location_id = data.get("location_id") or None
    frc.date_from = data.get("date_from") or None
    frc.date_to = data.get("date_to") or None
    frc.value = float(data.get("value", frc.value))
    frc.usd = data.get("usd", frc.usd)
    frc.exchange = int(data.get("exchange", frc.exchange))
    frc.fcu = data.get("fcu", frc.fcu)
    frc.per_day = data.get("per_day", frc.per_day)
    frc.recommended = data.get("recommended", frc.recommended)
    frc.increase = float(data.get("increase", frc.increase) or 0)
    frc.save()
    return JsonResponse({"ok": True})


@login_required
@csrf_exempt
def delete_fixed_cost(request, frc_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    CarFixedCost.objects.filter(pk=frc_id).delete()
    return JsonResponse({"ok": True})


# ─── Tarifas por destino ─────────────────────────────────────────────────────

@login_required
def destination_rates(request, location_id):
    location = get_object_or_404(Location, pk=location_id)
    categories = CarCategory.objects.filter(location=location, isActivated=True).order_by("order")
    config = CarHireConfig.get_solo()

    all_rate_lines = (
        CarRateLine.objects
        .filter(group__category__in=categories)
        .select_related("group__category")
        .prefetch_related("line_rates")
        .order_by("date_from")
    )

    blocks_map = defaultdict(lambda: {"cats": {}, "rate_line_ids": [], "usd": False, "block_increase": 0.0})
    for rl in all_rate_lines:
        key = (rl.date_from, rl.date_to, rl.season)
        rate = rl.line_rates.first()
        blocks_map[key]["cats"][rl.group.category_id] = {"rate": rate, "rate_line_id": rl.id}
        blocks_map[key]["rate_line_ids"].append(rl.id)
        blocks_map[key]["usd"] = rl.usd
        if rate and blocks_map[key]["block_increase"] == 0.0:
            blocks_map[key]["block_increase"] = float(rate.increase or 0)

    date_blocks = []
    for (date_from, date_to, season), block_data in sorted(blocks_map.items()):
        cat_data      = block_data["cats"]
        block_usd     = block_data["usd"]
        block_inc     = block_data["block_increase"]
        rate_line_ids = block_data["rate_line_ids"]
        rows = []
        for cat in categories:
            d = cat_data.get(cat.id, {})
            rate = d.get("rate")
            rack = rate.cost if rate else None
            if rack is not None:
                daily, sell = _car_daily_sell(rack, block_usd, block_inc, config)
            else:
                daily = sell = None
            rows.append({
                "category": cat,
                "rate": rate,
                "rate_line_id": d.get("rate_line_id"),
                "rack": rack,
                "daily_cost": daily,
                "sell": sell,
            })
        date_blocks.append({
            "date_from": date_from,
            "date_to": date_to,
            "season": season,
            "usd": block_usd,
            "block_increase": block_inc,
            "rate_line_ids": rate_line_ids,
            "rows": rows,
        })

    return render(request, "tariff/car_hire/destination_rates.html", {
        "location": location,
        "categories": categories,
        "date_blocks": date_blocks,
        "config": config,
    })


@login_required
@csrf_exempt
def update_block_currency(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rate_line_ids = data.get("rate_line_ids", [])
    usd = bool(data.get("usd", False))
    CarRateLine.objects.filter(pk__in=rate_line_ids).update(usd=usd)
    return JsonResponse({"ok": True})


@login_required
@csrf_exempt
def update_block_increase(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    rate_ids = [int(r) for r in data.get("rate_ids", []) if r]
    increase = float(data.get("increase", 0) or 0)
    CarRate.objects.filter(pk__in=rate_ids).update(increase=increase)
    return JsonResponse({"ok": True})


@login_required
@csrf_exempt
def create_destination_block(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    location_id = data.get("location_id")
    date_from   = data.get("date_from")
    date_to     = data.get("date_to")
    season      = data.get("season", "")

    if not all([location_id, date_from, date_to]):
        return JsonResponse({"error": "Faltan datos"}, status=400)

    location   = get_object_or_404(Location, pk=location_id)
    categories = CarCategory.objects.filter(location=location, isActivated=True).order_by("order")
    if not categories.exists():
        return JsonResponse({"error": "No hay categorías para este destino"}, status=400)

    created = []
    for cat in categories:
        group = cat.rate_groups.first()
        if not group:
            group = CarRateGroup.objects.create(name="Tarifa estándar", order=1, category=cat)
        rl = CarRateLine.objects.create(date_from=date_from, date_to=date_to, season=season, group=group)
        rate = CarRate.objects.create(rate_line=rl, cost=0, sell=0, status="Provisional")
        created.append({"category_id": cat.id, "rate_id": rate.id, "rate_line_id": rl.id})

    return JsonResponse({"ok": True, "rates": created})


@login_required
@csrf_exempt
def create_category_rate_in_block(request):
    """Create a single CarRateLine+CarRate for a category that was added after the block existed."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data        = json.loads(request.body)
    category_id = data.get("category_id")
    date_from   = data.get("date_from")
    date_to     = data.get("date_to")
    season      = data.get("season", "")

    if not all([category_id, date_from, date_to]):
        return JsonResponse({"error": "Faltan datos"}, status=400)

    category = get_object_or_404(CarCategory, pk=category_id)
    group = category.rate_groups.first()
    if not group:
        group = CarRateGroup.objects.create(name="Tarifa estándar", order=1, category=category)

    rl   = CarRateLine.objects.create(date_from=date_from, date_to=date_to, season=season, group=group)
    rate = CarRate.objects.create(rate_line=rl, cost=0, sell=0, status="Provisional")
    return JsonResponse({"ok": True, "rate_id": rate.id, "rate_line_id": rl.id})


@login_required
@csrf_exempt
def delete_destination_block(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    location_id = data.get("location_id")
    date_from   = data.get("date_from")
    date_to     = data.get("date_to")
    season      = data.get("season", "")

    location   = get_object_or_404(Location, pk=location_id)
    categories = CarCategory.objects.filter(location=location)
    deleted, _ = CarRateLine.objects.filter(
        group__category__in=categories,
        date_from=date_from,
        date_to=date_to,
        season=season,
    ).delete()
    return JsonResponse({"ok": True, "deleted": deleted})


@login_required
@csrf_exempt
def copy_destination_block(request):
    """Duplica una vigencia completa (todas las categorías del destino) a nuevas
    fechas. El 'aumento' del modal se guarda como Aum.% del bloque nuevo
    (CarRate.increase); el RACK se copia sin tocar y la venta se recalcula."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)

    location_id = data.get("location_id")
    src_from    = data.get("src_date_from")
    src_to      = data.get("src_date_to")
    src_season  = data.get("src_season", "") or ""
    new_from    = data.get("date_from")
    new_to      = data.get("date_to")
    new_season  = data.get("season", "") or ""
    increase    = float(data.get("increase") or 0)

    if not all([location_id, src_from, src_to, new_from, new_to]):
        return JsonResponse({"ok": False, "error": "Faltan datos"}, status=400)
    if new_to < new_from:
        return JsonResponse({"ok": False, "error": "La fecha de fin debe ser posterior a la de inicio"}, status=400)

    location   = get_object_or_404(Location, pk=location_id)
    categories = CarCategory.objects.filter(location=location)

    src_lines = list(
        CarRateLine.objects
        .filter(group__category__in=categories,
                date_from=src_from, date_to=src_to, season=src_season)
        .select_related("group")
        .prefetch_related("line_rates", "line_rates__extras")
    )
    if not src_lines:
        return JsonResponse({"ok": False, "error": "No se encontró la vigencia original"}, status=404)

    if CarRateLine.objects.filter(
        group__category__in=categories,
        date_from=new_from, date_to=new_to, season=new_season,
    ).exists():
        return JsonResponse({"ok": False, "error": "Ya existe una vigencia con esas fechas"}, status=409)

    config  = CarHireConfig.get_solo()
    created = 0
    for line in src_lines:
        new_line = CarRateLine.objects.create(
            date_from=new_from, date_to=new_to, season=new_season,
            group=line.group, usd=line.usd, is_revised=line.is_revised,
        )
        for rate in line.line_rates.all():
            new_increase = increase if increase else float(rate.increase or 0)
            _daily, new_sell = _car_daily_sell(rate.cost, new_line.usd, new_increase, config)
            new_rate = CarRate.objects.create(
                rate_line=new_line,
                status=rate.status,
                increase=new_increase,
                cost=rate.cost,
                sell=new_sell or 0,
                locked=rate.locked,
            )
            for ex in rate.extras.all():
                CarExtra.objects.create(
                    rate=new_rate, type=ex.type,
                    cost=ex.cost, sell=ex.sell,
                    manual_override=ex.manual_override,
                )
            created += 1

    return JsonResponse({"ok": True, "created": created})


# ─── Edición de modelo de vehículo (aplica a todas las categorías del modelo) ─

@login_required
def category_update_model(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    old_code = request.POST.get("old_code", "").strip()
    old_name = request.POST.get("old_name", "").strip()
    new_code = request.POST.get("code", "").upper().strip()
    new_name = request.POST.get("name", "").strip()
    location_ids = request.POST.getlist("location_ids")

    if not new_code or not new_name:
        return JsonResponse({"error": "Código y nombre son obligatorios"}, status=400)

    existing = list(CarCategory.objects.filter(code=old_code, name=old_name).select_related("location"))
    existing_map = {str(c.location_id): c for c in existing}

    pic_url = None
    photo = request.FILES.get("photo")
    if photo:
        from django.core.files.storage import default_storage
        path = default_storage.save(f"car_hire/{photo.name}", photo)
        pic_url = default_storage.url(path)
    elif existing:
        pic_url = existing[0].pic1_url

    max_passengers = request.POST.get("max_passengers") or None
    max_luggage    = request.POST.get("max_luggage") or None
    transmission   = request.POST.get("transmission") or ""
    note           = request.POST.get("note", "").strip()

    for cat in existing:
        if str(cat.location_id) in location_ids:
            cat.code = new_code
            cat.name = new_name
            cat.max_passengers = max_passengers or None
            cat.max_luggage    = max_luggage or None
            cat.transmission   = transmission
            cat.note           = note
            if pic_url:
                cat.pic1_url = pic_url
            cat.save()
        else:
            cat.delete()

    for loc_id in location_ids:
        if loc_id not in existing_map:
            location = get_object_or_404(Location, pk=loc_id)
            last = CarCategory.objects.filter(location=location).order_by("-order").values_list("order", flat=True).first() or 0
            cat = CarCategory.objects.create(
                code=new_code, name=new_name, location=location, order=last + 5,
                max_passengers=max_passengers or None, max_luggage=max_luggage or None,
                transmission=transmission, note=note, pic1_url=pic_url,
            )
            CarRateGroup.objects.create(name="Tarifa estándar", order=1, category=cat)

    return JsonResponse({"ok": True})


# ─── Cotizador online ─────────────────────────────────────────────────────────

@login_required
def quoter_page(request):
    # Por ahora el cotizador de alquiler es solo para usuarios internos.
    if getattr(request.user, "userType", None) == "Cliente":
        return redirect("tariff")

    locations_with_cats = (
        Location.objects
        .filter(car_categories__isnull=False, car_categories__isActivated=True)
        .distinct()
        .order_by("name")
    )
    all_cats = (
        CarCategory.objects
        .filter(isActivated=True)
        .select_related("location")
        .order_by("location_id", "code", "name")
    )
    cats_by_location = defaultdict(list)
    for cat in all_cats:
        cats_by_location[cat.location_id].append({"id": cat.id, "code": cat.code, "name": cat.name})

    config = CarHireConfig.get_solo()
    return render(request, "tariff/car_hire/quoter.html", {
        "locations": locations_with_cats,
        "cats_by_location_json": json.dumps(dict(cats_by_location)),
        "conditions_text": config.conditions_text,
        "config_markup": config.markup,
        "config_exchange": config.exchange,
        "config_increase": config.increase,
    })


@login_required
@csrf_exempt
def quoter_list_categories(request):
    """Categories with rates sorted cheapest first. date is optional:
    when omitted, uses the most recently added rate per category for ordering."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data        = json.loads(request.body)
    location_id = data.get("location_id")
    check_in    = data.get("date") or None
    passengers  = max(1, int(data.get("passengers") or 2))

    if not location_id:
        return JsonResponse({"error": "Missing location_id"}, status=400)

    config      = CarHireConfig.get_solo()
    exchange    = float(config.exchange or 1)
    markup      = float(config.markup or 1)
    comm_dec    = float(config.commission or 0) / 100.0
    disc_factor = 1.0 - float(config.extra_discount or 0) / 100.0

    base_qs = CarRate.objects.filter(
        rate_line__group__category__location_id=location_id,
        rate_line__group__category__isActivated=True,
    ).select_related("rate_line__group__category")

    if check_in:
        rates = base_qs.filter(
            rate_line__date_from__lte=check_in,
            rate_line__date_to__gte=check_in,
        ).order_by("rate_line__group__category__order", "rate_line__date_from")
    else:
        # No date: pick most recently added rate per category to determine price order
        rates = base_qs.order_by(
            "rate_line__group__category__order", "-rate_line__date_from"
        )

    seen = {}
    for rate in rates:
        cat = rate.rate_line.group.category
        if cat.id not in seen and float(rate.cost or 0) > 0:
            seen[cat.id] = (cat, rate)

    # Period (block) increase for the chosen date — normally uniform across the
    # block; surface the highest if they differ. None when no date was given.
    period_increase = None
    if check_in and seen:
        period_increase = max(float(rate.increase or 0) for _, rate in seen.values())

    results = []
    for cat, rate in seen.values():
        total_inc = 1.0 + (float(config.increase or 0) + float(rate.increase or 0)) / 100.0
        rack_raw  = float(rate.cost or 0)
        eff_pax   = max(1, min(passengers, cat.max_passengers or passengers))

        # Base sell: discount, then commission, ÷ exchange (ARS only), + increase, ÷ markup
        rack_usd = rack_raw if rate.rate_line.usd else rack_raw / exchange
        base_raw = rack_usd * (1 - comm_dec) * disc_factor * total_inc / markup

        sell_per_day = math.ceil(base_raw / eff_pax) * eff_pax

        results.append({
            "id":           cat.id,
            "code":         cat.code,
            "name":         cat.name,
            "sell_per_day": sell_per_day,
        })

    results.sort(key=lambda x: x["sell_per_day"])
    return JsonResponse({"ok": True, "categories": results, "period_increase": period_increase})


@login_required
@csrf_exempt
def quoter_calculate(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data        = json.loads(request.body)
    location_id = data.get("location_id")
    category_id = data.get("category_id")
    check_in    = data.get("date")
    days        = max(1, int(data.get("days", 1)))
    passengers  = max(1, int(data.get("passengers", 1)))

    if not all([location_id, category_id, check_in]):
        return JsonResponse({"error": "Missing parameters"}, status=400)

    category = get_object_or_404(CarCategory, pk=category_id, location_id=location_id)
    config   = CarHireConfig.get_solo()

    rate = (
        CarRate.objects
        .filter(
            rate_line__group__category=category,
            rate_line__date_from__lte=check_in,
            rate_line__date_to__gte=check_in,
        )
        .select_related("rate_line")
        .order_by("rate_line__date_from")
        .first()
    )

    if not rate:
        return JsonResponse({"error": "No rate found for this vehicle and date."})

    max_pax      = category.max_passengers or passengers
    exceeds      = passengers > max_pax
    eff_pax      = min(passengers, max_pax)

    exchange     = float(config.exchange or 1)
    markup       = float(config.markup or 1)

    rack_raw    = float(rate.cost or 0)
    comm_dec    = float(config.commission or 0) / 100.0
    disc_factor = 1.0 - float(config.extra_discount or 0) / 100.0

    # Peak-period surcharge: any hire day on a public holiday / long weekend
    # (external calendar) adds a flat % to the quote.
    try:
        _start = date.fromisoformat(check_in)
        _end   = _start + timedelta(days=days - 1)
        special_hits = _special_calendar_hits(int(location_id), _start, _end)
    except (ValueError, TypeError):
        special_hits = []
    surcharge_pct = SPECIAL_DATES_SURCHARGE_PCT if special_hits else 0.0

    # Combined increase: global config + per-period rate increase + peak surcharge
    total_inc = 1.0 + (float(config.increase or 0) + float(rate.increase or 0) + surcharge_pct) / 100.0

    rack_usd = rack_raw if rate.rate_line.usd else rack_raw / exchange

    # Base sell: discount, then commission, ÷ exchange (ARS only), + increase, ÷ markup
    base_raw = rack_usd * (1 - comm_dec) * disc_factor * total_inc / markup
    if eff_pax > 0:
        sell_per_day = math.ceil(base_raw / eff_pax) * eff_pax
    else:
        sell_per_day = math.ceil(base_raw)

    # Extras: % of RACK (USD) × increase ÷ markup → ceil per pax → × pax
    extras_data = []
    for etype in EXTRA_ORDER:
        pct       = category.pct_for(etype, config) / 100.0
        extra_raw = rack_usd * pct * total_inc / markup          # per vehicle per day, USD
        if eff_pax > 0:
            extra_sell = math.ceil(extra_raw / eff_pax) * eff_pax
        else:
            extra_sell = math.ceil(extra_raw)
        extras_data.append({
            "type":         etype,
            "label":        EXTRA_LABELS.get(etype, etype),
            "pct":          round(pct * 100, 1),
            "sell_per_day": extra_sell,
        })

    # Fixed costs: cost → USD → apply markup → sell
    loc_id_int = int(location_id)
    fixed_costs = list(
        CarFixedCost.objects
        .filter(Q(location_id=loc_id_int) | Q(location__isnull=True))
        .values("id", "name", "value", "usd", "exchange", "fcu", "per_day", "recommended")
    )
    for fc in fixed_costs:
        value_usd = float(fc["value"]) if fc["usd"] else float(fc["value"]) / exchange
        raw       = value_usd / markup
        # round up per passenger — per day for daily costs, on the one-time total
        # for the rest (frontend multiplies daily costs by the number of days)
        fc["sell"] = math.ceil(raw / eff_pax) * eff_pax if eff_pax > 0 else math.ceil(raw)

    return JsonResponse({
        "category": {
            "code":           category.code,
            "name":           category.name,
            "pic1_url":       category.pic1_url or "",
            "max_passengers": max_pax,
            "max_luggage":    category.max_luggage,
            "transmission":   category.get_transmission_display() if category.transmission else "",
            "note":           category.note or "",
        },
        "sell_per_day":       sell_per_day,
        "extras":             extras_data,
        "fixed_costs":        fixed_costs,
        "days":               days,
        "passengers":         passengers,
        "effective_passengers": eff_pax,
        "exceeds_capacity":   exceeds,
        "special_dates": {
            "surcharge_pct": surcharge_pct,
            "entries": [
                {
                    "name":     h["name"] or h["category"].replace("_", " ").title(),
                    "category": h["category"],
                    "from":     h["date_from"].isoformat(),
                    "to":       h["date_to"].isoformat(),
                }
                for h in special_hits
            ],
        },
    })


@login_required
@csrf_exempt
def quoter_category_info(request):
    """Return category metadata (photo, specs, note) without requiring a rate."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    data = json.loads(request.body)
    cat  = get_object_or_404(CarCategory, pk=data.get("category_id"))
    return JsonResponse({
        "code":           cat.code,
        "name":           cat.name,
        "pic1_url":       cat.pic1_url or "",
        "max_passengers": cat.max_passengers,
        "max_luggage":    cat.max_luggage,
        "transmission":   cat.get_transmission_display() if cat.transmission else "",
        "note":           cat.note or "",
    })


@login_required
@csrf_exempt
def quoter_manual_item(request):
    """Compute a single manually-added quote line. Non-client users only."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if getattr(request.user, "userType", None) == "Cliente":
        return JsonResponse({"ok": False, "error": "No autorizado"}, status=403)

    data   = json.loads(request.body)
    config = CarHireConfig.get_solo()
    row = _manual_item_row(data, config, data.get("days", 1), data.get("passengers", 1))
    if not row:
        return JsonResponse({"ok": False, "error": "Ingresá descripción y monto."}, status=400)
    return JsonResponse({"ok": True, "item": row})


@login_required
@csrf_exempt
def quoter_hertz_fixed_costs(request):
    """The loaded fixed costs (CarFixedCost), priced for the Hertz importer so
    they can be ticked into a pasted/PDF quote: same formula as the online
    quoter's fixed costs + the modal's 'Aumento %' + per-passenger rounding.
    Non-client users only."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if getattr(request.user, "userType", None) == "Cliente":
        return JsonResponse({"ok": False, "error": "No autorizado"}, status=403)

    data        = json.loads(request.body)
    passengers  = max(1, int(data.get("passengers") or 2))
    days        = max(1, int(data.get("days") or 1))
    location_id = data.get("location_id")

    config   = CarHireConfig.get_solo()
    exchange = float(config.exchange or 1) or 1
    markup   = float(config.markup or 1) or 1
    _ei          = data.get("extra_increase")
    increase_pct = float(config.increase or 0) if _ei is None else float(_ei or 0)
    tot_inc  = 1.0 + increase_pct / 100.0
    eff_pax  = max(1, passengers)

    qs = CarFixedCost.objects.all()
    if location_id:
        qs = qs.filter(Q(location_id=int(location_id)) | Q(location__isnull=True))

    rows = []
    for fc in qs.values("id", "name", "value", "usd", "per_day", "recommended",
                        "location__code", "location__name"):
        value_usd = float(fc["value"]) if fc["usd"] else float(fc["value"]) / exchange
        sell_pd   = math.ceil(value_usd * tot_inc / markup / eff_pax) * eff_pax
        if fc["location__code"]:
            location = f'{fc["location__code"]} — {fc["location__name"]}'
        else:
            location = "Todos los destinos"
        rows.append({
            "id":           fc["id"],
            "label":        fc["name"],
            "location":     location,
            "global":       not fc["location__code"],
            "per_day":      fc["per_day"],
            "recommended":  fc["recommended"],
            "sell_per_day": sell_pd if fc["per_day"] else None,
            "sell_total":   sell_pd * days if fc["per_day"] else sell_pd,
        })
    rows.sort(key=lambda r: (not r["recommended"], not r["global"], r["label"].lower()))
    return JsonResponse({"ok": True, "fixed_costs": rows})


@login_required
@csrf_exempt
def quoter_parse_email(request):
    """
    Parse a pasted Hertz Argentina quote email and calculate sell prices
    using the current CarHireConfig markup/commission/exchange settings.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if getattr(request.user, "userType", None) == "Cliente":
        return JsonResponse({"ok": False, "error": "No autorizado"}, status=403)

    data       = json.loads(request.body)
    text       = data.get("text", "")
    passengers = max(1, int(data.get("passengers") or 2))

    config   = CarHireConfig.get_solo()
    exchange = float(config.exchange or 1)
    markup   = float(config.markup or 1) if config.markup else 1
    comm     = float(config.commission or 0) / 100.0
    disc     = float(config.extra_discount or 0) / 100.0
    # The Hertz-import "Aumento %" box is prefilled with the general increase and
    # is the single increase applied here — it replaces config.increase, not adds
    # to it. When it isn't sent at all, fall back to config.increase.
    _ei          = data.get("extra_increase")
    increase_pct = float(config.increase or 0) if _ei is None else float(_ei or 0)
    tot_inc  = 1.0 + increase_pct / 100.0
    IVA      = 1.21
    eff_pax  = max(1, passengers)

    def parse_ars(s):
        return float(s.replace(".", "").replace(",", "."))

    # Single-line version (collapse ALL whitespace) for multi-line item patterns
    text_1 = re.sub(r"\s+", " ", text)

    items_raw = []
    days      = 1
    seen      = set()

    # ── 1. Base rental – daily: "Reserva por X días ($ 79.356,04 x día)" ──────
    m = re.search(
        r"Reserva por\s+(\d+)\s+d[íi]as?\s*\(\$\s*([\d.,]+)\s*x\s*d[íi]a\)",
        text_1, re.IGNORECASE,
    )
    if m:
        days = int(m.group(1))
        items_raw.append({"label": "Alquiler base", "rack_ars": parse_ars(m.group(2)), "per_day": True})
        seen.add("alquiler base")
    else:
        # Weekly: "Reserva por X días ($ Y x semana)"  → divide by 7
        m2 = re.search(
            r"Reserva por\s+(\d+)\s+d[íi]as?\s*\(\$\s*([\d.,]+)\s*x\s*semana\)",
            text_1, re.IGNORECASE,
        )
        if m2:
            days = int(m2.group(1))
            items_raw.append({"label": "Alquiler base", "rack_ars": parse_ars(m2.group(2)) / 7, "per_day": True})
            seen.add("alquiler base")

    # ── 2. Additional driver — ALWAYS a per-day charge, rounded per pax per day.
    #    Hertz writes this line in several shapes; we look at the text right after
    #    the label and work out the *daily* figure:
    #      "Conductor Adicional ($ 6.000,00 por Día) x 3 Días - Agencia $ 18.000,00"
    #      "Conductor Adicional - Agencia $ 6.000,00"
    #      "Conductor Adicional x 3 Días - Agencia $ 18.000,00"
    #      "Conductor Adicional $ 6.000,00 por día"
    cond_full = None
    cm = re.search(r"Conductor(?:es)? Adicional(?:es)?\b", text_1, re.IGNORECASE)
    if cm:
        window   = text_1[cm.end():cm.end() + 160]
        amounts  = re.findall(r"\$\s*([\d.,]+)", window)
        ndays_m  = re.search(r"x\s*(\d+)\s*d[íi]as?|por\s*(\d+)\s*d[íi]as?", window, re.IGNORECASE)
        per_dia  = re.search(r"por\s*d[íi]a|x\s*d[íi]a|diari[oa]", window, re.IGNORECASE)
        if amounts:
            n_days = int(next(g for g in ndays_m.groups() if g)) if ndays_m else 0
            if per_dia:
                # the "$ X por día" figure is already the daily rate
                daily_amt = parse_ars(amounts[0])
            elif n_days:
                # first amount after "x N Días" is the lump sum → prorate to one day
                daily_amt = parse_ars(amounts[0]) / max(1, n_days)
            else:
                # a bare "$ X" next to the label — Hertz quotes the driver per day
                daily_amt = parse_ars(amounts[0])
            if daily_amt > 0:
                items_raw.append({"label": "Conductor Adicional",
                                  "rack_ars": daily_amt, "per_day": True})
                seen.add("conductor adicional")
                # blank out the label + its whole trailing shape so the generic
                # matcher below can't add the driver a second time (or pick up a
                # stray "Días - Agencia $ …" fragment)
                tail = re.match(
                    r"\s*\(\$?[^)\n]*\)"
                    r"(?:\s*x\s*\d+\s*d[íi]as?)?"
                    r"(?:\s*-\s*[Aa]gencia\s*\$\s*[\d.,]+)?"
                    r"|\s*(?:x\s*\d+\s*d[íi]as?\s*)?-\s*[Aa]gencia\s*\$\s*[\d.,]+"
                    r"|\s*\$\s*[\d.,]+(?:\s*(?:por\s*d[íi]a|diari[oa]))?",
                    window, re.IGNORECASE,
                )
                cond_full = text_1[cm.start():cm.end() + (tail.end() if tail else 0)]

    if cond_full:
        text_1 = text_1.replace(cond_full, " ", 1)

    # ── 3. Generic: any "LABEL (optional-paren) - Agencia $ AMOUNT" ────────────
    # Skips: IVA, % OFF, Total, Deducibles, Garantía, Franquicia, Reserva, Conductor
    SKIP = re.compile(
        r"\b(iva|off|total|deducible|garantía|garantia|franquicia|solicitud|reserva|conductor)\b",
        re.IGNORECASE,
    )
    # Label: capital start, no $ or newline inside ($ in content would be part of day-rate
    # parentheticals like "($ 79.356,04 x día)", stopping the label early so those lines
    # won't match the generic pattern).
    # No IGNORECASE here: uppercase-only start prevents "x 3 Días" continuation
    # lines (which appear on same line as Conductor Adicional) from matching.
    generic_re = re.compile(
        r"(?:\(\d+\)\s+)?"                    # optional "(N) " prefix
        r"([A-ZÁÉÍÓÚÑ][^$\n]{2,80}?)"         # label — uppercase start, no $ inside
        r"(?:\s*\([^)]*\))?"                   # optional parenthetical (Precio variable...)
        r"\s*-\s*[Aa]gencia"                   # agency marker
        r"\s*\$\s*([\d.,]+)",                  # amount
    )
    for gm in generic_re.finditer(text_1):
        raw = gm.group(1).strip()
        if SKIP.search(raw):
            continue
        label = re.sub(r"\s+", " ", raw).strip(" -,")
        key   = label.lower()
        if not label or len(label) < 2 or key in seen:
            continue
        amount = parse_ars(gm.group(2))
        if amount <= 0:
            continue
        seen.add(key)
        items_raw.append({"label": label, "amount_ars": amount, "per_day": False})

    # Rack (ARS, net of IVA) of the base daily rate, if it was parsed — used
    # below to cross-check extra lines against the %-based formula.
    base_rack_ars = next(
        (it["rack_ars"] for it in items_raw if it["label"] == "Alquiler base"), None
    )

    def _pct_comparison(pct_value):
        """What a line would cost if computed as a % of the daily base (same
        formula/rounding as the 'extras' in the online quoter) instead of trusting
        Hertz's own amount. None when there's no parsed base to compare against."""
        if not base_rack_ars or not pct_value:
            return None
        pct = float(pct_value) / 100.0
        rack_usd = base_rack_ars * IVA / exchange
        extra_raw = rack_usd * pct * tot_inc / markup
        sell_pd = math.ceil(extra_raw / eff_pax) * eff_pax
        return {
            "pct": round(pct * 100, 1),
            "sell_per_day": sell_pd,
            "sell_total": sell_pd * days,
        }

    # Match a parsed line label (ES/EN) to the config % it should be cross-checked
    # against: airport tax, Smart cover, Tyre/Glass cover.
    _EXTRA_LABEL_PCTS = [
        (re.compile(r"aeropuerto|airport", re.IGNORECASE), config.default_airport_pct),
        (re.compile(r"\bsmart\b", re.IGNORECASE), config.default_smart_pct),
        (re.compile(r"tyre|tire|cubierta|cristal|parabris|windscreen|"
                    r"windshield|neum[aá]tic|\bcover\b", re.IGNORECASE),
         config.default_cover_pct),
    ]

    def _comparison_for(label):
        for rx, pct in _EXTRA_LABEL_PCTS:
            if rx.search(label):
                return _pct_comparison(pct)
        return None

    # ── Calculate sell prices ─────────────────────────────────────────────────
    result_items = []
    for item in items_raw:
        compare = _comparison_for(item["label"])
        if item.get("per_day") and "rack_ars" in item:
            if item["label"] == "Alquiler base":
                # Hertz line amounts are net of IVA (unlike the RACK field in the
                # destination-rates table, which is entered with IVA already
                # included) → gross up +21% first, then: discount → commission
                # → ÷ exchange → + increase → ÷ markup, same as the RACK formula.
                raw_pd = item["rack_ars"] * IVA * (1 - disc) * (1 - comm) / exchange * tot_inc / markup
            else:
                rack_usd = item["rack_ars"] * IVA / exchange
                raw_pd = rack_usd * tot_inc / markup
            sell_pd = math.ceil(raw_pd / eff_pax) * eff_pax
            result_items.append({
                "label":        item["label"],
                "per_day":      True,
                "sell_per_day": sell_pd,
                "sell_total":   sell_pd * days,
                "compare":      compare,
            })
        elif "amount_ars" in item:
            # Per-reservation total: add IVA, apply increase, convert to USD, apply
            # markup, then round the total up per passenger
            raw_total  = item["amount_ars"] * IVA * tot_inc / exchange / markup
            sell_total = math.ceil(raw_total / eff_pax) * eff_pax
            result_items.append({
                "label":        item["label"],
                "per_day":      False,
                "sell_per_day": None,
                "sell_total":   sell_total,
                "compare":      compare,
            })

    # ── Best-effort: detect the destination + Hertz category from the text ────
    text_norm = _strip_accents(re.sub(r"\s+", " ", text)).lower()
    detected_location_id = None
    detected_category_id = None
    for loc in (Location.objects
                .filter(car_categories__isnull=False).distinct()
                .values("id", "code", "name")):
        code  = _strip_accents(loc["code"] or "").lower()
        words = [w for w in re.split(r"[^a-z0-9]+", _strip_accents(loc["name"]).lower()) if len(w) >= 4]
        if (code and re.search(rf"\b{re.escape(code)}\b", text_norm)) or \
           any(re.search(rf"\b{re.escape(w)}\b", text_norm) for w in words):
            detected_location_id = loc["id"]
            break

    cat_qs = CarCategory.objects.filter(isActivated=True)
    if detected_location_id:
        cat_qs = cat_qs.filter(location_id=detected_location_id)
    for cat in cat_qs.values("id", "code", "location_id"):
        ccode = _strip_accents(cat["code"] or "").lower()
        if ccode and re.search(rf"\b{re.escape(ccode)}\b", text_norm):
            detected_category_id = cat["id"]
            detected_location_id = detected_location_id or cat["location_id"]
            break

    grand_total = sum(i["sell_total"] for i in result_items)
    return JsonResponse({
        "ok":            True,
        "days":          days,
        "passengers":    passengers,
        "items":         result_items,
        "grand_total":   grand_total,
        "per_passenger": math.ceil(grand_total / eff_pax),
        "detected_location_id": detected_location_id,
        "detected_category_id": detected_category_id,
    })
