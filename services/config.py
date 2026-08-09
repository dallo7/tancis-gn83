import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATABASE_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "tcams.db"))
INVOICE_DIR = Path(os.environ.get("INVOICE_DIR", BASE_DIR / "static" / "invoices"))
INVOICE_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "tcams-dev-secret-change-me")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

# Placeholder list — replace with real in-house clearer declarant TINs when provided.
INHOUSE_CLEARER_TINS = set(
    tin.strip()
    for tin in os.environ.get("INHOUSE_CLEARER_TINS", "").split(",")
    if tin.strip()
)

# GN 83 Order 6(1)(a): exempt consignments are flagged by TANCIS on the 080 payload
# via message_info.status — TCAMS does not infer exemption from cargo description.
EXEMPT_STATUSES = frozenset(
    s.strip().lower()
    for s in os.environ.get(
        "GN83_EXEMPT_STATUSES",
        "exempt,exempted,exemption",
    ).split(",")
    if s.strip()
)

CURRENCY = "TZS"
SERVICE_FEE_RATE = 0.10
VAT_RATE = 0.18
INVOICE_DUE_DAYS = 7

# BoT / operational USD→TZS rate for GN 83 schedule amounts (quoted in USD equivalents).
GN83_USD_TZS_RATE = float(os.environ.get("GN83_USD_TZS_RATE", "2500"))

# Tanzania Shipping Agencies (Fees for Clearing and Forwarding Services) Order, 2026 — GN No. 83
# Schedule minimum agency fees (USD equivalents) by route, transport mode, and tariff line.
GN83_SCHEDULE = {
    "IMPORT": {
        "SEA": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 150.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 200.0, "label": "40-foot shipping container"},
            "DRY_BULK": {"unit": "MT", "usd": 0.6, "label": "Dry bulk cargo"},
            "BULK_LIQUID": {"unit": "MT", "usd": 0.6, "label": "Bulk liquid"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 90.0, "label": "Live animal"},
            "LCL": {"unit": "BL", "usd": 90.0, "label": "Loose cargo / LCL"},
            "POST_ENTRY": {"unit": "BL", "usd": 60.0, "label": "Post entry & ex-bond"},
            "COASTWISE": {"unit": "Transire", "usd": 90.0, "label": "Carriage coastwise"},
        },
        "ROAD": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 130.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 190.0, "label": "40-foot shipping container"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 60.0, "label": "Live animal"},
            "LCL": {"unit": "Vehicle", "usd": 60.0, "label": "Loose cargo / LCL"},
        },
        "AIR": {
            "PARCEL": {"unit": "AWB", "usd": 60.0, "label": "Parcel / couriers"},
            "GENERAL_CARGO": {"unit": "AWB", "usd": 90.0, "label": "General cargo"},
            "LIVE_ANIMAL": {"unit": "AWB", "usd": 60.0, "label": "Live animal"},
        },
    },
    "EXPORT": {
        "SEA": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 150.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 200.0, "label": "40-foot shipping container"},
            "DRY_BULK": {"unit": "MT", "usd": 0.6, "label": "Dry bulk cargo"},
            "BULK_LIQUID": {"unit": "MT", "usd": 0.6, "label": "Bulk liquid"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 90.0, "label": "Live animal"},
            "LCL": {"unit": "BL", "usd": 90.0, "label": "Loose cargo / LCL"},
            "COASTWISE": {"unit": "Transire", "usd": 90.0, "label": "Carriage coastwise"},
        },
        "ROAD": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 130.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 190.0, "label": "40-foot shipping container"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 60.0, "label": "Live animal"},
            "LCL": {"unit": "Vehicle", "usd": 60.0, "label": "Loose cargo / LCL"},
        },
        "AIR": {
            "PARCEL": {"unit": "AWB", "usd": 60.0, "label": "Parcel / couriers"},
            "GENERAL_CARGO": {"unit": "AWB", "usd": 90.0, "label": "General cargo"},
            "PRECIOUS_MINERALS": {"unit": "AWB", "usd": 130.0, "label": "Precious metal / minerals"},
            "LIVE_ANIMAL": {"unit": "AWB", "usd": 60.0, "label": "Live animal"},
        },
    },
    "TRANSIT": {
        "SEA": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 200.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 250.0, "label": "40-foot shipping container"},
            "DRY_BULK": {"unit": "MT", "usd": 0.5, "label": "Dry bulk cargo"},
            "BULK_LIQUID": {"unit": "MT", "usd": 0.5, "label": "Bulk liquid"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 130.0, "label": "Live animal"},
            "LCL": {"unit": "BL", "usd": 130.0, "label": "Loose cargo / LCL"},
        },
        "ROAD": {
            "CONTAINER_20FT": {"unit": "Container", "usd": 210.0, "label": "20-foot shipping container"},
            "CONTAINER_40FT": {"unit": "Container", "usd": 250.0, "label": "40-foot shipping container"},
            "MOTOR_VEHICLE": {"unit": "Unit", "usd": 130.0, "label": "Motor vehicle"},
            "HEAVY_MACHINERY": {"unit": "Unit", "usd": 250.0, "label": "Heavy machines & equipment"},
            "LIVE_ANIMAL": {"unit": "BL", "usd": 90.0, "label": "Live animal"},
            "LCL": {"unit": "Vehicle", "usd": 90.0, "label": "Loose cargo / LCL"},
        },
        "AIR": {
            "GENERAL_CARGO": {"unit": "AWB", "usd": 130.0, "label": "General cargo"},
        },
    },
}

ACCEPTED_BANKS = [
    "Capital Pay Direct",
    "Mobile Money Selcom",
    "Equity Bank",
    "CRDB",
    "NBC",
    "Ecobank",
    "Absa Bank",
    "KCB",
]

# CapitalPay checkout (Service 99 / TT CAMS)
CAPITALPAY_API_BASE = os.environ.get(
    "CAPITALPAY_API_BASE", "https://app.capitalpay.co.tz/api"
).rstrip("/")
CAPITALPAY_CHECKOUT_URL = os.environ.get(
    "CAPITALPAY_CHECKOUT_URL",
    "https://app.capitalpay.co.tz/PaymentAPI/invoice/checkout",
)
CAPITALPAY_PUBLIC_HOST = os.environ.get(
    "CAPITALPAY_PUBLIC_HOST", "https://app.capitalpay.co.tz"
).rstrip("/")
CAPITALPAY_API_KEY = os.environ.get("CAPITALPAY_API_KEY", "")
CAPITALPAY_API_SECRET = os.environ.get("CAPITALPAY_API_SECRET", "")
CAPITALPAY_API_CLIENT_ID = os.environ.get("CAPITALPAY_API_CLIENT_ID", "3")
CAPITALPAY_SERVICE_ID = os.environ.get("CAPITALPAY_SERVICE_ID", "134")
CAPITALPAY_CALLBACK_URL = os.environ.get(
    "CAPITALPAY_CALLBACK_URL", ""
)
CAPITALPAY_NOTIFICATION_URL = os.environ.get(
    "CAPITALPAY_NOTIFICATION_URL", ""
)
CAPITALPAY_PRIVATE_HOSTS = tuple(
    host.strip()
    for host in os.environ.get(
        "CAPITALPAY_PRIVATE_HOSTS",
        "https://192.168.92.110,http://192.168.92.110",
    ).split(",")
    if host.strip()
)
