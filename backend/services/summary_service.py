"""Layanan kalkulasi deterministik ringkasan pengeluaran bulanan (SQLite & PostgreSQL)."""

from pathlib import Path

from sqlalchemy import func, select

from backend.database import Transaction, TransactionItem, session_scope
from backend.schemas.summary import (
    CategoryExpenseBreakdown,
    DailyExpenseBreakdown,
    MonthlySummaryResponse,
)


def get_monthly_summary(
    month: int,
    year: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> MonthlySummaryResponse:
    """Hitung total pengeluaran, jumlah barang, agregasi harian, dan kategori khusus milik user_id."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError("user_id harus berupa integer positif.")
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Parameter month harus berupa integer antara 1 hingga 12.")
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        raise ValueError("Parameter year harus berupa integer tahun 4 digit.")

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-31"

    daily_total_expr = func.coalesce(func.sum(TransactionItem.price), 0)
    category_total_expr = func.coalesce(func.sum(TransactionItem.price), 0)

    with session_scope(db_path) as session:
        daily_rows = session.execute(
            select(
                Transaction.transaction_date.label("date"),
                daily_total_expr.label("daily_total"),
                func.count(TransactionItem.id).label("daily_item_count"),
            )
            .join(TransactionItem, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.transaction_date)
            .order_by(Transaction.transaction_date.asc())
        ).all()

        category_rows = session.execute(
            select(
                TransactionItem.category.label("category"),
                category_total_expr.label("category_total"),
                func.count(TransactionItem.id).label("category_item_count"),
            )
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(TransactionItem.category)
            .order_by(category_total_expr.desc(), TransactionItem.category.asc())
        ).all()

    daily_breakdown = [
        DailyExpenseBreakdown(
            date=str(row.date),
            total=int(row.daily_total),
            item_count=int(row.daily_item_count),
        )
        for row in daily_rows
    ]

    category_breakdown = [
        CategoryExpenseBreakdown(
            category=str(row.category),
            total=int(row.category_total),
            item_count=int(row.category_item_count),
        )
        for row in category_rows
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
        category_breakdown=category_breakdown,
    )
