"""Rotating IF-E-CLR-018 sample payloads for the TANCIS simulator."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List

ScenarioBuilder = Callable[[Dict[str, Any], str], Dict[str, Any]]


from services.interfaces import CONSIGNMENT_INFORMATION


def _base_header(user: dict, tansad: str) -> Dict[str, Any]:
    return {
        "interface_id": CONSIGNMENT_INFORMATION,
        "send_date_and_time": datetime.utcnow().strftime("%Y%m%d%H%M%S") + "000",
        "sender_id": "SNDR-IFECLR018",
        "receiver_id": "RCVR-IFCLR018",
        "reference_number": f"REF-{user['username'].upper()}-{datetime.utcnow().strftime('%H%M%S')}",
        "transaction_id": f"TXN-{tansad}-001",
    }


def _base_bl() -> Dict[str, str]:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return {
        "bl_number": f"BL{stamp}",
        "master_bl_number": f"MBL{stamp}",
    }


def _container(number_suffix: str, size: str) -> Dict[str, str]:
    return {"container_number": f"MSKU{number_suffix}", "container_size": size}


def _scenario_import_20ft(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 18500.75,
            "gross_weight_unit": "KG",
            "volume": 28.5,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "General merchandise in 20-foot container",
                "containers": [_container("1234567", "20FT")],
            }
        ],
    }


def _scenario_import_dual_40ft(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 42000,
            "gross_weight_unit": "KG",
            "volume": 68.0,
            "volume_unit": "CBM",
            "no_of_package": 2,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Electronics and household goods",
                "containers": [
                    _container("7654321", "40FT"),
                    _container("7654322", "40FT"),
                ],
            }
        ],
    }


def _scenario_import_dry_bulk(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 500000,
            "gross_weight_unit": "KG",
            "volume": 620.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Dry bulk wheat grain in bulk carrier",
            }
        ],
    }


def _scenario_import_bulk_liquid(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 250,
            "gross_weight_unit": "MT",
            "volume": 280.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Bulk liquid palm oil",
            }
        ],
    }


def _scenario_import_motor_vehicle(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 6200,
            "gross_weight_unit": "KG",
            "volume": 42.0,
            "volume_unit": "CBM",
            "no_of_package": 2,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Motor vehicle Toyota Hilux pickup",
                "quantity": 2,
            }
        ],
    }


def _scenario_import_heavy_machinery(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 48000,
            "gross_weight_unit": "KG",
            "volume": 55.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Heavy equipment excavator CAT 320",
                "quantity": 1,
            }
        ],
    }


def _scenario_import_live_animal(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 8500,
            "gross_weight_unit": "KG",
            "volume": 35.0,
            "volume_unit": "CBM",
            "no_of_package": 40,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Live animal cattle for breeding",
            }
        ],
    }


def _scenario_import_lcl(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 3200,
            "gross_weight_unit": "KG",
            "volume": 12.5,
            "volume_unit": "CBM",
            "no_of_package": 18,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Loose cargo spare parts and accessories",
            }
        ],
    }


def _scenario_transit_bulk(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "TRANSIT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 100,
            "gross_weight_unit": "MT",
            "volume": 45.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Dry bulk cement in transit",
            }
        ],
    }


def _scenario_export_20ft(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "EXPORT",
        "transport_mode": "SEA",
        "consignment": {
            "gross_weight": 14200,
            "gross_weight_unit": "KG",
            "volume": 26.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Export cashew nuts in bags",
                "containers": [_container("9988776", "20FT")],
            }
        ],
    }


def _scenario_import_road_20ft(user: dict, tin: str) -> Dict[str, Any]:
    return {
        "route_type": "IMPORT",
        "transport_mode": "ROAD",
        "consignment": {
            "gross_weight": 9800,
            "gross_weight_unit": "KG",
            "volume": 24.0,
            "volume_unit": "CBM",
            "no_of_package": 1,
            "package_unit": "NMB",
        },
        "cargo": [
            {
                "item_description": "Border import consumer goods",
                "containers": [_container("5544332", "20FT")],
            }
        ],
    }


SCENARIOS: List[Dict[str, Any]] = [
    {"key": "import_20ft", "label": "Import · 20FT container", "build": _scenario_import_20ft},
    {"key": "import_dual_40ft", "label": "Import · 2×40FT containers", "build": _scenario_import_dual_40ft},
    {"key": "import_dry_bulk", "label": "Import · dry bulk 500 MT", "build": _scenario_import_dry_bulk},
    {"key": "import_bulk_liquid", "label": "Import · bulk liquid 250 MT", "build": _scenario_import_bulk_liquid},
    {"key": "import_motor_vehicle", "label": "Import · motor vehicles ×2", "build": _scenario_import_motor_vehicle},
    {"key": "import_heavy_machinery", "label": "Import · heavy machinery", "build": _scenario_import_heavy_machinery},
    {"key": "import_live_animal", "label": "Import · live animals", "build": _scenario_import_live_animal},
    {"key": "import_lcl", "label": "Import · loose cargo / LCL", "build": _scenario_import_lcl},
    {"key": "transit_bulk", "label": "Transit · dry bulk 100 MT", "build": _scenario_transit_bulk},
    {"key": "export_20ft", "label": "Export · 20FT container", "build": _scenario_export_20ft},
    {"key": "import_road_20ft", "label": "Import · road 20FT", "build": _scenario_import_road_20ft},
]


def scenario_count() -> int:
    return len(SCENARIOS)


def scenario_label(index: int) -> str:
    return SCENARIOS[index % len(SCENARIOS)]["label"]


def sample_080_payload(
    user: dict,
    exempted: bool = False,
    scenario_index: int = 0,
) -> dict:
    tin = user["declarant_tin"]
    tansad = f"TZDL{datetime.utcnow().strftime('%y')}{tin[-4:]}{uuid.uuid4().hex[:4].upper()}"
    scenario = SCENARIOS[scenario_index % len(SCENARIOS)]
    message_info = {
        "tansad_no": tansad,
        "bill_of_lading": _base_bl(),
        "declarant": {"tin": tin},
        **scenario["build"](user, tin),
    }
    if exempted:
        message_info["status"] = "exempted"

    payload = {
        "header": _base_header(user, tansad),
        "message_info": message_info,
        "_sample_meta": {
            "scenario_key": scenario["key"],
            "scenario_label": scenario["label"],
            "scenario_index": scenario_index % len(SCENARIOS),
        },
    }
    return payload


def payload_for_processing(payload: dict) -> dict:
    """Strip simulator-only fields before posting to TCAMS."""
    clean = dict(payload)
    clean.pop("_sample_meta", None)
    return clean
