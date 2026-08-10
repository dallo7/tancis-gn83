"""
TCAMS ↔ TANCIS GN 83 Invoice Studio
Dash + Dash Mantine application for Render deployment.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import jsonify, redirect, request, send_from_directory, session

from services import database as db
from services.capitalpay import CapitalPayError, fetch_checkout_page
from services.config import BASE_DIR, INVOICE_DIR, SECRET_KEY
from services.processor import process_consignment
from services.notes_status import process_notes_status
from services.interfaces import (
    AGENT_FEE_INVOICE,
    CONSIGNMENT_INFORMATION,
    CONSIGNMENT_NOTES_STATUS,
    INTERFACE_CATALOG,
)
from services.gn83 import calculate_fees, fee_breakdown_lines
from services.sample_payloads import (
    payload_for_processing,
    sample_080_payload,
    scenario_count,
    scenario_label,
)

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

# dash-mantine-components requires React 18 (useId). Dash 2.x defaults to React 16.
dash._dash_renderer._set_react_version("18.2.0")

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="TCAMS · TANCIS GN 83",
    update_title=None,
    assets_folder="assets",
)
app._favicon = "favicon.ico"
server = app.server
server.secret_key = SECRET_KEY

# Ensure Render / local always expose the Flask server object by name.
# gunicorn app:server

db.init_db()

# ---------------------------------------------------------------------------
# Flask API / static invoice routes
# ---------------------------------------------------------------------------


@server.post("/api/v1/webhooks/tancis/consignments")
def webhook_consignment():
    payload = request.get_json(silent=True) or {}
    base = request.host_url.rstrip("/")
    ack, _invoice = process_consignment(payload, public_base_url=base)
    return jsonify(ack)


@server.post("/api/v1/webhooks/tancis/consignment-notes-status")
def webhook_notes_status():
    """IF-E-CLR-022 Consignment notes status information (legacy IF-I-CLR-067)."""
    payload = request.get_json(silent=True) or {}
    ack, _meta = process_notes_status(payload)
    return jsonify(ack)


@server.get("/invoices/<path:filename>")
def serve_invoice(filename: str):
    return send_from_directory(INVOICE_DIR, filename)


@server.get("/go/<checkout_id>")
def capitalpay_hosted_checkout(checkout_id: str):
    """Hosted CapitalPay checkout — opens the live payment form for this invoice."""
    session_row = db.get_checkout_session(checkout_id)
    if not session_row:
        return "Checkout session not found or expired.", 404
    try:
        html = fetch_checkout_page(session_row["params"])
    except CapitalPayError as exc:
        return str(exc), 502
    return html


@server.get("/paymentlink/<invoice_no>")
def payment_checkout(invoice_no: str):
    inv = db.get_invoice_by_no(invoice_no)
    if not inv:
        return "Invoice not found", 404
    checkout = db.get_checkout_by_invoice(invoice_no)
    if checkout:
        return redirect(f"/go/{checkout['checkout_id']}", code=302)
    return f"""<!DOCTYPE html>
<html><head><title>Pay {invoice_no}</title>
<link rel="icon" href="/assets/favicon.ico"/>
<style>
body{{font-family:Segoe UI,sans-serif;background:linear-gradient(180deg,#EEF4FB,#fff);display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;border:1px solid #D7DEE8;border-radius:18px;padding:28px;max-width:460px;box-shadow:0 18px 40px rgba(11,58,110,.1)}}
h1{{color:#0B3A6E;margin:0 0 8px}} .amt{{font-size:32px;font-weight:800;color:#1B5FA8}}
a.btn{{display:inline-block;margin-top:16px;background:#0B3A6E;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px}}
</style></head>
<body><div class="card">
<img src="/assets/tcams-logo.png" width="72" alt="TCAMS"/>
<h1>Checkout unavailable</h1>
<p>Invoice <strong>{inv['invoice_no']}</strong> · TANSAD <strong>{inv['tansad_no']}</strong></p>
<div class="amt">{inv['currency']} {inv['total_due']:,.2f}</div>
<p>CapitalPay checkout was not created for this invoice. Configure CAPITALPAY_API_KEY and CAPITALPAY_API_SECRET.</p>
<a class="btn" href="{inv['invoice_path']}">Back to invoice</a>
</div></body></html>"""


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

THEME = {
    "colorScheme": "light",
    "primaryColor": "blue",
    "fontFamily": "'Segoe UI', 'Trebuchet MS', sans-serif",
    "headings": {"fontFamily": "'Segoe UI', 'Trebuchet MS', sans-serif"},
    "colors": {
        "blue": [
            "#E7F1FB",
            "#C9DFF5",
            "#A5C9EC",
            "#7FB0E0",
            "#5B98D2",
            "#3B82C4",
            "#1B5FA8",
            "#0B3A6E",
            "#082C54",
            "#051C36",
        ]
    },
}


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(uid)


def _fee_preview_block(payload: dict, declarant_tin: str):
    calc = calculate_fees(payload["message_info"], declarant_tin)
    breakdown = fee_breakdown_lines(calc)
    return dmc.Stack(
        [
            dmc.Text(
                f"GN 83 estimate: TZS {calc['total_due']:,.2f} · "
                f"{calc['fee_mode']} · {calc['gn83_tariff_code']}",
                fw=700,
                c="teal.8",
                size="sm",
            ),
            dmc.Text(breakdown[0], size="xs", c="dimmed"),
        ],
        gap=4,
    )


def login_layout():
    return html.Div(
        [
            html.Div(className="brand-ribbon"),
            html.Div(
                className="login-hero",
                children=dmc.Paper(
                    className="glass-card",
                    p="xl",
                    radius="lg",
                    withBorder=True,
                    style={"width": "min(440px, 100%)"},
                    children=[
                        dmc.Group(
                            [
                                html.Img(
                                    src="/assets/tcams-logo.png",
                                    style={"width": 72, "height": 72},
                                ),
                                dmc.Stack(
                                    [
                                        dmc.Title("TCAMS", order=2, c="blue.7"),
                                        dmc.Text(
                                            "Tanzania Clearing Agent Management System",
                                            size="sm",
                                            c="dimmed",
                                        ),
                                    ],
                                    gap=0,
                                ),
                            ]
                        ),
                        dmc.Space(h=16),
                        dmc.Text(
                            "Sign in as CFA / Declarant to open TCAMS or TANCIS simulator.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.Space(h=12),
                        dmc.TextInput(
                            id="login-username",
                            label="Username",
                            placeholder="Martin",
                            required=True,
                        ),
                        dmc.Space(h=10),
                        dmc.PasswordInput(
                            id="login-password",
                            label="Password",
                            placeholder="••••••••",
                            required=True,
                        ),
                        dmc.Space(h=8),
                        dmc.Text(id="login-error", c="red", size="sm"),
                        dmc.Space(h=8),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Enter TCAMS",
                                    id="login-tcams-btn",
                                    fullWidth=True,
                                    color="blue",
                                ),
                                dmc.Button(
                                    "Enter TANCIS UI",
                                    id="login-tancis-btn",
                                    fullWidth=True,
                                    variant="outline",
                                    color="teal",
                                ),
                            ],
                            grow=True,
                        ),
                        dmc.Space(h=14),
                        dmc.Alert(
                            title="Test accounts",
                            color="gray",
                            children=dmc.Text(
                                "Martin/Martin123 · Joshua/Joshua123 · Kevin/Kevin123 · Yohana/Yohana123",
                                size="xs",
                            ),
                        ),
                    ],
                ),
            ),
        ],
        className="tcams-shell",
    )


def topbar(user: dict, page: str, unread: int):
    return dmc.Paper(
        className="topbar",
        p="md",
        radius=0,
        children=dmc.Group(
            [
                dmc.Group(
                    [
                        html.Img(
                            src="/assets/tcams-logo.png",
                            style={"width": 46, "height": 46},
                        ),
                        dmc.Stack(
                            [
                                dmc.Text(
                                    "TCAMS" if page == "tcams" else "TANCIS Simulator",
                                    fw=800,
                                    c="blue.7",
                                ),
                                dmc.Text(
                                    f"{user['company_name']} · TIN {user['declarant_tin']}",
                                    size="xs",
                                    c="dimmed",
                                ),
                            ],
                            gap=0,
                        ),
                    ]
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "TCAMS Desk",
                            id="goto-tcams",
                            variant="light" if page != "tcams" else "filled",
                            className="nav-pill",
                            size="sm",
                        ),
                        dmc.Button(
                            "TANCIS UI",
                            id="goto-tancis",
                            variant="light" if page != "tancis" else "filled",
                            color="teal",
                            className="nav-pill",
                            size="sm",
                        ),
                        dmc.Button(
                            "View payloads",
                            id="open-exchange-modal",
                            variant="outline",
                            color="grape",
                            className="nav-pill",
                            size="sm",
                        ),
                        dmc.Badge(
                            f"Alerts {unread}",
                            id="notif-bell",
                            color="red" if unread else "gray",
                            variant="filled" if unread else "light",
                            size="lg",
                        ),
                        dmc.Button(
                            "Logout",
                            id="logout-btn",
                            variant="subtle",
                            color="gray",
                            size="sm",
                        ),
                    ]
                ),
            ],
            justify="space-between",
        ),
    )


def _interface_catalog_table() -> html.Table:
    rows = [
        html.Tr(
            [
                html.Th("Interface Id"),
                html.Th("Interface Name"),
                html.Th("Transmitter"),
                html.Th("Receiver"),
            ]
        )
    ]
    for item in INTERFACE_CATALOG:
        highlight = item["interface_id"] == CONSIGNMENT_NOTES_STATUS
        rows.append(
            html.Tr(
                [
                    html.Td(item["interface_id"]),
                    html.Td(
                        html.Span(
                            item["name"],
                            style={"fontWeight": 700 if highlight else 400},
                        )
                    ),
                    html.Td(item["transmitter"]),
                    html.Td(item["receiver"]),
                ],
                style={"background": "#F0FDF4" if highlight else "transparent"},
            )
        )
    return html.Table(rows, className="invoice-table")


def _pretty(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def build_exchange_modal_body(exchange_row):
    if not exchange_row:
        return dmc.Alert(
            "No TANCIS ↔ TCAMS payload exchange yet. Simulate a consignment from the TANCIS UI.",
            title="Waiting for transmission",
            color="gray",
        )
    ex = exchange_row.get("exchange") or {}
    meta = ex.get("meta") or {}
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Badge(CONSIGNMENT_INFORMATION, color="teal"),
                    dmc.Badge(AGENT_FEE_INVOICE, color="blue"),
                    dmc.Text(
                        exchange_row.get("summary") or "",
                        size="sm",
                        c="dimmed",
                    ),
                ]
            ),
            dmc.Text(
                f"TANSAD {exchange_row.get('tansad_no')} · Invoice {exchange_row.get('invoice_no')} · "
                f"{meta.get('currency', 'TZS')} {float(meta.get('total_due') or 0):,.2f}",
                fw=700,
            ),
            dmc.List(
                [
                    dmc.ListItem(step)
                    for step in ex.get("direction_flow")
                    or [
                        "TANCIS -> TCAMS | IF-E-CLR-018 Consignment Information",
                        "TCAMS -> TANCIS | IF-E-CLR-018 ack",
                        "TCAMS -> TANCIS | IF-E-CLR-019 Agent fee invoice",
                        "TANCIS -> TCAMS | IF-E-CLR-019 ack",
                    ]
                ],
                size="sm",
            ),
            dmc.Tabs(
                value="080_tx",
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab("018 Send (Consignment Information)", value="080_tx"),
                            dmc.TabsTab("018 Ack", value="080_rx"),
                            dmc.TabsTab("019 Send (Agent fee invoice)", value="081_tx"),
                            dmc.TabsTab("019 Ack", value="081_rx"),
                            dmc.TabsTab("All JSON", value="all"),
                        ]
                    ),
                    dmc.TabsPanel(
                        html.Pre(
                            _pretty(ex.get("if_i_clr_080_transmission")),
                            className="payload-box",
                        ),
                        value="080_tx",
                        pt="sm",
                    ),
                    dmc.TabsPanel(
                        html.Pre(
                            _pretty(ex.get("if_i_clr_080_reception")),
                            className="payload-box",
                        ),
                        value="080_rx",
                        pt="sm",
                    ),
                    dmc.TabsPanel(
                        html.Pre(
                            _pretty(ex.get("if_i_clr_081_transmission")),
                            className="payload-box",
                        ),
                        value="081_tx",
                        pt="sm",
                    ),
                    dmc.TabsPanel(
                        html.Pre(
                            _pretty(ex.get("if_i_clr_081_reception")),
                            className="payload-box",
                        ),
                        value="081_rx",
                        pt="sm",
                    ),
                    dmc.TabsPanel(
                        html.Pre(_pretty(ex), className="payload-box"),
                        value="all",
                        pt="sm",
                    ),
                ],
            ),
        ],
        gap="sm",
    )


def tcams_layout(user: dict):
    stats = db.analytics_for_user(user["id"])
    invoices = db.get_invoices_for_user(user["id"])
    notes = db.get_notifications(user["id"])
    unread = db.unread_count(user["id"])
    consignments = db.recent_consignments(user["id"])

    invoice_rows = [
        html.Tr(
            [
                html.Td(inv["invoice_no"]),
                html.Td(inv["tansad_no"]),
                html.Td(inv["invoice_type"]),
                html.Td(inv["fee_mode"]),
                html.Td(f"{inv['currency']} {inv['total_due']:,.2f}"),
                html.Td("Pushed" if inv["pushed_to_tancis"] else "Pending"),
                html.Td(
                    html.A(
                        "Download / View",
                        href=inv["invoice_path"],
                        target="_blank",
                        style={"color": "#1B5FA8", "fontWeight": 700},
                    )
                ),
            ]
        )
        for inv in invoices
    ] or [
        html.Tr([html.Td("No invoices yet. Simulate a consignment from TANCIS UI.", colSpan=7)])
    ]

    note_items = [
        dmc.Paper(
            p="sm",
            withBorder=True,
            radius="md",
            mb=8,
            children=[
                dmc.Group(
                    [
                        dmc.Badge(n["kind"], color="blue" if n["kind"] == "INVOICE" else "grape"),
                        dmc.Text(n["created_at"][:19].replace("T", " "), size="xs", c="dimmed"),
                    ],
                    justify="space-between",
                ),
                dmc.Text(n["title"], fw=700, size="sm"),
                dmc.Text(n["body"], size="xs", c="dimmed"),
            ],
        )
        for n in notes[:8]
    ] or [dmc.Text("No notifications yet.", c="dimmed", size="sm")]

    preview_src = invoices[0]["invoice_path"] if invoices else ""

    return html.Div(
        [
            html.Div(className="brand-ribbon"),
            topbar(user, "tcams", unread),
            dmc.Container(
                fluid=True,
                p="md",
                children=[
                    dmc.SimpleGrid(
                        cols=4,
                        spacing="md",
                        children=[
                            dmc.Paper(
                                className="stat-card glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Text("Invoices generated", size="xs", c="dimmed"),
                                    dmc.Title(str(stats["total_invoices"]), order=2),
                                ],
                            ),
                            dmc.Paper(
                                className="stat-card glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Text("Pushed to TANCIS", size="xs", c="dimmed"),
                                    dmc.Title(str(stats["pushed_count"]), order=2, c="teal"),
                                ],
                            ),
                            dmc.Paper(
                                className="stat-card glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Text("Consignments received", size="xs", c="dimmed"),
                                    dmc.Title(str(stats["consignments"]), order=2),
                                ],
                            ),
                            dmc.Paper(
                                className="stat-card glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Text("Total billed (TZS)", size="xs", c="dimmed"),
                                    dmc.Title(f"{stats['total_amount']:,.0f}", order=3),
                                ],
                            ),
                        ],
                    ),
                    dmc.Space(h=16),
                    dmc.Paper(
                        className="glass-card",
                        p="md",
                        withBorder=True,
                        children=[
                            dmc.Title("TANCIS ↔ TCAMS interface catalogue", order=4),
                            dmc.Text(
                                "IF-E-CLR-022 replaces the former Consignment cancellation interface "
                                "(IF-I-CLR-067). Payload structure is unchanged.",
                                size="sm",
                                c="dimmed",
                            ),
                            dmc.Space(h=10),
                            _interface_catalog_table(),
                        ],
                    ),
                    dmc.Space(h=16),
                    dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        children=[
                            dmc.Paper(
                                className="glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Group(
                                        [
                                            dmc.Title("Notifications", order=4),
                                            dmc.Badge(f"{unread} new", color="red"),
                                        ],
                                        justify="space-between",
                                    ),
                                    dmc.Space(h=8),
                                    html.Div(note_items),
                                    dmc.Button(
                                        "Mark all read",
                                        id="mark-read-btn",
                                        variant="light",
                                        size="xs",
                                        mt="sm",
                                    ),
                                ],
                            ),
                            dmc.Paper(
                                className="glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Title("Latest invoice preview", order=4),
                                    dmc.Space(h=8),
                                    html.Iframe(
                                        src=preview_src,
                                        className="invoice-preview-frame",
                                        id="invoice-preview",
                                    )
                                    if preview_src
                                    else dmc.Alert(
                                        "No invoice to preview yet.",
                                        color="gray",
                                        title="Waiting for TANCIS payload",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Space(h=16),
                    dmc.Paper(
                        className="glass-card",
                        p="md",
                        withBorder=True,
                        children=[
                            dmc.Title("Invoices pushed to TANCIS", order=4),
                            dmc.Text(
                                "Downloadable bank collection advice with QR + payment link.",
                                size="sm",
                                c="dimmed",
                            ),
                            dmc.Space(h=10),
                            html.Table(
                                [
                                    html.Thead(
                                        html.Tr(
                                            [
                                                html.Th("Invoice"),
                                                html.Th("TANSAD"),
                                                html.Th("Type"),
                                                html.Th("Fee mode"),
                                                html.Th("Amount"),
                                                html.Th("TANCIS"),
                                                html.Th("Action"),
                                            ]
                                        )
                                    ),
                                    html.Tbody(invoice_rows),
                                ],
                                style={
                                    "width": "100%",
                                    "borderCollapse": "collapse",
                                    "fontSize": "14px",
                                },
                            ),
                        ],
                    ),
                    dmc.Space(h=16),
                    dmc.Paper(
                        className="glass-card",
                        p="md",
                        withBorder=True,
                        children=[
                            dmc.Title("Recent consignment lineage", order=4),
                            dmc.Space(h=8),
                            dmc.Stack(
                                [
                                    dmc.Text(
                                        f"{c['tansad_no']} · {c['status']} · {c['created_at'][:19].replace('T',' ')}"
                                        + (f" — {c['lineage_note']}" if c.get("lineage_note") else ""),
                                        size="sm",
                                    )
                                    for c in consignments
                                ]
                                or [dmc.Text("No consignments yet.", c="dimmed", size="sm")]
                            ),
                        ],
                    ),
                ],
            ),
        ],
        className="tcams-shell",
    )


def tancis_layout(user: dict):
    unread = db.unread_count(user["id"])
    latest = db.get_latest_invoice_for_tin(user["declarant_tin"])
    preview_payload = sample_080_payload(user)
    return html.Div(
        [
            html.Div(className="brand-ribbon"),
            topbar(user, "tancis", unread),
            dmc.Container(
                fluid=True,
                p="md",
                children=[
                    dmc.Alert(
                        title="CFA engagement on TANCIS",
                        color="teal",
                        children=(
                            "Lodge the declaration here, send the consignment payload (IF-E-CLR-018) to TCAMS, "
                            "then download the generated invoice returned via IF-E-CLR-019 — without leaving TANCIS."
                        ),
                    ),
                    dmc.Space(h=14),
                    dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        children=[
                            dmc.Paper(
                                className="glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Title("Simulate Consignment Payload", order=4),
                                    dmc.Text(
                                        f"Declarant TIN locked to {user['declarant_tin']} ({user['company_name']}).",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                    dmc.Space(h=10),
                                    dmc.Switch(
                                        id="exempted-switch",
                                        label="Set message_info.status = exempted (service-fee invoice)",
                                        checked=False,
                                    ),
                                    dmc.Space(h=8),
                                    dmc.Text(
                                        id="scenario-label",
                                        size="sm",
                                        fw=600,
                                        c="blue.7",
                                    ),
                                    html.Div(id="fee-preview"),
                                    dmc.Space(h=8),
                                    html.Div(
                                        json.dumps(preview_payload, indent=2),
                                        id="payload-preview",
                                        className="payload-box",
                                    ),
                                    dmc.Space(h=12),
                                    dmc.Group(
                                        [
                                            dmc.Button(
                                                "Click To Send TCAMS Consignment Payload",
                                                id="simulate-080-btn",
                                                color="teal",
                                                size="md",
                                            ),
                                            dmc.Button(
                                                "Refresh sample payload",
                                                id="refresh-payload-btn",
                                                variant="light",
                                            ),
                                        ]
                                    ),
                                    dmc.Space(h=10),
                                    dmc.Text(id="simulate-status", size="sm"),
                                    html.Div(
                                        id="simulate-ack",
                                        className="payload-box",
                                        style={"display": "none"},
                                    ),
                                ],
                            ),
                            dmc.Paper(
                                className="glass-card",
                                p="md",
                                withBorder=True,
                                children=[
                                    dmc.Title("Invoice returned from TCAMS", order=4),
                                    dmc.Text(
                                        "Once TCAMS pushes IF-E-CLR-019, the CFA can view and download here.",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                    dmc.Space(h=10),
                                    html.Div(
                                        id="tancis-invoice-panel",
                                        children=_tancis_invoice_panel(latest),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
        className="tcams-shell",
    )


def _tancis_invoice_panel(invoice):
    if not invoice:
        return dmc.Alert(
            "No invoice received yet for this declarant.",
            title="Waiting for TCAMS",
            color="gray",
        )
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Badge(AGENT_FEE_INVOICE, color="blue"),
                    dmc.Badge(invoice["tancis_result_code"] or "S001", color="teal"),
                    dmc.Badge(invoice["invoice_type"], color="grape"),
                ]
            ),
            dmc.Text(f"Invoice {invoice['invoice_no']} · TANSAD {invoice['tansad_no']}", fw=700),
            dmc.Text(
                f"{invoice['currency']} {invoice['total_due']:,.2f} · {invoice['fee_mode']} settlement",
                c="dimmed",
                size="sm",
            ),
            dmc.Anchor(
                "Open / Download invoice",
                href=invoice["invoice_path"],
                target="_blank",
                fw=700,
            ),
            dmc.Anchor(
                "Open payment checkout link",
                href=invoice["payment_link"],
                target="_blank",
            ),
            html.Iframe(
                src=f"{invoice['invoice_path']}?v={invoice['invoice_no']}",
                className="invoice-preview-frame",
            ),
        ]
    )


app.layout = dmc.MantineProvider(
    theme=THEME,
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="session-store"),
        dcc.Store(id="latest-exchange-id"),
        dcc.Store(id="sample-scenario-index", data=0),
        dcc.Store(id="sample-payload-data"),
        html.Div(id="page-root"),
        dmc.Modal(
            id="exchange-modal",
            title="TANCIS ↔ TCAMS interface payloads",
            opened=False,
            centered=True,
            size="xl",
            children=[
                html.Div(id="exchange-modal-body"),
                dmc.Space(h=12),
                dmc.Group(
                    [
                        dmc.Button(
                            "Close",
                            id="close-exchange-modal",
                            variant="default",
                        )
                    ],
                    justify="flex-end",
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("page-root", "children"),
    Output("session-store", "data"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def render_page(pathname):
    user = current_user()
    path = (pathname or "/").rstrip("/") or "/"
    if not user:
        return login_layout(), {"authed": False}
    if path.startswith("/tancis"):
        return tancis_layout(user), {"authed": True, "user": user["username"]}
    if path.startswith("/tcams"):
        return tcams_layout(user), {"authed": True, "user": user["username"]}
    return tcams_layout(user), {"authed": True, "user": user["username"]}


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("login-error", "children"),
    Input("login-tcams-btn", "n_clicks"),
    Input("login-tancis-btn", "n_clicks"),
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def do_login(n_tcams, n_tancis, username, password):
    trig = dash.callback_context.triggered_id
    if not username or not password:
        return no_update, "Enter username and password."
    user = db.authenticate(username.strip(), password)
    if not user:
        return no_update, "Invalid credentials."
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    if trig == "login-tancis-btn":
        return "/tancis", ""
    return "/tcams", ""


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("logout-btn", "n_clicks"),
    prevent_initial_call=True,
)
def do_logout(n):
    if not n:
        raise PreventUpdate
    session.clear()
    return "/"


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("goto-tcams", "n_clicks"),
    Input("goto-tancis", "n_clicks"),
    prevent_initial_call=True,
)
def switch_desk(n1, n2):
    trig = dash.callback_context.triggered_id
    if trig == "goto-tancis":
        return "/tancis"
    return "/tcams"


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("mark-read-btn", "n_clicks"),
    prevent_initial_call=True,
)
def mark_read(n):
    user = current_user()
    if not user or not n:
        raise PreventUpdate
    db.mark_notifications_read(user["id"])
    return "/tcams"


@callback(
    Output("payload-preview", "children"),
    Output("sample-scenario-index", "data"),
    Output("scenario-label", "children"),
    Output("sample-payload-data", "data"),
    Output("fee-preview", "children"),
    Input("refresh-payload-btn", "n_clicks"),
    Input("exempted-switch", "checked"),
    State("sample-scenario-index", "data"),
    prevent_initial_call=False,
)
def refresh_payload(n, exempted, scenario_index):
    user = current_user()
    if not user:
        raise PreventUpdate
    idx = 0 if scenario_index is None else int(scenario_index)
    if ctx.triggered_id == "refresh-payload-btn" and n:
        idx = (idx + 1) % scenario_count()
    payload = sample_080_payload(user, bool(exempted), idx)
    label = f"Sample scenario {idx + 1}/{scenario_count()}: {scenario_label(idx)}"
    fee_block = _fee_preview_block(payload, user["declarant_tin"])
    return (
        json.dumps(payload, indent=2),
        idx,
        label,
        payload,
        fee_block,
    )


@callback(
    Output("simulate-status", "children"),
    Output("tancis-invoice-panel", "children"),
    Output("exchange-modal", "opened", allow_duplicate=True),
    Output("exchange-modal-body", "children", allow_duplicate=True),
    Output("latest-exchange-id", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("simulate-080-btn", "n_clicks"),
    State("sample-payload-data", "data"),
    prevent_initial_call=True,
)
def simulate_consignment(n, stored_payload):
    user = current_user()
    if not user or not n:
        raise PreventUpdate

    if not stored_payload:
        raise PreventUpdate
    payload = payload_for_processing(stored_payload)
    public_base = os.environ.get("BASE_URL") or request.host_url.rstrip("/")
    ack, _invoice = process_consignment(payload, public_base_url=public_base)
    code = ack.get("header", {}).get("result_status_code")
    tcams = ack.get("tcams") or {}
    status_msg = (
        f"Consignment accepted ({code}). Invoice {tcams.get('invoice_no')} "
        f"pushed to TANCIS ({tcams.get('fee_mode')}: "
        f"TZS {float(tcams.get('total_due') or 0):,.2f}). Payload modal opened."
        if code == "S001"
        else f"Processing result: {code} — {ack.get('header', {}).get('result_message')}"
    )
    latest_invoice = db.get_latest_invoice_for_tin(user["declarant_tin"])
    exchange_id = tcams.get("exchange_id")
    exchange_row = db.get_exchange_by_id(exchange_id) if exchange_id else db.get_latest_exchange_for_user(user["id"])
    return (
        status_msg,
        _tancis_invoice_panel(latest_invoice),
        True,
        build_exchange_modal_body(exchange_row),
        exchange_id,
        "/tancis",
    )


@callback(
    Output("exchange-modal", "opened", allow_duplicate=True),
    Output("exchange-modal-body", "children", allow_duplicate=True),
    Output("latest-exchange-id", "data", allow_duplicate=True),
    Input("open-exchange-modal", "n_clicks"),
    prevent_initial_call=True,
)
def open_payload_modal(n):
    user = current_user()
    if not user or not n:
        raise PreventUpdate
    exchange_row = db.get_latest_exchange_for_user(user["id"])
    return True, build_exchange_modal_body(exchange_row), (exchange_row or {}).get("id")


@callback(
    Output("exchange-modal", "opened", allow_duplicate=True),
    Input("close-exchange-modal", "n_clicks"),
    prevent_initial_call=True,
)
def close_payload_modal(n):
    if not n:
        raise PreventUpdate
    return False


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(host="0.0.0.0", port=port, debug=True)
