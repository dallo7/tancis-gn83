"""CapitalPay checkout session creation for TCAMS invoices."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from typing import Any, Dict, Optional

import requests

from services import database as db
from services.config import (
    CAPITALPAY_API_BASE,
    CAPITALPAY_API_CLIENT_ID,
    CAPITALPAY_API_KEY,
    CAPITALPAY_API_SECRET,
    CAPITALPAY_CALLBACK_URL,
    CAPITALPAY_CHECKOUT_URL,
    CAPITALPAY_NOTIFICATION_URL,
    CAPITALPAY_PRIVATE_HOSTS,
    CAPITALPAY_PUBLIC_HOST,
    CAPITALPAY_SERVICE_ID,
    CURRENCY,
)

logger = logging.getLogger(__name__)


class CapitalPayError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(CAPITALPAY_API_KEY and CAPITALPAY_API_SECRET)


def generate_token() -> str:
    response = requests.post(
        f"{CAPITALPAY_API_BASE}/oauth/generate/token",
        json={"key": CAPITALPAY_API_KEY, "secret": CAPITALPAY_API_SECRET},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise CapitalPayError(f"No token in response: {response.text[:300]}")
    return token


def compute_secure_hash(
    *,
    amount: str,
    client_id_number: str,
    currency: str,
    bill_ref_number: str,
    bill_desc: str,
    client_name: str,
) -> str:
    data_string = (
        CAPITALPAY_API_CLIENT_ID
        + amount
        + CAPITALPAY_SERVICE_ID
        + client_id_number
        + currency
        + bill_ref_number
        + bill_desc
        + client_name
        + CAPITALPAY_API_SECRET
    )
    digest = hmac.new(
        CAPITALPAY_API_KEY.encode(), data_string.encode(), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode()


def extract_invoice_number(data: dict) -> Optional[str]:
    invoice = data.get("invoice")
    if isinstance(invoice, dict) and invoice.get("invoice_number"):
        return str(invoice["invoice_number"])
    for key in ("invoice_number", "invoice_ref"):
        if data.get(key):
            return str(data[key])
    nested = data.get("data")
    if isinstance(nested, dict) and nested.get("invoice_number"):
        return str(nested["invoice_number"])
    return None


def build_invoice_payload(
    *,
    name: str,
    msisdn: str,
    email: str,
    id_number: str,
    amount: str,
    currency: str,
    bill_ref: str,
    desc: str,
    callback_url: str,
    notif_url: str,
    vat_amount: float = 0,
) -> dict:
    return {
        "api_client_id": CAPITALPAY_API_CLIENT_ID,
        "account_id": CAPITALPAY_SERVICE_ID,
        "amount_expected": str(amount),
        "amount_settled_offline": "0",
        "callback_url": callback_url,
        "client_invoice_ref": bill_ref,
        "currency": currency,
        "desc": desc,
        "email": email,
        "format": "json",
        "id_number": id_number,
        "items": [
            {
                "account_id": CAPITALPAY_SERVICE_ID,
                "desc": desc,
                "item_ref": bill_ref,
                "price": str(amount),
                "quantity": 1,
                "require_settlement": "true",
                "settlements": [
                    {
                        "account_number": 4567898765434567,
                        "desc": "ECO BANK - VAT",
                        "value": max(int(round(vat_amount)), 0),
                    }
                ],
            }
        ],
        "msisdn": msisdn,
        "name": name,
        "notification_url": notif_url,
        "payment_gateway_id": 1,
        "send_stk": False,
    }


def create_invoice(token: str, payload: dict) -> dict:
    response = requests.post(
        f"{CAPITALPAY_API_BASE}/invoice/create",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise CapitalPayError(
            f"Invoice API returned non-JSON: {response.text[:300]}"
        ) from exc

    if not response.ok:
        message = data.get("message") or data.get("error") or str(data)
        raise CapitalPayError(f"Invoice API error ({response.status_code}): {message}")
    return data


def build_checkout_params(
    *,
    name: str,
    msisdn: str,
    email: str,
    id_number: str,
    amount: str,
    currency: str,
    bill_ref: str,
    desc: str,
    callback_url: str,
    notif_url: str,
) -> Dict[str, str]:
    amount_str = f"{float(amount):.2f}"
    params = {
        "apiClientID": CAPITALPAY_API_CLIENT_ID,
        "secureHash": compute_secure_hash(
            amount=amount_str,
            client_id_number=id_number,
            currency=currency,
            bill_ref_number=bill_ref,
            bill_desc=desc,
            client_name=name,
        ),
        "billDesc": desc,
        "billRefNumber": bill_ref,
        "currency": currency,
        "serviceID": CAPITALPAY_SERVICE_ID,
        "clientMSISDN": msisdn,
        "clientName": name,
        "clientIDNumber": id_number,
        "clientEmail": email,
        "notificationURL": notif_url,
        "amountExpected": amount_str,
    }
    if callback_url:
        params["callBackURLOnSuccess"] = callback_url
    return params


def normalize_checkout_html(html: str) -> str:
    for private_host in CAPITALPAY_PRIVATE_HOSTS:
        html = html.replace(private_host, CAPITALPAY_PUBLIC_HOST)
    return html


def fetch_checkout_page(params: Dict[str, str]) -> str:
    response = requests.post(CAPITALPAY_CHECKOUT_URL, data=params, timeout=30)
    if not response.ok:
        raise CapitalPayError(
            f"Checkout error ({response.status_code}): {response.text[:300]}"
        )
    return normalize_checkout_html(response.text)


def build_checkout_url(base_url: str, checkout_id: str) -> str:
    root = (base_url or "https://example.com").rstrip("/")
    return f"{root}/go/{checkout_id}"


def create_checkout_session(
    *,
    invoice_no: str,
    suc_number: str,
    tansad_no: str,
    amount: float,
    vat_amount: float,
    base_url: str,
    user: Optional[Dict[str, Any]] = None,
    declarant_tin: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Create CapitalPay invoice + hosted checkout session.
    Returns checkout_url for QR / invoice printing, or None if not configured/failed.
    """
    if not is_configured():
        logger.warning("CapitalPay credentials not configured; skipping checkout session")
        return None

    name = (user or {}).get("company_name") or "TCAMS Importer"
    msisdn = (user or {}).get("phone") or "+255700000000"
    email = (user or {}).get("email") or "payments@tcams.tz"
    id_number = declarant_tin or (user or {}).get("declarant_tin") or "000000000"
    amount_str = f"{float(amount):.2f}"
    bill_ref = invoice_no
    desc = f"TCAMS SUC {suc_number} · TANSAD {tansad_no}"
    callback_url = CAPITALPAY_CALLBACK_URL or f"{base_url.rstrip('/')}/payment/success"
    notif_url = CAPITALPAY_NOTIFICATION_URL or f"{base_url.rstrip('/')}/payment/notify"

    try:
        token = generate_token()
        api_result = create_invoice(
            token,
            build_invoice_payload(
                name=name,
                msisdn=msisdn,
                email=email,
                id_number=id_number,
                amount=amount_str,
                currency=CURRENCY,
                bill_ref=bill_ref,
                desc=desc,
                callback_url=callback_url,
                notif_url=notif_url,
                vat_amount=vat_amount,
            ),
        )
        checkout_params = build_checkout_params(
            name=name,
            msisdn=msisdn,
            email=email,
            id_number=id_number,
            amount=amount_str,
            currency=CURRENCY,
            bill_ref=bill_ref,
            desc=desc,
            callback_url=callback_url,
            notif_url=notif_url,
        )
    except (CapitalPayError, requests.RequestException) as exc:
        logger.exception("CapitalPay checkout session failed for %s: %s", invoice_no, exc)
        return None

    checkout_id = uuid.uuid4().hex
    capitalpay_ref = extract_invoice_number(api_result) or bill_ref
    db.save_checkout_session(
        checkout_id=checkout_id,
        invoice_no=invoice_no,
        params=checkout_params,
        capitalpay_invoice_ref=capitalpay_ref,
        api_response=api_result,
    )
    checkout_url = build_checkout_url(base_url, checkout_id)
    return {
        "checkout_id": checkout_id,
        "checkout_url": checkout_url,
        "capitalpay_invoice_ref": capitalpay_ref,
        "api_response": api_result,
    }
