import sqlite3
from datetime import datetime
from app.config import Config

def get_conn():
    conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # 待審批與已執行訂單表（含 order_uuid 防重複落單）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_uuid TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            limit_price REAL NOT NULL,
            ai_reason TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            broker_order_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # 風控攔截與操作審計日誌
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            symbol TEXT,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def log_audit(event_type: str, detail: str, symbol: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_logs (event_type, symbol, detail, created_at) VALUES (?, ?, ?, ?)",
        (event_type, symbol, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def create_pending_order(order_uuid: str, symbol: str, action: str, quantity: int, limit_price: float, ai_reason: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        """INSERT INTO orders (order_uuid, symbol, action, quantity, limit_price, ai_reason, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)""",
        (order_uuid, symbol.upper(), action.upper(), quantity, limit_price, ai_reason, now, now)
    )
    conn.commit()
    conn.close()
    log_audit("SIGNAL_CREATED", f"建立待審批 {action} {quantity} 股 @ ${limit_price:.2f}", symbol)

def get_orders(status: str = None):
    conn = get_conn()
    if status:
        rows = conn.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_order_status(order_uuid: str, status: str, broker_order_id: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status = ?, broker_order_id = ?, updated_at = ? WHERE order_uuid = ?",
        (status, broker_order_id, now, order_uuid)
    )
    conn.commit()
    conn.close()

def is_order_already_processed(order_uuid: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT status FROM orders WHERE order_uuid = ?", (order_uuid,)).fetchone()
    conn.close()
    return row is not None and row["status"] in ("EXECUTED", "REJECTED")

def get_recent_audits(limit: int = 30):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]