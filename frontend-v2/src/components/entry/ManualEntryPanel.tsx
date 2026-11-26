import { useState, type FormEvent } from "react";
import { ApiClientError } from "../../api/client";
import { createTransaction } from "../../api/transactions";
import { DEFAULT_CATEGORY } from "../../constants/categories";
import type { EditableItemDraft } from "../../types/api";
import {
  createEmptyDraftRow,
  formatDateHuman,
  getTodayIsoDate,
  isValidIsoCalendarDate,
} from "../../utils/formatters";
import { validateEntryForm } from "../../utils/validation";
import { EditableItemsList } from "./EditableItemsList";

interface ManualEntryPanelProps {
  onSavedSuccess: (message: string) => void;
}

export function ManualEntryPanel({ onSavedSuccess }: ManualEntryPanelProps) {
  const [dateValue, setDateValue] = useState<string>(() => getTodayIsoDate());
  const [dateError, setDateError] = useState<string | null>(null);
  const [items, setItems] = useState<EditableItemDraft[]>(() => [
    createEmptyDraftRow(DEFAULT_CATEGORY),
  ]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const resetForm = () => {
    setDateValue(getTodayIsoDate());
    setDateError(null);
    setItems([createEmptyDraftRow(DEFAULT_CATEGORY)]);
    setValidationError(null);
  };

  const handleUpdateRow = (
    localId: string,
    patch: Partial<Pick<EditableItemDraft, "name" | "category" | "price">>,
  ) => {
    setItems((prev) =>
      prev.map((row) =>
        row.localId === localId
          ? {
              ...row,
              ...patch,
              nameError: patch.name !== undefined ? undefined : row.nameError,
              categoryError:
                patch.category !== undefined ? undefined : row.categoryError,
              priceError: patch.price !== undefined ? undefined : row.priceError,
            }
          : row,
      ),
    );
  };

  const handleRemoveRow = (localId: string) => {
    setItems((prev) => prev.filter((row) => row.localId !== localId));
  };

  const handleAddRow = () => {
    setItems((prev) => [...prev, createEmptyDraftRow(DEFAULT_CATEGORY)]);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (isSaving) return;
    setValidationError(null);

    const validation = validateEntryForm(dateValue, items);
    setItems(validation.validatedDrafts);
    setDateError(validation.dateError);

    if (!validation.isValid) {
      setValidationError(validation.bannerError);
      return;
    }

    setIsSaving(true);
    try {
      const response = await createTransaction({
        date: dateValue.trim(),
        items: validation.payloadItems,
      });

      const savedCount = response.data.items.length;
      const savedDate = response.data.date;
      resetForm();
      onSavedSuccess(
        `Berhasil mencatat manual ${savedCount} barang untuk tanggal ${formatDateHuman(savedDate)}.`,
      );
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menyimpan pengeluaran manual ke database.";
      setValidationError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="rounded-2xl border border-brand-200 bg-white p-4 shadow-md sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-900 sm:text-lg">
            Input Pengeluaran Manual
          </h3>
          <p className="mt-0.5 text-xs text-slate-600 sm:text-sm">
            Catat pengeluaran tanpa struk fisik (misal parkir, transportasi, jajan tunai) lalu tekan{" "}
            <strong>Konfirmasi &amp; Simpan</strong>.
          </p>
        </div>
        <span className="inline-flex items-center rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
          Tanpa Struk
        </span>
      </div>

      {validationError ? (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {validationError}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} noValidate>
        <div className="mb-5 max-w-xs">
          <label
            htmlFor="v2-manual-date"
            className="mb-1.5 block text-sm font-semibold text-slate-800"
          >
            Tanggal Transaksi <span className="text-red-600">*</span>
          </label>
          <input
            id="v2-manual-date"
            type="date"
            value={dateValue}
            disabled={isSaving}
            onChange={(e) => {
              const nextVal = e.target.value;
              setDateValue(nextVal);
              if (isValidIsoCalendarDate(nextVal)) {
                setDateError(null);
              }
            }}
            className={`w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 ${
              dateError
                ? "border-red-500 bg-red-50 focus:ring-red-200"
                : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
            }`}
          />
          <p
            className={`mt-1 text-xs ${
              dateError ? "font-semibold text-red-600" : "text-slate-500"
            }`}
          >
            {dateError ?? "Default tanggal hari ini (format YYYY-MM-DD)."}
          </p>
        </div>

        <EditableItemsList
          items={items}
          disabled={isSaving}
          addLabel="+ Tambah Barang"
          estimateLabel="Estimasi Total Input"
          onUpdateRow={handleUpdateRow}
          onRemoveRow={handleRemoveRow}
          onAddRow={handleAddRow}
        />

        <div className="mt-5 flex flex-col-reverse gap-2.5 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={isSaving}
            onClick={resetForm}
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            Reset Form
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center justify-center rounded-lg bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:opacity-50"
          >
            {isSaving ? "Menyimpan..." : "Konfirmasi & Simpan"}
          </button>
        </div>
      </form>
    </div>
  );
}
