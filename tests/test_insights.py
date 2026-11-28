"""Unit & integration tests untuk AI Financial Insights terpisah (M3.3)."""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
import pytest

from backend import config as app_config
from backend.main import app
from backend.services import insights_service


@pytest.fixture()
def insights_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, TestClient, TestClient]]:
    """Sediakan anon_client, client_a, dan client_b terisolasi di tmp_path."""
    db_file = tmp_path / "test_insights.db"
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
                json={"email": "insight-a@example.com", "password": "passwordA123"},
            ).status_code
            == 201
        )
        assert (
            client_b.post(
                "/api/auth/register",
                json={"email": "insight-b@example.com", "password": "passwordB123"},
            ).status_code
            == 201
        )
        yield anon_client, client_a, client_b


def _make_api_error(code: int, status: str, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(
        code,
        {"error": {"status": status, "message": message}},
    )


class TestInsightsIsolationAndResilience:
    """Pengujian agregasi deterministik, short-circuit, privacy payload, retry, & isolasi user."""

    def test_empty_month_short_circuits_without_calling_gemini(
        self,
        insights_clients: tuple[TestClient, TestClient, TestClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _anon, client_a, _client_b = insights_clients
        gemini_called = False

        def should_not_call(_key: str) -> object:
            nonlocal gemini_called
            gemini_called = True
            raise AssertionError("Gemini tidak boleh dipanggil untuk bulan kosong.")

        monkeypatch.setattr(insights_service, "_create_genai_client", should_not_call)

        resp = client_a.get(
            "/api/insights/monthly", params={"month": 11, "year": 2026}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["has_data"] is False
        assert body["recommendations"] == []
        assert body["metrics_snapshot"]["total_expense"] == 0
        assert body["metrics_snapshot"]["total_income"] == 0
        assert gemini_called is False

    def test_insights_sends_only_aggregated_metrics_never_raw_item_or_source_names(
        self,
        insights_clients: tuple[TestClient, TestClient, TestClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _anon, client_a, client_b = insights_clients

        # Data bulan sebelumnya (Oktober 2026) untuk hitung MoM
        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-10-15",
                "items": [
                    {
                        "name": "RAHASIA_ITEM_OKTOBER_XYZ",
                        "price": 200000,
                        "category": "Makanan & Minuman",
                    }
                ],
            },
        )

        # Data bulan target (November 2026): pemasukan, pengeluaran, dan budget over_budget
        client_a.post(
            "/api/incomes",
            json={
                "income_date": "2026-11-01",
                "source_name": "RAHASIA_SUMBER_GAJI_PT_ABC",
                "amount": 1000000,
            },
        )
        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-12",
                "items": [
                    {
                        "name": "RAHASIA_KOPI_SPESIAL_999",
                        "price": 300000,
                        "category": "Makanan & Minuman",
                    },
                    {
                        "name": "RAHASIA_OBAT_PRIBADI_777",
                        "price": 150000,
                        "category": "Kesehatan & Perawatan",
                    },
                ],
            },
        )
        client_a.put(
            "/api/budgets",
            json={
                "month": 11,
                "year": 2026,
                "category": "Makanan & Minuman",
                "limit_amount": 250000,
            },
        )

        captured_prompts: list[str] = []

        def fake_generate_content(**kwargs: object) -> SimpleNamespace:
            captured_prompts.append(str(kwargs["contents"]))
            return SimpleNamespace(
                text=(
                    '{"summary_text": "Pengeluaran bulan November 2026 sebesar Rp450.000 masih '
                    'lebih rendah dari pemasukan Rp1.000.000, namun kategori Makanan & Minuman '
                    'melebihi batas anggaran Rp250.000.", '
                    '"recommendations": ['
                    '"Kurangi porsi belanja pada kategori Makanan & Minuman agar kembali di bawah Rp250.000.", '
                    '"Sisihkan sebagian surplus Rp550.000 ke dana darurat."'
                    "]}"
                )
            )

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(
            insights_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=fake_generate_content)
            ),
        )

        resp = client_a.get(
            "/api/insights/monthly", params={"month": 11, "year": 2026}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_data"] is True
        assert len(body["recommendations"]) == 2
        assert body["metrics_snapshot"]["total_income"] == 1000000
        assert body["metrics_snapshot"]["total_expense"] == 450000
        assert body["metrics_snapshot"]["net_balance"] == 550000
        assert body["metrics_snapshot"]["previous_month_expense"] == 200000
        assert body["metrics_snapshot"]["mom_expense_change_amount"] == 250000
        assert body["metrics_snapshot"]["mom_expense_change_percentage"] == 125.0
        assert body["metrics_snapshot"]["budget_alerts"][0]["status"] == "over_budget"

        # Verifikasi KETAT: nama barang & sumber pemasukan mentah TIDAK BOLEH dikirim ke LLM
        assert len(captured_prompts) == 1
        sent_prompt = captured_prompts[0]
        assert "RAHASIA_ITEM_OKTOBER_XYZ" not in sent_prompt
        assert "RAHASIA_SUMBER_GAJI_PT_ABC" not in sent_prompt
        assert "RAHASIA_KOPI_SPESIAL_999" not in sent_prompt
        assert "RAHASIA_OBAT_PRIBADI_777" not in sent_prompt
        assert "Makanan & Minuman" in sent_prompt
        assert "450000" in sent_prompt

        # Verifikasi isolasi: User B pada bulan yang sama tetap melihat has_data=False
        resp_b = client_b.get(
            "/api/insights/monthly", params={"month": 11, "year": 2026}
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["has_data"] is False

    def test_insights_retries_on_503_uses_fallback_and_maps_persistent_429_to_503(
        self,
        insights_clients: tuple[TestClient, TestClient, TestClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        anon_client, client_a, _client_b = insights_clients

        # Tanpa login -> 401
        assert (
            anon_client.get(
                "/api/insights/monthly", params={"month": 11, "year": 2026}
            ).status_code
            == 401
        )

        client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-20",
                "items": [{"name": "Kopi", "price": 15000}],
            },
        )

        # 1. Simulasi 3x 503 di primary model -> pulih lewat fallback model
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def flaky_models(**kwargs: object) -> SimpleNamespace:
            model = str(kwargs["model"])
            called_models.append(model)
            if model == "gemini-primary":
                raise _make_api_error(503, "UNAVAILABLE", "Primary overloaded")
            return SimpleNamespace(
                text=(
                    '{"summary_text": "Pengeluaran bulan ini tercatat Rp15.000.", '
                    '"recommendations": ["Pertahankan pencatatan rutin setiap transaksi."]}'
                )
            )

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(insights_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            insights_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=flaky_models)
            ),
        )

        ok_resp = client_a.get(
            "/api/insights/monthly", params={"month": 11, "year": 2026}
        )
        assert ok_resp.status_code == 200
        assert ok_resp.json()["has_data"] is True
        assert called_models == [
            "gemini-primary",
            "gemini-primary",
            "gemini-primary",
            "gemini-fallback",
        ]
        assert sleep_calls == [1.0, 2.0, 4.0]

        # 2. Simulasi error persisten 429 pada primary & fallback -> 503 AI_SERVICE_UNAVAILABLE
        monkeypatch.setattr(
            insights_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(
                    generate_content=lambda **_kw: (_ for _ in ()).throw(
                        _make_api_error(429, "RESOURCE_EXHAUSTED", "Quota exhausted")
                    )
                )
            ),
        )
        fail_resp = client_a.get(
            "/api/insights/monthly", params={"month": 11, "year": 2026}
        )
        assert fail_resp.status_code == 503
        assert fail_resp.json()["status"] == "error"
        assert fail_resp.json()["error_code"] == "AI_SERVICE_UNAVAILABLE"
