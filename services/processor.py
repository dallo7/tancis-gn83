"""Process IF-I-CLR-080 consignments and emit IF-I-CLR-081 invoices."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from services import database as db
from services.config import BASE_DIR, BASE_URL
from services.gn83 import calculate_fees
from services.invoice_engine import (
    generate_invoice_no,
    generate_suc_number,
    write_invoice_artifacts,
)


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S") + "000"


def build_081_payload(
    *,
    tansad_no: str,
    invoice_no: str,
    invoice_type: str,
    invoice_path: str,
    reference_number: str,
    absolute_invoice_url: str,
) -> Dict[str, Any]:
    return {
        "header": {
            "interface_id": "IF-I-CLR-081",
            "send_date_and_time": _timestamp(),
            "sender_id": "TCAMS_ED_SNDR",
            "receiver_id": "TRA_ED_RCVR",
            "reference_number": reference_number or "",
            "transaction_id": str(uuid.uuid4()),
        },
        "message_info": {
            "tansad_no": tansad_no,
            "invoice_no": invoice_no,
            "invoice_type": invoice_type,
            "invoice_path": absolute_invoice_url or invoice_path,
        },
    }


def ack(interface_id: str, code: str, message: str, reference: str, txn: str) -> Dict[str, Any]:
    return {
        "header": {
            "interface_id": interface_id,
            "receive_date_and_time": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"),
            "result_status_code": code,
            "result_message": message,
            "reference_number": reference or "",
            "transaction_id": txn or str(uuid.uuid4()),
        }
    }


def process_consignment(
    payload: Dict[str, Any],
    *,
    public_base_url: str = "",
    invoice_type: str = "G",
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Accept IF-I-CLR-080, generate invoice, store, notify CFA, and return 080 ack + invoice record.
    Unknown declarant TINs are still processed and filed with lineage for operations.
    """
    header = payload.get("header") or {}
    message_info = payload.get("message_info") or {}

    if not header:
        return ack("IF-I-CLR-080", "E101", "Missing HTTP Header", "", ""), None
    if header.get("interface_id") != "IF-I-CLR-080":
        return (
            ack(
                header.get("interface_id") or "IF-I-CLR-080",
                "E201",
                "Interface id not found",
                header.get("reference_number", ""),
                header.get("transaction_id", ""),
            ),
            None,
        )

    tansad_no = str(message_info.get("tansad_no") or "").strip()
    declarant = message_info.get("declarant") or {}
    declarant_tin = str(declarant.get("tin") or "").strip()
    reference = str(header.get("reference_number") or "")
    txn = str(header.get("transaction_id") or str(uuid.uuid4()))

    if not tansad_no or not declarant_tin:
        return (
            ack("IF-I-CLR-080", "E102", "Invalid Request Parameter", reference, txn),
            None,
        )

    user = db.get_user_by_tin(declarant_tin)
    lineage_note = ""
    status = "MATCHED"
    if not user:
        status = "UNMATCHED_DECLARANT"
        lineage_note = (
            "Declarant TIN not among seeded CFA profiles. Filed for TCAMS operations follow-up."
        )

    consignment_id = db.insert_consignment(
        transaction_id=txn,
        reference_number=reference,
        tansad_no=tansad_no,
        declarant_tin=declarant_tin,
        user_id=user["id"] if user else None,
        payload=payload,
        status=status,
        lineage_note=lineage_note,
    )

    if user:
        db.add_notification(
            user["id"],
            "CONSIGNMENT",
            "New consignment received from TANCIS",
            f"TANSAD {tansad_no} received via IF-I-CLR-080. Invoice generation started.",
        )

    calc = calculate_fees(message_info, declarant_tin)
    invoice_no = generate_invoice_no()
    suc_number = generate_suc_number()
    base = (public_base_url or BASE_URL or "").rstrip("/")

    artifacts = write_invoice_artifacts(
        invoice_meta={
            "invoice_no": invoice_no,
            "suc_number": suc_number,
            "tansad_no": tansad_no,
            "declarant_tin": declarant_tin,
            "user_id": user["id"] if user else None,
            "consignment_id": consignment_id,
            "invoice_type": invoice_type,
        },
        user=user,
        message_info=message_info,
        calc=calc,
        logo_path=BASE_DIR / "assets" / "tcams-logo.png",
        base_url=base or "https://example.com",
    )

    absolute_invoice_url = (
        f"{base}{artifacts['invoice_path']}" if base else artifacts["invoice_path"]
    )
    payload_081 = build_081_payload(
        tansad_no=tansad_no,
        invoice_no=invoice_no,
        invoice_type=invoice_type,
        invoice_path=artifacts["invoice_path"],
        reference_number=reference,
        absolute_invoice_url=absolute_invoice_url,
    )

    # Simulated successful push to TANCIS (IF-I-CLR-081 -> S001)
    tancis_result = {
        "header": {
            "interface_id": "IF-I-CLR-081",
            "receive_date_and_time": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S"),
            "result_status_code": "S001",
            "result_message": "Successful data transmission",
            "reference_number": reference,
            "transaction_id": payload_081["header"]["transaction_id"],
        }
    }

    invoice_id = db.insert_invoice(
        {
            **artifacts,
            "pushed_to_tancis": True,
            "tancis_result_code": "S001",
            "tancis_payload": {
                "request": payload_081,
                "response": tancis_result,
            },
        }
    )

    invoice = db.get_invoice_by_no(invoice_no)
    if user:
        db.add_notification(
            user["id"],
            "INVOICE",
            "Invoice generated and pushed to TANCIS",
            (
                f"Invoice {invoice_no} ({artifacts['fee_mode']}) for TANSAD {tansad_no} "
                f"total {artifacts['currency']} {artifacts['total_due']:,.2f} sent via IF-I-CLR-081."
            ),
            related_invoice_no=invoice_no,
        )

    response = ack(
        "IF-I-CLR-080",
        "S001",
        "Successful data transmission",
        reference,
        txn,
    )
    # Clean ack returned to TANCIS (interface contract) — nested debug kept separately.
    ack_080 = {
        "header": response["header"],
    }
    exchange = {
        "direction_flow": [
            "1) TANCIS -> TCAMS | IF-I-CLR-080 consignment transmission",
            "2) TCAMS -> TANCIS | IF-I-CLR-080 acknowledgement",
            "3) TCAMS -> TANCIS | IF-I-CLR-081 invoice transmission",
            "4) TANCIS -> TCAMS | IF-I-CLR-081 acknowledgement",
        ],
        "if_i_clr_080_transmission": payload,
        "if_i_clr_080_reception": ack_080,
        "if_i_clr_081_transmission": payload_081,
        "if_i_clr_081_reception": tancis_result,
        "meta": {
            "invoice_no": invoice_no,
            "invoice_path": absolute_invoice_url,
            "payment_link": artifacts["payment_link"],
            "fee_mode": artifacts["fee_mode"],
            "total_due": artifacts["total_due"],
            "currency": artifacts["currency"],
            "lineage_note": lineage_note,
        },
    }
    exchange_id = db.insert_message_exchange(
        user_id=user["id"] if user else None,
        declarant_tin=declarant_tin,
        tansad_no=tansad_no,
        invoice_no=invoice_no,
        summary=(
            f"080 accepted S001 · 081 invoice {invoice_no} pushed S001 · "
            f"{artifacts['currency']} {artifacts['total_due']:,.2f}"
        ),
        exchange=exchange,
    )

    response["tcams"] = {
        "consignment_id": consignment_id,
        "invoice_id": invoice_id,
        "invoice_no": invoice_no,
        "invoice_path": absolute_invoice_url,
        "payment_link": artifacts["payment_link"],
        "fee_mode": artifacts["fee_mode"],
        "total_due": artifacts["total_due"],
        "lineage_note": lineage_note,
        "if_i_clr_081": payload_081,
        "if_i_clr_081_result": tancis_result,
        "exchange_id": exchange_id,
        "exchange": exchange,
    }
    return response, invoice