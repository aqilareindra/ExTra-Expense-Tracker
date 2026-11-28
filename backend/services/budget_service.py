"""Layanan CRUD pemasukan (incomes) dan pengelolaan anggaran bulanan per kategori (budgets)."""

from pathlib import Path

from sqlalchemy import func, select

from backend.database import (
    Budget,
    Income,
    Transaction,
    TransactionItem,
    session_scope,
)
from backend.schemas.budget import (
    BudgetListResponse,
    BudgetStatus,
    BudgetStatusItem,
    BudgetUpsert,
    IncomeCreate,
    IncomeListResponse,
    IncomeRecord,
)


def _validate_user_id(user_id: int) -> int:
    """Pastikan user_id bertipe integer positif."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError("user_id harus berupa integer positif.")
    return user_id


def _validate_period_params(month: int | None, year: int | None) -> None:
    """Validasi parameter bulan dan tahun opsional."""
    if month is not None and (isinstance(month, bool) or not 1 <= month <= 12):
        raise ValueError("Parameter month harus bernilai antara 1 hingga 12.")
    if year is not None and (isinstance(year, bool) or not 1000 <= year <= 9999):
        raise ValueError("Parameter year harus berupa tahun 4 digit (1000-9999).")


def compute_budget_metrics(
    limit_amount: int,
    spent_amount: int,
) -> tuple[int, float, BudgetStatus]:
    """Hitung sisa anggaran, persentase pemakaian, dan status secara deterministik."""
    remaining_amount = limit_amount - spent_amount
    if limit_amount == 0:
        if spent_amount == 0:
            return remaining_amount, 0.0, "safe"
        return remaining_amount, 100.0, "over_budget"

    usage_percentage = round((spent_amount / limit_amount) * 100.0, 2)
    if spent_amount > limit_amount:
        status: BudgetStatus = "over_budget"
    elif spent_amount * 100 >= limit_amount * 80:
        status = "warning"
    else:
        status = "safe"

    return remaining_amount, usage_percentage, status


def _orm_to_income_record(income: Income) -> IncomeRecord:
    """Konversi ORM Income ke skema IncomeRecord."""
    return IncomeRecord(
        id=int(income.id),
        income_date=str(income.income_date),
        source_name=str(income.source_name),
        amount=int(income.amount),
        created_at=str(income.created_at),
    )


def create_income(
    payload: IncomeCreate,
    user_id: int,
    db_path: str | Path | None = None,
) -> IncomeRecord:
    """Simpan catatan pemasukan baru milik user_id."""
    owner_id = _validate_user_id(user_id)
    with session_scope(db_path) as session:
        new_income = Income(
            user_id=owner_id,
            income_date=payload.income_date,
            source_name=payload.source_name,
            amount=payload.amount,
        )
        session.add(new_income)
        session.flush()
        session.refresh(new_income)
        return _orm_to_income_record(new_income)


def get_incomes(
    user_id: int,
    month: int | None = None,
    year: int | None = None,
    db_path: str | Path | None = None,
) -> IncomeListResponse:
    """Ambil daftar pemasukan milik user_id dengan filter opsional month & year."""
    owner_id = _validate_user_id(user_id)
    _validate_period_params(month, year)

    stmt = select(Income).where(Income.user_id == owner_id)
    if year is not None and month is not None:
        stmt = stmt.where(
            Income.income_date >= f"{year:04d}-{month:02d}-01",
            Income.income_date <= f"{year:04d}-{month:02d}-31",
        )
    elif year is not None:
        stmt = stmt.where(
            Income.income_date >= f"{year:04d}-01-01",
            Income.income_date <= f"{year:04d}-12-31",
        )
    elif month is not None:
        stmt = stmt.where(func.substr(Income.income_date, 6, 2) == f"{month:02d}")

    stmt = stmt.order_by(Income.income_date.desc(), Income.id.desc())

    with session_scope(db_path) as session:
        rows = session.scalars(stmt).all()
        records = [_orm_to_income_record(row) for row in rows]

    total_income = sum(item.amount for item in records)
    return IncomeListResponse(
        status="success",
        count=len(records),
        total_income=total_income,
        data=records,
    )


def count_monthly_incomes(
    month: int,
    year: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> int:
    """Hitung jumlah baris pemasukan milik user_id pada bulan dan tahun tertentu."""
    owner_id = _validate_user_id(user_id)
    _validate_period_params(month, year)
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-31"

    with session_scope(db_path) as session:
        count = session.scalar(
            select(func.count(Income.id)).where(
                Income.user_id == owner_id,
                Income.income_date >= start_date,
                Income.income_date <= end_date,
            )
        )
        return int(count or 0)


def delete_income(
    income_id: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Hapus catatan pemasukan milik user_id (kembalikan False jika tidak ditemukan)."""
    owner_id = _validate_user_id(user_id)
    with session_scope(db_path) as session:
        row = session.scalar(
            select(Income).where(
                Income.id == income_id,
                Income.user_id == owner_id,
            )
        )
        if row is None:
            return False
        session.delete(row)
        return True


def _build_budget_status_item(budget: Budget, spent_amount: int) -> BudgetStatusItem:
    """Konversi ORM Budget dan total realisasi pengeluaran menjadi BudgetStatusItem."""
    limit_amount = int(budget.limit_amount)
    remaining_amount, usage_percentage, status = compute_budget_metrics(
        limit_amount=limit_amount,
        spent_amount=spent_amount,
    )
    return BudgetStatusItem(
        id=int(budget.id),
        month=int(budget.month),
        year=int(budget.year),
        category=str(budget.category),
        limit_amount=limit_amount,
        spent_amount=spent_amount,
        remaining_amount=remaining_amount,
        usage_percentage=usage_percentage,
        status=status,
    )


def upsert_budget(
    payload: BudgetUpsert,
    user_id: int,
    db_path: str | Path | None = None,
) -> BudgetStatusItem:
    """Simpan atau perbarui batas anggaran untuk kombinasi (user_id, month, year, category)."""
    owner_id = _validate_user_id(user_id)
    start_date = f"{payload.year:04d}-{payload.month:02d}-01"
    end_date = f"{payload.year:04d}-{payload.month:02d}-31"

    with session_scope(db_path) as session:
        existing = session.scalar(
            select(Budget).where(
                Budget.user_id == owner_id,
                Budget.month == payload.month,
                Budget.year == payload.year,
                Budget.category == payload.category,
            )
        )
        if existing is not None:
            existing.limit_amount = payload.limit_amount
            budget_row = existing
        else:
            budget_row = Budget(
                user_id=owner_id,
                month=payload.month,
                year=payload.year,
                category=payload.category,
                limit_amount=payload.limit_amount,
            )
            session.add(budget_row)

        session.flush()
        session.refresh(budget_row)

        spent_amount = int(
            session.scalar(
                select(func.coalesce(func.sum(TransactionItem.price), 0))
                .join(Transaction, Transaction.id == TransactionItem.transaction_id)
                .where(
                    Transaction.user_id == owner_id,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    TransactionItem.category == payload.category,
                )
            )
            or 0
        )
        return _build_budget_status_item(budget_row, spent_amount)


def get_budgets(
    month: int,
    year: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> BudgetListResponse:
    """Ambil daftar anggaran milik user_id beserta realisasi pengeluaran deterministik per kategori."""
    owner_id = _validate_user_id(user_id)
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Parameter month harus berupa integer antara 1 hingga 12.")
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        raise ValueError("Parameter year harus berupa integer tahun 4 digit.")

    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-31"

    with session_scope(db_path) as session:
        budget_rows = session.scalars(
            select(Budget)
            .where(
                Budget.user_id == owner_id,
                Budget.month == month,
                Budget.year == year,
            )
            .order_by(Budget.category.asc())
        ).all()

        spent_rows = session.execute(
            select(
                TransactionItem.category.label("category"),
                func.coalesce(func.sum(TransactionItem.price), 0).label("spent_total"),
            )
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.user_id == owner_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(TransactionItem.category)
        ).all()

    spent_by_category = {str(r.category): int(r.spent_total) for r in spent_rows}

    items = [
        _build_budget_status_item(
            budget_row,
            spent_by_category.get(str(budget_row.category), 0),
        )
        for budget_row in budget_rows
    ]
    items.sort(key=lambda item: (-item.usage_percentage, item.category))

    total_budget = sum(item.limit_amount for item in items)
    total_spent = sum(item.spent_amount for item in items)
    total_remaining = total_budget - total_spent

    return BudgetListResponse(
        status="success",
        month=month,
        year=year,
        total_budget=total_budget,
        total_spent=total_spent,
        total_remaining=total_remaining,
        data=items,
    )


def delete_budget(
    budget_id: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Hapus satu aturan anggaran milik user_id (kembalikan False jika tidak ditemukan)."""
    owner_id = _validate_user_id(user_id)
    with session_scope(db_path) as session:
        row = session.scalar(
            select(Budget).where(
                Budget.id == budget_id,
                Budget.user_id == owner_id,
            )
        )
        if row is None:
            return False
        session.delete(row)
        return True
