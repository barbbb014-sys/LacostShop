import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("lacostshop.sqlite3")

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            stars_amount INTEGER NOT NULL,
            price_rub INTEGER NOT NULL,
            price_xtr INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            charge_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)

def create_order(user_id, username, stars_amount, price_rub, price_xtr):
    with connect() as con:
        cur = con.execute(
            """INSERT INTO orders
            (user_id, username, stars_amount, price_rub, price_xtr)
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, stars_amount, price_rub, price_xtr)
        )
        return cur.lastrowid

def set_order_paid(order_id, charge_id):
    with connect() as con:
        con.execute(
            "UPDATE orders SET status='paid_waiting_fulfillment', charge_id=? WHERE id=?",
            (charge_id, order_id)
        )

def get_user_orders(user_id):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
