# TCAMS ↔ TANCIS GN 83 Invoice Studio

Professional Dash + Dash Mantine demo for the TANCIS consignment → TCAMS invoice → TANCIS download loop (IF-E-CLR-018 / IF-E-CLR-019).

## Features

- 4 CFA profiles in SQLite with login credentials
- TANCIS simulator sends IF-E-CLR-018 consignment payloads
- TCAMS unpacks cargo, applies GN 83 fee rules + VAT, generates bank collection advice
- Invoice matches the SUC template and adds:
  - unique QR code embedding the payment link
  - clickable payment link hyperlink for checkout
- Notifications + analytics per CFA account
- Downloadable invoices on both TCAMS and TANCIS UIs
- Favicon + TCAMS logo branding
- Render.com ready (`server = app.server`)

## Test logins

| User | Password | Company | Declarant TIN |
|------|----------|---------|---------------|
| Martin | Martin123 | Martin Logistics | 1235678 |
| Joshua | Joshua123 | Joshua Logistics | 1235679 |
| Kevin | Kevin123 | Kevin Logistics | 1235670 |
| Yohana | Yohana123 | Yohana Logistics | 1235677 |

## Fee engine (GN No. 83 / 2026)

Minimum agency fees follow the **Tanzania Shipping Agencies (Fees for Clearing and Forwarding Services) Order, 2026** schedule (USD equivalents), converted to TZS:

```bash
GN83_USD_TZS_RATE=2500   # BoT / operational FX rate
```

| Example (import / sea) | Schedule | Calculation |
|------------------------|----------|-------------|
| 20-ft container | USD 150 / container | × qty × FX |
| 40-ft container | USD 200 / container | × qty × FX |
| Dry bulk | USD 0.60 / MT | gross weight → MT × rate × FX |
| Bulk liquid | USD 0.60 / MT | gross weight → MT × rate × FX |
| Motor vehicle | USD 130 / unit | × units × FX |
| LCL / loose cargo | USD 90 / BL | × FX |

Transit and road/air tables are also applied from `route_type` and `transport_mode` on the 080 payload.

**Full settlement**

`standard_minimum + 10% of standard_minimum + 18% of (standard_minimum + 10% of standard_minimum)`

**Service fee only** when TANCIS sends an exempt `message_info.status` on IF-E-CLR-018, or when the declarant TIN is listed as in-house:

`10% of standard_minimum + 18% of (10% of standard_minimum)`

```bash
GN83_EXEMPT_STATUSES=exempt,exempted,exemption
INHOUSE_CLEARER_TINS=111111111,222222222
```

TCAMS does **not** infer exemption from cargo description — only the status field on the inbound consignment payload.

Unknown declarant TINs are still processed and filed with lineage for operations follow-up.

## CapitalPay checkout

On invoice generation TCAMS:

1. Creates a CapitalPay invoice via the live API
2. Stores signed checkout parameters in SQLite
3. Embeds `{BASE_URL}/go/{checkout_id}` in the **QR code** and prints it on the invoice HTML

Opening `/go/{checkout_id}` posts to CapitalPay and renders the checkout form. `/paymentlink/{invoice_no}` redirects to the same session.

Configure in `.env`:

```bash
CAPITALPAY_API_KEY=...
CAPITALPAY_API_SECRET=...
CAPITALPAY_API_CLIENT_ID=3
CAPITALPAY_SERVICE_ID=134
CAPITALPAY_CALLBACK_URL=https://your-host/payment/success
CAPITALPAY_NOTIFICATION_URL=https://your-host/payment/notify
```

If CapitalPay credentials are missing, invoices fall back to the local `/paymentlink/{invoice_no}` stub.

## Local run

```bash
cd tcams-tancis-gn83
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:8050`

1. Login as Martin
2. Click **Enter TANCIS UI**
3. Click **Simulate Consignment Payload**
4. View/download the invoice returned to TANCIS
5. Switch to **TCAMS Desk** for notifications, analytics, and invoice history

## API

`POST /api/v1/webhooks/tancis/consignments` — IF-E-CLR-018 Consignment Information (legacy IF-I-CLR-080).

`POST /api/v1/webhooks/tancis/consignment-notes-status` — IF-E-CLR-022 Consignment notes status information (legacy IF-I-CLR-067 Consignment cancellation). Listens for `CL005` / `CL006` on `message_info.status`.

## Render.com deploy

1. Push this folder to a GitHub repo
2. Create a new **Web Service** on Render and connect the repo
3. Runtime: Python
4. Build: `pip install -r requirements.txt`
5. Start: `gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
6. Set env vars:
   - `SECRET_KEY` (auto or custom)
   - `BASE_URL` = your Render URL, e.g. `https://tcams-tancis-gn83.onrender.com`
   - optional `INHOUSE_CLEARER_TINS`

`render.yaml` and `Procfile` are included.

**Note:** Free Render disks are ephemeral. SQLite resets on redeploy unless you attach a persistent disk to `/opt/render/project/src/data`.
