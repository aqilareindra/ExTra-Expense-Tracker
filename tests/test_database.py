"""Unit test layer database SQLite dan transaction_service (Milestone 2)."""

from pathlib import Path
import sqlite3

import pytest

from backend.database import get_connection, init_db
from backend.schemas.transaction import (
    ItemUpdateRequest,
    TransactionCreateRequest,
    TransactionItemCreate,
)
from backend.services import transaction_service


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Path:
    """Buat database SQLite sementara yang terisolasi untuk setiap test."""
    db_file = tmp_path / "test_extra.db"
    init_db(db_file)
    return db_file


def _count_rows(db_path: Path, table_name: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
        return int(row["cnt"])
    finally:
        conn.close()


class TestDatabaseSchemaAndIntegrity:
    """Verifikasi struktur tabel, index, PRAGMA foreign_keys, dan CHECK constraints."""

    def test_init_db_creates_exact_two_tables_and_indexes_without_store_column(
        self, isolated_db: Path
    ) -> None:
        conn = get_connection(isolated_db)
        try:
            fk_row = conn.execute("PRAGMA foreign_keys;").fetchone()
            assert fk_row[0] == 1

            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            assert tables == {"transactions", "transaction_items"}

            tx_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(transactions);").fetchall()
            }
            assert tx_cols == {"id", "transaction_date", "created_at"}

            item_cols = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(transaction_items);"
                ).fetchall()
            }
            assert item_cols == {
                "id",
                "transaction_id",
                "item_name",
                "category",
                "price",
            }

            indexes = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            assert "idx_transactions_date" in indexes
            assert "idx_transaction_items_transaction_id" in indexes
            assert "idx_transaction_items_category" in indexes
        finally:
            conn.close()

    def test_init_db_migrates_legacy_v1_0_0_schema_preserving_existing_rows(
        self, tmp_path: Path
    ) -> None:
        legacy_db = tmp_path / "legacy_v1_0_0.db"
        raw_conn = sqlite3.connect(str(legacy_db))
        try:
            raw_conn.executescript(
                """
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE transaction_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL CHECK (length(trim(item_name)) > 0),
                    price INTEGER NOT NULL CHECK (price >= 0),
                    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
                );
                INSERT INTO transactions (transaction_date) VALUES ('2026-11-10');
                INSERT INTO transaction_items (transaction_id, item_name, price)
                VALUES (1, 'Indomie Goreng', 3500), (1, 'Aqua 600ml', 4000);
                """
            )
            raw_conn.commit()
        finally:
            raw_conn.close()

        # Jalankan init_db() di atas file DB lama (harus idempoten & aman)
        init_db(legacy_db)
        init_db(legacy_db)

        migrated_items = transaction_service.get_transactions(db_path=legacy_db)
        assert len(migrated_items) == 2
        assert [(it.name, it.price, it.category) for it in migrated_items] == [
            ("Aqua 600ml", 4000, "Lainnya"),
            ("Indomie Goreng", 3500, "Lainnya"),
        ]

    def test_sqlite_check_and_foreign_key_constraints_enforced(
        self, isolated_db: Path
    ) -> None:
        conn = get_connection(isolated_db)
        try:
            # Foreign key invalid harus ditolak
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO transaction_items (transaction_id, item_name, price) "
                    "VALUES (999, 'Aqua', 4000)"
                )

            cur = conn.execute(
                "INSERT INTO transactions (transaction_date) VALUES ('2026-11-24')"
            )
            tx_id = cur.lastrowid

            # Nama barang spasi kosong harus ditolak CHECK constraint
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO transaction_items (transaction_id, item_name, price) "
                    "VALUES (?, '   ', 4000)",
                    (tx_id,),
                )

            # Harga negatif harus ditolak CHECK constraint
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO transaction_items (transaction_id, item_name, price) "
                    "VALUES (?, 'Aqua', -1)",
                    (tx_id,),
                )
        finally:
            conn.close()


class TestTransactionServiceCRUD:
    """Pengujian fungsi CRUD, filter, search, cascade delete, dan orphan cleanup."""

    def test_create_and_get_transactions_default_ordering(
        self, isolated_db: Path
    ) -> None:
        t1 = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-10-15",
                items=[TransactionItemCreate(name="Roti Tawar", price=12000)],
            ),
            db_path=isolated_db,
        )
        t2 = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-24",
                items=[
                    TransactionItemCreate(name="Indomie Goreng", price=3500),
                    TransactionItemCreate(name="Aqua 600ml", price=4000),
                ],
            ),
            db_path=isolated_db,
        )

        assert t1.transaction_id == 1
        assert t2.transaction_id == 2
        assert len(t2.items) == 2

        history = transaction_service.get_transactions(db_path=isolated_db)
        assert [item.name for item in history] == [
            "Aqua 600ml",
            "Indomie Goreng",
            "Roti Tawar",
        ]

    def test_filter_by_month_year_and_case_insensitive_search(
        self, isolated_db: Path
    ) -> None:
        transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2025-11-10",
                items=[TransactionItemCreate(name="Kopi Susu", price=15000)],
            ),
            db_path=isolated_db,
        )
        transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-10-05",
                items=[TransactionItemCreate(name="Indomie Soto", price=3500)],
            ),
            db_path=isolated_db,
        )
        transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-24",
                items=[
                    TransactionItemCreate(name="Indomie Goreng", price=3500),
                    TransactionItemCreate(name="Sabun Cuci", price=9000),
                ],
            ),
            db_path=isolated_db,
        )

        nov_2026 = transaction_service.get_transactions(
            month=11, year=2026, db_path=isolated_db
        )
        assert [item.name for item in nov_2026] == ["Sabun Cuci", "Indomie Goreng"]

        only_nov = transaction_service.get_transactions(month=11, db_path=isolated_db)
        assert len(only_nov) == 3

        only_2026 = transaction_service.get_transactions(year=2026, db_path=isolated_db)
        assert len(only_2026) == 3

        search_indomie = transaction_service.get_transactions(
            search="iNdOmIe", db_path=isolated_db
        )
        assert [item.name for item in search_indomie] == [
            "Indomie Goreng",
            "Indomie Soto",
        ]

        combined = transaction_service.get_transactions(
            month=11, year=2026, search="goreng", db_path=isolated_db
        )
        assert len(combined) == 1
        assert combined[0].name == "Indomie Goreng"

    def test_update_item_splits_transaction_when_date_changed_on_multi_item_tx(
        self, isolated_db: Path
    ) -> None:
        created = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-20",
                items=[
                    TransactionItemCreate(name="Item A", price=5000),
                    TransactionItemCreate(name="Item B", price=7000),
                ],
            ),
            db_path=isolated_db,
        )
        item_a, item_b = created.items

        updated_a = transaction_service.update_item(
            item_id=item_a.id,
            payload=ItemUpdateRequest(
                name="Item A Revisi", price=5500, date="2026-11-22"
            ),
            db_path=isolated_db,
        )
        assert updated_a is not None
        assert updated_a.name == "Item A Revisi"
        assert updated_a.price == 5500
        assert updated_a.date == "2026-11-22"
        assert updated_a.transaction_id != created.transaction_id

        # Pastikan Item B tetap berada pada transaksi dan tanggal semula
        all_items = {
            item.id: item
            for item in transaction_service.get_transactions(db_path=isolated_db)
        }
        assert all_items[item_b.id].date == "2026-11-20"
        assert all_items[item_b.id].transaction_id == created.transaction_id
        assert _count_rows(isolated_db, "transactions") == 2

    def test_update_item_updates_date_in_place_for_single_item_tx(
        self, isolated_db: Path
    ) -> None:
        created = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-20",
                items=[TransactionItemCreate(name="Parkir", price=2000)],
            ),
            db_path=isolated_db,
        )
        only_item = created.items[0]

        updated = transaction_service.update_item(
            item_id=only_item.id,
            payload=ItemUpdateRequest(date="2026-11-21"),
            db_path=isolated_db,
        )
        assert updated is not None
        assert updated.date == "2026-11-21"
        assert updated.transaction_id == created.transaction_id
        assert _count_rows(isolated_db, "transactions") == 1

        assert (
            transaction_service.update_item(
                item_id=9999,
                payload=ItemUpdateRequest(price=3000),
                db_path=isolated_db,
            )
            is None
        )

    def test_delete_item_performs_orphan_cleanup_on_last_item(
        self, isolated_db: Path
    ) -> None:
        created = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-24",
                items=[
                    TransactionItemCreate(name="Barang 1", price=1000),
                    TransactionItemCreate(name="Barang 2", price=2000),
                ],
            ),
            db_path=isolated_db,
        )
        first_id = created.items[0].id
        second_id = created.items[1].id

        res_first = transaction_service.delete_item(first_id, db_path=isolated_db)
        assert res_first is not None
        assert res_first["orphan_transaction_deleted"] is False
        assert _count_rows(isolated_db, "transactions") == 1
        assert _count_rows(isolated_db, "transaction_items") == 1

        res_second = transaction_service.delete_item(second_id, db_path=isolated_db)
        assert res_second is not None
        assert res_second["orphan_transaction_deleted"] is True
        assert _count_rows(isolated_db, "transactions") == 0
        assert _count_rows(isolated_db, "transaction_items") == 0

        assert transaction_service.delete_item(9999, db_path=isolated_db) is None

    def test_delete_transaction_cascades_to_all_items(self, isolated_db: Path) -> None:
        created = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-24",
                items=[
                    TransactionItemCreate(name="Teh Botol", price=5000),
                    TransactionItemCreate(name="Keripik", price=10000),
                    TransactionItemCreate(name="Permen", price=2500),
                ],
            ),
            db_path=isolated_db,
        )
        assert _count_rows(isolated_db, "transactions") == 1
        assert _count_rows(isolated_db, "transaction_items") == 3

        deleted = transaction_service.delete_transaction(
            created.transaction_id, db_path=isolated_db
        )
        assert deleted is True
        assert _count_rows(isolated_db, "transactions") == 0
        assert _count_rows(isolated_db, "transaction_items") == 0

        assert (
            transaction_service.delete_transaction(
                created.transaction_id, db_path=isolated_db
            )
            is False
        )

    def test_category_persistence_filter_and_partial_update(
        self, isolated_db: Path
    ) -> None:
        created = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-26",
                items=[
                    TransactionItemCreate(
                        name="Bensin Pertalite",
                        price=25000,
                        category="Transportasi",
                    ),
                    TransactionItemCreate(
                        name="Kopi Susu",
                        price=18000,
                        category="Makanan & Minuman",
                    ),
                    TransactionItemCreate(name="Parkir", price=2000),
                ],
            ),
            db_path=isolated_db,
        )
        assert [it.category for it in created.items] == [
            "Transportasi",
            "Makanan & Minuman",
            "Lainnya",
        ]

        only_transport = transaction_service.get_transactions(
            category="Transportasi", db_path=isolated_db
        )
        assert len(only_transport) == 1
        assert only_transport[0].name == "Bensin Pertalite"

        # Update hanya category tanpa menyentuh name/price/date
        parkir_item = created.items[2]
        updated_parkir = transaction_service.update_item(
            item_id=parkir_item.id,
            payload=ItemUpdateRequest(category="Transportasi"),
            db_path=isolated_db,
        )
        assert updated_parkir is not None
        assert updated_parkir.category == "Transportasi"
        assert updated_parkir.name == "Parkir"
        assert updated_parkir.price == 2000

        # Update price saja harus mempertahankan category yang sudah ada
        re_updated = transaction_service.update_item(
            item_id=parkir_item.id,
            payload=ItemUpdateRequest(price=3000),
            db_path=isolated_db,
        )
        assert re_updated is not None
        assert re_updated.category == "Transportasi"
        assert re_updated.price == 3000

        with pytest.raises(ValueError):
            transaction_service.get_transactions(
                category="Kategori Ilegal", db_path=isolated_db
            )
