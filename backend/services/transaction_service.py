"""Layanan CRUD SQLAlchemy (SQLite & PostgreSQL), filter riwayat, dan isolasi arsip struk ExTra."""

from pathlib import Path

from sqlalchemy import func, select

from backend.database import Transaction, TransactionItem, session_scope
from backend.schemas.categories import validate_strict_category
from backend.schemas.transaction import (
    ItemUpdateRequest,
    TransactionCreatedData,
    TransactionCreateRequest,
    TransactionItemRecord,
)
from backend.services import image_service


def _validate_user_id(user_id: int) -> int:
    """Pastikan user_id bertipe integer positif."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError("user_id harus berupa integer positif.")
    return user_id


def _has_receipt_flag(receipt_image_path: str | None) -> bool:
    """Konversi path arsip struk menjadi boolean has_receipt tanpa membocorkan path."""
    return bool(isinstance(receipt_image_path, str) and receipt_image_path.strip())


def _orm_to_item_record(
    item: TransactionItem,
    tx: Transaction,
) -> TransactionItemRecord:
    """Konversi pasangan model ORM TransactionItem & Transaction ke skema TransactionItemRecord."""
    return TransactionItemRecord(
        id=int(item.id),
        transaction_id=int(item.transaction_id),
        date=str(tx.transaction_date),
        name=str(item.item_name),
        category=str(item.category),
        price=int(item.price),
        has_receipt=_has_receipt_flag(tx.receipt_image_path),
        created_at=str(tx.created_at),
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
    user_id: int,
    db_path: str | Path | None = None,
) -> TransactionCreatedData:
    """Simpan header transactions, transaction_items, serta arsip foto struk milik user_id."""
    owner_id = _validate_user_id(user_id)
    archived_filename: str | None = None
    if payload.temp_image_token is not None:
        archived_filename = image_service.promote_temp_receipt_to_archive(
            payload.temp_image_token,
            user_id=owner_id,
        )

    try:
        with session_scope(db_path) as session:
            new_tx = Transaction(
                user_id=owner_id,
                transaction_date=payload.date,
                receipt_image_path=archived_filename,
            )
            new_tx.items = [
                TransactionItem(
                    item_name=item.name,
                    category=item.category,
                    price=item.price,
                )
                for item in payload.items
            ]
            session.add(new_tx)
            session.flush()
            session.refresh(new_tx)

            ordered_items = sorted(new_tx.items, key=lambda row: int(row.id))
            item_records = [_orm_to_item_record(item, new_tx) for item in ordered_items]
            return TransactionCreatedData(
                transaction_id=int(new_tx.id),
                date=str(new_tx.transaction_date),
                has_receipt=_has_receipt_flag(new_tx.receipt_image_path),
                created_at=str(new_tx.created_at),
                items=item_records,
            )
    except Exception:
        if archived_filename is not None:
            image_service.delete_archived_receipt_file(archived_filename)
        raise


def get_transactions(
    user_id: int,
    month: int | None = None,
    year: int | None = None,
    category: str | None = None,
    search: str | None = None,
    db_path: str | Path | None = None,
) -> list[TransactionItemRecord]:
    """Ambil daftar item transaksi milik user_id dengan filter opsional periode, kategori, dan search."""
    owner_id = _validate_user_id(user_id)
    if month is not None and (isinstance(month, bool) or not 1 <= month <= 12):
        raise ValueError("Parameter month harus bernilai antara 1 hingga 12.")
    if year is not None and (isinstance(year, bool) or not 1000 <= year <= 9999):
        raise ValueError("Parameter year harus berupa tahun 4 digit (1000-9999).")

    stmt = (
        select(TransactionItem, Transaction)
        .join(Transaction, Transaction.id == TransactionItem.transaction_id)
        .where(Transaction.user_id == owner_id)
    )

    if year is not None and month is not None:
        stmt = stmt.where(
            Transaction.transaction_date >= f"{year:04d}-{month:02d}-01",
            Transaction.transaction_date <= f"{year:04d}-{month:02d}-31",
        )
    elif year is not None:
        stmt = stmt.where(
            Transaction.transaction_date >= f"{year:04d}-01-01",
            Transaction.transaction_date <= f"{year:04d}-12-31",
        )
    elif month is not None:
        stmt = stmt.where(func.substr(Transaction.transaction_date, 6, 2) == f"{month:02d}")

    if category is not None and category.strip():
        validated_cat = validate_strict_category(category)
        stmt = stmt.where(TransactionItem.category == validated_cat)

    if search is not None and search.strip():
        escaped = _escape_like_pattern(search.strip().lower())
        stmt = stmt.where(
            func.lower(TransactionItem.item_name).like(f"%{escaped}%", escape="\\")
        )

    stmt = stmt.order_by(Transaction.transaction_date.desc(), TransactionItem.id.desc())

    with session_scope(db_path) as session:
        rows = session.execute(stmt).all()
        return [_orm_to_item_record(item, tx) for item, tx in rows]


def get_transaction_receipt_filename(
    transaction_id: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> str | None:
    """Ambil nama file arsip struk milik transaksi tertentu yang dimiliki user_id."""
    owner_id = _validate_user_id(user_id)
    with session_scope(db_path) as session:
        stored = session.scalar(
            select(Transaction.receipt_image_path).where(
                Transaction.id == transaction_id,
                Transaction.user_id == owner_id,
            )
        )
    if not isinstance(stored, str):
        return None
    trimmed = stored.strip()
    return trimmed or None


def update_item(
    item_id: int,
    payload: ItemUpdateRequest,
    user_id: int,
    db_path: str | Path | None = None,
) -> TransactionItemRecord | None:
    """Perbarui item milik user_id; pertahankan kepemilikan user_id jika transaksi dipecah."""
    owner_id = _validate_user_id(user_id)
    with session_scope(db_path) as session:
        row = session.execute(
            select(TransactionItem, Transaction)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                TransactionItem.id == item_id,
                Transaction.user_id == owner_id,
            )
        ).first()

        if row is None:
            return None

        item, current_tx = row
        if payload.name is not None:
            item.item_name = payload.name
        if payload.category is not None:
            item.category = payload.category
        if payload.price is not None:
            item.price = payload.price

        target_tx = current_tx
        if payload.date is not None and payload.date != str(current_tx.transaction_date):
            sibling_count = int(
                session.scalar(
                    select(func.count(TransactionItem.id)).where(
                        TransactionItem.transaction_id == current_tx.id
                    )
                )
                or 0
            )
            if sibling_count > 1:
                new_tx = Transaction(
                    user_id=owner_id,
                    transaction_date=payload.date,
                    receipt_image_path=None,
                )
                session.add(new_tx)
                session.flush()
                session.refresh(new_tx)
                item.transaction_id = int(new_tx.id)
                target_tx = new_tx
            else:
                current_tx.transaction_date = payload.date

        session.flush()
        return _orm_to_item_record(item, target_tx)


def delete_item(
    item_id: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> dict[str, int | bool] | None:
    """Hapus satu item milik user_id dan bersihkan transaksi yatim beserta file arsipnya."""
    owner_id = _validate_user_id(user_id)
    receipt_to_delete: str | None = None
    tx_id: int
    orphan_deleted = False

    with session_scope(db_path) as session:
        row = session.execute(
            select(TransactionItem, Transaction)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                TransactionItem.id == item_id,
                Transaction.user_id == owner_id,
            )
        ).first()

        if row is None:
            return None

        item, tx = row
        tx_id = int(tx.id)
        session.delete(item)
        session.flush()

        remaining = int(
            session.scalar(
                select(func.count(TransactionItem.id)).where(
                    TransactionItem.transaction_id == tx_id
                )
            )
            or 0
        )

        if remaining == 0:
            if isinstance(tx.receipt_image_path, str):
                receipt_to_delete = tx.receipt_image_path.strip() or None
            session.delete(tx)
            orphan_deleted = True

    if orphan_deleted and receipt_to_delete is not None:
        image_service.delete_archived_receipt_file(receipt_to_delete)

    return {
        "deleted_item_id": item_id,
        "transaction_id": tx_id,
        "orphan_transaction_deleted": orphan_deleted,
    }


def delete_transaction(
    transaction_id: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """Hapus transaksi milik user_id, seluruh item via CASCADE, dan arsip foto struk terkait."""
    owner_id = _validate_user_id(user_id)
    receipt_to_delete: str | None = None

    with session_scope(db_path) as session:
        tx = session.scalar(
            select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == owner_id,
            )
        )
        if tx is None:
            return False

        if isinstance(tx.receipt_image_path, str):
            receipt_to_delete = tx.receipt_image_path.strip() or None

        session.delete(tx)

    if receipt_to_delete is not None:
        image_service.delete_archived_receipt_file(receipt_to_delete)

    return True
