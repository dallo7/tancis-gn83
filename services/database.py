import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from services.config import DATABASE_PATH

SEED_CFAS = [
    {
        "username": "Martin",
        "password": "Martin123",
        "company_name": "Martin Logistics",
        "declarant_tin": "1235678",
        "email": "martin@martinlogistics.tz",
        "phone": "+255700000001",
    },
    {
        "username": "Joshua",
        "password": "Joshua123",
        "company_name": "Joshua Logistics",
        "declarant_tin": "1235679",
        "email": "joshua@joshualogistics.tz",
        "phone": "+255700000002",
    },
    {
        "username": "Kevin",
        "password": "Kevin123",
        "company_name": "Kevin Logistics",
        "declarant_tin": "1235670",
        "email": "kevin@kevinlogistics.tz",
        "phone": "+255700000003",
    },
    {
        "username": "Yohana",
        "password": "Yohana123",
        "company_name": "Yohana Logistics",
        "declarant_tin": "1235677",
        "email": "yohana@yohanalogistics.tz",
        "phone": "+255700000004",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                company_name TEXT NOT NULL,
                declarant_tin TEXT UNIQUE NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT,
                reference_number TEXT,
                tansad_no TEXT NOT NULL,
                declarant_tin TEXT NOT NULL,
                user_id INTEGER,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                lineage_note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT UNIQUE NOT NULL,
                suc_number TEXT NOT NULL,
                tansad_no TEXT NOT NULL,
                declarant_tin TEXT NOT NULL,
                user_id INTEGER,
                consignment_id INTEGER,
                invoice_type TEXT NOT NULL,
                fee_mode TEXT NOT NULL,
                standard_minimum REAL NOT NULL,
                service_fee REAL NOT NULL,
                vat_amount REAL NOT NULL,
                total_due REAL NOT NULL,
                currency TEXT NOT NULL,
                cargo_category TEXT,
                payment_link TEXT NOT NULL,
                invoice_path TEXT NOT NULL,
                html_path TEXT NOT NULL,
                qr_path TEXT,
                pushed_to_tancis INTEGER NOT NULL DEFAULT 0,
                tancis_result_code TEXT,
                tancis_payload_json TEXT,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(consignment_id) REFERENCES consignments(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                related_invoice_no TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS message_exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                declarant_tin TEXT,
                tansad_no TEXT,
                invoice_no TEXT,
                summary TEXT,
                exchange_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS capitalpay_checkouts (
                checkout_id TEXT PRIMARY KEY,
                invoice_no TEXT NOT NULL,
                capitalpay_invoice_ref TEXT,
                params_json TEXT NOT NULL,
                api_response_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_capitalpay_checkouts_invoice
                ON capitalpay_checkouts(invoice_no);
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if existing == 0:
            for cfa in SEED_CFAS:
                conn.execute(
                    """
                    INSERT INTO users
                    (username, password_hash, company_name, declarant_tin, email, phone, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cfa["username"],
                        generate_password_hash(cfa["password"]),
                        cfa["company_name"],
                        cfa["declarant_tin"],
                        cfa["email"],
                        cfa["phone"],
                        _now(),
                    ),
                )


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        return dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_tin(tin: str) -> Optional[Dict[str, Any]]:
    cleaned = (tin or "").replace("-", "").strip()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
        for row in rows:
            if row["declarant_tin"].replace("-", "").strip() == cleaned:
                return dict(row)
        return None


def insert_consignment(
    *,
    transaction_id: str,
    reference_number: str,
    tansad_no: str,
    declarant_tin: str,
    user_id: Optional[int],
    payload: Dict[str, Any],
    status: str,
    lineage_note: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO consignments
            (transaction_id, reference_number, tansad_no, declarant_tin, user_id,
             payload_json, status, lineage_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                reference_number,
                tansad_no,
                declarant_tin,
                user_id,
                json.dumps(payload),
                status,
                lineage_note,
                _now(),
            ),
        )
        return cur.lastrowid


def insert_invoice(data: Dict[str, Any]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoices
            (invoice_no, suc_number, tansad_no, declarant_tin, user_id, consignment_id,
             invoice_type, fee_mode, standard_minimum, service_fee, vat_amount, total_due,
             currency, cargo_category, payment_link, invoice_path, html_path, qr_path,
             pushed_to_tancis, tancis_result_code, tancis_payload_json, issue_date,
             due_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["invoice_no"],
                data["suc_number"],
                data["tansad_no"],
                data["declarant_tin"],
                data.get("user_id"),
                data.get("consignment_id"),
                data["invoice_type"],
                data["fee_mode"],
                data["standard_minimum"],
                data["service_fee"],
                data["vat_amount"],
                data["total_due"],
                data["currency"],
                data.get("cargo_category"),
                data["payment_link"],
                data["invoice_path"],
                data["html_path"],
                data.get("qr_path"),
                1 if data.get("pushed_to_tancis") else 0,
                data.get("tancis_result_code"),
                json.dumps(data.get("tancis_payload") or {}),
                data["issue_date"],
                data["due_date"],
                _now(),
            ),
        )
        return cur.lastrowid


def add_notification(
    user_id: int,
    kind: str,
    title: str,
    body: str,
    related_invoice_no: Optional[str] = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO notifications
            (user_id, kind, title, body, related_invoice_no, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (user_id, kind, title, body, related_invoice_no, _now()),
        )


def get_notifications(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def unread_count(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
        return int(row["c"])


def mark_notifications_read(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
            (user_id,),
        )


def get_invoices_for_user(user_id: int) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM invoices
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_invoice_by_no(invoice_no: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invoices WHERE invoice_no = ?", (invoice_no,)
        ).fetchone()
        return dict(row) if row else None


def get_latest_invoice_for_tin(tin: str) -> Optional[Dict[str, Any]]:
    cleaned = (tin or "").replace("-", "").strip()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invoices ORDER BY id DESC"
        ).fetchall()
        for row in rows:
            if row["declarant_tin"].replace("-", "").strip() == cleaned:
                return dict(row)
        return None


def analytics_for_user(user_id: int) -> Dict[str, Any]:
    with get_conn() as conn:
        inv = conn.execute(
            """
            SELECT
              COUNT(*) AS total_invoices,
              COALESCE(SUM(total_due), 0) AS total_amount,
              COALESCE(SUM(CASE WHEN pushed_to_tancis = 1 THEN 1 ELSE 0 END), 0) AS pushed_count,
              COALESCE(SUM(CASE WHEN fee_mode = 'FULL' THEN 1 ELSE 0 END), 0) AS full_count,
              COALESCE(SUM(CASE WHEN fee_mode = 'SERVICE' THEN 1 ELSE 0 END), 0) AS service_count
            FROM invoices
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        cons = conn.execute(
            "SELECT COUNT(*) AS c FROM consignments WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return {
            "total_invoices": inv["total_invoices"],
            "total_amount": inv["total_amount"],
            "pushed_count": inv["pushed_count"],
            "full_count": inv["full_count"],
            "service_count": inv["service_count"],
            "consignments": cons["c"],
        }


def recent_consignments(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM consignments
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def insert_message_exchange(
    *,
    user_id: Optional[int],
    declarant_tin: str,
    tansad_no: str,
    invoice_no: Optional[str],
    summary: str,
    exchange: Dict[str, Any],
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO message_exchanges
            (user_id, declarant_tin, tansad_no, invoice_no, summary, exchange_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                declarant_tin,
                tansad_no,
                invoice_no,
                summary,
                json.dumps(exchange),
                _now(),
            ),
        )
        return cur.lastrowid


def get_latest_exchange_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM message_exchanges
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["exchange"] = json.loads(data["exchange_json"])
        return data


def get_exchange_by_id(exchange_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM message_exchanges WHERE id = ?",
            (exchange_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["exchange"] = json.loads(data["exchange_json"])
        return data


def list_exchanges_for_user(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, tansad_no, invoice_no, summary, created_at
            FROM message_exchanges
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def save_checkout_session(
    *,
    checkout_id: str,
    invoice_no: str,
    params: Dict[str, Any],
    capitalpay_invoice_ref: str = "",
    api_response: Optional[Dict[str, Any]] = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO capitalpay_checkouts
            (checkout_id, invoice_no, capitalpay_invoice_ref, params_json,
             api_response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                checkout_id,
                invoice_no,
                capitalpay_invoice_ref,
                json.dumps(params),
                json.dumps(api_response or {}),
                _now(),
            ),
        )


def get_checkout_session(checkout_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM capitalpay_checkouts WHERE checkout_id = ?",
            (checkout_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["params"] = json.loads(data["params_json"])
        data["api_response"] = json.loads(data["api_response_json"] or "{}")
        return data


def get_checkout_by_invoice(invoice_no: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM capitalpay_checkouts
            WHERE invoice_no = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (invoice_no,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["params"] = json.loads(data["params_json"])
        data["api_response"] = json.loads(data["api_response_json"] or "{}")
        return data