"""Process IF-E-CLR-022 Consignment notes status information (legacy IF-I-CLR-067)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from services import database as db
from services.interfaces import (
    CONSIGNMENT_NOTES_STATUS,
    LEGACY_NOTES_STATUS,
    NOTES_STATUS_CANCEL_CODES,
    NOTES_STATUS_INTERFACE_IDS,
)


def _ack(code: str, message: str, reference: str, txn: str) -> Dict[str, Any]:
    return {
        "header": {
            "interface_id": CONSIGNMENT_NOTES_STATUS,
            "receive_date_and_time": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"),
            "result_status_code": code,
            "result_message": message,
            "reference_number": reference or "",
            "transaction_id": txn or "",
        }
    }


def process_notes_status(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Accept Consignment notes status information from TANCIS.
    Same structure as legacy consignment cancellation (067).
    CL005 (Cancellation) and CL006 (Dismissal) are the only statuses acted on.
    """
    header = payload.get("header") or {}
    message_info = payload.get("message_info") or {}

    if not header:
        return _ack("E101", "Missing HTTP Header", "", ""), None

    interface_id = str(header.get("interface_id") or "").strip()
    if interface_id not in NOTES_STATUS_INTERFACE_IDS:
        return (
            _ack(
                "E201",
                "Interface id not found",
                str(header.get("reference_number") or ""),
                str(header.get("transaction_id") or ""),
            ),
            None,
        )

    tansad_no = str(message_info.get("tansad_no") or "").strip()
    status = str(message_info.get("status") or "").strip().upper()
    reference = str(header.get("reference_number") or "")
    txn = str(header.get("transaction_id") or "")

    if not tansad_no or not status:
        return _ack("E102", "Invalid Request Parameter", reference, txn), None

    invoice = db.get_latest_invoice_for_tansad(tansad_no)
    action = "RECORDED"
    if status in NOTES_STATUS_CANCEL_CODES and invoice:
        action = "CANCEL_TRIGGERED"
        user_id = invoice.get("user_id")
        if user_id:
            db.add_notification(
                user_id,
                "NOTES_STATUS",
                "Consignment notes status received",
                (
                    f"TANSAD {tansad_no}: status {status} on IF-E-CLR-022 "
                    f"(Consignment notes status information). "
                    f"Invoice {invoice['invoice_no']} marked for cancellation (IF-E-CLR-021)."
                ),
                related_invoice_no=invoice["invoice_no"],
            )

    return (
        _ack("S001", "Successful data transmission", reference, txn),
        {
            "tansad_no": tansad_no,
            "status": status,
            "action": action,
            "invoice_no": (invoice or {}).get("invoice_no"),
        },
    )
