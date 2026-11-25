"""Manajemen koneksi SQLite dan inisialisasi skema database ExTra."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from backend.config import get_database_path

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL,
    item_name TEXT NOT NULL CHECK (length(trim(item_name)) > 0),
    price INTEGER NOT NULL CHECK (price >= 0),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions(transaction_date);

CREATE INDEX IF NOT EXISTS idx_transaction_items_transaction_id
    ON transaction_items(transaction_id);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Buka koneksi SQLite dengan Row factory dan PRAGMA foreign_keys = ON."""
    resolved_path = str(db_path) if db_path is not None else get_database_path()
    is_uri = resolved_path.startswith("file:")
    conn = sqlite3.connect(resolved_path, uri=is_uri)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_transaction(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager transaksi SQLite atomik yang otomatis commit/rollback & close."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Inisialisasi tabel transactions, transaction_items, beserta index terkait."""
    with db_transaction(db_path) as conn:
        conn.executescript(_SCHEMA_SQL)
        conn.execute("PRAGMA foreign_keys = ON;")
