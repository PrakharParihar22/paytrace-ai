import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "paytrace.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def init_db():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merchant_orders (
            id TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            receipt TEXT,
            merchant_state TEXT NOT NULL,
            payment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            payment_id TEXT,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT,
            message TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_order
        ON payment_events(order_id)
    """)

    connection.commit()
    connection.close()