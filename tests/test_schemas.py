"""Unit test validasi skema Pydantic tahap ekstraksi & penyimpanan (Milestone 2 & 3)."""

import pytest
from pydantic import ValidationError

from backend.schemas.categories import EXPENSE_CATEGORIES
from backend.schemas.receipt import (
    ExtractedItem,
    ReceiptExtractionResult,
    ReceiptExtractResponse,
    ReceiptPreviewData,
)
from backend.schemas.summary import (
    CategoryExpenseBreakdown,
    DailyExpenseBreakdown,
    MonthlySummaryResponse,
)
from backend.schemas.transaction import (
    ItemUpdateRequest,
    TransactionCreateRequest,
    TransactionItemCreate,
)


class TestTransactionItemCreate:
    """Pengujian aturan validasi ketat pada TransactionItemCreate."""

    def test_valid_item_trims_whitespace_and_allows_zero_price(self) -> None:
        item = TransactionItemCreate(name="  Indomie Goreng  ", price=0)
        assert item.name == "Indomie Goreng"
        assert item.price == 0
        assert item.category == "Lainnya"

    @pytest.mark.parametrize("official_cat", EXPENSE_CATEGORIES)
    def test_accepts_all_seven_official_categories(self, official_cat: str) -> None:
        item = TransactionItemCreate(
            name="Contoh Barang",
            price=10000,
            category=f"  {official_cat}  ",
        )
        assert item.category == official_cat

    @pytest.mark.parametrize(
        "invalid_category",
        ["", "   ", "Elektronik", "makanan & minuman", None, 123, True],
    )
    def test_rejects_invalid_category_in_stage2(
        self, invalid_category: object
    ) -> None:
        with pytest.raises(ValidationError):
            TransactionItemCreate(
                name="Aqua 600ml",
                price=4000,
                category=invalid_category,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("invalid_name", ["", "   ", "\t\n  "])
    def test_rejects_empty_or_whitespace_only_name(self, invalid_name: str) -> None:
        with pytest.raises(ValidationError):
            TransactionItemCreate(name=invalid_name, price=3500)

    @pytest.mark.parametrize("non_str_name", [None, 123, True, ["Aqua"]])
    def test_rejects_non_string_name(self, non_str_name: object) -> None:
        with pytest.raises(ValidationError):
            TransactionItemCreate(name=non_str_name, price=3500)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "invalid_price",
        [-1, -5000, 3500.0, 3500.5, True, False, "3500", None],
    )
    def test_rejects_negative_float_bool_or_string_price(
        self, invalid_price: object
    ) -> None:
        with pytest.raises(ValidationError):
            TransactionItemCreate(name="Aqua 600ml", price=invalid_price)  # type: ignore[arg-type]


class TestTransactionCreateRequest:
    """Pengujian aturan validasi pada TransactionCreateRequest."""

    def test_valid_transaction_create_request(self) -> None:
        req = TransactionCreateRequest(
            date="2026-11-24",
            items=[
                TransactionItemCreate(name="Indomie Goreng", price=3500),
                TransactionItemCreate(name="Aqua 600ml", price=4000),
            ],
        )
        assert req.date == "2026-11-24"
        assert len(req.items) == 2

    def test_allows_valid_leap_year_date(self) -> None:
        req = TransactionCreateRequest(
            date="2024-02-29",
            items=[{"name": "Roti Coklat", "price": 8500}],  # type: ignore[list-item]
        )
        assert req.date == "2024-02-29"

    @pytest.mark.parametrize(
        "invalid_date",
        [
            "2026-02-29",
            "2026-02-30",
            "2025-02-29",
            "2026-13-01",
            "2026-00-10",
            "2026-11-31",
            "24-11-2026",
            "2026/11/24",
            "2026-1-5",
            "",
            None,
        ],
    )
    def test_rejects_invalid_calendar_or_format_date(
        self, invalid_date: object
    ) -> None:
        with pytest.raises(ValidationError):
            TransactionCreateRequest(
                date=invalid_date,  # type: ignore[arg-type]
                items=[{"name": "Aqua 600ml", "price": 4000}],  # type: ignore[list-item]
            )

    def test_rejects_empty_items_list(self) -> None:
        with pytest.raises(ValidationError):
            TransactionCreateRequest(date="2026-11-24", items=[])

    def test_rejects_extra_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            TransactionCreateRequest.model_validate(
                {
                    "date": "2026-11-24",
                    "store_name": "Minimarket",
                    "items": [{"name": "Aqua 600ml", "price": 4000}],
                }
            )

    def test_temp_image_token_accepts_none_or_valid_uuid_and_rejects_traversal(
        self,
    ) -> None:
        req_none = TransactionCreateRequest(
            date="2026-11-26",
            items=[TransactionItemCreate(name="Parkir", price=2000)],
            temp_image_token=None,
        )
        assert req_none.temp_image_token is None

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        req_valid = TransactionCreateRequest(
            date="2026-11-26",
            items=[TransactionItemCreate(name="Kopi", price=15000)],
            temp_image_token=f"  {valid_uuid.upper()}  ",
        )
        assert req_valid.temp_image_token == valid_uuid

        for bad_token in [
            "",
            "   ",
            "../../.env",
            "..\\secret.jpg",
            "550e8400-e29b-41d4-a716-446655440000/extra",
            "550e8400e29b41d4a716446655440000",
            "bukan-uuid",
            12345,
        ]:
            with pytest.raises(ValidationError):
                TransactionCreateRequest(
                    date="2026-11-26",
                    items=[TransactionItemCreate(name="Kopi", price=15000)],
                    temp_image_token=bad_token,  # type: ignore[arg-type]
                )


class TestItemUpdateRequest:
    """Pengujian aturan validasi pada ItemUpdateRequest."""

    def test_valid_partial_and_full_updates(self) -> None:
        by_name = ItemUpdateRequest(name="  Susu UHT  ")
        assert by_name.name == "Susu UHT"
        assert by_name.price is None
        assert by_name.date is None

        by_price = ItemUpdateRequest(price=6500)
        assert by_price.price == 6500

        by_date = ItemUpdateRequest(date="2026-11-25")
        assert by_date.date == "2026-11-25"

        full = ItemUpdateRequest(
            name="Susu UHT",
            price=6500,
            date="2026-11-25",
            category="Makanan & Minuman",
        )
        assert full.name == "Susu UHT"
        assert full.price == 6500
        assert full.date == "2026-11-25"
        assert full.category == "Makanan & Minuman"

        only_cat = ItemUpdateRequest(category="Kesehatan & Perawatan")
        assert only_cat.category == "Kesehatan & Perawatan"
        assert only_cat.name is None

    def test_rejects_when_all_fields_empty_or_none(self) -> None:
        with pytest.raises(ValidationError):
            ItemUpdateRequest()

        with pytest.raises(ValidationError):
            ItemUpdateRequest(name=None, price=None, date=None, category=None)

    def test_rejects_invalid_values_on_update(self) -> None:
        with pytest.raises(ValidationError):
            ItemUpdateRequest(name="   ")

        with pytest.raises(ValidationError):
            ItemUpdateRequest(price=-100)

        with pytest.raises(ValidationError):
            ItemUpdateRequest(price=2500.5)  # type: ignore[arg-type]

        with pytest.raises(ValidationError):
            ItemUpdateRequest(price=True)  # type: ignore[arg-type]

        with pytest.raises(ValidationError):
            ItemUpdateRequest(date="2026-02-30")

        with pytest.raises(ValidationError):
            ItemUpdateRequest(category="Kategori Ngawur")


class TestReceiptExtractionSchemas:
    """Pengujian skema tahap 1 ekstraksi AI (ReceiptExtractionResult & ExtractedItem)."""

    def test_valid_receipt_extraction_result(self) -> None:
        result = ReceiptExtractionResult(
            is_receipt=True,
            date="  2026-11-24  ",
            items=[
                ExtractedItem(name="  Indomie Goreng  ", price=3500),
                ExtractedItem(name="Aqua 600ml (x2)", price=8000),
            ],
        )
        assert result.is_receipt is True
        assert result.date == "2026-11-24"
        assert len(result.items) == 2
        assert result.items[0].name == "Indomie Goreng"
        assert result.error_reason is None

    def test_receipt_extraction_allows_null_date(self) -> None:
        result = ReceiptExtractionResult(
            is_receipt=True,
            date=None,
            items=[ExtractedItem(name="Roti Coklat", price=8500)],
        )
        assert result.date is None
        assert len(result.items) == 1

    @pytest.mark.parametrize(
        "malformed_date",
        [
            "",
            "   ",
            "tidak terbaca",
            "24-11-2026",
            "2026/11/24",
            "2026-02-29",
            "2026-02-30",
            "2025-02-29",
            20261124,
        ],
    )
    def test_malformed_or_unreadable_date_normalized_to_none(
        self, malformed_date: object
    ) -> None:
        result = ReceiptExtractionResult(
            is_receipt=True,
            date=malformed_date,  # type: ignore[arg-type]
            items=[ExtractedItem(name="Teh Botol", price=5000)],
        )
        assert result.date is None

    def test_non_receipt_result_with_error_reason(self) -> None:
        result = ReceiptExtractionResult(
            is_receipt=False,
            date=None,
            items=[],
            error_reason="Gambar bukan merupakan struk belanja.",
        )
        assert result.is_receipt is False
        assert result.items == []
        assert result.error_reason == "Gambar bukan merupakan struk belanja."

    def test_extracted_item_rejects_empty_name_or_invalid_price(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedItem(name="   ", price=3500)

        with pytest.raises(ValidationError):
            ExtractedItem(name="Aqua", price=-100)

        with pytest.raises(ValidationError):
            ExtractedItem(name="Aqua", price=True)  # type: ignore[arg-type]

    def test_receipt_extract_response_matches_prd_contract(self) -> None:
        resp = ReceiptExtractResponse(
            data=ReceiptPreviewData(
                date="2026-11-24",
                items=[ExtractedItem(name="Indomie Goreng", price=3500)],
            ),
            warnings=[],
        )
        dumped = resp.model_dump()
        assert dumped == {
            "status": "success",
            "data": {
                "date": "2026-11-24",
                "items": [
                    {
                        "name": "Indomie Goreng",
                        "price": 3500,
                        "category": "Lainnya",
                    }
                ],
            },
            "warnings": [],
            "temp_image_token": None,
        }

    @pytest.mark.parametrize(
        "unknown_ai_category",
        [None, "", "   ", "Elektronik", "Groceries", "makanan & minuman", 999],
    )
    def test_stage1_normalizes_unknown_ai_category_to_lainnya(
        self, unknown_ai_category: object
    ) -> None:
        item = ExtractedItem(
            name="Barang Misterius",
            price=12000,
            category=unknown_ai_category,  # type: ignore[arg-type]
        )
        assert item.category == "Lainnya"

    @pytest.mark.parametrize("official_cat", EXPENSE_CATEGORIES)
    def test_stage1_preserves_valid_ai_categories(self, official_cat: str) -> None:
        item = ExtractedItem(
            name="Barang Valid",
            price=12000,
            category=f" {official_cat} ",
        )
        assert item.category == official_cat


class TestMonthlySummarySchemas:
    """Pengujian skema Pydantic ringkasan bulanan (Daily, Category & MonthlySummaryResponse)."""

    def test_valid_monthly_summary_and_zero_values(self) -> None:
        summary = MonthlySummaryResponse(
            month=11,
            year=2026,
            total_expense=0,
            total_items=1,
            daily_breakdown=[
                DailyExpenseBreakdown(date="2026-11-24", total=0, item_count=1)
            ],
            category_breakdown=[
                CategoryExpenseBreakdown(category="Lainnya", total=0, item_count=1)
            ],
        )
        assert summary.status == "success"
        assert summary.total_expense == 0
        assert summary.daily_breakdown[0].total == 0
        assert summary.category_breakdown[0].category == "Lainnya"

    def test_rejects_invalid_breakdown_date_or_negative_numbers(self) -> None:
        with pytest.raises(ValidationError):
            DailyExpenseBreakdown(date="2026-02-29", total=5000, item_count=1)

        with pytest.raises(ValidationError):
            DailyExpenseBreakdown(date="2026-11-24", total=-1, item_count=1)

        with pytest.raises(ValidationError):
            DailyExpenseBreakdown(date="2026-11-24", total=5000.5, item_count=1)  # type: ignore[arg-type]

        with pytest.raises(ValidationError):
            CategoryExpenseBreakdown(category="Bukan Kategori", total=5000, item_count=1)
