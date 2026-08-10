"""TANCIS ↔ TCAMS interface catalogue (GN 83 integration)."""

from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

# Official interface IDs (IF-E-CLR-0xx) and legacy aliases still accepted on webhooks.
CONSIGNMENT_INFORMATION = "IF-E-CLR-018"
AGENT_FEE_INVOICE = "IF-E-CLR-019"
AGENT_FEE_PAYMENT = "IF-E-CLR-020"
AGENT_FEE_INVOICE_CANCELLATION = "IF-E-CLR-021"
CONSIGNMENT_NOTES_STATUS = "IF-E-CLR-022"

LEGACY_CONSIGNMENT = "IF-I-CLR-080"
LEGACY_INVOICE = "IF-I-CLR-081"
LEGACY_PAYMENT = "IF-I-CLR-068"
LEGACY_INVOICE_CANCEL = "IF-I-CLR-082"
LEGACY_NOTES_STATUS = "IF-I-CLR-067"

CONSIGNMENT_INTERFACE_IDS: FrozenSet[str] = frozenset(
    {CONSIGNMENT_INFORMATION, LEGACY_CONSIGNMENT}
)
INVOICE_INTERFACE_IDS: FrozenSet[str] = frozenset({AGENT_FEE_INVOICE, LEGACY_INVOICE})
NOTES_STATUS_INTERFACE_IDS: FrozenSet[str] = frozenset(
    {CONSIGNMENT_NOTES_STATUS, LEGACY_NOTES_STATUS}
)

# CL005 / CL006 on notes-status payload → trigger invoice cancellation (IF-E-CLR-021).
NOTES_STATUS_CANCEL_CODES: FrozenSet[str] = frozenset({"CL005", "CL006"})

INTERFACE_CATALOG: Tuple[Dict[str, str], ...] = (
    {
        "interface_id": CONSIGNMENT_INFORMATION,
        "name": "Consignment Information",
        "transmitter": "TANCIS",
        "receiver": "TCAMS",
        "sender_id": "SNDR-IFECLR018",
        "receiver_id": "RCVR-IFCLR018",
    },
    {
        "interface_id": AGENT_FEE_INVOICE,
        "name": "Agent fee invoice information",
        "transmitter": "TCAMS",
        "receiver": "TANCIS",
        "sender_id": "SNDR-IFECLR019",
        "receiver_id": "RCVR-IFCLR019",
    },
    {
        "interface_id": AGENT_FEE_PAYMENT,
        "name": "Agent fee payment information",
        "transmitter": "TCAMS",
        "receiver": "TANCIS",
        "sender_id": "SNDR-IFECLR020",
        "receiver_id": "RCVR-IFCLR020",
    },
    {
        "interface_id": AGENT_FEE_INVOICE_CANCELLATION,
        "name": "Agent fee invoice cancellation information",
        "transmitter": "TCAMS",
        "receiver": "TANCIS",
        "sender_id": "SNDR-IFECLR021",
        "receiver_id": "RCVR-IFCLR021",
    },
    {
        "interface_id": CONSIGNMENT_NOTES_STATUS,
        "name": "Consignment notes status information",
        "transmitter": "TANCIS",
        "receiver": "TCAMS",
        "sender_id": "SNDR-IFECLR022",
        "receiver_id": "RCVR-IFCLR022",
        "note": "Formerly Consignment cancellation (IF-I-CLR-067). Payload structure unchanged.",
    },
)


def interface_label(interface_id: str) -> str:
    for row in INTERFACE_CATALOG:
        if row["interface_id"] == interface_id:
            return row["name"]
    legacy = {
        LEGACY_CONSIGNMENT: "Consignment Information",
        LEGACY_INVOICE: "Agent fee invoice information",
        LEGACY_PAYMENT: "Agent fee payment information",
        LEGACY_INVOICE_CANCEL: "Agent fee invoice cancellation information",
        LEGACY_NOTES_STATUS: "Consignment notes status information",
    }
    return legacy.get(interface_id, interface_id)
