"""Unit & integration tests untuk pemasukan (incomes) dan anggaran bulanan (budgets) (M3.3)."""

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.database import get_connection
from backend.main import app


@pytest.fixture()
def multi_user_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, TestClient, TestClient, Path]]:
    """Sediakan client anonim, User A, dan User B berbagi DB & uploads terisolasi."""
    db_file = tmp_path / "test_budgets_incomes.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))

    with (
        TestClient(app) as anon_client,
        TestClient(app) as client_a,
        TestClient(app) as client_b,
    ):
        assert (
            client_a.post(
                "/api/auth/register",
                json={"email": "budget-a@example.com", "password": "passwordA123"},
            ).status_code
            == 201
        )
        assert (
            client_b.post(
                "/api/auth/register",
                json={"email": "budget-b@example.com", "password": "passwordB123"},
            ).status_code
            == 201
        )
        yield anon_client, client_a, client_b, db_file


class TestIncomesAndCashflowSummary:
    """Pengujian CRUD incomes, validasi ketat, dan integrasi arus kas di summary bulanan."""

    def test_incomes_crud_filtering_and_summary_cashflow_accuracy(
        self, multi_user_clients: tuple[TestClient, TestClient, TestClient, Path]
    ) -> None:
        _anon, client_a, _client_b, _db_file = multi_user_clients

        # 1. Catat pemasukan lintas bulan
        inc_oct = client_a.post(
            "/api/incomes",
            json={
                "income_date": "2026-10-25",
                "source_name": "Bonus Oktober",
                "amount": 1000000,
            },
        )
        assert inc_oct.status_code == 201

        inc_nov_1 = client_a.post(
            "/api/incomes",
            json={
                "income_date": "2026-11-01",
                "source_name": "  Gaji Bulanan  ",
                "amount": 5000000,
            },
        )
        assert inc_nov_1.status_code == 201
        assert inc_nov_1.json()["data"]["source_name"] == "Gaji Bulanan"

        inc_nov_2 = client_a.post(
            "/api/incomes",
            json={
                "income_date": "2026-11-15",
                "source_name": "Freelance Desain",
                "amount": 1500000,
            },
        )
        assert inc_nov_2.status_code == 201
        nov_2_id = inc_nov_2.json()["data"]["id"]

        # 2. List terfilter November 2026 (urut income_date DESC)
        nov_list = client_a.get("/api/incomes", params={"month": 11, "year": 2026})
        assert nov_list.status_code == 200
        nov_body = nov_list.json()
        assert nov_body["count"] == 2
        assert nov_body["total_income"] == 6500000
        assert [r["source_name"] for r in nov_body["data"]] == [
            "Freelance Desain",
            "Gaji Bulanan",
        ]

        # 3. Tambah pengeluaran di November 2026 & cek arus kas surplus di /api/summary/monthly
        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-10",
                "items": [
                    {
                        "name": "Belanja Mingguan",
                        "price": 1250000,
                        "category": "Kebutuhan Pokok",
                    }
                ],
            },
        )

        summary_surplus = client_a.get(
            "/api/summary/monthly", params={"month": 11, "year": 2026}
        ).json()
        assert summary_surplus["total_income"] == 6500000
        assert summary_surplus["total_expense"] == 1250000
        assert summary_surplus["net_balance"] == 5250000

        # 4. Hapus pemasukan & uji kasus defisit (net_balance negatif)
        assert client_a.delete(f"/api/incomes/{nov_2_id}").status_code == 200
        assert client_a.delete(f"/api/incomes/{nov_2_id}").status_code == 404

        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-20",
                "items": [
                    {
                        "name": "Servis Kendaraan",
                        "price": 4500000,
                        "category": "Transportasi",
                    }
                ],
            },
        )

        summary_deficit = client_a.get(
            "/api/summary/monthly", params={"month": 11, "year": 2026}
        ).json()
        assert summary_deficit["total_income"] == 5000000
        assert summary_deficit["total_expense"] == 5750000
        assert summary_deficit["net_balance"] == -750000

    @pytest.mark.parametrize(
        "bad_payload",
        [
            {"income_date": "2026-02-30", "source_name": "Gaji", "amount": 1000},
            {"income_date": "2026-11-10", "source_name": "   ", "amount": 1000},
            {"income_date": "2026-11-10", "source_name": "Gaji", "amount": -100},
            {"income_date": "2026-11-10", "source_name": "Gaji", "amount": 1000.5},
            {"income_date": "2026-11-10", "source_name": "Gaji", "amount": True},
        ],
    )
    def test_income_rejects_invalid_inputs_422(
        self,
        multi_user_clients: tuple[TestClient, TestClient, TestClient, Path],
        bad_payload: dict[str, object],
    ) -> None:
        _anon, client_a, _client_b, _db_file = multi_user_clients
        resp = client_a.post("/api/incomes", json=bad_payload)
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "VALIDATION_ERROR"


class TestBudgetsUpsertAndDeterministicStatus:
    """Pengujian upsert anggaran, batas status safe/warning/over_budget, & edge case limit=0."""

    def test_budgets_upsert_no_duplicates_statuses_and_zero_limit(
        self, multi_user_clients: tuple[TestClient, TestClient, TestClient, Path]
    ) -> None:
        _anon, client_a, _client_b, db_file = multi_user_clients

        # Catat pengeluaran terukur di November 2026
        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-08",
                "items": [
                    {
                        "name": "Makan Siang",
                        "price": 79000,
                        "category": "Makanan & Minuman",
                    },
                    {
                        "name": "Ojek Online",
                        "price": 80000,
                        "category": "Transportasi",
                    },
                    {
                        "name": "Vitamin",
                        "price": 100000,
                        "category": "Kesehatan & Perawatan",
                    },
                    {
                        "name": "Listrik",
                        "price": 120000,
                        "category": "Tagihan & Utilitas",
                    },
                    {
                        "name": "Nonton Bioskop",
                        "price": 50000,
                        "category": "Hiburan & Belanja",
                    },
                ],
            },
        )

        # Atur anggaran untuk menguji seluruh ambang batas:
        # safe (< 80%): 79.000 / 100.000 = 79%
        r_safe = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Makanan & Minuman",
                "limit_amount": 100000,
            },
        )
        assert r_safe.status_code == 200
        assert r_safe.json()["data"]["status"] == "safe"
        assert r_safe.json()["data"]["remaining_amount"] == 21000
        assert r_safe.json()["data"]["usage_percentage"] == 79.0

        # warning (tepat 80%): 80.000 / 100.000 = 80%
        r_warn_80 = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Transportasi",
                "limit_amount": 100000,
            },
        )
        assert r_warn_80.json()["data"]["status"] == "warning"

        # warning (tepat 100%): 100.000 / 100.000 = 100%
        r_warn_100 = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Kesehatan & Perawatan",
                "limit_amount": 100000,
            },
        )
        assert r_warn_100.json()["data"]["status"] == "warning"
        assert r_warn_100.json()["data"]["remaining_amount"] == 0

        # over_budget (> 100%): 120.000 / 100.000 = 120%
        r_over = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Tagihan & Utilitas",
                "limit_amount": 100000,
            },
        )
        assert r_over.json()["data"]["status"] == "over_budget"
        assert r_over.json()["data"]["remaining_amount"] == -20000
        assert r_over.json()["data"]["usage_percentage"] == 120.0

        # Edge case limit_amount == 0 dengan pengeluaran > 0 -> over_budget tanpa ZeroDivisionError
        r_zero_spent = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Hiburan & Belanja",
                "limit_amount": 0,
            },
        )
        assert r_zero_spent.status_code == 200
        assert r_zero_spent.json()["data"]["status"] == "over_budget"
        assert r_zero_spent.json()["data"]["remaining_amount"] == -50000

        # Edge case limit_amount == 0 dengan pengeluaran == 0 -> safe (0.0%)
        r_zero_clean = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Lainnya",
                "limit_amount": 0,
            },
        )
        assert r_zero_clean.status_code == 200
        assert r_zero_clean.json()["data"]["status"] == "safe"
        assert r_zero_clean.json()["data"]["usage_percentage"] == 0.0

        # Upsert kategori yang sudah ada ("Makanan & Minuman") harus update, bukan duplikat
        r_upsert = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Makanan & Minuman",
                "limit_amount": 200000,
            },
        )
        assert r_upsert.status_code == 200
        assert r_upsert.json()["data"]["id"] == r_safe.json()["data"]["id"]
        assert r_upsert.json()["data"]["limit_amount"] == 200000
        assert r_upsert.json()["data"]["usage_percentage"] == 39.5

        conn = get_connection(db_file)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM budgets WHERE category = 'Makanan & Minuman'"
            ).fetchone()["cnt"]
            assert row_count == 1
        finally:
            conn.close()

        # GET /api/budgets mengembalikan agregasi total_budget, total_spent, total_remaining
        list_resp = client_a.get("/api/budgets", params={"month": 11, "year": 2026})
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["total_budget"] == 500000
        assert body["total_spent"] == 429000
        assert body["total_remaining"] == 71000
        assert len(body["data"]) == 6

        # Hapus salah satu anggaran
        lainnya_id = r_zero_clean.json()["data"]["id"]
        assert client_a.delete(f"/api/budgets/{lainnya_id}").status_code == 200
        assert client_a.delete(f"/api/budgets/{lainnya_id}").status_code == 404

    def test_budget_rejects_invalid_category_with_422(
        self, multi_user_clients: tuple[TestClient, TestClient, TestClient, Path]
    ) -> None:
        _anon, client_a, _client_b, _db_file = multi_user_clients
        resp = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Elektronik Mewah",
                "limit_amount": 500000,
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "VALIDATION_ERROR"


class TestBudgetsAndIncomesAuthAndIsolation:
    """Verifikasi proteksi 401 tanpa login dan isolasi ketat User A vs User B."""

    def test_requires_auth_401_and_isolates_user_a_from_user_b(
        self, multi_user_clients: tuple[TestClient, TestClient, TestClient, Path]
    ) -> None:
        anon_client, client_a, client_b, _db_file = multi_user_clients

        # 1. Endpoint baru wajib 401 tanpa sesi login
        assert (
            anon_client.post(
                "/api/incomes",
                json={"income_date": "2026-11-01", "source_name": "Gaji", "amount": 1000},
            ).status_code
            == 401
        )
        assert anon_client.get("/api/incomes").status_code == 401
        assert anon_client.delete("/api/incomes/1").status_code == 401
        assert anon_client.get("/api/budgets").status_code == 401
        assert (
            anon_client.put(
                "/api/budgets",
                json={
                    "month": 11,
                    "year": 2026,
                    "category": "Lainnya",
                    "limit_amount": 10000,
                },
            ).status_code
            == 401
        )
        assert anon_client.delete("/api/budgets/1").status_code == 401

        # 2. User A simpan pemasukan & anggaran
        inc_a = client_a.post(
            "/api/incomes",
            json={
                "income_date": "2026-11-05",
                "source_name": "Gaji Rahasia A",
                "amount": 8000000,
            },
        ).json()["data"]
        bud_a = client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Makanan & Minuman",
                "limit_amount": 1000000,
            },
        ).json()["data"]

        # 3. User B tidak melihat data User A & tidak bisa menghapusnya
        b_incomes = client_b.get("/api/incomes", params={"month": 11, "year": 2026}).json()
        assert b_incomes["count"] == 0
        assert b_incomes["total_income"] == 0

        b_budgets = client_b.get("/api/budgets", params={"month": 11, "year": 2026}).json()
        assert b_budgets["data"] == []
        assert b_budgets["total_budget"] == 0

        b_summary = client_b.get(
            "/api/summary/monthly", params={"month": 11, "year": 2026}
        ).json()
        assert b_summary["total_income"] == 0
        assert b_summary["net_balance"] == 0

        assert client_b.delete(f"/api/incomes/{inc_a['id']}").status_code == 404
        assert client_b.delete(f"/api/budgets/{bud_a['id']}").status_code == 404

        # Data User A tetap utuh
        assert (
            client_a.get("/api/incomes", params={"month": 11, "year": 2026}).json()[
                "total_income"
            ]
            == 8000000
        )
