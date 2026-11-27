import { useEffect, useState, type FormEvent } from "react";
import { ApiClientError } from "../../api/client";
import { updateItem } from "../../api/transactions";
import {
  EXPENSE_CATEGORIES,
  isValidCategory,
  type ExpenseCategory,
} from "../../constants/categories";
import type { TransactionItemRecord } from "../../types/api";
import {
  isValidIsoCalendarDate,
  parseStrictNonNegativeInt,
} from "../../utils/formatters";

interface EditItemModalProps {
  item: TransactionItemRecord | null;
  onClose: () => void;
  onUpdated: (updated: TransactionItemRecord) => void;
}

export function EditItemModal({ item, onClose, onUpdated }: EditItemModalProps) {
  const [dateValue, setDateValue] = useState("");
  const [nameValue, setNameValue] = useState("");
  const [categoryValue, setCategoryValue] = useState<ExpenseCategory>("Lainnya");
  const [priceValue, setPriceValue] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!item) return;
    setDateValue(item.date);
    setNameValue(item.name);
    setCategoryValue(item.category);
    setPriceValue(String(item.price));
    setErrorMessage(null);
    setIsSubmitting(false);
  }, [item]);

  useEffect(() => {
    if (!item) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [item, isSubmitting, onClose]);

  if (!item) {
    return null;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (isSubmitting) return;
    setErrorMessage(null);

    const trimmedDate = dateValue.trim();
    const trimmedName = nameValue.trim();
    const parsedPrice = parseStrictNonNegativeInt(priceValue);

    if (!isValidIsoCalendarDate(trimmedDate)) {
      setErrorMessage("Tanggal transaksi wajib diisi dengan tanggal kalender yang valid.");
      return;
    }
    if (!trimmedName) {
      setErrorMessage("Nama barang tidak boleh kosong.");
      return;
    }
    if (!isValidCategory(categoryValue)) {
      setErrorMessage("Kategori pengeluaran tidak valid.");
      return;
    }
    if (parsedPrice === null) {
      setErrorMessage("Harga barang harus berupa bilangan bulat minimal 0.");
      return;
    }

    setIsSubmitting(true);
    try {
      const resp = await updateItem(item.id, {
        date: trimmedDate,
        name: trimmedName,
        category: categoryValue,
        price: parsedPrice,
      });
      onUpdated(resp.data);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menyimpan perubahan item.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="v2-edit-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl sm:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3
            id="v2-edit-modal-title"
            className="text-lg font-bold text-slate-900"
          >
            Edit Item Pengeluaran
          </h3>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={onClose}
            aria-label="Tutup modal edit"
            className="rounded-lg px-2 py-1 text-xl leading-none text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
          >
            &times;
          </button>
        </div>

        {errorMessage ? (
          <div
            role="alert"
            className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-800"
          >
            {errorMessage}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="v2-edit-date"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Tanggal Transaksi <span className="text-red-600">*</span>
            </label>
            <input
              id="v2-edit-date"
              type="date"
              value={dateValue}
              disabled={isSubmitting}
              onChange={(e) => setDateValue(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>

          <div>
            <label
              htmlFor="v2-edit-name"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Nama Barang <span className="text-red-600">*</span>
            </label>
            <input
              id="v2-edit-name"
              type="text"
              maxLength={200}
              value={nameValue}
              disabled={isSubmitting}
              onChange={(e) => setNameValue(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>

          <div>
            <label
              htmlFor="v2-edit-category"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Kategori <span className="text-red-600">*</span>
            </label>
            <select
              id="v2-edit-category"
              value={categoryValue}
              disabled={isSubmitting}
              onChange={(e) =>
                setCategoryValue(e.target.value as ExpenseCategory)
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              {EXPENSE_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="v2-edit-price"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Harga (Rp — bilangan bulat) <span className="text-red-600">*</span>
            </label>
            <input
              id="v2-edit-price"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              value={priceValue}
              disabled={isSubmitting}
              onChange={(e) => setPriceValue(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>

          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={onClose}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:opacity-50"
            >
              {isSubmitting ? "Menyimpan..." : "Simpan Perubahan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
