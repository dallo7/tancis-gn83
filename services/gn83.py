"""GN No. 83 (2026) minimum agency fee engine."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.config import (
    EXEMPT_STATUSES,
    GN83_SCHEDULE,
    GN83_USD_TZS_RATE,
    INHOUSE_CLEARER_TINS,
    SERVICE_FEE_RATE,
    VAT_RATE,
)

LIQUID_BULK_KEYWORDS = (
    "bulk liquid",
    "liquid bulk",
    "palm oil",
    "crude oil",
    "fuel oil",
    "vegetable oil",
    "molasses",
    "chemical liquid",
    "edible oil",
    "lubricant",
    "hydrocarbon",
)

DRY_BULK_KEYWORDS = (
    "dry bulk",
    "bulk cargo",
    "wheat",
    "maize",
    "corn",
    "rice",
    "cement",
    "clinker",
    "coal",
    "grain",
    "soda ash",
    "copper concentrate",
    "mineral ore",
    "bulk fertiliser",
    "bulk fertilizer",
)

HEAVY_MACHINERY_KEYWORDS = (
    "heavy machine",
    "heavy equipment",
    "excavator",
    "bulldozer",
    "crane",
    "generator set",
    "industrial plant",
)

LIVE_ANIMAL_KEYWORDS = (
    "live animal",
    "livestock",
    "cattle",
    "goat",
    "sheep",
    "pig",
    "chicken",
)

MOTOR_VEHICLE_KEYWORDS = (
    "motor vehicle",
    "motor_vehicle",
    "motorcycle",
    "truck",
    "bus",
    "trailer",
    "automobile",
    "vehicle with engine",
)


def _normalize_route(value: str) -> str:
    route = (value or "IMPORT").strip().upper()
    if route in {"IMPORT", "IMPORTATION"}:
        return "IMPORT"
    if route in {"EXPORT", "EXPORTATION"}:
        return "EXPORT"
    if route in {"TRANSIT", "TRANSITATION"}:
        return "TRANSIT"
    return "IMPORT"


def _normalize_transport(value: str) -> str:
    mode = (value or "SEA").strip().upper()
    if mode in {"SEA", "INLAND WATERWAY", "INLAND WATERWAYS", "WATER", "LAKE"}:
        return "SEA"
    if mode in {"ROAD", "LAND", "RAIL", "RAILWAY"}:
        return "ROAD"
    if mode in {"AIR", "AIRCRAFT"}:
        return "AIR"
    return "SEA"


def _cargo_text(message_info: Dict[str, Any]) -> str:
    cargo = message_info.get("cargo") or []
    return " ".join(str(item.get("item_description") or "") for item in cargo)


def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _container_counts(message_info: Dict[str, Any]) -> Tuple[int, int]:
    count_20 = 0
    count_40 = 0
    for item in message_info.get("cargo") or []:
        for container in item.get("containers") or []:
            size = str(container.get("container_size") or "").upper().replace(" ", "")
            if "40" in size:
                count_40 += 1
            elif "20" in size:
                count_20 += 1
            else:
                count_20 += 1
    return count_20, count_40


def _metric_tonnes(message_info: Dict[str, Any]) -> float:
    consignment = message_info.get("consignment") or {}
    weight = float(consignment.get("gross_weight") or 0)
    unit = str(consignment.get("gross_weight_unit") or "KG").upper().strip()
    if unit in {"MT", "TON", "TONNE", "TONNES", "T"}:
        return round(weight, 4)
    if unit in {"KG", "KGS", "KILOGRAM", "KILOGRAMS"}:
        return round(weight / 1000.0, 4)
    if unit in {"G", "GRAM", "GRAMS"}:
        return round(weight / 1_000_000.0, 6)
    return round(weight / 1000.0, 4)


def _count_units(message_info: Dict[str, Any], default: int = 1) -> int:
    cargo = message_info.get("cargo") or []
    total = 0
    for item in cargo:
        qty = item.get("quantity") or item.get("no_of_units") or item.get("units")
        if qty is not None:
            try:
                total += max(int(float(qty)), 0)
            except (TypeError, ValueError):
                total += 1
        else:
            total += 1
    return max(total, default)


def _schedule(route: str, transport: str) -> Dict[str, Dict[str, Any]]:
    return GN83_SCHEDULE.get(route, GN83_SCHEDULE["IMPORT"]).get(
        transport, GN83_SCHEDULE["IMPORT"]["SEA"]
    )


def is_exempted_payload(message_info: Dict[str, Any]) -> bool:
    """True when TANCIS marks the consignment exempt via message_info.status."""
    status = str(message_info.get("status") or "").strip().lower()
    return status in EXEMPT_STATUSES


def is_inhouse_clearer(declarant_tin: str) -> bool:
    cleaned = (declarant_tin or "").replace("-", "").strip()
    return cleaned in {t.replace("-", "").strip() for t in INHOUSE_CLEARER_TINS}


def resolve_tariff(message_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve the GN 83 schedule line and quantity for a consignment payload.
    Returns USD minimum before TZS conversion.
    """
    route = _normalize_route(str(message_info.get("route_type") or "IMPORT"))
    transport = _normalize_transport(str(message_info.get("transport_mode") or "SEA"))
    table = _schedule(route, transport)
    text = _cargo_text(message_info)
    count_20, count_40 = _container_counts(message_info)

    status = str(message_info.get("status") or "").strip().lower()
    if status in {"post_entry", "post entry", "ex_bond", "ex-bond"} and "POST_ENTRY" in table:
        line = table["POST_ENTRY"]
        return {
            "tariff_code": "POST_ENTRY",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": 1.0,
            "usd_rate": line["usd"],
            "usd_total": line["usd"],
        }

    if status in {"coastwise", "transire", "carriage_coastwise"} and "COASTWISE" in table:
        line = table["COASTWISE"]
        return {
            "tariff_code": "COASTWISE",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": 1.0,
            "usd_rate": line["usd"],
            "usd_total": line["usd"],
        }

    if count_20 or count_40:
        usd_total = 0.0
        parts: List[str] = []
        if count_20 and "CONTAINER_20FT" in table:
            line = table["CONTAINER_20FT"]
            usd_total += count_20 * line["usd"]
            parts.append(f"{count_20} × 20FT @ USD {line['usd']:.2f}")
        if count_40 and "CONTAINER_40FT" in table:
            line = table["CONTAINER_40FT"]
            usd_total += count_40 * line["usd"]
            parts.append(f"{count_40} × 40FT @ USD {line['usd']:.2f}")
        return {
            "tariff_code": "CONTAINER_MIXED" if count_20 and count_40 else (
                "CONTAINER_40FT" if count_40 else "CONTAINER_20FT"
            ),
            "route": route,
            "transport": transport,
            "label": "Containerised cargo",
            "unit": "Container",
            "quantity": float(count_20 + count_40),
            "usd_rate": round(usd_total / max(count_20 + count_40, 1), 4),
            "usd_total": round(usd_total, 4),
            "detail": "; ".join(parts),
        }

    if transport == "AIR":
        if _contains_any(text, ("parcel", "courier", "courier")) and "PARCEL" in table:
            code = "PARCEL"
        elif _contains_any(text, ("gold", "diamond", "mineral", "precious")) and "PRECIOUS_MINERALS" in table:
            code = "PRECIOUS_MINERALS"
        elif _contains_any(text, LIVE_ANIMAL_KEYWORDS) and "LIVE_ANIMAL" in table:
            code = "LIVE_ANIMAL"
        else:
            code = "GENERAL_CARGO"
        line = table[code]
        return {
            "tariff_code": code,
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": 1.0,
            "usd_rate": line["usd"],
            "usd_total": line["usd"],
        }

    if _contains_any(text, HEAVY_MACHINERY_KEYWORDS) and "HEAVY_MACHINERY" in table:
        units = _count_units(message_info)
        line = table["HEAVY_MACHINERY"]
        return {
            "tariff_code": "HEAVY_MACHINERY",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": float(units),
            "usd_rate": line["usd"],
            "usd_total": round(units * line["usd"], 4),
            "detail": f"{units} × Unit @ USD {line['usd']:.2f}",
        }

    if _contains_any(text, MOTOR_VEHICLE_KEYWORDS) and "MOTOR_VEHICLE" in table:
        units = _count_units(message_info)
        line = table["MOTOR_VEHICLE"]
        return {
            "tariff_code": "MOTOR_VEHICLE",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": float(units),
            "usd_rate": line["usd"],
            "usd_total": round(units * line["usd"], 4),
            "detail": f"{units} × Unit @ USD {line['usd']:.2f}",
        }

    if _contains_any(text, LIVE_ANIMAL_KEYWORDS) and "LIVE_ANIMAL" in table:
        line = table["LIVE_ANIMAL"]
        return {
            "tariff_code": "LIVE_ANIMAL",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": 1.0,
            "usd_rate": line["usd"],
            "usd_total": line["usd"],
        }

    mt = _metric_tonnes(message_info)
    is_liquid = _contains_any(text, LIQUID_BULK_KEYWORDS)
    is_dry_bulk = _contains_any(text, DRY_BULK_KEYWORDS)
    # Infer bulk-by-weight only for substantial tonnage; small LCL shipments stay on BL rate.
    bulk_by_weight = (
        mt >= 10
        and transport == "SEA"
        and ("DRY_BULK" in table or "BULK_LIQUID" in table)
    )

    if (is_liquid or (bulk_by_weight and not is_dry_bulk and _contains_any(text, ("oil", "liquid")))) and "BULK_LIQUID" in table:
        line = table["BULK_LIQUID"]
        qty = max(mt, 0.001)
        return {
            "tariff_code": "BULK_LIQUID",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": qty,
            "usd_rate": line["usd"],
            "usd_total": round(qty * line["usd"], 4),
            "detail": f"{qty:,.3f} MT × USD {line['usd']:.2f}/MT",
        }

    if (is_dry_bulk or bulk_by_weight) and "DRY_BULK" in table:
        line = table["DRY_BULK"]
        qty = max(mt, 0.001)
        return {
            "tariff_code": "DRY_BULK",
            "route": route,
            "transport": transport,
            "label": line["label"],
            "unit": line["unit"],
            "quantity": qty,
            "usd_rate": line["usd"],
            "usd_total": round(qty * line["usd"], 4),
            "detail": f"{qty:,.3f} MT × USD {line['usd']:.2f}/MT",
        }

    line = table.get("LCL") or table.get("GENERAL_CARGO") or next(iter(table.values()))
    return {
        "tariff_code": "LCL",
        "route": route,
        "transport": transport,
        "label": line["label"],
        "unit": line["unit"],
        "quantity": 1.0,
        "usd_rate": line["usd"],
        "usd_total": line["usd"],
    }


def classify_cargo_category(message_info: Dict[str, Any]) -> str:
    """Human-readable category label for invoices and analytics."""
    tariff = resolve_tariff(message_info)
    route = tariff["route"]
    transport = tariff["transport"]
    code = tariff["tariff_code"]
    unit = tariff["unit"]
    qty = tariff["quantity"]
    if unit == "MT":
        return f"{route}_{transport}_{code}_{qty:.3f}MT"
    if unit == "Container":
        return f"{route}_{transport}_{code}_x{int(qty)}"
    return f"{route}_{transport}_{code}"


def calculate_fees(
    message_info: Dict[str, Any],
    declarant_tin: str,
) -> Dict[str, Any]:
    """
    GN 83 minimum agency fee (USD schedule × FX) then:
      Full: minimum + 10% + 18% VAT on (minimum + 10%)
      Exempt / in-house: 10% + 18% VAT on 10% only
    """
    tariff = resolve_tariff(message_info)
    usd_total = float(tariff["usd_total"])
    minimum = round(usd_total * GN83_USD_TZS_RATE, 2)
    category = classify_cargo_category(message_info)
    exempted = is_exempted_payload(message_info)
    inhouse = is_inhouse_clearer(declarant_tin)

    if exempted or inhouse:
        service_fee = round(minimum * SERVICE_FEE_RATE, 2)
        vat_amount = round(service_fee * VAT_RATE, 2)
        total_due = round(service_fee + vat_amount, 2)
        fee_mode = "SERVICE"
        reason = "EXEMPTED" if exempted else "INHOUSE"
    else:
        service_fee = round(minimum * SERVICE_FEE_RATE, 2)
        taxable = round(minimum + service_fee, 2)
        vat_amount = round(taxable * VAT_RATE, 2)
        total_due = round(minimum + service_fee + vat_amount, 2)
        fee_mode = "FULL"
        reason = "STANDARD"

    return {
        "cargo_category": category,
        "gn83_tariff_code": tariff["tariff_code"],
        "gn83_tariff_label": tariff["label"],
        "gn83_route": tariff["route"],
        "gn83_transport": tariff["transport"],
        "gn83_unit": tariff["unit"],
        "gn83_quantity": tariff["quantity"],
        "gn83_usd_rate": tariff["usd_rate"],
        "gn83_usd_total": usd_total,
        "gn83_usd_tzs_rate": GN83_USD_TZS_RATE,
        "gn83_detail": tariff.get("detail") or (
            f"{tariff['quantity']:,.3f} {tariff['unit']} × USD {tariff['usd_rate']:.2f}/MT"
            if tariff["unit"] == "MT"
            else f"{tariff['quantity']:,.0f} {tariff['unit']} × USD {tariff['usd_rate']:.2f}"
        ),
        "standard_minimum": minimum,
        "service_fee": service_fee,
        "vat_amount": vat_amount,
        "total_due": total_due,
        "fee_mode": fee_mode,
        "fee_reason": reason,
        "vat_rate": VAT_RATE,
        "service_fee_rate": SERVICE_FEE_RATE,
    }


def fee_breakdown_lines(calc: Dict[str, Any]) -> Tuple[str, ...]:
    schedule_line = (
        f"GN 83 {calc['gn83_tariff_label']} ({calc['gn83_route']} / {calc['gn83_transport']}): "
        f"{calc['gn83_detail']} = USD {calc['gn83_usd_total']:,.2f} "
        f"× {calc['gn83_usd_tzs_rate']:,.2f} = TZS {calc['standard_minimum']:,.2f}"
    )
    if calc["fee_mode"] == "SERVICE":
        return (
            schedule_line,
            f"Exemption applied ({calc['fee_reason']}): service fee only",
            f"Service fee (10%): TZS {calc['service_fee']:,.2f}",
            f"VAT 18% on service fee: TZS {calc['vat_amount']:,.2f}",
            f"Total due: TZS {calc['total_due']:,.2f}",
        )
    taxable = calc["standard_minimum"] + calc["service_fee"]
    return (
        schedule_line,
        f"Service / admin fee (10%): TZS {calc['service_fee']:,.2f}",
        f"Taxable base: TZS {taxable:,.2f}",
        f"VAT 18%: TZS {calc['vat_amount']:,.2f}",
        f"Full settlement: TZS {calc['total_due']:,.2f}",
    )
