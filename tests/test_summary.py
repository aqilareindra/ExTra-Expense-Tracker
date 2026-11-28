"""Unit test kalkulasi deterministik ringkasan bulanan (Milestone 4)."""

from pathlib import Path

import pytest

from backend.database import init_db
from backend.schemas.auth import RegisterRequest, UserPublic
from backend.schemas.transaction import (
    ItemUpdateRequest,
    TransactionCreateRequest,
    TransactionItemCreate,
)
from backend.services import auth_service, summary_service, transaction_service


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Path:
    """Buat database SQLite sementara yang terisolasi untuk pengujian summary."""
    db_file = tmp_path / "test_summary.db"
    init_db(db_file)
    return db_file


@pytest.fixture()
def test_user(isolated_db: Path) -> UserPublic:
    """Daftarkan pengguna uji default untuk pengujian ringkasan bulanan."""
    return auth_service.register_user(
        RegisterRequest(email="summary@example.com", password="password123"),
        db_path=isolated_db,
    )


def _seed_transaction(
    db_path: Path, user_id: int, date_str: str, items: list[tuple[str, int]]
) -> None:
    transaction_service.create_transaction(
        TransactionCreateRequest(
            date=date_str,
            items=[TransactionItemCreate(name=n, price=p) for n, p in items],
        ),
        user_id=user_id,
        db_path=db_path,
    )


class TestMonthlySummaryService:
    """Pengujian akurasi total bulanan, jumlah item, isolasi periode, & urutan ASC."""

    def test_empty_month_returns_zero_metrics_and_empty_breakdown(
        self, isolated_db: Path, test_user: UserPublic
    ) -> None:
        result = summary_service.get_monthly_summary(
            month=11, year=2026, user_id=test_user.id, db_path=isolated_db
        )
        assert result.model_dump() == {
            "status": "success",
            "month": 11,
            "year": 2026,
            "total_expense": 0,
            "total_income": 0,
            "net_balance": 0,
            "total_items": 0,
            "daily_breakdown": [],
            "category_breakdown": [],
        }

    def test_aggregates_multiple_dates_and_same_day_transactions_chronologically(
        self, isolated_db: Path, test_user: UserPublic
    ) -> None:
        # Masukkan tanggal secara acak + 2 transaksi terpisah di tanggal 2026-11-24
        _seed_transaction(
            isolated_db,
            test_user.id,
            "2026-11-24",
            [("Indomie Goreng", 3500), ("Aqua 600ml", 4000)],
        )
        _seed_transaction(
            isolated_db,
            test_user.id,
            "2026-11-05",
            [("Beras 5kg", 68000)],
        )
        _seed_transaction(
            isolated_db,
            test_user.id,
            "2026-11-24",
            [("Roti Coklat", 8500)],
        )
        _seed_transaction(
            isolated_db,
            test_user.id,
            "2026-11-15",
            [("Sabun Mandi", 5000), ("Pasta Gigi", 12000)],
        )

        result = summary_service.get_monthly_summary(
            month=11, year=2026, user_id=test_user.id, db_path=isolated_db
        )

        # Total = 68000 + (5000 + 12000) + (3500 + 4000 + 8500) = 101000; 6 item
        assert result.status == "success"
        assert result.month == 11
        assert result.year == 2026
        assert result.total_expense == 101000
        assert result.total_items == 6

        # Pastikan urutan kronologis ASC & 2 transaksi 24 Nov tergabung jadi 1 entri
        assert [entry.model_dump() for entry in result.daily_breakdown] == [
            {"date": "2026-11-05", "total": 68000, "item_count": 1},
            {"date": "2026-11-15", "total": 17000, "item_count": 2},
            {"date": "2026-11-24", "total": 16000, "item_count": 3},
        ]

    def test_excludes_transactions_from_other_months_and_other_years(
        self, isolated_db: Path, test_user: UserPublic
    ) -> None:
        _seed_transaction(isolated_db, test_user.id, "2025-11-24", [("Tahun Lalu", 50000)])
        _seed_transaction(isolated_db, test_user.id, "2026-10-31", [("Akhir Oktober", 25000)])
        _seed_transaction(isolated_db, test_user.id, "2026-11-01", [("Awal November", 10000)])
        _seed_transaction(isolated_db, test_user.id, "2026-11-30", [("Akhir November", 15000)])
        _seed_transaction(isolated_db, test_user.id, "2026-12-01", [("Awal Desember", 30000)])

        nov_2026 = summary_service.get_monthly_summary(
            month=11, year=2026, user_id=test_user.id, db_path=isolated_db
        )
        assert nov_2026.total_expense == 25000
        assert nov_2026.total_items == 2
        assert [d.date for d in nov_2026.daily_breakdown] == [
            "2026-11-01",
            "2026-11-30",
        ]

    @pytest.mark.parametrize(
        ("bad_month", "bad_year"),
        [
            (0, 2026),
            (13, 2026),
            (-1, 2026),
            (True, 2026),
            (11, 99),
            (11, 10000),
            (11, False),
        ],
    )
    def test_rejects_invalid_month_or_year_arguments(
        self, isolated_db: Path, test_user: UserPublic, bad_month: int, bad_year: int
    ) -> None:
        with pytest.raises(ValueError):
            summary_service.get_monthly_summary(
                month=bad_month,
                year=bad_year,
                user_id=test_user.id,
                db_path=isolated_db,
            )

    def test_category_breakdown_sorted_desc_and_reacts_to_edit_and_delete(
        self, isolated_db: Path, test_user: UserPublic
    ) -> None:
        tx1 = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-10",
                items=[
                    TransactionItemCreate(
                        name="Beras 5kg",
                        price=70000,
                        category="Kebutuhan Pokok",
                    ),
                    TransactionItemCreate(
                        name="Kopi Susu",
                        price=18000,
                        category="Makanan & Minuman",
                    ),
                ],
            ),
            user_id=test_user.id,
            db_path=isolated_db,
        )
        tx2 = transaction_service.create_transaction(
            TransactionCreateRequest(
                date="2026-11-15",
                items=[
                    TransactionItemCreate(
                        name="Nasi Padang",
                        price=27000,
                        category="Makanan & Minuman",
                    ),
                    TransactionItemCreate(
                        name="Ojek Online",
                        price=15000,
                        category="Transportasi",
                    ),
                ],
            ),
            user_id=test_user.id,
            db_path=isolated_db,
        )

        initial_summary = summary_service.get_monthly_summary(
            month=11, year=2026, user_id=test_user.id, db_path=isolated_db
        )
        assert initial_summary.total_expense == 130000
        assert [c.model_dump() for c in initial_summary.category_breakdown] == [
            {"category": "Kebutuhan Pokok", "total": 70000, "item_count": 1},
            {"category": "Makanan & Minuman", "total": 45000, "item_count": 2},
            {"category": "Transportasi", "total": 15000, "item_count": 1},
        ]

        # Ubah kategori Beras 5kg menjadi Tagihan & Utilitas dan hapus Ojek Online
        beras_id = tx1.items[0].id
        ojek_id = tx2.items[1].id
        transaction_service.update_item(
            item_id=beras_id,
            payload=ItemUpdateRequest(category="Tagihan & Utilitas", price=30000),
            user_id=test_user.id,
            db_path=isolated_db,
        )
        transaction_service.delete_item(
            ojek_id, user_id=test_user.id, db_path=isolated_db
        )

        updated_summary = summary_service.get_monthly_summary(
            month=11, year=2026, user_id=test_user.id, db_path=isolated_db
        )
        assert updated_summary.total_expense == 75000
        assert updated_summary.total_items == 3
        assert [c.model_dump() for c in updated_summary.category_breakdown] == [
            {"category": "Makanan & Minuman", "total": 45000, "item_count": 2},
            {"category": "Tagihan & Utilitas", "total": 30000, "item_count": 1},
        ]
