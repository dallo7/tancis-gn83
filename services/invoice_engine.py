"""Invoice document generation with QR + payment link."""

from __future__ import annotations

import base64
import io
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import qrcode

from services.config import ACCEPTED_BANKS, CURRENCY, INVOICE_DIR, INVOICE_DUE_DAYS
from services.gn83 import fee_breakdown_lines
from services.capitalpay import create_checkout_session


def _short_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_invoice_no() -> str:
    return _short_code(6)


def generate_suc_number() -> str:
    year = datetime.utcnow().strftime("%y")
    return f"SUC-{year}-{secrets.token_hex(4).upper()}"


def build_payment_link(base_url: str, invoice_no: str) -> str:
    root = (base_url or "https://example.com").rstrip("/")
    return f"{root}/paymentlink/{invoice_no}"


def make_qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B3A6E", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def qr_data_uri(payload: str) -> str:
    raw = make_qr_png_bytes(payload)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def render_invoice_html(
    *,
    invoice: Dict[str, Any],
    user: Optional[Dict[str, Any]],
    message_info: Dict[str, Any],
    logo_data_uri: str,
    qr_data: str,
    breakdown: tuple,
) -> str:
    company = (user or {}).get("company_name") or "Clearing & Forwarding Agent"
    email = (user or {}).get("email") or "-"
    phone = (user or {}).get("phone") or "-"
    tin = invoice["declarant_tin"]
    bl = (message_info.get("bill_of_lading") or {}).get("bl_number") or "-"
    tansad = invoice["tansad_no"]
    banks_html = "".join(
        f'<div class="bank-chip">{bank}</div>' for bank in ACCEPTED_BANKS
    )
    breakdown_html = "".join(f"<li>{line}</li>" for line in breakdown)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TCAMS Invoice {invoice['invoice_no']}</title>
  <style>
    :root {{
      --navy: #0B3A6E;
      --blue: #1B5FA8;
      --muted: #6B7280;
      --line: #D7DEE8;
      --bg: #F5F7FB;
      --green: #1F9D55;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(180deg, #EAF1FA 0%, #F7F9FC 40%, #FFFFFF 100%);
      color: #111827;
      padding: 24px;
    }}
    .ribbon {{
      height: 8px;
      border-radius: 999px;
      background: linear-gradient(90deg, #5BB4E5, #0B3A6E, #1F9D55, #F2C94C);
      margin-bottom: 16px;
    }}
    .sheet {{
      max-width: 920px;
      margin: 0 auto;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 28px;
      box-shadow: 0 18px 40px rgba(11, 58, 110, 0.08);
    }}
    .top-grid {{
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .box {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      background: #fff;
    }}
    .label {{
      color: var(--blue);
      font-size: 11px;
      letter-spacing: 0.08em;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .hero-value {{
      color: var(--navy);
      font-size: 28px;
      font-weight: 800;
      margin-top: 6px;
      letter-spacing: 0.02em;
    }}
    .brand-row {{
      display: flex;
      gap: 16px;
      align-items: center;
      margin: 10px 0 18px;
    }}
    .brand-row img.logo {{ width: 88px; height: 88px; object-fit: contain; }}
    .brand-row h1 {{
      margin: 0;
      color: var(--navy);
      font-size: 28px;
      line-height: 1.15;
    }}
    .brand-row .sub {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.08em;
      margin-top: 4px;
    }}
    .meta {{ font-size: 13px; line-height: 1.7; color: #374151; }}
    .meta strong {{ color: #111827; }}
    .intro {{
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 18px;
      line-height: 1.5;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .section-title {{
      color: var(--blue);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }}
    .field {{ margin: 4px 0; font-size: 14px; }}
    .field span {{ color: var(--muted); display: inline-block; min-width: 140px; }}
    .amount-row {{
      display: grid;
      grid-template-columns: 1.1fr 1.4fr;
      gap: 14px;
      margin: 14px 0;
    }}
    .amount-box .hero-value {{ font-size: 34px; }}
    .pay-help {{ font-size: 13px; color: #374151; line-height: 1.55; }}
    .pay-link {{
      display: inline-block;
      margin-top: 10px;
      color: var(--blue);
      font-weight: 700;
      word-break: break-all;
    }}
    .qr-wrap {{
      display: flex;
      gap: 16px;
      align-items: center;
      margin-top: 12px;
      padding: 12px;
      border: 1px dashed #A8C2E0;
      border-radius: 12px;
      background: var(--bg);
    }}
    .qr-wrap img {{ width: 120px; height: 120px; border-radius: 8px; background: #fff; }}
    .banks {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-top: 8px;
    }}
    .bank-chip {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 8px;
      text-align: center;
      font-size: 12px;
      font-weight: 600;
      color: var(--navy);
      background: #fff;
    }}
    .settlement {{
      margin-top: 16px;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      background: #FBFCFF;
    }}
    .settlement-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      font-size: 13px;
    }}
    .footer-note {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 12px;
    }}
    .badge {{
      display: inline-block;
      background: #E8F7EE;
      color: var(--green);
      border: 1px solid #B7E4C7;
      border-radius: 999px;
      padding: 2px 10px;
      font-size: 11px;
      font-weight: 700;
      margin-left: 8px;
    }}
    ul.breakdown {{ margin: 8px 0 0; padding-left: 18px; color: #374151; font-size: 13px; }}
    @media (max-width: 720px) {{
      .top-grid, .two-col, .amount-row, .settlement-grid, .banks {{
        grid-template-columns: 1fr;
      }}
      .brand-row {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="sheet">
    <div class="ribbon"></div>
    <div class="top-grid">
      <div class="box">
        <div class="label">SUC Number</div>
        <div class="hero-value">{invoice['suc_number']}</div>
      </div>
      <div class="box">
        <div class="label">Invoice Number</div>
        <div class="hero-value">{invoice['invoice_no']}</div>
        <div class="meta" style="margin-top:10px;">
          <div><strong>SUC Number:</strong> {invoice['suc_number']}</div>
          <div><strong>Issue Date:</strong> {invoice['issue_date']}</div>
          <div><strong>Due Date:</strong> {invoice['due_date']}</div>
          <div><strong>Invoice Currency:</strong> {invoice['currency']}</div>
          <div><strong>Invoice Number:</strong> {invoice['invoice_no']}</div>
          <div><strong>Type:</strong> {invoice['invoice_type']} <span class="badge">{invoice['fee_mode']}</span></div>
        </div>
      </div>
    </div>

    <div class="brand-row">
      <img class="logo" src="{logo_data_uri}" alt="TCAMS logo" />
      <div>
        <h1>TCAMS Invoice - SUC</h1>
        <div class="sub">BANK COLLECTION ADVICE</div>
      </div>
    </div>
    <p class="intro">
      Payment advice for SUC processing and settlement. Present this invoice at an approved
      collection bank and quote the invoice number exactly as shown. Scan the QR code or open
      the payment link to complete checkout in the same session.
    </p>

    <div class="two-col">
      <div class="box">
        <div class="section-title">Invoice To</div>
        <div class="field"><span>Company</span><strong>{company}</strong></div>
        <div class="field"><span>TIN / TAX ID</span><strong>{tin}</strong></div>
        <div class="field"><span>Email</span><strong>{email}</strong></div>
        <div class="field"><span>Phone</span><strong>{phone}</strong></div>
      </div>
      <div class="box">
        <div class="section-title">SUC Reference</div>
        <div class="field"><span>Customs Entry</span><strong>{tansad}</strong></div>
        <div class="field"><span>Shipment Reference</span><strong>{bl}</strong></div>
        <div class="field"><span>Cargo Category</span><strong>{invoice.get('cargo_category') or '-'}</strong></div>
        <div class="field"><span>Document Reference</span><strong>{(message_info.get('bill_of_lading') or {}).get('master_bl_number') or '-'}</strong></div>
      </div>
    </div>

    <div class="amount-row">
      <div class="box amount-box">
        <div class="label">Amount Due</div>
        <div class="hero-value">{invoice['currency']} {invoice['total_due']:,.2f}</div>
        <ul class="breakdown">{breakdown_html}</ul>
      </div>
      <div class="box">
        <div class="section-title">Pay Now</div>
        <div class="pay-help">
          Pay through Capital Pay Direct checkout. Quote invoice number
          <strong>{invoice['invoice_no']}</strong>.
        </div>
        <div class="field" style="margin-top:8px;">
          <span>Checkout link</span>
        </div>
        <a class="pay-link" href="{invoice['payment_link']}" target="_blank" rel="noopener">
          {invoice['payment_link']}
        </a>
        <div class="qr-wrap">
          <img src="{qr_data}" alt="Payment QR code" />
          <div class="pay-help">
            <strong>Scan to pay</strong><br/>
            QR encodes the CapitalPay checkout link for this invoice.
          </div>
        </div>
      </div>
    </div>

    <div class="box">
      <div class="section-title">Accepted Collection Banks</div>
      <div class="banks">{banks_html}</div>
    </div>

    <div class="settlement">
      <div class="section-title">Settlement Details</div>
      <div class="settlement-grid">
        <div><strong>Invoice Number</strong><br/>{invoice['invoice_no']}</div>
        <div><strong>Due Date</strong><br/>{invoice['due_date']}</div>
        <div><strong>Total Due</strong><br/>{invoice['currency']} {invoice['total_due']:,.2f}</div>
        <div><strong>Collection Bank</strong><br/>—</div>
        <div><strong>Account Number</strong><br/>—</div>
        <div><strong>Branch</strong><br/>—</div>
        <div><strong>Beneficiary Name</strong><br/>TAFFA / TCAMS Collections</div>
        <div><strong>Beneficiary Bank</strong><br/>CapitalPay Network</div>
        <div><strong>Beneficiary Account</strong><br/>—</div>
      </div>
      <div class="footer-note">
        Present this invoice through CapitalPay or at an accepted collection bank and quote
        the invoice number exactly as shown.
      </div>
    </div>
  </div>
</body>
</html>
"""


def write_invoice_artifacts(
    *,
    invoice_meta: Dict[str, Any],
    user: Optional[Dict[str, Any]],
    message_info: Dict[str, Any],
    calc: Dict[str, Any],
    logo_path: Path,
    base_url: str,
) -> Dict[str, Any]:
    invoice_no = invoice_meta["invoice_no"]
    suc_number = invoice_meta["suc_number"]
    tansad_no = invoice_meta["tansad_no"]
    declarant_tin = invoice_meta["declarant_tin"]

    checkout = create_checkout_session(
        invoice_no=invoice_no,
        suc_number=suc_number,
        tansad_no=tansad_no,
        amount=float(calc["total_due"]),
        vat_amount=float(calc["vat_amount"]),
        base_url=base_url,
        user=user,
        declarant_tin=declarant_tin,
    )
    payment_link = (
        checkout["checkout_url"]
        if checkout
        else build_payment_link(base_url, invoice_no)
    )

    qr_bytes = make_qr_png_bytes(payment_link)
    qr_path = INVOICE_DIR / f"{invoice_no}-qr.png"
    qr_path.write_bytes(qr_bytes)

    logo_b64 = ""
    if logo_path.exists():
        logo_b64 = "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode(
            "ascii"
        )

    issue = datetime.utcnow()
    due = issue + timedelta(days=INVOICE_DUE_DAYS)
    record = {
        **invoice_meta,
        **calc,
        "currency": CURRENCY,
        "payment_link": payment_link,
        "checkout_id": checkout["checkout_id"] if checkout else None,
        "capitalpay_invoice_ref": checkout["capitalpay_invoice_ref"] if checkout else None,
        "issue_date": issue.strftime("%d %b %Y"),
        "due_date": due.strftime("%d %b %Y"),
        "invoice_type": invoice_meta.get("invoice_type", "G"),
    }

    html = render_invoice_html(
        invoice=record,
        user=user,
        message_info=message_info,
        logo_data_uri=logo_b64,
        qr_data=qr_data_uri(payment_link),
        breakdown=fee_breakdown_lines(calc),
    )
    html_path = INVOICE_DIR / f"{invoice_no}.html"
    html_path.write_text(html, encoding="utf-8")

    public_path = f"/invoices/{invoice_no}.html"
    return {
        **record,
        "html_path": str(html_path),
        "qr_path": str(qr_path),
        "invoice_path": public_path,
    }