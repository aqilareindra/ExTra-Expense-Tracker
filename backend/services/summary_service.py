"""Layanan kalkulasi deterministik ringkasan pengeluaran bulanan dari SQLite."""

from pathlib import Path

from backend.database import get_connection
from backend.schemas.summary import DailyExpenseBreakdown, MonthlySummaryResponse


def get_monthly_summary(
    month: int,
    year: int,
    db_path: str | Path | None = None,
) -> MonthlySummaryResponse:
    """Hitung total pengeluaran, jumlah barang, dan agregasi harian secara deterministik."""
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Parameter month harus berupa integer antara 1 hingga 12.")
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        raise ValueError("Parameter year harus berupa integer tahun 4 digit.")

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-31"

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                t.transaction_date AS date,
                COALESCE(SUM(ti.price), 0) AS daily_total,
                COUNT(ti.id) AS daily_item_count
            FROM transactions t
            JOIN transaction_items ti ON ti.transaction_id = t.id
            WHERE t.transaction_date >= ? AND t.transaction_date <= ?
            GROUP BY t.transaction_date
            ORDER BY t.transaction_date ASC
            """,
            (start_date, end_date),
        ).fetchall()
    finally:
        conn.close()

    daily_breakdown = [
        DailyExpenseBreakdown(
            date=str(row["date"]),
            total=int(row["daily_total"]),
            item_count=int(row["daily_item_count"]),
        )
        for row in rows
    ]

    total_expense = sum(entry.total for entry in daily_breakdown)
    total_items = sum(entry.item_count for entry in daily_breakdown)

    return MonthlySummaryResponse(
        status="success",
        month=month,
        year=year,
        total_expense=total_expense,
        total_items=total_items,
        daily_breakdown=daily_breakdown,
    )
