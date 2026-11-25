"""Layanan CRUD SQLite, pencarian, dan filter riwayat transaksi ExTra."""

from pathlib import Path
import sqlite3

from backend.database import db_transaction, get_connection
from backend.schemas.transaction import (
    ItemUpdateRequest,
    TransactionCreatedData,
    TransactionCreateRequest,
    TransactionItemRecord,
)


def _row_to_item_record(row: sqlite3.Row) -> TransactionItemRecord:
    """Konversi baris hasil join SQLite ke skema TransactionItemRecord."""
    return TransactionItemRecord(
        id=int(row["id"]),
        transaction_id=int(row["transaction_id"]),
        date=str(row["date"]),
        name=str(row["name"]),
        price=int(row["price"]),
        created_at=str(row["created_at"]),
    )


def _escape_like_pattern(term: str) -> str:
    """Escape karakter wildcard SQL LIKE agar pencarian substring presisi."""
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def create_transaction(
    payload: TransactionCreateRequest,
    db_path: str | Path | None = None,
) -> TransactionCreatedData:
    """Simpan header transactions dan seluruh transaction_items secara atomik."""
    with db_transaction(db_path) as conn:
        header_cursor = conn.execute(
            "INSERT INTO transactions (transaction_date) VALUES (?)",
            (payload.date,),
        )
        transaction_id = int(header_cursor.lastrowid)

        conn.executemany(
            """
            INSERT INTO transaction_items (transaction_id, item_name, price)
            VALUES (?, ?, ?)
            """,
            [(transaction_id, item.name, item.price) for item in payload.items],
        )

        tx_row = conn.execute(
            "SELECT id, transaction_date, created_at FROM transactions WHERE id = ?",
            (transaction_id,),
        ).fetchone()

        item_rows = conn.execute(
            """
            SELECT
                ti.id AS id,
                ti.transaction_id AS transaction_id,
                t.transaction_date AS date,
                ti.item_name AS name,
                ti.price AS price,
                t.created_at AS created_at
            FROM transaction_items ti
            JOIN transactions t ON t.id = ti.transaction_id
            WHERE ti.transaction_id = ?
            ORDER BY ti.id ASC
            """,
            (transaction_id,),
        ).fetchall()

    return TransactionCreatedData(
        transaction_id=int(tx_row["id"]),
        date=str(tx_row["transaction_date"]),
        created_at=str(tx_row["created_at"]),
        items=[_row_to_item_record(row) for row in item_rows],
    )


def get_transactions(
    month: int | None = None,
    year: int | None = None,
    search: str | None = None,
    db_path: str | Path | None = None,
) -> list[TransactionItemRecord]:
    """Ambil daftar item transaksi dengan filter opsional month, year, dan search."""
    if month is not None and (isinstance(month, bool) or not 1 <= month <= 12):
        raise ValueError("Parameter month harus bernilai antara 1 hingga 12.")
    if year is not None and (isinstance(year, bool) or not 1000 <= year <= 9999):
        raise ValueError("Parameter year harus berupa tahun 4 digit (1000-9999).")

    conditions: list[str] = []
    params: list[object] = []

    if year is not None and month is not None:
        conditions.append("t.transaction_date >= ? AND t.transaction_date <= ?")
        params.extend([f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-31"])
    elif year is not None:
        conditions.append("t.transaction_date >= ? AND t.transaction_date <= ?")
        params.extend([f"{year:04d}-01-01", f"{year:04d}-12-31"])
    elif month is not None:
        conditions.append("substr(t.transaction_date, 6, 2) = ?")
        params.append(f"{month:02d}")

    if search is not None and search.strip():
        escaped = _escape_like_pattern(search.strip().lower())
        conditions.append("LOWER(ti.item_name) LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT
            ti.id AS id,
            ti.transaction_id AS transaction_id,
            t.transaction_date AS date,
            ti.item_name AS name,
            ti.price AS price,
            t.created_at AS created_at
        FROM transaction_items ti
        JOIN transactions t ON t.id = ti.transaction_id
        {where_clause}
        ORDER BY t.transaction_date DESC, ti.id DESC
    """

    conn = get_connection(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return [_row_to_item_record(row) for row in rows]


def update_item(
    item_id: int,
    payload: ItemUpdateRequest,
    db_path: str | Path | None = None,
) -> TransactionItemRecord | None:
    """Perbarui nama, harga, dan/atau tanggal transaksi sebuah item.

    Jika tanggal diubah pada item dalam transaksi multi-item, item dipindahkan ke
    record transactions baru agar tanggal item lain pada transaksi asal tetap utuh.
    """
    with db_transaction(db_path) as conn:
        existing = conn.execute(
            """
            SELECT
                ti.id AS id,
                ti.transaction_id AS transaction_id,
                ti.item_name AS item_name,
                ti.price AS price,
                t.transaction_date AS transaction_date
            FROM transaction_items ti
            JOIN transactions t ON t.id = ti.transaction_id
            WHERE ti.id = ?
            """,
            (item_id,),
        ).fetchone()

        if existing is None:
            return None

        current_tx_id = int(existing["transaction_id"])
        target_tx_id = current_tx_id
        new_name = payload.name if payload.name is not None else str(existing["item_name"])
        new_price = payload.price if payload.price is not None else int(existing["price"])

        if payload.date is not None and payload.date != str(existing["transaction_date"]):
            count_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM transaction_items WHERE transaction_id = ?",
                (current_tx_id,),
            ).fetchone()
            sibling_count = int(count_row["cnt"])

            if sibling_count > 1:
                new_tx_cursor = conn.execute(
                    "INSERT INTO transactions (transaction_date) VALUES (?)",
                    (payload.date,),
                )
                target_tx_id = int(new_tx_cursor.lastrowid)
            else:
                conn.execute(
                    "UPDATE transactions SET transaction_date = ? WHERE id = ?",
                    (payload.date, current_tx_id),
                )

        conn.execute(
            """
            UPDATE transaction_items
            SET transaction_id = ?, item_name = ?, price = ?
            WHERE id = ?
            """,
            (target_tx_id, new_name, new_price, item_id),
        )

        updated_row = conn.execute(
            """
            SELECT
                ti.id AS id,
                ti.transaction_id AS transaction_id,
                t.transaction_date AS date,
                ti.item_name AS name,
                ti.price AS price,
                t.created_at AS created_at
            FROM transaction_items ti
            JOIN transactions t ON t.id = ti.transaction_id
            WHERE ti.id = ?
            """,
            (item_id,),
        ).fetchone()

    return _row_to_item_record(updated_row)


def delete_item(
    item_id: int,
    db_path: str | Path | None = None,
) -> dict[str, int | bool] | None:
    """Hapus satu item berdasarkan item_id dan bersihkan transaksi yatim (orphan cleanup)."""
    with db_transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT id, transaction_id FROM transaction_items WHERE id = ?",
            (item_id,),
        ).fetchone()

        if existing is None:
            return None

        tx_id = int(existing["transaction_id"])
        conn.execute("DELETE FROM transaction_items WHERE id = ?", (item_id,))

        remaining_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM transaction_items WHERE transaction_id = ?",
            (tx_id,),
        ).fetchone()

        orphan_deleted = False
        if int(remaining_row["cnt"]) == 0:
            conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
            orphan_deleted = True

    return {
        "deleted_item_id": item_id,
        "transaction_id": tx_id,
        "orphan_transaction_deleted": orphan_deleted,
    }


def delete_transaction(
    transaction_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Hapus transaksi beserta seluruh item terkait via ON DELETE CASCADE."""
    with db_transaction(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM transactions WHERE id = ?",
            (transaction_id,),
        )
        return cursor.rowcount > 0
